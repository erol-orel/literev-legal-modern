from pathlib import Path

import joblib
import pandas as pd

from django.conf import settings
from django.test import TestCase, override_settings

from literev.libs.scoring import (
    extract_keywords,
    get_dataframe_project,
    get_most_similar_keywords,
    get_topic_and_hdbscan_score,
    sort_by_keyword_score,
)
from literev.libs.table_choice import render_table_choice, sort_table_choice
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    TableChoice,
)

DATA_PATH = Path(__file__).parent / "sample_test"

@override_settings(ARTICLE_DATA=DATA_PATH)
class ScoringTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            id=30,
            name="test project",
            query="europe and paris not (trainer or pitbull)",
        )

        cluster_1 = Cluster.objects.create(
            project=self.project,
            order=1,
            topic="topic 1",
        )
        cluster_2 = Cluster.objects.create(
            project=self.project,
            order=2,
            topic="topic 2",
        )

        hdbscan_scores = joblib.load(
            settings.ARTICLE_DATA
            / f"hdbscan_scores_project_{self.project.id}.pkl"
        )

        list_id_docs = joblib.load(
            settings.ARTICLE_DATA / f"id_list_project_{self.project.id}.pkl"
        )

        for id_doc in list_id_docs:
            document = Document.objects.create(
                id=id_doc,
                project=self.project,
                raw_document_text=f"document text {id_doc}",
            )

            ClusterElement.objects.create(
                pos_x=0.0,
                pos_y=0.0,
                document=document,
                cluster=cluster_1 if int(id_doc) % 2 == 0 else cluster_2,
            )
            TableChoice.objects.create(
                project=self.project,
                document=document,
            )

        tablechoice = TableChoice.objects.filter(
            project=self.project, to_display=True
        )

        self.tablechoice = tablechoice

        self.hdbscan_scores = hdbscan_scores

    def test_extract_keywords(self):
        """Test to extract keywords"""
        data = "europe and paris not (trainer or pitbull)"
        expected = ["europe", "paris", "trainer", "pitbull"]

        result = extract_keywords(data)

        self.assertEqual(set(expected), set(result))

    def test_get_most_similar_keywords(self):
        """Test get similar keywords"""

        query_keywords = ["fils", "divorce"]

        columns_name = joblib.load(
            settings.ARTICLE_DATA
            / f"column_name_project_{self.project.id}.pkl"
        )

        expected = ["cousin_neveu", "divorcer", "neveu", "frère"]

        result = get_most_similar_keywords(query_keywords, columns_name)

        self.assertEqual(set(expected), set(result))


    def test_get_dataframe_project(self):
        """Test get dataframe tfidf"""
        df = get_dataframe_project(self.project)

        self.assertTrue(isinstance(df, pd.core.frame.DataFrame))

    def test_sort_by_keyword_score(self):
        """Test sorting by keyword score"""
        tablechoice_list = sort_by_keyword_score(
            self.project, self.tablechoice, "neveu"
        )

        # check the first element and last element and result length
        first_table_id = 1452
        last_table_id = 1459
        total_tablechoice = 53

        self.assertEqual(first_table_id, tablechoice_list[0].document.id)
        self.assertEqual(last_table_id, tablechoice_list[-1].document.id)
        self.assertEqual(len(tablechoice_list), total_tablechoice)

    def test_get_topic_and_hdbscan_score(self):
        """Test get topic and hdbscan score"""
        dict_topic_scores = get_topic_and_hdbscan_score(
            self.hdbscan_scores, self.project
        )
        sample_id = 1473
        expected_hdbscan_score = 0.8610864867390485
        expected_topic = "topic 2"

        result = dict_topic_scores[sample_id]

        self.assertEqual(result["topic"], expected_topic)
        self.assertEqual(result["hdbscan_score"], expected_hdbscan_score)

    def test_render_table_choice(self):
        """Test render tablechoice generation"""
        render_list, has_scores = render_table_choice(
            self.project, self.tablechoice, "divorcer"
        )

        self.assertTrue(has_scores)
        first_result = render_list[0]
        last_result = render_list[-1]

        self.assertEqual(first_result["document_pk"], 1472)
        self.assertEqual(first_result["sample_document"], "document text 1472")
        self.assertEqual(first_result["topic"], "topic 1")

        self.assertEqual(last_result["document_pk"], 1455)
        self.assertEqual(last_result["sample_document"], "document text 1455")
        self.assertEqual(last_result["topic"], "topic 2")

    def test_sort_table_choice(self):
        """Test sorting table choice"""
        tablechoice_list = sort_table_choice(
            self.project, self.tablechoice, "cousin_neveu"
        )

        first = tablechoice_list[0]
        last = tablechoice_list[-1]

        self.assertEqual(first.document.id, 1475)
        self.assertEqual(
            first.document.raw_document_text, "document text 1475"
        )

        self.assertEqual(last.document.id, 1459)
        self.assertEqual(last.document.raw_document_text, "document text 1459")
