"""Test RAG API."""

from __future__ import annotations

import pytest

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class TestBooleanQueryGeneration(APITestCase):
    def setUp(self):
        """Set up authentication and test data."""
        self.user = get_user_model().objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="securepassword",
        )
        self.client.force_authenticate(user=self.user)

    def get_boolean_query(self, nlq):
        """Helper method to retrieve boolean query from API."""
        url = reverse("nl-to-bool-query", args=[nlq])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.json()["query"]

    def test_and_or_usage_in_contract_termination(self):
        nlq = "Quels sont les critères pris en compte pour la garde d'enfants lors d'une procédure de divorce?"
        boolean_query = self.get_boolean_query(nlq)

        self.assertIn('"critères"', boolean_query)
        self.assertIn('"garde d\'enfants"', boolean_query)
        self.assertIn('"procédure de divorce"', boolean_query)

    def test_or_usage_in_employment_termination_reasons(self):
        nlq = "Quels sont les motifs de licenciement économique ou personnel?"
        boolean_query = self.get_boolean_query(nlq)
        self.assertIn(
            '("licenciement économique" OR "licenciement personnel")',
            boolean_query,
        )

    def test_and_or_usage_in_contractual_liability(self):
        nlq = "Comment engager la responsabilité contractuelle pour inexécution ou retard de livraison?"
        boolean_query = self.get_boolean_query(nlq)
        self.assertIn('"responsabilité contractuelle"', boolean_query)
        self.assertIn(
            '("inexécution" OR "retard de livraison")', boolean_query
        )

    def test_exclusion_in_non_compete_clause(self):
        nlq = "Recherchez des clauses de non-concurrence, sans inclure les contrats de dirigeants."
        boolean_query = self.get_boolean_query(nlq)
        self.assertIn('"clauses de non-concurrence"', boolean_query)
        self.assertIn('NOT "contrats de dirigeants"', boolean_query)

    def test_not_usage_in_civil_liability_exclusion(self):
        nlq = "Recherchez des décisions sur la responsabilité civile, sans inclure les cas de force majeure."
        boolean_query = self.get_boolean_query(nlq)
        self.assertIn('"responsabilité civile"', boolean_query)
        self.assertIn('NOT "force majeure"', boolean_query)

    def test_not_usage_in_workplace_harassment_exclusion(self):
        nlq = "Recherchez des affaires de harcèlement au travail, excluant celles portant sur la violence psychologique."
        boolean_query = self.get_boolean_query(nlq)
        self.assertIn('"harcèlement au travail"', boolean_query)
        self.assertIn('NOT "violence psychologique"', boolean_query)

    @pytest.mark.flaky(reruns=3, rerun_except="AssertionError")
    def test_and_or_usage_in_unfair_dismissal_without_notice(self):
        nlq = "Recherchez des jugements pour licenciement abusif sans préavis."
        boolean_query = self.get_boolean_query(nlq)
        self.assertIn('"licenciement abusif"', boolean_query)
        self.assertIn('"préavis"', boolean_query)
        self.assertIn('NOT "sans préavis"', boolean_query)
