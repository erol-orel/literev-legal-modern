from __future__ import annotations

import json
import re

from typing import Any, TypedDict

from django.urls import reverse

from literev.libs.project_workflows import validate_project_access
from literev.models import (
    Document,
    Project,
    ProjectDocumentRAG,
    ProjectRAG,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
    User,
)


class RagHistoryEntry(TypedDict):
    id: int
    query: str
    status: str
    status_display: str
    valid_answer_count: int
    num_documents: int
    created_at: str


class RagReference(TypedDict):
    id: int
    procedure_type: str


class RagContext(TypedDict, total=False):
    project: dict[str, Any]
    current: dict[str, Any] | None
    history: list[RagHistoryEntry]
    documents_ids: list[int]
    number_documents: int
    refinement: dict[str, int | None]
    urls: dict[str, str]


SECTION_INDICES = {
    "chambre_penale",
    "chambre_civile",
    "chambre_administrative",
}


def _parse_summary_answer(summary_answer: Any) -> dict[str, Any]:
    if isinstance(summary_answer, str):
        try:
            return json.loads(summary_answer)
        except json.JSONDecodeError:
            return {"summary": "", "considerations": []}
    if isinstance(summary_answer, dict):
        return summary_answer
    return {"summary": "", "considerations": []}


def _serialize_history(project: Project) -> list[RagHistoryEntry]:
    history: list[RagHistoryEntry] = []
    for rag in ProjectRAG.objects.filter(project=project).order_by(
        "-created_at"
    ):
        history.append(
            {
                "id": rag.id,
                "query": rag.query,
                "status": rag.status,
                "status_display": rag.get_status_display(),
                "valid_answer_count": rag.valid_answer_count,
                "num_documents": rag.num_documents,
                "created_at": rag.created_at.isoformat(),
            }
        )
    return history


def _resolve_references(value: Any) -> list[RagReference]:
    if isinstance(value, list):
        doc_ids = [int(num) for num in value]
    else:
        doc_ids = [int(num) for num in re.findall(r"\d+", str(value))]

    references: list[RagReference] = []
    for doc_id in doc_ids:
        document = Document.objects.filter(id=doc_id).first()
        if document:
            references.append(
                {"id": document.id, "procedure_type": document.procedure_type}
            )
    return references


def _normalize_reference_table(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []

    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cleaned: dict[str, Any] = {}
        for key, value in row.items():
            if key == "references":
                cleaned[key] = _resolve_references(value)
            else:
                cleaned[key] = value
        normalized.append(cleaned)
    return normalized


def _build_current_rag(
    project: Project,
    project_rag: ProjectRAG,
) -> dict[str, Any]:
    has_section_ans = bool(
        SECTION_INDICES.intersection(project.selected_indices)
    )
    summary_data = _parse_summary_answer(project_rag.summary_answer)

    considerations: list[dict[str, Any]] = []
    raw_considerations = summary_data.get("considerations", [])
    if isinstance(raw_considerations, list):
        for item in raw_considerations:
            if isinstance(item, dict):
                considerations.append(
                    {
                        "text": item.get("text", "").strip(),
                        "frequency": item.get("frequency", 0),
                        "percent": item.get("percent", 0.0),
                        "procedure_types": item.get("procedure_types", []),
                    }
                )

    considerations.sort(
        key=lambda entry: float(entry.get("percent", 0.0) or 0.0),
        reverse=True,
    )

    stats = getattr(project_rag, "stats", None)
    counts = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}
    percentages = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}
    show_closed_stats = False

    if stats and stats.classification_stats:
        if "counts" in stats.classification_stats:
            show_closed_stats = True
            counts = stats.classification_stats.get("counts", counts)
            percentages = stats.classification_stats.get(
                "percentages", percentages
            )

    has_confidence_score = False
    first_document_rag = ProjectDocumentRAG.objects.filter(
        project_rag=project_rag
    ).first()
    if first_document_rag:
        has_confidence_score = first_document_rag.confidence_score is not None

    return {
        "id": project_rag.id,
        "query": project_rag.query,
        "status": project_rag.status,
        "status_display": project_rag.get_status_display(),
        "summary_text": summary_data.get("summary", ""),
        "considerations": considerations,
        "regle_droit": summary_data.get("regle_droit", ""),
        "key_elements": _normalize_reference_table(
            summary_data.get("key_elements", [])
        ),
        "law_articles": _normalize_reference_table(
            summary_data.get("law_articles", [])
        ),
        "show_closed_stats": show_closed_stats,
        "counts": counts,
        "percentages": percentages,
        "has_section_ans": has_section_ans,
        "has_confidence_score": has_confidence_score,
        "valid_answer_count": project_rag.valid_answer_count,
        "num_documents": project_rag.num_documents,
    }


def _build_back_url(
    project: Project,
    refinement: ProjectRefinement | None,
    iteration: RefinementIteration | None,
) -> str:
    if refinement and iteration:
        return reverse(
            "tableselect",
            kwargs={
                "project_id": project.id,
                "refinement_id": refinement.id,
                "iteration_id": iteration.id,
                "num": 1,
                "order_by": "es_score",
            },
        )
    return reverse("projectpage", args=[project.id])


def build_rag_context(
    user: User,
    project_id: int,
    rag_id: int | None = None,
) -> RagContext | None:
    project = validate_project_access(user, project_id)
    if not project:
        return None

    documents_ids = list(
        TableChoice.objects.filter(
            project=project, user=user, is_check=True
        ).values_list("document_id", flat=True)
    )

    last_refinement = (
        ProjectRefinement.objects.filter(project=project)
        .order_by("-id")
        .first()
    )
    last_iteration = (
        RefinementIteration.objects.filter(refinement=last_refinement)
        .order_by("-id")
        .first()
        if last_refinement
        else None
    )

    current_rag: dict[str, Any] | None = None
    if rag_id:
        project_rag = ProjectRAG.objects.filter(
            project=project, id=rag_id
        ).first()
        if project_rag:
            current_rag = _build_current_rag(project, project_rag)

    context: RagContext = {
        "project": {
            "id": project.id,
            "name": project.name,
            "natural_language_query": project.natural_language_query or "",
        },
        "current": current_rag,
        "history": _serialize_history(project),
        "documents_ids": documents_ids,
        "number_documents": len(documents_ids),
        "refinement": {
            "id": last_refinement.id if last_refinement else None,
            "iteration_id": last_iteration.id if last_iteration else None,
        },
        "urls": {
            "back": _build_back_url(project, last_refinement, last_iteration),
            "rag_base": reverse("project-rag-page", args=[project.id]),
        },
    }
    return context


def delete_rag_entry(user: User, project_id: int, rag_id: int) -> bool:
    project = validate_project_access(user, project_id)
    if not project:
        return False

    deleted, _ = ProjectRAG.objects.filter(project=project, id=rag_id).delete()
    return deleted > 0
