import logging
import os

from celery import chain
from celery.result import AsyncResult
from django.conf import settings
from django.db import transaction

# Local imports
from config.celery import app
from literev.libs.collectors import ElasticSearchCollector
from literev.libs.pipeline import (
    update_pp_document,
)
from literev.libs.utils import save_documents_to_db, update_task_code
from literev.models import Document, Project, User
from literev.task_clustering import back_clustering_documents
from literev.task_plotting import back_plotting_documents
from literev_core.preprocessing import (
    create_ngrams,
    prepare_document,
    preprocess_documents,
    update_prepared_document,
)

logger = logging.getLogger(__name__)


def running_delete(project_id: str | int) -> None:
    project = Project.objects.filter(pk=project_id).first()
    # Using try and except in case the project is finish
    try:
        task_id = project.actual_task_code
        if task_id:
            task = AsyncResult(task_id)
            task.revoke(terminate=True, signal="SIGKILL")

    except:
        logging.info(
            f"There is no celery task code for project id: {project.id}"
        )

    project = Project.objects.filter(pk=project_id).first()

    project.delete()

    plot_path = settings.PLOT_DATA / f"{project_id}_plot.html"
    div_path = settings.PLOT_DATA / f"{project_id}_div.html"
    script_path = settings.PLOT_DATA / f"{project_id}_script.html"

    paths = [plot_path, div_path, script_path]

    for path in paths:
        if os.path.isfile(path):
            os.remove(path)


def remove_all_finished_projects(user: User) -> None:
    projects_query = Project.objects.filter(user=user, is_finish=True)

    for project in projects_query:
        running_delete(project.id)


def launch_process(project: Project) -> bool:
    """
    Initiates the document processing workflow for a given project.

    Parameters
    ----------
    project : Project
        The project instance containing details about the project.

    Returns
    -------
    bool
        True if the process was successfully started, False otherwise.
    """
    logger.info(f"Starting process for project {project.id}.")

    with transaction.atomic():
        if project.is_finish or project.is_running:
            return False

        # Pass the selected_indices as an argument to the first task
        task_chain = chain(
            back_get_documents.si(project.id),
            back_preparing_documents.si(project.id),
            back_preprocess_documents.si(project.id),
            back_clustering_documents.si(project.id),
            back_plotting_documents.si(project.id),
        )

        task_chain.apply_async()
        project.is_running = True
        project.save()

    logger.info(f"Processing workflow initiated for project {project.id}.")
    return True


@app.task(bind=True)
def back_get_documents(self, project_id: int) -> bool:
    """
    Fetches documents based on the project's criteria for each selected index and saves them into the database.

    Parameters
    ----------
    project_id : int
        The ID of the project for which documents are fetched.

    Returns
    -------
    bool
        True if documents were successfully fetched and saved, False otherwise.
    """

    process_all_corpus_query = str(settings.PROCESS_ALL_CORPUS_QUERY)

    project = Project.objects.get(id=project_id)
    update_task_code(project, self.request.id)

    indices = project.selected_indices
    project_query = project.query
    start_date = project.range_begin_date
    end_date = project.range_end_date

    logger.info(
        f"Starting document collection for project {project_id} with query: {project_query}"
    )

    failed_indices = []

    for index in indices:
        logger.info(f"Processing index: {index}")
        try:
            collector = ElasticSearchCollector(index_name=index)

            if project.query == process_all_corpus_query:
                documents = collector.collect_all_documents()
            else:
                documents = collector.collect_documents(
                    project_query, start_date, end_date
                )

            save_documents_to_db(project, documents)

            logger.info(f"Successfully saved documents for index: {index}")

        except Exception as e:
            logger.error(
                f"Failed to collect documents for index: {index}: {e}"
            )
            failed_indices.append(index)

    if failed_indices:
        logger.error(
            f"Document collection failed for indices: {', '.join(failed_indices)}"
        )
        return False

    project.step = "preparing"
    project.save()
    logger.info(
        f"Document collection and saving completed successfully for project {project_id}"
    )
    return True


@app.task(bind=True)
def back_preparing_documents(self, project_id: int):
    """
    Prepares documents for n-gram extraction by processing raw document text.

    Parameters
    ----------
    project_id : int
        The ID of the project for which documents are prepared.
    """

    project = Project.objects.get(id=project_id)

    update_task_code(project, self.request.id)

    documents = Document.objects.filter(project=project)
    logger.info(f"Documents from Database: {documents.count()}")

    # Getting all documents with no emtpy document_text field

    document_list = [
        document
        for document in documents
        if document.raw_document_text and not document.prepared_for_ngrams
    ]

    for document in document_list:
        try:
            result = prepare_document(document)
            if result:
                update_prepared_document(document, result)
            else:
                logger.info(
                    f"Rejected Document ID: {document.raw_document_id}, PK: {document.pk}"
                )
        except:
            logger.info(
                f"Failed preparing Document ID: {document.raw_document_id}, PK: {document.pk}"
            )

    logger.info("Success preparing Documents")
    project.step = "preprocessing"
    project.save()


@app.task(bind=True)
def back_preprocess_documents(self, project_id: int):
    """
    Processes documents to extract n-grams and other preprocess steps.

    Parameters
    ----------
    project_id : int
        The ID of the project for which documents are preprocessed.
    """

    project = Project.objects.get(id=project_id)

    update_task_code(project, self.request.id)

    documents = Document.objects.filter(project=project)
    document_pk_list = []
    document_corpus_list = []
    logger.info("Getting Documents from Database...")

    document_corpus_list = [
        document.prepared_for_ngrams
        for document in documents
        if document.prepared_for_ngrams
    ]
    document_pk_list = [
        document.pk for document in documents if document.prepared_for_ngrams
    ]
    # Getting all documents with no emtpy document_text field
    logger.info(f"Documents for ngrams: {len(document_pk_list)}")
    try:
        list_trigrams = create_ngrams(document_corpus_list)

    except Exception as e:
        logger.info(f"Failed in creating ngrams {e}")
        return

    try:
        # using preprocessing_m from literev_core
        preprocessed_corpus_list = preprocess_documents(list_trigrams)
        logger.info("Getting preprocessed Documents")

    except Exception as e:
        logger.error("Literev_Core failed in preprocessing")
        logger.error(e)
        return

    logger.info(
        f"Equal number of Documents: {len(document_pk_list)==len(preprocessed_corpus_list)}"
    )

    for pk, pp_corpus in zip(document_pk_list, preprocessed_corpus_list):
        try:
            update_pp_document(pk, pp_corpus)

        except Exception as e:
            logger.error(f"Adding preprocessed Document failed. Doc ID: {pk}")
            logger.error(e)
            continue
    project.step = "clustering"
    project.save()
    logger.info("Success preprocessing Documents")
