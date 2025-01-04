from __future__ import annotations

import datetime
import json
import logging

from http import HTTPStatus
from typing import Any, cast

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import TemplateView

from literev.forms import HistoricalForm, SearchForm
from literev.libs.historical_functions import (
    filter_and_sort_projects,
    sort_all_projects,
)
from literev.libs.nlp import nlp_topic_description
from literev.libs.pipeline import (
    running_restart,
)
from literev.libs.project_workflows import (
    handle_filters_submission,
    prepare_update_context,
    projectpage_load_final_results,
    validate_project_access,
)
from literev.libs.select_functions import (
    create_refinement,
    download_finalcsv,
    get_filters,
    get_rendered_filters,
    remove_refinement,
)
from literev.libs.table_choice import (
    create_iteration,
    get_iteration,
    get_json_iterations_render,
    iterate_check_list,
    remove_iteration_get_parent,
    render_table_choice,
    reset_table_choice,
    sort_table_choice,
    update_check_list_iteration,
    update_checked_document_page,
    update_new_table_choice,
)
from literev.libs.utils import (
    get_number_documents,
)
from literev.models import (
    Cluster,
    Document,
    Project,
    ProjectRAG,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
    User,
)
from literev.tasks import (
    get_shared_projects_ids,
    launch_process,
    remove_all_finished_projects,
    running_delete,
)

logging.basicConfig(level=logging.INFO)


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
    context: dict[str, Any] = {}

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
    context: dict[str, Any] = {}
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
        Project.objects.filter(
            Q(user=user) | Q(id__in=get_shared_projects_ids())
        )
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

    This view handles project refinement operations, including filtering,
    updates, and deletion.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object.
    project_id : int | None
        The ID of the project.

    Returns
    -------
    HttpResponse
        Rendered response for the project page.
    """
    user = request.user
    context = {"errors": []}
    actual_user = request.user

    project = validate_project_access(user, project_id)
    if not project:
        context["errors"].append("Project not found or access denied.")
        return redirect(reverse("search"))

    if not (project.is_finish or project.step in ["clustering", "plotting"]):
        return redirect(reverse("search"))

    context["is_finish"] = project.is_finish

    if request.method == "POST":
        if request.POST.get("get-refinement"):
            refinement_id = request.POST.get("get-refinement")

            if refinement_id:
                # get refinement and go the table select
                return redirect(
                    reverse(
                        "tableselect-default",
                        kwargs={
                            "project_id": project.id,
                            "refinement_id": int(refinement_id),
                        },
                    )
                )

        if request.POST.get("remove-refinement"):
            refinement_id = request.POST.get("remove-refinement")

            if refinement_id:
                remove_refinement(actual_user, project, int(refinement_id))

        submit = request.POST.get("submit")

        if submit == "filters":
            filters = get_filters(request.POST)
            context.update(handle_filters_submission(user, project, filters))

        elif submit == "update":
            context.update(prepare_update_context(project))

        elif submit == "remove-refinement":
            refinement_id = request.POST.get("remove-refinement")
            if refinement_id:
                remove_refinement(user, project, int(refinement_id))

        elif submit == "confirm_delete_project":
            running_delete(request.POST["project_id"])
            return redirect(reverse("running"))

        elif submit == "continue":
            document_pk_list_str = request.POST.get("document_pk_list", "")
            document_pk_list = [int(pk) for pk in document_pk_list_str.split()]

            filters_json = json.loads(request.POST.get("filters", ""))

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
                filters_json,
            )

            create_iteration(actual_user, project, new_refinement_id)

            return redirect(
                reverse(
                    "tableselect-default",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": new_refinement_id,
                    },
                )
            )

    context.update(projectpage_load_final_results(user, project))

    return render(request, "projectpage.html", context)


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
    iteration_id: int = -1,
    num: int = 1,
    order_by: str = "decision_date",
) -> HttpResponse:
    context: dict[str, Any] = {}
    context["iterations_limit_exceeded"] = False
    context["processing_filters"] = False
    context["has_es_scores"] = False

    actual_user = request.user

    # Fetch the project ensuring access control for non-admin projects
    project = Project.objects.filter(
        Q(id=project_id)
        & (Q(user=actual_user) | Q(id__in=get_shared_projects_ids()))
    ).first()

    if not project:
        return redirect(reverse("search"))
    context["project"] = project
    # enable processing message if needed
    # To check if it is running iteration process (for unfinished and finished projects)
    # here is using project.step_number instead of project.step field
    # project.step is could be being used in clustering step or plotting step
    # as flag. The number 50 is just a selected number for iteration process
    if project.step_number == 50:
        context["processing_filters"] = True
        return render(request, "tableselect.html", context)

    # get iteration_id if not given
    if iteration_id == -1:
        last_iteration = RefinementIteration.objects.filter(
            refinement_id=refinement_id
        ).last()
        if last_iteration:
            iteration_id = last_iteration.id
            get_iteration(actual_user, project, refinement_id, iteration_id)
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "iteration_id": iteration_id,
                        "num": 1,
                        "order_by": "decision_date",
                    },
                )
            )

    if iteration_id == -1:
        return redirect(reverse("search"))

    # validate page number
    # Handle pagination: Ensure current page is valid and falls within the allowed range
    current_page = max(1, num)

    tablechoice = TableChoice.objects.filter(user=actual_user, project=project)
    tablechoice_to_display = tablechoice.filter(to_display=True)
    total_documents = tablechoice_to_display.count()

    total_pages = max(
        1,
        (total_documents + settings.NUMBER_ARTICLE_BY_PAGE - 1)
        // settings.NUMBER_ARTICLE_BY_PAGE,
    )

    if current_page > total_pages:
        current_page = total_pages

    context["sort_by"] = order_by

    # Pagination: calculate the correct slice of documents
    first_document = (current_page - 1) * settings.NUMBER_ARTICLE_BY_PAGE
    last_document = min(
        current_page * settings.NUMBER_ARTICLE_BY_PAGE, total_documents
    )

    sorted_table_choice = sort_table_choice(
        project, tablechoice_to_display, order_by
    )

    sorted_page_table_choice = sorted_table_choice[
        first_document:last_document
    ]

    # Handle POST request for action buttons (iterate, reset, finish, navigation)
    if request.method == "POST":
        # Used for debbuging
        # for k, v in request.POST.items():
        #     print(k, v)

        check_list_yes = [
            int(table_id) for table_id in request.POST.getlist("yes_row", [])
        ]
        check_list_no = [
            int(table_id) for table_id in request.POST.getlist("no_row", [])
        ]
        check_list_maybe = [
            int(table_id) for table_id in request.POST.getlist("maybe_row", [])
        ]

        if request.POST.get("get-iteration") is not None:
            dest_iteration_id = request.POST.get("get-iteration")

            if dest_iteration_id is not None:
                get_iteration(
                    actual_user, project, refinement_id, int(dest_iteration_id)
                )
                # add a redirect tableselect
                return redirect(
                    reverse(
                        "tableselect",
                        kwargs={
                            "project_id": project_id,
                            "refinement_id": refinement_id,
                            "iteration_id": int(dest_iteration_id),
                            "num": 1,
                            "order_by": "decision_date",
                        },
                    )
                )

        if request.POST.get("remove-iteration") is not None:
            removed_iteration_id = request.POST.get("remove-iteration")

            if removed_iteration_id is not None:
                parent_id = remove_iteration_get_parent(
                    actual_user,
                    project,
                    refinement_id,
                    int(removed_iteration_id),
                )

                if parent_id and iteration_id == int(removed_iteration_id):
                    get_iteration(
                        actual_user, project, refinement_id, parent_id
                    )

                    return redirect(
                        reverse(
                            "tableselect",
                            kwargs={
                                "project_id": project_id,
                                "refinement_id": refinement_id,
                                "iteration_id": parent_id,
                                "num": 1,
                                "order_by": "decision_date",
                            },
                        )
                    )

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
                update_checked_document_page(
                    user=actual_user,
                    project=project,
                    check_list_yes=check_list_yes,
                    check_list_no=check_list_no,
                    check_list_maybe=check_list_maybe,
                )

                update_check_list_iteration(actual_user, project, iteration_id)

                iterate_check_list(
                    actual_user,
                    project,
                    refinement_id,
                    iteration_id,
                )

                return redirect(
                    reverse(
                        "tableselect-default",
                        kwargs={
                            "project_id": project_id,
                            "refinement_id": refinement_id,
                        },
                    )
                )

        elif submit == "reset":
            reset_table_choice(
                user=actual_user, project=project, refinement_id=refinement_id
            )

            return redirect(
                reverse(
                    "tableselect-default",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                    },
                )
            )

        elif submit == "finish":
            update_checked_document_page(
                user=actual_user,
                project=project,
                check_list_yes=check_list_yes,
                check_list_no=check_list_no,
                check_list_maybe=check_list_maybe,
            )

            return download_finalcsv(project=project)

        elif submit == "update_order":
            order_by = request.POST.get("update_order_by")
            update_checked_document_page(
                user=actual_user,
                project=project,
                check_list_yes=check_list_yes,
                check_list_no=check_list_no,
                check_list_maybe=check_list_maybe,
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "iteration_id": iteration_id,
                        "num": 1,
                        "order_by": order_by,
                    },
                )
            )

        elif submit == "previous" and current_page > 1:
            update_checked_document_page(
                user=actual_user,
                project=project,
                check_list_yes=check_list_yes,
                check_list_no=check_list_no,
                check_list_maybe=check_list_maybe,
            )

            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "iteration_id": iteration_id,
                        "num": current_page - 1,
                        "order_by": order_by,
                    },
                )
            )

        elif submit == "next" and current_page < total_pages:
            update_checked_document_page(
                user=actual_user,
                project=project,
                check_list_yes=check_list_yes,
                check_list_no=check_list_no,
                check_list_maybe=check_list_maybe,
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": project_id,
                        "refinement_id": refinement_id,
                        "iteration_id": iteration_id,
                        "num": current_page + 1,
                        "order_by": order_by,
                    },
                )
            )

    tablechoice_list, has_hdbscan_scores, has_es_scores = render_table_choice(
        project, sorted_page_table_choice
    )

    context["hdbscan_scores"] = has_hdbscan_scores
    context["has_es_scores"] = has_es_scores

    # Disable sorting by similar keywords
    # WORKAROUND to enable check why is taking long time
    # keywords = load_tfidf_keywords(project)
    # context["keywords"] = keywords

    context["tablechoice_list"] = tablechoice_list
    context["first_page"] = current_page == 1
    context["last_page"] = current_page == total_pages
    context["current_page"] = current_page
    context["total_page"] = total_pages

    # Count the initial documents, neighbors, and checked documents
    context["number_Article_initial"] = tablechoice.filter(
        is_initial=True
    ).count()
    context["number_Article_neighbour"] = tablechoice.filter(
        is_initial=False, to_display=True, is_check=False
    ).count()
    context["number_Article_chosen"] = tablechoice.filter(
        is_check=True
    ).count()

    iterations_render = get_json_iterations_render(refinement_id, iteration_id)
    context["iterations"] = iterations_render

    _refinement = ProjectRefinement.objects.filter(id=refinement_id).first()

    union_sets_str = ""
    excluded_set_str = ""

    if _refinement:
        try:
            raw_filter = json.loads(_refinement.filters)
            if raw_filter and not isinstance(raw_filter, str):
                union_sets_str, excluded_set_str = get_rendered_filters(
                    raw_filter
                )
        except Exception as e:
            logging.warning(
                f"An error ocurred: {e}, refinement id:{refinement_id}"
            )

    context["union_sets_str"] = union_sets_str
    context["excluded_set_str"] = excluded_set_str
    context["project_id"] = project_id
    context["iteration_id"] = iteration_id

    return render(request, "tableselect.html", context)


@login_required(login_url="/accounts/login/")
def contentdocument(request: HttpRequest, document_id: int) -> HttpResponse:
    context: dict[str, Any] = {}

    if not document_id:
        return redirect(reverse("search"))

    document = Document.objects.get(pk=document_id)

    context["document"] = document

    return render(request, "contentdocument.html", context)


def historicalpage(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = {}

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
            (Q(user=user) & Q(is_finish=True))
            | Q(id__in=get_shared_projects_ids())
        ).order_by("-id")

        if project_list.exists():
            context["projects_list"] = project_list

    return render(request, "historicalpage.html", context)


@login_required(login_url="/accounts/login/")
def rag(
    request: HttpRequest,
    project_id: int,
) -> HttpResponse:
    context: dict[str, Any] = dict(
        project_id=project_id,
    )

    project = Project.objects.filter(id=project_id).first()

    if not project:
        return redirect(reverse("search"))

    table_choice = TableChoice.objects.filter(
        project=project,
        user=cast(User, request.user),
        is_check=True,
    )

    documents_ids = list(table_choice.values_list("document_id", flat=True))

    project_rag = ProjectRAG.objects.filter(project=project).last()

    context["project_rag_id"] = project_rag.id if project_rag else None
    context["documents_ids"] = documents_ids
    context["number_documents"] = len(documents_ids)

    return render(request, "rag.html", context)


# Menu section
def product(request: HttpRequest) -> HttpResponse:
    return render(request, "product.html")


def company(request: HttpRequest) -> HttpResponse:
    return render(request, "company.html")


def blog(request: HttpRequest) -> HttpResponse:
    return render(request, "blog.html")


def team(request: HttpRequest) -> HttpResponse:
    return render(request, "team.html")
