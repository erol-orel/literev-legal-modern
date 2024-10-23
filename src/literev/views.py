from __future__ import annotations

import datetime
import logging

from django.db.models import Count, Q
from django.urls import reverse

logging.basicConfig(level=logging.INFO)

from http import HTTPStatus
from typing import Any, cast

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from literev.forms import HistoricalForm, SearchForm
from literev.libs.data_files import get_es_scores, load_tfidf_keywords
from literev.libs.historical_functions import (
    filter_and_sort_projects,
    sort_all_projects,
)
from literev.libs.nlp import nlp_topic_description
from literev.libs.pipeline import (
    running_restart,
)
from literev.libs.select_functions import (
    create_refinement,
    download_finalcsv,
    get_filtered_document,
    get_filters,
    get_raw_filters,
    load_last_iteration,
    remove_refinement,
)
from literev.libs.table_choice import (
    create_iteration,
    get_iteration,
    get_json_iterations_render,
    iterate_check_list,
    remove_iteration,
    render_table_choice,
    reset_table_choice,
    update_document_is_check_table_choice,
    update_document_to_display_table_choice,
    update_new_table_choice,
)
from literev.libs.utils import (
    get_number_documents,
)
from literev.models import (
    Cluster,
    Document,
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
    User,
)
from literev.task_plotting import get_color_map
from literev.tasks import (
    launch_process,
    remove_all_finished_projects,
    running_delete,
)

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


class HomePageView(TemplateView):
    template_name = "home.html"


def search_search(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    """
    Handles the search functionality and initiates project creation based on the selected indices.

    Parameters
    ----------
    request : HttpRequest
        The request object containing form data.
    context : dict[str, Any]
        The context dictionary to be passed to the template.

    Returns
    -------
    dict[str, Any]
        The updated context dictionary.
    """
    search_form = SearchForm(request.POST)
    context["search_form"] = search_form

    # Capture the selected indices from the POST request
    selected_indices = request.POST.get("selected_indices", "").split(",")
    context["selected_indices"] = selected_indices

    if search_form.is_valid():
        project_name = search_form.cleaned_data["project_name"]
        query = search_form.cleaned_data["query"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        # Calculate total documents for each selected index
        total_documents = sum(
            get_number_documents(
                index_name, query, range_begin_date, range_end_date
            )
            for index_name in selected_indices
        )

        # Enable the continue message box if criteria are met
        context["continue_message_box"] = True

        # Update context and session with the new data
        new_data = {
            "project_name": project_name,
            "query": query,
            "range_begin_date": range_begin_date.strftime("%Y/%m/%d"),
            "range_end_date": range_end_date.strftime("%Y/%m/%d"),
            "total_documents": total_documents,
            "selected_indices": selected_indices,  # Store selected indices in session
        }

        logging.info(
            "Updating request session with project details and selected indices."
        )
        context.update(new_data)
        request.session.update(new_data)

    return context


def search_continue(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    # use when implement login
    user = request.user
    project_name = request.session["project_name"]
    query = request.session["query"]
    range_begin_date = datetime.datetime.strptime(
        request.session["range_begin_date"], "%Y/%m/%d"
    ).date()
    range_end_date = datetime.datetime.strptime(
        request.session["range_end_date"], "%Y/%m/%d"
    ).date()

    total_documents = request.session["total_documents"]

    selected_indices = request.session["selected_indices"]

    project = Project.objects.create(
        user=user,
        name=project_name,
        creation_date=datetime.datetime.now(),
        query=query,
        range_begin_date=range_begin_date,
        range_end_date=range_end_date,
        total_documents=total_documents,
        selected_indices=selected_indices,
    )

    result = launch_process(project)

    if result:
        context["message_project_created"] = (
            "You project has been created and is running"
        )
    else:
        context["message_project_created"] = "error in launching project"

    return context


def search_evaluate(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    """
    Evaluate the search form and update the context with the total number of
    documents and selected indices.

    Parameters
    ----------
    request : HttpRequest
        The request object.
    context : dict[str, Any]
        The context dictionary.

    Returns
    -------
    dict[str, Any]
        The updated context.
    """
    search_form = SearchForm(request.POST)
    context["search_form"] = search_form

    # Capture the selected indices from the POST request
    selected_indices = request.POST.get("selected_indices", "").split(",")
    context["selected_indices"] = selected_indices

    if search_form.is_valid():
        query = search_form.cleaned_data["query"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        # Calculate total documents for each selected index
        total_documents = sum(
            get_number_documents(
                index_name, query, range_begin_date, range_end_date
            )
            for index_name in selected_indices
        )

        context["total_documents"] = total_documents

    return context


@login_required(login_url="/accounts/login/")
def search(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()

    # Actual form
    search_form = SearchForm()
    context["search_form"] = search_form

    # Aditional variables
    context["continue_message_box"] = False
    context["project_created_message"] = ""

    # if there no click in evaluate or create project
    # total documents = -1
    context["total_documents"] = -1

    if request.method != "POST":
        context["search_form"] = SearchForm()
        return render(request, "search.html", context)

    submit = request.POST["submit"]

    if submit == "search":
        context = search_search(request, context)

    elif submit == "evaluate":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        context = search_evaluate(request, context)

    elif submit == "continue":
        context = search_continue(request, context)

    elif submit == "cancel":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        pass

    return render(request, "search.html", context)


@login_required(login_url="/accounts/login/")
def running(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()
    context["delete_message"] = False
    user = request.user

    if request.method == "POST":
        submit = request.POST["submit"]

        if submit in ["reload", "cancel"]:
            pass

        if submit == "restart":
            logging.info("Restarting project")
            logging.info(request.POST)
            project_id = request.POST["project_id"]
            running_restart(project_id)

        if submit == "delete":
            project_id = request.POST["project_id"]
            project = Project.objects.filter(pk=project_id).first()
            context["project"] = project
            context["delete_message"] = True

        if submit == "confirm_delete":
            project_id = request.POST["project_id"]
            logging.info(f"Removing project: {project_id}")
            running_delete(project_id)

    # Include always the first project
    projects = (
        Project.objects.filter(Q(user=user) | Q(id=1))
        .exclude(is_finish=True)
        .order_by("-id")
    )

    context["projects"] = projects

    return render(request, "running.html", context)


@login_required(login_url="/accounts/login/")
def projectpage(
    request: HttpRequest, project_id: int | None = None
) -> HttpResponse:
    """
    Display the Refine project page.

    This view displays the Refine project page. It shows the list of clusters
    and documents, and allows the user to select a subset of documents to
    continue with the project. It also displays the graph of the project.

    Parameters
    ----------
    request : HttpRequest
        The request object.
    project_id : int
        identifier id of the project

    Returns
    -------
    HttpResponse
        The response object.
    """
    context: dict[str, Any] = {}
    context["AreYouSure"] = False
    context["confirm_delete_project"] = False
    context["refinement_limit_exceeded"] = False

    if not project_id:
        return redirect(reverse("search"))

    actual_user = request.user
    project_exist = (
        Project.objects.filter(id=project_id).exists()
        if project_id == 1
        else Project.objects.filter(user=actual_user, id=project_id).exists()
    )

    if not project_exist:
        return redirect(reverse("search"))

    project = Project.objects.filter(id=project_id).first()
    if not project or not project.is_finish:
        return redirect(reverse("search"))

    if request.method == "POST":
        if request.POST.get("get-refinement"):
            refinement_id = request.POST.get("get-refinement")

            if refinement_id:
                # get refinement and go the table select
                load_last_iteration(actual_user, project, int(refinement_id))

                return redirect(
                    reverse(
                        "tableselect",
                        kwargs={
                            "project_id": project.id,
                            "refinement_id": int(refinement_id),
                            "num": 1,
                            "order_by": "decision_date",
                        },
                    )
                )

        if request.POST.get("remove-refinement"):
            refinement_id = request.POST.get("remove-refinement")

            if refinement_id:
                remove_refinement(actual_user, project, int(refinement_id))

        submit = request.POST.get("submit")

        if submit == "filters":
            # check refinements limit
            refinement_limit = settings.LIMIT_NUMBER_REFINEMENTS
            refinement_number = ProjectRefinement.objects.filter(
                owner=actual_user, project=project
            ).count()

            if refinement_number >= refinement_limit:
                context["refinement_limit_exceeded"] = True
            else:
                filters = get_filters(request.POST)
                filters_str = get_raw_filters(request.POST)

                document_pk_list = get_filtered_document(
                    project=project, filters=filters
                )
                context["filters"] = filters_str
                context["document_pk_list"] = " ".join(
                    str(pk) for pk in document_pk_list
                )
                context["number_document"] = len(document_pk_list)
                context["AreYouSure"] = True

        elif submit == "delete":
            context["confirm_delete_project"] = True

        elif submit == "confirm_delete_project":
            project_id = request.POST["project_id"]
            running_delete(project_id)

            return redirect(reverse("running"))

        elif submit == "continue":
            document_pk_list_str = request.POST.get("document_pk_list", "")
            document_pk_list = [int(pk) for pk in document_pk_list_str.split()]

            filters_str = request.POST.get("filters", "")

            update_new_table_choice(
                user=actual_user,
                project=project,
                document_id_list=document_pk_list,
            )

            refinement_name = request.POST.get("refinement-name", "No name")

            number_documents = len(document_pk_list)

            new_refinement_id = create_refinement(
                actual_user,
                project,
                refinement_name,
                number_documents,
                filters_str,
            )

            # create iteration
            create_iteration(actual_user, project, new_refinement_id)

            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": new_refinement_id,
                        "num": 1,
                        "order_by": "decision_date",
                    },
                )
            )

    context.update(
        {
            "project": project,
            "project_id": project_id,
        }
    )

    context.update(load_plot_data(project.pk))

    cluster_list = (
        Cluster.objects.filter(project=project)
        .values_list("topic", flat=True)
        .order_by("order")
    )

    context["list_topics"] = list(cluster_list)

    grouped_clusters = get_grouped_clusters(project)

    context["list_number_topic10"] = format_grouped_clusters(grouped_clusters)

    topics, palette = get_color_map(context["list_topics"])

    context["topic_colors"] = dict(zip(topics, palette))

    context["standard_list"] = extract_refined_list(project)

    context["descriptors_list"] = extract_refined_list(
        project, is_descriptor=True
    )

    context["result_list"] = [
        "REJETE",
        "ADMIS",
        "PARTIELMNT ADMIS",
        "IRRECEVABLE",
        "REFUSE",
        "ACCORDE",
        "RETIRE",
        "SANS OBJECT",
        "NO RESULT",
    ]

    refinements = ProjectRefinement.objects.filter(
        owner=actual_user, project=project
    )
    context["refinements"] = refinements

    return render(request, "projectpage.html", context)


def load_plot_data(project_pk: int) -> dict[str, str]:
    """
    Load and return the div and script plot data.

    This function reads the div and script plot data from the files
    generated by the clustering and plotting task. It returns a dictionary
    with two keys: "div_plot" and "script_plot". The values associated with
    these keys are the contents of the files.

    Parameters
    ----------
    project_pk : int
        The primary key of the project for which to load the plot data.

    Returns
    -------
    dict[str, str]
        A dictionary with two keys: "div_plot" and "script_plot".
        The values associated with these keys are the contents of the
        files generated by the clustering and plotting task.
    """
    fname_project_div_plot = settings.PLOT_DATA / f"{project_pk}_div.html"
    fname_project_script_plot = (
        settings.PLOT_DATA / f"{project_pk}_script.html"
    )

    with open(fname_project_div_plot, "r") as f:
        div_plot = f.read()

    with open(fname_project_script_plot, "r") as f:
        script_plot = f.read()

    return {"div_plot": div_plot, "script_plot": script_plot}


def get_grouped_clusters(project: Project) -> list[dict]:
    """
    Return grouped clusters with total documents.

    This function returns a list of dictionaries, each with a "topic" key
    and a "total_documents" key. The list is ordered by "total_documents"
    in descending order.

    Parameters
    ----------
    project : Project
        The project for which to retrieve grouped clusters.

    Returns
    -------
    list[dict]
        A list of dictionaries, each with a "topic" key and a
        "total_documents" key.
    """
    return (
        Cluster.objects.filter(project=project)
        .values("topic")
        .annotate(total_documents=Count("clusterelement__document"))
        .order_by("order")
    )


def format_grouped_clusters(grouped_clusters: list[dict]) -> list[str]:
    """
    Format the grouped clusters for display.

    This function takes the grouped clusters and formats them for display
    by creating a list of strings with the index and the first 10 topics
    separated by commas. The unclassified papers cluster is excluded.

    Parameters
    ----------
    grouped_clusters : list[dict]
        The grouped clusters with total documents.

    Returns
    -------
    list[str]
        The formatted list of strings.
    """
    index = 0
    list_topic_10 = []
    exists_unclassified = False

    for cluster in grouped_clusters:
        if cluster["topic"] == UNCLASSIFIED_PAPERS_TOPIC:
            exists_unclassified = True
            continue
        index += 1
        number__topic10_cluster = (
            f"{index}: {', '.join(cluster['topic'].split(', ')[:10])}"
        )
        list_topic_10.append(number__topic10_cluster)

    if exists_unclassified:
        list_topic_10.append(UNCLASSIFIED_PAPERS_TOPIC)

    return list_topic_10


def extract_refined_list(
    project: Project, is_descriptor: bool = False
) -> list[str]:
    """
    Extract a refined list of standards or descriptors from the project documents.

    This function takes a project and a boolean flag indicating whether to extract
    descriptors or standards and returns a list of unique standards or descriptors
    from all the project documents, ordered by the result field.

    Parameters
    ----------
    project : Project
        The project from which the standards or descriptors are extracted.
    is_descriptor : bool
        A boolean flag indicating whether to extract descriptors or standards.
        Defaults to `False`, which means standards are extracted.

    Returns
    -------
    list[str]
        A list of unique standards or descriptors from all the project documents, ordered by the result field.
    """
    filter_field = "descriptors" if is_descriptor else "standards"

    filtered_list_raw = (
        Document.objects.filter(project=project)
        .order_by("result")
        .values_list(f"{filter_field}", flat=True)
    )

    filtered_list = set()
    for filter_value in filtered_list_raw:
        for value in filter_value.split(";"):
            filtered_list.add(value.strip())

    return sorted(filtered_list)


def generate_summary(request: HttpRequest, cluster_id: int) -> HttpResponse:
    """Generate a cluster topic summary text by calling openAI API"""

    # check if the request is ajax
    is_ajax = request.headers.get("X-Requested-With", None) == "XMLHttpRequest"

    # fails if request is not ajax
    if not is_ajax:
        return JsonResponse(
            {
                "message": (
                    "Invalid Request. X-Requested-With header "
                    "not found or not equal to XMLHttpRequest"
                )
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    # resolves POST requests only
    if request.method == "POST":
        # try to get cluster object
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse(
                {"message": f"Cluster with id={cluster_id} does not exist"},
                status=HTTPStatus.NOT_FOUND,
            )

        summary_text = nlp_topic_description(cluster)

        if not summary_text:
            # in case the openai service is still not
            # working and returning an empty string
            return JsonResponse(
                {
                    "message": "Service Unavailable",
                    "content": "It seems the service is still not available. Please, try again later.",
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        else:
            # update cluster summary text
            cluster.summary = summary_text
            cluster.save()
            return JsonResponse(
                {"message": "Success. Created.", "content": summary_text},
                status=HTTPStatus.CREATED,
            )
    else:
        # fails if request http method is not POST
        return JsonResponse(
            {"message": "Invalid Request. Http method should be POST"},
            status=HTTPStatus.BAD_REQUEST,
        )


@login_required(login_url="/accounts/login/")
def tableselect(
    request: HttpRequest,
    project_id: int,
    refinement_id: int,
    num: int = 1,
    order_by: str = "decision_date",
) -> HttpResponse:
    context: dict[str, Any] = {}
    context["active_iteration_id"] = -1
    context["iterations_limit_exceeded"] = False
    context["processing_filters"] = False
    context["active_iteration_id"] = -1
    context["has_es_scores"] = False

    if not project_id:
        return redirect(reverse("search"))

    if not refinement_id:
        return redirect(reverse("search"))

    actual_user = request.user

    # Fetch the project ensuring access control for non-admin projects
    project = Project.objects.filter(
        Q(id=project_id) & (Q(user=actual_user) | Q(id=1))
    ).first()

    if not project:
        return redirect(reverse("search"))

    sort_by = order_by
    context["sort_by"] = order_by

    # Handle pagination: Ensure current page is valid and falls within the allowed range
    current_page = max(1, num)
    total_documents = TableChoice.objects.filter(
        project=project, to_display=True
    ).count()

    total_pages = max(
        1,
        (total_documents + settings.NUMBER_ARTICLE_BY_PAGE - 1)
        // settings.NUMBER_ARTICLE_BY_PAGE,
    )

    if current_page > total_pages:
        current_page = total_pages

    # enable processing message if needed
    if project.step == "processing_filters":
        context["processing_filters"] = True
        return render(request, "tableselect.html", context)

    # Handle POST request for action buttons (iterate, reset, finish, navigation)
    if request.method == "POST":
        # Used for debbuging
        # for k, v in request.POST.items():
        #     print(k, v)

        check_list = []

        if "check_row" in request.POST:
            check_list = [
                int(table_id) for table_id in request.POST.getlist("check_row")
            ]

        if request.POST.get("get-iteration") is not None:
            iteration_id = request.POST.get("get-iteration")

            if iteration_id is not None:
                get_iteration(
                    actual_user, project, refinement_id, int(iteration_id)
                )
                context["active_iteration_id"] = int(iteration_id)

        if request.POST.get("remove-iteration") is not None:
            iteration_id = request.POST.get("remove-iteration")

            if iteration_id is not None:
                remove_iteration(
                    actual_user, project, refinement_id, int(iteration_id)
                )
                context["active_iteration_id"] = -1

        submit = request.POST.get("submit")

        if submit == "iterate":
            # Check iteration limit
            iterations_limit = settings.LIMIT_NUMBER_ITERATIONS
            iterations_number = RefinementIteration.objects.filter(
                refinement_id=refinement_id
            ).count()

            if iterations_number >= iterations_limit:
                context["iterations_limit_exceeded"] = True

            else:
                active_iteration_id = int(
                    request.POST.get("active_iteration_id", -1)
                )
                iterate_check_list(
                    actual_user,
                    project,
                    refinement_id,
                    check_list,
                    active_iteration_id,
                )

                return redirect(
                    reverse(
                        "tableselect",
                        kwargs={
                            "project_id": project_id,
                            "refinement_id": refinement_id,
                            "num": current_page,
                            "order_by": sort_by,
                        },
                    )
                )

        elif submit == "reset":
            reset_table_choice(
                user=actual_user, project=project, refinement_id=refinement_id
            )

            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                    },
                )
            )

        elif submit == "finish":
            update_document_is_check_table_choice(
                user=actual_user, project=project, list_id=check_list
            )
            update_document_to_display_table_choice(
                user=actual_user, project=project, list_id=check_list
            )
            return download_finalcsv(project=project)

        elif submit == "update_order":
            sort_by = request.POST.get("update_order_by")
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "num": current_page,
                        "order_by": sort_by,
                    },
                )
            )

        elif submit == "previous" and current_page > 1:
            update_document_is_check_table_choice(
                user=actual_user, project=project, list_id=check_list
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "num": current_page - 1,
                        "order_by": sort_by,
                    },
                )
            )

        elif submit == "next" and current_page < total_pages:
            update_document_is_check_table_choice(
                user=actual_user, project=project, list_id=check_list
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "num": current_page + 1,
                        "order_by": sort_by,
                    },
                )
            )

    # Fetch the TableChoice list ordered and paginated
    tablechoice_queryset = TableChoice.objects.filter(
        project=project,
        to_display=True,
    )

    # Check if the project has elasticsearch scores
    es_scores = get_es_scores(project)
    if es_scores:
        context["has_es_scores"] = True

    tablechoice_list, hdbscan_scores = render_table_choice(
        project, tablechoice_queryset, sort_by
    )

    context["hdbscan_scores"] = hdbscan_scores

    keywords = load_tfidf_keywords(project)

    context["keywords"] = keywords

    # Pagination: calculate the correct slice of documents
    first_document = (current_page - 1) * settings.NUMBER_ARTICLE_BY_PAGE
    last_document = min(
        current_page * settings.NUMBER_ARTICLE_BY_PAGE, total_documents
    )
    context["tablechoice_list"] = tablechoice_list[
        first_document:last_document
    ]
    context["first_page"] = current_page == 1
    context["last_page"] = current_page == total_pages
    context["current_page"] = current_page
    context["total_page"] = total_pages

    # Count the initial documents, neighbors, and checked documents
    context["number_Article_initial"] = TableChoice.objects.filter(
        project=project, is_initial=True
    ).count()
    context["number_Article_neighbour"] = TableChoice.objects.filter(
        project=project, is_initial=False, to_display=True, is_check=False
    ).count()
    context["number_Article_chosen"] = TableChoice.objects.filter(
        project=project, is_check=True
    ).count()

    input_active_iteration_id = int(
        request.POST.get("active_iteration_id", -1)
    )
    active_iteration_id = context.get(
        "active_iteration_id", input_active_iteration_id
    )

    iterations_render = get_json_iterations_render(
        refinement_id, active_iteration_id
    )

    context["iterations"] = iterations_render

    return render(request, "tableselect.html", context)


@login_required(login_url="/accounts/login/")
def contentdocument(request: HttpRequest, document_id: int) -> HttpResponse:
    context: dict[str, Any] = dict()

    if not document_id:
        return redirect(reverse("search"))

    document = Document.objects.get(pk=document_id)

    context["document"] = document

    return render(request, "contentdocument.html", context)


def historicalpage(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()

    historical_form = HistoricalForm()
    context["historical_form"] = historical_form
    context["filter_by_query"] = False

    user = cast(User, request.user)

    if request.method == "POST":
        submit = request.POST["submit"]

        if submit == "historical":
            historical_form = HistoricalForm(request.POST)
            context["historical_form"] = historical_form
            context["filter_by_query"] = True
            context["query_filter"] = ""

            if historical_form.is_valid():
                search = historical_form.cleaned_data["search"]

                keywords = search.split()
                sort_type = request.POST.get("sort_type", "")

                # filter according to keyword otherwise return
                # all project projects
                if keywords:
                    context["query_filter"] = search

                    context["projects_list"] = filter_and_sort_projects(
                        user, keywords, sort_type
                    )
                else:
                    context["projects_list"] = sort_all_projects(
                        user, sort_type
                    )

                return render(request, "historicalpage.html", context)

        if submit == "delete":
            project_id = int(request.POST["project_id"])
            project_name = request.POST["project_name"]
            project_query = request.POST["project_query"]
            context["delete_message"] = True
            context["project_id"] = project_id
            context["project_name"] = project_name
            context["project_query"] = project_query

        if submit == "confirm_delete":
            project_id = int(request.POST["project_id"])
            running_delete(project_id)

        if submit == "delete_all_finished":
            remove_all_finished_projects(user)

    if not context["filter_by_query"]:
        # get all finished project
        project_list = Project.objects.filter(
            (Q(user=user) & Q(is_finish=True)) | Q(id=1)
        ).order_by("-id")

        if project_list.exists():
            context["projects_list"] = project_list

    return render(request, "historicalpage.html", context)
