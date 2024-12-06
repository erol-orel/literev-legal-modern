"""API views."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.api.serializers import (
    ProjectDocumentRAGSerializer,
    ProjectRAGSerializer,
)
from literev.libs.table_choice import update_check_list_iteration
from literev.models import Project, ProjectDocumentRAG, ProjectRAG, TableChoice
from literev.tasks import get_shared_projects_ids, task_rag_result_table


class ProjectRAGbyProjectIdAPIView(APIView):
    """Handle ProjectRAG by Project ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, project_id: int) -> Response:
        """
        Handle GET requests to fetch data based on project_id.

        Parameters:
            project_id (int): The ID of the project.

        Returns:
            Response: A JSON response with the project_id.
        """

        project = get_object_or_404(Project, pk=project_id)

        if (
            project.user != request.user
            and project.id not in get_shared_projects_ids()
        ):
            raise PermissionDenied(
                "You do not have permission to access this project."
            )

        project_rag = ProjectRAG.objects.filter(project=project).last()

        serializer = ProjectRAGSerializer(project_rag)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request, project_id: int) -> Response:
        """
        Handle POST requests to process a project_id and a list of IDs.

        Expects:
            project_id (int): The ID of the project.
            documents_ids (list[int]): A list of IDs (e.g., document or entity IDs).

        Returns:
            Response: A JSON response with the provided project_id and list of IDs.
        """
        # Parse data from the request body
        query = request.data.get("query")
        document_ids = request.data.get("documents_ids", [])

        if not project_id or not isinstance(document_ids, list) or not query:
            return Response(
                {
                    "error": (
                        "project_id, query, and a list of "
                        "document ids are required."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        project = get_object_or_404(Project, pk=project_id)
        if (
            project.user != request.user
            and project_id not in get_shared_projects_ids()
        ):
            raise PermissionDenied(
                "You do not have permission to access this project."
            )

        project_rag = ProjectRAG.objects.create(
            query=query,
            project=project,
            status="in-progress",
        )

        task_rag_result_table.s(
            project_rag.id,
            document_ids,
        ).apply_async()

        serializer = ProjectRAGSerializer(project_rag)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectRAGViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ProjectRAG entries.
    """

    permission_classes = [IsAuthenticated]
    queryset = ProjectRAG.objects.all()
    serializer_class = ProjectRAGSerializer


class ProjectDocumentRAGViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ProjectDocumentRAG entries.
    """

    permission_classes = [IsAuthenticated]
    queryset = ProjectDocumentRAG.objects.select_related("document").all()
    serializer_class = ProjectDocumentRAGSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project_rag"]


class UpdateTableChoiceAPIView(APIView):
    """
    API View for updating TableChoice selections.
    """

    permission_classes = [IsAuthenticated]

    def put(
        self,
        request,
        project_id: int,
        iteration_id: int = -1,
        page: int = 1,
    ):
        """
        Update TableChoice selections for a specific page.

        Parameters
        ----------
        project_id:
            ID of the project.
        page:
            Current page number.
        selected_documents:
            List of document IDs to mark as selected.
        deselected_documents:
            List of document IDs to mark as deselected.
        iteration

        Notes
        -----
        Request body:
        {
            "selected_documents": [1, 2, 3],
            "deselected_documents": [4, 5, 6]
        }

        Returns
        -------
        HTTP 200: Success message.
        HTTP 403: Permission denied.
        HTTP 400: Invalid data.
        """
        user = request.user
        project = get_object_or_404(Project, id=project_id)

        # Check if the user has access to the project
        if (
            project.user != user
            and not project.id
            in get_shared_projects_ids()  # TODO: change this section to enable access to shared projects when implemented
        ):
            return Response(
                {
                    "detail": (
                        "You do not have permission to access this project."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        selected_documents = request.data.get("selected_documents", [])
        deselected_documents = request.data.get("deselected_documents", [])

        if not isinstance(selected_documents, list) or not isinstance(
            deselected_documents, list
        ):
            return Response(
                {
                    "detail": (
                        "Both 'selected_documents' and 'deselected_documents' "
                        "must be lists."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        TableChoice.objects.filter(
            user=user,
            project=project,
            id__in=selected_documents,
        ).update(is_check=True)

        TableChoice.objects.filter(
            user=user,
            project=project,
            id__in=deselected_documents,
        ).update(is_check=False)

        update_check_list_iteration(
            project=project, user=user, iteration_id=iteration_id
        )

        return Response(
            {"detail": "TableChoice updated successfully."},
            status=status.HTTP_200_OK,
        )
