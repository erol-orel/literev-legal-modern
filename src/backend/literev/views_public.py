from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.urls import reverse
from django.views.generic import TemplateView

from literev.templatetags.frontend import frontend_bundle_available


def build_public_frontend_context(request: HttpRequest) -> dict[str, Any]:
    """Build the minimal bootstrap context passed from Django to React."""
    return {
        "appName": "LiteRev Legal",
        "user": {
            "isAuthenticated": bool(request.user.is_authenticated),
            "email": getattr(request.user, "email", ""),
        },
        "urls": {
            "home": reverse("home"),
            "search": reverse("search"),
            "team": reverse("team"),
            "product": reverse("product"),
            "company": reverse("company"),
            "blog": reverse("blog"),
            "login": reverse("account_login"),
            "logout": reverse("account_logout"),
        },
    }


class PublicFrontendView(TemplateView):
    """Serve the minimal Django shell used by the React public app."""

    template_name = "generic.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["context"] = build_public_frontend_context(self.request)
        context["frontend_bundle_available"] = frontend_bundle_available()
        return context


public_frontend_app = PublicFrontendView.as_view()
