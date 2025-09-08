import json

from django.test import TestCase, TransactionTestCase, override_settings

from literev.libs.select_functions import (
    add_tooltips_topic,
    get_filtered_document,
    get_filters,
    get_rendered_filters,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
)

CLUSTERING_MIN_DOCUMENTS_TEST = 3


@override_settings(CLUSTERING_MIN_DOCUMENTS=CLUSTERING_MIN_DOCUMENTS_TEST)
class RefinementFilterTests(TransactionTestCase):
    def setUp(self):
        """Set up test data for refinement workflow tests."""
        self.project = Project.objects.create(name="licenciements 2000-2024")
        self.cluster = Cluster.objects.create(
            project=self.project,
            topic="administratif, résiliation, notification, proportionnalité",
            summary="Résumé sur les licenciements dans les hôpitaux.",
        )

        self.doc1 = Document.objects.create(
            project=self.project,
            standards="Cst.29.al2;LPAC.20;RPAC.44A;CO.336c.al1.letb",
            descriptors="FONCTIONNAIRE;LICENCIEMENT ADMINISTRATIF;JUSTE MOTIF",
            result="PARTIELMNT ADMIS",
            decision_type="ATA/1060/2020",
            decision_date="2020-10-27",
        )
        self.doc2 = Document.objects.create(
            project=self.project,
            standards="Cst.29.al2;LPAC.22;RPAC.20;LPol.1.al2",
            descriptors="POLICE;RÉSILIATION;MOTIF;PROPORTIONNALITÉ",
            result="REJETE",
            decision_type="ATA/1189/2022",
            decision_date="2022-11-29",
        )
        self.doc3 = Document.objects.create(
            project=self.project,
            standards="LPA.46;LPA.47;LPA.62",
            descriptors="NOTIFICATION IRRÉGULIÈRE;PRINCIPE DE LA BONNE FOI;CALCUL DU DÉLAI",
            result="IRRECEVABLE",
            decision_type="ATA/220/2012",
            decision_date="2012-04-17",
        )

        self.doc4 = Document.objects.create(
            project=self.project,
            standards="LPAC.21.al3;LPAC.22;RPAC.46A;Cst.36.al3",
            descriptors="DROIT DE LA FONCTION PUBLIQUE;LICENCIEMENT ADMINISTRATIF;RECONVERSION PROFESSIONNELLE",
            result="ACCORDE",
            decision_type="ATA/1261/2018",
            decision_date="2018-11-27",
        )

        ClusterElement.objects.create(
            pos_x=1.0, pos_y=1.0, document=self.doc1, cluster=self.cluster
        )
        ClusterElement.objects.create(
            pos_x=2.0, pos_y=2.0, document=self.doc2, cluster=self.cluster
        )
        ClusterElement.objects.create(
            pos_x=3.0, pos_y=3.0, document=self.doc3, cluster=self.cluster
        )
        ClusterElement.objects.create(
            pos_x=4.0, pos_y=4.0, document=self.doc4, cluster=self.cluster
        )

    def test_get_filters_valid(self):
        """Test valid filter extraction from POST data."""
        post_data = {
            "filter-union-0": json.dumps({"Topic": ["administratif"]}),
            "filter-exclude-0": json.dumps({"Norm": ["LPAC.20"]}),
        }
        expected_filters = {
            "filter-union-0": {"Topic": ["administratif"]},
            "filter-exclude-0": {"Norm": ["LPAC.20"]},
        }
        self.assertEqual(get_filters(post_data), expected_filters)

    def test_filter_by_topic(self):
        """Test filtering by Topic."""
        filters = {"filter-union-0": {"Topic": ["administratif"]}}
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [
            self.doc1.id,
            self.doc2.id,
            self.doc3.id,
            self.doc4.id,
        ]
        self.assertEqual(sorted(result_docs), sorted(expected_docs))

    def test_filter_by_norm(self):
        """Test filtering by Norm."""
        filters = {"filter-union-0": {"Norm": ["LPAC.20"]}}
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc1.id]
        self.assertEqual(result_docs, expected_docs)

    def test_filter_by_no_decis(self):
        """Test filtering by No_decis."""
        filters = {"filter-union-0": {"No_decis": ["ATA/1189/2022"]}}
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc2.id]
        self.assertEqual(result_docs, expected_docs)

    def test_filter_by_result(self):
        """Test filtering by Result."""
        filters = {"filter-union-0": {"Result": ["REJETE"]}}
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc2.id]
        self.assertEqual(result_docs, expected_docs)

    def test_filter_by_year(self):
        """Test filtering by Decision Year."""
        filters = {"filter-union-0": {"year_range": ["2020"]}}
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc1.id]
        self.assertEqual(result_docs, expected_docs)

    def test_combination_topic_and_year(self):
        """Test combining Topic and year_range filters."""
        filters = {
            "filter-union-0": {
                "Topic": ["résiliation"],
                "year_range": ["2022"],
            }
        }
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc2.id]
        self.assertEqual(result_docs, expected_docs)

    def test_combination_norm_and_descriptor(self):
        """Test combining Norm and Descriptor filters."""
        filters = {
            "filter-union-0": {
                "Norm": ["LPA.46"],
                "descriptors": ["CALCUL DU DÉLAI"],
            }
        }
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc3.id]
        self.assertEqual(result_docs, expected_docs)

    def test_combination_add_and_exclude(self):
        """Test combined adding and excluding filters."""
        filters = {
            "filter-union-0": {"year_range": ["2020"], "Norm": ["LPAC.20"]},
            "filter-exclude-0": {"descriptors": ["JUSTE MOTIF"]},
        }
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = []
        self.assertEqual(result_docs, expected_docs)

    def test_exclude_by_norm_and_no_decis(self):
        """Test excluding by Norm and No_decis."""
        filters = {
            "filter-exclude-0": {
                "Norm": ["LPA.46"],
                "No_decis": ["ATA/220/2012"],
            },
        }
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [
            self.doc1.id,
            self.doc2.id,
            self.doc4.id,
        ]
        self.assertEqual(sorted(result_docs), sorted(expected_docs))

    def test_add_and_exclude_multiple_conditions(self):
        filters = {
            "filter-union-0": {"descriptors": ["POLICE"]},
            "filter-union-1": {"Result": ["PARTIELMNT ADMIS"]},
            "filter-union-2": {"No_decis": ["ATA/220/2012"]},
            "filter-union-3": {"Norm": ["RPAC.46A"]},
            "filter-exclude": {
                "descriptors": ["PRINCIPE DE LA BONNE FOI"],
                "No_decis": ["ATA/1261/2018"],
            },
        }
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [
            self.doc1.id,
            self.doc2.id,
        ]
        self.assertSetEqual(set(result_docs), set(expected_docs))

    def test_combination_all_fields(self):
        """Test combining all fields in union and exclude filters."""
        filters = {
            "filter-union-0": {"Topic": ["notification"]},
            "filter-exclude-0": {
                "descriptors": ["PRINCIPE DE LA BONNE FOI"],
                "No_decis": ["ATA/1261/2018"],
                "Result": ["PARTIELMNT ADMIS"],
                "Norm": ["RPAC.46A"],
                "year_range": ["2020"],
            },
        }
        result_docs = get_filtered_document(self.project, filters)
        expected_docs = [self.doc2.id]
        self.assertEqual(result_docs, expected_docs)


class TableRenderFilters(TestCase):
    """Tests correct rendering filters in table select page."""

    def test_render_filters(self):
        """Check if render filters correctly"""
        input = {
            "filter-union-0": {"Topic": ["1: water, soil"]},
            "filter-union-1": {"Norm": ["ALCP", "CDI"]},
            "filter-exclude": {
                "Topic": ["2: energy"],
            },
        }
        expected_union_filter = (
            '(<span data-toggle="tooltip" data-placement="bottom" '
            'title="water, soil">Topic 1</span>)'
            "<b> OR </b>(Norm: ALCP<b> AND </b>Norm: CDI)"
        )
        result_union, result_excluded = get_rendered_filters(input)
        expected_excluded = (
            '(<span data-toggle="tooltip" data-placement="bottom" '
            'title="energy">Topic 2</span>)'
        )
        self.assertEqual(expected_union_filter, result_union)
        self.assertEqual(expected_excluded, result_excluded)

    def test_render_filter_w_unclassified(self):
        """Check if render filters correctly"""
        input = {
            "filter-union-0": {"Topic": ["unclassified papers"]},
            "filter-union-1": {"Norm": ["ALCP", "CDI"]},
            "filter-exclude": {
                "Keyword": ["france"],
                "No_decis": ["ATA/1013/2017"],
            },
        }
        expected_union_filter = (
            '(<span data-toggle="tooltip" data-placement="bottom" '
            'title="unclassified papers">unclassified papers</span>)'
            "<b> OR </b>(Norm: ALCP<b> AND </b>Norm: CDI)"
        )
        result_union, result_excluded = get_rendered_filters(input)
        expected_excluded = (
            "(Keyword: france<b> OR </b>No_decis: ATA/1013/2017)"
        )
        self.assertEqual(expected_union_filter, result_union)
        self.assertEqual(expected_excluded, result_excluded)

    def test_add_tooltip_topic(self):
        """Checks if add the tooltip correctly"""
        topic_dict = {"Topic 1": "conjugal, réintégration"}
        input = "(Topic 1)"
        expected = '(<span data-toggle="tooltip" data-placement="bottom" title="conjugal, réintégration">Topic 1</span>)'
        result = add_tooltips_topic(input, topic_dict)
        self.assertEqual(expected, result)
