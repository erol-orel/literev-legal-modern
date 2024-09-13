from __future__ import annotations

from datetime import datetime

from django.test import TransactionTestCase
from django.test.utils import override_settings

from literev.libs.collectors import ElasticSearchCollector


class ElasticSearchCollectorTestCase(
    TransactionTestCase,
):
    @override_settings(
        ES_HOST_URL="http://mockhost:1234",
        ES_USERNAME="abc",
        ES_PASSWORD="123",
    )
    def test_filter_duplicated_articles_from_es_response(self) -> None:
        pass

    def test_collect_documents(self) -> None:
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)

        search_query = (
            '("juridique du mariage" AND "rejoindre en Suisse") NOT congo'
        )

        articles = ElasticSearchCollector().collect_documents(
            search_query, start_date, end_date
        )  # [0].document_text

        match_pattern = lambda result: (
            "recours" in result
            or (
                "juridique du mariage" in result
                and "rejoindre en Suisse" in result
            )
            and "congo" not in result
        )

        check_results: list[bool] = [
            match_pattern(article.document_text.lower())
            for article in articles
        ]

        assert len(check_results)
        assert all(check_results)
