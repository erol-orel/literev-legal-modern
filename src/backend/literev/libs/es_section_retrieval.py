"""Section-RAG retrieval from Elasticsearch (the ChromaDB replacement).

The read side of the retrieval consolidation: for one decision, fetch its most
relevant section chunks from the ``<source>_sections`` index with a single
dense ``knn`` query, and return them grouped by section — the exact
``{section: [text, ...]}`` shape ``chroma_utils.get_best_section_chunks``
returns, so it is a drop-in behind the ``HYBRID_RETRIEVAL_ENABLED`` flag. The
retrieval is dense-only (like the ChromaDB path it replaces); the native RRF
hybrid retriever is a licensed Elasticsearch feature and 403s on the free
license, so we do not use it.

The index-name and hit-grouping helpers are the pure, unit-tested builders in
:mod:`lr_search`; this module is only the thin Elasticsearch I/O and the query
embedding. It has no ChromaDB dependency, so it survives when the Chroma path
is retired.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from lr_search import (
    group_hits_by_section,
    section_index_name,
)

# The four reasoning sections a decision's chunks carry. Kept in sync with the
# Chroma path's ``DOCUMENT_SECTIONS``, but defined here so this module does not
# import the ChromaDB module the consolidation removes.
SECTION_NAMES: tuple[str, ...] = (
    "Majeure",
    "Mineure-Faits",
    "Mineure-Subsommation",
    "Conclusion",
)


def _es_client() -> Any:
    from elasticsearch import Elasticsearch

    return Elasticsearch(
        [getattr(settings, "ES_HOST_URL", "")],
        basic_auth=(
            getattr(settings, "ES_USERNAME", ""),
            getattr(settings, "ES_PASSWORD", ""),
        ),
        verify_certs=bool(getattr(settings, "ES_SSL_CERTS", False)),
    )


def embed_section_query(question: str) -> list[float]:
    """Embed a query into the section index's vector space.

    Uses ``settings.HYBRID_EMBED_ENGINE`` — the *same* engine the index was
    built with (``embed_sections_to_es``), so the dense leg compares vectors
    from one space. Defaults to OpenAI (``text-embedding-3-large``, 3072-dim),
    matching the Geneva section vectors. The caller embeds the shared question
    once and passes the vector into :func:`get_best_section_chunks_es` for every
    document.

    ``embed_texts`` is imported lazily from ``chroma_utils`` because it is a
    neutral engine dispatcher (OpenAI or Hactar), not ChromaDB-specific; it
    moves to a dedicated module when the Chroma path is retired.
    """
    from literev.libs.chroma_utils import embed_texts

    engine = str(getattr(settings, "HYBRID_EMBED_ENGINE", "openai"))
    return embed_texts([question], engine)[0]


# Backwards-compatible alias: the historical name embedded via Hactar; it now
# routes through the configured engine like everything else.
embed_query_hactar = embed_section_query


def get_best_section_chunks_es(
    record_key: str,
    question: str,
    query_vector: list[float],
    source: str,
) -> dict[str, list[str]]:
    """A decision's most relevant section chunks, retrieved from Elasticsearch.

    One dense ``knn`` query over ``<source>_sections`` on ``query_vector``,
    filtered to this decision (``record_key``), then grouped into per-section
    blocks. Drop-in replacement for ``chroma_utils.get_best_section_chunks``
    (which was also dense-only). Uses plain ``knn`` rather than the RRF hybrid
    retriever, which the free Elasticsearch license does not permit.
    """
    top_k = int(getattr(settings, "HYBRID_TOP_K_PER_SECTION", 8))
    size = int(getattr(settings, "HYBRID_SEARCH_SIZE", 40))

    # Dense kNN over the section vectors, filtered to this decision. Pure dense
    # — like the ChromaDB path this replaces — because the native RRF *hybrid*
    # retriever is a licensed Elasticsearch feature (403 on the free/basic
    # license), and within a single decision the dense leg already selects the
    # relevant chunks. ``question`` stays in the signature for callers; the
    # query is carried by ``query_vector`` (its embedding).
    body = {
        "knn": {
            "field": "section_vector",
            "query_vector": query_vector,
            "k": size,
            "num_candidates": max(size * 3, 100),
            "filter": [{"term": {"record_key": record_key}}],
        },
        "size": size,
        "_source": ["section", "text"],
    }
    response = _es_client().search(index=section_index_name(source), body=body)
    hits = [
        hit.get("_source", {})
        for hit in response.get("hits", {}).get("hits", [])
    ]
    return group_hits_by_section(hits, SECTION_NAMES, top_k)
