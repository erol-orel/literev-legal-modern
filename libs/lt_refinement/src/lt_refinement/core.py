from __future__ import annotations

import re

from collections.abc import Callable, Iterator, Mapping, Sequence
from typing import TypeVar

T = TypeVar("T")
LOGICAL_OPERATORS = frozenset({"and", "or", "not"})
UNCLASSIFIED_PAPERS_TOPIC = "unclassified papers"


def _highlight_with_renderer(
    text: str,
    words_to_highlight: Sequence[str],
    renderer: Callable[[str], str],
) -> str:
    highlighted_text = text
    for word in words_to_highlight:
        if not word:
            continue
        pattern = r'\b(?<!["\'<>])(' + re.escape(word) + r")(?![^<>]*>)\b"
        highlighted_text = re.sub(
            pattern,
            lambda match: renderer(match.group(1)),
            highlighted_text,
            flags=re.IGNORECASE,
        )
    return highlighted_text


def highlight_words(
    text: str,
    words_to_highlight: Sequence[str],
    style_class: str,
) -> str:
    return _highlight_with_renderer(
        text,
        words_to_highlight,
        lambda value: f'<span class="{style_class}">{value}</span>',
    )


def highlight_words_topic(
    text: str,
    words_to_highlight: Sequence[str],
    color_code: str,
) -> str:
    return _highlight_with_renderer(
        text,
        words_to_highlight,
        lambda value: (
            f'<span style="background-color: {color_code}40">{value}</span>'
        ),
    )


def extract_keywords(expression: str) -> list[str]:
    lowered_expression = expression.lower()
    matches = re.findall(r'"([^"]+)"|(\b\w+\b)', lowered_expression)
    phrases = [match[0] or match[1] for match in matches]
    return [phrase for phrase in phrases if phrase not in LOGICAL_OPERATORS]


def sort_items_by_score(
    items: Sequence[T],
    scores_by_id: Mapping[int, float],
    get_item_id: Callable[[T], int],
) -> list[T]:
    return sorted(
        items,
        key=lambda item: scores_by_id.get(get_item_id(item), float("-inf")),
        reverse=True,
    )


def format_topic_label(cluster_order: int, cluster_topic: str) -> str:
    if cluster_order == -1:
        return cluster_topic or UNCLASSIFIED_PAPERS_TOPIC
    return f"Topic {cluster_order} : {cluster_topic}"


def build_topic_scores(
    document_ids: Sequence[int],
    hdbscan_scores: Sequence[float],
    cluster_topics_by_document_id: Mapping[int, tuple[int, str]],
) -> dict[int, dict[str, str | float]]:
    scores_by_document_id = {
        document_id: score
        for document_id, score in zip(document_ids, hdbscan_scores)
    }
    topic_scores: dict[int, dict[str, str | float]] = {}
    for document_id, (
        cluster_order,
        cluster_topic,
    ) in cluster_topics_by_document_id.items():
        if document_id not in scores_by_document_id:
            continue
        topic_scores[document_id] = {
            "topic": format_topic_label(cluster_order, cluster_topic),
            "hdbscan_score": scores_by_document_id[document_id] * 100,
        }
    return topic_scores


def divide_in_chunks(
    id_list: Sequence[int],
    batch_size: int,
) -> Iterator[list[int]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero")
    for index in range(0, len(id_list), batch_size):
        yield list(id_list[index : index + batch_size])
