from __future__ import annotations

import pytest

from lr_refinement import (
    build_topic_scores,
    divide_in_chunks,
    extract_keywords,
    highlight_words,
    sort_items_by_score,
)


class Row:
    def __init__(self, identifier: int) -> None:
        self.identifier = identifier


def test_extract_keywords_ignores_boolean_operators() -> None:
    assert extract_keywords(
        '"contrat de bail" AND locataire OR NOT appel'
    ) == [
        "contrat de bail",
        "locataire",
        "appel",
    ]


def test_highlight_words_skips_existing_html() -> None:
    rendered = highlight_words(
        "Contrat <span>contrat</span>",
        ["contrat"],
        "query-highlight",
    )

    assert rendered.count('class="query-highlight"') == 1


def test_sort_items_by_score_orders_descending() -> None:
    rows = [Row(1), Row(2), Row(3)]
    sorted_rows = sort_items_by_score(
        rows,
        {1: 0.1, 2: 0.9, 3: 0.5},
        lambda row: row.identifier,
    )

    assert [row.identifier for row in sorted_rows] == [2, 3, 1]


def test_build_topic_scores_formats_cluster_labels() -> None:
    scores = build_topic_scores(
        [10, 11],
        [0.42, 0.75],
        {
            10: (3, "contrat, bail"),
            11: (-1, "unclassified papers"),
        },
    )

    assert scores[10]["topic"] == "Topic 3 : contrat, bail"
    assert scores[10]["hdbscan_score"] == 42.0
    assert scores[11]["topic"] == "unclassified papers"


def test_divide_in_chunks_validates_batch_size() -> None:
    with pytest.raises(ValueError):
        list(divide_in_chunks([1, 2, 3], 0))
