from __future__ import annotations

from lr_legal import (
    NormRef,
    fedlex_url,
    resolve,
    resolve_citation,
    resolve_norm_token,
    rsge_url,
)


def test_fedlex_url_federal_code_with_article() -> None:
    assert (
        fedlex_url("CO", "336c", "fr")
        == "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/fr#art_336c"
    )


def test_fedlex_url_language_segment() -> None:
    assert fedlex_url("ZGB", "8", "de").endswith("/de#art_8")
    assert fedlex_url("CC", "8", "it").endswith("/it#art_8")
    # Unknown language falls back to French.
    assert fedlex_url("CC", "8", "xx").endswith("/fr#art_8")


def test_fedlex_url_unknown_code_is_none() -> None:
    assert fedlex_url("LPAC", "20", "fr") is None
    assert fedlex_url("Cst-GE", "21", "fr") is None


def test_fedlex_url_code_only_links_to_act() -> None:
    assert (
        fedlex_url("CP", None, "fr")
        == "https://www.fedlex.admin.ch/eli/cc/54/757_781_799/fr"
    )


def test_resolve_norm_token_full() -> None:
    ref = resolve_norm_token("CO.336c.al1.letb", "fr")
    assert ref is not None
    assert ref.code == "CO"
    assert ref.article == "336c"
    assert ref.subrefs == ("al. 1", "let. b")
    assert (
        ref.url
        == "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/fr#art_336c"
    )
    assert ref.label == "CO art. 336c al. 1 let. b"


def test_resolve_norm_token_constitution() -> None:
    ref = resolve_norm_token("Cst.29.al2", "fr")
    assert ref is not None
    assert ref.article == "29"
    assert ref.subrefs == ("al. 2",)
    assert ref.url == "https://www.fedlex.admin.ch/eli/cc/1999/404/fr#art_29"


def test_resolve_norm_token_geneva_cantonal_links_to_rsge() -> None:
    ref = resolve_norm_token("LIPAD.36.al1.leta", "fr")
    assert ref is not None
    assert ref.code == "LIPAD"
    assert ref.article == "36"
    # Geneva codes resolve to the rsGE act page (no per-article anchor).
    assert ref.url == "https://silgeneve.ch/legis/data/rsg_a2_08.htm"
    assert ref.label == "LIPAD art. 36 al. 1 let. a"


def test_resolve_norm_token_article_with_letter_suffix() -> None:
    ref = resolve_norm_token("RPAC.44A", "fr")
    assert ref is not None
    assert ref.article == "44A"
    # RPAC is a mapped Geneva code -> rsGE act page.
    assert ref.url == "https://silgeneve.ch/legis/data/rsg_b5_05p01.htm"


def test_resolve_norm_token_truly_unmapped_has_no_url() -> None:
    ref = resolve_norm_token("XYZ.5", "fr")
    assert ref is not None
    assert ref.code == "XYZ"
    assert ref.url is None
    assert ref.label == "XYZ art. 5"


def test_resolve_norm_token_empty() -> None:
    assert resolve_norm_token("", "fr") is None
    assert resolve_norm_token("   ", "fr") is None


def test_resolve_citation_french() -> None:
    ref = resolve_citation("art. 336c al. 1 let. b CO", "fr")
    assert ref is not None
    assert ref.code == "CO"
    assert ref.article == "336c"
    assert ref.subrefs == ("al. 1", "let. b")
    assert (
        ref.url
        == "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/fr#art_336c"
    )


def test_resolve_citation_german() -> None:
    ref = resolve_citation("Art. 336c OR", "de")
    assert ref is not None
    assert ref.code == "OR"
    assert (
        ref.url
        == "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/de#art_336c"
    )


def test_resolve_citation_no_match() -> None:
    assert resolve_citation("see the ruling above", "fr") is None
    assert resolve_citation("", "fr") is None


def test_resolve_prefers_citation_then_token() -> None:
    # Free-text form
    assert isinstance(resolve("art. 8 CC", "fr"), NormRef)
    # Compact token form
    ref = resolve("CP.111", "fr")
    assert ref is not None
    assert (
        ref.url
        == "https://www.fedlex.admin.ch/eli/cc/54/757_781_799/fr#art_111"
    )


def test_rsge_url_maps_geneva_codes() -> None:
    assert rsge_url("LPA") == "https://silgeneve.ch/legis/data/rsg_e5_10.htm"
    assert (
        rsge_url("Cst-GE") == "https://silgeneve.ch/legis/data/rsg_a2_00.htm"
    )
    assert rsge_url("LOJ") == "https://silgeneve.ch/legis/data/rsg_e2_05.htm"


def test_rsge_url_unknown_is_none() -> None:
    assert rsge_url("CO") is None  # federal, not a Geneva code
    assert rsge_url("XYZ") is None


def test_resolve_citation_geneva_cantonal() -> None:
    ref = resolve_citation("art. 65 LPA", "fr")
    assert ref is not None
    assert ref.code == "LPA"
    assert ref.url == "https://silgeneve.ch/legis/data/rsg_e5_10.htm"


def test_fedlex_takes_precedence_over_rsge() -> None:
    # A code present only in the federal map still resolves to Fedlex.
    ref = resolve_norm_token("CC.8", "fr")
    assert ref is not None
    assert ref.url is not None
    assert "fedlex.admin.ch" in ref.url
