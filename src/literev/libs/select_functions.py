from __future__ import annotations

import json
import logging
import os

from typing import Any

import pandas as pd

from django.conf import settings
from django.db.models import Count, Q
from django.http import HttpResponse

from literev.libs.table_choice import get_iteration
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
    User,
)

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


def create_final_file(project: Project) -> str:
    """Creates a csv file with all metadata for every document
    from the list selected documents related with the project an user.

    Parameters
    ----------
    project : project object Model database
               The project object model where is used to store
               search query, status and related data.
    user : User
        A User object related with the data of the user.

    Returns
    -------
    path_to_file : str
        path to the csv file.

    """
    # get the documents
    list_tablechoice = TableChoice.objects.filter(
        project=project, is_check=True
    )

    # create the csv file from a dictionary
    metadata: dict[str, list[int | str]] = dict()

    metadata["number_cluster"] = []
    metadata["topic"] = []
    metadata["decision_type"] = []
    metadata["procedure_type"] = []
    metadata["decision_date"] = []
    metadata["standards"] = []
    metadata["result"] = []
    metadata["summary"] = []
    # metadata["raw_document"] = []

    clusters = Cluster.objects.filter(project=project)

    sorted_clusters = (
        clusters.values("topic")
        .annotate(total_documents=Count("clusterelement__document"))
        .order_by("-total_documents")
    )

    number_topic: dict[str, str] = dict()

    index = 0
    for cluster in sorted_clusters:
        if cluster["topic"] == UNCLASSIFIED_PAPERS_TOPIC:
            number_topic[cluster["topic"]] = "No cluster"
            continue
        index += 1
        number_topic[cluster["topic"]] = index

    for tablechoice in list_tablechoice:
        document = tablechoice.document
        # get the cluster object of this project and document
        try:
            cluster_element = ClusterElement.objects.get(
                cluster__project=project, document=document
            )
        except ClusterElement.DoesNotExist:
            continue

        # metadata["number_cluster"].append(cluster_element.cluster.topic)
        topic = cluster_element.cluster.topic
        metadata["number_cluster"].append(number_topic[topic])
        metadata["topic"].append(", ".join(topic.split(", ")[:10]))
        metadata["decision_type"].append(document.decision_type)
        metadata["procedure_type"].append(document.procedure_type)
        metadata["decision_date"].append(document.decision_date)
        metadata["standards"].append(document.standards)
        metadata["result"].append(document.result)
        metadata["summary"].append(document.descriptors)
        # metadata["raw_document"].append(document.raw_document_text)

    path_to_file = f"{settings.ARTICLE_DATA}/export_project_{project.id}_"

    # Create csv file from pandas
    metadata_df = pd.DataFrame(metadata)

    metadata_df.to_csv(path_to_file)

    return path_to_file


def download_finalcsv(project: Project) -> HttpResponse:
    """Return a csv file as attachment.

    Parameters
    ----------
    project : project object Model database
               The project object model where is used to store
               search query, status and related data.
    user : User
        A User object related with the data of the user.

    Returns
    -------
    response : HttpResponse
        A csv file as attachment.

    """
    # Create a csv file
    filepath = create_final_file(project)
    # Open the file for reading content

    with open(filepath, "rb") as f:
        reader = f.read()

    # Remove the csv file because we do not needed anymore
    os.remove(filepath)

    # Set the return value of the HttpResponse
    response = HttpResponse(reader, content_type="text/csv")
    # Set the HTTP header for sending to browser
    response["Content-Disposition"] = (
        "attachment; filename={name_file}".format(
            name_file="selected_documents_literev.csv"
        )
    )

    # Return the response value
    return response


def get_raw_filters(post_data: dict[str, str]) -> str:
    """
    Return a raw filter dictionary from the post_data

    Use the post_data (request.POST) as a argument to extract
    the key, values where key start with "filter.." and convert its
    str value to python object, then is converted to and str value
    to store in session.
    This generates the value will be stored in request.sessions
    and will help to keep the filters selected by the user.

    Parameters
    ----------
    post_data : a request.POST dictionary dict [str, str]
        A dictionary obtained from the frontend has the filters sent by
        the user

    Returns
    -------
    raw_filters : str
        Store the selected filters in a string, this string has
        json format.
    """
    filters: dict[str, Any] = {}

    for key, value in post_data.items():
        if "filter" in key and value != "{}":
            filters[key] = json.loads(value)

    raw_filters = json.dumps(filters)

    return raw_filters


def get_filters(post_data: dict[str, str]) -> dict[str, dict[str, Any]]:
    """
    Return a filter dictionary from the post_data.

    Use the post_data (request.POST) as an argument to extract
    the key, values where key starts with "filter.." and convert its
    str value to json object and from there add the starting value to
    filter for the function get_filtered_documents.

    Parameters
    ----------
    post_data : dict[str, str]
        A dictionary obtained from the frontend that has the filters sent by
        the user.

    Returns
    -------
    dict[str, dict[str, Any]]
        A dictionary of filters that will be used in get_filtered_documents.
    """
    filters: dict[str, Any] = {}

    for key, value in post_data.items():
        if "filter" in key:
            try:
                if value and value != "{}":
                    filters[key] = json.loads(value)
            except json.JSONDecodeError:
                logging.error(f"Invalid JSON data for key {key}: {value}")

    return filters


def get_filtered_document(
    project: Project, filters: dict[str, Any]
) -> list[int]:
    """
    Retrieve a list of filtered document IDs based on the given filters.

    This method filters judiciary documents by several criteria such as
    Topic, Norm, Keyword, No_decis, Result, and year range, and applies
    both inclusion and exclusion filters. It returns the document IDs that
    match the filters.

    Parameters
    ----------
    project : Project
        The project instance used for filtering documents.
    filters : dict
        A dictionary containing filter types and their corresponding values.
        Example format:
        {"filter-union": {"Topic": ["topic1", "topic2"], ...},
        "filter-exclude": {"Norm": ["norm1", "norm2"], ...}}

    Returns
    -------
    list[int]
        A list of document IDs that match the applied filters.
    """
    union_documents = apply_filters(project, filters, "filter-union")
    excluded_documents = apply_filters(project, filters, "filter-exclude")

    if not union_documents and not any(
        "filter-union" in key for key in filters
    ):
        union_documents = set(
            ClusterElement.objects.filter(
                cluster__project=project
            ).values_list("document__pk", flat=True)
        )

    filtered_documents = union_documents - excluded_documents
    return list(filtered_documents)


def apply_filters(
    project: Project, filters: dict[str, Any], filter_type: str
) -> set[int]:
    """
    Apply filters to retrieve document IDs based on filter type (union or exclude).

    Parameters
    ----------
    project : Project
        The project instance used for filtering documents.
    filters : dict
        The filter data.
    filter_type : str
        The type of filter to apply ("filter-union" or "filter-exclude").

    Returns
    -------
    set[int]
        A set of document IDs that match the applied filters.
    """
    document_set = set()
    filter_list = [v for k, v in filters.items() if filter_type in k]
    for filter_dict in filter_list:
        filter_sets = [
            get_documents_by_topic(project, filter_dict.get("Topic", [])),
            get_documents_by_norm(project, filter_dict.get("Norm", [])),
            get_documents_by_descriptor(
                project, filter_dict.get("descriptors", [])
            ),
            get_documents_by_keyword(project, filter_dict.get("Keyword", [])),
            get_documents_by_no_decis(
                project, filter_dict.get("No_decis", [])
            ),
            get_documents_by_result(project, filter_dict.get("Result", [])),
            get_documents_by_year_range(
                project, filter_dict.get("year_range", [])
            ),
        ]
        intersection_set = get_intersection_of_non_empty_sets(filter_sets)
        document_set |= intersection_set

    return document_set


def get_documents_by_topic(project: Project, topics: list[str]) -> set[int]:
    """Retrieve document IDs filtered by topic."""
    result = set()

    for topic in topics:
        if topic == UNCLASSIFIED_PAPERS_TOPIC:
            cluster_elements = ClusterElement.objects.filter(
                cluster__project=project,
                cluster__topic=UNCLASSIFIED_PAPERS_TOPIC,
            ).values_list("document__pk", flat=True)
            result.update(cluster_elements)

        else:
            prepared_topic = topic.split(": ")[1]
            cluster_elements = ClusterElement.objects.filter(
                cluster__project=project,
                cluster__topic__startswith=prepared_topic,
            ).values_list("document__pk", flat=True)
            result.update(cluster_elements)

    return result


def get_documents_by_descriptor(
    project: Project, descriptors: list[str]
) -> set[int]:
    """Retrieve document IDs filtered by descriptors."""
    result = set()
    for desc in descriptors:
        regex_key = r".*" + desc.strip() + r".*"
        documents = Document.objects.filter(
            project=project, descriptors__iregex=regex_key
        ).values_list("pk", flat=True)

        result.update(documents)
    return result


def get_documents_by_norm(project: Project, norms: list[str]) -> set[int]:
    """Retrieve document IDs filtered by norm."""
    result = set()
    for norm in norms:
        regex_key = r".*" + norm.strip() + r".*"
        documents = Document.objects.filter(project=project).filter(
            Q(standards__iregex=regex_key)
        )
        result.update(documents.values_list("pk", flat=True))
    return result


def get_documents_by_keyword(
    project: Project, keywords: list[str]
) -> set[int]:
    """Retrieve document IDs filtered by keyword."""
    result = set()
    for keyword in keywords:
        regex_key = r".*" + keyword + r".*"
        documents = Document.objects.filter(project=project).filter(
            Q(prepared_for_ngrams__iregex=regex_key)
        )
        result.update(documents.values_list("pk", flat=True))
    return result


def get_documents_by_no_decis(
    project: Project, no_decis: list[str]
) -> set[int]:
    """Retrieve document IDs filtered by 'no_decis'."""
    result = set()
    for no_d in no_decis:
        documents = Document.objects.filter(
            project=project, raw_document_id=no_d
        ).exclude(document__clusterelement__isnull=True)
        result.update(documents.values_list("pk", flat=True))
    return result


def get_documents_by_result(project: Project, results: list[str]) -> set[int]:
    """Retrieve document IDs filtered by result."""
    result = set()
    for result_value in results:
        if result_value == "NO RESULT":
            documents = Document.objects.filter(
                project=project, result=""
            ).exclude(document__clusterelement__isnull=True)
        else:
            documents = Document.objects.filter(
                project=project, result=result_value
            )
        result.update(documents.values_list("pk", flat=True))
    return result


def get_documents_by_year_range(
    project: Project, year_ranges: list[str]
) -> set[int]:
    """Retrieve document IDs filtered by year range."""
    result = set()
    for year_range in year_ranges:
        if "-" in year_range:
            start_year, end_year = year_range.split("-")
        else:
            start_year = end_year = year_range
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"
        documents = Document.objects.filter(
            project=project, decision_date__range=(start_date, end_date)
        ).exclude(clusterelement__isnull=True)
        result.update(documents.values_list("pk", flat=True))
    return result


def get_intersection_of_non_empty_sets(sets: list[set[int]]) -> set[int]:
    """Return the intersection of non-empty sets."""
    non_empty_sets = [s for s in sets if s]
    if non_empty_sets:
        intersection_set = non_empty_sets[0]
        for s in non_empty_sets[1:]:
            intersection_set &= s
        return intersection_set
    return set()


def remove_refinement(
    user: User, project: Project, refinement_id: int
) -> None:
    ProjectRefinement.objects.filter(
        owner=user, project=project, id=refinement_id
    ).delete()


def create_refinement(
    user: User,
    project: Project,
    refinement_name: str,
    number_documents: int,
    filters: str,
    origin: ProjectRefinement | None = None,
) -> int:
    """Save the actual state of all TableChoices objects.
    Give a name to this actual states and saves it into refinement json file.

    Parameters
    ----------
    user : User
        Refinement owner.
    research : Research object Model database
        The research object model where is used to store
        search query, status and related data.
    refinement_name : str
        name of the refinment.
    number_documents : int
        documents in the new created refinement.
    origin : ResearchRefinement object model database
        Parent of the refinement.
    """

    refinement = ProjectRefinement.objects.create(
        project=project,
        owner=user,
        name=f"{refinement_name} ({number_documents} documents)",
        origin=origin,
        filters=json.dumps(filters),
    )

    return refinement.id


def load_last_iteration(
    user: User, project: Project, refinement_id: int
) -> None:
    """Loads the last iteration from the given refinement id

    Parameters
    ----------
    user : User
        Refinement owner.
    research : Research object Model database
        The research object model where is used to store
        search query, status and related data.
    refinement_id : int
        Refinement object id which is related with the iterations.
    """
    last_iteration = RefinementIteration.objects.filter(
        refinement_id=refinement_id
    ).last()

    if last_iteration:
        get_iteration(user, project, refinement_id, last_iteration.id)
