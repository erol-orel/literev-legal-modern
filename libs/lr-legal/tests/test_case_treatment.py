from __future__ import annotations

from lr_legal import (
    Treatment,
    build_citation_edges,
    classify_treatment,
    extract_citations_with_context,
    is_negative_treatment,
)


class TestClassifyTreatment:
    def test_overruled_fr(self) -> None:
        passage = (
            "Il y a lieu d'opérer un revirement de jurisprudence : "
            "l'ATF 130 III 28 ne saurait être maintenue."
        )
        assert classify_treatment(passage) == Treatment.OVERRULED

    def test_overruled_de(self) -> None:
        assert (
            classify_treatment(
                "In einer Praxisänderung wird BGE 130 III 28 aufgegeben."
            )
            == Treatment.OVERRULED
        )

    def test_criticized(self) -> None:
        assert (
            classify_treatment(
                "Cette solution est contestable et critiquable."
            )
            == Treatment.CRITICIZED
        )

    def test_distinguished(self) -> None:
        assert (
            classify_treatment(
                "Contrairement à l'ATF 145 III 72, ce cas différent…"
            )
            == Treatment.DISTINGUISHED
        )

    def test_followed(self) -> None:
        assert (
            classify_treatment(
                "Le Tribunal confirme la jurisprudence de l'ATF 145 III 72."
            )
            == Treatment.FOLLOWED
        )

    def test_neutral_default(self) -> None:
        assert (
            classify_treatment("Voir aussi ATF 145 III 72.") == Treatment.CITED
        )
        assert classify_treatment("") == Treatment.CITED

    def test_severity_order_overruled_beats_followed(self) -> None:
        # Both cues present — the more severe one wins.
        passage = (
            "Le tribunal confirme, mais opère un revirement de jurisprudence."
        )
        assert classify_treatment(passage) == Treatment.OVERRULED

    def test_is_negative(self) -> None:
        assert is_negative_treatment(Treatment.OVERRULED)
        assert is_negative_treatment(Treatment.CRITICIZED)
        assert not is_negative_treatment(Treatment.DISTINGUISHED)
        assert not is_negative_treatment(Treatment.FOLLOWED)
        assert not is_negative_treatment(Treatment.CITED)


class TestContextAndEdges:
    def test_extract_with_context_returns_passage(self) -> None:
        text = (
            "x" * 50 + "un revirement : ATF 130 III 28 abandonnée" + "y" * 50
        )
        [(citation, context)] = extract_citations_with_context(text, window=30)
        assert citation.key == "ATF_130_III_28"
        assert "revirement" in context

    def test_edges_default_shape_unchanged(self) -> None:
        edges = build_citation_edges([("k", "voir ATF 145 III 72")])
        assert edges == [
            {"source": "k", "target": "ATF_145_III_72", "kind": "ATF"}
        ]

    def test_edges_with_treatment(self) -> None:
        records = [
            (
                "k1",
                "revirement de jurisprudence : ATF 130 III 28 ne saurait être maintenue",
            ),
            ("k2", "confirme la jurisprudence de l'ATF 145 III 72"),
        ]
        edges = build_citation_edges(records, with_treatment=True)
        by_target = {e["target"]: e for e in edges}
        assert by_target["ATF_130_III_28"]["treatment"] == "overruled"
        assert by_target["ATF_145_III_72"]["treatment"] == "followed"
