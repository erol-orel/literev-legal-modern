"""RAG workspace API views."""

from __future__ import annotations

from typing import cast

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.rag_workspace import build_rag_context, delete_rag_entry
from literev.models import User


class RagContextAPIView(APIView):
    """Return the bootstrap payload for the RAG workspace."""

    permission_classes = [IsAuthenticated]

    def get(
        self,
        request: Request,
        project_id: int,
        rag_id: int | None = None,
    ) -> Response:
        payload = build_rag_context(
            cast(User, request.user), project_id, rag_id
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)


class RagDeleteAPIView(APIView):
    """Delete a RAG entry for a project."""

    permission_classes = [IsAuthenticated]

    def delete(
        self,
        request: Request,
        project_id: int,
        rag_id: int,
    ) -> Response:
        deleted = delete_rag_entry(
            cast(User, request.user), project_id, rag_id
        )
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            {"detail": "RAG entry removed."}, status=status.HTTP_200_OK
        )
