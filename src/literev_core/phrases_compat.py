"""Compatibility with gensim phrases."""

from __future__ import annotations

from collections import Counter
from math import log2
from typing import Iterable, List, Sequence, Set, Tuple

Doc = List[str]
Pair = Tuple[str, str]


def _bigrams(doc: Sequence[str]) -> Iterable[Pair]:
    for i in range(len(doc) - 1):
        yield (doc[i], doc[i + 1])


def _select_bigrams(
    docs: Iterable[Doc],
    min_count: int,
    pmi_threshold: float,
) -> Set[Pair]:
    unig = Counter()
    big = Counter()
    total_tokens = 0
    total_bigrams = 0

    for doc in docs:
        total_tokens += len(doc)
        unig.update(doc)
        bs = list(_bigrams(doc))
        total_bigrams += len(bs)
        big.update(bs)

    sel: Set[Pair] = set()
    denom_tok = max(1, total_tokens)
    denom_big = max(1, total_bigrams)

    for (w1, w2), c12 in big.items():
        if c12 < min_count:
            continue
        p12 = c12 / denom_big
        p1 = unig[w1] / denom_tok
        p2 = unig[w2] / denom_tok
        if p12 == 0 or p1 == 0 or p2 == 0:
            continue
        pmi = log2(p12 / (p1 * p2))
        if pmi >= pmi_threshold:
            sel.add((w1, w2))
    return sel


def _merge(doc: Doc, selected: Set[Pair], sep: str) -> Doc:
    out: Doc = []
    i, n = 0, len(doc)
    while i < n:
        if i + 1 < n and (doc[i], doc[i + 1]) in selected:
            out.append(f"{doc[i]}{sep}{doc[i + 1]}")
            i += 2
        else:
            out.append(doc[i])
            i += 1
    return out


class Phrases:
    """
    Gensim-like interface backed by PMI.
    `threshold` maps to a PMI cutoff (try 5-8 to mimic gensim's 10-ish).
    """

    def __init__(
        self,
        sentences: Iterable[Doc],
        min_count: int = 5,
        threshold: float = 10.0,
        sep: str = "_",
    ):
        self.sep = sep
        # Heuristic mapping: gensim threshold≈10 → PMI≈6-8 works well in practice.
        pmi_threshold = max(1.0, float(threshold) * 0.7)
        self.selected = _select_bigrams(
            sentences, min_count=min_count, pmi_threshold=pmi_threshold
        )


class Phraser:
    def __init__(self, phrases: Phrases):
        self.selected = phrases.selected
        self.sep = phrases.sep

    def __getitem__(self, doc: Doc) -> Doc:
        return _merge(doc, self.selected, self.sep)
