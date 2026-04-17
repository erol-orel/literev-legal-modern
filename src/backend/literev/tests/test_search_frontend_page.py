from __future__ import annotations

import json
import tempfile

from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import resolve, reverse

from literev.models import Project, ProjectRefinement
from literev.views_public import (
    AuthenticatedFrontendView,
    authenticated_frontend_app,
)


class AuthenticatedFrontendRouteTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._temp_dir = tempfile.TemporaryDirectory()
        cls.manifest_path = Path(cls._temp_dir.name) / "asset-manifest.json"
        cls.manifest_path.write_text(
            json.dumps(
                {
                    "files": {
                        "main.css": "/static/css/main.test.css",
                        "main.js": "/static/js/main.test.js",
                    }
                }
            )
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp_dir.cleanup()
        super().tearDownClass()

    def setUp(self) -> None:
        self.user = get_user_model().objects.create_user(
            username="search-view-user",
            email="search-view@example.com",
            password="secure-password",
        )
        self.project = Project.objects.create(
            user=self.user,
            name="Frontend Project",
            query='"housing"',
            range_begin_date="2020-01-01",
            range_end_date="2020-12-31",
            total_documents=3,
            selected_indices=["chambre_administrative"],
            step="plotting",
            is_finish=True,
        )
        self.refinement = ProjectRefinement.objects.create(
            project=self.project,
            owner=self.user,
            name="Frontend Refinement",
        )

    def test_authenticated_routes_share_the_same_frontend_entry_view(
        self,
    ) -> None:
        routes = [
            reverse("search"),
            reverse("running"),
            reverse("historicalpage"),
            reverse("projectpage", args=[self.project.id]),
            reverse("project-rag-page", args=[self.project.id]),
            reverse("project-rag-id-page", args=[self.project.id, 1]),
            reverse("contentdocument", args=[1]),
            reverse("contentdocument_highlighted", args=[1]),
            reverse(
                "tableselect-default",
                args=[self.project.id, self.refinement.id],
            ),
            reverse(
                "tableselect",
                args=[
                    self.project.id,
                    self.refinement.id,
                    1,
                    1,
                    "decision_date",
                ],
            ),
        ]
        for route in routes:
            match = resolve(route)
            self.assertIs(match.func, authenticated_frontend_app)
            self.assertIs(match.func.view_class, AuthenticatedFrontendView)

    def test_authenticated_routes_redirect_guests_to_login(self) -> None:
        routes = [
            (reverse("search"), "/search/"),
            (reverse("running"), "/running/"),
            (reverse("historicalpage"), "/historicalpage/"),
            (
                reverse("projectpage", args=[self.project.id]),
                reverse("project-rag-page", args=[self.project.id]),
                reverse("project-rag-id-page", args=[self.project.id, 1]),
                f"/project/{self.project.id}/",
            ),
            (
                reverse("contentdocument", args=[1]),
                "/contentdocument/1",
            ),
            (
                reverse("contentdocument_highlighted", args=[1]),
                "/contentdocument_highlighted/1/",
            ),
            (
                reverse(
                    "tableselect-default",
                    args=[self.project.id, self.refinement.id],
                ),
                f"/tableselect/{self.project.id}/{self.refinement.id}/",
            ),
            (
                reverse(
                    "tableselect",
                    args=[
                        self.project.id,
                        self.refinement.id,
                        1,
                        1,
                        "decision_date",
                    ],
                ),
                (
                    f"/tableselect/{self.project.id}/{self.refinement.id}/"
                    "1/page=1/order_by=decision_date/"
                ),
            ),
        ]
        for route, next_path in routes:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/accounts/login/", response["Location"])
            self.assertIn(f"next={next_path}", response["Location"])

    def test_authenticated_search_route_renders_generic_frontend_template(
        self,
    ) -> None:
        self.client.force_login(self.user)

        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(reverse("search"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "generic.html")
        self.assertContains(response, 'id="root"')
        self.assertContains(response, "/static/css/main.test.css")
        self.assertContains(response, "/static/js/main.test.js")
        self.assertEqual(
            response.context["context"]["api"]["searchPreview"],
            "/api/project/search/preview/",
        )
        self.assertEqual(
            response.context["context"]["search"]["sources"][0]["value"],
            "chambre_administrative",
        )

    def test_generic_frontend_template_skips_legacy_jquery_assets(
        self,
    ) -> None:
        self.client.force_login(self.user)

        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(reverse("search"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            "ajax.googleapis.com/ajax/libs/jquery/3.4.1/jquery.min.js",
        )
        self.assertNotContains(
            response,
            "cdnjs.cloudflare.com/ajax/libs/bootstrap-datepicker/1.9.0/js/bootstrap-datepicker.min.js",
        )
        self.assertNotContains(
            response, "cdn.jsdelivr.net/npm/axios/dist/axios.min.js"
        )

    def test_running_route_exposes_running_and_delete_apis(self) -> None:
        self.client.force_login(self.user)

        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(reverse("running"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["context"]["api"]["runningProjects"],
            "/api/project/running/",
        )
        self.assertEqual(
            response.context["context"]["api"]["projectDeleteBase"],
            "/api/project/projects/",
        )
        self.assertEqual(
            response.context["context"]["api"]["projectApiBase"],
            "/api/project/projects/",
        )
        self.assertEqual(
            response.context["context"]["urls"]["ragBase"],
            "/rag/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragContextBase"],
            "/api/project/rag/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragDeleteBase"],
            "/api/project/rag/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragStatusBase"],
            "/api/project-rags-by-project/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragCreateBase"],
            "/api/project-rags-by-project/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragDocumentsBase"],
            "/api/project-documents-rag/",
        )

    def test_historical_route_exposes_historical_apis(self) -> None:
        self.client.force_login(self.user)

        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(reverse("historicalpage"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["context"]["api"]["historicalProjects"],
            "/api/project/historical/",
        )
        self.assertEqual(
            response.context["context"]["api"]["historicalDeleteAll"],
            "/api/project/historical/delete-all/",
        )

    def test_project_route_exposes_project_base_urls(self) -> None:
        self.client.force_login(self.user)

        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(
                reverse("projectpage", args=[self.project.id])
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["context"]["urls"]["projectBase"], "/project/"
        )
        self.assertEqual(
            response.context["context"]["api"]["projectApiBase"],
            "/api/project/projects/",
        )
        self.assertEqual(
            response.context["context"]["urls"]["ragBase"],
            "/rag/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragContextBase"],
            "/api/project/rag/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragDeleteBase"],
            "/api/project/rag/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragStatusBase"],
            "/api/project-rags-by-project/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragCreateBase"],
            "/api/project-rags-by-project/",
        )
        self.assertEqual(
            response.context["context"]["api"]["ragDocumentsBase"],
            "/api/project-documents-rag/",
        )

    def test_tableselect_route_exposes_tableselect_base_urls(self) -> None:
        self.client.force_login(self.user)

        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(
                reverse(
                    "tableselect-default",
                    args=[self.project.id, self.refinement.id],
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["context"]["urls"]["tableselectBase"],
            "/tableselect/",
        )
        self.assertEqual(
            response.context["context"]["api"]["tableSelectionBase"],
            "/api/project/tableselect/",
        )
