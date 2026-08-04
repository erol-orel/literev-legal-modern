"""Tests for legal-norm URL enrichment in the document + RAG payloads.

These exercise the pure enrichment helpers (no database, no OpenAI): the
document ``standards`` splitter and the RAG ``law_articles`` URL resolver.
"""

from __future__ import annotations

from literev.libs.document_content import _build_standards_refs
from literev.libs.rag_workspace import _enrich_law_articles

FEDLEX_CO = "https://www.fedlex.admin.ch/eli/cc/27/317_321_377/fr"


def test_build_standards_refs_links_federal_and_keeps_cantonal() -> None:
    refs = _build_standards_refs("Cst.29.al2;LPAC.20;CO.336c.al1.letb")

    assert [r["token"] for r in refs] == [
        "Cst.29.al2",
        "LPAC.20",
        "CO.336c.al1.letb",
    ]
    by_token = {r["token"]: r for r in refs}
    # Federal codes resolve to Fedlex deep links.
    assert by_token["Cst.29.al2"]["url"] == (
        "https://www.fedlex.admin.ch/eli/cc/1999/404/fr#art_29"
    )
    assert by_token["CO.336c.al1.letb"]["url"] == f"{FEDLEX_CO}#art_336c"
    assert by_token["CO.336c.al1.letb"]["label"] == "CO art. 336c al. 1 let. b"
    # Cantonal (Geneva) code stays as plain text.
    assert by_token["LPAC.20"]["url"] is None
    assert by_token["LPAC.20"]["label"] == "LPAC art. 20"


def test_build_standards_refs_empty() -> None:
    assert _build_standards_refs("") == []
    assert _build_standards_refs("   ;  ;") == []


def test_enrich_law_articles_adds_url_for_federal_citation() -> None:
    rows = [
        {"article": "art. 336c CO", "content": "résiliation en temps inopportun"},
        {"article": "art. 20 LPAC", "content": "droit cantonal genevois"},
        {"content": "row without an article key"},
    ]
    enriched = _enrich_law_articles(rows)

    assert enriched[0]["article_url"] == f"{FEDLEX_CO}#art_336c"
    # Cantonal citation is left unlinked.
    assert "article_url" not in enriched[1]
    # Rows without an article are passed through untouched.
    assert "article_url" not in enriched[2]


def test_enrich_law_articles_non_list_is_empty() -> None:
    assert _enrich_law_articles(None) == []
    assert _enrich_law_articles("not a list") == []
