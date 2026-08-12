"""Unit tests for the Elasticsearch section-RAG retrieval (Chroma replacement).

The Elasticsearch client is mocked, so these run without a live cluster or
Hactar. They pin the query the retrieval POSTs (hybrid RRF, filtered to one
decision, against the ``<source>_sections`` index) and that the response is
grouped into the same per-section block shape the Chroma path returned.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from literev.libs import es_section_retrieval as esr


def _response() -> dict:
    return {
        "hits": {
            "hits": [
                {"_source": {"section": "Conclusion", "text": "c1"}},
                {"_source": {"section": "Mineure-Faits", "text": "f1"}},
                {"_source": {"section": "Conclusion", "text": "c2"}},
                {"_source": {"section": "Metadata", "text": "ignored"}},
            ]
        }
    }


class TestGetBestSectionChunksEs:
    def test_groups_hits_into_section_blocks(self) -> None:
        client = MagicMock()
        client.search.return_value = _response()
        with patch.object(esr, "_es_client", return_value=client):
            blocks = esr.get_best_section_chunks_es(
                "REC_KEY",
                "le congé est-il valable ?",
                [0.1, 0.2],
                "chambre_civile",
            )
        assert blocks["Conclusion"] == ["c1", "c2"]
        assert blocks["Mineure-Faits"] == ["f1"]
        assert blocks["Majeure"] == []  # present, empty
        assert "Metadata" not in blocks  # unknown section dropped

    def test_queries_the_source_section_index_filtered_to_the_decision(
        self,
    ) -> None:
        client = MagicMock()
        client.search.return_value = {"hits": {"hits": []}}
        with patch.object(esr, "_es_client", return_value=client):
            esr.get_best_section_chunks_es(
                "REC_KEY", "question", [0.3, 0.4], "bundesgericht"
            )
        _, kwargs = client.search.call_args
        assert kwargs["index"] == "bundesgericht_sections"
        body = kwargs["body"]
        legs = body["retriever"]["rrf"]["retrievers"]
        # both legs constrained to this decision only
        record_filter = [{"term": {"record_key": "REC_KEY"}}]
        assert legs[1]["knn"]["filter"] == record_filter
        assert legs[0]["standard"]["query"]["bool"]["filter"] == record_filter
        # dense leg carries the caller-provided query vector
        assert legs[1]["knn"]["query_vector"] == [0.3, 0.4]

    def test_empty_response_yields_all_empty_sections(self) -> None:
        client = MagicMock()
        client.search.return_value = {"hits": {"hits": []}}
        with patch.object(esr, "_es_client", return_value=client):
            blocks = esr.get_best_section_chunks_es(
                "K", "q", [0.0], "chambre_penale"
            )
        assert blocks == {name: [] for name in esr.SECTION_NAMES}
