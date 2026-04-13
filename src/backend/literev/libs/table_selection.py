from __future__ import annotations

import json

from typing import Any, TypedDict, cast

from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse

from literev.libs.data_files import get_es_scores
from literev.libs.project_listing import count_processed_documents
from literev.libs.project_workflows import validate_project_access
from literev.libs.select_functions import (
    download_finalcsv,
    get_rendered_filters,
)
from literev.libs.table_choice import (
    check_all2_maybe_tablechoice,
    check_all2_yes_tablechoice,
    get_iteration,
    get_iterations_render,
    iterate_check_list,
    remove_iteration_get_parent,
    render_table_choice,
    reset_table_choice,
    sort_table_choice,
    update_check_list_iteration,
    update_checked_document_page,
)
from literev.models import (
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
    User,
)

STEP_NOT_VALID_TO_ITERATE = {
    "getting_documents",
    "question-answering",
    "preparing",
    "preprocessing",
}


class TableSelectionFilters(TypedDict):
    union_sets_html: str
    excluded_set_html: str


class TableSelectionCounts(TypedDict):
    chosen: int
    initial: int
    neighbour: int
    total_display: int


class TableSelectionSortOption(TypedDict):
    label: str
    value: str


ProjectFilters = dict[str, dict[str, list[str]]]


def get_accessible_project(user: User, project_id: int) -> Project | None:
    """Return the project when the current user can access it."""
    return validate_project_access(user, project_id)


def get_project_refinement(
    project: Project,
    refinement_id: int,
) -> ProjectRefinement | None:
    """Return the refinement when it belongs to the project."""
    return ProjectRefinement.objects.filter(
        project=project,
        id=refinement_id,
    ).first()


def normalize_order_by(project: Project, order_by: str | None) -> str:
    """Normalize the table sort key to supported values."""
    normalized_order_by = (order_by or "es_score").strip()

    if normalized_order_by in {"-es_score", "es_scores"}:
        normalized_order_by = "es_score"

    if normalized_order_by not in {
        "es_score",
        "decision_date",
        "-decision_date",
    }:
        normalized_order_by = "es_score"

    if normalized_order_by == "es_score" and not get_es_scores(project):
        return "-decision_date"

    return normalized_order_by


def build_tableselect_detail_url(
    project_id: int,
    refinement_id: int,
    iteration_id: int,
    page: int,
    order_by: str,
) -> str:
    """Build the canonical tableselect detail URL."""
    return reverse(
        "tableselect",
        kwargs={
            "project_id": project_id,
            "refinement_id": refinement_id,
            "iteration_id": iteration_id,
            "num": page,
            "order_by": order_by,
        },
    )


def build_tableselect_default_url(project_id: int, refinement_id: int) -> str:
    """Build the default tableselect URL without iteration information."""
    return reverse(
        "tableselect-default",
        kwargs={
            "project_id": project_id,
            "refinement_id": refinement_id,
        },
    )


def _parse_refinement_filters(raw_filters: Any) -> ProjectFilters:
    if isinstance(raw_filters, str):
        try:
            parsed = json.loads(raw_filters)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return cast(ProjectFilters, parsed)
        return {}

    if isinstance(raw_filters, dict):
        return cast(ProjectFilters, raw_filters)

    return {}


def build_rendered_filters(
    refinement: ProjectRefinement,
) -> TableSelectionFilters:
    """Build rendered refinement filter metadata for the tableselect page."""
    raw_filters = _parse_refinement_filters(refinement.filters)
    if not raw_filters:
        return {
            "union_sets_html": "",
            "excluded_set_html": "",
        }

    union_sets_html, excluded_set_html = get_rendered_filters(raw_filters)
    return {
        "union_sets_html": union_sets_html,
        "excluded_set_html": excluded_set_html,
    }


def build_sort_options(has_es_scores: bool) -> list[TableSelectionSortOption]:
    """Return the sort options supported by the current payload."""
    sort_options: list[TableSelectionSortOption] = []

    if has_es_scores:
        sort_options.append(
            {
                "label": "Query relevance score",
                "value": "es_score",
            }
        )

    sort_options.extend(
        [
            {
                "label": "Decision Date (Ascending)",
                "value": "decision_date",
            },
            {
                "label": "Decision Date (Descending)",
                "value": "-decision_date",
            },
        ]
    )

    return sort_options


def build_counts(tablechoice: Any) -> TableSelectionCounts:
    """Build the document summary counters shown above the table."""
    return {
        "chosen": tablechoice.filter(is_check=True).count(),
        "initial": tablechoice.filter(is_initial=True).count(),
        "neighbour": tablechoice.filter(
            is_initial=False, to_display=True
        ).count(),
        "total_display": tablechoice.filter(to_display=True).count(),
    }


def build_table_selection_state(
    user: User,
    project_id: int,
    refinement_id: int,
    iteration_id: int | None,
    page: int,
    order_by: str | None,
) -> dict[str, Any] | None:
    """Build the full table-selection page payload for the React page."""
    project = get_accessible_project(user, project_id)
    if not project:
        return None

    refinement = get_project_refinement(project, refinement_id)
    if not refinement:
        return None

    normalized_order_by = normalize_order_by(project, order_by)
    requested_page = max(1, page)
    iterations_queryset = RefinementIteration.objects.filter(
        refinement=refinement
    ).order_by("id")
    last_iteration = iterations_queryset.last()
    canonical_url = ""

    if project.step_number == 50:
        active_iteration_id = iteration_id or (
            last_iteration.id if last_iteration else None
        )
        return {
            "canonical_url": canonical_url,
            "counts": build_counts(
                TableChoice.objects.filter(user=user, project=project)
            ),
            "current_iteration_id": active_iteration_id,
            "filters": build_rendered_filters(refinement),
            "iterations": get_iterations_render(
                refinement.id, active_iteration_id or -1
            ),
            "processing_filters": True,
            "project": {
                "creation_date": project.creation_date.isoformat(),
                "id": project.id,
                "name": project.name,
                "processed_documents": count_processed_documents(project),
                "query": project.query,
                "range_begin_date": project.range_begin_date.isoformat(),
                "range_end_date": project.range_end_date.isoformat(),
                "step": project.step,
                "step_number": project.step_number,
            },
            "refinement": {
                "id": refinement.id,
                "name": refinement.name,
            },
            "table": {
                "current_page": requested_page,
                "has_es_scores": False,
                "has_hdbscan_scores": False,
                "rows": [],
                "sort_by": normalized_order_by,
                "sort_options": build_sort_options(False),
                "total_pages": 1,
            },
            "urls": {
                "ask_selected": reverse(
                    "api-tableselect-ask-selected",
                    args=[project.id, refinement.id],
                ),
                "back_to_filter": reverse("projectpage", args=[project.id]),
                "default": build_tableselect_default_url(
                    project.id, refinement.id
                ),
                "project_rag": reverse("project-rag-page", args=[project.id]),
            },
            "warnings": [],
        }

    active_iteration = None

    if iteration_id is None:
        if last_iteration is not None:
            get_iteration(user, project, refinement.id, last_iteration.id)
            active_iteration = last_iteration
            canonical_url = build_tableselect_detail_url(
                project.id,
                refinement.id,
                last_iteration.id,
                1,
                normalized_order_by,
            )
    else:
        active_iteration = iterations_queryset.filter(id=iteration_id).first()
        if active_iteration is None:
            return None

    tablechoice = TableChoice.objects.filter(user=user, project=project)

    if not tablechoice.exists() and active_iteration is not None:
        get_iteration(user, project, refinement.id, active_iteration.id)
        tablechoice = TableChoice.objects.filter(user=user, project=project)

    tablechoice_to_display = tablechoice.filter(to_display=True)
    total_documents = tablechoice_to_display.count()
    articles_per_page = getattr(settings, "NUMBER_ARTICLE_BY_PAGE", 10)
    total_pages = max(
        1, (total_documents + articles_per_page - 1) // articles_per_page
    )
    current_page = min(requested_page, total_pages)
    first_doc = (current_page - 1) * articles_per_page
    last_doc = min(current_page * articles_per_page, total_documents)

    sorted_tablechoice = sort_table_choice(
        project,
        tablechoice_to_display,
        normalized_order_by,
    )[first_doc:last_doc]

    rows, has_hdbscan_scores, has_es_scores = render_table_choice(
        project,
        sorted_tablechoice,
    )

    for row in rows:
        row["content_url"] = reverse(
            "contentdocument",
            kwargs={"document_id": cast(int, row["document_pk"])},
        )

    if active_iteration is not None and not canonical_url:
        canonical_url = build_tableselect_detail_url(
            project.id,
            refinement.id,
            active_iteration.id,
            current_page,
            normalized_order_by,
        )

    return {
        "canonical_url": canonical_url,
        "counts": build_counts(tablechoice),
        "current_iteration_id": active_iteration.id
        if active_iteration
        else None,
        "filters": build_rendered_filters(refinement),
        "iterations": get_iterations_render(
            refinement.id,
            active_iteration.id if active_iteration else -1,
        ),
        "processing_filters": False,
        "project": {
            "can_iterate": project.step not in STEP_NOT_VALID_TO_ITERATE,
            "creation_date": project.creation_date.isoformat(),
            "id": project.id,
            "name": project.name,
            "processed_documents": count_processed_documents(project),
            "query": project.query,
            "range_begin_date": project.range_begin_date.isoformat(),
            "range_end_date": project.range_end_date.isoformat(),
            "step": project.step,
            "step_number": project.step_number,
        },
        "refinement": {
            "id": refinement.id,
            "iterations_limit": settings.LIMIT_NUMBER_ITERATIONS,
            "name": refinement.name,
        },
        "table": {
            "current_page": current_page,
            "has_es_scores": has_es_scores,
            "has_hdbscan_scores": has_hdbscan_scores,
            "rows": rows,
            "sort_by": normalized_order_by,
            "sort_options": build_sort_options(has_es_scores),
            "total_pages": total_pages,
        },
        "urls": {
            "back_to_filter": reverse("projectpage", args=[project.id]),
            "default": build_tableselect_default_url(
                project.id, refinement.id
            ),
            "project_rag": reverse("project-rag-page", args=[project.id]),
        },
        "warnings": [],
    }


def update_table_selection(
    user: User,
    project: Project,
    iteration_id: int | None,
    selected_documents: list[int],
    deselected_documents: list[int],
    maybe_documents: list[int],
) -> None:
    """Persist the current table selection for the visible page."""
    update_checked_document_page(
        user,
        project,
        selected_documents,
        deselected_documents,
        maybe_documents,
    )

    if iteration_id:
        update_check_list_iteration(
            user=user,
            project=project,
            iteration_id=iteration_id,
        )


def activate_table_iteration(
    user: User,
    project: Project,
    refinement_id: int,
    iteration_id: int,
    order_by: str,
) -> dict[str, str] | None:
    """Load a previous iteration into table choice state and return its URL."""
    iteration = RefinementIteration.objects.filter(
        refinement_id=refinement_id,
        id=iteration_id,
    ).first()
    if not iteration:
        return None

    get_iteration(user, project, refinement_id, iteration_id)
    return {
        "detail": "Iteration loaded.",
        "url": build_tableselect_detail_url(
            project.id,
            refinement_id,
            iteration_id,
            1,
            normalize_order_by(project, order_by),
        ),
    }


def delete_table_iteration(
    user: User,
    project: Project,
    refinement_id: int,
    iteration_id: int,
    order_by: str,
) -> dict[str, str] | None:
    """Delete an iteration and return the parent iteration URL."""
    parent_id = remove_iteration_get_parent(
        user,
        project,
        refinement_id,
        iteration_id,
    )
    if not parent_id:
        return None

    get_iteration(user, project, refinement_id, parent_id)
    return {
        "detail": "Iteration removed.",
        "url": build_tableselect_detail_url(
            project.id,
            refinement_id,
            parent_id,
            1,
            normalize_order_by(project, order_by),
        ),
    }


def iterate_table_selection(
    user: User,
    project: Project,
    refinement_id: int,
    iteration_id: int,
    selected_documents: list[int],
    deselected_documents: list[int],
    maybe_documents: list[int],
) -> dict[str, str]:
    """Start the background iterate workflow for the current selection."""
    current_iterations = RefinementIteration.objects.filter(
        refinement_id=refinement_id
    ).count()
    iteration_limit = getattr(settings, "LIMIT_NUMBER_ITERATIONS", 10)

    if current_iterations >= iteration_limit:
        raise ValueError("You have reached the limit of iterations.")

    update_table_selection(
        user=user,
        project=project,
        iteration_id=iteration_id,
        selected_documents=selected_documents,
        deselected_documents=deselected_documents,
        maybe_documents=maybe_documents,
    )
    iterate_check_list(
        user,
        project,
        refinement_id,
        iteration_id,
    )

    return {
        "detail": "A new iteration is being prepared.",
        "url": build_tableselect_default_url(project.id, refinement_id),
    }


def reset_table_selection_state(
    user: User,
    project: Project,
    refinement_id: int,
) -> dict[str, str]:
    """Reset the table-selection state to the root iteration."""
    reset_table_choice(user, project, refinement_id)
    return {
        "detail": "Iterations reset.",
        "url": build_tableselect_default_url(project.id, refinement_id),
    }


def set_all_table_selection(
    user: User,
    project: Project,
    iteration_id: int | None,
    mode: str,
) -> None:
    """Set all visible table rows to yes or maybe."""
    if mode == "yes":
        check_all2_yes_tablechoice(user, project)
    elif mode == "maybe":
        check_all2_maybe_tablechoice(user, project)
    else:
        raise ValueError("Unsupported selection mode.")

    if iteration_id:
        update_check_list_iteration(
            user=user,
            project=project,
            iteration_id=iteration_id,
        )


def export_selected_table_documents(
    user: User,
    project: Project,
    iteration_id: int | None,
    selected_documents: list[int],
    deselected_documents: list[int],
    maybe_documents: list[int],
) -> HttpResponse:
    """Persist the current selection and export the selected documents CSV."""
    update_table_selection(
        user=user,
        project=project,
        iteration_id=iteration_id,
        selected_documents=selected_documents,
        deselected_documents=deselected_documents,
        maybe_documents=maybe_documents,
    )
    return download_finalcsv(project=project)


def ask_selected_documents(
    user: User,
    project: Project,
    iteration_id: int | None,
    selected_documents: list[int],
    deselected_documents: list[int],
    maybe_documents: list[int],
) -> dict[str, str]:
    """Persist the current selection and return the RAG page URL."""
    update_table_selection(
        user=user,
        project=project,
        iteration_id=iteration_id,
        selected_documents=selected_documents,
        deselected_documents=deselected_documents,
        maybe_documents=maybe_documents,
    )
    return {
        "detail": "Selection saved.",
        "url": reverse("project-rag-page", args=[project.id]),
    }
