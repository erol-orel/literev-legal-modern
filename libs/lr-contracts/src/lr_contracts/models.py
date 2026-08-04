from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, NamedTuple, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class QueryDateRange:
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class SearchQuerySpec:
    query: str
    date_range: QueryDateRange | None = None
    search_fields: tuple[str, ...] = ("document_text",)


@dataclass(frozen=True, slots=True)
class ElasticsearchConnectionConfig:
    host_url: str
    username: str = ""
    password: str = ""
    verify_certs: bool = False
    slices: int = 1
    page_size: int = 1000


@dataclass(frozen=True, slots=True)
class SearchDocumentMetadata:
    doc_id: str
    chamber: str
    document_text: str
    document_html_text: str
    procedure_type: str
    decision_type: str
    decision_date: str | None
    descriptors: str
    summary: str
    standards: str
    result: str
    es_score: float
    record_key: str
    language: str = ""


class ClusteringRunResult(NamedTuple):
    embedding_2d_array: Any
    clusterer: Any
    tf_idf: Any
    columns_name: Any
    best_score: float
    number_neighbour: int


@dataclass(frozen=True, slots=True)
class ClusterPosition:
    document_id: int
    pos_x: float
    pos_y: float


@dataclass(frozen=True, slots=True)
class TopicScore:
    topic: str
    hdbscan_score: float


@runtime_checkable
class SearchClientProtocol(Protocol):
    def search(self, *args: Any, **kwargs: Any) -> Any: ...
    def count(self, *args: Any, **kwargs: Any) -> Any: ...
    def scroll(self, *args: Any, **kwargs: Any) -> Any: ...
    def clear_scroll(self, *args: Any, **kwargs: Any) -> Any: ...
