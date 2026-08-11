"""Tests for the cantonal (Romandie) searchable-source registry.

Verifies that every cantonal court in ``CANTONAL_SPIDERS`` is registered as a
searchable, section-eligible source under the lower-cased ``hierarchy`` code,
and that the Geneva ``Cour de justice`` is intentionally left out.
"""

from __future__ import annotations

from literev.libs.entscheidsuche import (
    ALL_SPIDERS,
    CANTONAL_SPIDERS,
    FEDERAL_SPIDERS,
)
from literev.libs.search import (
    SEARCH_SOURCE_VALUES,
    SECTION_SOURCES,
    validate_selected_indices,
)


def _source_key(spider_code: str) -> str:
    return spider_code.lower()


def test_all_cantonal_spiders_are_registered_sources() -> None:
    for code in CANTONAL_SPIDERS:
        key = _source_key(code)
        assert key in SEARCH_SOURCE_VALUES, f"{key} missing from options"
        assert key in SECTION_SOURCES, f"{key} not section-eligible"


def test_cantonal_sources_pass_validation() -> None:
    keys = [_source_key(code) for code in CANTONAL_SPIDERS]
    assert validate_selected_indices(keys) == keys


def test_geneva_cour_de_justice_is_not_registered() -> None:
    # GE_CJ overlaps the existing chambre_* Geneva sources and is deliberately
    # excluded to avoid double-counting.
    assert "GE_CJ" not in CANTONAL_SPIDERS
    assert "ge_cj" not in SEARCH_SOURCE_VALUES


def test_all_spiders_is_federal_plus_cantonal() -> None:
    assert ALL_SPIDERS == {**FEDERAL_SPIDERS, **CANTONAL_SPIDERS}
    # No key collisions between the two sets.
    assert set(FEDERAL_SPIDERS).isdisjoint(CANTONAL_SPIDERS)
    assert len(ALL_SPIDERS) == len(FEDERAL_SPIDERS) + len(CANTONAL_SPIDERS)
