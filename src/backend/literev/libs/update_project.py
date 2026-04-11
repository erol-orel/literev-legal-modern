from datetime import date

from literev.libs.collectors import ElasticSearchCollector
from literev.models import ClusterElement, Project


def estimate_new_documents(project: Project) -> int:
    """
    Return the estimated number of new documents for given project.
    to assess the new documents update the range_end_date with today's date
    after that uses the same query with updated date range.

    Parameters
    ----------
    project : Project
        The project instance containing details about the project.

    Returns
    -------
    int
        number of estimated documents fot the project.
    """
    count = 0

    for index_name in project.selected_indices:
        collector = ElasticSearchCollector(index_name)
        today = date.today()
        count += collector.get_max_documents(
            project.query, project.range_end_date, today
        )

    return count


def get_actual_number_documents(project: Project) -> int:
    """
    Return the total number of processed document for given project.

    Parameters
    ----------
    project : Project
        The project instance containing details about the project.

    Returns
    -------
    int
        total number of processed documents inside project.
    """

    return ClusterElement.objects.filter(cluster__project=project).count()
