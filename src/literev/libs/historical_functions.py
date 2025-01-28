from __future__ import annotations

from django.db.models import Case, When
from django.db.models.query import QuerySet

from literev.models import (
    ClusterElement,
    Project,
    User,
)


def get_projects_list(project_id_list: list[int]) -> QuerySet[Project]:
    """
    Return a QuerySet of Project objects model db in
    the sorted by its ids in Project_id_list

    Parameters
    ----------
    Project_id_list : list[int]
        A list of Project ids

    Returns
    -------
    Project_sorted : Query(Project)
        A QuerySet that has Project objects

    """
    preferred = Case(
        *(
            When(id=id, then=pos)
            for pos, id in enumerate(project_id_list, start=1)
        )
    )
    projects_sorted = Project.objects.filter(id__in=project_id_list).order_by(
        preferred
    )

    return projects_sorted


def filter_and_sort_projects(
    user: User, keywords: list[str], sort_type: str
) -> list[Project]:
    """
    Filter project by keywords and sort by ClusterElements count.

    Parameters
    ----------
    user: User
        user object owner.
    keywords : list[str]
        A list of keywords.
    sort_type : str
        A string indicating the way of sorting.

    Returns
    -------
    Queryset[Project]
        A sorted QuerySet that has Project objects

    """
    for keyword in keywords:
        key_regex = r".*" + keyword + r".*"
        projects_queryset = Project.objects.filter(
            user=user,
            query__iregex=key_regex,
            is_finish=True,
        )
        project_id_count = {}

        for project in projects_queryset:
            project_id_count[project.id] = ClusterElement.objects.filter(
                cluster__project=project
            ).count()

    if sort_type == "more_documents_first":
        sorted_id_list = list(
            sorted(
                project_id_count.keys(),
                key=lambda x: project_id_count[x],
                reverse=True,
            )
        )

    elif sort_type == "less_documents_first":
        sorted_id_list = list(
            sorted(project_id_count.keys(), key=lambda x: project_id_count[x])
        )
    else:
        sorted_id_list = list(project_id_count.keys())

    return get_projects_list(sorted_id_list)


def sort_all_projects(user: User, sort_type: str) -> list[Project]:
    """
    Sorts project by ClusterElements count.

    Parameters
    ----------
    user: User
        user object owner.
    sort_type : str
        A string indicating the way of sorting.

    Returns
    -------
     Queryset[Project]
        A sorted QuerySet that has Project objects

    """
    projects_query_set = Project.objects.filter(user=user, is_finish=True)

    project_id_count = {}
    for project in projects_query_set:
        project_id_count[project.id] = ClusterElement.objects.filter(
            cluster__project=project
        ).count()

    if sort_type == "more_documents_first":
        sorted_id_list = list(
            sorted(
                project_id_count.keys(),
                key=lambda x: project_id_count[x],
                reverse=True,
            )
        )

    elif sort_type == "less_documents_first":
        sorted_id_list = list(
            sorted(project_id_count.keys(), key=lambda x: project_id_count[x])
        )
    else:
        sorted_id_list = list(project_id_count.keys())

    return get_projects_list(sorted_id_list)
