"""Unit tests for parallel faithfulness scoring (``compute_faithfulness_scores``).

Network/DB-free: the LLM scorer and the on-disk faithfulness cache are mocked,
so the tests assert only on the scoring/cache logic and that cached results
skip the LLM entirely.
"""

from __future__ import annotations

from unittest import mock

from literev.libs import rag_pdf


class _FakeRagDoc:
    """Minimal stand-in for a ProjectDocumentRAG row (no DB)."""

    def __init__(
        self, pk: int, document_id: int, answer: str, citation_context: list
    ) -> None:
        self.pk = pk
        self.document_id = document_id
        self.answer = answer
        self.citation_context = citation_context


async def _fake_score(query: str, answer: str, citation: list) -> float:
    return {"a": 0.5, "b": 0.9}[answer]


def test_parallel_cache_miss_computes_and_caches() -> None:
    docs = [
        _FakeRagDoc(1, 10, "a", ["ctx-a"]),
        _FakeRagDoc(2, 20, "b", ["ctx-b"]),
    ]
    saved: dict = {}
    with (
        mock.patch.object(rag_pdf, "get_faithfulness_score", new=_fake_score),
        mock.patch.object(rag_pdf.FAITH_CACHE, "load", return_value=None),
        mock.patch.object(
            rag_pdf.FAITH_CACHE,
            "save",
            side_effect=lambda key, value: saved.__setitem__(key, value),
        ),
    ):
        result = rag_pdf.compute_faithfulness_scores("q", docs)

    assert result == {1: 0.5, 2: 0.9}
    # Both misses were written back to the cache.
    assert len(saved) == 2


def test_cache_hit_skips_the_llm() -> None:
    docs = [_FakeRagDoc(3, 30, "a", ["ctx"])]
    called = False

    async def _should_not_run(*args: object, **kwargs: object) -> float:
        nonlocal called
        called = True
        return 0.0

    with (
        mock.patch.object(
            rag_pdf, "get_faithfulness_score", new=_should_not_run
        ),
        mock.patch.object(
            rag_pdf.FAITH_CACHE, "load", return_value={"score": 0.7}
        ),
        mock.patch.object(rag_pdf.FAITH_CACHE, "save") as save,
    ):
        result = rag_pdf.compute_faithfulness_scores("q", docs)

    assert result == {3: 0.7}
    assert called is False
    save.assert_not_called()


def test_empty_input_is_noop() -> None:
    assert rag_pdf.compute_faithfulness_scores("q", []) == {}
