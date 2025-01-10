from __future__ import annotations

import logging
import re

from threading import Thread
from typing import Iterator

from django.db.models.query import QuerySet

from literev.libs.data_files import get_es_scores, load_hdbscan_prob
from literev.libs.scoring import (
    extract_keywords,
    get_topic_and_hdbscan_score,
    sort_by_es_score,
)
from literev.models import (
    Cluster,
    ClusterElement,
    Document,
    Project,
    ProjectRefinement,
    RefinementIteration,
    TableChoice,
    User,
)
from literev.task_plotting import get_color_map

filter_thread_dict = {}

UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


def highlight_words(
    text: str, words_to_highlight: list[str], style_class: str
) -> str:
    """
    Highlights word in words_to_highlight wrapping it with an html tag with style_class.

    Parameters
    ----------
    text : str
        Text where the words will be highlighted
    words_to_highlight : list[str]
        list of word to be highlighted.
    style_class : str
        style class to be assined to the word,
        this class should exist in the css file.

    Returns
    -------
    test : str
        A text containing highlighted words with html tags.
    """
    for word in words_to_highlight:
        # Regular expression pattern to match the whole word in a case-insensitive manner
        pattern = r'\b(?<!["\'<>])(' + re.escape(word) + r")(?![^<>]*>)\b"

        # Use a lambda function to replace and retain the matched word's original case
        # The `re.sub` will handle all matches of the pattern in the text
        text = re.sub(
            pattern,
            lambda match: f'<span class="{style_class}">{match.group(1)}</span>',
            text,
            flags=re.IGNORECASE,
        )
    return text


def highlight_words_topic(
    text: str, words_to_highlight: list[str], color_code: str
) -> str:
    """
    Highlights word in words_to_highlight wrapping it with an html tag with color_code.

    Parameters
    ----------
    text : str
        Text where the words will be highlighted
    words_to_highlight : list[str]
        list of word to be highlighted.
    style_class : str
        style class to be assined to the word,
        this class should exist in the css file.

    Returns
    -------
    test : str
        A text containing highlighted words with html tags.
    """
    for word in words_to_highlight:
        # Regular expression pattern to match the whole word in a case-insensitive manner
        pattern = r'\b(?<!["\'<>])(' + re.escape(word) + r")(?![^<>]*>)\b"

        # Use a lambda function to replace and retain the matched word's original case
        # The `re.sub` will handle all matches of the pattern in the text
        text = re.sub(
            pattern,
            lambda match: f'<span style="background-color: {color_code}40">{match.group(1)}</span>',
            text,
            flags=re.IGNORECASE,
        )
    return text


def render_table_choice(
    project: Project,
    tablechoice: QuerySet[TableChoice],
) -> tuple[list[dict[str | int, str | float | int]], bool, bool]:
    """
    Return a list of documents data and a boolean value to indicate if the document has hdbscan scores.

    Parameters
    ----------
    project : Project object
        A project related with topic and scores.
    tablechoice: QuerySet[TableChoice]
        A set of tablechoice object, used to show table select page.
    order_by : str
        Used to sort the tablechoice objects

    Returns
    -------
    tablechoice_render, has_scores : list, bool
        list of documents data and boolean value to check if the documents has scores from hhdbscan.
    """
    has_hdbscan_scores = False
    has_es_scores = False
    tablechoice_render = []

    es_scores = get_es_scores(project)

    if es_scores:
        has_es_scores = True

    hdbscan_scores = load_hdbscan_prob(project)

    if hdbscan_scores:
        has_hdbscan_scores = True
        topic_scores = get_topic_and_hdbscan_score(
            hdbscan_scores, project, tablechoice
        )

    query_keywords = extract_keywords(project.query)

    if has_hdbscan_scores:
        clusters = Cluster.objects.filter(project=project).order_by("order")

        topics_for_color = []
        for cluster in clusters:
            topics_for_color.append(cluster.topic)

        topics, palette = get_color_map(topics_for_color)

        color_dict = {
            topic_str: color for topic_str, color in zip(topics, palette)
        }

    for tablechoice_e in tablechoice:
        rendered_sample = tablechoice_e.document.raw_document_text[:800]

        rendered_sample = highlight_words(
            rendered_sample,
            query_keywords,
            "query-keywords-highlight",
        )
        render_e = {
            "id": tablechoice_e.id,
            "is_check": tablechoice_e.is_check,
            "document_pk": tablechoice_e.document.pk,
            "procedure_type": tablechoice_e.document.procedure_type,
            "decision_type": tablechoice_e.document.decision_type,
            "decision_date": tablechoice_e.document.decision_date,
            "result": tablechoice_e.document.result,
            "standards": tablechoice_e.document.standards,
            "sample_document": rendered_sample,
            "is_initial": tablechoice_e.is_initial,
        }

        if has_hdbscan_scores:
            topic = topic_scores[tablechoice_e.document.id]["topic"]
            if topic != UNCLASSIFIED_PAPERS_TOPIC:
                topic_key = topic.split(" : ")[1]
            else:
                topic_key = UNCLASSIFIED_PAPERS_TOPIC

            topic10 = (
                topic.split(" : ")[0]
                + " : "
                + ", ".join(topic.split(" : ")[1].split(", ")[:10])
                if topic != UNCLASSIFIED_PAPERS_TOPIC
                else topic
            )

            render_e.update(
                {
                    "topic": topic10,
                    "hdbscan_score": topic_scores[tablechoice_e.document.id][
                        "hdbscan_score"
                    ],
                    "color": color_dict[topic_key],
                }
            )
            if topic != UNCLASSIFIED_PAPERS_TOPIC:
                topic_keywords = topic.split(" : ")[1].split(", ")
                color_code = color_dict[topic_key]
                render_e["sample_document"] = highlight_words_topic(
                    rendered_sample,
                    topic_keywords[:10],
                    color_code,
                )

        if has_es_scores:
            render_e.update({"es_score": es_scores[tablechoice_e.document.id]})

        tablechoice_render.append(render_e)

    return tablechoice_render, has_hdbscan_scores, has_es_scores


def sort_table_choice(
    project: Project, tablechoice: QuerySet[TableChoice], order_by: str
) -> list[TableChoice]:
    """
    Sort tablechoice object by order_by string.

    Parameters
    ----------
    project : Project object
        A project related with the keywords
    tablechoice: QuerySet[TableChoice]
        A set of tablechoice object, used to show table select page.
    order_by : str
        Used to sort the tablechoice objects

    Returns
    -------
    list[TableChoice]
        List of sorted tablechoice objects.
    """
    if order_by == "decision_date":
        return list(tablechoice.order_by("document__decision_date"))
    elif order_by == "-decision_date":
        return list(tablechoice.order_by("-document__decision_date"))
    elif order_by == "es_score":
        return sort_by_es_score(project, tablechoice)

    # Disable for sorting by similar keyword score
    # return sort_by_keyword_score(project, tablechoice, order_by)

    return list(tablechoice)


def neighbour_document(document: Document, project: Project) -> list[Document]:
    """
    Return a list of document but there isn't the center document in the list.

    The function take an document, a project and process with clusterelement
    object, the nearest neighbor. By default, take the 5 nearest.
    by iteration, search around the document +-100 and if doesn't
    have enough, the same but with +-200 around. We make max +-1000.
    """
    number_neighbor = 10

    neighbour_documents: list[Document] = []

    clusters_elements = ClusterElement.objects.filter(cluster__project=project)

    cluster_center_document = ClusterElement.objects.filter(
        document=document, cluster__project=project
    ).first()

    # if the document doesn't exist in the cluster
    if not cluster_center_document:
        return neighbour_documents

    distances = {}

    for cluster_e in clusters_elements:
        distances[cluster_e] = (
            cluster_center_document.pos_x - cluster_e.pos_x
        ) ** 2 + (cluster_center_document.pos_y - cluster_e.pos_y) ** 2

    sorted_cluster_elems = sorted(distances.keys(), key=lambda x: distances[x])
    # counting from 1 because in the position 0 is the same center cluster element
    if len(sorted_cluster_elems) <= number_neighbor:
        for cluster_e in sorted_cluster_elems[1:]:
            neighbour_documents.append(cluster_e.document)
        return neighbour_documents

    for cluster_e in sorted_cluster_elems[1 : number_neighbor + 1]:
        neighbour_documents.append(cluster_e.document)

    return neighbour_documents


def create_iteration(
    user: User,
    project: Project,
    refinement_id: int,
    parent_iteration: RefinementIteration | None = None,
) -> None:
    """Save the actual state of all TableChoices objects in a iteration
    object model database.

    Parameters
    ----------
    user : User
        project owner.
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    refinement_id : int
        Refinement object id used to generate a relationship between
        the new iteration and the refinement.
    parent_iteration : RefinementIteration
        Iteration object used to create a new iteration
    """

    table_choice = TableChoice.objects.filter(user=user, project=project)

    if not table_choice:
        logging.info("There no table choice for project {project.id}")
        return

    result_documents_ids = [tc.document.id for tc in table_choice]

    no_display = [
        tc.document.id for tc in table_choice.filter(to_display=False)
    ]  # it could be valid to use as well `is_check=False`

    new_neighbors_ids = [
        tc.document.id for tc in table_choice.filter(is_initial=False)
    ]

    checked_documents_ids = [
        tc.document.id for tc in table_choice.filter(is_check=True)
    ]

    number_documents = table_choice.filter(to_display=True).count()

    RefinementIteration.objects.create(
        refinement_id=refinement_id,
        parent_iteration=parent_iteration,
        number_documents=number_documents,
        checked_documents_ids=checked_documents_ids,
        excluded_documents_ids=no_display,
        new_neighbors_ids=new_neighbors_ids,
        result_documents_ids=result_documents_ids,
    )


def get_json_iterations_render(
    refinement_id: int,
    active_iteration_id: int,
) -> list[dict[str, int | bool | str]]:
    """Returns a list object created with the full iteration_dict
    this new dict will used to render iterations in frontend.

    Parameters
    ----------
    refinement_id : int
        Refinement object id which is related with the iterations.
    active_iteration_id : int
        It is the iteration id from the current iteration showed in front end.

    Returns
    -------
    iteration_render_list : list[dict[str, Any]]
        a list of dictionaries, each dict has name, id, is_parent, is_root, is_active fields
        used to render in front end.
    """
    iteration_render_list: list[dict[str, int | bool | str]] = []
    refinement = ProjectRefinement.objects.filter(id=refinement_id).first()

    iterations = RefinementIteration.objects.filter(refinement=refinement)

    if not refinement:
        return iteration_render_list

    owner_id = refinement.owner.id
    last_iteration = iterations.last()

    if last_iteration is None:
        return iteration_render_list

    if active_iteration_id == -1:
        active_iteration_id = last_iteration.id

    parents_id_set = {
        iter_id
        for iter_id in iterations.values_list("parent_iteration", flat=True)
    }
    c = 0

    for iteration in iterations.order_by("id"):
        iteration_render_list.append(
            {
                "id": iteration.id,
                "owner_id": owner_id,
                "is_root": True
                if iteration.parent_iteration is None
                else False,
                "name": f"Iteration {c + 1}: ({iteration.number_documents} documents)",
                "is_active": True
                if iteration.id == active_iteration_id
                else False,
                "is_parent": True if iteration.id in parents_id_set else False,
            }
        )
        c += 1

    return iteration_render_list


def divide_in_chunks(
    id_list: list[int], batch_size: int
) -> Iterator[list[int]]:
    """Divides a list into chuncks.

    Parameters
    ----------
    id_list : list[int]
        fill list of ids.
    batch_size : int
        size of chunks

    Returns
    -------
    Iterator[list[int]]
        A chunked id list.
    """
    for i in range(0, len(id_list), batch_size):
        yield id_list[i : i + batch_size]


def get_iteration(
    user: User,
    project: Project,
    refinement_id: int,
    iteration_id: int,
) -> None:
    """Recreates tablechoices objects using iter_id.
    Removes old TableChoices object and recreates it again
    using iteration_id and data from database.

    Parameters
    ----------
    user : User
        project owner.
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    refinement_id : int
        Refinement object id which is related with the iterations.
    iter_id : int
        iteration id which will be used to create TablChoice objs.
    """
    refinement = ProjectRefinement.objects.filter(
        project=project, id=refinement_id
    )
    if not refinement:
        return
    iteration = RefinementIteration.objects.filter(
        refinement_id=refinement_id, id=iteration_id
    ).first()

    if not iteration:
        return

    all_documents_ids = iteration.result_documents_ids
    no_display_ids = iteration.excluded_documents_ids
    no_initial_ids = iteration.new_neighbors_ids
    checked_ids = iteration.checked_documents_ids

    TableChoice.objects.filter(user=user, project=project).delete()

    # create tablechoice with different documents id
    batch_size = 1000

    for document_id_list in divide_in_chunks(all_documents_ids, batch_size):
        table_choice_objs = []

        for document_id in document_id_list:
            table_choice_objs.append(
                TableChoice(
                    user=user,
                    project=project,
                    document_id=document_id,
                )
            )

        TableChoice.objects.bulk_create(table_choice_objs)

    # There is no need to set maybe documents selection because is created by default

    # set excluded ids
    TableChoice.objects.filter(document_id__in=no_display_ids).update(
        to_display=False
    )

    # set no initial documents
    TableChoice.objects.filter(document_id__in=no_initial_ids).update(
        is_initial=False
    )

    # set checked(yes) documents
    TableChoice.objects.filter(document_id__in=checked_ids).update(
        is_check=True
    )


def remove_iteration_get_parent(
    user: User, project: Project, refinement_id: int, iteration_id: int
) -> int | None:
    """Removes iteration from database.

    Parameters
    ----------
    user : User
        project owner.
    project : project object Model database
               The project object model where is used to store
               search query, status and related data.
    refinement_id : int
        Refinement object id which is related with the iterations.
    iter_id : int
        iteration id which will be removed
    """
    iteration = RefinementIteration.objects.filter(
        refinement__owner=user, refinement_id=refinement_id, id=iteration_id
    ).first()

    if iteration is None:
        return None

    parent_iteration = iteration.parent_iteration

    if parent_iteration is None:
        return None

    iteration.delete()

    return parent_iteration.id


def update_new_table_choice(
    user: User, project: Project, document_id_list: list[int]
) -> None:
    """Removes old TableChoice objects related with project and user
    and create a new TableChoices objects.

    Parameters
    ----------
    user : User
        TableChoice owner.
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    document_id_list : list[int]
        New list of documents ids to create new TableChoice objects.
    """
    # remove all row with this user
    TableChoice.objects.filter(user=user, project=project).delete()
    # add new rows

    batch_size = 1000

    for document_id_list in divide_in_chunks(document_id_list, batch_size):
        table_choice_objs = []

        for document_id in document_id_list:
            table_choice_objs.append(
                TableChoice(
                    user=user,
                    project=project,
                    document_id=document_id,
                )
            )

        TableChoice.objects.bulk_create(table_choice_objs)


def update_neighbour_table_choice(
    user: User, project: Project, excluded_set: set[int]
) -> None:
    """
    With an initial list of document from all row who are to_display
    True, add the nearest neighbour of these document in table choice.
    """
    table_choice = TableChoice.objects.filter(
        user=user,
        project=project,
    )

    for row in table_choice.filter(is_check=True):
        neighbours = neighbour_document(row.document, project)

        for document in neighbours:
            # Check if the document id is in the excluded set
            if document.id in excluded_set:
                continue

            # check if a tablechoice with the documente has been created before
            if table_choice.filter(document=document).first():
                continue

            TableChoice.objects.create(
                user=user,
                project=project,
                document=document,
                is_initial=False,
            )


def reset_table_choice(
    user: User, project: Project, refinement_id: int
) -> None:
    """Restart to iteration root.

    Parameters
    ----------
    user : User
        TableChoice owner.
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    refinement_id : int
        Refinement object id which is related with the iterations.
    """
    last_iteration = RefinementIteration.objects.filter(
        refinement__owner=user, refinement_id=refinement_id
    ).last()

    if last_iteration is None:
        return

    next_iteration = last_iteration.parent_iteration

    while last_iteration.parent_iteration is not None:
        next_iteration = last_iteration.parent_iteration
        last_iteration.delete()
        last_iteration = next_iteration

    get_iteration(user, project, refinement_id, last_iteration.id)


def update_document_to_display_table_choice(
    user: User,
    project: Project,
) -> bool:
    """
    Sets `to_display=False` to all no checked (no selected) documents.
    """

    table_choice = TableChoice.objects.filter(user=user, project=project)

    if not table_choice.count():
        return

    table_choice.filter(is_check=False).update(to_display=False)


def update_checked_document_page(
    user: User,
    project: Project,
    check_list_yes: list[int],
    check_list_no: list[int],
    check_list_maybe: list[int],
) -> None:
    """
    Updates tablechoice according to checked lists
    """
    all_table_ids = check_list_yes + check_list_no + check_list_maybe

    table_choice = TableChoice.objects.filter(
        user=user, project=project, id__in=all_table_ids
    )

    if not table_choice.count():
        return

    table_choice.filter(id__in=check_list_yes).update(is_check=True)
    table_choice.filter(id__in=check_list_no).update(is_check=False)
    table_choice.filter(id__in=check_list_maybe).update(is_check=None)


def update_document_is_check_table_choice(
    user: User, project: Project, list_id: list[int]
) -> None:
    """
    The function take a list of id object of TableChoice row and user.
    All row who is in list_id,
    the boolean 'is_check' will be put to True. The function take user
    id by security. We check if all id
    in 'list_id' is owned by user because, the list of id come
    from the front-end by the user
    """

    # update the boolean 'to_display' and the boolean "is_checked"
    table_choice = TableChoice.objects.filter(user=user, project=project)

    if not table_choice.count():
        return

    table_choice.filter(id__in=list_id).update(is_check=True)
    table_choice.exclude(id__in=list_id).update(is_check=False)


def all_display_table_choice(project: Project) -> None:
    """Reset all document so can display all document"""
    tablechoice = TableChoice.objects.filter(project=project)
    for row in tablechoice:
        row.to_display = True


def back_process_iterate(
    user: User,
    project: Project,
    refinement_id: int,
    parent_iteration_id: int,
) -> None:
    """
    Execute the iterate process in brackground.

    Parameters
    ----------
    user : User
        user object who has the project ownership
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    refinement_id : int
        Refinement object id which is related with the iterations.

    Notes
    -----
    This function modifies the project.step status to
    "processing_filters" meawhile the filtering
    process is happening.
    At the end of the process removes that status.
    """
    # TODO: update this step to not crush with clustering , plotting step
    project.step_number = 50
    project.save()

    update_document_to_display_table_choice(
        user=user,
        project=project,
    )

    if parent_iteration_id == -1:
        last_iteration = RefinementIteration.objects.filter(
            refinement_id=refinement_id
        ).last()

        if last_iteration:
            parent_iteration_id = last_iteration.id

    parent_iteration = RefinementIteration.objects.get(id=parent_iteration_id)

    # remove child iterations
    last_iteration = RefinementIteration.objects.filter(
        refinement_id=refinement_id
    ).last()

    if last_iteration is None:
        return

    while last_iteration != parent_iteration:
        next_iteration = last_iteration.parent_iteration
        if next_iteration is None:
            break
        last_iteration.delete()
        last_iteration = next_iteration

    # update exluded documents id set
    table_choices_not_selected = TableChoice.objects.filter(
        user=user, project=project, is_check=False
    )
    excluded_document_ids_set = set(parent_iteration.excluded_documents_ids)

    # update excluded documents ids
    for table_choice in table_choices_not_selected:
        excluded_document_ids_set.add(table_choice.document.id)

    # update update neighbor table choice
    update_neighbour_table_choice(
        user=user, project=project, excluded_set=excluded_document_ids_set
    )

    create_iteration(
        user=user,
        project=project,
        refinement_id=refinement_id,
        parent_iteration=parent_iteration,
    )

    project.step_number = 0
    project.save()

    del filter_thread_dict[project.id]


def update_check_list_iteration(
    user: User, project: Project, iteration_id: int
) -> None:
    """Update all checked articles in iteration object.

    Parameters
    ----------
    user : User
        research owner.
    project : Project object Model database
        The project object model where is used to store
        search query, status and related data.
    iteration_id : int
        It is the iteration id from the current iteration showed in front end.

    """
    iteration = RefinementIteration.objects.get(id=iteration_id)
    tablechoice = TableChoice.objects.filter(
        user=user,
        project=project,
        is_check=True,
    )

    new_check_set = set(tc.document.id for tc in tablechoice)
    # update check list in iteration
    iteration.checked_documents_ids = list(new_check_set)
    iteration.save()


def iterate_check_list(
    user: User,
    project: Project,
    refinement_id: int,
    active_iteration_id: int,
) -> None:
    """
    It is a wrapper to execute back_process_iterate in a separated thread.

    Parameters
    ----------
    user : User
        user object who has the project ownership
    project : project object Model database
        The project object model where is used to store
        search query, status and related data.
    """

    # TODO:  Check if the project has another step in progress,
    # if there is any this do nothing
    if project.step not in ["", "clustering", "plotting"]:
        return

    filter_thread_dict[project.id] = Thread(
        target=back_process_iterate,
        args=[user, project, refinement_id, active_iteration_id],
        daemon=True,
    )

    filter_thread_dict[project.id].start()
