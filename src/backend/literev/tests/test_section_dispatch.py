"""Tests for section-vs-generic RAG dispatch (``tasks._section_source_for``).

The section pipeline (structured multi-section answers + rich summary) must be
chosen whenever a selected source has a usable section Chroma collection, and a
missing chamber collection must be surfaced (WARNING) rather than silently
downgrading to the generic pipeline.
"""

from __future__ import annotations

import logging

from unittest import mock

from literev import tasks


def test_returns_source_when_section_collection_available() -> None:
    with mock.patch(
        "literev.libs.chroma_utils.has_section_collection", return_value=True
    ):
        assert (
            tasks._section_source_for(["chambre_penale"]) == "chambre_penale"
        )


def test_returns_none_when_no_section_collection() -> None:
    with mock.patch(
        "literev.libs.chroma_utils.has_section_collection", return_value=False
    ):
        assert tasks._section_source_for(["chambre_penale"]) is None


def test_ignores_sources_outside_section_sources() -> None:
    with mock.patch(
        "literev.libs.chroma_utils.has_section_collection", return_value=True
    ) as has_coll:
        assert tasks._section_source_for(["not_a_registered_source"]) is None
    has_coll.assert_not_called()


def test_missing_chamber_collection_logs_warning(caplog) -> None:
    with mock.patch(
        "literev.libs.chroma_utils.has_section_collection", return_value=False
    ):
        with caplog.at_level(logging.WARNING):
            tasks._section_source_for(["chambre_civile"])
    assert any(
        "chambre_civile" in record.getMessage()
        and record.levelno >= logging.WARNING
        for record in caplog.records
    ), "expected a WARNING naming the degraded chamber"


def test_first_available_section_source_wins() -> None:
    # chambre_penale has no collection; bundesgericht does -> pick bundesgericht.
    def fake_has(source: str) -> bool:
        return source == "bundesgericht"

    with mock.patch(
        "literev.libs.chroma_utils.has_section_collection",
        side_effect=fake_has,
    ):
        result = tasks._section_source_for(["chambre_penale", "bundesgericht"])
    assert result == "bundesgericht"
