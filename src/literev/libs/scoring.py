import logging
import re

import joblib
import spacy

from django.conf import settings
from django.db.models.query import QuerySet

from literev.libs.data_files import get_dataframe_project, get_es_scores
from literev.models import ClusterElement, Project, TableChoice

logging.basicConfig(level=logging.INFO)
NLP = spacy.load("fr_core_news_md")


def get_most_similar_keywords(
    keywords: list[str], columns_name: list[str]
) -> set[str]:
    """
    Returns a set of words that have a similarity score greater than 0.75 with the keywords

    Parameters
    ----------
    keywords : list[str]
        list of keywords fromt he query.
    columns_name : list[str]
        List of words from the the tfidf matrix.

    Returns
    -------
    set[str]
        set of most similar to keywords.
    """
    SIMILARITY_THRESHOLD = 0.75
    tfidf_keywords = set()

    for keyword in keywords:
        target_token = NLP(keyword)[0]
        target_lemma = target_token.lemma_
        target_lemma_token = NLP(target_lemma)

        similarity_scores = {}

        for word in columns_name:
            # In bigrams and trigams words are separated by _
            if "_" in word:
                word = word.replace("_", " ")

            word_token = NLP(word)
            similarity = target_lemma_token.similarity(word_token)

            # for bigrams and trigrams go back its original separation "_"
            if " " in word:
                word = word.replace(" ", "_")

            similarity_scores[word] = similarity

        for key in similarity_scores.keys():
            if similarity_scores[key] >= SIMILARITY_THRESHOLD:
                tfidf_keywords.add(key)

    return tfidf_keywords


def extract_keywords(expression: str) -> list[str]:
    """
    Returns a list of keywords from the query

    Parameters
    ----------
    expresion : str
        A query string

    Returns
    -------
    list[str]
        list of keywords from the query
    """
    # Regular expression to match quoted phrases and standalone words
    expression = expression.lower()
    pattern = r'"([^"]+)"|(\b\w+\b)'

    # Use `findall` to extract all matches of the pattern in the expression
    matches = re.findall(pattern, expression)

    # Extract matched groups from the tuple returned by findall
    phrases = [match[0] or match[1] for match in matches]

    # Logical operators to exclude
    logical_operators = {"and", "or", "not"}

    # Filter out logical operators
    result = [phrase for phrase in phrases if phrase not in logical_operators]

    return result


def sort_by_es_score(
    project: Project, tablechoice: QuerySet[TableChoice]
) -> list[TableChoice]:
    """
    Sort tablechoice object by elasticsearch score.

    Parameters
    ----------
    project : Project object
        A project related with the keywords
    tablechoice: QuerySet[TableChoice]
        A set of tablechoice object, used to show table select page.

    Returns
    -------
    list[TableChoice]
        List of sorted tablechoice objects.
    """
    scores = get_es_scores(project)

    if scores:
        sorted_list = sorted(
            tablechoice,
            key=lambda x: scores[x.document.id],
            reverse=True,
        )

        return sorted_list

    logging.warning(f"There is no es scores for project : {project.id}")

    return list(tablechoice)


def sort_by_keyword_score(
    project: Project, tablechoice: QuerySet[TableChoice], keyword: str
) -> list[TableChoice]:
    """
    Sort tablechoice object by keyword.

    Parameters
    ----------
    project : Project object
        A project related with the keywords
    tablechoice: QuerySet[TableChoice]
        A set of tablechoice object, used to show table select page.
    keyword : str
        keyword used to sort the tablechoice objects

    Returns
    -------
    list[TableChoice]
        List of sorted tablechoice objects.
    """

    df = get_dataframe_project(project)

    if keyword in df:
        scores = df[keyword]
        sorted_list = sorted(
            tablechoice,
            key=lambda x: scores.loc[x.document.id],
            reverse=True,
        )
        return sorted_list

    logging.warning(f"There is no keyword in the tf idf matrix: {keyword}")

    return list(tablechoice)


def get_topic_and_hdbscan_score(
    hdbscan_scores: list[float], project: Project
) -> dict[int, dict[str, str | float]]:
    """
    Return a dict containing the scores and topic for documents.

    Parameters
    ----------
    project : Project object
        A project related with topic and scores.

    Returns
    -------
    topic_scores_dict : dict
        A dict containing the scores and topic for documents.
    """
    scores_dict = dict()
    topic_scores_dict = dict()

    list_id_docs = joblib.load(
        settings.ARTICLE_DATA / f"id_list_project_{project.id}.pkl"
    )

    for doc_id, score in zip(list_id_docs, hdbscan_scores):
        scores_dict[doc_id] = score

    cluster_elements = ClusterElement.objects.filter(cluster__project=project)

    for cluster_e in cluster_elements:
        topic_scores_dict[cluster_e.document.id] = {
            "topic": cluster_e.cluster.topic,
            "hdbscan_score": scores_dict[cluster_e.document.id],
        }

    return topic_scores_dict
