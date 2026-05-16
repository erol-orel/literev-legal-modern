from __future__ import annotations

import json
import tempfile

from pathlib import Path

from django.contrib import messages
from django.contrib.messages.storage.base import BaseStorage, Message
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse

from config import __version__
from literev.views_public import (
    HomeFrontendView,
    PublicFrontendView,
    build_frontend_context,
    home_frontend_app,
    public_frontend_app,
)


class ListMessageStorage(BaseStorage):
    """In-memory message storage for RequestFactory-only tests."""

    def _get(
        self, *args: object, **kwargs: object
    ) -> tuple[list[Message], bool]:
        """Return no loaded messages.

        Returns
        -------
        tuple[list, bool]
            Empty loaded message list and all-retrieved flag.
        """
        return [], True

    def _store(
        self,
        messages: list[Message],
        response: object,
        *args: object,
        **kwargs: object,
    ) -> list[Message]:
        """Store no messages because tests only inspect immediate iteration.

        Parameters
        ----------
        messages
            Messages that would be persisted.
        response
            Response object, unused.

        Returns
        -------
        list
            Empty unstored message list.
        """
        return []


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
                "account/logout.html",
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
        for route_name in ["team", "product", "company", "blog"]:
            match = resolve(reverse(route_name))
            self.assertIs(match.func, public_frontend_app)
            self.assertIs(match.func.view_class, PublicFrontendView)

    def test_home_route_uses_authenticated_redirect_entry_view(self) -> None:
        """The home route should redirect authenticated users to search."""
        match = resolve(reverse("home"))

        self.assertIs(match.func, home_frontend_app)
        self.assertIs(match.func.view_class, HomeFrontendView)

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

    def test_authenticated_home_route_redirects_to_search(self) -> None:
        """Authenticated direct visits to home should land in search."""
        request = RequestFactory().get(reverse("home"))
        request.user = type("User", (), {"is_authenticated": True})()
        response = home_frontend_app(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("search"))

    def test_frontend_context_consumes_django_messages(self) -> None:
        """React-owned pages should consume Django messages exactly once."""
        request = RequestFactory().get(reverse("home"))
        request.session = {}
        request._messages = ListMessageStorage(request)
        request.user = type(
            "User",
            (),
            {"email": "", "is_authenticated": False},
        )()
        messages.success(request, "Successfully signed out.")

        storage = request._messages
        context = build_frontend_context(request)

        self.assertEqual(
            context["messages"],
            [
                {
                    "level": messages.SUCCESS,
                    "levelTag": "success",
                    "message": "Successfully signed out.",
                    "tags": "success",
                }
            ],
        )
        self.assertTrue(storage.used)

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
