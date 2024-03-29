from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.generic import TemplateView

from literev.forms import SearchForm
from tasks.sample_tasks import add_one_task, run_pipeline


def run_task(request, number):
    if number:
        task = add_one_task.delay(number)
        return JsonResponse({"task_id": task.id}, status=202)


def run_pipeline_sample(request):
    task = run_pipeline()
    return JsonResponse({"task_id": task.id}, status=202)


class HomePageView(TemplateView):
    template_name = "home.html"


def search_search(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    search_form = SearchForm(request.POST)
    print("getting the search form")
    context["search_form"] = search_form

    if search_form.is_valid():
        print("valid form")
        project_name = search_form.cleaned_data["project_name"]
        search = search_form.cleaned_data["search"]
        range_begin_date = search_form.cleaned_data["range_begin_date"]
        range_end_date = search_form.cleaned_data["range_end_date"]

        number_documents = (
            100  # TODO: refactor to get the right number of documents
        )

        # enable continue message box
        context["continue_message_box"] = True

        new_data = {
            "project_name": project_name,
            "search": search,
            "range_begin_date": range_begin_date.strftime("%Y/%m/%d"),
            "range_end_date": range_end_date.strftime("%Y/%m/%d"),
            "number_documents": number_documents,
        }
        print("update")
        # update context variables
        context.update(new_data)
        # save in request session the data
        request.session.update(new_data)

    return context


def search(request: HttpRequest) -> HttpResponse:
    print("executing the search function")
    context: dict[str, Any] = dict()
    context["continue_message_box"] = False
    print(request.POST)
    if request.method != "POST":
        context["search_form"] = SearchForm()
        print("no post")
        return render(request, "search.html", context)

    submit = request.POST["submit"]

    if submit == "search":
        context = search_search(request, context)

    elif submit == "evaluate":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        context["search_form"] = SearchForm()
        return render(request, "search.html", context)

    elif submit == "continue":
        # TODO: Implement this create
        # create a Project object
        # send it to the back process
        context["search_form"] = SearchForm()
        return render(request, "search.html", context)

    elif submit == "cancel":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        context["search_form"] = SearchForm()
        return render(request, "search.html", context)

    return render(request, "search.html", context)


class SearchPageView(TemplateView):
    template_name = "search.html"


class RunningPageView(TemplateView):
    template_name = "running.html"
