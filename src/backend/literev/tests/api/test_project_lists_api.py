from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from literev.models import Cluster, ClusterElement, Document, Project


class ProjectListsApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="project-list-user",
            email="project-list@example.com",
            password="secure-password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="other-user",
            email="other@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=self.user)

        self.running_project = Project.objects.create(
            user=self.user,
            name="Running Alpha",
            query='"alpha"',
            total_documents=10,
            step="getting_documents",
            selected_indices=["chambre_administrative"],
        )
        Document.objects.create(project=self.running_project)
        Document.objects.create(project=self.running_project)

        self.shared_running_project = Project.objects.create(
            user=self.other_user,
            name="Shared Running",
            query="#PROCESS-ALL-CORPUS-LITEREV-00",
            total_documents=4,
            step="preparing",
            selected_indices=["chambre_civile"],
        )
        Document.objects.create(
            project=self.shared_running_project,
            prepared_for_ngrams="ready",
        )
        Document.objects.create(
            project=self.shared_running_project,
            prepared_for_ngrams="ready",
        )

        self.historical_project = Project.objects.create(
            user=self.user,
            name="Historical Water",
            query="water rights",
            is_finish=True,
            total_documents=3,
            selected_indices=["chambre_administrative"],
        )
        historical_cluster = Cluster.objects.create(
            project=self.historical_project
        )
        for index in range(3):
            document = Document.objects.create(project=self.historical_project)
            ClusterElement.objects.create(
                cluster=historical_cluster,
                document=document,
                pos_x=index,
                pos_y=index,
            )

        self.historical_project_small = Project.objects.create(
            user=self.user,
            name="Historical Water Small",
            query="water contract",
            is_finish=True,
            total_documents=2,
            selected_indices=["chambre_administrative"],
        )
        small_cluster = Cluster.objects.create(
            project=self.historical_project_small
        )
        for index in range(2):
            document = Document.objects.create(
                project=self.historical_project_small
            )
            ClusterElement.objects.create(
                cluster=small_cluster,
                document=document,
                pos_x=index,
                pos_y=index,
            )

        self.shared_finished_project = Project.objects.create(
            user=self.other_user,
            name="Shared Finished",
            query="#PROCESS-ALL-CORPUS-LITEREV-00",
            is_finish=True,
            total_documents=1,
            selected_indices=["chambre_penale"],
        )
        shared_cluster = Cluster.objects.create(
            project=self.shared_finished_project
        )
        document = Document.objects.create(
            project=self.shared_finished_project
        )
        ClusterElement.objects.create(
            cluster=shared_cluster,
            document=document,
            pos_x=0,
            pos_y=0,
        )

    def test_running_projects_endpoint_lists_accessible_projects(self) -> None:
        response = self.client.get(reverse("api-running-projects"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()["projects"]
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["name"], "Shared Running")
        self.assertFalse(payload[0]["can_delete"])
        self.assertEqual(payload[0]["progress"]["label"], "2/4")
        self.assertEqual(payload[1]["name"], "Running Alpha")
        self.assertTrue(payload[1]["can_delete"])
        self.assertEqual(payload[1]["progress"]["percentage"], 20)

    @patch("literev.libs.project_listing.running_restart")
    def test_running_restart_endpoint_restarts_owned_project(
        self,
        mocked_running_restart,
    ) -> None:
        response = self.client.post(
            reverse(
                "api-running-project-restart",
                args=[self.running_project.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_running_restart.assert_called_once_with(
            str(self.running_project.id)
        )

    def test_running_restart_endpoint_rejects_shared_project(self) -> None:
        response = self.client.post(
            reverse(
                "api-running-project-restart",
                args=[self.shared_running_project.id],
            )
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_historical_projects_endpoint_filters_and_sorts_projects(
        self,
    ) -> None:
        response = self.client.get(
            reverse("api-historical-projects"),
            {"search": "water", "sort_type": "more_documents_first"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["query_filter"], "water")
        self.assertEqual(payload["sort_type"], "more_documents_first")
        self.assertEqual(payload["projects"][0]["name"], "Historical Water")
        self.assertEqual(
            payload["projects"][1]["name"], "Historical Water Small"
        )

    @patch("literev.tasks.running_delete")
    def test_project_delete_endpoint_deletes_owned_project(
        self,
        mocked_running_delete,
    ) -> None:
        response = self.client.delete(
            reverse("api-project-delete", args=[self.historical_project.id])
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        mocked_running_delete.assert_called_once_with(
            self.historical_project.id
        )

    @patch("literev.tasks.remove_all_finished_projects")
    def test_historical_delete_all_endpoint_deletes_owned_finished_projects(
        self,
        mocked_remove_all_finished_projects,
    ) -> None:
        response = self.client.delete(reverse("api-historical-delete-all"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["deleted_count"], 2)
        mocked_remove_all_finished_projects.assert_called_once_with(self.user)
