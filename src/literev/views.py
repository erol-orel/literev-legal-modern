from __future__ import annotations

import datetime

from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from literev.forms import SearchForm
from literev.libs.pipeline import (
    get_color_map,
    launch_process,
    running_restart,
)
from literev.libs.utils import get_number_documents
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
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
        total_documents=total_documents,
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

    elif submit == "cancel":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        pass

    return render(request, "search.html", context)


def running(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()
    context["continue_message_box"] = False

    if request.method == "POST":
        submit = request.POST["submit"]

        if submit == "reload":
            pass

        if submit == "restart":
            print(request.POST)
            project_id = request.POST["project_id"]
            running_restart(project_id)

        if submit == "delete":
            ...
            # project_id = request.POST["project_id"]
            # running_delete(project_id)

    projects = Project.objects.all().order_by("-id")
    context["projects"] = projects

    return render(request, "running.html", context)


def previousgraph(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()
    # when receive all data for filters
    project_id = request.GET.get("project_id", None)
    if not project_id:
        return redirect("/search")
    # check if there is the id of the research and this id is available
    # Check if the research project belongs to the actual user
    # actual_user = cast(User, request.user)
    # research_exist = Research.objects.filter(
    #     user=actual_user, id=research_id
    # ).exists()
    # if not research_exist:
    #     return redirect("/search")
    # give all the variable
    # list of cluster
    project = Project.objects.filter(id=project_id).first()

    if not project:
        return redirect("/search")

    if not project.is_finish:
        return redirect("/search")

    context["project"] = project
    context["cluster_list"] = ClusterElement.objects.filter(
        cluster__project=project
    )

    # list of documents, check for valid and invalids documents
    context["documents_list"] = Document.objects.filter(project=project)

    # id of the research
    context["project_id"] = project_id
    # path = settings.TEMP_DATA / "html" / f"{project.pk}_plot.html"

    FNAME_PROJECT_DIV_PLOT = (
        settings.TEMP_DATA / "plot" / f"{project.pk}_div.html"
    )
    FNAME_RESEARCH_SCRIPT_PLOT = (
        settings.TEMP_DATA / "script" / f"{project.pk}_script.html"
    )
    # get the div plot
    with open(FNAME_PROJECT_DIV_PLOT, "r") as f:
        div_plot = f.read()
    context["div_plot"] = div_plot

    with open(FNAME_RESEARCH_SCRIPT_PLOT, "r") as f:
        script_plot = f.read()
    context["script_plot"] = script_plot

    # Get the html plot
    # data = ""

    # FNAME_PROJECT_PLOT = str(
    #     settings.PLOT_DATA / f"research_{research_id}_plot.html"
    # )
    # with open(FNAME_RESEARCH_PLOT, "r") as file:
    #     data = file.read()
    # context["path_plot"] = FNAME_PROJECT_PLOT

    # context["plot_html"] = data

    # Load the  div and script components

    # give a list of all topics
    cluster_list = Cluster.objects.filter(project=project).values_list(
        "topic", flat=True
    )
    list_topics = list(set(cluster_list))
    context["list_topics"] = list_topics

    topics, palette = get_color_map(list_topics)

    context["topic_colors"] = {
        topic: color for topic, color in zip(topics, palette)
    }

    # authors_list_query = Author.objects.filter(
    #     article__researcharticle__research=research
    # ).distinct()

    # authors_list = []
    # if authors_list_query.exists():
    #     for author in authors_list_query:
    #         last_name = author.last_name if author.last_name else ""
    #         first_name = author.first_name if author.first_name else ""
    #         authors_list.append(last_name + ", " + first_name)

    # context["authors_list"] = authors_list

    # if request.session.get("id_research", False) == research_id:
    #     filters = request.session.get("filters", False)
    #     if filters:
    #         context["filters"] = filters
    #     else:
    #         context["filters"] = ""

    return render(request, "previousgraph.html", context)
