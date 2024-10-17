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
    es_score: float  # elastic search score given by _score field


class ElasticSearchCollector:
    """Implements all essential methods for collecting data from Elasticsearch sources."""

    es: Elasticsearch
    ES_PAGE_SIZE: int = 1000
    index_name: str = ""

    def __init__(self, index_name: str) -> None:
        """
        Initializes the ElasticSearchCollector with the specified index name.

        Parameters
        ----------
        index_name : str
            The name of the Elasticsearch index to be used for collecting data.
        """
        self.index_name = index_name
        self.es = Elasticsearch(
            [settings.ES_HOST_URL],
            basic_auth=(settings.ES_USERNAME, settings.ES_PASSWORD),
            verify_certs=settings.ES_SSL_CERTS,
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
            index=self.index_name, body=es_query, scroll="2m"
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
            es_score = es_hit.get("_score", 0)
            article = es_hit["_source"]
            if article:
                article["es_score"] = es_score
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
        es_score = document.get("es_score", 0)

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
                es_score=es_score,
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

        response = self.es.count(index=self.index_name, body=es_query)

        return int(response["count"])

    def create_document_from_metadata(self, metadata: MetaData) -> None:
        """Create document from metadata."""
        pass

    # Collecting and counting documents in PROCESS-ALL-CORPUS
    def collect_all_documents(self) -> list[MetaData]:
        """
        Retrieve all articles from the Elasticsearch index based on the 'match_all' query.

        Returns
        -------
        list[MetaData]
            A list of metadata for the retrieved documents.
        """
        es_query = {"query": {"match_all": {}}}
        try:
            documents = self.get_all_documents_from_es_response(es_query)
            result = [
                metadata
                for doc in documents
                if (metadata := self.extract_document_metadata(doc))
            ]
            if not result:
                logging.warning(
                    "No valid documents found with 'document_text' field."
                )
            logging.info(f"Total documents collected: {len(result)}")
            return result
        except Exception as e:
            logging.error(f"Error while collecting documents: {e}")
            return []

    def count_all_documents(self) -> int:
        """
        Count the total number of documents in the specified Elasticsearch index.

        Returns
        -------
        int
            The total number of documents in the index.
        """
        try:
            total_count_response = self.es.count(index=self.index_name)
            count = total_count_response.get("count", 0)
            logging.info(
                f"Total documents in index '{self.index_name}': {count}"
            )
            return count
        except Exception as e:
            logging.error(
                f"Error counting documents in index '{self.index_name}': {e}"
            )
            return 0
