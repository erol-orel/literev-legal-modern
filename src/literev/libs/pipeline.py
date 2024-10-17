import logging

from datetime import datetime
from threading import Thread

from literev.libs.collectors import MetaData
from literev.models import Document, Project

thread_dict = dict()


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

    t = thread_dict[project.id]
    if not t.is_alive():
        # if the thread is not alive, recreate thread
        thread_dict[project.id] = Thread(
            target=back_process, args=[project], daemon=True
        )
        thread_dict[project.id].start()

    return


def convert_to_target_type(
    value: str, target_type: type = str
) -> str | int | datetime:
    """
    Convert the given value to the specified target type, handling `None` values appropriately.

    This function ensures data conforms to the expected type in Django model fields,
    especially when dealing with potentially nullable fields in database operations.

    Parameters
    ----------
    value : str
        The value to be converted. Can be a string representation of any type including `None`.
    target_type : type, optional
        The target data type to which the value should be converted. Supports `str`, `int`,
        and `datetime`. Default is `str`.

    Returns
    -------
    str | int | datetime
        The value converted to the target type. If the original value is `None`,
        returns a default value appropriate for the specified `target_type`: an
        empty string for `str`, `0` for `int`, and the current datetime for `datetime`.
    """

    if value is None or value == "":
        if target_type == str:
            return ""
        elif target_type == int:
            return 0
        elif target_type == datetime:
            return datetime.now()
    else:
        if target_type == datetime:
            return datetime.strptime(value, "%Y-%m-%d")
        else:
            return target_type(value)


def create_document_db(project: Project, document: MetaData) -> None:
    """
    Create and save a document object in the database.

    This function takes a project instance and a MetaData instance containing document
    metadata. It transforms the metadata values to ensure they are stored correctly in the
    database, particularly converting None values to empty strings where necessary, and then
    creates a new Document object in the database.

    Parameters
    ----------
    project : Project
        The project instance to which the document belongs.
    document : MetaData
        The MetaData instance containing the document's metadata.

    Returns
    -------
    None

    """

    new_document = Document.objects.create(
        project=project,
        raw_document_id=convert_to_target_type(document.doc_id),
        raw_document_text=convert_to_target_type(document.document_text),
        decision_date=document.decision_date,
        decision_type=convert_to_target_type(document.decision_type),
        procedure_type=convert_to_target_type(document.procedure_type),
        descriptors=convert_to_target_type(document.descriptors),
        standards=convert_to_target_type(document.standards),
        result=convert_to_target_type(document.result),
    )

    return new_document.id


def update_pp_document(pk: int, pp_corpus: str) -> None:
    document = Document.objects.get(pk=pk)
    document.preprocessed_document = pp_corpus
    document.save()


def back_process(project: Project) -> None:
    pass
