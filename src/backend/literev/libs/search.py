from __future__ import annotations

import datetime

from typing import Any, Sequence, TypedDict

from django.contrib.auth.models import User
from django.utils import timezone

from literev.libs.parsing import process_search_query
from literev.libs.utils import get_number_documents
from literev.models import Project

SEARCH_SOURCE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("chambre_administrative", "Chambre Administrative"),
    ("chambre_penale", "Chambre Penale"),
    ("chambre_civile", "Chambre Civile"),
    # Swiss federal courts, populated via `manage.py import_entscheidsuche`.
    ("bundesgericht", "Tribunal fédéral (Bundesgericht)"),
    ("bundesverwaltungsgericht", "Tribunal administratif fédéral"),
    ("bundesstrafgericht", "Tribunal pénal fédéral"),
)
SEARCH_SOURCE_VALUES = {value for value, _label in SEARCH_SOURCE_OPTIONS}


class SearchPayload(TypedDict):
    project_name: str
    selected_indices: list[str]
    natural_language_query: str
    query: str
    range_begin_date: datetime.date
    range_end_date: datetime.date


class SearchPreview(TypedDict):
    project_name: str
    selected_indices: list[str]
    natural_language_query: str
    query: str
    range_begin_date: str
    range_end_date: str
    total_documents: int
    clustering_min_documents: int
    can_cluster: bool
    can_continue: bool


def get_search_source_options() -> list[dict[str, str]]:
    """Return the supported jurisprudence source options."""
    return [
        {"value": value, "label": label}
        for value, label in SEARCH_SOURCE_OPTIONS
    ]


def validate_selected_indices(selected_indices: Sequence[str]) -> list[str]:
    """Validate and normalize the selected Elasticsearch indices."""
    cleaned_indices: list[str] = []

    for value in selected_indices:
        normalized_value = str(value).strip()
        if normalized_value and normalized_value not in cleaned_indices:
            cleaned_indices.append(normalized_value)

    if not cleaned_indices:
        raise ValueError(
            "The 'Select Source' field is required and cannot be empty. "
            "Please ensure a valid selection is made."
        )

    invalid_indices = [
        value for value in cleaned_indices if value not in SEARCH_SOURCE_VALUES
    ]
    if invalid_indices:
        raise ValueError("Invalid search source selection.")

    return cleaned_indices


def validate_date_range(
    range_begin_date: datetime.date,
    range_end_date: datetime.date,
) -> tuple[datetime.date, datetime.date]:
    """Validate the inclusive decision date range."""
    if range_end_date < range_begin_date:
        raise ValueError(
            "Please provide an ending date equal to or more recent "
            "than the beginning date."
        )

    return range_begin_date, range_end_date


def normalize_boolean_query(query: str) -> str:
    """Validate and normalize a boolean search query."""
    cleaned_query = query.strip()
    if not cleaned_query:
        raise ValueError("This field may not be blank.")

    validated_search, (is_valid_query, error_in_query) = process_search_query(
        cleaned_query
    )
    if not is_valid_query:
        raise ValueError(str(error_in_query))

    return validated_search.replace("+", " ").strip()


def build_search_payload(data: dict[str, Any]) -> SearchPayload:
    """Build a normalized payload for search preview and creation."""
    range_begin_date, range_end_date = validate_date_range(
        data["range_begin_date"],
        data["range_end_date"],
    )

    return {
        "project_name": str(data["project_name"]).strip(),
        "selected_indices": validate_selected_indices(
            data["selected_indices"]
        ),
        "natural_language_query": str(
            data.get("natural_language_query", "")
        ).strip(),
        "query": normalize_boolean_query(str(data["query"])),
        "range_begin_date": range_begin_date,
        "range_end_date": range_end_date,
    }


def count_search_documents(payload: SearchPayload) -> int:
    """Count the total number of matching documents for the payload."""
    return sum(
        get_number_documents(
            index_name,
            payload["query"],
            payload["range_begin_date"],
            payload["range_end_date"],
        )
        for index_name in payload["selected_indices"]
    )


def build_search_preview(
    payload: SearchPayload,
    clustering_min_documents: int,
) -> SearchPreview:
    """Build the preview payload returned by the search preview API."""
    total_documents = count_search_documents(payload)

    return {
        "project_name": payload["project_name"],
        "selected_indices": payload["selected_indices"],
        "natural_language_query": payload["natural_language_query"],
        "query": payload["query"],
        "range_begin_date": payload["range_begin_date"].isoformat(),
        "range_end_date": payload["range_end_date"].isoformat(),
        "total_documents": total_documents,
        "clustering_min_documents": clustering_min_documents,
        "can_cluster": total_documents >= clustering_min_documents,
        "can_continue": total_documents > 0,
    }


def create_search_project(
    user: User,
    payload: SearchPayload,
    total_documents: int,
) -> Project:
    """Create a project from a validated search payload."""
    return Project.objects.create(
        user=user,
        name=payload["project_name"],
        creation_date=timezone.now().date(),
        query=payload["query"],
        natural_language_query=payload["natural_language_query"],
        range_begin_date=payload["range_begin_date"],
        range_end_date=payload["range_end_date"],
        total_documents=total_documents,
        selected_indices=payload["selected_indices"],
    )


def create_and_launch_search_project(
    user: User,
    payload: SearchPayload,
    total_documents: int | None = None,
) -> tuple[Project, bool]:
    """Create a project and launch the asynchronous processing workflow."""
    if total_documents is None:
        total_documents = count_search_documents(payload)

    project = create_search_project(user, payload, total_documents)
    from literev.tasks import launch_process

    process_started = launch_process(project)

    if not process_started:
        project.delete()

    return project, process_started
