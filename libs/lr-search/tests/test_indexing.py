"""Unit tests for the section-index document/bulk-action builders.

Pure transforms — no cluster. They pin the ``_source`` shape, the stable id
scheme (which makes re-indexing idempotent), and the batching.
"""

from __future__ import annotations

import pytest

from lr_search.hybrid import DEFAULT_VECTOR_FIELD
from lr_search.indexing import (
    batched,
    bulk_index_action,
    iter_batches,
    iter_section_bulk_actions,
    section_doc_id,
    section_document,
    section_index_name,
)


class TestSectionIndexName:
    def test_suffixes_the_source(self) -> None:
        assert (
            section_index_name("chambre_civile") == "chambre_civile_sections"
        )

    def test_strips_and_rejects_empty(self) -> None:
        assert (
            section_index_name("  bundesgericht ") == "bundesgericht_sections"
        )
        with pytest.raises(ValueError):
            section_index_name("   ")


class TestSectionDocId:
    def test_stable_in_its_inputs(self) -> None:
        assert (
            section_doc_id("ATF_1", "Conclusion", 0) == "ATF_1::Conclusion::0"
        )
        # Same inputs -> same id (idempotent re-index).
        assert section_doc_id("ATF_1", "Conclusion", 0) == section_doc_id(
            "ATF_1", "Conclusion", 0
        )


class TestSectionDocument:
    def test_carries_text_and_vector(self) -> None:
        doc = section_document(
            record_key="ATF_1",
            source="chambre_civile",
            section="Mineure-Faits",
            text="les faits",
            vector=[0.1, 0.2],
            decision_date="2023-05-12",
        )
        assert doc["record_key"] == "ATF_1"
        assert doc["source"] == "chambre_civile"
        assert doc["section"] == "Mineure-Faits"
        assert doc["text"] == "les faits"
        assert doc[DEFAULT_VECTOR_FIELD] == [0.1, 0.2]
        assert doc["decision_date"] == "2023-05-12"

    def test_omits_absent_decision_date(self) -> None:
        doc = section_document(
            record_key="k",
            source="s",
            section="Conclusion",
            text="t",
            vector=[0.0],
        )
        assert "decision_date" not in doc


class TestBulkActions:
    def test_single_action_shape(self) -> None:
        action = bulk_index_action("idx", "id-1", {"text": "t"})
        assert action == {
            "_op_type": "index",
            "_index": "idx",
            "_id": "id-1",
            "_source": {"text": "t"},
        }

    def test_ordinals_increment_per_record_and_section(self) -> None:
        docs = [
            {"record_key": "A", "section": "Conclusion", "text": "1"},
            {"record_key": "A", "section": "Conclusion", "text": "2"},
            {"record_key": "A", "section": "Mineure-Faits", "text": "3"},
            {"record_key": "B", "section": "Conclusion", "text": "4"},
        ]
        ids = [a["_id"] for a in iter_section_bulk_actions("idx", docs)]
        assert ids == [
            "A::Conclusion::0",
            "A::Conclusion::1",
            "A::Mineure-Faits::0",
            "B::Conclusion::0",
        ]

    def test_all_actions_target_the_index(self) -> None:
        docs = [{"record_key": "A", "section": "X", "text": "t"}]
        actions = list(iter_section_bulk_actions("my_sections", docs))
        assert actions[0]["_index"] == "my_sections"
        assert actions[0]["_op_type"] == "index"


class TestBatched:
    def test_splits_into_chunks(self) -> None:
        assert list(batched([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]

    def test_exact_multiple(self) -> None:
        assert list(batched([1, 2, 3, 4], 2)) == [[1, 2], [3, 4]]

    def test_empty(self) -> None:
        assert list(batched([], 3)) == []

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValueError):
            list(batched([1], 0))


class TestIterBatches:
    def test_batches_a_generator_lazily(self) -> None:
        def gen() -> object:
            yield from range(5)

        assert list(iter_batches(gen(), 2)) == [[0, 1], [2, 3], [4]]

    def test_empty_iterable(self) -> None:
        assert list(iter_batches(iter([]), 3)) == []

    def test_rejects_non_positive_size(self) -> None:
        with pytest.raises(ValueError):
            list(iter_batches(iter([1]), 0))
