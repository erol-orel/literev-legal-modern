from __future__ import annotations

from literev.libs.select_functions import neighbour_document
from literev.models import Document, Project, TableChoice


def update_new_table_choice(
    project: Project, document_id_list: list[int]
) -> None:
    """
    When user make a new project filtering, the ancients
    are deleted and the new are written
    """
    # remove all row with this user
    TableChoice.objects.filter(project=project).delete()
    # add new rows
    for document_id in document_id_list:
        TableChoice.objects.create(
            project=project,
            document=Document.objects.get(id=document_id),
        )


def update_neighbour_table_choice(project: Project) -> None:
    """
    With an initial list of document from all row who are to_display
    True, add the nearest neighbour of these document in table choice.
    """
    tablechoice = TableChoice.objects.filter(project=project, to_display=True)
    for row in tablechoice:
        neighbours = neighbour_document(row.document, project)
        # add these document. We check if the document is already in a row
        for document in neighbours:
            table_choice, created = TableChoice.objects.get_or_create(
                project=project, document=document
            )
            if not created:
                continue
            table_choice.is_initial = False
            table_choice.save()


def update_article_to_display_table_choice(
    project: Project, list_id: list[int]
) -> bool:
    """
    The function take a list of id object of TableChoice row and user.
    All row who is not in list_id,
    the boolean 'to_display' will be put to False. The function take
    user id by security. We check if all id
    in 'list_id' is owned by user because, the list of id come from
    the front-end by the user
    """

    # update the boolean 'to_display' if the document is in the
    # list or is checked, put to True
    tablechoice = TableChoice.objects.filter(project=project, to_display=True)
    for row in tablechoice:
        # if the document is not in the check list, not to display
        if row.id not in list_id and not row.is_check:
            row.to_display = False
            row.save()

    return True


def update_article_is_check_table_choice(
    project: Project, list_id: list[int]
) -> bool:
    """
    The function take a list of id object of TableChoice row and user.
    All row who is in list_id,
    the boolean 'is_check' will be put to True. The function take user
    id by security. We check if all id
    in 'list_id' is owned by user because, the list of id come
    from the front-end by the user
    """

    # update the boolean 'to_display' and the boolean "is_checked"
    tablechoice = TableChoice.objects.filter(project=project, to_display=True)
    for row in tablechoice:
        # if the document is  in the check list, keep the checkbox checked
        if row.id in list_id:
            row.is_check = True
            row.save()
    return True


def all_display_table_choice(project: Project) -> None:
    """Reset all document so can display all document"""
    tablechoice = TableChoice.objects.filter(project=project)
    for row in tablechoice:
        row.to_display = True


def reset_table_choice(project: Project) -> None:
    """
    To reset, delete all row who have been added
    and put to_display to true
    """
    TableChoice.objects.filter(project=project, is_initial=False).delete()
    for tablechoice in TableChoice.objects.filter(project=project):
        tablechoice.to_display = True
        tablechoice.is_check = False
        tablechoice.save()
