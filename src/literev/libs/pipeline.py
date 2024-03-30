from threading import Thread

from literev.libs.collectors import ElasticSearchCollector, MetaData
from literev.models import Document, Project
from literev_core.preprocessing import preprocessing_mp

thread_dict = dict()


def create_document_db(project: Project, document: MetaData) -> None:
    Document.objects.create(
        project=project,
        raw_document_id=document.doc_id,
        raw_document_text=document.document_text,
        # TODO: add procedure year, procedure year exists?
        decision_date=document.decision_date,
    )


def back_get_documents(project: Project) -> bool:
    es_collector = ElasticSearchCollector()

    try:
        documents_list = es_collector.collect_documents(
            project.query, project.range_begin_date, project.range_end_date
        )

    except Exception as e:
        print("ElasticSearchCollector Failed")
        print(e)
        return False

    for document in documents_list:
        try:
            create_document_db(project, document)

        except Exception as e:
            print("Document creation failed", document.doc_id)
            print(e)

    return True


def update_pp_document(pk: int, pp_corpus: str) -> None:
    document = Document.objects.get(pk=pk)
    document.preprocessed_document = pp_corpus
    document.save()


def back_preprocess_documents(project: Project) -> None:
    documents = Document.objects.filter(project=project)
    document_pk_list = [document.pk for document in documents]
    document_corpus_list = [
        document.raw_document_text for document in documents
    ]

    try:
        # using preprocessing_mpo from literev_core
        preprocessed_corpus_list = preprocessing_mp(document_corpus_list)

    except Exception as e:
        print("literev_core failed in preprocessing_mp")
        print(e)
        return

    for pk, pp_corpus in zip(document_pk_list, preprocessed_corpus_list):
        try:
            update_pp_document(pk, pp_corpus)
        except Exception as e:
            print(e)
            print("Adding preprocessed document failed. Doc id:", id)


def back_process(project: Project) -> None:
    if project.step == "get_documents":
        project.is_running = True
        project.save()

        if back_get_documents(project):
            project.step = "preprocess"
            project.save()

    if project.step == "preprocess":
        back_preprocess_documents(project)
        project.step = "clustering"
        project.save()

    # TODO: implement clustering
    # if project.step == "clustering":
    #     back_clustering_documents(project)
    #     project.step = ""
    #     project.is_finish = True
    #     project.is_running = False
    #     project.save()


def launch_process(project: Project) -> bool:
    if project.is_finish:
        return False

    # check if the research is currently running
    if project.is_running:
        return False

    project_id = project.id

    thread_dict[project_id] = Thread(
        target=back_process, args=[project], daemon=True
    )

    thread_dict[project_id].start()

    return True
