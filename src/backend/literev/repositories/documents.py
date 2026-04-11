from __future__ import annotations

from literev.models import Document, Project
from lr_contracts import SearchDocumentMetadata


def create_document(
    project: Project, metadata: SearchDocumentMetadata
) -> Document:
    return Document.objects.create(
        project=project,
        raw_document_id=metadata.doc_id,
        chamber=metadata.chamber,
        raw_document_text=metadata.document_text,
        document_html_text=metadata.document_html_text,
        decision_date=metadata.decision_date,
        decision_type=metadata.decision_type,
        procedure_type=metadata.procedure_type,
        descriptors=metadata.descriptors,
        standards=metadata.standards,
        result=metadata.result,
        record_key=metadata.record_key,
    )


def update_prepared_document(
    document: Document, prepared_document: str
) -> None:
    document.prepared_for_ngrams = prepared_document
    document.save()


def update_preprocessed_document(
    document_id: int, preprocessed_document: str
) -> None:
    document = Document.objects.get(pk=document_id)
    document.preprocessed_document = preprocessed_document
    document.save()
