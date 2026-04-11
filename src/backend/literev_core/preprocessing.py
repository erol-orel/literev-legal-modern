from __future__ import annotations

from literev.models import Document
from lr_preprocessing import (
    create_ngrams,
    preprocess_documents,
)
from lr_preprocessing import (
    prepare_document as prepare_document_text,
)


def prepare_document(document: Document) -> str | None:
    return prepare_document_text(
        document.raw_document_text or "",
        raw_document_id=document.raw_document_id,
        document_pk=document.pk,
    )


def update_prepared_document(
    document: Document, prepared_document: str
) -> None:
    document.prepared_for_ngrams = prepared_document
    document.save()


__all__ = [
    "create_ngrams",
    "prepare_document",
    "preprocess_documents",
    "update_prepared_document",
]
