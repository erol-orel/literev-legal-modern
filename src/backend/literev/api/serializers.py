"""Project Serializers."""

from __future__ import annotations

from django.urls import reverse
from rest_framework import serializers

from literev.models import ProjectDocumentRAG, ProjectRAG


class ProjectRAGSerializer(serializers.ModelSerializer):
    status_display = serializers.SerializerMethodField()

    class Meta:
        model = ProjectRAG
        fields = [
            "id",
            "project",
            "query",
            "created_at",
            "status",
            "status_display",
            "valid_answer_count",
            "num_documents",
        ]
        read_only_fields = ["id", "project", "created_at"]

    def get_status_display(self, obj):
        return obj.get_status_display()


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
            "confidence_score",
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
            "language": instance.document.language or "",
            "procedure_year": instance.document.procedure_year,
            "url_document": reverse(
                "contentdocument_highlighted",
                kwargs={
                    "document_rag_id": instance.id,
                },
            ),
        }
        return representation
