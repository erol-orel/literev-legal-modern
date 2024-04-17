from __future__ import annotations

import json

from typing import Any

from django.db.models import Q

from literev.models import (
    ClusterElement,
    Document,
    Project,
)


def get_filters(
    project: Project, post_data: dict[str, str]
) -> dict[str, dict[str, Any]]:
    """
    Return a filter dictionary from the post_data

    Use the post_data (request.POST) as a argument to extract
    the key, values where key start with "filter.." and convert its
    str value to json object and from there add the starting value to
    filter for the function get_filtered_documents.

    Parameters
    ----------
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    post_data : a request.POST dictionary dict [str, str]
        A dictionary obtained from the frontend has the filters sent by
        the user

    Returns
    -------
    filters : A dictonary of filters
        This variable will be used in get_filtered_documents
    """
    filters: dict[str, Any] = {}

    for key, value in post_data.items():
        if "filter" in key:
            if value != "{}":
                filters[key] = json.loads(value)

    return filters


def get_filtered_document(
    project: Project, filters: dict[str, Any]
) -> list[int]:
    """
    Return a list of documents id that have been filtered

    Using the `filters` dictionary and `project` get the filtered
    documents and return its id in a list.

    Parameters
    ----------
    project : Project object Model database
        The project object model where is used to store
        search query, status and related data.
    filters : A dictionary of filters
        This has the format {"filter_0": "keyword":[keyword01,...]...}

    Returns
    -------
    list_id : list[int]
        A list of filtered documents id.
    """
    union_documents = set()
    excluded_documents = set()
    document_center_set: set[int] = set()

    filter_union_list = [v for k, v in filters.items() if "filter-union" in k]
    filter_exclude_list = [
        v for k, v in filters.items() if "filter-exclude" in k
    ]

    for filter_dict in filter_union_list:
        topic_set = set()
        norm_set = set()
        keyword_set = set()
        no_decis_set = set()

        intersection_set = set()

        # suggested code
        # topic_list = functools.reduce(operator.iadd, [v for k, v in filter_dict.items() if k == "Topic"], [])
        # ignoring rule because readability
        topic_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "Topic"], start=[]
        )
        for topic in topic_list:
            cluster_elements = ClusterElement.objects.filter(
                cluster__project=project,
                cluster__topic=topic,
            )
            for cluster in cluster_elements:
                topic_set.add(cluster.document.pk)

        norm_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "Norm"], start=[]
        )

        for norm in norm_list:
            regex_key = r".*" + norm + r".*"
            document_list = Document.objects.filter(
                project=project,
            ).filter(
                Q(standards__iregex=regex_key),
            )

            for document in document_list:
                norm_set.add(document.pk)

        keyword_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "Keyword"], start=[]
        )

        for keyword in keyword_list:
            regex_key = r".*" + keyword + r".*"
            document_list = Document.objects.filter(project=project).filter(
                Q(preprocessed_document__iregex=regex_key)
            )

            for document in document_list:
                keyword_set.add(document.pk)

        no_decis_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "No_decis"], start=[]
        )

        for no_d in no_decis_list:
            documents = Document.objects.filter(
                project=project,
                raw_document_id=no_d,
            )

            for document in documents:
                no_decis_set.add(document.pk)

        set_list = [
            norm_set,
            no_decis_set,
            keyword_set,
            topic_set,
        ]

        non_empty_set = [elem for elem in set_list if elem]

        if non_empty_set:
            intersection_set = non_empty_set[0]

            for elem_set in non_empty_set[1:]:
                intersection_set &= elem_set

            union_documents |= intersection_set

    for filter_dict in filter_exclude_list:
        topic_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "Topic"], start=[]
        )

        for topic in topic_list:
            # get all cluster element object with the topic
            cluster_elements = ClusterElement.objects.filter(
                cluster__topic=topic, cluster__project=project
            )
            for cluster in cluster_elements:
                excluded_documents.add(cluster.document.pk)

        norm_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "Norm"], start=[]
        )

        for norm in norm_list:
            regex_key = r".*" + norm + r".*"
            document_list = Document.objects.filter(
                project=project,
            ).filter(
                Q(standards__iregex=regex_key),
            )
            for document in document_list:
                excluded_documents.add(document.pk)

        keyword_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "Keyword"], start=[]
        )

        for keyword in keyword_list:
            regex_key = r".*" + keyword + r".*"
            document_list = Document.objects.filter(project=project).filter(
                Q(preprocessed_document__iregex=regex_key)
            )

            for document in document_list:
                excluded_documents.add(document.pk)

        no_decis_list = sum(  # noqa: RUF017
            [v for k, v in filter_dict.items() if k == "No_decis"], start=[]
        )

        for no_d in no_decis_list:
            documents = Document.objects.filter(
                project=project,
                raw_document_id=no_d,
            )

            for document in documents:
                excluded_documents.add(document.pk)

    # check if union_documents are empty because no filter was added
    # in that union_documents should be all documents in the clusters
    if not union_documents:
        empty_filters = True
        for filter_type in filters.keys():
            if "filter-union" in filter_type:
                empty_filters = False
        if empty_filters:
            all_cluster_elements = ClusterElement.objects.filter(
                cluster__project=project
            )

            for cluster_element in all_cluster_elements:
                union_documents.add(cluster_element.document.pk)

    filtered_documents = union_documents - excluded_documents
    list_id: list[int] = list(document_center_set) + list(filtered_documents)

    return list_id


def distant_from_center(
    pos_x: float, pos_y: float, center: tuple[float, float]
) -> float:
    return (center[0] - pos_x) ** 2 + (center[1] - pos_y) ** 2


def neighbour_document(document: Document, project: Project) -> list[Document]:
    """
    Return a list of document but there isn't the center document in the list.

    The function take an document, a project and process with clusterelement
    object, the nearest neighbor. By default, take the 5 nearest.
    by iteration, search around the document +-100 and if doesn't
    have enough, the same but with +-200 around. We make max +-1000.
    """
    number_neighbor = project.number_neighbour
    neighbour_documents: list[Document] = []
    distant = 100
    cluster_center_document_list = ClusterElement.objects.filter(
        document=document, cluster__project=project
    )
    # if the document doesn't exist in the cluster
    if not cluster_center_document_list.exists():
        return neighbour_documents

    cluster_center_document = cluster_center_document_list[0]
    center = (cluster_center_document.pos_x, cluster_center_document.pos_y)

    nearest_cluster: list[ClusterElement] = []

    while True:
        if len(nearest_cluster) >= number_neighbor or distant > 1000:
            break

        cluster_list = ClusterElement.objects.filter(
            cluster__project=project,
            pos_x__gte=center[0] - distant,
            pos_x__lte=center[0] + distant,
            pos_y__gte=center[1] - distant,
            pos_y__lte=center[1] + distant,
        )

        for cluster in cluster_list:
            # if this is the cluster of the center document pass to next
            # iteration
            if cluster.document == document:
                continue

            # if there are some place, add the cluster
            if len(nearest_cluster) < number_neighbor:
                nearest_cluster.append(cluster)
            else:
                # else, check distant from center with all cluster in list
                # if there is one who is better, the new replace the ancient
                for i in range(len(nearest_cluster)):
                    ancient_distant = distant_from_center(
                        nearest_cluster[i].pos_x,
                        nearest_cluster[i].pos_y,
                        center,
                    )
                    new_distant = distant_from_center(
                        cluster.pos_x, cluster.pos_y, center
                    )
                    if new_distant < ancient_distant:
                        nearest_cluster[i] = cluster
                        break

        distant += 100

    # recuperate all document from cluster list
    for cluster in nearest_cluster:
        neighbour_documents.append(cluster.document)

    return neighbour_documents
