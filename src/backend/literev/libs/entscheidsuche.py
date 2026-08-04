"""Map entscheidsuche.ch decisions into the app's Elasticsearch schema.

`entscheidsuche.ch <https://entscheidsuche.ch>`_ is a Swiss non-profit
open-data portal aggregating published decisions from courts at every level, in
German, French and Italian. It exposes an Elasticsearch backend
(``entscheidsuche.v2-*``) whose documents carry a metadata header plus the
extracted full text (``attachment.content``).

This module turns an entscheidsuche hit ``_source`` into the compact document
shape this app's collector already reads
(``lr_search.collectors.get_all_documents_from_es_response``), so imported
federal decisions flow through the normal search / cluster / RAG pipeline.

The mapping is pure and unit-tested here; the network scroll + indexing live in
the ``import_entscheidsuche`` management command. The public entscheidsuche ES
is not reachable from CI, so the exact source field names are centralised in the
helpers below and should be confirmed against a live hit in the deployment.
"""

from __future__ import annotations

from typing import Any

# Federal-level entscheidsuche spiders (all have canton == "CH").
FEDERAL_SPIDERS: dict[str, str] = {
    "CH_BGer": "Tribunal fédéral (Bundesgericht)",
    "CH_BGE": "ATF / BGE — arrêts de principe",
    "CH_BVGer": "Tribunal administratif fédéral",
    "CH_BStGer": "Tribunal pénal fédéral",
    "CH_BPatGer": "Tribunal fédéral des brevets",
}

SUPPORTED_LANGUAGES: tuple[str, ...] = ("de", "fr", "it")


def detect_language(source: dict[str, Any]) -> str:
    """Return the two-letter language of a hit (``de``/``fr``/``it``) or ``''``."""
    raw = source.get("Sprache") or source.get("language") or ""
    if isinstance(raw, str):
        code = raw.strip().lower()[:2]
        if code in SUPPORTED_LANGUAGES:
            return code
    return ""


def _first_str(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _attachment_text(source: dict[str, Any]) -> str:
    """Extract the decision full text from the ingest-attachment field."""
    attachment = source.get("attachment")
    if isinstance(attachment, dict):
        content = attachment.get("content")
        if isinstance(content, str):
            return content
    if isinstance(attachment, list):
        for item in attachment:
            if isinstance(item, dict) and isinstance(item.get("content"), str):
                return item["content"]
    # Fallbacks for feeds that inline the text.
    return _first_str(
        source.get("Text"), source.get("content"), source.get("text")
    )


def _case_numbers(source: dict[str, Any]) -> list[str]:
    num = source.get("Num")
    if isinstance(num, list):
        return [str(n).strip() for n in num if str(n).strip()]
    if isinstance(num, str) and num.strip():
        return [num.strip()]
    return []


def _abstract(source: dict[str, Any]) -> str:
    """Pull a short summary from the abstract/regeste/headnote fields."""
    for key in ("Abstract", "Regeste", "Leitsatz", "Kopfzeile"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list):
            texts = [
                item["Text"].strip()
                for item in value
                if isinstance(item, dict)
                and isinstance(item.get("Text"), str)
                and item["Text"].strip()
            ]
            if texts:
                return " ".join(texts)
    return ""


def _procedure_type(source: dict[str, Any]) -> str:
    """A human-readable court label for the decision."""
    spider = _first_str(source.get("Spider"))
    return _first_str(
        FEDERAL_SPIDERS.get(spider),
        source.get("Gericht"),
        source.get("Abteilung"),
        spider,
    )


def map_hit(
    source: dict[str, Any],
    *,
    collector_name: str,
) -> dict[str, Any] | None:
    """Map an entscheidsuche ``_source`` to the app's ES document schema.

    Returns ``None`` for records without a signature or full text, mirroring the
    collector which skips documents that lack ``document_text``.
    """
    text = _attachment_text(source)
    signature = _first_str(source.get("Signatur"), source.get("id"))
    if not signature or not text.strip():
        return None

    case_numbers = _case_numbers(source)
    return {
        "record_key": signature,
        "document_text": text,
        # No stored HTML from the feed — the plain text renders as the body.
        "document": text,
        "collector_name": collector_name,
        "decision_date": _first_str(source.get("Datum")) or None,
        "decision_type": (case_numbers[0] if case_numbers else ""),
        "procedure_type": _procedure_type(source),
        "descriptors": _first_str(source.get("Rechtsgebiet")),
        "standards": "",
        "result": "",
        "summary": _abstract(source),
        "language": detect_language(source),
    }
