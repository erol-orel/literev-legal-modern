"""Project running/historical list API views."""

from __future__ import annotations

from typing import cast

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.project_listing import (
    delete_all_finished_projects_for_user,
    delete_project,
    get_accessible_project,
    list_historical_projects,
    list_running_projects,
    normalize_sort_type,
    restart_project,
)
from literev.models import User


class RunningProjectsAPIView(APIView):
    """List accessible running projects for the current user."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(
            {"projects": list_running_projects(user)},
            status=status.HTTP_200_OK,
        )


class RunningProjectRestartAPIView(APIView):
    """Restart an owned running project."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, project_id: int) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if project.user != user:
            raise PermissionDenied(
                "You do not have permission to restart this project."
            )

        if not restart_project(user, project_id):
            raise PermissionDenied(
                "You do not have permission to restart this project."
            )

        return Response(
            {"detail": "Project restart requested."},
            status=status.HTTP_200_OK,
        )


class ProjectDeleteAPIView(APIView):
    """Delete one owned project from either running or historical views."""

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request, project_id: int) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if project.user != user:
            raise PermissionDenied(
                "You do not have permission to delete this project."
            )

        if not delete_project(user, project_id):
            raise PermissionDenied(
                "You do not have permission to delete this project."
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class HistoricalProjectsAPIView(APIView):
    """List accessible finished projects with optional search and sorting."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        search = request.query_params.get("search", "").strip()
        sort_type = normalize_sort_type(
            request.query_params.get("sort_type", "more_documents_first")
        )

        return Response(
            {
                "projects": list_historical_projects(user, search, sort_type),
                "query_filter": search,
                "sort_type": sort_type,
            },
            status=status.HTTP_200_OK,
        )


class HistoricalProjectsDeleteAllAPIView(APIView):
    """Delete all finished owned projects for the current user."""

    permission_classes = [IsAuthenticated]

    def delete(self, request: Request) -> Response:
        user = cast(User, request.user)
        deleted_count = delete_all_finished_projects_for_user(user)
        return Response(
            {"deleted_count": deleted_count},
            status=status.HTTP_200_OK,
        )
