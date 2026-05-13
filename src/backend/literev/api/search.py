"""Search domain API views."""

from __future__ import annotations

import logging

from typing import cast

from django.conf import settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.search import (
    SearchPayload,
    build_search_payload,
    build_search_preview,
    create_and_launch_search_project,
)
from literev_core.boolean_query import convert_nl_to_boolean

logger = logging.getLogger(__name__)


class SearchRequestSerializer(serializers.Serializer):
    """Validate search payloads submitted by the React search page."""

    project_name = serializers.CharField(max_length=256)
    selected_indices = serializers.ListField(
        child=serializers.CharField(max_length=128),
        allow_empty=False,
    )
    natural_language_query = serializers.CharField(
        max_length=4096,
        allow_blank=True,
        required=False,
        default="",
    )
    query = serializers.CharField(max_length=4096)
    range_begin_date = serializers.DateField(
        input_formats=["%Y/%m/%d", "%Y-%m-%d"]
    )
    range_end_date = serializers.DateField(
        input_formats=["%Y/%m/%d", "%Y-%m-%d"]
    )

    def validate(self, attrs: dict[str, object]) -> SearchPayload:
        try:
            return build_search_payload(attrs)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc


class NaturalLanguageQuerySerializer(serializers.Serializer):
    """Validate natural-language boolean-query conversion requests."""

    natural_language_query = serializers.CharField(
        max_length=4096,
        allow_blank=False,
        trim_whitespace=True,
    )


class ConvertToBooleanQueryAPIView(APIView):
    """Convert natural language queries to boolean queries."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = NaturalLanguageQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        natural_language_query = cast(
            str, serializer.validated_data["natural_language_query"]
        )

        try:
            if getattr(settings, "USE_HACTAR_LLM_FOR_BOOLEAN_QUERY", False):
                boolean_query = convert_nl_to_boolean(
                    natural_language_query,
                    model_name=f"openai/{settings.HACTAR_BOOLEAN_QUERY_MODEL}",
                    base_url=f"{settings.HACTAR_BASE_URL}/api",
                    api_key=settings.HACTAR_API_KEY,
                )
            else:
                boolean_query = convert_nl_to_boolean(
                    natural_language_query,
                    model_name=f"openai/{getattr(settings, 'CHAT_MODEL', 'gpt-4.1-mini')}",
                    api_key=settings.OPENAI_API_KEY,
                )

        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.error("Error generating boolean query: %s", exc)
            return Response(
                {"detail": "An error occurred while processing the request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({"query": boolean_query}, status=status.HTTP_200_OK)


class SearchValidationAPIView(APIView):
    """Validate search input and return the normalized payload."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = cast(SearchPayload, serializer.validated_data)

        return Response(
            {
                "project_name": payload["project_name"],
                "selected_indices": payload["selected_indices"],
                "natural_language_query": payload["natural_language_query"],
                "query": payload["query"],
                "range_begin_date": payload["range_begin_date"].isoformat(),
                "range_end_date": payload["range_end_date"].isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class SearchPreviewAPIView(APIView):
    """Preview the total number of documents for a validated search."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = cast(SearchPayload, serializer.validated_data)

        preview = build_search_preview(
            payload,
            settings.CLUSTERING_MIN_DOCUMENTS,
        )
        return Response(preview, status=status.HTTP_200_OK)


class SearchProjectAPIView(APIView):
    """Create a project from a validated search payload and launch processing."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = SearchRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = cast(SearchPayload, serializer.validated_data)

        preview = build_search_preview(
            payload,
            settings.CLUSTERING_MIN_DOCUMENTS,
        )
        if not preview["can_continue"]:
            return Response(
                {"detail": "No documents were found for this query."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        project, process_started = create_and_launch_search_project(
            cast(User, request.user),
            payload,
            total_documents=preview["total_documents"],
        )

        if not process_started:
            return Response(
                {
                    "detail": "Project creation failed while starting the workflow."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "id": project.id,
                "name": project.name,
                "total_documents": preview["total_documents"],
                "detail": "Your project has been created and is running.",
                "urls": {
                    "running": reverse("running"),
                    "project": reverse("projectpage", args=[project.id]),
                },
            },
            status=status.HTTP_201_CREATED,
        )
