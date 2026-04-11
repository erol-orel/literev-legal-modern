from pathlib import Path

import joblib

from django.conf import settings
from django.test import TestCase, override_settings

from literev.libs.nlp import get_top_documents_from_cluster
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
)

DATA_PATH = Path(__file__).parent / "sample_test"


@override_settings(ARTICLE_DATA=DATA_PATH)
class NLPTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            id=30,
            name="test project",
            query="europe and paris not (trainer or pitbull)",
        )
        self.cluster = Cluster.objects.create(
            project=self.project,
            topic="test topic",
        )
        list_id_docs = joblib.load(
            settings.ARTICLE_DATA
            / f"id_list_project_{self.cluster.project.id}.pkl"
        )
        for id_doc in list_id_docs:
            document = Document.objects.create(
                id=id_doc,
                project=self.project,
                raw_document_text=f"raw text {id_doc}",
            )
            ClusterElement.objects.create(
                pos_x=0.0,
                pos_y=0.0,
                document=document,
                cluster=self.cluster,
            )

    def test_get_top_docs_from_cluster(self):
        """Test get top docs from cluster"""
        sorted_documents = get_top_documents_from_cluster(self.cluster)
        top_document = sorted_documents[0]
        self.assertEqual(top_document.raw_document_text, "raw text 1496")

        top_10th_document = sorted_documents[-1]
        self.assertEqual(top_10th_document.raw_document_text, "raw text 1459")

        self.assertEqual(len(sorted_documents), 10)
