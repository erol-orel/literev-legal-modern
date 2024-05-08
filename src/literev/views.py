from __future__ import annotations

import datetime
import logging

logging.basicConfig(level=logging.INFO)

from http import HTTPStatus
from typing import Any

from django.conf import settings
from django.db.models import Count
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView

from literev.forms import SearchForm
from literev.libs.nlp import nlp_topic_description
from literev.libs.pipeline import (
    get_color_map,
    running_delete,
    running_restart,
)
from literev.libs.select_functions import (
    download_finalcsv,
    get_filtered_document,
    get_filters,
)
from literev.libs.table_choice import (
    reset_table_choice,
    update_article_is_check_table_choice,
    update_article_to_display_table_choice,
    update_neighbour_table_choice,
    update_new_table_choice,
)
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
    TableChoice,
)
from literev.tasks import launch_process

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


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

    total_documents = request.session["total_documents"]

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
    context["delete_message"] = False

    if request.method == "POST":
        submit = request.POST["submit"]

        if submit in ["reload", "cancel"]:
            pass

        if submit == "restart":
            logging.info("Restarting project")
            logging.info(request.POST)
            project_id = request.POST["project_id"]
            running_restart(project_id)

        if submit == "delete":
            project_id = request.POST["project_id"]
            project = Project.objects.filter(pk=project_id).first()
            context["project"] = project
            context["delete_message"] = True

        if submit == "confirm_delete":
            project_id = request.POST["project_id"]
            logging.info(f"Removing project: {project_id}")
            running_delete(project_id)

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
    # check if there is the id of the project and this id is available
    # Check if the project project belongs to the actual user
    # actual_user = cast(User, request.user)
    # research_exist = Project.objects.filter(
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
            request.session["id_project"] = project_id
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

            update_new_table_choice(
                # user=user,
                project=project,
                document_id_list=request.session["document_pk_list"],
            )

            return redirect("/tableselect?project_id=" + str(project_id))

        elif submit == "cancel":
            pass

    context["project"] = project
    context["cluster_list"] = ClusterElement.objects.filter(
        cluster__project=project
    )

    # list of documents, check for valid and invalids documents
    context["documents_list"] = Document.objects.filter(project=project)

    # id of the project
    context["project_id"] = project_id
    # path = settings.TEMP_DATA / "html" / f"{project.pk}_plot.html"

    FNAME_PROJECT_DIV_PLOT = settings.PLOT_DATA / f"{project.pk}_div.html"
    FNAME_PROJECT_SCRIPT_PLOT = (
        settings.PLOT_DATA / f"{project.pk}_script.html"
    )
    # get the div plot
    with open(FNAME_PROJECT_DIV_PLOT, "r") as f:
        div_plot = f.read()
    context["div_plot"] = div_plot

    with open(FNAME_PROJECT_SCRIPT_PLOT, "r") as f:
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

    # Get the grouped cluster
    clusters = Cluster.objects.filter(project=project)

    grouped_clusters = (
        clusters.values("topic")
        .annotate(
            total_documents=Count("clusterelement__document"),
        )
        .order_by("-total_documents")
    )

    index = 0
    list_topic_10 = []
    for e_cluster in grouped_clusters:
        if e_cluster["topic"] == UNCLASSIFIED_PAPERS_TOPIC:
            continue
        index += 1
        number__topic10_cluster = f"{index}: " + ", ".join(
            e_cluster["topic"].split(", ")[:10]
        )
        list_topic_10.append(number__topic10_cluster)

    context["list_number_topic10"] = list_topic_10

    list_topics = list(set(cluster_list))
    context["list_topics"] = list_topics

    topics, palette = get_color_map(list_topics)

    context["topic_colors"] = {
        topic: color for topic, color in zip(topics, palette)
    }

    # Get normes list
    standards_list_raw = Document.objects.filter(
        project=project,
    ).values_list("standards", flat=True)

    # CEDH.6 ; CEDH.8 ; LPA.59.letb
    # LEtr.69.al4;LEtr.74.al3;LEtr.74.al1.leta;LaLEtr.6.al3;LaLEtr.10;LaLEtr.12.al2;Cst.36.al3;CEDH.5

    standard_list = set()

    for standards in standards_list_raw:
        for standard in standards.split(";"):
            standard_list.add(standard.strip())

    context["standard_list"] = list(standard_list)

    # add values for autocompletion in result
    result_list = [
        "REJETE",
        "ADMIS",
        "PARTIELMNT ADMIS",
        "IRRECEVABLE",
        "REFUSE",
        "ACCORDE",
        "RETIRE",
        "SANS OBJECT",
        "NO RESULT",
    ]

    context["result_list"] = result_list

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


def tableselect(request: HttpRequest) -> HttpResponse:
    context: dict[str, Any] = dict()
    current_page = 1

    project_id = request.GET.get("project_id", None)

    if not project_id:
        return redirect("/search")

    project = Project.objects.filter(id=project_id).first()

    if not project:
        return redirect("/search")

    if "page" in request.GET:
        current_page = int(request.GET["page"])
        # check if the page is good.
        # if too low, redirect to first page
        if current_page < 1:
            current_page = 1
        # if too high, redirect to last page

        number_document = TableChoice.objects.filter(project=project).count()
        if (
            int(request.GET["page"])
            > int(number_document / settings.NUMBER_ARTICLE_BY_PAGE) + 1
        ):
            current_page = (
                int(number_document / settings.NUMBER_ARTICLE_BY_PAGE) + 1
            )

    # if receive a POST request
    if request.method == "POST":
        check_list = []
        if "check_row" in request.POST:
            check_list = [
                int(table_id) for table_id in request.POST.getlist("check_row")
            ]
        submit = request.POST.get("submit")

        number_document = TableChoice.objects.filter(project=project).count()

        if submit == "iterate":
            update_article_is_check_table_choice(
                project=project,
                list_id=check_list,
            )
            update_article_to_display_table_choice(
                project=project,
                list_id=check_list,
            )
            update_neighbour_table_choice(project=project)
            return redirect(f"/tableselect?project_id={project.id}")

        elif submit == "reset":
            reset_table_choice(project=project)
            return redirect(f"/tableselect?project_id={project.id}")

        elif submit == "finish":
            update_article_is_check_table_choice(
                project=project,
                list_id=check_list,
            )
            update_article_to_display_table_choice(
                project=project,
                list_id=check_list,
            )
            # note: removed redirect
            return download_finalcsv(project=project)

        elif submit == "previous":
            if current_page == 1:
                pass
            else:
                update_article_is_check_table_choice(
                    project=project,
                    list_id=check_list,
                )
                return redirect(
                    f"/tableselect?project_id={project.id}&page={current_page-1}"
                )
        elif submit == "next":
            if (
                current_page
                == int(number_document / settings.NUMBER_ARTICLE_BY_PAGE) + 1
            ):
                pass
            else:
                update_article_is_check_table_choice(
                    project=project,
                    list_id=check_list,
                )
                return redirect(
                    f"/tableselect?project_id={project.id}&page={current_page+1}"
                )

    tablechoice_list = TableChoice.objects.filter(
        project=project,
        to_display=True,
    ).order_by("id")

    # define variable about number of articles
    context["number_Article_initial"] = TableChoice.objects.filter(
        project=project, is_initial=True
    ).count()
    context["number_Article_neighbour"] = TableChoice.objects.filter(
        project=project,
        is_initial=False,
        to_display=True,
        is_check=False,
    ).count()
    context["number_Article_chosen"] = TableChoice.objects.filter(
        project=project, is_check=True
    ).count()

    # give the number of neigbour
    # context["number_k_neighbour"] = project.number_neighbour

    # define the interval of article for the current page
    first_article = (current_page - 1) * settings.NUMBER_ARTICLE_BY_PAGE
    last_article = current_page * settings.NUMBER_ARTICLE_BY_PAGE

    # check if last_article is not greater than the size of the list
    if last_article < tablechoice_list.count():
        context["tablechoice_list"] = tablechoice_list[
            first_article:last_article
        ]
        context["last_page"] = False
    else:
        context["tablechoice_list"] = tablechoice_list[first_article:]
        context["last_page"] = True
    if current_page == 1:
        context["first_page"] = True
    else:
        context["first_page"] = False

    context["current_page"] = current_page

    if tablechoice_list.count() % settings.NUMBER_ARTICLE_BY_PAGE == 0:
        context["total_page"] = int(
            tablechoice_list.count() // settings.NUMBER_ARTICLE_BY_PAGE
        )
    else:
        context["total_page"] = (
            tablechoice_list.count() // settings.NUMBER_ARTICLE_BY_PAGE + 1
        )

    return render(request, "tableselect.html", context)


def contentdocument(request: HttpRequest, document_id: int) -> HttpResponse:
    context: dict[str, Any] = dict()

    if not document_id:
        return redirect("/search")

    document = Document.objects.get(pk=document_id)

    context["document"] = document

    return render(request, "contentdocument.html", context)
