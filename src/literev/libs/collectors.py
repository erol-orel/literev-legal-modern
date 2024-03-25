from __future__ import annotations
import datetime
from elasticsearch import Elasticsearch
from django.conf import settings
from literev.libs.parsing import process_search_query_elasticsearch
from dataclasses import dataclass
from typing import cast


@dataclass
class MetaData:
    doc_id: str
    summary: str
    document_text: str
    decision_date: datetime.date
    result: str

class ElasticSearchCollector():
    """Implements all essential methods for collecting data from elasticsearch sources."""

    es: Elasticsearch
    ES_PAGE_SIZE: int = 1000
    ES_INDEX_NAME: str = "judiciary"

    def __init__(self) -> None:
        self.es = Elasticsearch(
            [settings.ES_HOSTNAME],
            basic_auth=(settings.ES_USERNAME, settings.ES_PASSWORD),
        )


    def collect_documents(self, search: str, date_begin: datetime.date, date_end: datetime.date) -> list[MetaData]:
        """Retrieve articles based on the provided search parameters."""

        es_query = process_search_query_elasticsearch(
            search_query=search,
            start_date=date_begin,
            end_date=date_end,
        )

        # get all documents from every page response from elasticsearch
        documents = self.get_all_documents_from_es_response(es_query)

        result = []

        for doc in documents:
            metadata = self.extract_document_metadata(doc)

            if metadata:
                result.append(metadata)
            else:
                self.log(
                    f"This document does not have document_text field: {doc}"
                )

        return result

    def get_all_documents_from_es_response(
        self,
        es_query: dict[str, int | list[str] | dict[str, str]],
    ) -> list[dict[str, str]]:
        """Get all articles from elasticsearch response."""

        es_query["size"] = self.ES_PAGE_SIZE

        response = self.es.search(
            index=self.ES_INDEX_NAME, body=es_query, scroll="2m"
        )

        scroll_id = response["_scroll_id"]
        hits = response["hits"]["hits"]

        documents = []

        # process the first page from elasticsearch
        documents += self._process_documents_from_es_response_page(hits)

        # then we process the rest of the pages if they exist
        # by passing the scroll_id to es.scroll
        while hits:
            response = self.es.scroll(scroll_id=scroll_id, scroll="2m")
            hits = response["hits"]["hits"]
            documents += self._process_documents_from_es_response_page(hits)

        return documents

    def _process_documents_from_es_response_page(
        self, hits: list[dict[str, dict[str, str]]]
    ) -> list[dict[str, str]]:
        """Process all articles from elasticsearch response page."""
        documents = []
        for es_hit in hits:
            # get article from elasticsearch hit _source key
            article = es_hit["_source"]
            if article:
                documents.append(article)
        return documents

    def extract_document_metadata(
        self, document: dict[str, str]
    ) -> MetaData | None:
        """Create Metadata from source article."""

        doc_id = document.get("id")
        summary = document.get("summary", "")
        document_text = document.get("document_text")
        date_decision = document.get("date_decision")
        result = document.get("result", "")
       
        if document_text:
            metadata = MetaData(
                doc_id=doc_id,
                summary=summary,
                document_text=document_text,
                decision_date=cast(datetime.date, date_decision),
                result=result,
            )

            return metadata

        return None

    def get_max_articles(
        self, search: str, begin: datetime.date, end: datetime.date
    ) -> int:
        """Counts total number of articles for a given query."""
        es_query = process_search_query_elasticsearch(
            search_query=search,
            start_date=begin,
            end_date=end,
        )

        response = self.es.count(
            index=self.ES_INDEX_NAME,
            body=es_query
            )
        
        return int(response["count"])

    def create_document_from_metadata(self, metadata: MetaData) -> None:
        """Create document from metadata."""
        pass
    