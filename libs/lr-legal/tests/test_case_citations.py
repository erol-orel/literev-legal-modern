from __future__ import annotations

from lr_legal import (
    build_citation_edges,
    extract_citations,
    format_citation,
)


def _keys(text: str) -> list[str]:
    return [c.key for c in extract_citations(text)]


def test_extracts_atf_french() -> None:
    [citation] = extract_citations("Cf. ATF 145 III 72 consid. 3.2.")
    assert citation.kind == "ATF"
    assert citation.key == "ATF_145_III_72"
    assert format_citation(citation) == "ATF 145 III 72"


def test_atf_bge_dtf_normalise_to_the_same_key() -> None:
    # All three language collections denote the same series.
    assert _keys("BGE 145 III 72") == ["ATF_145_III_72"]
    assert _keys("DTF 145 III 72") == ["ATF_145_III_72"]


def test_extracts_federal_docket_numbers() -> None:
    assert _keys("arrêt 4A_123/2020 du Tribunal fédéral") == ["TF_4A_123/2020"]
    assert _keys("Urteil 6B_1234/2019") == ["TF_6B_1234/2019"]
    assert _keys("2C_44/2021") == ["TF_2C_44/2021"]


def test_deduplicates_and_preserves_order() -> None:
    text = (
        "ATF 130 III 28 ... puis 4A_5/2018 ... et de nouveau ATF 130 III 28."
    )
    assert _keys(text) == ["ATF_130_III_28", "TF_4A_5/2018"]


def test_ignores_malformed_references() -> None:
    # Not a Roman part, missing page, or not a docket shape.
    assert extract_citations("ATF 145 Z 72") == []
    assert extract_citations("art. 271 CO") == []
    assert extract_citations("no citation here at all") == []


def test_roman_part_with_suffix() -> None:
    assert _keys("ATF 120 Ia 31") == ["ATF_120_Ia_31"]


def test_build_citation_edges_drops_self_and_shapes_rows() -> None:
    records = [
        # Cites ATF 145 III 72, and cites itself (ATF 130 III 28) — the
        # self-edge must be dropped.
        ("ATF_130_III_28", "renvoie à ATF 145 III 72 et à ATF 130 III 28"),
        ("some_ata_key", "voir arrêt 4A_123/2020"),
    ]
    edges = build_citation_edges(records)
    assert {
        "source": "ATF_130_III_28",
        "target": "ATF_145_III_72",
        "kind": "ATF",
    } in edges
    assert {
        "source": "some_ata_key",
        "target": "TF_4A_123/2020",
        "kind": "TF",
    } in edges
    # The self-citation ATF_130_III_28 -> ATF_130_III_28 is dropped.
    assert all(not (e["source"] == e["target"]) for e in edges)
    assert len(edges) == 2
