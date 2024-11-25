import datetime
import logging

from typing import cast

import joblib
import psycopg2

from django.conf import settings

from literev.libs.collectors import ElasticSearchCollector, MetaData
from literev.libs.pipeline import create_document_db
from literev.models import Project


def update_task_code(project: Project, task_code) -> None:
    project.actual_task_code = task_code
    project.save()


def get_study_name(project: Project) -> str:
    """
    Constructs the project study name.

    It is used for optuna optimization.

    Returns
    -------
    str
        A string which is study name related with the project.
    """

    return f"study_{project.id}"


def get_database_uri() -> str:
    """
    Constructs the database URI from environment variables.
    the database is expected to be used by optuna library in optimization.

    Returns
    -------
    str
        A string representing the PostgreSQL database URI.
    """

    db = settings.DATABASES["default"]
    return f"postgresql://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"


def count_trials(project: Project) -> int:
    """
    Counts the trials for project from optuna database.

    Returns
    -------
    counter : int
        A number of trials made for project.
    """
    try:
        database_uri = get_database_uri()
        conn = psycopg2.connect(database_uri)
        cursor = conn.cursor()
        study_name_research = get_study_name(project)

        cursor.execute(
            f"SELECT study_id FROM studies WHERE study_name='{study_name_research}';"
        )

        study_id = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT count(*) FROM trials WHERE study_id={study_id} AND state='COMPLETE';"
        )

        counter = cast(int, cursor.fetchone()[0])

        conn.close()

    except TypeError:
        counter = 0

    return counter


def get_number_documents(
    index_name: str,
    query: str,
    range_begin_date: datetime.date,
    range_end_date: datetime.date,
) -> int:
    es_collector = ElasticSearchCollector(index_name=index_name)
    result = 0
    try:
        result += es_collector.get_max_documents(
            query, range_begin_date, range_end_date
        )
    except Exception as e:
        logging.warning(e)

    return result


def save_documents_to_db(project: Project, documents: list[MetaData]) -> None:
    """
    Saves a list of documents into the database for a specific project.

    Parameters
    ----------
    project : Project
        The project for which documents are saved.
    documents : list[MetaData]
        A list of metadata objects representing the documents to be saved.
    """
    es_scores_dict = {}
    for document in documents:
        try:
            new_project_id = create_document_db(project, document)
            es_scores_dict[new_project_id] = document.es_score
        except Exception as e:
            logging.error(
                f"Failed to save document ID: {document.doc_id} - {e}"
            )
    # Saving elastic search scores
    joblib.dump(
        es_scores_dict,
        settings.ARTICLE_DATA / f"es_scores_project_{project.id}.pkl",
    )
