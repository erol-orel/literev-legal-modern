import datetime

from literev.libs.collectors import ElasticSearchCollector


def get_number_documents(
    query: str, range_begin_date: datetime.date, range_end_date: datetime.date
) -> int:
    es_collector = ElasticSearchCollector()

    try:
        result = es_collector.get_max_documents(
            query, range_begin_date, range_end_date
        )
    except Exception as e:
        print(e)
        result = 0

    return result
