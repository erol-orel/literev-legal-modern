"""Unit tests for the Elasticsearch hybrid (BM25 + dense kNN, RRF) builders.

Pure dict transforms — no cluster, no client. They pin the exact query shape
the application will POST so a change to the fusion contract is a visible diff.
"""

from __future__ import annotations

import pytest

from lr_search import (
    build_hybrid_search_body,
    dense_vector_field,
    knn_retriever,
    section_index_mapping,
    standard_retriever,
)
from lr_search.hybrid import DEFAULT_RANK_CONSTANT, DEFAULT_VECTOR_FIELD

LEXICAL = {"match": {"text": "résiliation bail"}}
VECTOR = [0.1, 0.2, 0.3]


class TestDenseVectorField:
    def test_quantized_by_default(self) -> None:
        field = dense_vector_field(1024)
        assert field["type"] == "dense_vector"
        assert field["dims"] == 1024
        assert field["index"] is True
        assert field["similarity"] == "cosine"
        assert field["index_options"] == {"type": "int8_hnsw"}

    def test_index_type_is_overridable(self) -> None:
        assert dense_vector_field(1024, index_type="bbq_hnsw")[
            "index_options"
        ] == {"type": "bbq_hnsw"}

    def test_rejects_non_positive_dims(self) -> None:
        with pytest.raises(ValueError):
            dense_vector_field(0)


class TestSectionIndexMapping:
    def test_carries_text_and_vector_on_one_document(self) -> None:
        props = section_index_mapping(1024)["mappings"]["properties"]
        # BM25 text and the dense vector live on the same document — one store.
        assert props["text"] == {"type": "text"}
        assert props[DEFAULT_VECTOR_FIELD]["type"] == "dense_vector"
        assert props["record_key"] == {"type": "keyword"}
        assert props["source"] == {"type": "keyword"}
        assert props["section"] == {"type": "keyword"}
        assert props["decision_date"] == {"type": "date"}

    def test_vector_dims_flow_through(self) -> None:
        props = section_index_mapping(768)["mappings"]["properties"]
        assert props[DEFAULT_VECTOR_FIELD]["dims"] == 768


class TestRetrieverLegs:
    def test_standard_wraps_the_lexical_query(self) -> None:
        assert standard_retriever(LEXICAL) == {"standard": {"query": LEXICAL}}

    def test_standard_applies_filters_without_touching_score(self) -> None:
        filters = [{"term": {"source": "chambre_civile"}}]
        wrapped = standard_retriever(LEXICAL, filters=filters)["standard"][
            "query"
        ]
        assert wrapped == {"bool": {"must": [LEXICAL], "filter": filters}}

    def test_knn_leg_shape(self) -> None:
        leg = knn_retriever(VECTOR, k=10, num_candidates=100)["knn"]
        assert leg["field"] == DEFAULT_VECTOR_FIELD
        assert leg["query_vector"] == VECTOR
        assert leg["k"] == 10
        assert leg["num_candidates"] == 100
        assert "filter" not in leg

    def test_knn_leg_filter_matches_lexical_filter(self) -> None:
        filters = [{"term": {"source": "chambre_civile"}}]
        leg = knn_retriever(VECTOR, k=10, num_candidates=100, filters=filters)[
            "knn"
        ]
        assert leg["filter"] == filters

    def test_knn_rejects_empty_vector(self) -> None:
        with pytest.raises(ValueError):
            knn_retriever([], k=10, num_candidates=100)


class TestBuildHybridSearchBody:
    def test_fuses_both_legs_with_rrf(self) -> None:
        body = build_hybrid_search_body(LEXICAL, VECTOR, size=25)
        rrf = body["retriever"]["rrf"]
        legs = rrf["retrievers"]
        assert "standard" in legs[0] and "knn" in legs[1]
        assert body["size"] == 25
        assert rrf["rank_constant"] == DEFAULT_RANK_CONSTANT

    def test_defaults_derive_from_size(self) -> None:
        body = build_hybrid_search_body(LEXICAL, VECTOR, size=10)
        knn = body["retriever"]["rrf"]["retrievers"][1]["knn"]
        assert knn["k"] == 10  # k defaults to size
        assert knn["num_candidates"] == 100  # max(size*4, 100)
        assert body["retriever"]["rrf"]["rank_window_size"] == 10

    def test_overrides_are_honoured(self) -> None:
        body = build_hybrid_search_body(
            LEXICAL,
            VECTOR,
            size=5,
            k=7,
            num_candidates=200,
            rank_window_size=50,
            rank_constant=20,
        )
        rrf = body["retriever"]["rrf"]
        knn = rrf["retrievers"][1]["knn"]
        assert knn["k"] == 7
        assert knn["num_candidates"] == 200
        assert rrf["rank_window_size"] == 50
        assert rrf["rank_constant"] == 20

    def test_filters_constrain_both_legs_identically(self) -> None:
        filters = [
            {"terms": {"source": ["chambre_civile", "bundesgericht"]}},
            {"range": {"decision_date": {"gte": "2020-01-01"}}},
        ]
        body = build_hybrid_search_body(LEXICAL, VECTOR, filters=filters)
        legs = body["retriever"]["rrf"]["retrievers"]
        lexical_filter = legs[0]["standard"]["query"]["bool"]["filter"]
        knn_filter = legs[1]["knn"]["filter"]
        assert lexical_filter == filters == knn_filter

    def test_source_fields_projected_when_given(self) -> None:
        body = build_hybrid_search_body(
            LEXICAL, VECTOR, source_fields=["record_key", "section", "text"]
        )
        assert body["_source"] == ["record_key", "section", "text"]

    def test_no_source_key_when_not_requested(self) -> None:
        assert "_source" not in build_hybrid_search_body(LEXICAL, VECTOR)

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValueError):
            build_hybrid_search_body(LEXICAL, VECTOR, size=0)
