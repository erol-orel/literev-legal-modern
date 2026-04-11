import logging

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from literev.libs.tableselect_workflows import TableSelectHandler
from literev.models import (
    Document,
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
)

logging.basicConfig(level=logging.INFO)


class TableSelectHandlerTests(TestCase):
    def setUp(self):
        """Set up test data and environment."""
        self.user = User.objects.create_user(
            username="testuser", password="password"
        )
        self.project = Project.objects.create(
            user=self.user,
            name="Test Project",
            creation_date="2025-01-01",
            query="example query",
        )
        self.refinement = ProjectRefinement.objects.create(
            project=self.project,
            owner=self.user,
            name="Test Refinement",
        )
        self.refinement_iteration = RefinementIteration.objects.create(
            refinement=self.refinement,
            number_documents=5,
            checked_documents_ids=[1, 2],
        )
        self.document1 = Document.objects.create(
            project=self.project,
            decision_type="Decision 1",
            decision_date="2025-01-01",
        )
        self.document2 = Document.objects.create(
            project=self.project,
            decision_type="Decision 2",
            decision_date="2025-01-02",
        )
        self.table_choice_1 = TableChoice.objects.create(
            user=self.user,
            project=self.project,
            document=self.document1,
            is_initial=True,
        )
        self.table_choice_2 = TableChoice.objects.create(
            user=self.user,
            project=self.project,
            document=self.document2,
            is_initial=False,
        )
        self.factory = RequestFactory()

    def create_authenticated_request(self, method: str, url: str, data=None):
        """Create an authenticated request."""
        request_method = getattr(self.factory, method)
        request = request_method(url, data=data)
        request.user = self.user
        return request

    def test_validate_id_positive(self):
        """Test _validate_id with valid positive IDs."""
        request = self.create_authenticated_request("get", "/")
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=self.refinement_iteration.id,
            num=1,
            order_by="decision_date",
        )
        self.assertEqual(handler.project_id, self.project.id)

    def test_validate_id_invalid(self):
        """Test _validate_id with invalid ID values."""
        request = self.create_authenticated_request("get", "/")
        with self.assertRaises(ValueError):
            TableSelectHandler(
                request=request,
                project_id=-1,
                refinement_id=self.refinement.id,
                iteration_id=self.refinement_iteration.id,
                num=1,
                order_by="decision_date",
            )

    def test_get_project(self):
        """Test that _get_project returns the correct project."""
        request = self.create_authenticated_request("get", "/")
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=self.refinement_iteration.id,
            num=1,
            order_by="decision_date",
        )
        self.assertEqual(handler.project, self.project)

    def test_get_tablechoice(self):
        """Test that _get_tablechoice returns correct table choices."""
        request = self.create_authenticated_request("get", "/")
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=self.refinement_iteration.id,
            num=1,
            order_by="decision_date",
        )
        self.assertEqual(handler.tablechoice.count(), 2)

    def test_handle_iterate_action(self):
        """Test iteration action behavior."""
        request = self.create_authenticated_request(
            "post",
            "/",
            {
                "submit": "iterate",
                "yes_row": [self.table_choice_1.id],
                "no_row": [],
                "maybe_row": [],
            },
        )
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=self.refinement_iteration.id,
            num=1,
            order_by="decision_date",
        )
        response = handler._handle_iterate_action(
            [self.table_choice_1.id], [], []
        )
        self.assertEqual(response.status_code, 302)

    def test_get_context(self):
        """Test that the context is correctly populated."""
        request = self.create_authenticated_request("get", "/")
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=self.refinement_iteration.id,
            num=1,
            order_by="-es_score",
        )
        context = handler.get_context()
        self.assertIn("tablechoice_list", context)
        self.assertEqual(len(context["tablechoice_list"]), 2)
        self.assertEqual(context["current_page"], 1)
        self.assertEqual(context["sort_by"], "-es_score")

    def test_handle_post_actions_update_order(self):
        """Test POST handling for update order action."""
        request = self.create_authenticated_request(
            "post",
            "/",
            {"submit": "update_order", "update_order_by": "-decision_date"},
        )
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=self.refinement_iteration.id,
            num=1,
            order_by="decision_date",
        )
        response = handler.handle_post_actions()
        self.assertEqual(response.status_code, 302)
        self.assertIn("order_by=-decision_date", response.url)

    def test_get_iteration_redirect(self):
        """Test redirection to the latest iteration."""
        request = self.create_authenticated_request("get", "/")
        handler = TableSelectHandler(
            request=request,
            project_id=self.project.id,
            refinement_id=self.refinement.id,
            iteration_id=-1,
            num=1,
            order_by="decision_date",
        )
        response = handler.get_iteration_redirect()
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            f"/tableselect/{self.project.id}/{self.refinement.id}/{self.refinement_iteration.id}/",
            response.url,
        )
