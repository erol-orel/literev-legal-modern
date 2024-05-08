import datetime
import logging

from literev.libs.collectors import ElasticSearchCollector
from literev.models import Project
from literev.tasks import launch_process


def get_number_documents(
    query: str, range_begin_date: datetime.date, range_end_date: datetime.date
) -> int:
    es_collector = ElasticSearchCollector()
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


def process_all_documents():
    total_documents = count_all_corpus()

    project = Project.objects.create(
        name="Process all corpus",
        creation_date=datetime.datetime.now(),
        query="#PROCESS-ALL-CORPUS-LITEREV-00",
        total_documents=total_documents,
    )

    if launch_process(project):
        logging.info("Starting processing the whole corpus")
    else:
        logging.warning("error trying to process the whole corpus")

    return
