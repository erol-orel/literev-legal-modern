"""Project Serializers."""

from __future__ import annotations

from django.urls import reverse
from rest_framework import serializers

from literev.models import ProjectDocumentRAG, ProjectRAG


class ProjectRAGSerializer(serializers.ModelSerializer):
    """
    Serializer for ProjectRAG model.
    """

    class Meta:
        model = ProjectRAG
        fields = ["id", "project", "query", "created_at", "status"]
        read_only_fields = ["id", "project", "created_at"]


class ProjectDocumentRAGSerializer(serializers.ModelSerializer):
    """
    Serializer for ProjectDocumentRAG model.
    """

    class Meta:
        model = ProjectDocumentRAG
        fields = [
            "id",
            "project_rag",
            "document",
            "citation",
            "answer",
        ]
        read_only_fields = ["id", "project_rag", "document"]

    def to_representation(self, instance):
        """Customize the representation to include document object."""
        representation = super().to_representation(instance)
        representation["document"] = {
            "id": instance.document.id,
            "procedure_type": instance.document.procedure_type,
            "decision_type": instance.document.decision_type,
            "decision_date": instance.document.decision_date,
            "result": instance.document.result,
            "standards": instance.document.standards,
            "procedure_year": instance.document.procedure_year,
            "url_document": reverse(
                "contentdocument",
                kwargs={
                    "document_id": instance.document.id,
                },
            ),
        }
        return representation
