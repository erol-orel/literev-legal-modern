from __future__ import annotations

import datetime
import logging

from django.db.models import Count, Q

logging.basicConfig(level=logging.INFO)

from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from literev.forms import SearchForm
from literev.libs.nlp import nlp_topic_description
from literev.libs.pipeline import (
    get_color_map,
    running_restart,
)
from literev.libs.select_functions import (
    download_finalcsv,
    get_filtered_document,
    get_filters,
)
from literev.libs.table_choice import (
    reset_table_choice,
    update_article_is_check_table_choice,
    update_article_to_display_table_choice,
    update_neighbour_table_choice,
    update_new_table_choice,
)
from literev.libs.utils import (
    count_all_corpus,
    get_number_documents,
    process_all_documents,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    TableChoice,
)
from literev.tasks import launch_process, running_delete

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


class HomePageView(TemplateView):
    template_name = "home.html"


def search_search(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    search_form = SearchForm(request.POST)
    context["search_form"] = search_form

    if search_form.is_valid():
        project_name = search_form.cleaned_data["project_name"]
        query = search_form.cleaned_data["query"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        total_documents = get_number_documents(
            query, range_begin_date, range_end_date
        )

        # enable continue message box
        context["continue_message_box"] = True

        new_data = {
            "project_name": project_name,
            "query": query,
            "range_begin_date": range_begin_date.strftime("%Y/%m/%d"),
            "range_end_date": range_end_date.strftime("%Y/%m/%d"),
            "total_documents": total_documents,
        }
        logging.info("updating request session")
        # update context variables
        context.update(new_data)
        # save in request session the data
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

    project = Project.objects.create(
        user=user,
        name=project_name,
        creation_date=datetime.datetime.now(),
        query=query,
        range_begin_date=range_begin_date,
        range_end_date=range_end_date,
        total_documents=total_documents,
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
    documents.

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

    if search_form.is_valid():
        query = search_form.cleaned_data["query"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        total_documents = get_number_documents(
            query, range_begin_date, range_end_date
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
        query_text = SearchForm(request.POST)["query"].value()
        if query_text == "#COUNT-ALL-CORPUS-LITEREV-00":
            result_all = count_all_corpus()
            logging.info("counting all corpus")
            logging.info(result_all)

        elif query_text == "#PROCESS-ALL-CORPUS-LITEREV-00":
            process_all_documents()
            logging.info("processing all corpus")

        else:
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
    projects = Project.objects.filter(Q(user=user) | Q(id=1)).order_by("-id")

    context["projects"] = projects

    return render(request, "running.html", context)


@login_required(login_url="/accounts/login/")
def previousgraph(request: HttpRequest) -> HttpResponse:
    """
    Display the Refine project page.

    This view displays the Refine project page. It shows the list of clusters
    and documents, and allows the user to select a subset of articles to
    continue with the project. It also displays the graph of the project.

    Parameters
    ----------
    request : HttpRequest
        The request object.

    Returns
    -------
    HttpResponse
        The response object.
    """
    context: dict[str, Any] = {}
    context["AreYouSure"] = False

    project_id = request.GET.get("project_id")
    if not project_id:
        return redirect("/search")

    actual_user = request.user
    project_exist = (
        Project.objects.filter(id=project_id).exists()
        if project_id == "1"
        else Project.objects.filter(user=actual_user, id=project_id).exists()
    )

    if not project_exist:
        return redirect("/search")

    project = Project.objects.filter(id=project_id).first()
    if not project or not project.is_finish:
        return redirect("/search")

    if request.method == "POST":
        submit = request.POST.get("submit")

        if submit == "filters":
            filters = get_filters(request.POST)
            document_pk_list = get_filtered_document(
                project=project, filters=filters
            )
            request.session["document_pk_list"] = document_pk_list
            request.session["id_project"] = project_id
            context["number_article"] = len(document_pk_list)
            context["AreYouSure"] = True

        elif submit == "continue":
            update_new_table_choice(
                project=project,
                document_id_list=request.session["document_pk_list"],
            )
            return redirect(f"/tableselect?project_id={project_id}")

    context.update(
        {
            "project": project,
            "cluster_list": ClusterElement.objects.filter(
                cluster__project=project
            ),
            "documents_list": Document.objects.filter(project=project),
            "project_id": project_id,
        }
    )

    context.update(load_plot_data(project.pk))

    cluster_list = Cluster.objects.filter(project=project).values_list(
        "topic", flat=True
    )
    context["list_topics"] = list(set(cluster_list))

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

    return render(request, "previousgraph.html", context)


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
        .order_by("-total_documents")
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
    for cluster in grouped_clusters:
        if cluster["topic"] == UNCLASSIFIED_PAPERS_TOPIC:
            continue
        index += 1
        number__topic10_cluster = (
            f"{index}: {', '.join(cluster['topic'].split(', ')[:10])}"
        )
        list_topic_10.append(number__topic10_cluster)
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
def tableselect(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = {}

    project_id = request.POST.get("project_id") or request.GET.get(
        "project_id"
    )
    if not project_id:
        return redirect("/search")

    actual_user = request.user

    # Fetch the project ensuring access control for non-admin projects
    project = Project.objects.filter(
        Q(id=project_id) & (Q(user=actual_user) | Q(id="1"))
    ).first()

    if not project:
        return redirect("/search")

    # Handle pagination: Ensure current page is valid and falls within the allowed range
    current_page = max(1, int(request.GET.get("page", 1)))
    total_documents = TableChoice.objects.filter(project=project).count()
    total_pages = max(
        1,
        (total_documents + settings.NUMBER_ARTICLE_BY_PAGE - 1)
        // settings.NUMBER_ARTICLE_BY_PAGE,
    )

    if current_page > total_pages:
        current_page = total_pages

    # Prioritize order_by from POST if available, else fallback to GET
    order_by = request.POST.get("order_by") or request.GET.get(
        "order_by", "-document__decision_date"
    )

    # Map order_by fields to correct ForeignKey fields in TableChoice
    valid_order_by_fields = {
        "decision_date": "document__decision_date",
        "-decision_date": "-document__decision_date",
    }

    # Ensure the order_by field is valid, defaulting if not found
    order_by = valid_order_by_fields.get(order_by, "-document__decision_date")
    print(f"Ordenando por: {order_by}")

    # Fetch the TableChoice list ordered and paginated
    tablechoice_list = TableChoice.objects.filter(
        project=project,
        to_display=True,
    ).order_by(order_by)

    # Handle POST request for action buttons (iterate, reset, finish, navigation)
    if request.method == "POST":
        check_list = list(map(int, request.POST.getlist("check_row", [])))
        submit = request.POST.get("submit")

        if submit == "iterate":
            update_article_is_check_table_choice(
                project=project, list_id=check_list
            )
            update_article_to_display_table_choice(
                project=project, list_id=check_list
            )
            update_neighbour_table_choice(project=project)
            return redirect(f"/tableselect?project_id={project.id}")

        elif submit == "reset":
            reset_table_choice(project=project)
            return redirect(f"/tableselect?project_id={project.id}")

        elif submit == "finish":
            update_article_is_check_table_choice(
                project=project, list_id=check_list
            )
            update_article_to_display_table_choice(
                project=project, list_id=check_list
            )
            return download_finalcsv(project=project)

        elif submit == "previous" and current_page > 1:
            update_article_is_check_table_choice(
                project=project, list_id=check_list
            )
            return redirect(
                f"/tableselect?project_id={project.id}&page={current_page - 1}"
            )

        elif submit == "next" and current_page < total_pages:
            update_article_is_check_table_choice(
                project=project, list_id=check_list
            )
            return redirect(
                f"/tableselect?project_id={project.id}&page={current_page + 1}"
            )

    # Pagination: calculate the correct slice of documents
    first_article = (current_page - 1) * settings.NUMBER_ARTICLE_BY_PAGE
    last_article = min(
        current_page * settings.NUMBER_ARTICLE_BY_PAGE, total_documents
    )
    context["tablechoice_list"] = tablechoice_list[first_article:last_article]
    context["first_page"] = current_page == 1
    context["last_page"] = current_page == total_pages
    context["current_page"] = current_page
    context["total_page"] = total_pages

    # Count the initial articles, neighbors, and checked articles
    context["number_Article_initial"] = TableChoice.objects.filter(
        project=project, is_initial=True
    ).count()
    context["number_Article_neighbour"] = TableChoice.objects.filter(
        project=project, is_initial=False, to_display=True, is_check=False
    ).count()
    context["number_Article_chosen"] = TableChoice.objects.filter(
        project=project, is_check=True
    ).count()

    return render(request, "tableselect.html", context)


@login_required(login_url="/accounts/login/")
def contentdocument(request: HttpRequest, document_id: int) -> HttpResponse:
    context: dict[str, Any] = dict()

    if not document_id:
        return redirect("/search")

    document = Document.objects.get(pk=document_id)

    context["document"] = document

    return render(request, "contentdocument.html", context)
