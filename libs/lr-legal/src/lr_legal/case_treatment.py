"""Classify how one decision *treats* another it cites.

An edge in the citation graph says "A cites B"; it does not say *how*. This
module labels the citing passage — the sentence around the citation — with a
treatment, so a decision that has been overruled or criticised can be flagged
"verify: still good law?" and distinguishing authority can be surfaced.

Phase 2 of the adverse-authority feature (see ``docs/adverse-authority.md``).
It is a **deterministic, explainable** keyword classifier — multilingual
(fr/de/it) — chosen over an LLM on purpose: a citation-treatment label drives a
professional-stakes warning, so it must be reproducible and its evidence (the
matched cue and passage) inspectable. An LLM pass can be layered on later for
the ambiguous middle; the heuristic is the dependable floor.

Pure Python (no Django, no network), unit-tested in isolation.
"""

from __future__ import annotations

import re

from enum import Enum

__all__ = [
    "Treatment",
    "classify_treatment",
    "is_negative_treatment",
]


class Treatment(str, Enum):
    """How a citing decision treats the decision it cites (most→least severe)."""

    OVERRULED = "overruled"  # revirement / abandoned / no longer good law
    CRITICIZED = "criticized"  # doubted / contestable
    DISTINGUISHED = "distinguished"  # does not apply to these facts
    FOLLOWED = "followed"  # confirmed / applied
    CITED = "cited"  # neutral mention (default)


# Cue phrases per treatment, ordered strongest-first. Multilingual (fr/de/it);
# lower-cased substring match on a normalised passage. Deliberately narrow —
# a false "overruled" is worse than a missed one, so only unambiguous cues.
_CUES: tuple[tuple[Treatment, tuple[str, ...]], ...] = (
    (
        Treatment.OVERRULED,
        (
            "revirement de jurisprudence",
            "changement de jurisprudence",
            "abandonne la jurisprudence",
            "ne saurait être maintenue",
            "n'est plus valable",
            "n'est plus d'actualité",
            "praxisänderung",
            "aufgegeben",
            "nicht mehr gefolgt",
            "cambiamento di giurisprudenza",
            "non più valida",
        ),
    ),
    (
        Treatment.CRITICIZED,
        (
            "critiquée",
            "critiquable",
            "contestable",
            "doute sur",
            "on peut se demander",
            "kritisiert",
            "zweifelhaft",
            "criticata",
            "discutibile",
        ),
    ),
    (
        Treatment.DISTINGUISHED,
        (
            "à distinguer",
            "se distingue",
            "contrairement à",
            "ne s'applique pas",
            "n'est pas applicable",
            "cas différent",
            "abzugrenzen",
            "im unterschied zu",
            "nicht anwendbar",
            "a differenza di",
            "non applicabile",
        ),
    ),
    (
        Treatment.FOLLOWED,
        (
            "confirme",
            "confirmée",
            "conformément à",
            "dans le même sens",
            "il y a lieu de suivre",
            "selon la jurisprudence",
            "bestätigt",
            "gemäss",
            "in gleichem sinne",
            "conferma",
            "conformemente",
            "secondo la giurisprudenza",
        ),
    ),
)

_WS_RE = re.compile(r"\s+")


def _normalise(passage: str) -> str:
    return _WS_RE.sub(" ", passage).strip().lower()


def classify_treatment(passage: str) -> Treatment:
    """Return the treatment expressed in a citing ``passage``.

    Scans strongest-cue-first; falls back to ``CITED`` (a neutral mention) when
    no cue matches, so an unrecognised passage never over-claims.
    """
    text = _normalise(passage)
    if not text:
        return Treatment.CITED
    for treatment, cues in _CUES:
        if any(cue in text for cue in cues):
            return treatment
    return Treatment.CITED


def is_negative_treatment(treatment: Treatment) -> bool:
    """Whether the treatment should trigger a "verify: still good law?" flag."""
    return treatment in (Treatment.OVERRULED, Treatment.CRITICIZED)
