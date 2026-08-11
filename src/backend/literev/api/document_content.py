"""Document content API views."""

from __future__ import annotations

from typing import cast

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.document_content import (
    build_document_content_payload,
    build_highlighted_document_content_payload,
)
from literev.libs.response_cache import get_or_set_payload, make_key
from literev.models import User


class DocumentContentAPIView(APIView):
    """Return a document payload for the React content page."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, document_id: int) -> Response:
        user = cast(User, request.user)
        payload = get_or_set_payload(
            make_key("doc-content", user.id, document_id),
            lambda: build_document_content_payload(user, document_id),
            timeout=settings.RESPONSE_CACHE_TTL,
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)


class HighlightedDocumentContentAPIView(APIView):
    """Return a highlighted document payload for the React content page."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, document_rag_id: int) -> Response:
        user = cast(User, request.user)
        payload = get_or_set_payload(
            make_key("doc-highlighted", user.id, document_rag_id),
            lambda: build_highlighted_document_content_payload(
                user, document_rag_id
            ),
            timeout=settings.RESPONSE_CACHE_TTL,
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)
