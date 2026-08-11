"""Unit tests for cross-encoder reranking (``libs.reranking``).

Network- and DB-free: the reranker HTTP call is mocked, and documents/projects
are lightweight stand-ins. Covers the reorder logic, the local (TEI) and Cohere
response shapes, and the graceful-fallback behaviour that keeps search working
when reranking is disabled or the backend errors.
"""

from __future__ import annotations

from unittest import mock

from django.test import override_settings

from literev.libs import reranking


class _Doc:
    def __init__(self, pk, text):
        self.id = pk
        self.procedure_type = ""
        self.descriptors = ""
        self.raw_document_text = text


class _Project:
    def __init__(self, nl_query):
        self.natural_language_query = nl_query


def test_reorder_by_scores_sorts_desc() -> None:
    items = ["a", "b", "c"]
    assert reranking.reorder_by_scores(items, [0.1, 0.9, 0.5]) == [
        "b",
        "c",
        "a",
    ]


@override_settings(RERANK_ENABLED=False)
def test_rerank_scores_disabled_returns_none() -> None:
    assert reranking.rerank_scores("q", ["t1", "t2"]) is None


@override_settings(RERANK_ENABLED=True)
def test_rerank_scores_empty_inputs_return_none() -> None:
    assert reranking.rerank_scores("", ["t"]) is None
    assert reranking.rerank_scores("q", []) is None


@override_settings(
    RERANK_ENABLED=True,
    RERANKER_PROVIDER="local",
    RERANKER_URL="http://reranker:80",
    RERANKER_TIMEOUT_S=5,
)
def test_local_rerank_maps_scores_by_index() -> None:
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    # TEI returns out-of-order index/score pairs.
    resp.json.return_value = [
        {"index": 1, "score": 0.8},
        {"index": 0, "score": 0.2},
    ]
    with mock.patch.object(
        reranking.requests, "post", return_value=resp
    ) as post:
        scores = reranking.rerank_scores("q", ["t0", "t1"])
    assert scores == [0.2, 0.8]
    assert post.call_args[0][0] == "http://reranker:80/rerank"


@override_settings(
    RERANK_ENABLED=True,
    RERANKER_PROVIDER="cohere",
    RERANKER_MODEL="rerank-multilingual-v3.0",
    COHERE_API_KEY="secret",
)
def test_cohere_rerank_maps_relevance_scores() -> None:
    resp = mock.Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {
        "results": [
            {"index": 0, "relevance_score": 0.9},
            {"index": 1, "relevance_score": 0.1},
        ]
    }
    with mock.patch.object(reranking.requests, "post", return_value=resp):
        scores = reranking.rerank_scores("q", ["t0", "t1"])
    assert scores == [0.9, 0.1]


@override_settings(RERANK_ENABLED=True, RERANKER_PROVIDER="local")
def test_backend_error_falls_back_to_none() -> None:
    with mock.patch.object(
        reranking.requests, "post", side_effect=RuntimeError("down")
    ):
        assert reranking.rerank_scores("q", ["t0", "t1"]) is None


@override_settings(RERANK_ENABLED=True, RERANK_TOP_K=50)
def test_rerank_documents_reorders_head() -> None:
    docs = [_Doc(1, "alpha"), _Doc(2, "beta"), _Doc(3, "gamma")]
    project = _Project("my question")
    with mock.patch.object(
        reranking, "rerank_scores", return_value=[0.1, 0.5, 0.9]
    ):
        out = reranking.rerank_documents(project, docs)
    assert [d.id for d in out] == [3, 2, 1]


@override_settings(RERANK_ENABLED=True)
def test_rerank_documents_no_query_is_unchanged() -> None:
    docs = [_Doc(1, "a"), _Doc(2, "b")]
    out = reranking.rerank_documents(_Project(""), docs)
    assert [d.id for d in out] == [1, 2]


@override_settings(RERANK_ENABLED=True)
def test_rerank_documents_fallback_keeps_order() -> None:
    docs = [_Doc(1, "a"), _Doc(2, "b")]
    with mock.patch.object(reranking, "rerank_scores", return_value=None):
        out = reranking.rerank_documents(_Project("q"), docs)
    assert [d.id for d in out] == [1, 2]
