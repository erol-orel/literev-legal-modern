"""Section-RAG retrieval from Elasticsearch (the ChromaDB replacement).

The read side of the retrieval consolidation: for one decision, fetch its most
relevant section chunks from the ``<source>_sections`` index with a single
hybrid (BM25 + dense kNN, RRF) query, and return them grouped by section — the
exact ``{section: [text, ...]}`` shape ``chroma_utils.get_best_section_chunks``
returns, so it is a drop-in behind the ``HYBRID_RETRIEVAL_ENABLED`` flag.

The query/index shapes and the hit-grouping are the pure, unit-tested builders
in :mod:`lr_search`; this module is only the thin Elasticsearch I/O and the
Hactar query embedding. It has no ChromaDB dependency, so it survives when the
Chroma path is retired.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings

from lr_search import (
    build_hybrid_search_body,
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


def embed_query(question: str) -> list[float]:
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
embed_query_hactar = embed_query


def get_best_section_chunks_es(
    record_key: str,
    question: str,
    query_vector: list[float],
    source: str,
) -> dict[str, list[str]]:
    """A decision's most relevant section chunks, retrieved from Elasticsearch.

    One hybrid RRF query over ``<source>_sections`` — the BM25 leg on the
    question text, the dense leg on ``query_vector`` — filtered to this decision
    (``record_key``), then grouped into per-section blocks. Drop-in replacement
    for ``chroma_utils.get_best_section_chunks``.
    """
    top_k = int(getattr(settings, "HYBRID_TOP_K_PER_SECTION", 8))
    size = int(getattr(settings, "HYBRID_SEARCH_SIZE", 40))

    body = build_hybrid_search_body(
        {"match": {"text": question}},
        query_vector,
        filters=[{"term": {"record_key": record_key}}],
        size=size,
        source_fields=["section", "text"],
    )
    response = _es_client().search(index=section_index_name(source), body=body)
    hits = [
        hit.get("_source", {})
        for hit in response.get("hits", {}).get("hits", [])
    ]
    return group_hits_by_section(hits, SECTION_NAMES, top_k)
