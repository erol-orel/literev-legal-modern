from __future__ import annotations

from django.conf import settings

from lr_contracts import (
    ElasticsearchConnectionConfig,
    SearchDocumentMetadata,
)
from lr_search import ElasticSearchCollector as BaseElasticSearchCollector

MetaData = SearchDocumentMetadata


def _get_setting_str(name: str) -> str:
    value = getattr(settings, name, "")
    return str(value or "")


class ElasticSearchCollector(BaseElasticSearchCollector):
    def __init__(self, index_name: str) -> None:
        super().__init__(
            index_name=index_name,
            connection_config=ElasticsearchConnectionConfig(
                host_url=_get_setting_str("ES_HOST_URL"),
                username=_get_setting_str("ES_USERNAME"),
                password=_get_setting_str("ES_PASSWORD"),
                verify_certs=bool(getattr(settings, "ES_SSL_CERTS", False)),
                slices=int(getattr(settings, "ES_SLICES", 1)),
                page_size=int(getattr(settings, "ES_PAGE_SIZE", 1000)),
            ),
        )
