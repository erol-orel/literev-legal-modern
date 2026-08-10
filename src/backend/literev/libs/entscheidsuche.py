"""Map entscheidsuche.ch decisions into the app's Elasticsearch schema.

`entscheidsuche.ch <https://entscheidsuche.ch>`_ is a Swiss non-profit
open-data portal aggregating published decisions from courts at every level, in
German, French and Italian. It exposes an Elasticsearch backend (one index per
court, e.g. ``entscheidsuche-ch_bger``) whose documents carry a metadata header
plus an ``attachment`` object with the extracted full text.

Confirmed live schema (2026) of a ``_source`` document::

    {
      "id":        "CH_BGer_002_9C-130-2023_2023-03-01",
      "date":      "2023-03-01",
      "canton":    "CH",
      "hierarchy": ["CH", "CH_BGer", "CH_BGer_002"],
      "reference": ["9C 130/2023", "9C_130/2023"],
      "abstract":  {"de": "...", "fr": "...", "it": "..."},
      "title":     {"de": "...", "fr": "...", "it": "..."},
      "meta":      {"de": "...", "fr": "...", "it": "..."},
      "attachment": {
        "language":     "de",
        "content_type": "text/html; charset=UTF-8",
        "content_url":  "https://entscheidsuche.ch/docs/.../....html",
        "content":      "<full extracted text>"
      }
    }

Courts are identified by ``hierarchy[1]`` (e.g. ``CH_BGer`` = Tribunal fédéral);
the decision language is ``attachment.language``. This module turns such a hit
into the compact document shape the app's collector already reads
(``lr_search.collectors.get_all_documents_from_es_response``), so imported
federal decisions flow through the normal search / cluster / RAG pipeline.

The mapping is pure and unit-tested here; the network scroll + indexing live in
the ``import_entscheidsuche`` management command.
"""

from __future__ import annotations

from typing import Any

# Federal-level entscheidsuche courts, keyed by their ``hierarchy[1]`` code
# (all have canton == "CH").
FEDERAL_SPIDERS: dict[str, str] = {
    "CH_BGer": "Tribunal fédéral (Bundesgericht)",
    "CH_BVGer": "Tribunal administratif fédéral",
    "CH_BStGer": "Tribunal pénal fédéral",
    "CH_BPatGer": "Tribunal fédéral des brevets",
}

SUPPORTED_LANGUAGES: tuple[str, ...] = ("de", "fr", "it")


def _attachment(source: dict[str, Any]) -> dict[str, Any]:
    """Return the attachment object (handling the list-valued variant)."""
    attachment = source.get("attachment")
    if isinstance(attachment, dict):
        return attachment
    if isinstance(attachment, list):
        for item in attachment:
            if isinstance(item, dict):
                return item
    return {}


def detect_language(source: dict[str, Any]) -> str:
    """Return the two-letter decision language (``de``/``fr``/``it``) or ``''``.

    The language lives in ``attachment.language`` in the current schema; older
    feeds used a top-level ``Sprache``/``language`` field, still accepted here.
    """
    attachment = _attachment(source)
    raw = (
        attachment.get("language")
        or source.get("Sprache")
        or source.get("language")
        or ""
    )
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


def _localized(value: Any, lang: str) -> str:
    """Pick the ``lang`` entry from a ``{de,fr,it}`` dict, with fallbacks."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        ordered = [lang] if lang else []
        ordered += ["fr", "de", "it"]
        for key in ordered:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _attachment_text(source: dict[str, Any]) -> str:
    """Extract the decision full text from ``attachment.content``."""
    content = _attachment(source).get("content")
    if isinstance(content, str):
        return content
    # Fallbacks for feeds that inline the text elsewhere.
    return _first_str(
        source.get("Text"), source.get("content"), source.get("text")
    )


def _case_numbers(source: dict[str, Any]) -> list[str]:
    num = source.get("reference")
    if num is None:
        num = source.get("Num")
    if isinstance(num, list):
        return [str(n).strip() for n in num if str(n).strip()]
    if isinstance(num, str) and num.strip():
        return [num.strip()]
    return []


def _court_code(source: dict[str, Any]) -> str:
    """Return the court code (``hierarchy[1]``, e.g. ``CH_BGer``)."""
    hierarchy = source.get("hierarchy")
    if isinstance(hierarchy, list) and len(hierarchy) >= 2:
        code = hierarchy[1]
        if isinstance(code, str):
            return code.strip()
    return _first_str(source.get("Spider"))


def _procedure_type(source: dict[str, Any], lang: str) -> str:
    """A human-readable court label for the decision."""
    code = _court_code(source)
    return _first_str(
        FEDERAL_SPIDERS.get(code),
        _localized(source.get("meta"), lang),
        _localized(source.get("title"), lang),
        source.get("Gericht"),
        code,
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
    signature = _first_str(source.get("id"), source.get("Signatur"))
    if not signature or not text.strip():
        return None

    lang = detect_language(source)
    case_numbers = _case_numbers(source)
    return {
        "record_key": signature,
        "document_text": text,
        # No stored HTML markup from the feed — the plain text renders as the
        # body via the document viewer's raw-text fallback.
        "document": "",
        "collector_name": collector_name,
        "decision_date": _first_str(source.get("date"), source.get("Datum"))
        or None,
        "decision_type": (case_numbers[0] if case_numbers else ""),
        "procedure_type": _procedure_type(source, lang),
        "descriptors": _localized(source.get("title"), lang),
        "standards": "",
        "result": "",
        "summary": _localized(source.get("abstract"), lang)
        or _localized(source.get("Abstract"), lang),
        "language": lang,
    }
