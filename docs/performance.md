# Performance & cost

Perceived speed drives adoption for busy practitioners. This note covers the
levers, what's shipped, and what's queued.

## Response caching (shipped, opt-in)

A decision's full content is expensive to fetch and render and **never
changes** — an ideal cache target. A dedicated `documents` cache alias
(`settings.CACHES`) backs the document-content endpoints via
`libs.response_cache`.

- **Default off.** With `RESPONSE_CACHE_ENABLED` unset the alias is a
  `DummyCache` (a no-op), so behaviour is identical to no caching. Turn it on
  in the VM `.env`:

  ```
  RESPONSE_CACHE_ENABLED=true
  RESPONSE_CACHE_TTL=300        # seconds
  ```

  It reuses the app's existing Redis (`REDIS_URL`) — nothing new to run.
- **Safe by construction.** Keys are **per-user** (`make_key`), so serving from
  cache never bypasses the payload builders' own access checks, and `None`
  (404 / no-access) is never cached, so access is always re-evaluated.
- **What it covers today:** `DocumentContentAPIView` and
  `HighlightedDocumentContentAPIView` — the heaviest read path (full decision
  HTML/highlighted text). Bump `_KEY_VERSION` in `response_cache.py` to
  invalidate after a content-format change.

## Streaming answers (queued)

The RAG summary and per-decision answers are produced by the LLM and returned
in one shot. **Streaming** them token-by-token (SSE from the answer view, or a
Channels/ASGI endpoint) makes the wait *feel* far shorter even when total time
is unchanged — the single biggest perceived-speed win for the RAG flow. It's an
ASGI/transport change, so it lands as its own project rather than a flag.

## Take RAG embedding off the ingestion critical path (queued)

Section embedding during ingest slows the import and couples two concerns.
Moving embedding to an async Celery task after the document is indexed lets
search/cluster availability lead, with RAG answers becoming available as the
embeddings complete — the same graceful-degradation contract the federal
sources already use. Pairs with the eval harness
([rag-evaluation.md](rag-evaluation.md)) to confirm no answer-quality
regression when the pipeline is reordered.

## Already on `main`

Route-level code-splitting and the leaner id-only queries + `TableChoice`
index (perf batch) are already merged; this note is about the *next* tier.
Measure retrieval latency with `scripts/bench_retrieval.py` and answer quality
with `scripts/eval_rag.py` before and after any change here.
