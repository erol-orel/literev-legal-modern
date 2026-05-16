from __future__ import annotations

import json
import tempfile

from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse

from config import __version__
from literev.views_public import PublicFrontendView, public_frontend_app


class PublicReactPageRouteTests(SimpleTestCase):
    def test_only_generic_and_auth_templates_remain_for_backend_pages(
        self,
    ) -> None:
        """Migrated workflow templates should be retired from the Django app."""
        template_names = sorted(
            str(path.relative_to(Path("src/backend/literev/templates")))
            for path in Path("src/backend/literev/templates").rglob("*.html")
        )

        self.assertEqual(
            template_names,
            [
                "account/base.html",
                "account/login.html",
                "account/signup.html",
                "generic.html",
                "registration/base.html",
                "registration/login.html",
            ],
        )

    @classmethod
    def setUpClass(cls) -> None:
        """Create a temporary frontend manifest for route tests."""
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
        """Clean up the temporary manifest."""
        cls._temp_dir.cleanup()
        super().tearDownClass()

    def test_public_routes_share_the_same_frontend_entry_view(self) -> None:
        """All migrated public routes should resolve to one React entry view."""
        for route_name in ["home", "team", "product", "company", "blog"]:
            match = resolve(reverse(route_name))
            self.assertIs(match.func, public_frontend_app)
            self.assertIs(match.func.view_class, PublicFrontendView)

    def test_home_route_renders_generic_frontend_template(self) -> None:
        """The home route should render the generic React entry template."""
        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "generic.html")
        self.assertEqual(response.context["context"]["urls"]["home"], "/")
        self.assertEqual(
            response.context["context"]["appVersion"], __version__
        )
        self.assertContains(response, 'id="root"')
        self.assertContains(response, 'id="context-data"')
        self.assertContains(response, "/static/css/main.test.css")
        self.assertContains(response, "/static/js/main.test.js")

    def test_team_route_renders_generic_frontend_template(self) -> None:
        """The team route should render the generic React entry template."""
        with override_settings(
            FRONTEND_ASSET_MANIFEST_PATH=self.manifest_path
        ):
            response = self.client.get(reverse("team"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "generic.html")
        self.assertEqual(response.context["context"]["urls"]["team"], "/team/")

    def test_missing_bundle_shows_build_warning(self) -> None:
        """The generic template should expose a missing bundle warning."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_manifest_path = Path(tmp_dir) / "asset-manifest.json"
            with override_settings(
                FRONTEND_ASSET_MANIFEST_PATH=missing_manifest_path
            ):
                response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "generic.html")
        self.assertFalse(response.context["frontend_bundle_available"])
        self.assertContains(response, "makim reactjs.build")
