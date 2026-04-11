from __future__ import annotations

import datetime

from django.conf import settings

from lt_contracts import ElasticsearchConnectionConfig
from lt_search import ElasticSearchCollector


def _get_setting_str(name: str) -> str:
    value = getattr(settings, name, "")
    return str(value or "")


def get_connection_config() -> ElasticsearchConnectionConfig:
    return ElasticsearchConnectionConfig(
        host_url=_get_setting_str("ES_HOST_URL"),
        username=_get_setting_str("ES_USERNAME"),
        password=_get_setting_str("ES_PASSWORD"),
        verify_certs=bool(getattr(settings, "ES_SSL_CERTS", False)),
        slices=int(getattr(settings, "ES_SLICES", 1)),
        page_size=int(getattr(settings, "ES_PAGE_SIZE", 1000)),
    )


def build_collector(index_name: str) -> ElasticSearchCollector:
    return ElasticSearchCollector(
        index_name=index_name,
        connection_config=get_connection_config(),
    )


def get_number_documents(
    index_name: str,
    query: str,
    range_begin_date: datetime.date,
    range_end_date: datetime.date,
) -> int:
    return build_collector(index_name).get_max_documents(
        query,
        range_begin_date,
        range_end_date,
    )
