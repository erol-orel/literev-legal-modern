"""RAG workspace API views."""

from __future__ import annotations

import re

from typing import Any, cast

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from literev.libs.rag_workspace import build_rag_context, delete_rag_entry
from literev.libs.report_docx import build_report_docx
from literev.models import ProjectDocumentRAG, User

_DOCX_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


def _report_filename(question: str) -> str:
    """A safe ASCII ``.docx`` filename derived from the question."""
    slug = re.sub(r"[^a-z0-9]+", "-", (question or "").lower()).strip("-")
    return f"{slug[:60] or 'literev-report'}.docx"


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


class RagReportDocxAPIView(APIView):
    """Export a completed RAG analysis as a Word (.docx) memo.

    Reuses ``build_rag_context`` for auth + the summary/considerations/rule-of-
    law/tables, joins the per-decision answers, and streams the rendered
    document as an attachment. The heavy lifting (and every formatting choice)
    lives in the Django-free ``libs.report_docx`` module so it is unit-tested
    without a request.
    """

    permission_classes = [IsAuthenticated]

    def get(
        self,
        request: Request,
        project_id: int,
        rag_id: int,
    ) -> HttpResponse:
        context = build_rag_context(
            cast(User, request.user), project_id, rag_id
        )
        if not context:
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)
        current = context.get("current")
        if not current:
            return HttpResponse(status=status.HTTP_404_NOT_FOUND)

        answers: list[dict[str, Any]] = []
        document_rags = (
            ProjectDocumentRAG.objects.filter(project_rag_id=rag_id)
            .select_related("document")
            .order_by("id")
        )
        for document_rag in document_rags:
            document = document_rag.document
            decision_date = getattr(document, "decision_date", None)
            answers.append(
                {
                    "procedure_type": getattr(document, "procedure_type", ""),
                    "decision_type": getattr(document, "decision_type", ""),
                    "decision_date": (
                        decision_date.isoformat() if decision_date else ""
                    ),
                    "result": getattr(document, "result", ""),
                    "language": getattr(document, "language", "") or "",
                    "citation": document_rag.citation or "",
                    "answer": document_rag.answer or "",
                    "confidence_score": document_rag.confidence_score,
                }
            )

        payload = {
            "question": current.get("query", ""),
            "summary": current.get("summary_text", ""),
            "regle_droit": current.get("regle_droit", ""),
            "considerations": current.get("considerations", []),
            "counts": current.get("counts", {}),
            "percentages": current.get("percentages", {}),
            "show_closed_stats": current.get("show_closed_stats", False),
            "key_elements": current.get("key_elements", []),
            "law_articles": current.get("law_articles", []),
            "answers": answers,
        }

        content = build_report_docx(payload)
        response = HttpResponse(content, content_type=_DOCX_CONTENT_TYPE)
        filename = _report_filename(current.get("query", ""))
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
