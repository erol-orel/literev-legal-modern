from __future__ import annotations

import re

from collections.abc import Iterable
from typing import Any, TypedDict, cast

from django.utils.safestring import SafeString, mark_safe
from rapidfuzz import fuzz

from literev.libs.project_workflows import validate_project_access
from literev.models import Document, ProjectDocumentRAG, User
from lr_legal.legal_refs import resolve_norm_token


class NormRefEntry(TypedDict):
    token: str
    label: str
    url: str | None


class DocumentSummary(TypedDict):
    id: int
    procedure_type: str
    decision_type: str
    decision_date: str | None
    result: str
    standards: str
    standards_refs: list[NormRefEntry]
    language: str


def _build_standards_refs(standards: str) -> list[NormRefEntry]:
    """Split the ``;``-separated ``standards`` field into linkable references.

    Each token (e.g. ``CO.336c.al1.letb``) becomes ``{token, label, url}``;
    ``url`` is ``None`` for cantonal/unmapped codes so the UI shows plain text.
    """
    refs: list[NormRefEntry] = []
    for raw in (standards or "").split(";"):
        token = raw.strip()
        if not token:
            continue
        ref = resolve_norm_token(token)
        if ref is not None:
            refs.append({"token": token, "label": ref.label, "url": ref.url})
        else:
            refs.append({"token": token, "label": token, "url": None})
    return refs


class DocumentContentPayload(TypedDict):
    document: DocumentSummary
    content: dict[str, Any]


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


def _build_document_summary(document: Document) -> DocumentSummary:
    return {
        "id": document.id,
        "procedure_type": document.procedure_type,
        "decision_type": document.decision_type or "",
        "decision_date": document.decision_date.isoformat()
        if document.decision_date
        else None,
        "result": document.result or "",
        "standards": document.standards or "",
        "standards_refs": _build_standards_refs(document.standards or ""),
        "language": document.language or "",
    }


def build_document_content_payload(
    user: User,
    document_id: int,
) -> DocumentContentPayload | None:
    document = (
        Document.objects.select_related("project")
        .filter(id=document_id)
        .first()
    )
    if not document:
        return None

    if not validate_project_access(user, document.project_id):
        return None

    return {
        "document": _build_document_summary(document),
        "content": {
            "html_text": document.document_html_text or "",
            "raw_text": document.raw_document_text or "",
        },
    }


def build_highlighted_document_content_payload(
    user: User,
    document_rag_id: int,
) -> DocumentContentPayload | None:
    document_rag = (
        ProjectDocumentRAG.objects.select_related(
            "document", "project_rag__project"
        )
        .filter(id=document_rag_id)
        .first()
    )
    if not document_rag:
        return None

    if not validate_project_access(user, document_rag.project_rag.project_id):
        return None

    citation_context = document_rag.citation_context or {}
    highlight_sents: list[str] = []
    if isinstance(citation_context, dict):
        highlight_sents = list(citation_context.get("Mineure-Faits", []))
        highlight_sents += list(
            citation_context.get("Mineure-Subsommation", [])
        )

    raw_document_text = document_rag.document.raw_document_text or ""
    html_text = document_rag.document.document_html_text or ""

    if highlight_sents:
        highlighted_text = cast(
            str,
            highlight_sentences_fuzzy(
                raw_document_text.replace("\n", "<br>"),
                highlight_sents,
            ),
        )
    else:
        highlighted_text = raw_document_text

    return {
        "document": _build_document_summary(document_rag.document),
        "content": {
            "html_text": html_text,
            "raw_text": raw_document_text,
            "highlighted_text": highlighted_text.replace("\n", "<br>"),
        },
    }


__all__ = [
    "build_document_content_payload",
    "build_highlighted_document_content_payload",
    "highlight_sentences_fuzzy",
    "split_into_sentences",
]
