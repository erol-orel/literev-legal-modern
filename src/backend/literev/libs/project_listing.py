from __future__ import annotations

from typing import TypedDict, cast

from django.conf import settings
from django.db.models import Q, QuerySet

from literev.libs.historical_functions import (
    filter_and_sort_projects,
    sort_all_projects,
)
from literev.libs.pipeline import running_restart
from literev.libs.utils import count_trials, get_shared_projects_ids
from literev.models import ClusterElement, Document, Project, User


class ProjectProgress(TypedDict, total=False):
    kind: str
    current: int
    label: str
    max: int
    message: str
    percentage: int


class ProjectListItem(TypedDict):
    best_dbcv: float
    can_delete: bool
    can_open_project: bool
    can_restart: bool
    creation_date: str
    id: int
    is_finish: bool
    is_shared: bool
    processed_documents: int
    project_url: str
    query: str
    range_begin_date: str
    range_end_date: str
    selected_indices: list[str]
    step: str
    step_label: str
    progress: ProjectProgress
    name: str
    total_documents: int


ALLOWED_SORT_TYPES = {"more_documents_first", "less_documents_first"}


def get_accessible_projects(user: User) -> QuerySet[Project]:
    """Return projects visible to the current user."""
    shared_ids = get_shared_projects_ids()
    return Project.objects.filter(Q(user=user) | Q(id__in=shared_ids))


def get_running_projects(user: User) -> QuerySet[Project]:
    """Return accessible running projects ordered from newest to oldest."""
    return (
        get_accessible_projects(user).exclude(is_finish=True).order_by("-id")
    )


def get_accessible_project(user: User, project_id: int) -> Project | None:
    """Return one accessible project or ``None`` if access is denied."""
    return get_accessible_projects(user).filter(id=project_id).first()


def is_shared_project(project: Project) -> bool:
    """Return whether the project belongs to the shared-project pool."""
    return project.id in get_shared_projects_ids()


def count_processed_documents(project: Project) -> int:
    """Count processed documents using the same semantics as the legacy UI."""
    documents_count = Document.objects.filter(project=project).count()

    if documents_count < project.total_documents:
        return documents_count

    if (
        "chambre_penale" in project.selected_indices
        or "chambre_civile" in project.selected_indices
        or "chambre_administrative" in project.selected_indices
    ):
        return documents_count

    return ClusterElement.objects.filter(cluster__project=project).count()


def _percentage(current: int, total: int) -> int:
    if total <= 0:
        return 0
    return int(current / total * 100)


def build_project_progress(project: Project) -> ProjectProgress:
    """Build the progress payload shown by the running projects page."""
    step = project.step

    if step == "getting_documents":
        current = Document.objects.filter(project=project).count()
        return {
            "kind": "progress",
            "current": current,
            "label": f"{current}/{project.total_documents}",
            "max": project.total_documents,
            "message": "Collecting documents",
            "percentage": _percentage(current, project.total_documents),
        }

    if step == "preparing":
        current = (
            Document.objects.filter(project=project)
            .exclude(prepared_for_ngrams="")
            .count()
        )
        return {
            "kind": "progress",
            "current": current,
            "label": f"{current}/{project.total_documents}",
            "max": project.total_documents,
            "message": "Preparing documents",
            "percentage": _percentage(current, project.total_documents),
        }

    if step == "clustering":
        current = count_trials(project)
        total_trials = int(settings.NUMBER_TRIALS)
        return {
            "kind": "progress",
            "current": current,
            "label": f"Trial {current}/{total_trials}",
            "max": total_trials,
            "message": "Clustering documents",
            "percentage": _percentage(current, total_trials),
        }

    if step == "preprocessing":
        return {
            "kind": "status",
            "label": "Preprocessing",
            "message": "Preprocessing documents",
        }

    if step == "question-answering":
        return {
            "kind": "status",
            "label": "Question Answering",
            "message": "Generating question-answering results",
        }

    if step == "plotting":
        return {
            "kind": "status",
            "label": "Plotting",
            "message": "Creating plot results",
        }

    return {
        "kind": "status",
        "label": step.replace("-", " ").replace("_", " ").title(),
        "message": step.replace("-", " ").replace("_", " ").title(),
    }


def _step_label(step: str) -> str:
    if step == "question-answering":
        return "Asking"
    return step.replace("-", " ").replace("_", " ").title()


def serialize_project(project: Project) -> ProjectListItem:
    """Serialize one project for the running/historical React pages."""
    shared = is_shared_project(project)
    progress = build_project_progress(project)
    return {
        "best_dbcv": float(project.best_dbcv),
        "can_delete": not shared,
        "can_open_project": project.step != "getting_documents",
        "can_restart": not shared and not project.is_finish,
        "creation_date": project.creation_date.isoformat(),
        "id": project.id,
        "is_finish": bool(project.is_finish),
        "is_shared": shared,
        "name": project.name,
        "processed_documents": count_processed_documents(project),
        "progress": progress,
        "project_url": f"/project/{project.id}/",
        "query": project.query,
        "range_begin_date": project.range_begin_date.isoformat(),
        "range_end_date": project.range_end_date.isoformat(),
        "selected_indices": cast(list[str], project.selected_indices),
        "step": project.step,
        "step_label": _step_label(project.step),
        "total_documents": project.total_documents,
    }


def list_running_projects(user: User) -> list[ProjectListItem]:
    """Serialize running projects for the current user."""
    return [
        serialize_project(project) for project in get_running_projects(user)
    ]


def normalize_sort_type(sort_type: str) -> str:
    """Normalize a historical sort type to the supported values."""
    if sort_type in ALLOWED_SORT_TYPES:
        return sort_type
    return "more_documents_first"


def list_historical_projects(
    user: User,
    search: str = "",
    sort_type: str = "more_documents_first",
) -> list[ProjectListItem]:
    """Serialize historical projects with optional search and sorting."""
    normalized_sort_type = normalize_sort_type(sort_type)
    normalized_search = search.strip()
    keywords = normalized_search.split()

    if keywords:
        queryset = filter_and_sort_projects(
            user, keywords, normalized_sort_type
        )
    else:
        queryset = sort_all_projects(user, normalized_sort_type)

    return [serialize_project(project) for project in queryset]


def delete_project(user: User, project_id: int) -> bool:
    """Delete an owned project and return whether deletion was allowed."""
    project = get_accessible_project(user, project_id)
    if not project or is_shared_project(project) or project.user != user:
        return False

    from literev.tasks import running_delete

    running_delete(project.id)
    return True


def restart_project(user: User, project_id: int) -> bool:
    """Restart an owned running project and return whether it was allowed."""
    project = get_accessible_project(user, project_id)
    if (
        not project
        or is_shared_project(project)
        or project.user != user
        or project.is_finish
    ):
        return False

    running_restart(str(project.id))
    return True


def delete_all_finished_projects_for_user(user: User) -> int:
    """Delete all finished owned projects and return the number targeted."""
    project_ids = list(
        Project.objects.filter(user=user, is_finish=True).values_list(
            "id", flat=True
        )
    )
    from literev.tasks import remove_all_finished_projects

    remove_all_finished_projects(user)
    return len(project_ids)
