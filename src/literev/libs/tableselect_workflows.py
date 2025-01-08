import logging
import math

from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from literev.libs.project_workflows import validate_project_access
from literev.libs.table_choice import (
    get_iteration,
    get_json_iterations_render,
    iterate_check_list,
    render_table_choice,
    reset_table_choice,
    sort_table_choice,
    update_checked_document_page,
)
from literev.models import Project, RefinementIteration, TableChoice

logger = logging.getLogger(__name__)


class TableSelectHandler:
    def __init__(
        self,
        request: HttpRequest,
        project_id: int,
        refinement_id: int,
        iteration_id: int,
        num: int,
        order_by: str,
    ):
        self.request = request
        self.project_id = self._validate_id(project_id, "project_id")
        self.refinement_id = self._validate_id(refinement_id, "refinement_id")
        self.iteration_id = self._validate_id(
            iteration_id, "iteration_id", allow_negative=True
        )
        self.num = max(1, num)
        self.order_by = order_by or "decision_date"
        self.context = self._initialize_context()
        self.project = self._get_project()
        self.tablechoice = self._get_tablechoice()
        self.total_documents = (
            self.tablechoice.count() if self.tablechoice else 0
        )

    def _validate_id(
        self, value: int, name: str, allow_negative: bool = False
    ) -> int:
        """Validate that the provided ID is valid."""
        if value is None or (not allow_negative and value <= 0):
            logger.error(f"Invalid or missing {name}: {value}")
            raise ValueError(f"{name} is invalid.")

        return value

    def _initialize_context(self) -> dict[str, Any]:
        """Initialize the context with default values."""

        return {
            "iterations_limit_exceeded": False,
            "processing_filters": False,
            "has_es_scores": False,
            "error_message": "",
        }

    def _get_project(self) -> Optional[Project]:
        """Retrieve the project and ensure it has a valid ID."""
        project = validate_project_access(self.request.user, self.project_id)
        if not project:
            logger.warning(
                f"Unauthorized access attempt for project ID: {self.project_id}"
            )

        return project

    def _get_tablechoice(self) -> Optional[TableChoice]:
        """Fetch table choice for the user and project."""

        return TableChoice.objects.filter(
            user=self.request.user, project=self.project
        )

    def _handle_iterate_action(
        self,
        check_list_yes: list[int],
        check_list_no: list[int],
        check_list_maybe: list[int],
    ) -> Optional[HttpResponse]:
        """Handle the iteration action and redirect as needed."""
        iteration_limit = getattr(settings, "LIMIT_NUMBER_ITERATIONS", 10)
        current_iterations = RefinementIteration.objects.filter(
            refinement_id=self.refinement_id
        ).count()

        if current_iterations >= iteration_limit:
            self.context["iterations_limit_exceeded"] = True
            logger.warning(
                f"Iteration limit reached for refinement ID: {self.refinement_id}"
            )
        else:
            update_checked_document_page(
                self.request.user,
                self.project,
                check_list_yes,
                check_list_no,
                check_list_maybe,
            )
            iterate_check_list(
                self.request.user,
                self.project,
                self.refinement_id,
                self.iteration_id,
            )
            return redirect(
                reverse(
                    "tableselect-default",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                    },
                )
            )

        return None

    def get_context(self) -> dict[str, Any]:
        """Build the context for rendering the template."""
        articles_per_page = getattr(settings, "NUMBER_ARTICLE_BY_PAGE", 10)
        total_pages = max(
            1, math.ceil(self.total_documents / articles_per_page)
        )

        self.num = min(self.num, total_pages)
        first_doc = (self.num - 1) * articles_per_page
        last_doc = self.num * articles_per_page

        sorted_table_choice = sort_table_choice(
            self.project, self.tablechoice, self.order_by
        )[first_doc:last_doc]
        tablechoice_list, _, has_es_scores = render_table_choice(
            self.project, sorted_table_choice
        )

        if has_es_scores:
            self.order_by = "-es_score"

        self.context.update(
            {
                "tablechoice_list": tablechoice_list,
                "current_page": self.num,
                "total_page": total_pages,
                "first_page": self.num == 1,
                "last_page": self.num == total_pages,
                "has_es_scores": has_es_scores,
                "sort_by": self.order_by,
                "iterations": get_json_iterations_render(
                    self.refinement_id, self.iteration_id
                ),
                "number_Article_initial": self.tablechoice.filter(
                    is_initial=True
                ).count(),
                "number_Article_neighbour": self.tablechoice.filter(
                    is_initial=False
                ).count(),
                "number_Article_chosen": self.tablechoice.filter(
                    is_check=True
                ).count(),
            }
        )

        return self.context

    def get_iteration_redirect(self) -> Optional[HttpResponse]:
        """Redirect to the latest iteration if no iteration ID is provided."""
        last_iteration = RefinementIteration.objects.filter(
            refinement_id=self.refinement_id
        ).last()
        if last_iteration:
            get_iteration(
                self.request.user,
                self.project,
                self.refinement_id,
                last_iteration.id,
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                        "iteration_id": last_iteration.id,
                        "num": 1,
                        "order_by": self.order_by or "-decision_date",
                    },
                )
            )

        return None

    def handle_post_actions(self) -> Optional[HttpResponse]:
        """Handle POST actions based on the 'submit' value."""
        submit = self.request.POST.get("submit")
        check_list_yes = [
            int(id) for id in self.request.POST.getlist("yes_row", [])
        ]
        check_list_no = [
            int(id) for id in self.request.POST.getlist("no_row", [])
        ]
        check_list_maybe = [
            int(id) for id in self.request.POST.getlist("maybe_row", [])
        ]

        if submit == "iterate":
            return self._handle_iterate_action(
                check_list_yes, check_list_no, check_list_maybe
            )
        elif submit == "reset":
            reset_table_choice(
                self.request.user, self.project, self.refinement_id
            )
            return redirect(
                reverse(
                    "tableselect-default",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                    },
                )
            )
        elif submit == "finish":
            update_checked_document_page(
                self.request.user,
                self.project,
                check_list_yes,
                check_list_no,
                check_list_maybe,
            )
            return None
        elif submit == "update_order":
            self.order_by = self.request.POST.get(
                "update_order_by", self.order_by
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                        "iteration_id": self.iteration_id,
                        "num": 1,
                        "order_by": self.order_by,
                    },
                )
            )
        elif submit in ["previous", "next"]:
            target_page = (
                self.num - 1 if submit == "previous" else self.num + 1
            )
            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                        "iteration_id": self.iteration_id,
                        "num": target_page,
                        "order_by": self.order_by,
                    },
                )
            )

        return None
