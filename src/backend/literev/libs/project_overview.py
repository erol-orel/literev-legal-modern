from __future__ import annotations

import json

from typing import Any, TypedDict, cast

from django.conf import settings
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Func
from django.urls import reverse

from literev.libs.nlp import nlp_topic_description
from literev.libs.project_listing import (
    build_project_progress,
    count_processed_documents,
    is_shared_project,
)
from literev.libs.project_workflows import (
    extract_refined_list,
    get_grouped_clusters,
    load_plot_data,
    validate_project_access,
)
from literev.libs.select_functions import (
    create_refinement,
    get_filtered_document,
    remove_refinement,
)
from literev.libs.table_choice import (
    create_iteration,
    create_tablechoice_rag_iteration,
    update_new_table_choice,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Project,
    ProjectRefinement,
    User,
)
from literev.task_plotting import get_color_map

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"
RESULT_OPTIONS = [
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


class FilterOption(TypedDict, total=False):
    label: str
    tooltip: str
    value: str


class FilterTypeDefinition(TypedDict, total=False):
    input_kind: str
    label: str
    options: list[FilterOption]
    placeholder: str
    value: str


class RepresentativeDocument(TypedDict):
    decision_type: str
    document_id: str
    procedure_type: str
    result: str


class ClusterSummaryItem(TypedDict, total=False):
    cluster_id: int
    cluster_order: int
    representative_document: RepresentativeDocument | None
    summary_text: str
    topic: str
    topic_color: str
    topic_label: str
    total_documents: int


class RefinementItem(TypedDict):
    can_delete: bool
    filters: dict[str, Any]
    id: int
    name: str
    open_url: str
    owner_name: str


class ProjectOverviewPayload(TypedDict):
    cluster_summaries: list[ClusterSummaryItem]
    filters: dict[str, Any]
    no_clusters: bool
    plot: dict[str, str] | None
    project: dict[str, Any]
    refinements: list[RefinementItem]


class RefinementPreviewPayload(TypedDict):
    can_continue: bool
    filters: dict[str, dict[str, list[str]]]
    number_documents: int


class CreatedRefinementPayload(TypedDict):
    detail: str
    id: int
    name: str
    number_documents: int
    refinement: RefinementItem
    url: str


class GeneratedSummaryPayload(TypedDict):
    cluster: ClusterSummaryItem
    detail: str


ProjectFilters = dict[str, dict[str, list[str]]]


def get_accessible_project(user: User, project_id: int) -> Project | None:
    """Return the project when the current user can access it."""
    return validate_project_access(user, project_id)


def _step_label(step: str) -> str:
    return step.replace("-", " ").replace("_", " ").title()


def _parse_refinement_filters(raw_filters: Any) -> dict[str, Any]:
    if isinstance(raw_filters, str):
        try:
            parsed = json.loads(raw_filters)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    if isinstance(raw_filters, dict):
        return cast(dict[str, Any], raw_filters)

    return {}


def _safe_load_plot_data(project_id: int) -> dict[str, str] | None:
    try:
        return load_plot_data(project_id)
    except FileNotFoundError:
        return None


def _build_topic_options(project: Project) -> list[FilterOption]:
    grouped_clusters = get_grouped_clusters(project)
    topic_options: list[FilterOption] = []
    visible_index = 0

    for cluster in grouped_clusters:
        topic = cluster["topic"]
        if topic == UNCLASSIFIED_PAPERS_TOPIC:
            label = topic
        else:
            visible_index += 1
            label = f"{visible_index}: {', '.join(topic.split(', ')[:10])}"

        topic_options.append(
            {
                "label": label,
                "tooltip": topic,
                "value": label,
            }
        )

    return topic_options


def _build_filter_type_definitions(
    project: Project,
    no_clusters: bool,
) -> list[FilterTypeDefinition]:
    filter_types: list[FilterTypeDefinition] = []

    if project.is_finish and not no_clusters:
        filter_types.append(
            {
                "input_kind": "select",
                "label": "Topic",
                "options": _build_topic_options(project),
                "placeholder": "Select a topic",
                "value": "Topic",
            }
        )

    filter_types.extend(
        [
            {
                "input_kind": "datalist",
                "label": "Norms",
                "options": [
                    {"label": value, "value": value}
                    for value in extract_refined_list(project, "standards")
                ],
                "placeholder": "Norms to search",
                "value": "Norm",
            },
            {
                "input_kind": "datalist",
                "label": "No Decision",
                "options": [
                    {"label": value, "value": value}
                    for value in extract_refined_list(project, "decision_type")
                ],
                "placeholder": "No Decision to search",
                "value": "No_decis",
            },
        ]
    )

    if project.is_finish or project.step in ["clustering", "plotting"]:
        filter_types.append(
            {
                "input_kind": "text",
                "label": "Keyword Search",
                "placeholder": "Criteria",
                "value": "Keyword",
            }
        )

    filter_types.extend(
        [
            {
                "input_kind": "text",
                "label": "Decision Year",
                "placeholder": (
                    "Enter a year as YYYY or a range as YYYY-YYYY "
                    "(e.g., 2020 or 2017-2022)."
                ),
                "value": "year_range",
            },
            {
                "input_kind": "datalist",
                "label": "Descriptor",
                "options": [
                    {"label": value, "value": value}
                    for value in extract_refined_list(project, "descriptors")
                ],
                "placeholder": "Descriptors to search",
                "value": "descriptors",
            },
            {
                "input_kind": "datalist",
                "label": "Result",
                "options": [
                    {"label": value, "value": value}
                    for value in RESULT_OPTIONS
                ],
                "placeholder": "Result to search",
                "value": "Result",
            },
        ]
    )

    if project.selected_indices == ["civil_court"]:
        filter_types.append(
            {
                "input_kind": "datalist",
                "label": "Chamber",
                "options": [
                    {"label": value, "value": value}
                    for value in extract_refined_list(project, "chamber")
                ],
                "placeholder": "Court Division",
                "value": "chamber",
            }
        )

    return filter_types


def _serialize_representative_document(
    cluster_element: ClusterElement | None,
) -> RepresentativeDocument | None:
    if not cluster_element:
        return None

    return {
        "decision_type": cluster_element.document.decision_type or "",
        "document_id": cluster_element.document.raw_document_id or "",
        "procedure_type": cluster_element.document.procedure_type or "",
        "result": cluster_element.document.result or "",
    }


def serialize_cluster_summaries(project: Project) -> list[ClusterSummaryItem]:
    """Serialize cluster summaries for the project overview page."""
    cluster_summaries: list[ClusterSummaryItem] = []
    clusters = Cluster.objects.filter(project=project)

    if not clusters.exists():
        return cluster_summaries

    cluster_topics = list(
        clusters.values_list("topic", flat=True).order_by("order")
    )
    topics, palette = get_color_map(cluster_topics)
    topic_colors = dict(zip(topics, palette))

    grouped_clusters = (
        clusters.values("topic", "summary", "order", "id")
        .annotate(
            center_x=Avg("clusterelement__pos_x", output_field=FloatField()),
            center_y=Avg("clusterelement__pos_y", output_field=FloatField()),
            total_documents=Count("clusterelement__document"),
        )
        .order_by("order")
    )

    unclassified_cluster: ClusterSummaryItem | None = None

    for cluster in grouped_clusters:
        topic = cast(str, cluster["topic"])
        cluster_id = cast(int, cluster["id"])
        cluster_order = cast(int, cluster["order"])
        summary_text = cast(str, cluster["summary"])
        total_documents = cast(int, cluster["total_documents"])

        if topic == UNCLASSIFIED_PAPERS_TOPIC:
            unclassified_cluster = {
                "cluster_id": cluster_id,
                "cluster_order": -1,
                "representative_document": None,
                "summary_text": (
                    "Unclassified papers are the outliers or noise points that "
                    "could not fit into any identified group during clustering."
                ),
                "topic": topic,
                "topic_color": topic_colors.get(topic, ""),
                "topic_label": topic,
                "total_documents": total_documents,
            }
            continue

        center_x = cluster["center_x"]
        center_y = cluster["center_y"]
        most_centered_element = (
            ClusterElement.objects.filter(cluster_id=cluster_id)
            .annotate(
                distance=ExpressionWrapper(
                    Func(
                        (F("pos_x") - center_x) ** 2
                        + (F("pos_y") - center_y) ** 2,
                        function="SQRT",
                    ),
                    output_field=FloatField(),
                )
            )
            .order_by("distance")
            .first()
        )

        cluster_summaries.append(
            {
                "cluster_id": cluster_id,
                "cluster_order": cluster_order,
                "representative_document": _serialize_representative_document(
                    most_centered_element
                ),
                "summary_text": summary_text,
                "topic": topic,
                "topic_color": topic_colors.get(topic, ""),
                "topic_label": ", ".join(topic.split(", ")[:10]),
                "total_documents": total_documents,
            }
        )

    if unclassified_cluster:
        cluster_summaries.append(unclassified_cluster)

    return cluster_summaries


def serialize_refinement(
    refinement: ProjectRefinement,
    project: Project,
) -> RefinementItem:
    """Serialize one refinement row for the project overview page."""
    return {
        "can_delete": True,
        "filters": _parse_refinement_filters(refinement.filters),
        "id": refinement.id,
        "name": refinement.name,
        "open_url": reverse(
            "tableselect-default",
            kwargs={
                "project_id": project.id,
                "refinement_id": refinement.id,
            },
        ),
        "owner_name": refinement.owner.username,
    }


def build_project_overview(
    user: User,
    project: Project,
) -> ProjectOverviewPayload:
    """Build the project overview payload served to the React page."""
    is_shared = is_shared_project(project)
    cluster_summaries = serialize_cluster_summaries(project)
    no_clusters = project.is_finish and len(cluster_summaries) == 0
    plot_data = (
        _safe_load_plot_data(project.id)
        if project.is_finish and not no_clusters
        else None
    )
    refinements = ProjectRefinement.objects.filter(owner=user, project=project)
    filter_types = _build_filter_type_definitions(project, no_clusters)

    return {
        "cluster_summaries": cluster_summaries,
        "filters": {
            "refinement_limit": settings.LIMIT_NUMBER_REFINEMENTS,
            "refinement_count": refinements.count(),
            "types": filter_types,
        },
        "no_clusters": no_clusters,
        "plot": plot_data,
        "project": {
            "best_dbcv": float(project.best_dbcv),
            "can_ask_top_docs": True,
            "can_delete": not is_shared and project.user == user,
            "creation_date": project.creation_date.isoformat(),
            "id": project.id,
            "is_finish": bool(project.is_finish),
            "is_running": bool(project.is_running),
            "is_shared": is_shared,
            "name": project.name,
            "natural_language_query": project.natural_language_query or "",
            "processed_documents": count_processed_documents(project),
            "progress": build_project_progress(project),
            "query": project.query,
            "range_begin_date": project.range_begin_date.isoformat(),
            "range_end_date": project.range_end_date.isoformat(),
            "selected_indices": cast(list[str], project.selected_indices),
            "step": project.step,
            "step_label": _step_label(project.step),
            "total_documents": project.total_documents,
        },
        "refinements": [
            serialize_refinement(refinement, project)
            for refinement in refinements.order_by("-id")
        ],
    }


def preview_project_filters(
    user: User,
    project: Project,
    filters: ProjectFilters,
) -> RefinementPreviewPayload:
    """Preview the number of documents matched by a refinement filter set."""
    refinement_count = ProjectRefinement.objects.filter(
        owner=user,
        project=project,
    ).count()
    if refinement_count >= settings.LIMIT_NUMBER_REFINEMENTS:
        raise ValueError("You have reached the limit of refinements.")

    document_ids = get_filtered_document(project, filters)
    return {
        "can_continue": True,
        "filters": filters,
        "number_documents": len(document_ids),
    }


def create_project_refinement(
    user: User,
    project: Project,
    refinement_name: str,
    filters: ProjectFilters,
) -> CreatedRefinementPayload:
    """Create a new refinement and return its tableselect URL."""
    preview = preview_project_filters(user, project, filters)
    document_ids = get_filtered_document(project, filters)

    update_new_table_choice(
        user=user,
        project=project,
        document_ids_list=document_ids,
    )
    refinement_id = create_refinement(
        user,
        project,
        refinement_name,
        len(document_ids),
        filters,
    )
    create_iteration(user, project, refinement_id)

    refinement = ProjectRefinement.objects.get(id=refinement_id)
    open_url = reverse(
        "tableselect-default",
        kwargs={
            "project_id": project.id,
            "refinement_id": refinement_id,
        },
    )
    return {
        "detail": "Refinement created.",
        "id": refinement_id,
        "name": refinement.name,
        "number_documents": preview["number_documents"],
        "refinement": serialize_refinement(refinement, project),
        "url": open_url,
    }


def delete_project_refinement(
    user: User,
    project: Project,
    refinement_id: int,
) -> bool:
    """Delete an owned refinement from the project overview page."""
    refinement = ProjectRefinement.objects.filter(
        id=refinement_id,
        owner=user,
        project=project,
    ).first()
    if not refinement:
        return False

    remove_refinement(user, project, refinement_id)
    return True


def generate_cluster_summary(
    project: Project,
    cluster_id: int,
) -> GeneratedSummaryPayload:
    """Generate and persist a cluster summary for the current project."""
    cluster = Cluster.objects.filter(project=project, id=cluster_id).first()
    if not cluster:
        raise ValueError("Cluster not found.")

    summary_text = nlp_topic_description(cluster)
    if not summary_text:
        raise RuntimeError(
            "It seems the service is still not available. Please, try again later."
        )

    cluster.summary = summary_text
    cluster.save(update_fields=["summary"])

    summary_lookup = {
        item["cluster_id"]: item
        for item in serialize_cluster_summaries(project)
    }
    return {
        "cluster": summary_lookup[cluster_id],
        "detail": "Summary generated.",
    }


def start_top_documents_rag(user: User, project: Project) -> str:
    """Prepare the top-documents RAG selection and return the destination URL."""
    create_tablechoice_rag_iteration(user, project)
    return reverse(
        "project-rag-page",
        kwargs={"project_id": project.id},
    )
