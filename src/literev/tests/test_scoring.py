import asyncio

from functools import wraps
from pathlib import Path
from unittest import TestCase as UnitTestCase
from unittest import skip

import joblib
import openai
import pandas as pd

from django.conf import settings
from django.test import TestCase, TransactionTestCase, override_settings

from literev.libs.scoring import (
    assign_faithfulnesswithHHEM_scores,
    assign_similarity_scores,
    extract_keywords,
    get_dataframe_project,
    get_faithfulnesswithHHEM_score,
    get_most_similar_keywords,
    get_similarity_score_phrases,
    get_topic_and_hdbscan_score,
    sort_by_es_score,
    sort_by_keyword_score,
    sort_documents_by_es_score,
)
from literev.libs.table_choice import render_table_choice, sort_table_choice
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectDocumentRAG,
    ProjectRAG,
    TableChoice,
)

DATA_PATH = Path(__file__).parent / "sample_test"

DATA_DOC = Path(__file__).parent / "data"


def skip_on(exception, reason="Default"):
    def decorator_function(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Try to run the test
                return func(*args, **kwargs)
            except exception:
                # If exception of given type happens, absorb it
                # and raise pytest.Skip with given reason
                UnitTestCase.skipTest(func, reason)

        return wrapper

    return decorator_function


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
            self.hdbscan_scores, self.project, self.tablechoice
        )
        sample_id = 1473
        expected_hdbscan_score = 0.8610864867390485 * 100
        expected_topic = "Topic 2 : topic 2"

        result = dict_topic_scores[sample_id]

        self.assertEqual(result["topic"], expected_topic)
        self.assertEqual(result["hdbscan_score"], expected_hdbscan_score)

    @skip("skipping because the functions is not enabled in the workflow")
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

    @skip("skipping because the functions is not enabled in the workflow")
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

    def test_sort_by_es_score(self):
        """Test sorting by elasticsearch score"""
        result = sort_by_es_score(self.project, self.tablechoice)

        first_tablechoice = result[0]
        last_tablechoice = result[-1]

        self.assertEqual(first_tablechoice.document.id, 1474)
        self.assertEqual(last_tablechoice.document.id, 1454)

    def test_sort_documents_by_es_score(self):
        documents = Document.objects.filter(project=self.project)
        expected_first_doc_id = 1474
        expected_last_document_id = 1454

        sorted_list_docs = sort_documents_by_es_score(self.project, documents)

        self.assertEqual(sorted_list_docs[0].id, expected_first_doc_id)
        self.assertEqual(sorted_list_docs[-1].id, expected_last_document_id)


class ScoringRAGAnwersTest(TestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            name="test project",
            query="etest query",
        )
        self.project_rag = ProjectRAG.objects.create(
            project=self.project,
            query="Quel est la vitesse dépassée ?",
        )

        with open(DATA_DOC / "rag_answers.txt", "r") as f:
            rag_answers = f.read().split("\n\n")

        with open(DATA_DOC / "rag_citation.txt", "r") as f:
            rag_citations = f.read().split("\n\n")

        for i in range(7):
            document = Document.objects.create(
                project=self.project,
                raw_document_text=rag_citations[i],
            )
            ProjectDocumentRAG.objects.create(
                project_rag=self.project_rag,
                document=document,
                citation=rag_citations[i],
                answer=rag_answers[i],
            )

    def test_similarity_phrases(self):
        string_A = "The hamburger is cooked in the kitchen"
        string_B = "The pizza is made in a restaurant"
        expected = 0.8501040217284543
        result = get_similarity_score_phrases(string_A, string_B)

        self.assertEqual(expected, result)

    def test_asigning_confidence_scores(self):
        expected_score_0 = 0.6886859583329661
        expected_score_1 = 0.2840474803546656
        assign_similarity_scores(self.project_rag)
        rag_documents = ProjectDocumentRAG.objects.filter(
            project_rag=self.project_rag
        )

        first_rag_doc = rag_documents.first()
        last_rag_doc = rag_documents.last()

        self.assertEqual(expected_score_0, first_rag_doc.confidence_score)
        self.assertEqual(expected_score_1, last_rag_doc.confidence_score)


class ScoringFaithfulnessRAGAnwersTest(TransactionTestCase):
    def setUp(self) -> None:
        self.project = Project.objects.create(
            name="test project",
            query="test query for ragas",
        )
        self.project_rag = ProjectRAG.objects.create(
            project=self.project,
            query="Quel est la vitesse dépassée ?",
        )

        with open(DATA_DOC / "rag_answers.txt", "r") as f:
            rag_answers = f.read().split("\n\n")

        with open(DATA_DOC / "rag_citation.txt", "r") as f:
            rag_citations = f.read().split("\n\n")

        # create two documents_rag
        first_document = Document.objects.create(
            project=self.project,
            raw_document_text=rag_citations[2],
        )
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=first_document,
            citation=rag_citations[2],
            answer=rag_answers[2],
        )

        last_document = Document.objects.create(
            project=self.project,
            raw_document_text=rag_citations[5],
        )
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=last_document,
            citation=rag_citations[5],
            answer=rag_answers[5],
        )

    @skip_on(openai.RateLimitError, reason="API returns quota exceeded")
    def test_assign_faithfulness_scores(self):
        expected_score_0 = 1.00
        expected_score_1 = 0.00
        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            assign_faithfulnesswithHHEM_scores(self.project_rag)
        )

        rag_documents = ProjectDocumentRAG.objects.filter(
            project_rag=self.project_rag
        )

        first_rag_doc = rag_documents.first()
        last_rag_doc = rag_documents.last()

        self.assertEqual(expected_score_0, first_rag_doc.confidence_score)
        self.assertEqual(expected_score_1, last_rag_doc.confidence_score)

    @skip_on(openai.RateLimitError, reason="API returns quota exceeded")
    async def test_get_faithfulness_score(self):
        query = "Where and when was Einstein born?"
        faithfulness_response = (
            "Einstein was born in Germany on 14th March 1879."
        )
        context = (
            "Albert Einstein (born 14 March 1879) was a German-born theoretical physicist, "
            "widely held to be one of the greatest and most influential scientists of all time"
        )
        result_faithfulness_score = await get_faithfulnesswithHHEM_score(
            query, faithfulness_response, context
        )

        low_faithfulness_response = (
            "Einstein was born in Germany on 20th March 1879."
        )

        faithfulness_expected_score = 1.0
        low_faithfulness_expected_score = 0.5

        self.assertEqual(
            result_faithfulness_score, faithfulness_expected_score
        )

        result_low_faithfulness_score = await get_faithfulnesswithHHEM_score(
            query, low_faithfulness_response, context
        )

        self.assertEqual(
            result_low_faithfulness_score, low_faithfulness_expected_score
        )
