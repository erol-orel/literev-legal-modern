from __future__ import annotations

from datetime import date

from lr_contracts import (
    ElasticsearchConnectionConfig,
    QueryDateRange,
    SearchDocumentMetadata,
    SearchQuerySpec,
)


def test_contract_models_capture_explicit_values() -> None:
    date_range = QueryDateRange(
        start=date(2024, 1, 1),
        end=date(2024, 12, 31),
    )
    query_spec = SearchQuerySpec(
        query="contrat",
        date_range=date_range,
        search_fields=("document_text", "summary"),
    )
    connection = ElasticsearchConnectionConfig(
        host_url="http://example.test",
        username="elastic",
        password="secret",
    )
    metadata = SearchDocumentMetadata(
        doc_id="doc-1",
        chamber="civil",
        document_text="Texte",
        document_html_text="<p>Texte</p>",
        procedure_type="appel",
        decision_type="arret",
        decision_date="2024-01-01",
        descriptors="bail",
        summary="resume",
        standards="norme",
        result="admis",
        es_score=1.2,
        record_key="rk-1",
    )

    assert query_spec.date_range == date_range
    assert connection.username == "elastic"
    assert metadata.record_key == "rk-1"
