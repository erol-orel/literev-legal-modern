import datetime
import logging

from typing import cast

import psycopg2

from django.conf import settings

from literev.libs.collectors import ElasticSearchCollector, MetaData
from literev.libs.pipeline import create_document_db
from literev.models import Project

# from literev.tasks import launch_process


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
            f"SELECT count(*) FROM trials WHERE study_id={study_id};"
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


def count_all_corpus():
    es_collector = ElasticSearchCollector()
    result = 0
    # fetch the total documents from elastic search
    # It could happen that ES is not working at the moment
    try:
        result += es_collector.count_all_corpus()
    except Exception as e:
        logging.warning("ElasticSearch Error in counting all documents")
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
    for document in documents:
        try:
            create_document_db(project, document)
        except Exception as e:
            logging.error(
                f"Failed to save document ID: {document.doc_id} - {e}"
            )


# WORKAROUND: Keeping this code commented for future legal documents processing
# def process_all_documents():
#     total_documents = count_all_corpus()

#     project = Project.objects.create(
#         name="Process all corpus",
#         creation_date=datetime.datetime.now(),
#         query="#PROCESS-ALL-CORPUS-LITEREV-00",
#         total_documents=total_documents,
#     )

#     if launch_process(project):
#         logging.info("Starting processing the whole corpus")
#     else:
#         logging.warning("error trying to process the whole corpus")

#     return
