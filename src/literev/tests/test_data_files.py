from pathlib import Path

import pandas as pd

from django.test import TestCase, override_settings

from literev.libs.data_files import (
    get_dataframe_project,
    load_hdbscan_prob,
    load_tfidf_keywords,
)
from literev.models import (
    Project,
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

    def test_load_tfidf_keywords(self):
        """Test load tfidf_keywords_scores"""
        keywords_list = load_tfidf_keywords(self.project)

        self.assertTrue(isinstance(keywords_list, set))

    def test_get_dataframe_project(self):
        """Test get dataframe tfidf"""
        df = get_dataframe_project(self.project)

        self.assertTrue(isinstance(df, pd.core.frame.DataFrame))

    def test_load_hdbscan_prob(self):
        """Loads hdbscan prob scores"""
        scores = load_hdbscan_prob(self.project)

        self.assertTrue(isinstance(scores, list))
