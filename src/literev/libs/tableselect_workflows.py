import logging

from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from literev.libs.project_workflows import validate_project_access
from literev.libs.select_functions import download_finalcsv
from literev.libs.table_choice import (
    get_iteration,
    get_json_iterations_render,
    iterate_check_list,
    remove_iteration_get_parent,
    render_table_choice,
    reset_table_choice,
    sort_table_choice,
    update_check_list_iteration,
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
        order_by: str = "es_score",
    ):
        self.request = request
        self.project_id = self._validate_id(project_id, "project_id")
        self.refinement_id = self._validate_id(refinement_id, "refinement_id")
        self.iteration_id = self._validate_id(
            iteration_id, "iteration_id", allow_negative=True
        )
        self.current_page = max(1, num)
        self.order_by = order_by
        self.context = self._initialize_context()
        self.project = self._get_project()
        self.tablechoice = self._get_tablechoice()
        self.tablechoice_to_display = self.tablechoice.filter(to_display=True)
        self.total_documents = (
            self.tablechoice_to_display.count()  # Check if it is returning 0 if no records exists
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
            "error_message": "",  # Check this is not used
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
            logger.warning(f"Iteration limit reached: {current_iterations}")
        else:
            update_checked_document_page(
                self.request.user,
                self.project,
                check_list_yes,
                check_list_no,
                check_list_maybe,
            )

            update_check_list_iteration(
                self.request.user, self.project, self.iteration_id
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
            1,
            (self.total_documents + articles_per_page - 1)
            // articles_per_page,
        )

        if self.current_page > total_pages:
            self.current_page = total_pages

        first_doc = (self.current_page - 1) * articles_per_page
        last_doc = min(
            self.current_page * articles_per_page, self.total_documents
        )

        sorted_page_table_choice = sort_table_choice(
            self.project, self.tablechoice_to_display, self.order_by
        )[first_doc:last_doc]

        # TODO: split the returning tuple
        tablechoice_list, has_hdbscan_scores, has_es_scores = (
            render_table_choice(self.project, sorted_page_table_choice)
        )

        self.context.update(
            {
                "tablechoice_list": tablechoice_list,
                "current_page": self.current_page,
                "total_page": total_pages,
                "first_page": self.current_page == 1,
                "last_page": self.current_page == total_pages,
                "has_es_scores": has_es_scores,
                "hdbscan_scores": has_hdbscan_scores,
                "sort_by": self.order_by,
                "iterations": get_json_iterations_render(
                    self.refinement_id, self.iteration_id
                ),
                "number_Article_initial": self.tablechoice.filter(
                    is_initial=True
                ).count(),
                "number_Article_neighbour": self.tablechoice.filter(
                    is_initial=False, to_display=True
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
                        "order_by": self.order_by,
                    },
                )
            )

        return None

    def handle_post_actions(self) -> Optional[HttpResponse]:
        """Handle POST actions based on the 'submit' value."""

        # Check for get-iteration and remove iteration
        if self.request.POST.get("get-iteration") is not None:
            dest_iteration_id = self.request.POST.get("get-iteration")

            if dest_iteration_id is not None:
                get_iteration(
                    self.request.user,
                    self.project,
                    self.refinement_id,
                    int(dest_iteration_id),
                )
                return redirect(
                    reverse(
                        "tableselect",
                        kwargs={
                            "project_id": self.project_id,
                            "refinement_id": self.refinement_id,
                            "iteration_id": int(dest_iteration_id),
                            "num": 1,
                            "order_by": self.order_by,
                        },
                    )
                )

        if self.request.POST.get("remove-iteration") is not None:
            removed_iteration_id = self.request.POST.get("remove-iteration")

            if removed_iteration_id is not None:
                parent_id = remove_iteration_get_parent(
                    self.request.user,
                    self.project,
                    self.refinement_id,
                    int(removed_iteration_id),
                )

                if parent_id and self.iteration_id == int(
                    removed_iteration_id
                ):
                    get_iteration(
                        self.request.user,
                        self.project,
                        self.refinement_id,
                        parent_id,
                    )

                    return redirect(
                        reverse(
                            "tableselect",
                            kwargs={
                                "project_id": self.project_id,
                                "refinement_id": self.refinement_id,
                                "iteration_id": parent_id,
                                "num": 1,
                                "order_by": self.order_by,
                            },
                        )
                    )

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

        articles_per_page = getattr(settings, "NUMBER_ARTICLE_BY_PAGE", 10)

        total_pages = max(
            1,
            (self.total_documents + articles_per_page - 1)
            // articles_per_page,
        )

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
            return download_finalcsv(project=self.project)

        elif submit == "update_order":
            self.order_by = self.request.POST.get(
                "update_order_by", self.order_by
            )
            update_checked_document_page(
                self.request.user,
                self.project,
                check_list_yes,
                check_list_no,
                check_list_maybe,
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

        elif submit == "previous" and self.current_page > 1:
            update_checked_document_page(
                self.request.user,
                self.project,
                check_list_yes,
                check_list_no,
                check_list_maybe,
            )

            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                        "iteration_id": self.iteration_id,
                        "num": self.current_page - 1,
                        "order_by": self.order_by,
                    },
                )
            )

        elif submit == "next" and self.current_page < total_pages:
            update_checked_document_page(
                self.request.user,
                self.project,
                check_list_yes,
                check_list_no,
                check_list_maybe,
            )

            return redirect(
                reverse(
                    "tableselect",
                    kwargs={
                        "project_id": self.project_id,
                        "refinement_id": self.refinement_id,
                        "iteration_id": self.iteration_id,
                        "num": self.current_page + 1,
                        "order_by": self.order_by,
                    },
                )
            )

        return None
