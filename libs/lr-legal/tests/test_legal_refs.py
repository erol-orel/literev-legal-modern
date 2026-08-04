from __future__ import annotations

from lr_legal import (
    NormRef,
    fedlex_url,
    resolve,
    resolve_citation,
    resolve_norm_token,
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


def test_resolve_norm_token_cantonal_unmapped_keeps_label_no_url() -> None:
    ref = resolve_norm_token("LIPAD.36.al1.leta", "fr")
    assert ref is not None
    assert ref.code == "LIPAD"
    assert ref.article == "36"
    assert ref.url is None
    assert ref.label == "LIPAD art. 36 al. 1 let. a"


def test_resolve_norm_token_article_with_letter_suffix() -> None:
    ref = resolve_norm_token("RPAC.44A", "fr")
    assert ref is not None
    assert ref.article == "44A"
    assert ref.url is None  # RPAC is cantonal, unmapped


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
