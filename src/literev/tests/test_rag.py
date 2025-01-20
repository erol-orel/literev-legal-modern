"""Tests for RAG."""

import pytest

from literev.libs.rag_pdf import PDFRAG
from literev.models import Document, ProjectRAG


@pytest.fixture
def project_rag(project) -> ProjectRAG:
    query = (
        "Quelles sont les conditions nécessaires pour qu'une victime puisse "
        "obtenir une réparation morale selon l'art. 22 LAVI?"
    )
    project_rag = ProjectRAG(
        project=project,
        query=query,
        status="completed",
    )
    project_rag.save()
    return project_rag


def test_rag(project_rag: ProjectRAG, document_real: Document) -> None:
    docs_rag = PDFRAG(project_rag.id, [document_real.id])
    docs_rag.run()
    assert docs_rag.project_rag.documents.first().answer
