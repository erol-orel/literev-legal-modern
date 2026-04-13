"""Project overview and refinement domain API views."""

from __future__ import annotations

from typing import Any, cast

from django.urls import reverse
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.project_overview import (
    ProjectFilters,
    build_project_overview,
    create_project_refinement,
    delete_project_refinement,
    generate_cluster_summary,
    get_accessible_project,
    preview_project_filters,
    start_top_documents_rag,
)
from literev.models import User


class ProjectFiltersSerializer(serializers.Serializer):
    """Validate project refinement filter payloads."""

    filters = serializers.JSONField(required=False, default=dict)

    def validate_filters(self, value: Any) -> ProjectFilters:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a JSON object.")
        return cast(ProjectFilters, value)


class ProjectRefinementCreateSerializer(ProjectFiltersSerializer):
    """Validate refinement creation requests."""

    refinement_name = serializers.CharField(
        max_length=1024,
        trim_whitespace=True,
    )


class ProjectOverviewAPIView(APIView):
    """Return the project overview payload for the React project page."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, project_id: int) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if project.step == "getting_documents":
            return Response(
                {
                    "detail": "Project is still collecting documents.",
                    "redirect_url": reverse("search"),
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            build_project_overview(user, project),
            status=status.HTTP_200_OK,
        )


class ProjectFilterPreviewAPIView(APIView):
    """Preview how many documents a refinement would include."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, project_id: int) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ProjectFiltersSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        filters = cast(ProjectFilters, serializer.validated_data["filters"])

        try:
            preview = preview_project_filters(user, project, filters)
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(preview, status=status.HTTP_200_OK)


class ProjectRefinementsAPIView(APIView):
    """Create project refinements from the overview page."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, project_id: int) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = ProjectRefinementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refinement_name = cast(
            str, serializer.validated_data["refinement_name"]
        )
        filters = cast(ProjectFilters, serializer.validated_data["filters"])

        try:
            refinement = create_project_refinement(
                user,
                project,
                refinement_name,
                filters,
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(refinement, status=status.HTTP_201_CREATED)


class ProjectRefinementDetailAPIView(APIView):
    """Delete refinements owned by the current user."""

    permission_classes = [IsAuthenticated]

    def delete(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        deleted = delete_project_refinement(user, project, refinement_id)
        if not deleted:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectClusterSummaryAPIView(APIView):
    """Generate summaries for clusters in a project overview."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        cluster_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        try:
            payload = generate_cluster_summary(project, cluster_id)
        except ValueError:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except RuntimeError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(payload, status=status.HTTP_200_OK)


class ProjectAskTopDocumentsAPIView(APIView):
    """Create a top-documents RAG selection from the overview page."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, project_id: int) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        rag_url = start_top_documents_rag(user, project)
        return Response(
            {
                "detail": "Top documents were prepared for question answering.",
                "urls": {"rag": rag_url},
            },
            status=status.HTTP_200_OK,
        )
