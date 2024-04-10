from __future__ import annotations

import datetime
import logging

from dataclasses import dataclass

from django.conf import settings
from elasticsearch import Elasticsearch

from literev.libs.parsing import process_search_query_elasticsearch


@dataclass
class MetaData:
    """
    A data class for storing metadata of a document, with attributes adjusted to French terms.

    This class encapsulates all relevant information needed to process and display documents,
    matching the provided French terms to their corresponding metadata aspects.

    Attributes
    ----------
    doc_id : str
        Unique identifier for the document. Corresponds to "id".
    document_text : str
        The full text of the document. Corresponds to "document_text".
    procedure_type : str
        The type of procedure that the document relates to. Corresponds to "procedure".
    decision_type : str
        The type of decision made in the document. Corresponds to "decision".
    decision_date : str
        The date the decision was made, in ISO format (YYYY-MM-DD). Corresponds to "datedecision" and "dt_decision".
    descriptors : str
        Descriptors or keywords associated with the document. Corresponds to "descripteurs".
    summary : str
        A summary of the document's content. Corresponds to "resume".
    standards : str
        Standards mentioned or applied within the document. Corresponds to "normes".
    result : str
        The outcome or result described in the document. Corresponds to "resultat".
    """

    doc_id: str  # id
    document_text: str  # document_text
    procedure_type: str  # procedure
    decision_type: str  # decision
    decision_date: str  # datedecision, dt_decision
    descriptors: str  # descripteurs
    summary: str  # resume
    standards: str  # normes
    result: str  # resultat


class ElasticSearchCollector:
    """Implements all essential methods for collecting data from elasticsearch sources."""

    es: Elasticsearch
    ES_PAGE_SIZE: int = 1000
    ES_INDEX_NAME: str = "judiciary"

    def __init__(self) -> None:
        self.es = Elasticsearch(
            [settings.ES_HOST_URL],
            basic_auth=(settings.ES_USERNAME, settings.ES_PASSWORD),
        )

    def collect_documents(
        self, search: str, date_begin: datetime.date, date_end: datetime.date
    ) -> list[MetaData]:
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
                logging.warning(
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
        """
        Extract metadata from a source document and creates a `MetaData` instance.

        This function parses a dictionary representing a document and extracts various
        pieces of metadata. If the document contains text, it creates a `MetaData`
        object with the extracted information. Otherwise, it returns `None`.

        Parameters
        ----------
        document : dict[str, str]
            A dictionary containing key-value pairs of document attributes. Keys include
            'id', 'document_text', 'procedure_type', 'decision_type', 'decision_date',
            'descriptors', 'summary', 'standards', and 'result'.

        Returns
        -------
        MetaData | None
            A `MetaData` instance populated with the document's metadata if the document
            contains text; otherwise, `None`.

        """

        doc_id = document.get("id")
        document_text = document.get("document_text", "")
        procedure_type = document.get("procedure_type", "")
        decision_type = document.get("decision_type", "")
        decision_date = document.get("decision_date", "")
        descriptors = document.get("descriptors", "")
        summary = document.get("summary", "")
        standards = document.get("standards", "")
        result = document.get("result", "")

        if document_text:
            metadata = MetaData(
                doc_id=doc_id,
                document_text=document_text,
                procedure_type=procedure_type,
                decision_type=decision_type,
                decision_date=decision_date,
                descriptors=descriptors,
                summary=summary,
                standards=standards,
                result=result,
            )

            return metadata

        return None

    def get_max_documents(
        self, search: str, begin: datetime.date, end: datetime.date
    ) -> int:
        """Counts total number of articles for a given query."""
        es_query = process_search_query_elasticsearch(
            search_query=search,
            start_date=begin,
            end_date=end,
        )

        response = self.es.count(index=self.ES_INDEX_NAME, body=es_query)

        return int(response["count"])

    def create_document_from_metadata(self, metadata: MetaData) -> None:
        """Create document from metadata."""
        pass

    def count_all_corpus(self):
        """Counts total number of articles for a given query."""
        es_query = {"query": {"match_all": {}}}

        response = self.es.count(index=self.ES_INDEX_NAME, body=es_query)

        return int(response["count"])

    def collect_all_documents(self) -> list[MetaData]:
        """Retrieve articles based on the provided search parameters."""

        es_query = {"query": {"match_all": {}}}

        # get all documents from every page response from elasticsearch
        documents = self.get_all_documents_from_es_response(es_query)

        result = []

        for doc in documents:
            metadata = self.extract_document_metadata(doc)

            if metadata:
                result.append(metadata)
            else:
                logging.warning(
                    f"This document does not have document_text field: {doc}"
                )

        return result
