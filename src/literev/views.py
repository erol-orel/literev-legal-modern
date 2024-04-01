from __future__ import annotations

import datetime

from typing import Any, Optional

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from literev.forms import SearchForm
from literev.libs.pipeline import launch_process
from literev.libs.utils import get_number_documents
from literev.models import (
    Project,
)
from tasks.sample_tasks import add_one_task, run_pipeline  # type: ignore


# TODO: check tht typing maybe is wrong
def run_task(request: HttpRequest, number: int) -> Optional[JsonResponse]:
    if number:
        task = add_one_task.delay(number)
        return JsonResponse({"task_id": task.id}, status=202)
    # Check this part this should return something?
    return None


def run_pipeline_sample(request: HttpRequest) -> JsonResponse:
    task = run_pipeline()
    return JsonResponse({"task_id": task.id}, status=202)


class HomePageView(TemplateView):
    template_name = "home.html"


def search_search(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    search_form = SearchForm(request.POST)
    context["search_form"] = search_form

    if search_form.is_valid():
        print("valid form")
        project_name = search_form.cleaned_data["project_name"]
        query = search_form.cleaned_data["query"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        total_documents = get_number_documents(
            query, range_begin_date, range_end_date
        )

        # enable continue message box
        context["continue_message_box"] = True

        new_data = {
            "project_name": project_name,
            "query": query,
            "range_begin_date": range_begin_date.strftime("%Y/%m/%d"),
            "range_end_date": range_end_date.strftime("%Y/%m/%d"),
            "total_documents": total_documents,
        }
        print("updatin request session")
        # update context variables
        context.update(new_data)
        # save in request session the data
        request.session.update(new_data)

    return context


def search_continue(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    # user = cast(User, request.user)
    project_name = request.session["project_name"]
    query = request.session["query"]
    range_begin_date = datetime.datetime.strptime(
        request.session["range_begin_date"], "%Y/%m/%d"
    ).date()
    range_end_date = datetime.datetime.strptime(
        request.session["range_end_date"], "%Y/%m/%d"
    ).date()

    total_documents = get_number_documents(
        query, range_begin_date, range_end_date
    )

    project = Project.objects.create(
        name=project_name,
        creation_date=datetime.datetime.now(),
        query=query,
        range_begin_date=range_begin_date,
        range_end_date=range_end_date,
        estimated_documents=total_documents,
    )

    result = launch_process(project)

    if result:
        context["message_project_created"] = (
            "You project has been created and is running"
        )
    else:
        context["message_project_created"] = "error in launching project"

    return context


def search_evaluate(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    search_form = SearchForm(request.POST)
    context["search_form"] = search_form

    if search_form.is_valid():
        print("evaluate valid form")
        # project_name = search_form.cleaned_data["project_name"]
        query = search_form.cleaned_data["query"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        total_documents = get_number_documents(
            query, range_begin_date, range_end_date
        )

        context["total_documents"] = total_documents

    return context


def search(request: HttpRequest) -> HttpResponse:
    print("executing the search function")
    context: dict[str, Any] = dict()

    # Actual form
    search_form = SearchForm()
    context["search_form"] = search_form

    # Aditional variables
    context["continue_message_box"] = False
    context["project_created_message"] = ""

    # if there no click in evaluate or create project
    # total documents = -1
    context["total_documents"] = -1

    if request.method != "POST":
        context["search_form"] = SearchForm()
        return render(request, "search.html", context)

    submit = request.POST["submit"]

    if submit == "search":
        print("search search")
        context = search_search(request, context)

    elif submit == "evaluate":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        print("search evaluate")
        context = search_evaluate(request, context)

    elif submit == "continue":
        context = search_continue(request, context)

        return render(request, "search.html", context)

    elif submit == "cancel":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        return render(request, "search.html", context)

    return render(request, "search.html", context)


def running(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()
    context["continue_message_box"] = False

    if request.method == "POST":
        submit = request.POST["submit"]
        if submit == "reload":
            pass

    projects = Project.objects.all().order_by("-id")
    context["projects"] = projects

    return render(request, "running.html", context)
