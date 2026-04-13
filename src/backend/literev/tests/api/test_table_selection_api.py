from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from literev.models import (
    Document,
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
)


class TableSelectionApiTests(APITestCase):
    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="tableselect-user",
            email="tableselect@example.com",
            password="secure-password",
        )
        self.client.force_authenticate(user=self.user)

        self.project = Project.objects.create(
            user=self.user,
            name="Table Selection Project",
            query='"housing"',
            range_begin_date="2020-01-01",
            range_end_date="2020-12-31",
            total_documents=2,
            selected_indices=["chambre_administrative"],
            step="plotting",
            step_number=0,
            is_finish=True,
        )
        self.refinement = ProjectRefinement.objects.create(
            project=self.project,
            owner=self.user,
            name="Selection refinement",
            filters={"filter-union-0": {"Keyword": ["housing"]}},
        )
        self.document_1 = Document.objects.create(
            project=self.project,
            decision_type="Decision 1",
            procedure_type="Appeal",
            raw_document_text="Housing contract sample one.",
            decision_date="2020-01-03",
        )
        self.document_2 = Document.objects.create(
            project=self.project,
            decision_type="Decision 2",
            procedure_type="Appeal",
            raw_document_text="Housing contract sample two.",
            decision_date="2020-01-05",
        )
        self.iteration_1 = RefinementIteration.objects.create(
            refinement=self.refinement,
            number_documents=2,
            checked_documents_ids=[self.document_1.id],
            excluded_documents_ids=[],
            new_neighbors_ids=[],
            result_documents_ids=[self.document_1.id, self.document_2.id],
        )
        self.iteration_2 = RefinementIteration.objects.create(
            refinement=self.refinement,
            parent_iteration=self.iteration_1,
            number_documents=2,
            checked_documents_ids=[self.document_2.id],
            excluded_documents_ids=[],
            new_neighbors_ids=[],
            result_documents_ids=[self.document_1.id, self.document_2.id],
        )
        self.table_choice_1 = TableChoice.objects.create(
            user=self.user,
            project=self.project,
            document=self.document_1,
            is_check=True,
        )
        self.table_choice_2 = TableChoice.objects.create(
            user=self.user,
            project=self.project,
            document=self.document_2,
            is_check=None,
        )

    def test_state_endpoint_returns_workspace_payload(self) -> None:
        response = self.client.get(
            reverse(
                "api-tableselect-state",
                args=[self.project.id, self.refinement.id],
            ),
            {
                "iteration_id": self.iteration_1.id,
                "page": 1,
                "order_by": "decision_date",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        self.assertEqual(payload["project"]["name"], "Table Selection Project")
        self.assertEqual(payload["current_iteration_id"], self.iteration_1.id)
        self.assertEqual(payload["table"]["current_page"], 1)
        self.assertEqual(len(payload["table"]["rows"]), 2)
        self.assertEqual(
            payload["filters"]["union_sets_html"], "(Keyword: housing)"
        )

    def test_selection_endpoint_updates_table_choices(self) -> None:
        response = self.client.put(
            reverse(
                "api-tableselect-selection",
                args=[self.project.id, self.refinement.id],
            ),
            {
                "iteration_id": self.iteration_1.id,
                "selected_documents": [self.table_choice_2.id],
                "deselected_documents": [self.table_choice_1.id],
                "maybe_documents": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.table_choice_1.refresh_from_db()
        self.table_choice_2.refresh_from_db()
        self.iteration_1.refresh_from_db()
        self.assertFalse(self.table_choice_1.is_check)
        self.assertTrue(self.table_choice_2.is_check)
        self.assertEqual(
            self.iteration_1.checked_documents_ids, [self.document_2.id]
        )

    def test_activate_iteration_endpoint_reloads_tablechoice_state(
        self,
    ) -> None:
        response = self.client.post(
            reverse(
                "api-tableselect-iteration-activate",
                args=[
                    self.project.id,
                    self.refinement.id,
                    self.iteration_2.id,
                ],
            ),
            {"order_by": "decision_date"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        selected_document_ids = list(
            TableChoice.objects.filter(
                project=self.project, user=self.user, is_check=True
            ).values_list("document_id", flat=True)
        )
        self.assertEqual(selected_document_ids, [self.document_2.id])
        self.assertIn(
            f"/tableselect/{self.project.id}/{self.refinement.id}/{self.iteration_2.id}/page=1/order_by=decision_date/",
            response.json()["url"],
        )

    @patch("literev.libs.table_selection.iterate_check_list")
    def test_iterate_endpoint_starts_processing(
        self, mocked_iterate_check_list
    ) -> None:
        response = self.client.post(
            reverse(
                "api-tableselect-iterate",
                args=[self.project.id, self.refinement.id],
            ),
            {
                "iteration_id": self.iteration_1.id,
                "selected_documents": [self.table_choice_1.id],
                "deselected_documents": [self.table_choice_2.id],
                "maybe_documents": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["url"],
            f"/tableselect/{self.project.id}/{self.refinement.id}/",
        )
        mocked_iterate_check_list.assert_called_once_with(
            self.user,
            self.project,
            self.refinement.id,
            self.iteration_1.id,
        )

    def test_ask_selected_endpoint_returns_rag_url(self) -> None:
        response = self.client.post(
            reverse(
                "api-tableselect-ask-selected",
                args=[self.project.id, self.refinement.id],
            ),
            {
                "iteration_id": self.iteration_1.id,
                "selected_documents": [self.table_choice_1.id],
                "deselected_documents": [self.table_choice_2.id],
                "maybe_documents": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["url"],
            reverse("project-rag-page", args=[self.project.id]),
        )
