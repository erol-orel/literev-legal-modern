"""Extract and normalise Swiss case-law citations from decision text.

Where ``legal_refs`` resolves *statute* citations (``art. 336c CO`` → Fedlex),
this module handles *case* citations — references from one decision to another.
Building a citation graph over the corpus is the foundation for the feature no
generic RAG has and every litigator needs: surfacing **adverse and
distinguishing authority**, and flagging when a cited decision has itself been
overturned or criticised.

Two Swiss federal citation forms are recognised, in all three languages:

* **Published leading decisions** — ``ATF`` (fr) / ``BGE`` (de) / ``DTF`` (it),
  as ``<collection> <volume> <part> <page>`` e.g. ``ATF 145 III 72``,
  ``BGE 145 III 72``. All three collections denote the same series, so they
  normalise to a single ``ATF`` canonical key.
* **Unpublished Federal Court judgments** — the docket number
  ``<chamber>_<seq>/<year>`` e.g. ``4A_123/2020``, ``6B_1234/2019``, optionally
  prefixed by ``arrêt``/``Urteil``/``sentenza`` or ``TF``/``BGer``/``TF``.

Pure Python (no Django, no network) so it is unit-testable in isolation and
safe to import from the backend, a management command, or the RAG pipeline.
Deliberately conservative: only well-formed references are matched, because in
a legal tool a wrong citation edge is worse than a missing one.
"""

from __future__ import annotations

import re

from dataclasses import dataclass
from typing import Iterable

__all__ = [
    "Citation",
    "build_citation_edges",
    "canonical_key",
    "extract_citations",
    "format_citation",
]

# ATF / BGE / DTF <volume> <part> <page>. Part is a Roman numeral (I-V) with an
# optional lowercase suffix (Ia, Ib). Volume 1-999, page 1-9999.
_ATF_RE = re.compile(
    r"\b(?:ATF|BGE|DTF)\s+"
    r"(?P<volume>\d{1,3})\s+"
    r"(?P<part>I[ab]?|II|III|IV|V)\s+"
    r"(?P<page>\d{1,4})\b"
)

# Federal Court docket: <1-2 digits><1-2 uppercase letters>_<seq>/<year>.
# An optional court prefix (arrêt/Urteil/sentenza/TF/TF/BGer/Tribunal fédéral)
# is allowed but not required.
_TF_RE = re.compile(
    r"\b(?P<chamber>\d{1,2}[A-F])_(?P<seq>\d{1,4})/(?P<year>\d{4})\b"
)


@dataclass(frozen=True)
class Citation:
    """A single recognised reference to another decision.

    ``kind`` is ``"ATF"`` (published leading decision) or ``"TF"`` (docket
    number). ``key`` is the normalised, language-independent identifier used as
    a graph node; ``text`` is the canonical human-readable form.
    """

    kind: str
    key: str
    text: str


def _atf(volume: str, part: str, page: str) -> Citation:
    key = f"ATF_{volume}_{part}_{page}"
    return Citation(kind="ATF", key=key, text=f"ATF {volume} {part} {page}")


def _tf(chamber: str, seq: str, year: str) -> Citation:
    docket = f"{chamber}_{seq}/{year}"
    return Citation(kind="TF", key=f"TF_{docket}", text=f"TF {docket}")


def extract_citations(text: str) -> list[Citation]:
    """Return the distinct decision citations found in ``text``, in order.

    Deduplicates by canonical key while preserving first-seen order, so a
    decision that references ``ATF 145 III 72`` three times yields one edge.
    """
    if not text:
        return []

    found: list[Citation] = []
    seen: set[str] = set()

    def _add(citation: Citation) -> None:
        if citation.key not in seen:
            seen.add(citation.key)
            found.append(citation)

    matches: list[tuple[int, Citation]] = []
    for match in _ATF_RE.finditer(text):
        matches.append(
            (
                match.start(),
                _atf(
                    match.group("volume"),
                    match.group("part"),
                    match.group("page"),
                ),
            )
        )
    for match in _TF_RE.finditer(text):
        matches.append(
            (
                match.start(),
                _tf(
                    match.group("chamber"),
                    match.group("seq"),
                    match.group("year"),
                ),
            )
        )

    for _, citation in sorted(matches, key=lambda item: item[0]):
        _add(citation)
    return found


def canonical_key(citation: Citation) -> str:
    """The normalised graph-node identifier for a citation."""
    return citation.key


def format_citation(citation: Citation) -> str:
    """The canonical human-readable form (``ATF 145 III 72`` / ``TF 4A_123/2020``)."""
    return citation.text


def extract_citations_with_context(
    text: str, window: int = 220
) -> list[tuple[Citation, str]]:
    """Like :func:`extract_citations`, but pair each citation with its passage.

    The passage is a ``±window``-character window around the first occurrence of
    each distinct citation — enough context for treatment classification (does
    the citing decision confirm, distinguish or overrule the cited one?).
    Deduplicated by key, first occurrence wins, ordered by position.
    """
    if not text:
        return []

    spans: list[tuple[int, int, Citation]] = []
    for match in _ATF_RE.finditer(text):
        spans.append(
            (
                match.start(),
                match.end(),
                _atf(
                    match.group("volume"),
                    match.group("part"),
                    match.group("page"),
                ),
            )
        )
    for match in _TF_RE.finditer(text):
        spans.append(
            (
                match.start(),
                match.end(),
                _tf(
                    match.group("chamber"),
                    match.group("seq"),
                    match.group("year"),
                ),
            )
        )

    out: list[tuple[Citation, str]] = []
    seen: set[str] = set()
    for start, end, citation in sorted(spans, key=lambda item: item[0]):
        if citation.key in seen:
            continue
        seen.add(citation.key)
        context = text[max(0, start - window) : end + window]
        out.append((citation, context))
    return out


def build_citation_edges(
    records: Iterable[tuple[str, str]],
    *,
    with_treatment: bool = False,
) -> list[dict[str, str]]:
    """Build a citation edge list from ``(record_key, text)`` decision records.

    Each edge is ``{"source": <citing record_key>, "target": <cited key>,
    "kind": "ATF"|"TF"}``. Self-citations (a decision that cites its own
    normalised key) are dropped.

    With ``with_treatment=True`` each edge also carries a ``"treatment"`` label
    (overruled / criticized / distinguished / followed / cited) classified from
    the citing passage, so a later stage can flag decisions treated negatively.
    Default off keeps the original 3-key shape.
    """
    edges: list[dict[str, str]] = []
    for record_key, text in records:
        if with_treatment:
            occurrences = extract_citations_with_context(text)
        else:
            occurrences = [(c, "") for c in extract_citations(text)]
        for citation, context in occurrences:
            if citation.key == record_key:
                continue
            edge = {
                "source": record_key,
                "target": citation.key,
                "kind": citation.kind,
            }
            if with_treatment:
                # Imported lazily so the base extractor stays dependency-free.
                from .case_treatment import classify_treatment

                edge["treatment"] = classify_treatment(context).value
            edges.append(edge)
    return edges
