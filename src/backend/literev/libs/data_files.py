from __future__ import annotations

from typing import cast

import joblib
import pandas as pd

from django.conf import settings

from literev.models import Project


def load_tfidf_keywords(project: Project) -> list[str]:
    """
    Loads saved keywords

    Parameters
    ----------
    project : Project object
        A project related with the keywords.

    Returns
    -------
    list[str]
        List of saved tfidif keywords for the project.
    """
    # TODO: where this file is created?
    #       it seems the code that create the file is commented out
    #       in the task_clustering.py
    path = settings.ARTICLE_DATA / f"tfidf_keywords_project_{project.id}.pkl"

    if not path.exists():
        return cast(list[str], [])

    keywords_list = joblib.load(path)

    return keywords_list


def get_dataframe_project(project: Project) -> pd.DataFrame:
    """
    Return the saved tf-idf pandas dataframe for the project.

    Parameters
    ----------
    project : Project object
        A project related with the keywords

    Returns
    -------
    df : pd.Dataframe
        tfidf matrix for the project.
    """
    list_id_docs = joblib.load(
        settings.ARTICLE_DATA / f"id_list_project_{project.id}.pkl"
    )
    tf_idf = joblib.load(
        settings.ARTICLE_DATA / f"tf_idf_project_{project.id}.pkl"
    )
    columns_name = joblib.load(
        settings.ARTICLE_DATA / f"column_name_project_{project.id}.pkl"
    )

    df = pd.DataFrame.sparse.from_spmatrix(
        tf_idf, columns=columns_name, index=list_id_docs
    )

    return df


def get_es_scores(project: Project) -> dict[int, float]:
    """
    Loads saved elasticsearch scores.
    Parameters
    ----------
    project : Project object
        A project related with the elasticsearch scores.

    Returns
    -------
    dict[int, float]
        Dictionary with document_id as key and elasticsearch
        score as value for the project.
    """
    path = settings.ARTICLE_DATA / f"es_scores_project_{project.id}.pkl"

    if not path.exists():
        return {}

    scores = joblib.load(path)

    return cast(dict[int, float], scores)


def load_hdbscan_prob(project: Project) -> list[float]:
    """
    Loads saved hdbscan scores.
    Parameters
    ----------
    project : Project object
        A project related with the hdbscan scores.

    Returns
    -------
    list[str]
        List of saved hdbscan scores for the project.
    """
    path = settings.ARTICLE_DATA / f"hdbscan_scores_project_{project.id}.pkl"

    if not path.exists():
        return []

    scores = joblib.load(path)

    return list(scores)
