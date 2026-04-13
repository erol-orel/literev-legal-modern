"""Document content API views."""

from __future__ import annotations

from typing import cast

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.document_content import (
    build_document_content_payload,
    build_highlighted_document_content_payload,
)
from literev.models import User


class DocumentContentAPIView(APIView):
    """Return a document payload for the React content page."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, document_id: int) -> Response:
        payload = build_document_content_payload(
            cast(User, request.user), document_id
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)


class HighlightedDocumentContentAPIView(APIView):
    """Return a highlighted document payload for the React content page."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, document_rag_id: int) -> Response:
        payload = build_highlighted_document_content_payload(
            cast(User, request.user), document_rag_id
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)
