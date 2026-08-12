"""Build section documents and bulk actions for the Elasticsearch section index.

The companion to :mod:`lr_search.hybrid`: where ``hybrid`` builds the *query*
over the consolidated section index, this builds the *documents* that go into
it and the Elasticsearch bulk actions that write them. Framework-free and
side-effect-free — the application layer supplies the section text/vectors
(embedded via Hactar) and the ``Elasticsearch`` client; these helpers decide
the index name, the stable document id, and the exact ``_source`` shape, all
unit-tested without a cluster.

Stable ids (``record_key``/``section``/ordinal) make re-indexing idempotent: a
re-run of the embed command overwrites each chunk in place instead of
duplicating it, so the one-time migration is safe to repeat.
"""

from __future__ import annotations

from itertools import islice
from typing import Any, Iterable, Iterator, Sequence, TypeVar

from .hybrid import DEFAULT_VECTOR_FIELD

T = TypeVar("T")

# The section index is one physical index per source, named off the source key
# (``chambre_civile`` -> ``chambre_civile_sections``). Keeping the sources in
# separate indices mirrors the per-source Chroma collections they replace and
# lets a source be re-embedded or dropped without touching the others.
SECTION_INDEX_SUFFIX = "_sections"


def section_index_name(source: str) -> str:
    """Elasticsearch index name holding ``source``'s section vectors."""
    cleaned = source.strip()
    if not cleaned:
        raise ValueError("source must be a non-empty string")
    return f"{cleaned}{SECTION_INDEX_SUFFIX}"


def section_doc_id(record_key: str, section: str, ordinal: int) -> str:
    """Stable ``_id`` for a section chunk.

    Deterministic in ``(record_key, section, ordinal)`` so re-indexing the same
    chunk overwrites rather than duplicates it — the property that makes the
    migration command idempotent.
    """
    return f"{record_key}::{section}::{ordinal}"


def section_document(
    *,
    record_key: str,
    source: str,
    section: str,
    text: str,
    vector: Sequence[float],
    decision_date: str | None = None,
    vector_field: str = DEFAULT_VECTOR_FIELD,
) -> dict[str, Any]:
    """The ``_source`` for one section chunk: BM25 text + dense vector together.

    ``decision_date`` is only emitted when present so a source without dates
    does not write nulls the mapping's ``date`` type would reject.
    """
    document: dict[str, Any] = {
        "record_key": record_key,
        "source": source,
        "section": section,
        "text": text,
        vector_field: list(vector),
    }
    if decision_date:
        document["decision_date"] = decision_date
    return document


def bulk_index_action(
    index: str, doc_id: str, document: dict[str, Any]
) -> dict[str, Any]:
    """A single Elasticsearch ``index`` bulk action (upsert-by-id)."""
    return {
        "_op_type": "index",
        "_index": index,
        "_id": doc_id,
        "_source": document,
    }


def iter_section_bulk_actions(
    index: str,
    documents: Iterable[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    """Yield bulk ``index`` actions for section ``documents``.

    Each document must carry ``record_key`` and ``section``; the ordinal is the
    running position of the chunk within the stream, which keeps ids stable as
    long as the source is read in the same order.
    """
    seen: dict[tuple[str, str], int] = {}
    for document in documents:
        record_key = str(document.get("record_key", ""))
        section = str(document.get("section", ""))
        ordinal = seen.get((record_key, section), 0)
        seen[(record_key, section)] = ordinal + 1
        yield bulk_index_action(
            index,
            section_doc_id(record_key, section, ordinal),
            document,
        )


def group_hits_by_section(
    hits: Iterable[dict[str, Any]],
    sections: Sequence[str],
    per_section_cap: int,
    *,
    section_field: str = "section",
    text_field: str = "text",
) -> dict[str, list[str]]:
    """Group ES section-index hits into ``{section: [text, ...]}`` blocks.

    The read-side mirror of the section index: it turns a flat, relevance-ordered
    list of hit ``_source`` dicts (from a hybrid query filtered to one decision)
    into the per-section blocks the section-RAG generator consumes — one list of
    chunk texts per known section, in hit order, capped at ``per_section_cap``.
    Hits whose section is unknown, or that carry no text, are dropped; every
    section in ``sections`` is present in the result (empty if it had no hit), so
    the shape matches the Chroma path it replaces.
    """
    blocks: dict[str, list[str]] = {section: [] for section in sections}
    for hit in hits:
        section = hit.get(section_field)
        text = hit.get(text_field)
        if (
            section in blocks
            and text
            and len(blocks[section]) < per_section_cap
        ):
            blocks[section].append(str(text))
    return blocks


def batched(items: Sequence[T], size: int) -> Iterator[list[T]]:
    """Split a sequence into consecutive lists of at most ``size`` elements."""
    if size <= 0:
        raise ValueError("size must be a positive integer")
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def iter_batches(iterable: Iterable[T], size: int) -> Iterator[list[T]]:
    """Batch a lazy ``iterable`` (e.g. a generator) into lists of ``size``.

    Unlike :func:`batched`, this never materialises the whole input — the embed
    command streams millions of chunks out of Chroma, so it must batch without
    holding them all in memory.
    """
    if size <= 0:
        raise ValueError("size must be a positive integer")
    iterator = iter(iterable)
    while True:
        chunk = list(islice(iterator, size))
        if not chunk:
            return
        yield chunk
