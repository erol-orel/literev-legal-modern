from __future__ import annotations

import datetime
import logging

logging.basicConfig(level=logging.INFO)

from http import HTTPStatus
from typing import Any, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from literev.forms import SearchForm
from literev.libs.nlp import nlp_topic_description
from literev.libs.pipeline import (
    get_color_map,
    launch_process,
    running_restart,
)
from literev.libs.select_functions import get_filtered_document, get_filters
from literev.libs.utils import (
    count_all_corpus,
    get_number_documents,
    process_all_documents,
)
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
        logging.info("updating request session")
        # update context variables
        context.update(new_data)
        # save in request session the data
        request.session.update(new_data)

    return context


def search_continue(
    request: HttpRequest, context: dict[str, Any]
) -> dict[str, Any]:
    # use when implement login
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
    logging.info("executing the search function")
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
        logging.info("search search")
        query_text = SearchForm(request.POST)["query"].value()
        logging.info(query_text)
        if query_text == "#COUNT-ALL-CORPUS-LITEREV-00":
            result_all = count_all_corpus()
            logging.info("counting all corpus")
            logging.info(result_all)

        elif query_text == "#PROCESS-ALL-CORPUS-LITEREV-00":
            process_all_documents()
            logging.info("processing all corpus")

        else:
            context = search_search(request, context)

    elif submit == "evaluate":
        # TODO: Implement this
        # return to the saved variables from
        # request session
        logging.info("search evaluate")
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
            logging.info("Restarting project")
            logging.info(request.POST)
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
    context["AreYouSure"] = False
    # when receive all data for filters

    project_id = request.GET.get("project_id", None)
    if not project_id:
        return redirect("/search")
    # TODO: Add this piece of code after adding user
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

    # when receive all data for filters
    if request.method == "POST":
        submit = request.POST["submit"]

        if submit == "filters":
            # Used for debbuging
            # for key, value in request.POST.items():
            #     print(key, value)
            # transform the POST data
            filters = get_filters(project, request.POST)

            # get a list of id article who match all the filters
            document_pk_list = get_filtered_document(
                project=project, filters=filters
            )
            # save this list in session user
            request.session["document_pk_list"] = document_pk_list
            request.session["id_research"] = project_id
            context["number_article"] = len(document_pk_list)
            context["project"] = project
            context["AreYouSure"] = True
            # save data filters if the user cancel and return to select page
            # request.session["filter_data"] =
            #   filter_recover_data(request.POST)

            # return render(request, "previousgraph.html", context)

        elif submit == "continue":
            # update the new table choice with
            # the article selected without their neighbour
            logging.info(request.session["document_pk_list"])

            # TODO:Implement a tableselect page
            # update_new_table_choice(
            #     user=user,
            #     research=project,
            #     article_id_list=request.session["id_article_list"],
            # )

            # return redirect("/tableselect?research_id=" + str(project_id))

        elif submit == "cancel":
            pass

    context["project"] = project
    context["cluster_list"] = ClusterElement.objects.filter(
        cluster__project=project
    )

    # list of documents, check for valid and invalids documents
    context["documents_list"] = Document.objects.filter(project=project)

    # id of the research
    context["project_id"] = project_id
    # path = settings.TEMP_DATA / "html" / f"{project.pk}_plot.html"

    FNAME_PROJECT_DIV_PLOT = settings.PLOT_DATA / f"{project.pk}_div.html"
    FNAME_RESEARCH_SCRIPT_PLOT = (
        settings.PLOT_DATA / f"{project.pk}_script.html"
    )
    # get the div plot
    with open(FNAME_PROJECT_DIV_PLOT, "r") as f:
        div_plot = f.read()
    context["div_plot"] = div_plot

    with open(FNAME_RESEARCH_SCRIPT_PLOT, "r") as f:
        script_plot = f.read()
    context["script_plot"] = script_plot

    # Use in case we  want to export html file
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

    # Use in case of we want to restart filters
    # if request.session.get("id_research", False) == research_id:
    #     filters = request.session.get("filters", False)
    #     if filters:
    #         context["filters"] = filters
    #     else:
    #         context["filters"] = ""

    return render(request, "previousgraph.html", context)


def generate_summary(request: HttpRequest, cluster_id: int) -> HttpResponse:
    """Generate a cluster topic summary text by calling openAI API"""

    # check if the request is ajax
    is_ajax = request.headers.get("X-Requested-With", None) == "XMLHttpRequest"

    # fails if request is not ajax
    if not is_ajax:
        return JsonResponse(
            {
                "message": (
                    "Invalid Request. X-Requested-With header "
                    "not found or not equal to XMLHttpRequest"
                )
            },
            status=HTTPStatus.BAD_REQUEST,
        )

    # resolves POST requests only
    if request.method == "POST":
        # try to get cluster object
        try:
            cluster = Cluster.objects.get(pk=cluster_id)
        except Cluster.DoesNotExist:
            return JsonResponse(
                {"message": f"Cluster with id={cluster_id} does not exist"},
                status=HTTPStatus.NOT_FOUND,
            )

        summary_text = nlp_topic_description(cluster)

        if not summary_text:
            # in case the openai service is still not
            # working and returning an empty string
            return JsonResponse(
                {
                    "message": "Service Unavailable",
                    "content": "It seems the service is still not available. Please, try again later.",
                },
                status=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        else:
            # update cluster summary text
            cluster.summary = summary_text
            cluster.save()
            return JsonResponse(
                {"message": "Success. Created.", "content": summary_text},
                status=HTTPStatus.CREATED,
            )
    else:
        # fails if request http method is not POST
        return JsonResponse(
            {"message": "Invalid Request. Http method should be POST"},
            status=HTTPStatus.BAD_REQUEST,
        )
