from __future__ import annotations

import datetime as dt
import logging

from pathlib import Path
from typing import Optional, Sequence, Tuple, Union

import bokeh.plotting
import distinctipy

from bokeh.embed import components
from bokeh.io import output_file, save

# https://github.com/bokeh/bokeh/issues/12960
from bokeh.models import (  # type: ignore
    CategoricalColorMapper,
    HoverTool,
    LabelSet,  # error importing mypy
)
from bokeh.plotting import ColumnDataSource, figure
from django.conf import settings
from django.db.models import Avg, FloatField

from config.celery import app
from literev.libs.utils import update_task_code
from literev.models import (
    Cluster,
    ClusterElement,
    Project,
)

logger = logging.getLogger(__name__)

UNCLASSIFIED_PAPERS_COLOR = "#9494b8"
UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


def get_color_map(topics: list[str]) -> Tuple[Sequence[str], list[str]]:
    """
    Generate a color palette based on the number of topics/clusters.

    Parameters
    ----------
    topics : list[str]
        A list of topics or factors.

    Returns
    -------
    Tuple[list[str], list[str]]
        (topics, palette)
        A tuple containing the sorted topics and corresponding color palette.

    Notes
    -----
    This function is useful for obtaining the cluster's color in different
    parts of the system, such as the summary table. The generated values can
    be used to create a bokeh.models.CategoricalColorMapper object.

    Topics must be sorted to ensure consistent palettes, preventing
    color changes based on the order of the topics in the list.
    """

    # check if we have unclassified papers cluster
    unclassified_cluster_exists = UNCLASSIFIED_PAPERS_TOPIC in topics

    if unclassified_cluster_exists:
        topics.remove(UNCLASSIFIED_PAPERS_TOPIC)

    # topics must be sorted so that the palettes are always consistent
    # otherwise the colors may change depending on the topic's list order

    # set seed rng=5 to get repeatibility and reproducibility in colors
    colors = distinctipy.get_colors(n_colors=len(topics), rng=5)
    palette = [distinctipy.distinctipy.get_hex(color) for color in colors]

    # insert unclassified papers cluster with color
    if unclassified_cluster_exists:
        topics.append(UNCLASSIFIED_PAPERS_TOPIC)
        palette = [*palette, UNCLASSIFIED_PAPERS_COLOR]

    return topics, palette


def plot_clusters(
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
    and Cluster objects model database related with research model database.

    Parameters
    ----------
    project : Project object Model database
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

    config: dict[str, list[Optional[Union[float, str, dt.date]]]] = {}
    config["x"] = []
    config["y"] = []
    config["procedure_type"] = []
    config["decision_type"] = []
    config["decision_date"] = []
    config["descriptors"] = []
    config["topic"] = []
    config["topic_10"] = []
    config["standards"] = []
    config["result"] = []
    config["cluster_order"] = []

    clusters_points = ClusterElement.objects.filter(cluster__project=project)

    # Get the grouped cluster
    clusters = Cluster.objects.filter(project=project)

    grouped_clusters = (
        clusters.values("topic", "order")
        .annotate(
            center_x=Avg("clusterelement__pos_x", output_field=FloatField()),
            center_y=Avg("clusterelement__pos_y", output_field=FloatField()),
        )
        .order_by("order")
    )

    cluster_number_data: dict[str, list[str | int]] = {}

    cluster_number_data["x"] = []
    cluster_number_data["y"] = []
    cluster_number_data["number"] = []

    for e_cluster in grouped_clusters:
        if e_cluster["topic"] == UNCLASSIFIED_PAPERS_TOPIC:
            continue
        cluster_number_data["x"].append(e_cluster["center_x"])
        cluster_number_data["y"].append(e_cluster["center_y"])
        cluster_number_data["number"].append(str(e_cluster["order"]))

    cluster_number_source = ColumnDataSource(data=cluster_number_data)

    fig.circle(
        x="x",
        y="y",
        size=38,
        fill_color="white",
        line_color="black",
        source=cluster_number_source,
    )

    number_label = LabelSet(
        x="x",
        y="y",
        text="number",
        source=cluster_number_source,
        text_font_size="36px",
        text_color="black",
        text_font_style="bold",
        text_align="center",
        text_baseline="middle",
    )

    for point in clusters_points:
        config["x"].append(point.pos_x)
        config["y"].append(point.pos_y)
        decision_date = (
            point.document.decision_date
            if point.document.decision_date
            else None
        )
        config["cluster_order"].append(point.cluster.order)
        config["decision_type"].append(point.document.decision_type)
        config["procedure_type"].append(point.document.procedure_type)
        config["decision_date"].append(decision_date)
        config["descriptors"].append(point.document.descriptors)
        config["topic"].append(point.cluster.topic)
        topic_10 = ", ".join(point.cluster.topic.split(", ")[:10])
        config["topic_10"].append(topic_10)
        config["standards"].append(point.document.standards)
        config["result"].append(point.document.result)

    # the unique topic should be always sorted
    # so it can be predictable and replicable in the color pallette

    unique_topic = [e_cluster["topic"] for e_cluster in grouped_clusters]

    factors, palette = get_color_map(unique_topic)

    color_map = CategoricalColorMapper(factors=factors, palette=palette)

    source = ColumnDataSource(data=config)

    # We need a name so that can restrict hover tools to just this
    # particular 'series' on the plot. You can specify it (in case it
    # needs to be something specific for other reasons), otherwise
    # just use 'main'

    if name is None:
        name = "main"

    # make bigger points with less documents
    if clusters_points.count() < 100:
        size = 16
    else:
        size = 5

    fig.scatter(
        "x",
        "y",
        size=size,
        source=source,
        name=name,
        marker=marker,
        color={"field": "topic", "transform": color_map},
    )

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
    @topic_10</span>
    </div>

    <div>
    <span style="font-size: 12px; color: blue;">
    Topic number:</span>
    <span style="font-size: 12px; font-weight: bold;">
    @cluster_order</span>
    </div>
    </div>

    """
    hover = HoverTool(name=name, tooltips=tooltips)

    fig.add_tools(hover)
    fig.add_layout(number_label)
    # Now create the hover tool, and make sure it is only active with
    # the series plotted in the previous line

    fig.axis.visible = False

    # removes grid lines from both axis (x, y)
    fig.xgrid.grid_line_color = None
    fig.ygrid.grid_line_color = None

    # removes logo
    fig.toolbar.logo = None  # type: ignore

    output_file(filename=path)
    save(fig, path)

    # separate in components to embed in the previous graph
    # and save it
    script, div = components(fig)

    with open(div_path, "w") as f:
        f.write(div)

    with open(script_path, "w") as f:
        f.write(script)


@app.task(bind=True)
def back_plotting_documents(self, project_id: int):
    """
    Generates visual plots for clustered data.

    Parameters
    ----------
    project_id : int
        The ID of the project for which plots are generated.
    """
    project = Project.objects.get(id=project_id)

    update_task_code(project, self.request.id)

    try:
        path = settings.PLOT_DATA / f"{project.pk}_plot.html"
        div_path = settings.PLOT_DATA / f"{project.pk}_div.html"
        script_path = settings.PLOT_DATA / f"{project.pk}_script.html"

        plot_clusters(project, path, div_path, script_path)

    except Exception as e:
        logger.error("Error creating Plot")
        logger.error(e)
        return

    logger.info("Success creating Plot")
    project.step = ""
    project.actual_task_code = ""
    project.is_finish = True
    project.is_running = False
    project.save()
