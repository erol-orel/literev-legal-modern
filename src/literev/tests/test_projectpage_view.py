from django.test import TransactionTestCase

from literev.models import Cluster, Document, Project
from literev.templatetags.filtering_functions import has_early_results
from literev.views import (
    extract_refined_list,
    format_grouped_clusters,
    get_color_map,
    get_grouped_clusters,
)


class TestProjectPageView(TransactionTestCase):
    def setUp(self):
        """
        Set up test data.
        """
        self.project = Project.objects.create(name="project test")

        topics_list = [
            "water, sample, cap, pilon, air, climate, pair, saint, country, salt, sugar, window",
            "unclassified papers",
            "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11",
        ]
        for i, topic in enumerate(topics_list):
            # Creater cluster with order in reverse
            Cluster.objects.create(
                project=self.project,
                order=3 - i + 1,
                topic=topic,
            )

        results_list = ["accepted", "rejected", "dismissed"]
        standards_list = ["tltr;rtfm", "tul;mph;bpm", "lgtm;rtfma;tltr"]
        descriptors_list = ["descriptor 1", "descriptor 2", "descriptor 3"]

        for result, standard, descriptors in zip(
            results_list, standards_list, descriptors_list
        ):
            Document.objects.create(
                project=self.project,
                descriptors=descriptors,
                standards=standard,
                result=result,
            )

    def test_has_early_results(self):
        """
        Tests if has_early_results function return correct values.
        """

        for status in ["getting_documents", "preparing", "preprocessing"]:
            self.project.step = status
            self.project.save()

            result = has_early_results(self.project)
            self.assertEqual(result, False)

        for status in ["clustering", "plotting"]:
            self.project.step = status
            self.project.save()

            result = has_early_results(self.project)
            self.assertEqual(result, True)

    def test_get_grouped_cluster(self):
        """
        Test if the function get_grouped_cluster return correct order
        """
        # Create test data

        clusters_list = get_grouped_clusters(self.project)
        first_cluster = clusters_list[0]

        self.assertEqual(
            "1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11", first_cluster["topic"]
        )

    def test_format_grouped_clusters(self):
        """
        Tests if the clusters are formatted in the right way before rendering
        """
        clusters_list_topics = get_grouped_clusters(self.project)
        formatted_clusters_topic = format_grouped_clusters(
            clusters_list_topics
        )

        first_cluster_topic = formatted_clusters_topic[0]
        last_cluster = formatted_clusters_topic[-1]

        # check if  unclassified papers topic is at the end of the returned list
        self.assertEqual("unclassified papers", last_cluster)

        # check if the topic is formatted in the right way
        expected = "1: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10"

        self.assertEqual(expected, first_cluster_topic)

    def test_get_color_map(self):
        """
        Tests colors for topics
        """
        clusters_list = list(
            Cluster.objects.filter(project=self.project)
            .values_list("topic", flat=True)
            .order_by("order")
        )

        topics, palette = get_color_map(clusters_list)

        topic_colors = dict(zip(topics, palette))

        self.assertEqual(topic_colors["unclassified papers"], "#9494b8")
        self.assertEqual(
            topic_colors[
                "water, sample, cap, pilon, air, climate, pair, saint, country, salt, sugar, window"
            ],
            "#ff00ff",
        )
        self.assertEqual(
            topic_colors["1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11"], "#00ff00"
        )

    def test_extract_refined_list(self):
        """
        Test extract list of standards
        """

        expected = ["bpm", "lgtm", "mph", "rtfm", "rtfma", "tltr", "tul"]
        results = extract_refined_list(self.project)

        self.assertEqual(results, expected)
