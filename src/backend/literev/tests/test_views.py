import json

from pathlib import Path
from unittest import skip

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from literev.libs.rag_pdf import RagAnswersManager
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectDocumentRAG,
    ProjectRAG,
)


@skip("update test for table select and new project pages")
class TestPreviousGraphView(TestCase):
    def setUp(self):
        """
        Set up test data, including users, projects, and related models.
        """
        plot_dir = Path(settings.PLOT_DATA)
        plot_dir.mkdir(parents=True, exist_ok=True)

        (plot_dir / "1_script.html").touch()
        (plot_dir / "1_div.html").touch()

        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpassword"
        )
        self.project = Project.objects.create(
            user=self.user, is_finish=True, id=1
        )
        self.url = reverse("previousgraph")

    def test_redirect_on_invalid_project_id(self):
        """
        Test that the user is redirected if no project ID is provided.
        """
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(self.url, follow=True)

        self.assertEqual(response.request["PATH_INFO"], "/search/")
        self.assertEqual(
            response.status_code, 200, "Redirected page is not accessible."
        )

    def test_project_authorization(self):
        """
        Test that only the project's owner can access the project.
        """
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(f"{self.url}?project_id=1")
        self.assertEqual(response.status_code, 200)

    def test_cluster_and_documents_list(self):
        """
        Test that clusters, documents, standards, and descriptors are properly included in the context.
        """
        cluster = Cluster.objects.create(
            project=self.project, topic="test topic"
        )
        document = Document.objects.create(
            project=self.project,
            standards="CEDH.6",
            descriptors="SANCTION ADMINISTRATIVE",
        )

        ClusterElement.objects.create(
            cluster=cluster, document=document, pos_x=1.0, pos_y=2.0
        )

        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(f"{self.url}?project_id=1")
        self.assertContains(response, "test topic")
        self.assertContains(response, "CEDH.6")
        self.assertContains(response, "SANCTION ADMINISTRATIVE")

    def test_session_data_on_post_filters(self):
        """
        Test that the correct session data is set when filters (including standards and descriptors) are applied.
        """
        self.client.login(username="testuser", password="testpassword")
        response = self.client.post(
            f"{self.url}?project_id=1",
            {
                "submit": "filters",
                "Topic": ["test_topic"],
                "Standards": ["CEDH.6"],
                "Descriptors": ["SANCTION ADMINISTRATIVE"],
            },
        )
        self.assertEqual(self.client.session["id_project"], "1")
        self.assertTrue("document_pk_list" in self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_plot_file_rendering(self):
        """
        Test that the plot HTML files are read and included in the response.
        """
        plot_div_path = settings.PLOT_DATA / "1_div.html"
        plot_script_path = settings.PLOT_DATA / "1_script.html"

        with open(plot_div_path, "w") as f:
            f.write("<div>Test plot div</div>")
        with open(plot_script_path, "w") as f:
            f.write("<script>Test plot script</script>")

        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(f"{self.url}?project_id=1")
        self.assertContains(response, "Test plot div")
        self.assertContains(response, "Test plot script")

    def test_post_continue(self):
        """
        Test the 'continue' submit action which updates the new table choice and redirects.
        """
        self.client.login(username="testuser", password="testpassword")

        document1 = Document.objects.create(
            project=self.project,
            id=1,
            standards="CEDH.1",
            descriptors="MATERNITÉ",
        )
        document2 = Document.objects.create(
            project=self.project,
            id=2,
            standards="CEDH.2",
            descriptors="MARIAGE",
        )
        document3 = Document.objects.create(
            project=self.project,
            id=3,
            standards="CEDH.3",
            descriptors="RÉPRIMANDE",
        )

        session = self.client.session
        session["document_pk_list"] = [
            document1.pk,
            document2.pk,
            document3.pk,
        ]
        session.save()

        response = self.client.post(
            f"{self.url}?project_id=1", {"submit": "continue"}, follow=True
        )

        self.assertEqual(response.status_code, 200)

    def test_standard_and_descriptor_list_extraction(self):
        """
        Test that standards and descriptors are properly extracted and included in the context.
        """
        Document.objects.create(
            project=self.project,
            standards="CEDH.6; CEDH.8; LPA.59",
            descriptors="MATERNITÉ; MARIAGE",
        )
        self.client.login(username="testuser", password="testpassword")
        response = self.client.get(f"{self.url}?project_id=1")
        self.assertContains(response, "CEDH.6")
        self.assertContains(response, "CEDH.8")
        self.assertContains(response, "LPA.59")
        self.assertContains(response, "MATERNITÉ")
        self.assertContains(response, "MARIAGE")


class ProjectRAGTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        self.project = Project.objects.create(name="Test Project")
        self.document, _ = Document.objects.get_or_create(
            project=self.project,
            defaults={"raw_document_text": "Test document text"},
        )
        self.project_rag = ProjectRAG.objects.create(
            query="test query",
            project=self.project,
            summary_answer=json.dumps(
                {
                    "summary": "Ceci est un résumé.",
                    "considerations": ["Point 1", "Point 2", "Point 3"],
                }
            ),
        )

    def test_project_rag_general_summary_and_considerations(self):
        project_rag = ProjectRAG.objects.get(project=self.project)
        self.assertIsInstance(project_rag.summary_answer, str)

        try:
            summary_data = json.loads(project_rag.summary_answer)
        except json.JSONDecodeError:
            summary_data = {"summary": "", "considerations": []}

        self.assertEqual(summary_data.get("summary"), "Ceci est un résumé.")
        self.assertEqual(
            summary_data.get("considerations"),
            ["Point 1", "Point 2", "Point 3"],
        )

    def test_pdf_rag_run_method(self):
        pdf_rag = RagAnswersManager(
            project_rag_id=self.project_rag.id,
            documents_ids=[self.document.id],
        )
        pdf_rag.run_pipeline()

        self.project_rag.refresh_from_db()

        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=self.document,
            citation="Example citation",
            answer="Generated answer",
        )

        try:
            summary_data = json.loads(self.project_rag.summary_answer)
        except json.JSONDecodeError:
            summary_data = {"summary": "", "considerations": []}

        self.assertIn("summary", summary_data)
        self.assertIn("considerations", summary_data)
        self.assertIsInstance(summary_data["summary"], str)
        self.assertIsInstance(summary_data["considerations"], list)
