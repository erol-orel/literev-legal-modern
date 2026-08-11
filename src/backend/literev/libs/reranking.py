"""Optional cross-encoder reranking of the lexical (BM25) candidate set.

Elasticsearch ranks the candidate documents by BM25 (lexical). A cross-encoder
reranker reorders the top-K of that set by *semantic* relevance to the
natural-language query, which is where most retrieval-quality gains come from
(paraphrase / synonymy / conceptual and cross-lingual matches that BM25 misses).

Design goals:
- **Safe to leave wired in.** Disabled unless ``settings.RERANK_ENABLED``; on
  any error (reranker down, timeout, bad response) it returns the input order
  unchanged, so search never breaks because of the reranker.
- **On-prem first.** The default backend is a self-hosted cross-encoder
  exposing a TEI-style ``POST /rerank`` (e.g. ``BAAI/bge-reranker-v2-m3`` via
  HuggingFace Text Embeddings Inference on the VM) — multilingual, keeps the
  privileged decision text on-prem, and costs nothing per query. A managed
  ``cohere`` backend is available for those who prefer it.

Only ``rerank_documents(project, documents)`` is called by the pipeline; the
lower helpers are split out so the HTTP shaping and the reorder logic can be
unit-tested without a database or a live reranker.
"""

from __future__ import annotations

import logging

from typing import Any, Callable, Sequence

import requests

from django.conf import settings

logger = logging.getLogger(__name__)


def _rerank_local(query: str, texts: list[str], timeout: int) -> list[float]:
    """Score ``texts`` against ``query`` via a TEI-style ``/rerank`` service.

    Text Embeddings Inference returns ``[{"index": i, "score": s}, ...]``; we
    map it back to a score-per-input-position list.
    """
    url = str(settings.RERANKER_URL).rstrip("/") + "/rerank"
    response = requests.post(
        url,
        json={"query": query, "texts": texts, "truncate": True},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    scores = [0.0] * len(texts)
    for item in payload:
        idx = int(item["index"])
        if 0 <= idx < len(scores):
            scores[idx] = float(item["score"])
    return scores


def _rerank_cohere(query: str, texts: list[str], timeout: int) -> list[float]:
    """Score ``texts`` against ``query`` via the Cohere Rerank API."""
    response = requests.post(
        "https://api.cohere.com/v2/rerank",
        headers={
            "Authorization": f"Bearer {settings.COHERE_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.RERANKER_MODEL,
            "query": query,
            "documents": texts,
            "top_n": len(texts),
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    scores = [0.0] * len(texts)
    for item in payload.get("results", []):
        idx = int(item["index"])
        if 0 <= idx < len(scores):
            scores[idx] = float(item["relevance_score"])
    return scores


def rerank_scores(query: str, texts: list[str]) -> list[float] | None:
    """Return a relevance score per text, or ``None`` to signal 'keep order'.

    ``None`` is returned when reranking is disabled, the inputs are empty, or
    the backend errors — every caller treats that as "leave the BM25 order
    untouched".
    """
    if not getattr(settings, "RERANK_ENABLED", False):
        return None
    if not query or not query.strip() or not texts:
        return None

    provider = getattr(settings, "RERANKER_PROVIDER", "local")
    timeout = int(getattr(settings, "RERANKER_TIMEOUT_S", 20))
    try:
        if provider == "cohere":
            return _rerank_cohere(query, texts, timeout)
        return _rerank_local(query, texts, timeout)
    except Exception:
        logger.warning(
            "Reranker (%s) failed; keeping the BM25 order.",
            provider,
            exc_info=True,
        )
        return None


def reorder_by_scores(items: Sequence[Any], scores: list[float]) -> list[Any]:
    """Return ``items`` sorted by ``scores`` descending (stable)."""
    order = sorted(range(len(items)), key=lambda i: scores[i], reverse=True)
    return [items[i] for i in order]


def _document_snippet(document: Any) -> str:
    """A compact, cross-encoder-sized representation of a decision."""
    parts = [
        getattr(document, "procedure_type", "") or "",
        getattr(document, "descriptors", "") or "",
        getattr(document, "raw_document_text", "") or "",
    ]
    text = "\n".join(part for part in parts if part).strip()
    max_chars = int(getattr(settings, "RERANK_MAX_CHARS", 2000))
    return text[:max_chars]


def rerank_documents(
    project: Any,
    documents: list[Any],
    text_of: Callable[[Any], str] = _document_snippet,
) -> list[Any]:
    """Reorder ``documents`` (already BM25-sorted) by cross-encoder relevance.

    Only the first ``settings.RERANK_TOP_K`` documents are reranked (a
    cross-encoder over the whole corpus would be needlessly slow); the tail
    keeps its BM25 order and is appended unchanged. Reranks against the
    project's natural-language query — a boolean-only search has no semantic
    intent to rerank against, so it is left as-is. Returns the input list
    unchanged whenever reranking is disabled or fails.
    """
    query = (getattr(project, "natural_language_query", "") or "").strip()
    if not query or len(documents) < 2:
        return documents

    top_k = int(getattr(settings, "RERANK_TOP_K", 50))
    head = documents[:top_k]
    tail = documents[top_k:]

    scores = rerank_scores(query, [text_of(doc) for doc in head])
    if scores is None:
        return documents

    return reorder_by_scores(head, scores) + list(tail)
