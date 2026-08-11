"""Tests for the searchable-source registry (``libs.search``).

Ensures every federal court mapped in ``FEDERAL_SPIDERS`` is registered as a
searchable, section-RAG-eligible source and passes selection validation.
"""

from __future__ import annotations

from literev.libs.entscheidsuche import FEDERAL_SPIDERS
from literev.libs.search import (
    SEARCH_SOURCE_OPTIONS,
    SEARCH_SOURCE_VALUES,
    SECTION_SOURCES,
    get_search_source_options,
    validate_selected_indices,
)

# entscheidsuche spider (hierarchy code) -> registered source key.
SPIDER_TO_SOURCE = {
    "CH_BGer": "bundesgericht",
    "CH_BGE": "atf",
    "CH_BVGE": "bundesverwaltungsgericht",
    "CH_BSTG": "bundesstrafgericht",
    "CH_PATG": "bundespatentgericht",
}


def test_all_federal_spiders_have_a_registered_source() -> None:
    # Every federal spider we can import must be searchable.
    assert set(SPIDER_TO_SOURCE) == set(FEDERAL_SPIDERS)
    for source_key in SPIDER_TO_SOURCE.values():
        assert source_key in SEARCH_SOURCE_VALUES


def test_new_sources_are_section_eligible() -> None:
    for source_key in ("atf", "bundespatentgericht"):
        assert source_key in SECTION_SOURCES


def test_new_sources_appear_in_ui_options() -> None:
    options = {
        opt["value"]: opt["label"] for opt in get_search_source_options()
    }
    assert options["atf"] == "Tribunal fédéral — arrêts principaux (ATF)"
    assert options["bundespatentgericht"] == "Tribunal fédéral des brevets"


def test_validate_selected_indices_accepts_new_sources() -> None:
    assert validate_selected_indices(["atf", "bundespatentgericht"]) == [
        "atf",
        "bundespatentgericht",
    ]


def test_source_options_have_no_duplicate_keys() -> None:
    keys = [value for value, _label in SEARCH_SOURCE_OPTIONS]
    assert len(keys) == len(set(keys))
