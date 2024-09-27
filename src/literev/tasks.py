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
    create_document_db,
    update_pp_document,
)
from literev.libs.utils import update_task_code
from literev.models import Document, Project
from literev.task_clustering import back_clustering_documents
from literev.task_plotting import back_plotting_documents
from literev_core.preprocessing import (
    create_ngrams,
    prepare_document,
    preprocess_documents,
    update_prepared_document,
)

logger = logging.getLogger(__name__)


def running_delete(project_id: str) -> None:
    project = Project.objects.filter(pk=project_id).first()
    # Using try and except in case the project is finish
    try:
        task_id = project.actual_task_code
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

    # Use a database transaction to ensure data integrity
    with transaction.atomic():
        # Reload the project instance from the database to avoid stale data
        # Double check the project's state to avoid race conditions
        if project.is_finish or project.is_running:
            return False

        # The chain primitive lets us link together signatures so that one is called
        # after the other, essentially forming a chain of callbacks.
        task_chain = chain(
            back_get_documents.si(project.id),
            back_preparing_documents.si(project.id),
            back_preprocess_documents.si(project.id),
            back_clustering_documents.si(project.id),
            back_plotting_documents.si(project.id),
        )

        # Use delay() for the task chain when the execution is straightforward and
        # you don't need any specific configurations for how the chain should execute.
        # Use apply_async() when you need to configure particular execution parameters for the chain,
        # like scheduling, prioritizing, or assigning to specific queues.

        task_chain.apply_async()
        # Update the project's state to reflect that it is now running
        project.is_running = True
        project.save()

    logger.info(f"Processing workflow initiated for project {project.id}.")
    return True


@app.task(bind=True)
def back_get_documents(self, project_id: int):
    """
    Fetches documents based on the project's criteria and saves them into the database.

    Parameters
    ----------
    project_id : int
        The ID of the project for which documents are fetched.
    """
    project = Project.objects.get(id=project_id)

    update_task_code(project, self.request.id)

    es_collector = ElasticSearchCollector()

    try:
        documents_list = es_collector.collect_documents(
            project.query, project.range_begin_date, project.range_end_date
        )

    except Exception as e:
        logger.error("ElasticSearchCollector Failed")
        logger.error(e)
        return False

    for document in documents_list:
        try:
            create_document_db(project, document)

        except Exception as e:
            logger.error(f"Document creation failed, ID: {document.doc_id}")
            logger.error(e)

    logger.info("Success getting Documents")
    project.step = "preparing"
    project.save()

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
    project.step = "processing"
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
