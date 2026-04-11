from __future__ import annotations

import datetime

from lr_query.parsing import (
    process_search_query_elasticsearch,
    tokenize_expression,
    validate_expression,
)


def test_tokenize_and_validate_expression() -> None:
    tokens = tokenize_expression("(contrat AND bail) OR locataire")
    is_valid, error = validate_expression(tokens)
    assert is_valid is True
    assert error is None


def test_process_search_query_elasticsearch_adds_date_filter() -> None:
    query = process_search_query_elasticsearch(
        search_query="contrat AND bail",
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 12, 31),
    )
    decision_date = query["query"]["bool"]["filter"][0]["range"][
        "decision_date"
    ]
    assert decision_date == {"gte": "2024-01-01", "lte": "2024-12-31"}
