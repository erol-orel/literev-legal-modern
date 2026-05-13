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
from literev.libs.utils import get_shared_projects_ids
from literev.models import Project, ProjectDocumentRAG, ProjectRAG


class ProjectRAGbyProjectIdAPIView(APIView):
    """Handle ProjectRAG by Project ID."""

    permission_classes = [IsAuthenticated]

    def get(
        self, request: Request, project_id: int, rag_id: int = 0
    ) -> Response:
        """Handle GET requests to fetch ProjectRAG data based on project_id or rag_id."""
        project = get_object_or_404(Project, pk=project_id)

        if (
            project.user != request.user
            and project.id not in get_shared_projects_ids()
        ):
            raise PermissionDenied(
                "You do not have permission to access this project."
            )

        project_rag: ProjectRAG | None
        if rag_id:
            project_rag = get_object_or_404(
                ProjectRAG, project=project, id=rag_id
            )
        else:
            project_rag = ProjectRAG.objects.filter(project=project).last()

        if not project_rag:
            return Response({}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProjectRAGSerializer(project_rag)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request: Request, project_id: int) -> Response:
        """Create a new ProjectRAG entry for the provided document list."""
        query = request.data.get("query", "")
        document_ids = request.data.get("documents_ids", [])

        if not project_id or not isinstance(document_ids, list) or not query:
            return Response(
                {
                    "error": (
                        "project_id, query, and a list of document ids are required."
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
            query=query.strip(),
            project=project,
            status="in-progress",
        )

        from literev.tasks import task_rag_result_table

        task_rag_result_table.s(project_rag.id, document_ids).apply_async()

        serializer = ProjectRAGSerializer(project_rag)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProjectRAGViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ProjectRAG entries."""

    permission_classes = [IsAuthenticated]
    queryset = ProjectRAG.objects.all()
    serializer_class = ProjectRAGSerializer


class ProjectDocumentRAGViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ProjectDocumentRAG entries."""

    permission_classes = [IsAuthenticated]
    queryset = ProjectDocumentRAG.objects.select_related("document").all()
    serializer_class = ProjectDocumentRAGSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project_rag"]
