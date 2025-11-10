from __future__ import annotations

import datetime
import json
import logging

from http import HTTPStatus
from typing import Any, cast

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import (
    HttpRequest,
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView

from literev.forms import HistoricalForm, SearchForm
from literev.libs.data_files import get_es_scores
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
    remove_rag_history,
    validate_project_access,
)
from literev.libs.select_functions import (
    create_refinement,
    get_filters,
    get_rendered_filters,
    remove_refinement,
)
from literev.libs.table_choice import (
    create_iteration,
    create_tablechoice_rag_iteration,
    update_new_table_choice,
)
from literev.libs.tableselect_workflows import TableSelectHandler
from literev.libs.utils import (
    get_number_documents,
)
from literev.models import (
    Cluster,
    Document,
    Project,
    ProjectDocumentRAG,
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
    Evaluate the search form and update the context with the total number of
    documents and selected indices. If the search form is valid, the function
    will also update the session with the new data.

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
    context["clustering_min_documents"] = settings.CLUSTERING_MIN_DOCUMENTS

    search_form = SearchForm(request.POST)
    context["search_form"] = search_form

    selected_indices = request.POST.get("selected_indices", "").split(",")
    context["selected_indices"] = selected_indices

    if search_form.is_valid():
        project_name = search_form.cleaned_data["project_name"]
        query = search_form.cleaned_data["query"]
        natural_language_query = search_form.cleaned_data.get(
            "natural_language_query", ""
        )

        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        total_documents = sum(
            get_number_documents(
                index_name, query, range_begin_date, range_end_date
            )
            for index_name in selected_indices
        )

        context["continue_message_box"] = True

        new_data = {
            "project_name": project_name,
            "selected_indices": selected_indices,
            "query": query,
            "natural_language_query": natural_language_query,
            "range_begin_date": range_begin_date.strftime("%Y/%m/%d"),
            "range_end_date": range_end_date.strftime("%Y/%m/%d"),
            "total_documents": total_documents,
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
    user = cast(User, request.user)
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

    natural_language_query = request.session["natural_language_query"]

    project = Project.objects.create(
        user=user,
        name=project_name,
        creation_date=datetime.datetime.now(),
        query=query,
        natural_language_query=natural_language_query,
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
    user = cast(User, request.user)
    actual_user = cast(User, request.user)
    errors: list[str] = []
    context: dict[str, list[str] | bool | int] = {"errors": errors}

    project = validate_project_access(user, project_id) if project_id else None
    if not project:
        errors.append("Project not found or access denied.")
        return redirect(reverse("search"))

    if project.step == "getting_documents":
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

        elif submit == "ask-top-docs":
            create_tablechoice_rag_iteration(user, project)

            return redirect(
                reverse(
                    "project-rag-page",
                    kwargs={
                        "project_id": project.id,
                    },
                )
            )

        elif submit == "update":
            context.update(prepare_update_context(project))

        elif submit == "remove-refinement":
            refinement_id = request.POST.get("remove-refinement")
            if refinement_id:
                remove_refinement(user, project, int(refinement_id))

        elif submit == "delete":
            context["project_id"] = project.id
            context["confirm_delete_project"] = True

        elif submit == "confirm_delete_project":
            running_delete(int(request.POST["project_id"]))
            return redirect(reverse("search"))

        elif submit == "continue":
            document_pk_list_str = request.POST.get("document_pk_list", "")
            document_pk_list = [int(pk) for pk in document_pk_list_str.split()]

            filters_json = json.loads(request.POST.get("filters", ""))

            update_new_table_choice(
                user=actual_user,
                project=project,
                document_ids_list=document_pk_list,
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
    order_by: str = "es_score",
) -> HttpResponse:
    """
    Handles table selection for a given project, refinement, and iteration.

    Parameters
    ----------
    request : HttpRequest
        The HTTP request object.
    project_id : int
        The project ID.
    refinement_id : int
        The refinement ID.
    iteration_id : int, optional
        The iteration ID (default is -1 for the latest iteration).
    num : int, optional
        Page number for pagination (default is 1).
    order_by : str, optional
        Sorting criteria (default is "es_score").
    """
    project = Project.objects.filter(
        Q(id=project_id)
        & (Q(user=request.user) | Q(id__in=get_shared_projects_ids()))
    ).first()

    if not project:
        logging.warning(
            f"Project not found or unauthorized access: {project_id}"
        )
        return redirect(reverse("search"))

    if project.step_number == 50:
        return render(
            request,
            "tableselect.html",
            {"processing_filters": True, "project": project},
        )

    if order_by == "es_scores" and not get_es_scores(project):
        return redirect(
            reverse(
                "tableselect",
                kwargs={
                    "project_id": project_id,
                    "refinement_id": refinement_id,
                    "iteration_id": iteration_id,
                    "num": 1,
                    "order_by": "-decision_date",
                },
            )
        )

    handler = TableSelectHandler(
        request, project_id, refinement_id, iteration_id, num, order_by
    )

    context = handler.get_context()

    if iteration_id == -1:
        iteration_redirect = handler.get_iteration_redirect()
        if iteration_redirect:
            return iteration_redirect

    if request.method == "POST":
        response = handler.handle_post_actions()

        if response:
            return response

    # Process refinement filters
    refinement = ProjectRefinement.objects.filter(id=refinement_id).first()
    if refinement:
        try:
            raw_filter = json.loads(refinement.filters)
            if raw_filter and not isinstance(raw_filter, str):
                context["union_sets_str"], context["excluded_set_str"] = (
                    get_rendered_filters(raw_filter)
                )
        except Exception as e:
            logging.error(f"Error processing refinement filters: {e}")
            context["error_message"] = (
                "An error occurred while processing filters. Please try again later."
            )
    step_not_valid_to_iterate = [
        "getting_documents",
        "question-answering",
        "preparing",
        "preprocessing",
    ]
    # Add project details to the context
    context.update(
        {
            "project_id": project_id,
            "iteration_id": iteration_id,
            "project": project,
            "sort_by": order_by,
            "step_not_valid_to_iterate": step_not_valid_to_iterate,
        }
    )
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


def rag(
    request: HttpRequest, project_id: int, rag_id: int = 0
) -> HttpResponse:
    user = cast(User, request.user)

    project = Project.objects.filter(id=project_id).first()
    if not project:
        return redirect(reverse("search"))

    if request.method == "POST" and "remove-rag-id" in request.POST:
        rag_to_remove_id = int(request.POST["remove-rag-id"])
        remove_rag_history(project, rag_to_remove_id)
        return redirect(
            reverse("project-rag-page", kwargs={"project_id": project_id})
        )

    has_section_ans = False
    regle_droit = ""

    project_rag = None
    show_closed_stats = False
    counts = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}
    percentages = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}

    if rag_id:
        project_rag = get_object_or_404(
            ProjectRAG, project_id=project_id, id=rag_id
        )

        if "chambre_penale" in project.selected_indices:
            has_section_ans = True
            project_rag.summary_answer
            answer_block = (
                json.loads(project_rag.summary_answer)
                if project_rag.summary_answer
                else {}
            )

            regle_droit = answer_block.get("regle_droit", "")

        stats = getattr(project_rag, "stats", None)

        if stats and stats.classification_stats:
            if "counts" in stats.classification_stats:
                show_closed_stats = True
                counts = stats.classification_stats.get("counts", {})
                percentages = stats.classification_stats.get("percentages", {})
            else:
                counts = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}
                percentages = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}

    table_choices = TableChoice.objects.filter(
        project=project, user=user, is_check=True
    )
    documents_ids = list(table_choices.values_list("document_id", flat=True))

    project_rags = ProjectRAG.objects.filter(project=project).order_by(
        "-created_at"
    )

    last_refinement = (
        ProjectRefinement.objects.filter(project=project)
        .order_by("-id")
        .first()
    )
    last_iteration = (
        RefinementIteration.objects.filter(refinement=last_refinement)
        .order_by("-id")
        .first()
        if last_refinement
        else None
    )

    first_document_rag = ProjectDocumentRAG.objects.filter(
        project_rag=project_rag
    ).first()

    has_confidence_score = False

    if first_document_rag:
        has_confidence_score = (
            True if first_document_rag.confidence_score is not None else False
        )

    summary_data = {}
    summary_text = ""
    considerations = []

    if project_rag and project_rag.summary_answer:
        try:
            summary_data = (
                json.loads(project_rag.summary_answer)
                if isinstance(project_rag.summary_answer, str)
                else project_rag.summary_answer
            )
        except json.JSONDecodeError:
            summary_data = {"summary": "", "considerations": []}

        summary_text = summary_data.get("summary", "")
        raw_considerations = summary_data.get("considerations", [])

        # Normalize considerations
        for c in raw_considerations:
            if isinstance(c, dict):
                considerations.append(
                    {
                        "text": c.get("text", "").strip(),
                        "frequency": c.get("frequency", 0),
                        "percent": c.get("percent", 0.0),
                        "procedure_types": c.get("procedure_types", []),
                    }
                )

    considerations.sort(
        key=lambda c: float(c.get("percent", 0.0) or 0.0), reverse=True
    )

    context = {
        "project": project,
        "project_rags": project_rags,
        "project_rag": project_rag,
        "project_rag_id": project_rag.id if project_rag else 0,
        "project_id": project_id,
        "documents_ids": documents_ids,
        "number_documents": len(documents_ids),
        "refinement_id": last_refinement.id if last_refinement else 0,
        "iteration_id": last_iteration.id if last_iteration else 0,
        "summary_text": summary_text,
        "considerations": considerations,
        "natural_language_query": project.natural_language_query or "",
        "classification_total": sum(counts.values()),
        "oui_count": counts.get("oui", 0),
        "non_count": counts.get("non", 0),
        "peut_etre_count": counts.get("peut_etre", 0),
        "mixte_count": counts.get("mixte", 0),
        "oui_percent": percentages.get("oui", 0),
        "non_percent": percentages.get("non", 0),
        "peut_etre_percent": percentages.get("peut_etre", 0),
        "mixte_percent": percentages.get("mixte", 0),
        "show_closed_stats": show_closed_stats,
        "has_confidence_score": has_confidence_score,
        "has_section_ans": has_section_ans,
        "regle_droit": regle_droit,
    }

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
