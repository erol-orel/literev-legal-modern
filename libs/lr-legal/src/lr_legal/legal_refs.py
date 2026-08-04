"""Resolve Swiss legal-norm citations to canonical statute URLs.

Two input forms are supported:

* **Compact corpus tokens** as stored in ``Document.standards`` (the raw
  ``normes`` field) — e.g. ``CO.336c.al1.letb``, ``Cst.29.al2``, ``LPAC.20``.
* **Free-text article citations** produced by the RAG summariser — e.g.
  ``art. 336c al. 1 let. b CO`` (fr), ``Art. 336c OR`` (de),
  ``art. 336c CO`` (it).

Federal codes resolve to deep links on the official Fedlex portal
(https://www.fedlex.admin.ch), anchored to the article (``#art_<n>``). Codes we
do not have a *verified* mapping for resolve to ``url=None`` so callers render
plain text: in a legal tool a wrong citation link is worse than no link, so the
mapping is deliberately conservative and only covers the core federal codes.

The module is pure Python (no Django, no network) so it is unit-testable in
isolation and safe to import from both the backend and the RAG pipeline.
"""

from __future__ import annotations

import re

from dataclasses import dataclass

__all__ = [
    "FEDLEX_CODES",
    "NormRef",
    "fedlex_url",
    "resolve",
    "resolve_citation",
    "resolve_norm_token",
]

# Fedlex ELI base segments, verified against fedlex.admin.ch (SR numbers noted).
# Keys are lower-cased code abbreviations across the three official languages
# (fr / de / it) so the same statute resolves whatever language cited it.
FEDLEX_CODES: dict[str, str] = {
    # Civil Code — CC (fr/it) / ZGB (de), SR 210
    "cc": "24/233_245_233",
    "zgb": "24/233_245_233",
    # Code of Obligations — CO (fr/it) / OR (de), SR 220
    "co": "27/317_321_377",
    "or": "27/317_321_377",
    # Criminal Code — CP (fr/it) / StGB (de), SR 311.0
    "cp": "54/757_781_799",
    "stgb": "54/757_781_799",
    # Federal Constitution — Cst (fr) / BV (de) / Cost (it), SR 101
    "cst": "1999/404",
    "bv": "1999/404",
    "cost": "1999/404",
    # Civil Procedure — CPC (fr/it) / ZPO (de), SR 272
    "cpc": "2010/262",
    "zpo": "2010/262",
    # Criminal Procedure — CPP (fr/it) / StPO (de), SR 312.0
    "cpp": "2010/267",
    "stpo": "2010/267",
    # Federal Supreme Court Act — LTF (fr/it) / BGG (de), SR 173.110
    "ltf": "2006/218",
    "bgg": "2006/218",
}

_LANGS = {"fr", "de", "it", "rm", "en"}
_DEFAULT_LANG = "fr"

# A sub-reference segment inside a compact token, e.g. ``al1``, ``letb``, ``ch2``.
_SUBREF_RE = re.compile(
    r"^(al|let|lit|lett|ch|cpv|abs|ziff|par|n|no)\.?\s*([0-9]+|[a-z]+)$",
    re.IGNORECASE,
)
# A plausible article number: digits with an optional letter/bis/ter suffix.
_ARTICLE_RE = re.compile(r"^\d+[a-z]*$", re.IGNORECASE)

# A free-text citation such as "art. 336c al. 1 let. b CO" / "Art. 336c OR".
_CITATION_RE = re.compile(
    r"art(?:icle|\.)?\s*"
    r"(?P<article>\d+[a-z]*)"
    r"(?P<subs>(?:\s*(?:al|let|lit|lett|ch|cpv|abs|ziff|par)\.?\s*"
    r"(?:[0-9]+|[a-z]+))*)"
    r"[\s.,;]*"
    r"(?P<code>[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.\-]*)\s*$",
    re.IGNORECASE,
)

_SUBREF_LABELS = {
    "al": "al.",
    "let": "let.",
    "lit": "lit.",
    "lett": "lett.",
    "ch": "ch.",
    "cpv": "cpv.",
    "abs": "Abs.",
    "ziff": "Ziff.",
    "par": "§",
    "n": "n°",
    "no": "n°",
}


@dataclass(frozen=True)
class NormRef:
    """A parsed legal-norm reference and its canonical URL (if resolvable)."""

    code: str
    """Display code as cited, e.g. ``CO`` or ``Cst-GE``."""
    article: str | None
    """Article number as cited, e.g. ``336c`` (``None`` if code-only)."""
    subrefs: tuple[str, ...]
    """Formatted sub-references, e.g. ``("al. 1", "let. b")``."""
    url: str | None
    """Canonical statute URL, or ``None`` when the code is not mapped."""

    @property
    def label(self) -> str:
        """Human-readable citation, e.g. ``CO art. 336c al. 1 let. b``."""
        parts = [self.code]
        if self.article:
            parts.append(f"art. {self.article}")
        parts.extend(self.subrefs)
        return " ".join(parts)


def fedlex_url(
    code: str, article: str | None, lang: str = _DEFAULT_LANG
) -> str | None:
    """Build a Fedlex URL for a federal ``code`` (+ optional ``article``).

    Returns ``None`` when ``code`` is not one of the mapped federal codes.
    """
    eli = FEDLEX_CODES.get(code.strip().rstrip(".").lower())
    if not eli:
        return None
    lang = lang if lang in _LANGS else _DEFAULT_LANG
    base = f"https://www.fedlex.admin.ch/eli/cc/{eli}/{lang}"
    if article:
        return f"{base}#art_{article.strip().lower()}"
    return base


def _format_subref(segment: str) -> str | None:
    match = _SUBREF_RE.match(segment)
    if not match:
        return None
    marker = match.group(1).lower()
    value = match.group(2).lower()
    label = _SUBREF_LABELS.get(marker, marker + ".")
    return f"{label} {value}"


def resolve_norm_token(
    token: str, lang: str = _DEFAULT_LANG
) -> NormRef | None:
    """Resolve a compact corpus token like ``CO.336c.al1.letb``.

    Returns ``None`` only when the token is empty/unparseable; an unmapped code
    still yields a :class:`NormRef` with ``url=None`` so the caller keeps the
    (unlinked) label.
    """
    token = (token or "").strip()
    if not token:
        return None

    segments = [seg.strip() for seg in token.split(".") if seg.strip()]
    if not segments:
        return None

    code = segments[0]
    rest = segments[1:]

    article: str | None = None
    subref_segments: list[str] = []
    if rest and _ARTICLE_RE.match(rest[0]) and not _SUBREF_RE.match(rest[0]):
        article = rest[0]
        subref_segments = rest[1:]
    else:
        subref_segments = rest

    subrefs = tuple(
        formatted
        for seg in subref_segments
        if (formatted := _format_subref(seg)) is not None
    )
    return NormRef(
        code=code,
        article=article,
        subrefs=subrefs,
        url=fedlex_url(code, article, lang),
    )


def resolve_citation(text: str, lang: str = _DEFAULT_LANG) -> NormRef | None:
    """Resolve a free-text citation like ``art. 336c al. 1 let. b CO``.

    Returns ``None`` if no article-and-code pattern is found.
    """
    match = _CITATION_RE.search((text or "").strip())
    if not match:
        return None

    code = match.group("code").strip().rstrip(".")
    article = match.group("article")
    subs_blob = match.group("subs") or ""
    subrefs = tuple(
        formatted
        for seg in re.findall(
            r"(?:al|let|lit|lett|ch|cpv|abs|ziff|par)\.?\s*(?:[0-9]+|[a-z]+)",
            subs_blob,
            re.IGNORECASE,
        )
        if (formatted := _format_subref(re.sub(r"\s+", "", seg))) is not None
    )
    return NormRef(
        code=code,
        article=article,
        subrefs=subrefs,
        url=fedlex_url(code, article, lang),
    )


def resolve(text: str, lang: str = _DEFAULT_LANG) -> NormRef | None:
    """Best-effort resolve: try the free-text form, then the compact token."""
    if not text or not text.strip():
        return None
    return resolve_citation(text, lang) or resolve_norm_token(text, lang)
