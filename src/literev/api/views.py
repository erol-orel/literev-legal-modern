"""API views."""

from __future__ import annotations

import json
import logging

from typing import Any

from django.conf import settings
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from openai import OpenAI
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

MODEL_OPENAI = "gpt-4.1-mini"
OPENAI_API_KEY = settings.OPENAI_API_KEY


class ConvertToBooleanQueryAPIView(APIView):
    """
    Convert natural language queries to boolean queries for jurisprudence.
    """

    permission_classes = [IsAuthenticated]

    def extract_json(self, text: str) -> dict:
        """Extract json text from the openai response."""
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("No JSON found")
            return json.loads(text[start : end + 1])

    def concepts_to_es_query(self, concepts_json: dict) -> dict:
        """Convert concept_json to a valid elastic search query dict."""
        must: list[dict[str, Any]] = []
        should: list[dict[str, Any]] = []
        for c in concepts_json["concepts"]:
            group = {
                "bool": {
                    "should": [
                        {"match_phrase": {"document_text": s}}
                        for s in c["synonyms"]
                    ],
                    # "minimum_should_match": 1, # commented because the criteria to search is match_phrase instead of match
                }
            }
            (must if c["importance"] == "must" else should).append(group)

        query = {"query": {"bool": {"must": must}}}
        if should:
            query["query"]["bool"]["should"] = should
            query["query"]["bool"]["minimum_should_match"] = 1  # type: ignore

        return query

    def extract_legal_concepts(self, question: str) -> dict:
        """Ask to openai extract dict concepts from a question."""
        SYSTEM_PROMPT = """
            You are a legal information retrieval expert.

            Extract key legal concepts from a French legal question.
            For each concept, produce legally equivalent expressions used in jurisprudence.

            Rules:
            - Deterministic output only
            - Normalize accents and hyphens
            - Lowercase everything
            - Output valid JSON only

            Schema:
            {
            "concepts": [
                {
                "core": "canonical concept",
                "synonyms": ["variant 1", "variant 2"],
                "importance": "must | should",
                "explanation": "why this concept matters for retrieval"
                }
            ]
            }
            """
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
        response = openai_client.chat.completions.create(
            model=MODEL_OPENAI,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question},
            ],
        )

        concepts = response.choices[0].message.content
        return self.extract_json(concepts) if concepts else {}

    def render_es_clause(self, clause: dict) -> str:
        """Render an Elasticsearch clause into a Boolean string."""

        if "match_phrase" in clause:
            term = next(iter(clause["match_phrase"].values()))
            return f'"{term}"'

        if "bool" in clause:
            bool_part = clause["bool"]
            parts = []

            if "must" in bool_part:
                must_rendered = [
                    self.render_es_clause(c) for c in bool_part["must"]
                ]
                parts.append(" AND ".join(must_rendered))

            if "should" in bool_part:
                should_rendered = [
                    self.render_es_clause(c) for c in bool_part["should"]
                ]
                parts.append("(" + " OR ".join(should_rendered) + ")")

            return " AND ".join(parts)

        raise ValueError(f"Unsupported ES clause structure: {clause}")

    def es_query_to_boolean_string(self, es_query: dict) -> str:
        """Convert a valid Elastic Search query dict to a boolean query string."""
        bool_query = es_query["query"]["bool"]

        parts = []

        for clause in bool_query.get("must", []):
            parts.append(self.render_es_clause(clause))

        for clause in bool_query.get("should", []):
            parts.append(self.render_es_clause(clause))

        return " AND ".join(parts)

    def get(
        self,
        request: Request,
        natural_lenguage: str,
    ) -> Response:
        """
        Handles GET requests to translate a natural language query
        into a boolean query.

        Parameters
        ----------
        request : Request
            The HTTP request object.
        natural_lenguage : str
            The natural language query string to convert.

        Returns
        -------
        Response
            A JSON response containing the translated boolean query.
        """

        try:
            concepts = self.extract_legal_concepts(natural_lenguage)
            es_query = self.concepts_to_es_query(concepts)

            boolean_query = self.es_query_to_boolean_string(es_query)

            return Response(
                {
                    "query": boolean_query,
                    "es_query": json.dumps(es_query),
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logging.error(f"Error generating boolean query: {e!s}")

            return Response(
                {
                    "error": "An error occurred while processing the request. Please try again later."
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ProjectRAGbyProjectIdAPIView(APIView):
    """Handle ProjectRAG by Project ID."""

    permission_classes = [IsAuthenticated]

    def get(
        self, request: Request, project_id: int, rag_id: int = 0
    ) -> Response:
        """
        Handle GET requests to fetch ProjectRAG data based on project_id or rag_id.
        """

        project = get_object_or_404(Project, pk=project_id)

        if (
            project.user != request.user
            and project.id not in get_shared_projects_ids()
        ):
            raise PermissionDenied(
                "You do not have permission to access this project."
            )

        project_rag: None | ProjectRAG = None
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
        """
        Handle POST requests to process a project_id and a list of IDs.

        Expects:
            project_id (int): The ID of the project.
            documents_ids (list[int]): A list of IDs (e.g., document or entity IDs).

        Returns:
            Response: A JSON response with the provided project_id and list of IDs.
        """
        query = request.data.get("query", "")
        document_ids = request.data.get("documents_ids", [])

        if not project_id or not isinstance(document_ids, list) or not query:
            return Response(
                {
                    "error": "project_id, query, and a list of document ids are required."
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

        # Disabled to avoid cache results
        # normalized_query = normalize_query(query)
        # matching_rags = (
        #     ProjectRAG.objects.filter(project=project)
        #     .annotate(normalized_query_db=Lower(Trim("query")))
        #     .filter(normalized_query_db=normalized_query)
        # )

        # doc_id_set = set(document_ids)
        # for rag in matching_rags:
        #     existing_doc_ids = set(
        #         ProjectDocumentRAG.objects.filter(project_rag=rag).values_list(
        #             "document_id", flat=True
        #         )
        #     )
        #     if doc_id_set == existing_doc_ids:
        #         # Reuse existing RAG
        #         serializer = ProjectRAGSerializer(rag)
        #         return Response(serializer.data, status=status.HTTP_200_OK)

        project_rag = ProjectRAG.objects.create(
            query=query.strip(),
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

        check_list_yes = request.data.get("selected_documents", [])
        check_list_no = request.data.get("deselected_documents", [])

        check_list_maybe = request.data.get("maybe_documents", [])

        if (
            not isinstance(check_list_yes, list)
            or not isinstance(check_list_no, list)
            or not isinstance(check_list_maybe, list)
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

        all_table_ids = check_list_yes + check_list_no + check_list_maybe

        table_choice = TableChoice.objects.filter(
            user=user, project=project, id__in=all_table_ids
        )

        if not table_choice.count():
            return

        table_choice.filter(id__in=check_list_yes).update(is_check=True)
        table_choice.filter(id__in=check_list_no).update(is_check=False)
        table_choice.filter(id__in=check_list_maybe).update(is_check=None)

        update_check_list_iteration(
            project=project, user=user, iteration_id=iteration_id
        )

        return Response(
            {"detail": "TableChoice updated successfully."},
            status=status.HTTP_200_OK,
        )


def normalize_query(text: str) -> str:
    return " ".join(text.strip().lower().split())
