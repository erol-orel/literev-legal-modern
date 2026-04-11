from __future__ import annotations

import re

from collections.abc import Iterable

from django.utils.safestring import SafeString, mark_safe
from rapidfuzz import fuzz


def split_into_sentences(text: str) -> list[str]:
    """Split a document into coarse sentences for highlighting.

    Parameters
    ----------
    text : str
        Raw document text.

    Returns
    -------
    list[str]
        Sentence-like text chunks.
    """
    normalized_text = text.replace("\n", " ")
    return [
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text)
        if sentence
    ]


def highlight_sentences_fuzzy(
    document_text: str,
    highlight_sents: Iterable[str],
    threshold: int = 65,
) -> SafeString:
    """Highlight document sentences that fuzzily match target sentences.

    Parameters
    ----------
    document_text : str
        Source document text.
    highlight_sents : Iterable[str]
        Sentences that should be highlighted when matched.
    threshold : int, default=65
        Minimum fuzzy-match score required to highlight a sentence.

    Returns
    -------
    SafeString
        HTML-safe text with matching sentences wrapped in a highlight span.
    """
    doc_sents = split_into_sentences(document_text)
    target_sentences = list(highlight_sents)
    matching_indexes: set[int] = set()

    for index, doc_sentence in enumerate(doc_sents):
        for highlight_sentence in target_sentences:
            score = fuzz.token_sort_ratio(doc_sentence, highlight_sentence)
            if score >= threshold:
                matching_indexes.add(index)
                break

    highlighted_sentences = [
        (
            f'<span style="background-color: #FFFF77">{sentence}</span>'
            if index in matching_indexes
            else sentence
        )
        for index, sentence in enumerate(doc_sents)
    ]
    return mark_safe(" ".join(highlighted_sentences))


__all__ = ["highlight_sentences_fuzzy", "split_into_sentences"]
