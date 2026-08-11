from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages import get_messages
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from config import __version__
from literev.libs.search import get_search_source_options
from literev.templatetags.frontend import frontend_bundle_available


def build_frontend_context(request: HttpRequest) -> dict[str, Any]:
    """Build the minimal bootstrap context passed from Django to React."""
    return {
        "appName": "LiteRev Legal",
        "appVersion": __version__,
        "messages": [
            {
                "level": message.level,
                "levelTag": message.level_tag,
                "message": str(message),
                "tags": message.tags,
            }
            for message in get_messages(request)
        ],
        "user": {
            "isAuthenticated": bool(request.user.is_authenticated),
            "email": getattr(request.user, "email", ""),
        },
        "urls": {
            "home": reverse("home"),
            "search": reverse("search"),
            "running": reverse("running"),
            "historicalpage": reverse("historicalpage"),
            "projectBase": reverse("projectpage", args=[0]).removesuffix("0/"),
            "contentdocumentBase": reverse(
                "contentdocument", args=[0]
            ).removesuffix("0"),
            "contentdocumentHighlightedBase": reverse(
                "contentdocument_highlighted", args=[0]
            ).removesuffix("0/"),
            "tableselectBase": reverse(
                "tableselect-default", args=[0, 0]
            ).removesuffix("0/0/"),
            "ragBase": reverse("project-rag-page", args=[0]).removesuffix(
                "0/"
            ),
            "team": reverse("team"),
            "product": reverse("product"),
            "company": reverse("company"),
            "blog": reverse("blog"),
            "login": reverse("account_login"),
            "logout": reverse("account_logout"),
        },
        "api": {
            "searchConvertQuery": reverse("api-search-convert-query"),
            "searchValidate": reverse("api-search-validate"),
            "searchPreview": reverse("api-search-preview"),
            "searchProjects": reverse("api-search-projects"),
            "runningProjects": reverse("api-running-projects"),
            "historicalProjects": reverse("api-historical-projects"),
            "historicalDeleteAll": reverse("api-historical-delete-all"),
            "projectApiBase": reverse(
                "api-project-delete", args=[0]
            ).removesuffix("0/"),
            "projectDeleteBase": reverse(
                "api-project-delete", args=[0]
            ).removesuffix("0/"),
            "tableSelectionBase": reverse(
                "api-tableselect-state", args=[0, 0]
            ).removesuffix("0/0/state/"),
            "documentContentBase": reverse(
                "api-document-content", args=[0]
            ).removesuffix("0/"),
            "documentHighlightedBase": reverse(
                "api-document-content-highlighted", args=[0]
            ).removesuffix("0/highlighted/"),
            "ragContextBase": reverse(
                "api-rag-context", args=[0]
            ).removesuffix("0/context/"),
            "ragDeleteBase": reverse(
                "api-rag-delete", args=[0, 0]
            ).removesuffix("0/0/"),
            "ragStatusBase": reverse(
                "projectrag-by-project-rag-id", args=[0, 0]
            ).removesuffix("0/0/"),
            "ragCreateBase": reverse(
                "projectrag-by-project", args=[0]
            ).removesuffix("0/"),
            "ragReportBase": reverse(
                "api-rag-report-docx", args=[0, 0]
            ).removesuffix("0/0/report.docx/"),
            "ragDocumentsBase": reverse("projectdocumentsrag-list"),
        },
        "search": {
            "clusteringMinDocuments": settings.CLUSTERING_MIN_DOCUMENTS,
            "sources": get_search_source_options(),
        },
    }


class FrontendView(TemplateView):
    """Serve the minimal Django shell used by the React frontend app."""

    template_name = "generic.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["context"] = build_frontend_context(self.request)
        context["frontend_bundle_available"] = frontend_bundle_available()
        return context


class PublicFrontendView(FrontendView):
    """Serve the generic frontend shell for public routes."""


class HomeFrontendView(FrontendView):
    """Serve the public home, or send authenticated users to search."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        """Redirect authenticated users away from the public landing page."""
        if request.user.is_authenticated:
            return redirect("search")

        return super().dispatch(request, *args, **kwargs)


class AuthenticatedFrontendView(LoginRequiredMixin, FrontendView):
    """Serve the generic frontend shell for authenticated routes."""

    login_url = "/accounts/login/"


public_frontend_app = PublicFrontendView.as_view()
home_frontend_app = HomeFrontendView.as_view()
authenticated_frontend_app = AuthenticatedFrontendView.as_view()
