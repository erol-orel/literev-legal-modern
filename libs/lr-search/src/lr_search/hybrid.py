"""Elasticsearch hybrid retrieval: BM25 + dense kNN, fused with native RRF.

Framework-free, side-effect-free builders for the Elasticsearch 8.x
``retriever``/``rrf`` API. They turn a lexical query (the BM25 body produced by
``lr_query.process_search_query_elasticsearch``) and a query vector into a
single search body that fuses lexical and dense retrieval in one round trip —
the foundation for retiring the separate Chroma vector store and querying one
store for both signals.

Everything here is a pure dict transform, so the query shape, quantization, and
fusion parameters are unit-tested without a live cluster. The application layer
(``literev.libs``) supplies the ``Elasticsearch`` client, the section index
name, and the query vector (embedded via Hactar), then POSTs the body these
functions return.

Requires Elasticsearch >= 8.12 (``int8_hnsw`` quantization, the ``rrf``
retriever), which matches the project's ``elasticsearch >=8.12.1,<9.0.0`` pin.
"""

from __future__ import annotations

from typing import Any

# The single section-vector field the dense signal lives on. Kept as a module
# constant so the mapping and the query cannot drift apart.
DEFAULT_VECTOR_FIELD = "section_vector"

# RRF's rank constant. 60 is the value from the original RRF paper and the
# Elasticsearch default; a smaller constant weights the very top ranks more
# heavily. We keep the ES default so behaviour is predictable and documented.
DEFAULT_RANK_CONSTANT = 60


def dense_vector_field(
    dims: int,
    *,
    similarity: str = "cosine",
    index_type: str = "int8_hnsw",
) -> dict[str, Any]:
    """Mapping fragment for the section-vector field.

    ``int8_hnsw`` quantizes each dimension to a byte, cutting the on-disk vector
    footprint ~4x for a negligible recall cost — the reason vectors can live in
    Elasticsearch instead of a dedicated store. Pass ``index_type="bbq_hnsw"``
    on ES >= 8.16 for even denser storage, or ``"hnsw"`` for full precision.
    """
    if dims <= 0:
        raise ValueError("dims must be a positive integer")
    return {
        "type": "dense_vector",
        "dims": dims,
        "index": True,
        "similarity": similarity,
        "index_options": {"type": index_type},
    }


def section_index_mapping(
    dims: int,
    *,
    vector_field: str = DEFAULT_VECTOR_FIELD,
    index_type: str = "int8_hnsw",
) -> dict[str, Any]:
    """Full ``mappings`` for a section index that carries BM25 text *and* the
    dense vector on the same document — one store for both retrieval signals.

    The fields mirror what the section RAG pipeline needs: the decision it came
    from (``record_key``), the ``source`` index it belongs to, the ``section``
    label (Majeure / Mineure-Faits / Mineure-Subsomption / Conclusion), the
    ``text`` that is BM25-searchable, the ``decision_date`` for range filters,
    and the quantized ``section_vector``.
    """
    return {
        "mappings": {
            "properties": {
                "record_key": {"type": "keyword"},
                "source": {"type": "keyword"},
                "section": {"type": "keyword"},
                "text": {"type": "text"},
                "decision_date": {"type": "date"},
                vector_field: dense_vector_field(dims, index_type=index_type),
            }
        }
    }


def _with_filters(
    query: dict[str, Any], filters: list[dict[str, Any]] | None
) -> dict[str, Any]:
    """Constrain a lexical query with ``filters`` (source, section, date …).

    ``filter`` clauses do not affect scoring, so the BM25 ranking is preserved;
    they only restrict which documents are eligible.
    """
    if not filters:
        return query
    return {"bool": {"must": [query], "filter": list(filters)}}


def standard_retriever(
    lexical_query: dict[str, Any],
    *,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Wrap a BM25 query body as a ``standard`` retriever (the lexical leg)."""
    return {"standard": {"query": _with_filters(lexical_query, filters)}}


def knn_retriever(
    query_vector: list[float],
    *,
    field: str = DEFAULT_VECTOR_FIELD,
    k: int,
    num_candidates: int,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The dense ``knn`` retriever leg.

    ``k`` is how many neighbours to return; ``num_candidates`` is how many the
    HNSW graph explores per shard before keeping the top ``k`` (higher =
    better recall, more work). Filters restrict the candidate set to the same
    documents the lexical leg is allowed to see.
    """
    if not query_vector:
        raise ValueError("query_vector must be non-empty")
    knn: dict[str, Any] = {
        "field": field,
        "query_vector": list(query_vector),
        "k": k,
        "num_candidates": num_candidates,
    }
    if filters:
        knn["filter"] = list(filters)
    return {"knn": knn}


def build_hybrid_search_body(
    lexical_query: dict[str, Any],
    query_vector: list[float],
    *,
    vector_field: str = DEFAULT_VECTOR_FIELD,
    size: int = 50,
    k: int | None = None,
    num_candidates: int | None = None,
    rank_window_size: int | None = None,
    rank_constant: int = DEFAULT_RANK_CONSTANT,
    filters: list[dict[str, Any]] | None = None,
    source_fields: list[str] | None = None,
) -> dict[str, Any]:
    """Build the full ES search body fusing BM25 and dense kNN with RRF.

    Reciprocal Rank Fusion ranks each document by ``sum(1 / (rank_constant +
    rank_i))`` across the two result lists, so a document ranked highly by
    *either* leg surfaces — lexical recall for exact terms and legal citations,
    dense recall for paraphrase and cross-lingual matches — without having to
    tune a score-scale weighting between two incomparable scoring systems. That
    robustness is why RRF is the default fusion here.

    ``k``/``num_candidates``/``rank_window_size`` default off ``size``; override
    them to trade recall for latency. ``filters`` constrain both legs to the
    same eligible set (e.g. selected sources, a decision-date range).
    """
    if size <= 0:
        raise ValueError("size must be a positive integer")
    resolved_k = k if k is not None else size
    resolved_candidates = (
        num_candidates if num_candidates is not None else max(size * 4, 100)
    )
    resolved_window = (
        rank_window_size if rank_window_size is not None else size
    )

    body: dict[str, Any] = {
        "size": size,
        "retriever": {
            "rrf": {
                "retrievers": [
                    standard_retriever(lexical_query, filters=filters),
                    knn_retriever(
                        query_vector,
                        field=vector_field,
                        k=resolved_k,
                        num_candidates=resolved_candidates,
                        filters=filters,
                    ),
                ],
                "rank_window_size": resolved_window,
                "rank_constant": rank_constant,
            }
        },
    }
    if source_fields is not None:
        body["_source"] = source_fields
    return body
