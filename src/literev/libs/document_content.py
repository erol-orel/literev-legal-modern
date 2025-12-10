import re

from django.utils.safestring import mark_safe
from rapidfuzz import fuzz


def split_into_sentences(text):
    # Very basic French sentence splitter (period, question, exclamation + newlines)
    text = text.replace("\n", " ")
    sents = re.split(r"(?<=[.!?])\s+", text)
    return sents


def highlight_sentences_fuzzy(document_text, highlight_sents, threshold=50):
    """Highlights sentences in `document_text` that are similar to those in `highlight_sents`."""
    doc_sents = split_into_sentences(document_text)
    matches = []

    # For each doc sentence, see if it matches any highlight sentence
    for i, doc_sent in enumerate(doc_sents):
        for h in highlight_sents:
            score = fuzz.token_sort_ratio(doc_sent, h)
            if score >= threshold:
                matches.append((i, doc_sent, h, score))
                break  # only highlight once per doc sentence

    # query-keywords-highlight
    # Now rebuild the text, wrapping matches in <mark>
    highlighted = []
    for i, sent in enumerate(doc_sents):
        if any(m[0] == i for m in matches):
            # highlighted.append(f'<mark style="background: yellow">{sent}</mark>')
            highlighted.append(
                f'<span style="background-color: #FFFF77">{sent}</span>'
            )
        else:
            highlighted.append(sent)
    # Put the text back together (preserving paragraphs approximately)
    return mark_safe(" ".join(highlighted))
