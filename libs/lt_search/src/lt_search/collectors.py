from __future__ import annotations

import datetime
import logging

from typing import Any

from elasticsearch import Elasticsearch

from lt_contracts import (
    ElasticsearchConnectionConfig,
    SearchClientProtocol,
    SearchDocumentMetadata,
)
from lt_query import process_search_query_elasticsearch

MetaData = SearchDocumentMetadata


class ElasticSearchCollector:
    es: SearchClientProtocol
    connection_config: ElasticsearchConnectionConfig
    index_name: str = ""

    def __init__(
        self,
        index_name: str,
        connection_config: ElasticsearchConnectionConfig,
        client: SearchClientProtocol | None = None,
    ) -> None:
        self.index_name = index_name
        self.connection_config = connection_config
        self.es = client or Elasticsearch(
            [self.connection_config.host_url],
            basic_auth=(
                self.connection_config.username,
                self.connection_config.password,
            ),
            verify_certs=self.connection_config.verify_certs,
        )

    def collect_documents(
        self,
        search: str,
        date_begin: datetime.date,
        date_end: datetime.date,
    ) -> list[MetaData]:
        es_query: dict[str, Any] = process_search_query_elasticsearch(
            search_query=search,
            start_date=date_begin,
            end_date=date_end,
        )
        documents = self.get_all_documents_from_es_response(es_query)
        result: list[MetaData] = []
        for doc in documents:
            metadata = self.extract_document_metadata(doc)
            if metadata:
                result.append(metadata)
            else:
                logging.warning(
                    "Document without document_text skipped: %s", doc
                )
        return result

    def get_all_documents_from_es_response(
        self,
        es_query: dict[str, Any],
    ) -> list[dict[str, Any]]:
        keepalive = "15m"
        page_size = int(es_query.get("size", self.connection_config.page_size))
        query = es_query.get("query", {"match_all": {}})
        source_fields = es_query.get(
            "_source",
            [
                "id",
                "collector_name",
                "document_text",
                "procedure_type",
                "decision_type",
                "decision_date",
                "descriptors",
                "summary",
                "standards",
                "result",
                "record_key",
                "document",
            ],
        )
        base_body = {
            "query": query,
            "size": page_size,
            "sort": ["_doc"],
            "_source": source_fields,
            "track_scores": True,
        }
        results: list[dict[str, Any]] = []
        num_slices = (
            self.connection_config.slices
            if self.connection_config.slices > 1
            else 1
        )
        for slice_id in range(num_slices):
            body = dict(base_body)
            if num_slices > 1:
                body["slice"] = {"id": slice_id, "max": num_slices}
            response = self.es.search(
                index=self.index_name,
                body=body,
                scroll=keepalive,
                request_timeout=600,
            )
            scroll_id = response.get("_scroll_id")
            hits = response.get("hits", {}).get("hits", [])
            results.extend(self._process_documents_from_es_response_page(hits))
            try:
                while hits:
                    response = self.es.scroll(
                        scroll_id=scroll_id,
                        scroll=keepalive,
                        request_timeout=600,
                    )
                    scroll_id = response.get("_scroll_id", scroll_id)
                    hits = response.get("hits", {}).get("hits", [])
                    results.extend(
                        self._process_documents_from_es_response_page(hits)
                    )
            finally:
                if scroll_id:
                    try:
                        self.es.clear_scroll(scroll_id=scroll_id)
                    except Exception:
                        pass
        return results

    def _process_documents_from_es_response_page(
        self,
        hits: list[dict[str, dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for es_hit in hits:
            es_score = es_hit.get("_score") or 0
            document = es_hit.get("_source", {}) or {}
            if document:
                document.setdefault("id", es_hit.get("_id"))
                document["es_score"] = es_score
                documents.append(document)
        return documents

    def extract_document_metadata(
        self,
        document: dict[str, Any],
    ) -> MetaData | None:
        document_text = document.get("document_text", "")
        if not document_text:
            return None
        return MetaData(
            doc_id=str(document.get("id", "")),
            chamber=str(document.get("collector_name", "")),
            document_text=str(document_text),
            document_html_text=str(document.get("document", "")),
            procedure_type=str(document.get("procedure_type", "")),
            decision_type=str(document.get("decision_type", "")),
            decision_date=document.get("decision_date"),
            descriptors=str(document.get("descriptors", "")),
            summary=str(document.get("summary", "")),
            standards=str(document.get("standards", "")),
            result=str(document.get("result", "")),
            es_score=float(document.get("es_score", 0) or 0),
            record_key=str(document.get("record_key", "no record key")),
        )

    def get_max_documents(
        self,
        search: str,
        begin: datetime.date,
        end: datetime.date,
    ) -> int:
        es_query: dict[str, Any] = process_search_query_elasticsearch(
            search_query=search,
            start_date=begin,
            end_date=end,
        )
        response = self.es.count(index=self.index_name, body=es_query)
        return int(response["count"])

    def collect_all_documents(self) -> list[MetaData]:
        es_query: dict[str, Any] = {"query": {"match_all": {}}}
        documents = self.get_all_documents_from_es_response(es_query)
        return [
            metadata
            for doc in documents
            if (metadata := self.extract_document_metadata(doc))
        ]

    def count_all_documents(self) -> int:
        response = self.es.count(index=self.index_name)
        return int(response.get("count", 0))
