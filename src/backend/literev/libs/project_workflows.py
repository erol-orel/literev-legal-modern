from __future__ import annotations

from itertools import chain
from typing import Optional, TypedDict, cast

from django.conf import settings
from django.db.models import Count
from django.db.models.query import QuerySet
from django_stubs_ext import WithAnnotations

from literev.models import Cluster, Document, Project, ProjectRAG
from literev.task_plotting import get_color_map
from literev.tasks import get_shared_projects_ids

__all__ = [
    "extract_refined_list",
    "format_grouped_clusters",
    "get_color_map",
    "get_grouped_clusters",
    "load_plot_data",
    "remove_rag_history",
    "validate_project_access",
]


class _Ann(TypedDict):
    total_documents: int


class TopicCountRow(TypedDict):
    topic: str
    total_documents: int


def load_plot_data(project_pk: int) -> dict[str, str]:
    """Load the saved Bokeh div/script pair for a project."""
    fname_project_div_plot = settings.PLOT_DATA / f"{project_pk}_div.html"
    fname_project_script_plot = (
        settings.PLOT_DATA / f"{project_pk}_script.html"
    )

    with open(fname_project_div_plot, "r") as file_pointer:
        div_plot = file_pointer.read()

    with open(fname_project_script_plot, "r") as file_pointer:
        script_plot = file_pointer.read()

    return {"div_plot": div_plot, "script_plot": script_plot}


def extract_refined_list(
    project: Project,
    filter_field: str = "standards",
) -> list[str]:
    """Return a sorted unique list of filter values for the project."""
    filtered_list_raw = (
        Document.objects.filter(project=project)
        .order_by("result")
        .values_list(f"{filter_field}", flat=True)
    )
    flattened_values = chain.from_iterable(
        filter_value.split(";")
        for filter_value in filtered_list_raw
        if filter_value
    )
    refined_set = {value.strip() for value in flattened_values}
    return sorted(refined_set)


def get_grouped_clusters(
    project: Project,
) -> QuerySet[WithAnnotations[Cluster, _Ann], TopicCountRow]:
    """Return project clusters grouped by topic with document counts."""
    queryset = (
        Cluster.objects.filter(project=project)
        .values("topic")
        .annotate(total_documents=Count("clusterelement__document"))
        .order_by("order")
    )
    return cast(
        "QuerySet[WithAnnotations[Cluster, _Ann], TopicCountRow]",
        queryset,
    )


def format_grouped_clusters(
    grouped_clusters: QuerySet[WithAnnotations[Cluster, _Ann], TopicCountRow],
) -> list[str]:
    """Format grouped clusters as numbered topic labels."""
    unclassified_papers_topic = "unclassified papers"

    index = 0
    list_topic_10: list[str] = []
    exists_unclassified = False

    for cluster in grouped_clusters:
        if cluster["topic"] == unclassified_papers_topic:
            exists_unclassified = True
            continue
        index += 1
        list_topic_10.append(
            f"{index}: {', '.join(cluster['topic'].split(', ')[:10])}"
        )

    if exists_unclassified:
        list_topic_10.append(unclassified_papers_topic)

    return list_topic_10


def validate_project_access(user, project_id: int) -> Optional[Project]:
    """Return the project when the current user can access it."""
    shared_projects = get_shared_projects_ids()
    if (
        project_id in shared_projects
        or Project.objects.filter(user=user, id=project_id).exists()
    ):
        return Project.objects.filter(id=project_id).first()
    return None


def remove_rag_history(project: Project, rag_id: int) -> None:
    """Remove a RAG entry if it belongs to the specified project."""
    ProjectRAG.objects.filter(project=project, id=rag_id).delete()
