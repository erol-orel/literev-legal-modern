"""API views."""

from __future__ import annotations

import logging

from django.conf import settings
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rago.generation import OpenAIGen
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


class ConvertToBooleanQueryAPIView(APIView):
    """
    Convert natural language queries to boolean queries for jurisprudence.
    """

    permission_classes = [IsAuthenticated]

    def get(
        self,
        request: Request,
        natural_lenguage: str,
        api_key: str = settings.OPENAI_API_KEY,
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
        api_key : str
            OpenAI API key for the language model.

        Returns
        -------
        Response
            A JSON response containing the translated boolean query.
        """
        # PROMPT_TEMPLATE = """
        # Translate the following question into a boolean query suitable for jurisprudence.
        # Adhere to the following rules:
        # - Ensure all key concepts and terms from the question are included in the query.
        # - Use "AND" to combine distinct concepts.
        # - Use "OR" to include synonyms or related terms for a concept.
        # - Use "NOT" to exclude terms, where negations such as "sans" should exclude the associated terms.
        # - "NOT" must directly precede the term it excludes, and avoid using "AND NOT".
        # - Wrap multi-word terms (composed words) in double quotes.
        # - Use parentheses to group terms where appropriate.
        # - Ensure the boolean query is valid and includes all relevant terms from the question, properly handling negations like "sans."
        # - Return only the boolean query, without any explanation or extra text.

        # Question:
        # {context}
        PROMPT_TEMPLATE = """
        Translate the following question into a Boolean query suitable for jurisprudence.
        Strictly follow these rules to ensure accuracy, logical correctness, and reproducibility:
        **GENERAL RULES:**
        - Do NOT remove, modify, reorder, or omit any terms unless necessary for logical correctness.
        - Ensure all key concepts and terms from the question are included in the Bolean query.
        - Ensure the boolean query is valid and includes all relevant terms from the question.
        - Wrap multi-word phrases in double quotes (e.g., `"breach of contract"`).
        - NEVER wrap single-word terms in double quotes.
        - Boolean operators MUST be UPPER CASE: AND, OR, NOT.
        - Use `AND` to combine distinct legal concepts.
        - Group synonyms with `OR`, wrapped in parentheses, even with only two terms.
        - Do NOT use `AND` inside `OR` groups.
        - Avoid extra or unnecessary parentheses.
        - Maintain the original term order unless required for clarity.
        - The SAME input MUST ALWAYS produce the SAME Boolean query.
        **NEGATIONS (`NOT`):**
        - Express negations like `sans`, `excluding`, or `without` using `NOT`.
        - Multi-word exclusions MUST be in double quotes (e.g., `NOT "faute grave"`).
        - Apply `NOT` INDIVIDUALLY to each excluded term.
        - If the excluded terms form a multi-word phrase, they MUST remain enclosed in double quotes.
        - Correct: `"résolution amiable" AND "obligation contractuelle" NOT "défaut de paiement"`
        - Incorrect: `("résolution amiable" AND "obligation contractuelle") NOT défaut de paiement`
        - NEVER use `AND NOT` in the Boolean query.
        - Correct: `indemnisation NOT "retard injustifié"`
        - Incorrect: `indemnisation AND NOT "retard injustifié"`
        **SYNONYMS (`OR`):**
        - Group related terms inside parentheses with `OR`.
        - Example: `("préjudice moral" OR "dommage corporel") AND "responsabilité civile"`.
        **LEGAL CONTEXT:**
        - Preserve key legal expressions.
        - Example: `"absence de consentement"` must be represented as `("absence de consentement" OR "défaut de consentement" OR "vice du consentement")`.
        - Ensure precise, valid, and contextually accurate queries.

        Return only the Boolean query, with no extra text.

        Question:
        {context}

        Boolean Query:
        """

        try:
            gen = OpenAIGen(
                prompt_template=PROMPT_TEMPLATE,
                model_name="gpt-4o-mini",
                api_key=api_key,
                output_max_length=2048,
                temperature=0,
                api_params={
                    "top_p": 0.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                },
            )

            result = gen.generate(query="", context=[natural_lenguage])

            boolean_query = result.strip()

            return Response(
                {"query": boolean_query}, status=status.HTTP_200_OK
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
        if rag_id:
            project_rag = ProjectRAG.objects.get(project=project, id=rag_id)
        else:
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
