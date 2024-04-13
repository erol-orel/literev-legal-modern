import datetime as dt
import logging

from datetime import datetime
from pathlib import Path
from threading import Thread
from typing import Optional, Sequence, Union, cast

import bokeh.plotting
import hdbscan
import numpy as np
import numpy.typing as npt
import pandas as pd

from bokeh.embed import components
from bokeh.io import save
from bokeh.models import CategoricalColorMapper, HoverTool, LabelSet
from bokeh.plotting import ColumnDataSource, figure
from django.conf import settings
from django.db.models import Avg, Count, FloatField

from literev.libs.collectors import ElasticSearchCollector, MetaData
from literev.models import Cluster, ClusterElement, Document, Project
from literev_core.clustering import cluster
from literev_core.preprocessing import preprocessing

thread_dict = dict()
UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"
UNCLASSIFIED_PAPERS_COLOR = "#9494b8"


COLOR_PALETTE_30 = (
    "#1F77B4",
    "#FF861C",
    "#2CA02C",
    "#F20001",
    "#472BEF",
    "#8C564B",
    "#17BECF",
    "#FFD92F",
    "#98DF8A",
    "#FF00B1",
    "#B168F4",
    "#C49C94",
    "#9EDAE5",
    "#E4A169",
    "#38ED15",
    "#EC1557",
    "#8D0FFF",
    "#E4AE21",
    "#1448FF",
    "#F1D96D",
    "#054F22",
    "#E377C2",
    "#551955",
    "#4C1B00",
    "#46C3AD",
    "#BB1819",
    "#92FF92",
    "#A79C3A",
    "#892889",
    "#B23D19",
)


def running_restart(project_id: str) -> None:
    try:
        project = Project.objects.get(is_running=True, id=project_id)
    except Project.DoesNotExist:
        logging.warning(f"the project does no exist, id: {project_id}")
        return

    # check if the research has his own entry
    if project.id not in thread_dict:
        thread_dict[project.id] = Thread(
            target=back_process, args=[project], daemon=True
        )
        thread_dict[project.id].start()
        logging.info(f"Restoring project, id: {project_id}")

        return

    t = thread_dict[project.id]
    if not t.is_alive():
        # if the thread is not alive, recreate thread
        thread_dict[project.id] = Thread(
            target=back_process, args=[project], daemon=True
        )
        thread_dict[project.id].start()

    return


def convert_to_target_type(
    value: str, target_type: type = str
) -> str | int | datetime:
    """
    Convert the given value to the specified target type, handling `None` values appropriately.

    This function ensures data conforms to the expected type in Django model fields,
    especially when dealing with potentially nullable fields in database operations.

    Parameters
    ----------
    value : str
        The value to be converted. Can be a string representation of any type including `None`.
    target_type : type, optional
        The target data type to which the value should be converted. Supports `str`, `int`,
        and `datetime`. Default is `str`.

    Returns
    -------
    str | int | datetime
        The value converted to the target type. If the original value is `None`,
        returns a default value appropriate for the specified `target_type`: an
        empty string for `str`, `0` for `int`, and the current datetime for `datetime`.
    """

    if value is None or value == "":
        if target_type == str:
            return ""
        elif target_type == int:
            return 0
        elif target_type == datetime:
            return datetime.now()
    else:
        if target_type == datetime:
            return datetime.strptime(value, "%Y-%m-%d")
        else:
            return target_type(value)


def create_document_db(project: Project, document: MetaData) -> None:
    """
    Create and save a document object in the database.

    This function takes a project instance and a MetaData instance containing document
    metadata. It transforms the metadata values to ensure they are stored correctly in the
    database, particularly converting None values to empty strings where necessary, and then
    creates a new Document object in the database.

    Parameters
    ----------
    project : Project
        The project instance to which the document belongs.
    document : MetaData
        The MetaData instance containing the document's metadata.

    Returns
    -------
    None

    """

    Document.objects.create(
        project=project,
        raw_document_id=convert_to_target_type(document.doc_id),
        raw_document_text=convert_to_target_type(document.document_text),
        decision_date=document.decision_date,
        decision_type=convert_to_target_type(document.decision_type),
        procedure_type=convert_to_target_type(document.procedure_type),
        descriptors=convert_to_target_type(document.descriptors),
        standards=convert_to_target_type(document.standards),
        result=convert_to_target_type(document.result),
    )


def back_get_documents(project: Project) -> bool:
    es_collector = ElasticSearchCollector()

    try:
        # Just to get all documents
        logging.info(f"Project query: {project.query}")
        if project.query == "#PROCESS-ALL-CORPUS-LITEREV-00":
            documents_list = es_collector.collect_all_documents()
        else:
            documents_list = es_collector.collect_documents(
                project.query, project.range_begin_date, project.range_end_date
            )

    except Exception as e:
        logging.warning("ElasticSearchCollector Failed")
        logging.warning(e)
        return False

    for document in documents_list:
        try:
            create_document_db(project, document)

        except Exception as e:
            logging.warning(f"Document creation failed, id: {document.doc_id}")
            logging.warning(e)

    return True


def update_pp_document(pk: int, pp_corpus: str) -> None:
    document = Document.objects.get(pk=pk)
    document.preprocessed_document = pp_corpus
    document.save()


def back_preprocess_documents(project: Project) -> None:
    documents = Document.objects.filter(project=project)
    document_pk_list = []
    document_corpus_list = []
    logging.info("getting documents from database")

    # Getting all documents with no emtpy document_text field
    document_pk_list = [
        document.pk for document in documents if document.raw_document_text
    ]
    document_corpus_list = [
        document.raw_document_text
        for document in documents
        if document.raw_document_text
    ]

    # TODO use cache documents

    try:
        # using preprocessing_m from literev_core
        rejected_pk_documents, preprocessed_corpus_list = preprocessing(
            project, document_pk_list, document_corpus_list
        )
        logging.info(f"rejected articles number {len(rejected_pk_documents)}")
    except Exception as e:
        logging.warning("literev_core failed in preprocessing")
        logging.warning(e)
        return

    new_document_pk_list = []

    for pk in document_pk_list:
        if pk not in rejected_pk_documents:
            new_document_pk_list.append(pk)

    for pk, pp_corpus in zip(new_document_pk_list, preprocessed_corpus_list):
        try:
            update_pp_document(pk, pp_corpus)

        except Exception as e:
            logging.warning(
                f"Adding preprocessed document failed. Doc id: {pk}"
            )
            logging.warning(e)


def get_color_map(topics: list[str]) -> tuple[Sequence[str], Sequence[str]]:
    """
    Generate a color palette based on the number of topics/clusters.

    Parameters
    ----------
    topics : List[str]
        A list of topics or factors.

    Returns
    -------
    Tuple[List[str], List[str]]
        (topics, palette)
        A tuple containing the sorted topics and corresponding color palette.

    Notes
    -----
    This function is useful for obtaining the cluster's color in different
    parts of the system, such as the summary table. The generated values can
    be used to create a bokeh.models.CategoricalColorMapper object.

    The color palette is determined based on the number of topics:
        - 3: COLOR_PALETTE[:3] get 3 colors
        - 10: COLOR_PALETTE[:10] get 10 colors
        - 20: COLOR_PALETTE[:20] get 20 colors

    Topics must be sorted to ensure consistent palettes, preventing
    color changes based on the order of the topics in the list.
    """

    # check if we have unclassified papers cluster
    unclassified_cluster_exists = UNCLASSIFIED_PAPERS_TOPIC in topics

    if unclassified_cluster_exists:
        topics.remove(UNCLASSIFIED_PAPERS_TOPIC)

    # topics must be sorted so that the palettes are always consistent
    # otherwise the colors may change depending on the topic's list order
    topics = sorted(topics)

    if len(topics) <= len(COLOR_PALETTE_30):
        palette = COLOR_PALETTE_30[: len(topics)]
    else:
        palette = COLOR_PALETTE_30

    # insert unclassified papers cluster with color
    if unclassified_cluster_exists:
        topics.append(UNCLASSIFIED_PAPERS_TOPIC)
        palette = (*palette, UNCLASSIFIED_PAPERS_COLOR)

    return topics, palette


def scatter_with_hover(
    project: Project,
    path: Path,
    div_path: Path,
    script_path: Path,
    fig: Optional[bokeh.plotting.figure] = None,
    name: Optional[str] = None,
    marker: str = "circle",
    fig_width: int = 1500,
    fig_height: int = 900,
) -> None:
    """Creates a html Plot file an interactive scatter plot of `x` vs `y`
    using bokeh, with automatic tooltips showing columns from ClusterElement
    and Cluter objects model database related with research model database.

    Parameters
    ----------
    research : Research object Model database
               The research object model where is used to store
               search query, status and related data.
    path : str, Path
           Full path to where the html plot file will be stored
           after being generated
    div_path : str, Path
                Full path to where the div component from the plot will be
                stored after being generated
    script_path : str, Path
                Full path to where the script component from the plot will
                be stored after being generated
    fig : bokeh.plotting.Figure, optional, default None
        Figure on which to plot (if not given then a new figure will be
        created)
    name : str, optional, default None
        Bokeh series name to give to the scattered data
    marker : str, default circle
        Name of marker to use for scatter plot
    fig_width : int,  default 1800
                with of the resulting plot.
    fig_height : int,  default 900
                 height of the resulting plot.

    Returns
    -------
    None

    Notes
    -----
    Creates a html Plot file from Clusters objects and store in the path

    Acknowledgment
    --------------
    Original code from Robin Wilson <robin@rtwilson.com>
    with thanks to Max Albert for original code example
    """
    # If haven't been given a figure obj then create it with default
    # size etc.
    if fig is None:
        fig = figure(
            width=fig_width,
            height=fig_height,
            tools=["box_zoom", "reset", "tap"],
        )

    config: dict[str, list[Optional[Union[float, str, dt.date]]]] = dict()
    config["x"] = []
    config["y"] = []
    config["procedure_type"] = []
    config["decision_type"] = []
    config["decision_date"] = []
    config["descriptors"] = []
    config["topic"] = []
    config["standards"] = []
    config["result"] = []

    clusters_point = ClusterElement.objects.filter(cluster__project=project)

    # Get the grouped cluster
    clusters = Cluster.objects.filter(project=project)

    grouped_clusters = (
        clusters.values("topic", "summary", "id")
        .annotate(
            center_x=Avg("clusterelement__pos_x", output_field=FloatField()),
            center_y=Avg("clusterelement__pos_y", output_field=FloatField()),
            total_documents=Count("clusterelement__document"),
        )
        .order_by("-total_documents")
    )

    cluster_number_data = dict()

    cluster_number_data["x"] = []
    cluster_number_data["y"] = []
    cluster_number_data["number"] = []

    index = 0
    for e_cluster in grouped_clusters:
        if e_cluster["topic"] == UNCLASSIFIED_PAPERS_TOPIC:
            continue
        index += 1
        cluster_number_data["x"].append(e_cluster["center_x"])
        cluster_number_data["y"].append(e_cluster["center_y"])
        cluster_number_data["number"].append(index)

    cluster_number_source = ColumnDataSource(data=cluster_number_data)

    number_label = LabelSet(
        x="x",
        y="y",
        text="number",
        source=cluster_number_source,
        text_font_size="36px",
        text_color="#807876",
    )

    for point in clusters_point:
        config["x"].append(point.pos_x)
        config["y"].append(point.pos_y)

        decision_date = (
            point.document.decision_date
            if point.document.decision_date
            else None
        )

        config["decision_type"].append(point.document.decision_type)
        config["procedure_type"].append(point.document.procedure_type)
        config["decision_date"].append(decision_date)
        config["descriptors"].append(point.document.descriptors)
        config["topic"].append(point.cluster.topic)
        # config["summary"].append(point.document.summary)
        config["standards"].append(point.document.standards)
        config["result"].append(point.document.result)

        # config["title"].append(points.article.title)
        # config["abstract"].append(points.article.abstract)
        # note: remove that after the refactoring in the migration files

    # the unique topic should be always sorted
    # so it can be predictable and replicable in the color pallette
    unique_topic = cast(list[str], list(set(config["topic"])))

    factors, palette = get_color_map(unique_topic)

    color_map = CategoricalColorMapper(factors=factors, palette=palette)
    # We're getting data from the given dataframe
    source = ColumnDataSource(data=config)

    # We need a name so that can restrict hover tools to just this
    # particular 'series' on the plot. You can specify it (in case it
    # needs to be something specific for other reasons), otherwise
    # just use 'main'

    if name is None:
        name = "main"

    # make bigger points with less articles
    if clusters_point.count() < 100:
        size = 16
    else:
        size = 4

    fig.scatter(
        "x",
        "y",
        size=size,
        source=source,
        name=name,
        marker=marker,
        color={"field": "topic", "transform": color_map},
    )

    fig.add_layout(number_label)

    # Now create the hover tool, and make sure it is only active with
    # the series plotted in the previous line

    tooltips = """
    <div style="width: 400px;">

    <div>
    <span style="font-size: 12px; color: blue;">
    Decision type:</span>
    <span style="font-size: 12px; font-weight: bold;">
    @decision_type</span>
    </div>

    <div>
    <span style="font-size: 12px; color: blue;">
    Decision Date: </span>
    <span style="font-size: 12px; font-weight: bold; ">
    @decision_date</span>
    </div>

    <div>
    <span style="font-size: 12px; color: blue;">
    Descriptors:</span>
    <span style="font-size: 12px; font-weight: bold;">
    @descriptors</span>
    </div>

    <div>
    <span style="font-size: 12px; color: blue;">
    Standards:</span>
    <span style="font-size: 12px; font-weight: bold;">
    @standards</span>
    </div>

    <div>
    <span style="font-size: 12px; color: blue;">
    Result: </span>
    <span style="font-size: 12px; font-weight: bold; ">
    @result</span>
    </div>

    <div>
    <span style="font-size: 12px; color: blue;">
    Topic:</span>
    <span style="font-size: 12px; font-weight: bold;">
    @topic</span>
    </div>

    </div>

    """
    hover = HoverTool(name=name, tooltips=tooltips)

    fig.add_tools(hover)
    fig.axis.visible = False

    # removes grid lines from both axis (x, y)
    fig.xgrid.grid_line_color = None
    fig.ygrid.grid_line_color = None

    # removes logo
    fig.toolbar.logo = None  # type: ignore

    # taptool = fig.select(type=TapTool)  # type: ignore

    save(fig, path)

    # separate in components to embed in the previous graph
    # and save it
    script, div = components(fig)

    with open(div_path, "w") as f:
        f.write(div)

    with open(script_path, "w") as f:
        f.write(script)


def hover_with_keywords(
    project: Project,
    list_id: list[int],
    embedding_2d_array: npt.NDArray[np.float_],
    best_study_clusterer: hdbscan.HDBSCAN,
    tf_idf_sorted: pd.DataFrame,
) -> None:
    """
    Create a cluster from research articles.

    Create an object database model for every
    article according to list_id, extract the x,y coordinates from
    embedding_2d and make the clusters given by best_study_clusterer,
    every cluster has label extracted from tf_idf_sorted.

    Parameters
    ----------
    research : Research object Model database
        The research object model where is used to store
        search query, status and related data.
    list_id_final : list of str
        list of id_articles related with the research
    embedding_2d_array : numpy array from pacmap.PaCMAP object
        An object wich reduces dimensionality to visualize
    best_study_clusterer : optuna.study.Study
        An object used to optimize parameters
        and create clusters with embedding_2d.
    tf_idf_sorted : pandas DataFrame
        Storage the tf-idf index for each word in
        articles. A dataframe with keywords
        as row index in the columns the
        article related.

    Returns
    -------
    None

    Notes
    -----
    Create a cluster object database model for every
    article according to list_id, with research, article_id,
    pos_x, pos_y and labels
    """

    num_clusters = set(best_study_clusterer.labels_)

    for cluster_num in num_clusters:
        w = np.where(best_study_clusterer.labels_ == cluster_num)[0]
        kws = (
            tf_idf_sorted.iloc[:, w]
            .mean(axis=1)
            .sort_values(ascending=False)
            .head(10)
            .index.values
        )

        labels = (
            ", ".join(kws) if cluster_num != -1 else UNCLASSIFIED_PAPERS_TOPIC
        )

        cluster = Cluster.objects.create(
            project=project,
            topic=labels,
        )

        position_article = []

        for i in range(len(best_study_clusterer.labels_)):
            if best_study_clusterer.labels_[i] == cluster_num:
                position_article.append(i)

        embedding_df = pd.DataFrame(embedding_2d_array)
        for i in position_article:
            pos_x = embedding_df[0][i]
            pos_y = embedding_df[1][i]

            document = Document.objects.filter(pk=list_id[i])[0]
            ClusterElement.objects.get_or_create(
                document=document,
                cluster=cluster,
                pos_x=pos_x,
                pos_y=pos_y,
            )
            # TODO: Review the code and uses of the returned variables
            # cluster_element, created = ClusterElement.objects.get_or_create(
            #     document=document,
            #     cluster=cluster,
            #     pos_x=pos_x,
            #     pos_y=pos_y,
            # )
            # cluster_element.save()

        # After the clustering is done, we generate the topic description
        # TODO: Implement summary text use open AI functions
        # topic_summary_text = (
        #     nlp_topic_description(cluster) if cluster_num != -1 else ""
        # )

        # cluster.summary = topic_summary_text
        # cluster.save()


def back_clustering_documents(project: Project) -> None:
    documents = Document.objects.filter(project=project)

    try:
        pp_documents = [
            document.preprocessed_document
            for document in documents
            if document.preprocessed_document != ""
        ]
        list_id_docs = [
            document.pk
            for document in documents
            if document.preprocessed_document != ""
        ]
    except Exception as e:
        logging.warning("error getting preprocessed document from db")
        logging.warning("project id: {project.pk}")
        logging.warning(e)
        return

    try:
        embedding_2d_array, best_study_clusterer, tf_idf_sorted = cluster(
            project, pp_documents
        )
    except Exception as e:
        logging.warning("error in clustering, project id: {project.pk}")
        logging.warning(e)
        return

    try:
        hover_with_keywords(
            project,
            list_id_docs,
            embedding_2d_array,
            best_study_clusterer,
            tf_idf_sorted,
        )
    except Exception as e:
        logging.warning("error creating Cluster, ClusterElement in db")
        logging.warning("project id: {project.pk}")
        logging.warning(e)
        return

    logging.info("success in clustering")


def back_plotting_documents(project: Project) -> None:
    try:
        path = settings.TEMPORARY_DATA / f"{project.pk}_plot.html"
        div_path = settings.PLOT_DATA / f"{project.pk}_div.html"
        script_path = settings.PLOT_DATA / f"{project.pk}_script.html"

        scatter_with_hover(project, path, div_path, script_path)

    except Exception as e:
        logging.warning("error creating plot")
        logging.warning(e)
        return

    logging.info("Success creating plot")


def back_process(project: Project) -> None:
    if project.step == "getting_documents":
        project.is_running = True
        project.save()

        if back_get_documents(project):
            project.step = "preprocessing"
            project.step_number = 0
            project.save()
            logging.info("Success getting documents")

    if project.step == "preprocessing":
        back_preprocess_documents(project)
        project.step = "clustering"
        project.step_number = 0
        project.save()

    # TODO: implement clustering
    if project.step == "clustering":
        back_clustering_documents(project)
        project.step_number = 0
        project.step = "plotting"
        project.save()

    if project.step == "plotting":
        back_plotting_documents(project)
        project.step = ""
        project.is_finish = True
        project.is_running = False
        project.save()


def launch_process(project: Project) -> bool:
    if project.is_finish:
        return False

    # check if the research is currently running
    if project.is_running:
        return False

    project_id = project.id

    thread_dict[project_id] = Thread(
        target=back_process, args=[project], daemon=True
    )

    thread_dict[project_id].start()

    return True
