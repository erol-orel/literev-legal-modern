from __future__ import annotations

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from literev.models import Document, Project, ProjectDocumentRAG, ProjectRAG


class DocumentContentApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="doc-user",
            email="doc-user@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            user=self.user,
            name="Doc Project",
            query='"housing"',
            range_begin_date="2020-01-01",
            range_end_date="2020-12-31",
            total_documents=1,
            selected_indices=["chambre_administrative"],
            step="plotting",
            step_number=0,
            is_finish=True,
        )
        self.document = Document.objects.create(
            project=self.project,
            decision_type="Decision",
            procedure_type="Appeal",
            raw_document_text="This is a sentence. Another sentence.",
            document_html_text="<p>HTML document</p>",
            decision_date="2020-01-01",
        )
        self.project_rag = ProjectRAG.objects.create(
            project=self.project,
            query="What is the ruling?",
            status="completed",
        )
        self.document_rag = ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=self.document,
            citation="This is a sentence.",
            citation_context={
                "Mineure-Faits": ["This is a sentence."],
                "Mineure-Subsommation": [],
            },
            answer="Answer",
        )

    def test_document_content_endpoint_returns_payload(self) -> None:
        response = self.client.get(
            reverse("api-document-content", args=[self.document.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["document"]["id"], self.document.id)
        self.assertEqual(
            payload["content"]["html_text"], "<p>HTML document</p>"
        )
        self.assertEqual(
            payload["content"]["raw_text"],
            "This is a sentence. Another sentence.",
        )

    def test_highlighted_document_endpoint_returns_payload(self) -> None:
        response = self.client.get(
            reverse(
                "api-document-content-highlighted",
                args=[self.document_rag.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["document"]["id"], self.document.id)
        self.assertIn(
            "background-color", payload["content"]["highlighted_text"]
        )
