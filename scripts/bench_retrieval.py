#!/usr/bin/env python3
"""Benchmark retrieval latency and recall on the live Elasticsearch index.

Standalone by design: it speaks to Elasticsearch directly (no Django, no app
imports) so it can be run on the VM against the real corpus to produce the
concrete numbers behind ``docs/hybrid-retrieval.md``.

It reports, per query and in aggregate:
  * latency percentiles (p50 / p90 / p99) of the search call, and
  * recall@k against a labelled relevant set, when the query file provides one.

Two retrieval modes:
  * ``bm25``   — lexical ``simple_query_string`` over the text fields (works
                 today).
  * ``hybrid`` — ES 8.x native ``rrf`` retriever fusing the BM25 branch with a
                 ``knn`` branch over a ``dense_vector`` field. Requires the
                 index to have been re-indexed with vectors and a query
                 embedding to be available (via Hactar, see ``--embed-url``).

Connection uses the same environment variables as ``elasticsearch_loader.py``:
``ES_HOST_URL``, ``ES_USERNAME``, ``ES_PASSWORD``.

Query file format (JSON list)::

    [
      {
        "query": "resiliation AND bail",              // optional boolean text
        "natural_language_query": "Le bailleur peut-il resilier le bail ?",
        "relevant": ["record_key_1", "record_key_2"]  // optional labels
      }
    ]

The natural-language query drives retrieval when present (it is what the dense
branch and the reranker key on); otherwise the boolean ``query`` text is used.

Examples
--------
    # latency only, BM25 (works today):
    python scripts/bench_retrieval.py --index bge_fr \
        --queries scripts/bench_queries.sample.json

    # recall@k too, once you have a labelled set:
    python scripts/bench_retrieval.py --index bge_fr --queries labelled.json \
        --k 10 20 50

    # hybrid, once vectors are indexed and Hactar embeddings are reachable:
    python scripts/bench_retrieval.py --index bge_fr --queries labelled.json \
        --mode hybrid --embed-url "$HACTAR_URL" --embed-model mxbai-embed-large
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time

from pathlib import Path
from typing import Any, Sequence

try:
    from elasticsearch import Elasticsearch
except ImportError as exc:  # pragma: no cover - operational script
    raise SystemExit(
        "The 'elasticsearch' package is required. Run this inside the app "
        "environment on the VM (it is already a project dependency)."
    ) from exc

import requests

# Fields the lexical branch searches, best-first. Mirrors the snippet the
# reranker builds (procedure_type + descriptors + raw_document_text).
DEFAULT_FIELDS = ["raw_document_text", "descriptors", "procedure_type"]
DEFAULT_VECTOR_FIELD = "embedding"


def create_es_client() -> Elasticsearch:
    """Create an Elasticsearch client from environment credentials."""
    return Elasticsearch(
        [os.getenv("ES_HOST_URL", "http://localhost:9200")],
        basic_auth=(
            os.getenv("ES_USERNAME", "elastic"),
            os.getenv("ES_PASSWORD", ""),
        ),
        verify_certs=False,
        request_timeout=60,
    )


def embed_query(
    text: str, embed_url: str, model: str, timeout: int = 30
) -> list[float]:
    """Embed ``text`` via an Ollama-style ``/api/embeddings`` gateway (Hactar)."""
    url = embed_url.rstrip("/") + "/api/embeddings"
    response = requests.post(
        url, json={"model": model, "prompt": text}, timeout=timeout
    )
    response.raise_for_status()
    payload = response.json()
    vector = payload.get("embedding") or payload.get("data")
    if not isinstance(vector, list):
        raise ValueError(f"Unexpected embedding response shape: {payload!r}")
    return [float(x) for x in vector]


def query_text(item: dict[str, Any]) -> str:
    """The text to retrieve on: natural-language query first, boolean fallback."""
    return str(
        item.get("natural_language_query") or item.get("query") or ""
    ).strip()


def bm25_body(text: str, fields: Sequence[str], size: int) -> dict[str, Any]:
    """A lexical ``simple_query_string`` search body."""
    return {
        "size": size,
        "_source": False,
        "query": {
            "simple_query_string": {
                "query": text,
                "fields": list(fields),
                "default_operator": "or",
            }
        },
    }


def hybrid_body(
    text: str,
    vector: list[float],
    fields: Sequence[str],
    vector_field: str,
    size: int,
) -> dict[str, Any]:
    """An ES 8.x ``rrf`` retriever fusing BM25 and kNN branches."""
    return {
        "size": size,
        "_source": False,
        "retriever": {
            "rrf": {
                "retrievers": [
                    {
                        "standard": {
                            "query": {
                                "simple_query_string": {
                                    "query": text,
                                    "fields": list(fields),
                                    "default_operator": "or",
                                }
                            }
                        }
                    },
                    {
                        "knn": {
                            "field": vector_field,
                            "query_vector": vector,
                            "k": size,
                            "num_candidates": max(size * 4, 100),
                        }
                    },
                ]
            }
        },
    }


def run_search(
    es: Elasticsearch, index: str, body: dict[str, Any]
) -> tuple[list[str], float]:
    """Run one search; return (ordered record ids, elapsed milliseconds)."""
    start = time.perf_counter()
    response = es.search(index=index, body=body)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    ids = [hit["_id"] for hit in response["hits"]["hits"]]
    return ids, elapsed_ms


def recall_at_k(
    retrieved: Sequence[str], relevant: Sequence[str], k: int
) -> float:
    """Fraction of the relevant set found within the top-k retrieved ids."""
    if not relevant:
        return float("nan")
    top = set(retrieved[:k])
    hits = sum(1 for rid in relevant if rid in top)
    return hits / len(relevant)


def percentile(values: Sequence[float], pct: float) -> float:
    """Simple nearest-rank percentile (values need not be pre-sorted)."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = max(
        0, min(len(ordered) - 1, round(pct / 100.0 * (len(ordered) - 1)))
    )
    return ordered[rank]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--index", required=True, help="Elasticsearch index name"
    )
    parser.add_argument(
        "--queries",
        required=True,
        type=Path,
        help="Path to the query JSON file",
    )
    parser.add_argument(
        "--mode",
        choices=["bm25", "hybrid"],
        default="bm25",
        help="Retrieval mode",
    )
    parser.add_argument(
        "--k",
        type=int,
        nargs="+",
        default=[10, 20, 50],
        help="Cut-offs for recall@k (default: 10 20 50)",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=50,
        help="Number of hits to retrieve per query (candidate depth)",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=DEFAULT_FIELDS,
        help=f"Lexical fields to search (default: {' '.join(DEFAULT_FIELDS)})",
    )
    parser.add_argument(
        "--vector-field",
        default=DEFAULT_VECTOR_FIELD,
        help=f"dense_vector field for hybrid (default: {DEFAULT_VECTOR_FIELD})",
    )
    parser.add_argument("--embed-url", default=os.getenv("HACTAR_URL", ""))
    parser.add_argument("--embed-model", default="mxbai-embed-large")
    parser.add_argument(
        "--warmup",
        type=int,
        default=1,
        help="Warm-up queries excluded from latency stats (default: 1)",
    )
    args = parser.parse_args()

    if args.mode == "hybrid" and not args.embed_url:
        parser.error(
            "--mode hybrid requires --embed-url (or HACTAR_URL) for query embeddings"
        )

    items = json.loads(args.queries.read_text(encoding="utf-8"))
    if not isinstance(items, list) or not items:
        parser.error("Query file must be a non-empty JSON list")

    es = create_es_client()
    max_k = max(args.k)
    size = max(args.size, max_k)

    latencies: list[float] = []
    recalls: dict[int, list[float]] = {k: [] for k in args.k}
    labelled = 0

    for position, item in enumerate(items):
        text = query_text(item)
        if not text:
            continue

        if args.mode == "hybrid":
            vector = embed_query(text, args.embed_url, args.embed_model)
            body = hybrid_body(
                text, vector, args.fields, args.vector_field, size
            )
        else:
            body = bm25_body(text, args.fields, size)

        retrieved, elapsed_ms = run_search(es, args.index, body)
        if position >= args.warmup:
            latencies.append(elapsed_ms)

        relevant = item.get("relevant") or []
        if relevant:
            labelled += 1
            for k in args.k:
                recalls[k].append(recall_at_k(retrieved, relevant, k))

    print(f"\nIndex        : {args.index}")
    print(f"Mode         : {args.mode}")
    print(
        f"Queries      : {len(items)} ({labelled} labelled, {args.warmup} warm-up)"
    )
    if latencies:
        print("\nLatency (ms) — search call only, excludes reranker:")
        print(f"  mean : {statistics.mean(latencies):8.1f}")
        print(f"  p50  : {percentile(latencies, 50):8.1f}")
        print(f"  p90  : {percentile(latencies, 90):8.1f}")
        print(f"  p99  : {percentile(latencies, 99):8.1f}")
    if labelled:
        print("\nRecall@k:")
        for k in sorted(args.k):
            scores = [s for s in recalls[k] if s == s]  # drop NaN
            if scores:
                print(f"  recall@{k:<3}: {statistics.mean(scores):.3f}")
    else:
        print(
            "\nNo labelled queries — add a 'relevant' list per query for recall@k."
        )


if __name__ == "__main__":
    main()
