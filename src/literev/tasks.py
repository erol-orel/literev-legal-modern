import logging
import os

from datetime import date
from typing import Iterator

import pandas as pd

from celery import chain
from celery.result import AsyncResult
from django.conf import settings
from django.db import transaction
from django.db.models.query import QuerySet
from sklearn.feature_extraction.text import TfidfVectorizer

# Local imports
from config.celery import app
from literev.libs.collectors import ElasticSearchCollector
from literev.libs.data_files import get_es_scores
from literev.libs.pipeline import (
    update_pp_document,
)
from literev.libs.rag_pdf import CustomRagAnswersGenerator, RagAnswersManager
from literev.libs.scoring import (
    sort_documents_by_es_score,
)
from literev.libs.utils import (
    save_documents_to_db,
    update_es_scores_file,
    update_task_code,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectRAG,
    User,
)
from literev.task_clustering import back_clustering_documents
from literev.task_plotting import back_plotting_documents
from literev_core.clustering import pacmap_default
from literev_core.preprocessing import (
    create_ngrams,
    prepare_document,
    preprocess_documents,
    update_prepared_document,
)

logger = logging.getLogger(__name__)

CLUSTERING_MIN_DOCUMENTS = settings.CLUSTERING_MIN_DOCUMENTS


def get_shared_projects_ids() -> list[int]:
    return [
        project.id
        for project in Project.objects.filter(
            query="#PROCESS-ALL-CORPUS-LITEREV-00"
        )
    ]


def running_delete(project_id: str | int) -> None:
    # Avoid to remove SHARED projects
    if int(project_id) in get_shared_projects_ids():
        return

    project = Project.objects.filter(pk=project_id).first()

    if not project:
        logging.debug(f"There is no project with id: {project_id}")
        return

    # Using try and except in case the project is finish
    try:
        task_id = project.actual_task_code
        if task_id:
            task = AsyncResult(task_id)
            task.revoke(terminate=True, signal="SIGKILL")

    except:
        logging.info(
            f"There is no celery task code for project id: {project_id}"
        )

    project = Project.objects.filter(pk=project_id).first()

    if project:
        project.delete()

    plot_path = settings.PLOT_DATA / f"{project_id}_plot.html"
    div_path = settings.PLOT_DATA / f"{project_id}_div.html"
    script_path = settings.PLOT_DATA / f"{project_id}_script.html"
    hdbscan_scores_path = (
        settings.ARTICLE_DATA / f"hdbscan_scores_project_{project_id}.pkl"
    )
    list_id_docs_path = (
        settings.ARTICLE_DATA / f"id_list_project_{project_id}.pkl"
    )
    tf_idf_path = settings.ARTICLE_DATA / f"tf_idf_project_{project_id}.pkl"
    columns_name_path = (
        settings.ARTICLE_DATA / f"column_name_project_{project_id}.pkl"
    )

    paths = [
        plot_path,
        div_path,
        script_path,
        hdbscan_scores_path,
        list_id_docs_path,
        tf_idf_path,
        columns_name_path,
    ]

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
            get_nl_rag_ans.si(project.id),
            back_preparing_documents.si(project.id),
            back_preprocess_documents.si(project.id),
            back_get_early_results.si(project.id),
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
    project.step = "getting_documents"
    project.save()

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

    logger.info(
        f"Document collection and saving completed successfully for project {project_id}"
    )
    return True


def get_top_docs_by_es(
    project: Project, documents: list[Document], n: int = 1
) -> list[Document]:
    scores = get_es_scores(project)

    if scores:
        sorted_tablechoice = sort_documents_by_es_score(project, documents)
        top10_docs = sorted_tablechoice[:n]
        return top10_docs

    return []


@app.task(bind=True)
def get_nl_rag_ans(self, project_id: int) -> None:
    project = Project.objects.get(id=project_id)

    if not project.natural_language_query:
        return None

    project = Project.objects.get(id=project_id)
    project.step = "question-answering"
    project.save()

    project_rag, _ = ProjectRAG.objects.get_or_create(
        project=project,
        query=project.natural_language_query,
    )

    documents = Document.objects.filter(project=project)
    number_documents = documents.count()

    upper_limit = number_documents

    top_docs = get_top_docs_by_es(project, list(documents), upper_limit)
    if not top_docs:
        return None

    docs_ids = [doc.id for doc in top_docs]
    max_doc_ans = min(10, number_documents)

    if (
        "chambre_penale" in project.selected_indices
        or "chambre_civile" in project.selected_indices
    ):
        rag_op = CustomRagAnswersGenerator(
            project_rag_id=project_rag.id,
            documents_ids=docs_ids,
            chambre_name=project.selected_indices[0],
        )
        rag_op.get_and_save_answers_from_documents(max_doc_ans=max_doc_ans)
    else:
        rag = RagAnswersManager(
            project_rag_id=project_rag.id,
            documents_ids=docs_ids,
        )
        rag.run_pipeline(max_doc_ans=max_doc_ans)

    return None


@app.task(bind=True)
def back_get_early_results(self, project_id: int) -> None:
    """
    Generates early reduction of dimensionality and create early 2d map in
    cluster and cluster elements objects
    """
    project = Project.objects.get(id=project_id)
    documents = (
        Document.objects.filter(project=project)
        .exclude(preprocessed_document__isnull=True)
        .exclude(preprocessed_document="")
    )

    if documents.count() < CLUSTERING_MIN_DOCUMENTS:
        return

    pp_documents = [
        pp_doc
        for pp_doc in documents.values_list("preprocessed_document", flat=True)
    ]

    if not pp_documents:
        logger.info("There are no preprocessed documents for research")
        return

    list_doc_ids = [
        id_doc for id_doc in documents.values_list("id", flat=True)
    ]

    update_task_code(project, self.request.id)

    cluster = Cluster.objects.create(
        project=project, topic="Cluster from early results"
    )

    tfidfVectorizer = TfidfVectorizer()
    tf_idf = tfidfVectorizer.fit_transform(pp_documents)

    embedding_2d_array = pacmap_default(tf_idf)

    embedding_df = pd.DataFrame(embedding_2d_array)

    for i, doc_id in enumerate(list_doc_ids):
        ClusterElement.objects.create(
            document_id=doc_id,
            cluster=cluster,
            pos_x=embedding_df[0][i],
            pos_y=embedding_df[1][i],
        )

    logger.info("Success preparing early results")


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
    project.step = "preparing"
    project.save()

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
    project.step = "preprocessing"
    project.save()

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
        f"Equal number of Documents: {len(document_pk_list) == len(preprocessed_corpus_list)}"
    )

    for pk, pp_corpus in zip(document_pk_list, preprocessed_corpus_list):
        try:
            update_pp_document(pk, pp_corpus)

        except Exception as e:
            logger.error(f"Adding preprocessed Document failed. Doc ID: {pk}")
            logger.error(e)
            continue

    logger.info("Success preprocessing Documents")


@app.task
def task_rag_result_table(
    project_rag_id: int,
    document_ids: list[int],
) -> int:
    """Run RAG for the data from result table."""
    try:
        project_rag = ProjectRAG.objects.get(id=project_rag_id)
        if (
            "chambre_penale" in project_rag.project.selected_indices
            or "chambre_civile" in project_rag.project.selected_indices
        ):
            rag = CustomRagAnswersGenerator(
                project_rag_id,
                document_ids,
                project_rag.project.selected_indices[0],
            )
            rag.get_and_save_answers_from_documents()
        else:
            rag = RagAnswersManager(  # type: ignore
                project_rag_id=project_rag.id,
                documents_ids=document_ids,
            )
            rag.run_pipeline()  # type: ignore

    except Exception as e:
        logging.error(f"[task_rag_result_table] (#{project_rag_id}): {e}")
        project_rag_fallback = ProjectRAG.objects.filter(
            id=project_rag_id
        ).first()
        if project_rag_fallback:
            project_rag_fallback.status = "failed"
            project_rag_fallback.save()
        raise e

    return project_rag_id


@app.task(bind=True)
def back_get_update_documents(
    self,
    old_project_id: int,
    new_project_id: int,
    pair_document_ids: list[tuple[int, int]],
) -> bool:
    """
    Fetches documents based on the project's criteria for each selected index and saves them into the database.

    Parameters
    ----------
    old_project_id : int
        The ID of the project for which documents are being updated.
    new_project_id : int
        The ID of the project which will be the updated version for old project
        and will fetch new documents.

    Returns
    -------
    bool
        True if documents were successfully fetched and saved, False otherwise.
    """

    old_project = Project.objects.get(id=old_project_id)
    new_project = Project.objects.get(id=new_project_id)

    update_task_code(new_project, self.request.id)

    indices = new_project.selected_indices
    new_project_query = new_project.query
    start_date = old_project.range_end_date
    end_date = new_project.range_end_date

    logger.info(
        f"Starting document collection for project {old_project_id} with query: {new_project_query}"
    )

    failed_indices = []

    for index in indices:
        logger.info(f"Processing index: {index}")
        try:
            collector = ElasticSearchCollector(index_name=index)

            documents = collector.collect_documents(
                new_project_query, start_date, end_date
            )

            save_documents_to_db(new_project, documents)

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

    update_es_scores_file(old_project_id, new_project_id, pair_document_ids)

    new_project.step = "preparing"
    new_project.save()
    logger.info(
        f"Document collection and saving completed successfully for project {new_project_id}"
    )
    return True


def divide_in_chunks_query(
    query_set: QuerySet[Document], batch_size: int = 500
) -> Iterator[list[Document]]:
    """Divides a list into chuncks.

    Parameters
    ----------
    query_set : QuerySet[Document]
        QuerySet containing Document objects.
    batch_size : int
        size of chunks

    Returns
    -------
    Iterator[list[Document]]
        A chunked Document list.
    """
    total = query_set.count()

    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)
        yield list(query_set[i:end])


def launch_update_process(
    old_project: Project, new_name: str, new_number_docs: int
) -> bool:
    """
    Creates a new project which is the updated version of project.

    Parameters
    ----------
    project : Project
        The project instance containing details about the project.
    new_name: str
        New name for the updated project.
    new_number_docs : int
        The new estimated total number of documents for the
        updated project.

    Returns
    -------
    bool
        True if the process was successfully started, False otherwise.
    """

    today = date.today()

    new_project = Project.objects.create(
        user=old_project.user,
        name=new_name,
        query=old_project.query,
        range_begin_date=old_project.range_begin_date,
        range_end_date=today,
        total_documents=new_number_docs,
        selected_indices=old_project.selected_indices,
    )

    documents = Document.objects.filter(project=old_project)

    pair_document_ids = []
    # Copy documents from the old project to the new project
    for documents_list in divide_in_chunks_query(documents):
        new_documents_obj = []
        for document in documents_list:
            new_documents_obj.append(
                Document(
                    project=new_project,
                    decision_type=document.decision_type,
                    decision_date=document.decision_date,
                    procedure_type=document.procedure_type,
                    descriptors=document.descriptors,
                    standards=document.standards,
                    result=document.result,
                    raw_document_id=document.raw_document_id,
                    raw_document_text=document.raw_document_text,
                    prepared_for_ngrams=document.prepared_for_ngrams,
                    procedure_year=document.procedure_year,
                )
            )

        new_documents = Document.objects.bulk_create(new_documents_obj)

        for new_document, old_document in zip(new_documents, documents_list):
            pair_document_ids.append((old_document.id, new_document.id))

    with transaction.atomic():
        if new_project.is_finish or new_project.is_running:
            return False

        # Pass the selected_indices as an argument to the first task
        task_chain = chain(
            back_get_update_documents.si(
                old_project.id, new_project.id, pair_document_ids
            ),
            back_preparing_documents.si(new_project.id),
            back_preprocess_documents.si(new_project.id),
            back_get_early_results.si(new_project.id),
            back_clustering_documents.si(new_project.id),
            back_plotting_documents.si(new_project.id),
        )

        task_chain.apply_async()
        new_project.is_running = True
        new_project.save()

    logger.info(f"Processing workflow initiated for project {new_project.id}.")

    return True
