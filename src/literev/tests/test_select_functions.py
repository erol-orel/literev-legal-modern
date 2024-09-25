import json

from django.test import TestCase

from literev.libs.select_functions import (
    get_filtered_document,
    get_filters,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
)


class FilterTests(TestCase):
    def setUp(self):
        self.project = Project.objects.create(name="Test Project")
        self.cluster = Cluster.objects.create(
            project=self.project, topic="Test Topic", summary="Summary"
        )
        self.doc1 = Document.objects.create(
            project=self.project,
            standards="Test Standard",
            descriptors="Descriptor 1; Descriptor 2",
            result="RETIRE",
            decision_date="2023-06-01",
        )
        self.doc2 = Document.objects.create(
            project=self.project,
            standards="Another Standard",
            descriptors="Descriptor 3; Descriptor 4",
            result="REFUSE",
            decision_date="2023-07-01",
        )

        ClusterElement.objects.create(
            pos_x=1.0, pos_y=1.0, document=self.doc1, cluster=self.cluster
        )
        ClusterElement.objects.create(
            pos_x=2.0, pos_y=2.0, document=self.doc2, cluster=self.cluster
        )

    def test_get_filters_valid(self):
        """Test valid filter extraction from post data."""
        post_data = {
            "filter-union-0": json.dumps({"Topic": ["Test Topic"]}),
            "filter-exclude-0": json.dumps({"Norm": ["Some Norm"]}),
        }
        expected_filters = {
            "filter-union-0": {"Topic": ["Test Topic"]},
            "filter-exclude-0": {"Norm": ["Some Norm"]},
        }
        self.assertEqual(get_filters(post_data), expected_filters)

    def test_get_filters_invalid_json(self):
        """Test invalid JSON in post data."""
        post_data = {"filter-union-0": "invalid json"}
        expected_filters = {}
        self.assertEqual(get_filters(post_data), expected_filters)

    def test_get_filters_empty_value(self):
        """Test empty filter values."""
        post_data = {"filter-union-0": "{}"}
        expected_filters = {}
        self.assertEqual(get_filters(post_data), expected_filters)

    def test_get_filters_no_filters(self):
        """Test case with no filters."""
        post_data = {}
        expected_filters = {}
        self.assertEqual(get_filters(post_data), expected_filters)

    def test_get_filtered_document_union(self):
        """Test filter logic with union filters."""
        filters = {
            "filter-union-0": {"Topic": ["1: Test Topic"]},
            "filter-exclude-0": {"Norm": ["Some Norm"]},
        }
        result_docs = get_filtered_document(self.project, filters)

        expected_docs = sorted(
            [self.doc1.id, self.doc2.id]
        )  # Expect both docs
        self.assertEqual(sorted(result_docs), expected_docs)

    def test_get_filtered_document_exclude(self):
        """Test filter logic with exclusion filters."""
        filters = {"filter-exclude-0": {"Norm": ["Test Standard"]}}
        expected_docs = [self.doc2.pk]  # Exclude doc1
        result_docs = get_filtered_document(self.project, filters)
        self.assertEqual(result_docs, expected_docs)

    def test_get_filtered_document_combination(self):
        """Test combined union and exclusion filters."""
        filters = {
            "filter-union-0": {"Topic": ["1: Test Topic"]},
            "filter-exclude-0": {"Norm": ["Test Standard"]},
        }
        expected_docs = [self.doc2.id]  # Doc1 excluded, expect only doc2
        result_docs = get_filtered_document(self.project, filters)
        self.assertEqual(result_docs, expected_docs)

    def test_get_filtered_document_no_filters(self):
        """Test case with no filters applied."""
        filters = {}
        expected_docs = [self.doc1.pk, self.doc2.pk]  # Both documents expected
        result_docs = get_filtered_document(self.project, filters)
        self.assertEqual(result_docs, expected_docs)

    def test_get_filtered_document_union_with_and_logic(self):
        """Test filter logic with union filters combining Topic and year_range (AND logic)."""

        doc3 = Document.objects.create(
            project=self.project,
            standards="Standard 3",
            result="NO RESULT",
            decision_date="2020-06-01",
        )

        ClusterElement.objects.create(
            pos_x=3.0, pos_y=3.0, document=doc3, cluster=self.cluster
        )

        filters = {
            "filter-union-0": {
                "Topic": [
                    "1: reconsidération, élève, chien, pays, révocation, interdiction, infraction, condamner, kosovo, collègue"
                ],
                "year_range": ["2020"],
            }
        }

        # We expect doc3 to match because it belongs to 2020 and the topic is valid.
        expected_docs = [doc3.id]

        result_docs = get_filtered_document(self.project, filters)

        self.assertEqual(result_docs, expected_docs)

    def test_get_filtered_document_exclude_year_range(self):
        """Test exclusion filter with year_range excluding 2022."""

        doc3 = Document.objects.create(
            project=self.project,
            standards="Standard 3",
            result="NO RESULT",
            decision_date="2022-06-01",
        )

        doc4 = Document.objects.create(
            project=self.project,
            standards="Standard 4",
            result="NO RESULT",
            decision_date="2019-05-01",
        )

        doc5 = Document.objects.create(
            project=self.project,
            standards="Standard 5",
            result="NO RESULT",
            decision_date="2023-07-01",
        )

        ClusterElement.objects.create(
            pos_x=3.0, pos_y=3.0, document=doc3, cluster=self.cluster
        )
        ClusterElement.objects.create(
            pos_x=4.0, pos_y=4.0, document=doc4, cluster=self.cluster
        )

        ClusterElement.objects.create(
            pos_x=5.0, pos_y=5.0, document=doc5, cluster=self.cluster
        )

        # Filters: Exclude documents in year 2022
        filters = {
            "filter-exclude": {
                "year_range": ["2022"],
            }
        }

        expected_docs = sorted([self.doc1.id, self.doc2.id, doc4.id, doc5.id])

        result_docs = get_filtered_document(self.project, filters)

        self.assertEqual(sorted(result_docs), expected_docs)

    def test_get_filtered_document_union_with_descriptors(self):
        """Test filter logic with union filters using descriptors."""

        # Filters: union by descriptors
        filters = {
            "filter-union-0": {"descriptors": ["Descriptor 1"]},
        }

        # Expect doc1 to match, as it has "Descriptor 1"
        expected_docs = [self.doc1.id]

        result_docs = get_filtered_document(self.project, filters)

        self.assertEqual(result_docs, expected_docs)

    def test_get_filtered_document_exclude_descriptors(self):
        """Test exclusion filter using descriptors."""

        # Filters: exclude documents with "Descriptor 1"
        filters = {
            "filter-exclude-0": {"descriptors": ["Descriptor 1"]},
        }

        # Expect doc2 to match, as doc1 has "Descriptor 1" and is excluded
        expected_docs = [self.doc2.id]

        result_docs = get_filtered_document(self.project, filters)

        self.assertEqual(result_docs, expected_docs)

    def test_get_filtered_document_combined_descriptor_and_topic(self):
        """Test combined filter logic with both descriptors and topic."""

        # Filters: Union with both descriptors and topic
        filters = {
            "filter-union-0": {
                "descriptors": ["Descriptor 3"],
                "Topic": ["1: Test Topic"],
            },
        }

        # Expect doc2 to match since it has "Descriptor 3" and matches the topic
        expected_docs = [self.doc2.id]

        result_docs = get_filtered_document(self.project, filters)

        self.assertEqual(result_docs, expected_docs)
