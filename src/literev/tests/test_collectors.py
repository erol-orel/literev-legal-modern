import unittest

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

    def test_collect_administrative_court_documents(self) -> None:
        start_date = datetime(2000, 1, 1)
        end_date = datetime(2024, 12, 31)

        search_query = (
            '("juridique du mariage" AND "rejoindre en Suisse") NOT congo'
        )

        # TODO: Update index name to "administrative_court"
        collector = ElasticSearchCollector(index_name="judiciary")

        documents = collector.collect_documents(
            search_query, start_date, end_date
        )

        match_pattern = lambda result: (
            "recours" in result
            or (
                "juridique du mariage" in result
                and "rejoindre en Suisse" in result
            )
            and "congo" not in result
        )

        check_results: list[bool] = [
            match_pattern(document.document_text.lower())
            for document in documents
        ]

        assert len(check_results) > 0
        assert all(check_results)

    @unittest.skip("Skipping test for penal court documents.")
    def test_collect_penal_court_documents(self) -> None:
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2024, 12, 31)

        search_query = "amour"

        collector = ElasticSearchCollector(index_name="penal_court")

        documents = collector.collect_documents(
            search_query, start_date, end_date
        )

        assert len(documents) == 3

    @unittest.skip("Skipping test for civil court documents.")
    def test_collect_civil_court_documents(self) -> None:
        start_date = datetime(2023, 1, 1)
        end_date = datetime(2023, 8, 31)

        search_query = "divorce"

        collector = ElasticSearchCollector(index_name="civil_court")

        documents = collector.collect_documents(
            search_query, start_date, end_date
        )
        # breakpoint()
        assert len(documents) == 158
