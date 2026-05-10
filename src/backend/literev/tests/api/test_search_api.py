from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from literev.models import Project


class SearchApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="search-user",
            email="search@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=self.user)
        self.payload = {
            "project_name": "Housing rights",
            "selected_indices": ["chambre_administrative"],
            "natural_language_query": "",
            "query": '"contrat" AND "résiliation"',
            "range_begin_date": "2020-01-01",
            "range_end_date": "2020-12-31",
        }

    def test_validate_endpoint_returns_normalized_payload(self) -> None:
        response = self.client.post(
            reverse("api-search-validate"),
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["project_name"], "Housing rights")
        self.assertEqual(
            response.json()["selected_indices"],
            ["chambre_administrative"],
        )
        self.assertEqual(response.json()["range_begin_date"], "2020-01-01")

    @patch("literev.libs.search.get_number_documents", return_value=21)
    def test_preview_endpoint_returns_document_count(
        self,
        mocked_get_number_documents,
    ) -> None:
        payload = {
            **self.payload,
            "selected_indices": [
                "chambre_administrative",
                "chambre_penale",
            ],
        }
        response = self.client.post(
            reverse("api-search-preview"),
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total_documents"], 42)
        self.assertTrue(response.json()["can_continue"])
        self.assertEqual(mocked_get_number_documents.call_count, 2)

    @patch("literev.libs.search.launch_process", return_value=True)
    @patch("literev.libs.search.get_number_documents", return_value=13)
    def test_project_creation_endpoint_creates_and_launches_project(
        self,
        mocked_get_number_documents,
        mocked_launch_process,
    ) -> None:
        response = self.client.post(
            reverse("api-search-projects"),
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Project.objects.count(), 1)

        project = Project.objects.get()
        self.assertEqual(project.user, self.user)
        self.assertEqual(project.name, "Housing rights")
        self.assertEqual(project.total_documents, 13)
        self.assertEqual(project.selected_indices, ["chambre_administrative"])
        self.assertEqual(
            response.json()["urls"]["running"], reverse("running")
        )
        mocked_get_number_documents.assert_called_once()
        mocked_launch_process.assert_called_once_with(project)

    def test_preview_endpoint_returns_validation_errors(self) -> None:
        response = self.client.post(
            reverse("api-search-preview"),
            {
                **self.payload,
                "range_begin_date": "2020-12-31",
                "range_end_date": "2020-01-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Please provide an ending date equal to or more recent",
            str(response.json()),
        )

    @patch("literev.libs.search.get_number_documents", return_value=0)
    def test_project_creation_requires_matching_documents(
        self,
        mocked_get_number_documents,
    ) -> None:
        response = self.client.post(
            reverse("api-search-projects"),
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json()["detail"],
            "No documents were found for this query.",
        )
        self.assertEqual(Project.objects.count(), 0)
        mocked_get_number_documents.assert_called_once()

    @override_settings(
        HACTAR_BOOLEAN_QUERY_MODEL="test-model",
        HACTAR_BASE_URL="http://hactar.local",
        HACTAR_API_KEY="test-key",
    )
    @patch(
        "literev.api.search.convert_nl_to_boolean",
        return_value='"contrat" AND "résiliation"',
    )
    def test_convert_query_endpoint_returns_boolean_query(
        self,
        mocked_convert_nl_to_boolean,
    ) -> None:
        response = self.client.post(
            reverse("api-search-convert-query"),
            {"natural_language_query": "Quels sont les droits du locataire ?"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["query"],
            '"contrat" AND "résiliation"',
        )
        mocked_convert_nl_to_boolean.assert_called_once_with(
            "Quels sont les droits du locataire ?",
            model_name="openai/test-model",
            base_url="http://hactar.local/api",
            api_key="test-key",
        )
