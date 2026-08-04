from __future__ import annotations

import logging

from threading import Thread

from literev.libs.collectors import MetaData
from literev.models import Document, Project

thread_dict: dict[int, Thread] = {}


def running_restart(project_id: str) -> None:
    try:
        project = Project.objects.get(is_running=True, id=project_id)
    except Project.DoesNotExist:
        logging.warning(f"the project does no exist, id: {project_id}")
        return

    # check if the research has his own entry
    if project.id not in thread_dict:
        thread_dict[project.id] = Thread(
            target=back_process, args=[project], daemon=True
        )
        thread_dict[project.id].start()
        logging.info(f"Restoring project, id: {project_id}")
        return

    thread = thread_dict[project.id]
    if not thread.is_alive():
        # if the thread is not alive, recreate thread
        thread_dict[project.id] = Thread(
            target=back_process, args=[project], daemon=True
        )
        thread_dict[project.id].start()


def convert_to_target_type(
    value: object | None,
    target_type: type[str] = str,
) -> str:
    """Normalize metadata values before creating a Document row.

    The current pipeline stores the incoming Elasticsearch metadata in text
    fields, so `None` becomes an empty string and everything else is coerced to
    `str`.
    """
    if target_type is not str:
        raise TypeError("convert_to_target_type only supports str targets")
    if value is None:
        return ""
    return str(value)


def create_document_db(project: Project, document: MetaData) -> int:
    """Create and save a document object in the database."""
    new_document = Document.objects.create(
        project=project,
        raw_document_id=convert_to_target_type(document.doc_id),
        chamber=document.chamber,
        raw_document_text=convert_to_target_type(document.document_text),
        document_html_text=document.document_html_text,
        decision_date=document.decision_date,
        decision_type=convert_to_target_type(document.decision_type),
        procedure_type=convert_to_target_type(document.procedure_type),
        descriptors=convert_to_target_type(document.descriptors),
        standards=convert_to_target_type(document.standards),
        result=convert_to_target_type(document.result),
        record_key=document.record_key,
        language=convert_to_target_type(document.language),
    )

    return new_document.id


def update_pp_document(pk: int, pp_corpus: str) -> None:
    document = Document.objects.get(pk=pk)
    document.preprocessed_document = pp_corpus
    document.save()


def back_process(project: Project) -> None:
    pass
