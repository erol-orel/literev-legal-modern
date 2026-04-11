"""Compatibility with gensim phrases."""

from __future__ import annotations

from collections import Counter
from math import log2
from typing import (
    AbstractSet,
    Dict,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    overload,
)

Doc = List[str]
Corpus = Iterable[Doc]
Pair = Tuple[str, str]

# Optional: shipped by gensim; included here to ease migration
ENGLISH_CONNECTOR_WORDS: FrozenSet[str] = frozenset(
    "a an the for of with without at from to in on by and or".split()
)


def _bigrams(doc: Sequence[str]) -> Iterable[Pair]:
    for i in range(len(doc) - 1):
        yield (doc[i], doc[i + 1])


def _is_single(obj: Iterable[object]) -> Tuple[bool, Iterable[object]]:
    it = iter(obj)
    tmp = it
    try:
        first = next(it)
        it = (x for x in (first, *it))
    except StopIteration:
        return True, obj
    if isinstance(first, str):
        return True, it
    if tmp is obj:
        return False, it
    return False, obj


def _select_bigrams(
    docs: Corpus,
    min_count: int,
    pmi_threshold: float,
) -> Dict[Pair, float]:
    unig: Counter[str] = Counter()
    big: Counter[Pair] = Counter()
    total_tokens = 0
    total_bigrams = 0

    for doc in docs:
        total_tokens += len(doc)
        unig.update(doc)
        bs = list(_bigrams(doc))
        total_bigrams += len(bs)
        big.update(bs)

    denom_tok = max(1, total_tokens)
    denom_big = max(1, total_bigrams)

    selected: Dict[Pair, float] = {}
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
            selected[(w1, w2)] = pmi
    return selected


def _merge(doc: Doc, selected: AbstractSet[Pair], sep: str) -> Doc:
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


def _apply(
    sentences: Corpus, selected: AbstractSet[Pair], sep: str
) -> Iterator[Doc]:
    for d in sentences:
        yield _merge(d, selected, sep)


class _HasSelected(Protocol):
    selected: AbstractSet[Pair]
    sep: str


class Phrases:
    """
    Gensim-like interface backed by PMI. Only adjacent bigrams are merged.
    `threshold` maps roughly to a PMI cutoff (`~0.7 * gensim_threshold`).
    """

    def __init__(
        self,
        sentences: Optional[Corpus] = None,
        min_count: int = 5,
        threshold: float = 10.0,
        max_vocab_size: int = 0,  # ignored; present for signature compatibility
        delimiter: str = "_",
        progress_per: int = 0,  # ignored
        scoring: str = "default",  # ignored; PMI is used
        connector_words: AbstractSet[str] = frozenset(),
    ) -> None:
        self.sep: str = delimiter
        self.min_count: int = int(min_count)
        self.threshold: float = float(threshold)
        self.connector_words: FrozenSet[str] = frozenset(connector_words)

        # Heuristic mapping: gensim threshold≈10 → PMI≈6-8
        pmi_threshold = max(1.0, float(threshold) * 0.7)

        self._selected: Dict[Pair, float] = {}
        if sentences is not None:
            sel = _select_bigrams(
                sentences,
                min_count=self.min_count,
                pmi_threshold=pmi_threshold,
            )
            self._selected.update(sel)

        # Expose gensim-like attributes
        self.phrasegrams: Dict[str, float] = {
            f"{a}{self.sep}{b}": score
            for (a, b), score in self._selected.items()
        }

    @property
    def selected(self) -> Set[Pair]:
        # set view for merging
        return set(self._selected.keys())

    def export_phrases(self) -> Dict[str, float]:
        return dict(self.phrasegrams)

    def freeze(self) -> FrozenPhrases:
        return FrozenPhrases(self)

    @overload
    def __getitem__(self, sentence: Doc) -> Doc: ...
    @overload
    def __getitem__(self, sentence: Corpus) -> Iterable[Doc]: ...
    def __getitem__(self, sentence: Doc | Corpus) -> Doc | Iterable[Doc]:
        is_single, it = _is_single(sentence)
        if not is_single:
            return _apply(it, self.selected, self.sep)  # type: ignore[arg-type]
        return _merge(sentence, self.selected, self.sep)  # type: ignore[arg-type]


class FrozenPhrases:
    """
    Read-only applier compatible with gensim's FrozenPhrases for typical usage:
    - created via Phrases.freeze() or FrozenPhrases(Phrases)
    - indexable for single sentence or corpus
    """

    def __init__(self, phrases_model: Phrases | _HasSelected) -> None:
        if isinstance(phrases_model, Phrases):
            self.sep: str = phrases_model.sep
            self.threshold: float = phrases_model.threshold
            self.min_count: int = phrases_model.min_count
            self.connector_words: FrozenSet[str] = (
                phrases_model.connector_words
            )
            self.phrasegrams: Dict[str, float] = phrases_model.export_phrases()
            self._selected: Set[Pair] = phrases_model.selected
        else:
            # Accept a minimal “phraser-like” object (selected + sep)
            self.sep = phrases_model.sep
            self.threshold = 0.0
            self.min_count = 1
            self.connector_words = frozenset()
            self._selected = set(phrases_model.selected)
            self.phrasegrams = {
                f"{a}{self.sep}{b}": 1.0 for (a, b) in self._selected
            }

    @overload
    def __getitem__(self, sentence: Doc) -> Doc: ...
    @overload
    def __getitem__(self, sentence: Corpus) -> Iterable[Doc]: ...
    def __getitem__(self, sentence: Doc | Corpus) -> Doc | Iterable[Doc]:
        is_single, it = _is_single(sentence)
        if not is_single:
            return _apply(it, self._selected, self.sep)  # type: ignore[arg-type]
        return _merge(sentence, self._selected, self.sep)  # type: ignore[arg-type]


# Back-compat alias like gensim:
Phraser = FrozenPhrases
