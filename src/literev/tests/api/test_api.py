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

    def _assert_terms(self, query, *terms):
        """Assert each term appears in the query (case-insensitive)."""
        q_lower = query.lower()
        for term in terms:
            self.assertIn(
                term.lower(),
                q_lower,
                msg=f"Expected term {term!r} not found in query: {query!r}",
            )

    def test_and_or_usage_in_contract_termination(self):
        nlq = "Quels sont les critères pris en compte pour la garde d'enfants lors d'une procédure de divorce?"
        boolean_query = self.get_boolean_query(nlq)

        self._assert_terms(boolean_query, "critères", "garde", "divorce")
        # At least one boolean operator should appear
        self.assertTrue(
            any(op in boolean_query.upper() for op in ("AND", "OR", "NOT")),
            msg=f"No boolean operator found in query: {boolean_query!r}",
        )

    def test_or_usage_in_employment_termination_reasons(self):
        nlq = "Quels sont les motifs de licenciement économique ou personnel?"
        boolean_query = self.get_boolean_query(nlq)

        self._assert_terms(boolean_query, "licenciement")
        self.assertIn(
            "OR",
            boolean_query.upper(),
            msg=f"Expected OR operator in query: {boolean_query!r}",
        )

    def test_and_or_usage_in_contractual_liability(self):
        nlq = "Comment engager la responsabilité contractuelle pour inexécution ou retard de livraison?"
        boolean_query = self.get_boolean_query(nlq)

        self._assert_terms(boolean_query, "responsabilité", "contractuelle")
        self.assertIn(
            "OR",
            boolean_query.upper(),
            msg=f"Expected OR operator in query: {boolean_query!r}",
        )

    def test_exclusion_in_non_compete_clause(self):
        nlq = "Recherchez des clauses de non-concurrence, sans inclure les contrats de dirigeants."
        boolean_query = self.get_boolean_query(nlq)

        # "dirigeant" covers both singular and plural forms the LLM may produce
        self._assert_terms(boolean_query, "non-concurrence", "dirigeant")
        self.assertIn(
            "NOT",
            boolean_query.upper(),
            msg=f"Expected NOT operator in query: {boolean_query!r}",
        )

    def test_not_usage_in_civil_liability_exclusion(self):
        nlq = "Recherchez des décisions sur la responsabilité civile, sans inclure les cas de force majeure."
        boolean_query = self.get_boolean_query(nlq)

        self._assert_terms(
            boolean_query, "responsabilité civile", "force majeure"
        )
        self.assertIn(
            "NOT",
            boolean_query.upper(),
            msg=f"Expected NOT operator in query: {boolean_query!r}",
        )

    def test_not_usage_in_workplace_harassment_exclusion(self):
        nlq = "Recherchez des affaires de harcèlement au travail, excluant celles portant sur la violence psychologique."
        boolean_query = self.get_boolean_query(nlq)

        self._assert_terms(boolean_query, "harcèlement", "violence")
        self.assertIn(
            "NOT",
            boolean_query.upper(),
            msg=f"Expected NOT operator in query: {boolean_query!r}",
        )

    @pytest.mark.flaky(reruns=3, rerun_except="AssertionError")
    def test_and_or_usage_in_unfair_dismissal_without_notice(self):
        nlq = "Recherchez des jugements pour licenciement abusif sans préavis."
        boolean_query = self.get_boolean_query(nlq)

        # LLM may use synonyms: "licenciement abusif", "licenciement injustifié", "rupture abusive"
        q_lower = boolean_query.lower()
        self.assertTrue(
            any(
                t in q_lower
                for t in (
                    "licenciement abusif",
                    "licenciement injustifié",
                    "rupture abusive",
                    "licenciement",
                )
            ),
            msg=f"Expected a dismissal term in query: {boolean_query!r}",
        )
        self._assert_terms(boolean_query, "préavis")
        # The LLM may use AND to combine "licenciement abusif" and "préavis"
        # concepts rather than NOT — both are valid interpretations.
        self.assertTrue(
            any(op in boolean_query.upper() for op in ("AND", "OR", "NOT")),
            msg=f"No boolean operator found in query: {boolean_query!r}",
        )
