from __future__ import annotations

from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectRefinement,
)


class ProjectOverviewApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="overview-user",
            email="overview@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            user=self.user,
            name="Overview Project",
            query='"housing"',
            natural_language_query="What are the housing rights?",
            range_begin_date="2020-01-01",
            range_end_date="2020-12-31",
            total_documents=2,
            selected_indices=["chambre_administrative"],
            step="plotting",
            is_finish=True,
            is_running=False,
            best_dbcv=0.412,
        )
        self.cluster = Cluster.objects.create(
            project=self.project,
            order=1,
            topic="housing, rights, tenancy, contract, eviction",
            summary="",
        )
        self.document = Document.objects.create(
            project=self.project,
            raw_document_id="DOC-001",
            procedure_type="Appeal",
            decision_type="Decision",
            result="ADMIS",
            standards="CEDH.6",
            descriptors="Housing",
            prepared_for_ngrams="housing rights contract",
            decision_date="2020-03-10",
        )
        ClusterElement.objects.create(
            cluster=self.cluster,
            document=self.document,
            pos_x=1.0,
            pos_y=1.0,
        )
        self.refinement = ProjectRefinement.objects.create(
            project=self.project,
            owner=self.user,
            name="Initial refinement",
            filters='{"filter-union-0": {"Keyword": ["housing"]}}',
        )

    def test_project_overview_endpoint_returns_project_payload(self) -> None:
        response = self.client.get(
            reverse("api-project-overview", args=[self.project.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["project"]["name"], "Overview Project")
        self.assertEqual(payload["project"]["processed_documents"], 1)
        self.assertEqual(
            payload["cluster_summaries"][0]["cluster_id"],
            self.cluster.id,
        )
        self.assertEqual(payload["refinements"][0]["id"], self.refinement.id)
        self.assertEqual(
            payload["filters"]["refinement_limit"],
            settings.LIMIT_NUMBER_REFINEMENTS,
        )

    def test_project_filter_preview_endpoint_counts_documents(self) -> None:
        response = self.client.post(
            reverse("api-project-filter-preview", args=[self.project.id]),
            {"filters": {"filter-union-0": {"Keyword": ["housing"]}}},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["number_documents"], 1)

    @patch("literev.libs.project_overview.create_iteration")
    @patch("literev.libs.project_overview.update_new_table_choice")
    def test_project_refinement_creation_endpoint_creates_refinement(
        self,
        mocked_update_new_table_choice,
        mocked_create_iteration,
    ) -> None:
        response = self.client.post(
            reverse("api-project-refinements", args=[self.project.id]),
            {
                "filters": {"filter-union-0": {"Keyword": ["housing"]}},
                "refinement_name": "Housing only",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.json()["number_documents"], 1)
        self.assertTrue(
            ProjectRefinement.objects.filter(
                project=self.project,
                owner=self.user,
                name__startswith="Housing only",
            ).exists()
        )
        mocked_update_new_table_choice.assert_called_once()
        mocked_create_iteration.assert_called_once()

    def test_project_refinement_delete_endpoint_removes_refinement(
        self,
    ) -> None:
        response = self.client.delete(
            reverse(
                "api-project-refinement-detail",
                args=[self.project.id, self.refinement.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            ProjectRefinement.objects.filter(id=self.refinement.id).exists()
        )

    @patch("literev.libs.nlp.nlp_topic_description")
    def test_project_cluster_summary_endpoint_generates_summary(
        self,
        mocked_nlp_topic_description,
    ) -> None:
        mocked_nlp_topic_description.return_value = "Generated project summary"

        response = self.client.post(
            reverse(
                "api-project-cluster-summary",
                args=[self.project.id, self.cluster.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cluster.refresh_from_db()
        self.assertEqual(self.cluster.summary, "Generated project summary")
        self.assertEqual(
            response.json()["cluster"]["summary_text"],
            "Generated project summary",
        )

    @patch("literev.libs.project_overview.create_tablechoice_rag_iteration")
    def test_project_ask_top_documents_endpoint_redirects_to_rag(
        self,
        mocked_create_tablechoice_rag_iteration,
    ) -> None:
        response = self.client.post(
            reverse("api-project-ask-top-docs", args=[self.project.id])
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["urls"]["rag"],
            reverse("project-rag-page", args=[self.project.id]),
        )
        mocked_create_tablechoice_rag_iteration.assert_called_once_with(
            self.user,
            self.project,
        )
