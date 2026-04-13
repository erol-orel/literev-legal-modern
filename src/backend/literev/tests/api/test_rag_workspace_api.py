from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from literev.models import (
    Document,
    Project,
    ProjectDocumentRAG,
    ProjectRAG,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
)


class RagWorkspaceApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="rag-user",
            email="rag@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            user=self.user,
            name="RAG Project",
            query='"housing"',
            range_begin_date="2020-01-01",
            range_end_date="2020-12-31",
            total_documents=1,
            selected_indices=["chambre_administrative"],
            step="plotting",
            step_number=0,
            is_finish=True,
            natural_language_query="What is the ruling?",
        )
        self.refinement = ProjectRefinement.objects.create(
            project=self.project,
            owner=self.user,
            name="Refinement",
        )
        self.iteration = RefinementIteration.objects.create(
            refinement=self.refinement,
            number_documents=1,
            checked_documents_ids=[],
            excluded_documents_ids=[],
            new_neighbors_ids=[],
            result_documents_ids=[],
        )
        self.document = Document.objects.create(
            project=self.project,
            decision_type="Decision",
            procedure_type="Appeal",
            raw_document_text="Document body",
            decision_date="2020-01-01",
        )
        TableChoice.objects.create(
            user=self.user,
            project=self.project,
            document=self.document,
            is_check=True,
        )
        self.project_rag = ProjectRAG.objects.create(
            project=self.project,
            query="What is the ruling?",
            status="completed",
            summary_answer=json.dumps(
                {
                    "summary": "Summary text",
                    "considerations": [
                        {
                            "text": "Consideration",
                            "frequency": 1,
                            "percent": 50,
                            "procedure_types": ["Appeal"],
                        }
                    ],
                }
            ),
            num_documents=1,
            valid_answer_count=1,
        )
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=self.document,
            citation="Citation",
            answer="Answer",
        )

    def test_rag_context_endpoint_returns_payload(self) -> None:
        response = self.client.get(
            reverse("api-rag-context", args=[self.project.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["project"]["id"], self.project.id)
        self.assertEqual(payload["number_documents"], 1)
        self.assertEqual(payload["refinement"]["id"], self.refinement.id)

    def test_rag_context_detail_includes_current_rag(self) -> None:
        response = self.client.get(
            reverse(
                "api-rag-context-detail",
                args=[self.project.id, self.project_rag.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["current"]["id"], self.project_rag.id)
        self.assertEqual(payload["current"]["summary_text"], "Summary text")

    def test_rag_delete_endpoint_removes_entry(self) -> None:
        response = self.client.delete(
            reverse(
                "api-rag-delete",
                args=[self.project.id, self.project_rag.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            ProjectRAG.objects.filter(id=self.project_rag.id).exists()
        )
