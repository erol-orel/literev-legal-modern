"""
Tests for api serializers.
"""

from __future__ import annotations

import pytest

from django.urls import reverse

from literev.api.serializers import (
    ProjectDocumentRAGSerializer,
    ProjectRAGSerializer,
)
from literev.models import Document, Project, ProjectDocumentRAG, ProjectRAG


@pytest.mark.django_db
def test_project_rag_serializer(project: Project):
    """
    Test the ProjectRAGSerializer.

    Ensures the serializer validates and serializes ProjectRAG instances correctly.
    """
    # Create a sample ProjectRAG instance
    project_rag = ProjectRAG.objects.create(
        project=project,
        query="What is the impact of climate change?",
        status="in-progress",
    )

    # Serialize the ProjectRAG instance
    serializer = ProjectRAGSerializer(instance=project_rag)
    data = serializer.data

    # Assert serialized fields
    assert data["id"] == project_rag.id
    assert data["project"] == project_rag.project.id
    assert data["query"] == project_rag.query
    assert data["status"] == project_rag.status
    assert "created_at" in data


@pytest.mark.django_db
def test_project_document_rag_serializer(project: Project):
    """
    Test the ProjectDocumentRAGSerializer.

    Ensures the serializer validates and serializes ProjectDocumentRAG instances correctly.
    """
    # Create sample instances
    document = Document.objects.create(
        project=project,
        procedure_type="Type A",
        decision_type="Decision X",
        decision_date="2023-01-01",
        result="Accepted",
        standards="Standard 123",
        procedure_year="2023-01-01",
    )

    project_rag = ProjectRAG.objects.create(
        project=project,
        query="What is the impact of climate change?",
        status="in-progress",
    )

    project_document_rag = ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=document,
        citation="This is a sample citation.",
        answer="This is a sample answer.",
    )

    # Serialize the ProjectDocumentRAG instance
    serializer = ProjectDocumentRAGSerializer(instance=project_document_rag)
    data = serializer.data

    # Assert serialized fields
    assert data["id"] == project_document_rag.id
    assert data["project_rag"] == project_document_rag.project_rag.id
    assert data["citation"] == project_document_rag.citation
    assert data["answer"] == project_document_rag.answer

    # Check customized document representation
    document_data = data["document"]
    assert document_data["id"] == document.id
    assert document_data["procedure_type"] == document.procedure_type
    assert document_data["decision_type"] == document.decision_type
    assert document_data["decision_date"] == document.decision_date
    assert document_data["result"] == document.result
    assert document_data["standards"] == document.standards
    assert document_data["procedure_year"] == document.procedure_year
    assert document_data["url_document"] == reverse(
        "contentdocument",
        kwargs={"document_id": document.id},
    )


@pytest.mark.django_db
def test_project_rag_serializer_validation():
    """
    Test the validation of ProjectRAGSerializer.

    Ensures invalid data raises ValidationError.
    """
    # Invalid data (missing required fields)
    invalid_data = {}
    serializer = ProjectRAGSerializer(data=invalid_data)
    assert not serializer.is_valid()
    assert "query" in serializer.errors


@pytest.mark.django_db
def test_project_document_rag_serializer_validation():
    """
    Test the validation of ProjectDocumentRAGSerializer.

    Ensures invalid data raises ValidationError.
    """
    # Invalid data (missing required fields)
    invalid_data = {}

    serializer = ProjectDocumentRAGSerializer(data=invalid_data)
    assert not serializer.is_valid()
    assert "citation" in serializer.errors
    assert "answer" in serializer.errors
