"""Table-selection workspace API views."""

from __future__ import annotations

from typing import cast

from django.http import HttpResponse
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.table_selection import (
    activate_table_iteration,
    ask_selected_documents,
    build_table_selection_state,
    delete_table_iteration,
    export_selected_table_documents,
    get_accessible_project,
    get_project_refinement,
    iterate_table_selection,
    reset_table_selection_state,
    set_all_table_selection,
    update_table_selection,
)
from literev.models import User


class TableSelectionQuerySerializer(serializers.Serializer):
    """Validate state-query parameters for the table-selection page."""

    iteration_id = serializers.IntegerField(required=False, min_value=1)
    order_by = serializers.CharField(required=False, allow_blank=True)
    page = serializers.IntegerField(required=False, min_value=1, default=1)


class TableSelectionUpdateSerializer(serializers.Serializer):
    """Validate page-level table-selection update payloads."""

    deselected_documents = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )
    iteration_id = serializers.IntegerField(required=False, min_value=1)
    maybe_documents = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )
    selected_documents = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
    )


class TableSelectionCheckAllSerializer(serializers.Serializer):
    """Validate the mode used for bulk table-selection updates."""

    iteration_id = serializers.IntegerField(required=False, min_value=1)
    mode = serializers.ChoiceField(choices=["yes", "maybe"])


class TableSelectionStateAPIView(APIView):
    """Return the table-selection workspace payload for the React page."""

    permission_classes = [IsAuthenticated]

    def get(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        serializer = TableSelectionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        payload = build_table_selection_state(
            cast(User, request.user),
            project_id=project_id,
            refinement_id=refinement_id,
            iteration_id=cast(
                int | None,
                serializer.validated_data.get("iteration_id"),
            ),
            page=cast(int, serializer.validated_data.get("page", 1)),
            order_by=cast(
                str | None,
                serializer.validated_data.get("order_by"),
            ),
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(payload, status=status.HTTP_200_OK)


class TableSelectionUpdateAPIView(APIView):
    """Persist current page selections before navigation or actions."""

    permission_classes = [IsAuthenticated]

    def put(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TableSelectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_table_selection(
            user=user,
            project=project,
            iteration_id=cast(
                int | None,
                serializer.validated_data.get("iteration_id"),
            ),
            selected_documents=cast(
                list[int], serializer.validated_data["selected_documents"]
            ),
            deselected_documents=cast(
                list[int], serializer.validated_data["deselected_documents"]
            ),
            maybe_documents=cast(
                list[int], serializer.validated_data["maybe_documents"]
            ),
        )

        return Response(
            {"detail": "Table selection updated successfully."},
            status=status.HTTP_200_OK,
        )


class TableSelectionIterationActivateAPIView(APIView):
    """Load a specific iteration into the working table-selection state."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
        iteration_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        payload = activate_table_iteration(
            user,
            project,
            refinement_id,
            iteration_id,
            order_by=request.data.get("order_by", "es_score"),
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(payload, status=status.HTTP_200_OK)


class TableSelectionIterationDetailAPIView(APIView):
    """Delete a non-root iteration from the table-selection history."""

    permission_classes = [IsAuthenticated]

    def delete(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
        iteration_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        payload = delete_table_iteration(
            user,
            project,
            refinement_id,
            iteration_id,
            order_by=request.query_params.get("order_by", "es_score"),
        )
        if not payload:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(payload, status=status.HTTP_200_OK)


class TableSelectionIterateAPIView(APIView):
    """Start the iterate workflow for the current table-selection state."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TableSelectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        iteration_id = cast(
            int | None, serializer.validated_data.get("iteration_id")
        )
        if not iteration_id:
            return Response(
                {"detail": "An active iteration is required to iterate."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            payload = iterate_table_selection(
                user=user,
                project=project,
                refinement_id=refinement_id,
                iteration_id=iteration_id,
                selected_documents=cast(
                    list[int], serializer.validated_data["selected_documents"]
                ),
                deselected_documents=cast(
                    list[int],
                    serializer.validated_data["deselected_documents"],
                ),
                maybe_documents=cast(
                    list[int], serializer.validated_data["maybe_documents"]
                ),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(payload, status=status.HTTP_200_OK)


class TableSelectionResetAPIView(APIView):
    """Reset the table-selection state to the root iteration."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        return Response(
            reset_table_selection_state(user, project, refinement_id),
            status=status.HTTP_200_OK,
        )


class TableSelectionCheckAllAPIView(APIView):
    """Set all currently displayed rows to yes or maybe."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TableSelectionCheckAllSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            set_all_table_selection(
                user=user,
                project=project,
                iteration_id=cast(
                    int | None,
                    serializer.validated_data.get("iteration_id"),
                ),
                mode=cast(str, serializer.validated_data["mode"]),
            )
        except ValueError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "Selection updated."},
            status=status.HTTP_200_OK,
        )


class TableSelectionExportAPIView(APIView):
    """Export the currently selected documents to CSV."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> HttpResponse | Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TableSelectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return export_selected_table_documents(
            user=user,
            project=project,
            iteration_id=cast(
                int | None,
                serializer.validated_data.get("iteration_id"),
            ),
            selected_documents=cast(
                list[int], serializer.validated_data["selected_documents"]
            ),
            deselected_documents=cast(
                list[int], serializer.validated_data["deselected_documents"]
            ),
            maybe_documents=cast(
                list[int], serializer.validated_data["maybe_documents"]
            ),
        )


class TableSelectionAskSelectedAPIView(APIView):
    """Persist current selections and return the RAG page URL."""

    permission_classes = [IsAuthenticated]

    def post(
        self,
        request: Request,
        project_id: int,
        refinement_id: int,
    ) -> Response:
        user = cast(User, request.user)
        project = get_accessible_project(user, project_id)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)

        refinement = get_project_refinement(project, refinement_id)
        if not refinement:
            return Response(status=status.HTTP_404_NOT_FOUND)

        serializer = TableSelectionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = ask_selected_documents(
            user=user,
            project=project,
            iteration_id=cast(
                int | None,
                serializer.validated_data.get("iteration_id"),
            ),
            selected_documents=cast(
                list[int], serializer.validated_data["selected_documents"]
            ),
            deselected_documents=cast(
                list[int], serializer.validated_data["deselected_documents"]
            ),
            maybe_documents=cast(
                list[int], serializer.validated_data["maybe_documents"]
            ),
        )
        return Response(payload, status=status.HTTP_200_OK)
