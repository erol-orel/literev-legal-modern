from django.contrib.auth.models import User
from django.test import TestCase

from literev.libs.historical_functions import (
    filter_and_sort_projects,
    get_projects_list,
    sort_all_projects,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
)


class HistoricalTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create(username="user_test", password="test")
        keywords = ["water", "water", "bible", "air", "sky"]
        for i, keyword in zip(range(31, 36), keywords):
            Project.objects.create(
                id=i,
                user=self.user,
                name=f"test project {i}",
                query=f"query {i}: {keyword}",
                is_finish=True,
            )

        project_1 = Project.objects.filter(id=31).first()
        cluster_1 = Cluster.objects.create(project=project_1)

        project_2 = Project.objects.filter(id=32).first()
        cluster_2 = Cluster.objects.create(project=project_2)

        for j in range(3):
            document = Document.objects.create(
                project=project_1,
                raw_document_text=f"content document {project_1.name} document {j}",
            )
            ClusterElement.objects.create(
                pos_x=j,
                pos_y=j,
                document=document,
                cluster=cluster_1,
            )

        for j in range(2):
            document = Document.objects.create(
                project=project_2,
                raw_document_text=f"content document {project_1.name} document {j}",
            )
            ClusterElement.objects.create(
                pos_x=j * 2,
                pos_y=j * 2,
                document=document,
                cluster=cluster_2,
            )

    def test_get_project_list(self):
        """Check if it is sorted accoring to the list."""
        id_list = [35, 33, 31, 34, 32]
        sorted_projects = get_projects_list(id_list)
        for id_project, project in zip(id_list, sorted_projects):
            self.assertEqual(project.id, id_project)

    def test_filter_and_sort_projects(self):
        """Check filtering by keywords and sorting"""
        keywords = ["water"]
        sorted_list = filter_and_sort_projects(
            self.user, keywords, "more_documents_first"
        )
        first_project = sorted_list.first()
        last_project = sorted_list.last()
        self.assertEqual(first_project.id, 31)
        self.assertEqual(last_project.id, 32)

        sorted_list_reverse = filter_and_sort_projects(
            self.user, keywords, "less_documents_first"
        )

        first_project_reverse = sorted_list_reverse.first()
        last_project_reverse = sorted_list_reverse.last()

        self.assertEqual(first_project_reverse.id, 32)
        self.assertEqual(last_project_reverse.id, 31)

    def test_sort_all_projects(self):
        sorted_list = sort_all_projects(self.user, "more_documents_first")
        first_project = sorted_list.first()
        expected_total_documents = 5
        self.assertEqual(first_project.id, 31)
        self.assertEqual(len(sorted_list), expected_total_documents)

        sorted_list_reverse = sort_all_projects(
            self.user, "less_documents_first"
        )

        last_project_reverse = sorted_list_reverse.last()
        expected_total_documents_reverse = 5
        self.assertEqual(
            len(sorted_list_reverse), expected_total_documents_reverse
        )
        self.assertEqual(last_project_reverse.id, 31)
