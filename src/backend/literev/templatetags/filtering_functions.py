from __future__ import annotations

import re

from typing import Any, Union

from django import template
from django.conf import settings
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Func

from literev.libs.utils import count_trials, get_shared_projects_ids
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
)

register = template.Library()

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"
CLUSTERING_MIN_DOCUMENTS = settings.CLUSTERING_MIN_DOCUMENTS


@register.filter
def has_early_results(project: Project) -> bool:
    return project.step in ["clustering", "plotting"]


@register.filter
def check_shared_project(project_id: int):
    return project_id in get_shared_projects_ids()


@register.filter
def count_processed_documents(project: Project) -> int:
    documents_count = Document.objects.filter(project=project).count()

    if documents_count < CLUSTERING_MIN_DOCUMENTS:
        return documents_count

    if (
        "chambre_penale" in project.selected_indices
        or "chambre_civile" in project.selected_indices
        or "chambre_administrative" in project.selected_indices
    ):
        return documents_count

    return ClusterElement.objects.filter(cluster__project=project).count()


@register.filter
def clustering_percentage(project: Project) -> int:
    n_total_trials = int(settings.NUMBER_TRIALS)
    step_number = count_trials(project)

    return int(step_number / n_total_trials * 100)


@register.filter
def clustering_progress(project: Project) -> str:
    n_total_trials = settings.NUMBER_TRIALS
    step_number = count_trials(project)

    return f"{step_number}/{n_total_trials}"


@register.filter
def prepared_percentage(project: Project) -> int:
    total_documents = project.total_documents
    documents = (
        Document.objects.filter(project=project)
        .exclude(prepared_for_ngrams="")
        .count()
    )

    return int(documents / total_documents * 100)


@register.filter
def prepared_progress(project: Project) -> str:
    total_documents = project.total_documents
    documents = (
        Document.objects.filter(project=project)
        .exclude(prepared_for_ngrams="")
        .count()
    )

    return f"{documents}/{total_documents}"


@register.filter
def created_percentage(project: Project) -> int:
    total_documents = project.total_documents
    documents = Document.objects.filter(project=project).count()

    return int(documents / total_documents * 100)


@register.filter
def created_documents(project: Project) -> str:
    total_documents = project.total_documents
    documents = Document.objects.filter(project=project).count()

    return f"{documents}/{total_documents}"


@register.filter
def clusters_summary(project: Project) -> list[dict[str, Union[str, int]]]:
    """
    Generate summaries for each cluster related to a project.

    This function calculates the center of each cluster by grouping them
    based on topic and summary text. It finds the element closest to the
    center for each cluster. Then, it generates a summary for each cluster
    ordered by the total number of articles in the cluster. If the project
    contains an unclassified/noise papers cluster, it is appended to the end
    of the returned list of clusters.

    Parameters
    ----------
    project : Project
        The project object to retrieve summaries for.

    Returns
    -------
    List[Dict[str, Union[str, int]]]
        A list of dictionaries representing cluster summaries. Each dictionary
        includes the following keys:
        - 'topic' (str): The cluster's topic.
        - 'total_documents' (int): The total number of articles in the cluster.
        - 'article_title' (str): The article's title in the closest element.
        - 'article_url' (str): The article's URL of the closest element.
        - 'summary_text' (str): ChatGPT generated summary text based on topic.

    Example
    -------
    clusters_summary(my_project)
        Returns a list of cluster summaries.

    Usage in Template
    -----------------
    {% with project|clusters_summary as summaries %}
    {% if summaries %}
        {% for summary in summaries %}
            {{ summary.topic }}
            {{ summary.summary_text }}
            {{ summary.total_documents }}
            {{ summary.article_title }}
        {% endfor %}
    {% endif %}
    {% endwith %}
    """
    clusters_summary = []

    # Get all clusters associated with the project
    clusters = Cluster.objects.filter(project=project)

    # Group clusters by 'topic' and 'summary' to calculate
    # the center coordinates for each group
    grouped_clusters = (
        clusters.values("topic", "summary", "order", "id")
        .annotate(
            center_x=Avg("clusterelement__pos_x", output_field=FloatField()),
            center_y=Avg("clusterelement__pos_y", output_field=FloatField()),
            total_documents=Count("clusterelement__document"),
        )
        .order_by("order")
    )

    # outlier or noise papers cluster
    unclassified_papers_cluster: dict[str, Any] = {}

    for cluster in grouped_clusters:
        topic = cluster["topic"]
        center_x = cluster["center_x"]
        center_y = cluster["center_y"]
        total_documents = cluster["total_documents"]
        summary = cluster["summary"]
        cluster_id = cluster["id"]
        cluster_order = cluster["order"]

        if topic == UNCLASSIFIED_PAPERS_TOPIC:
            # reserve the unclassified/noise papers cluster
            # and continue with the rest of the clusters
            unclassified_papers_cluster = {
                "cluster_id": cluster_id,
                "topic": topic,
                "total_documents": total_documents,
                "cluster_order": -1,
                "summary_text": (
                    "Unclassified papers are the outliers or noise points that could "
                    "not fit into any of the identified groups during the clustering process."
                ),
            }
            continue

        # Calculate the closest cluster for this group
        most_centered_element = (
            ClusterElement.objects.filter(cluster__topic=topic)
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
            # .exclude(article__url_file="")  # exclude invalid urls
            .order_by("distance")
            .first()
        )

        topic_10 = ", ".join(topic.split(", ")[:10])

        if most_centered_element:
            clusters_summary.append(
                {
                    "cluster_id": cluster_id,
                    "cluster_order": cluster_order,
                    "topic": topic,
                    "topic_10": topic_10,
                    "total_documents": total_documents,
                    "summary_text": summary,
                    "document_id": most_centered_element.document.raw_document_id,
                    "procedure_type": most_centered_element.document.procedure_type,
                    "decision_type": most_centered_element.document.decision_type,
                    "result": most_centered_element.document.result,
                }
            )

    # if unclassified papers cluster exists, append it
    # as the last element in the summary list
    if unclassified_papers_cluster:
        clusters_summary.append(unclassified_papers_cluster)

    return clusters_summary


@register.filter
def get_dict_value(dictionary: dict[str, str], key: str) -> str:
    """This filter gets a value from a dictionary given a specific key."""
    return dictionary.get(key, "")


@register.filter
def document_id_by_procedure_type(procedure_type):
    doc = Document.objects.filter(procedure_type=procedure_type).first()
    return doc.id if doc else None


@register.filter
def extract_doc_data(value):
    """Extract numbers from a string like '[1], [3], [4]' into a list of integers."""
    if isinstance(value, list):
        doc_ids = [int(num) for num in value]
    else:
        doc_ids = [int(num) for num in re.findall(r"\d+", str(value))]

    document_data = {}

    for doc_id in doc_ids:
        document = Document.objects.filter(id=doc_id).first()
        if document:
            document_data[document.id] = document.procedure_type

    return document_data
