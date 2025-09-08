"""Test RAG classification builder."""

from __future__ import annotations

import os

from typing import Any, Dict

import pytest

from django.conf import settings

from literev.libs.rag_pdf import DocumentCache, RAGClassificationBuilder
from literev.models import Document, Project


@pytest.fixture
def project(db) -> Project:
    return Project.objects.create(name="RAG Test Project")


@pytest.fixture
def builder(monkeypatch, tmp_path) -> RAGClassificationBuilder:
    # Isolate cache into a temp dir so tests don't write to prod paths
    monkeypatch.setenv("LITEREV_CACHE_DIR", str(tmp_path))
    return RAGClassificationBuilder()


@pytest.fixture
def short_doc(db, project: Project) -> Document:
    # Small EN DROIT section
    txt = (
        "FAITS\nLe père n'a pas versé la pension.\n\n"
        "EN DROIT\nSelon l'article 371-2 du Code civil, "
        "chacun des parents contribue à l'entretien et à l'éducation des enfants. "
        "En l'espèce, les paiements ont cessé en janvier 2024.\n"
        "Le juge peut fixer une contribution en tenant compte des ressources et des besoins.\n"
    )
    return Document.objects.create(
        project=project,
        procedure_type="ProcTest",
        raw_document_id=None,  # force fallback to builder._safe_raw_key(..., id)
        raw_document_text=txt,
    )


@pytest.fixture
def long_doc(db, project: Project) -> Document:
    # Large EN DROIT section
    droit = (
        "EN DROIT\n"
        "La règle de droit impose l'obligation alimentaire. "
        "Chaque parent doit contribuer en fonction de ses ressources. "
        "Le juge apprécie au regard des éléments chiffrés et des besoins concrets.\n"
    )
    txt = "FAITS\nHistorique factuel...\n\n" + (droit * 250)
    return Document.objects.create(
        project=project,
        procedure_type="ProcLong",
        raw_document_id="GENEVA-808081",
        raw_document_text=txt,
    )


# Skip networked tests if no API key
requires_openai = pytest.mark.skipif(
    not getattr(settings, "OPENAI_API_KEY", "")
    and not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not configured; skipping live classification tests.",
)


def test_safe_raw_key_formats(
    builder: RAGClassificationBuilder, db, project: Project
):
    doc = Document.objects.create(
        project=project, procedure_type="P", raw_document_text="x"
    )
    assert builder._safe_raw_key(None, doc.id) == f"doc_{doc.id}"
    assert builder._safe_raw_key("ABC-123", doc.id) == "ABC-123"
    assert builder._safe_raw_key("  ", doc.id) == f"doc_{doc.id}"


def test_clean_ws_collapse(builder: RAGClassificationBuilder):
    dirty = "Texte\xa0avec\u202fespaces   multiples\n\n   et retours  "
    cleaned = builder._clean_ws(dirty)
    assert cleaned == "Texte avec espaces multiples et retours"


def test_normalize_field_to_list_and_invalid(
    builder: RAGClassificationBuilder,
):
    assert builder.normalize_field_to_list(None) == []
    assert builder.normalize_field_to_list("A") == ["A"]
    assert builder.normalize_field_to_list([" A ", "", "B"]) == ["A", "B"]
    # invalid answers should be caught
    assert builder.is_invalid_list([]) is True
    assert builder.is_invalid_list(["", "Réponse non disponible"]) is True
    assert builder.is_invalid_list(["Quelque chose"]) is False


def test_slice_text_by_lines_limits_and_wrapping(
    builder: RAGClassificationBuilder,
):
    # Includes blank lines and a long single line to exercise the hard-wrap branch
    text = "L1 courte\n\nL2 très longue: " + ("x" * 130) + "\nL3 fin\n"
    parts = builder.slice_text_by_lines(text, max_chars=60)
    assert all(len(p) <= 60 for p in parts)
    # The long line should cause >1 slices overall
    assert len(parts) >= 3
    # Ensure order is preserved across slices (first token should appear first)
    assert parts[0].startswith("L1 courte")


def test_document_cache_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("LITEREV_CACHE_DIR", str(tmp_path))
    cache = DocumentCache()
    payload: Dict[str, Any] = {
        "raw_document_id": "80801",
        "results": [{"majeures": ["R1"], "mineures": ["F1", "F2"]}],
    }
    engine = "openai"
    cache.save("80801", engine, payload)
    loaded = cache.load("80801", engine)
    assert loaded == payload


def test_build_corpus_from_lists(
    builder: RAGClassificationBuilder, db, project: Project
):
    doc = Document.objects.create(
        project=project,
        procedure_type="ProcX",
        raw_document_id="80801",
        raw_document_text="EN DROIT\n(irrelevant for this test)",
    )
    raw_key = builder._safe_raw_key(doc.raw_document_id, doc.id)

    results_by_document = {
        raw_key: {
            "raw_document_id": raw_key,
            "results": [
                {
                    "mineures": [" Fait A ", "Fait A", "Fait B"],
                    "majeures": [" Règle 1 "],
                },
                {"mineures": ["Fait C"], "majeures": []},
            ],
        }
    }

    corpus = builder.build_corpus_from_lists(
        results_by_document, field="mineures"
    )

    # Order and duplicates are preserved
    texts = [text for (text, _raw_id, _item_index) in corpus]
    assert texts == ["Fait A", "Fait A", "Fait B", "Fait C"]

    # Same raw_id for all
    raw_ids = [raw_id for (_text, raw_id, _item_index) in corpus]
    assert all(raw_id == raw_key for raw_id in raw_ids)

    # Per-row item_index is preserved (0,1,2 from first row; 0 from second row)
    item_indexes = [item_index for (_text, _raw_id, item_index) in corpus]
    assert item_indexes == [0, 1, 2, 0]


def test_get_fragments_for_answering_from_cache(
    builder: RAGClassificationBuilder, db, project: Project
):
    # Build a doc
    doc = Document.objects.create(
        project=project,
        procedure_type="ProcY",
        raw_document_id="CACHE-ONLY-2",
        raw_document_text="EN DROIT\n(content ignored here)",
    )
    raw_key = builder._safe_raw_key(doc.raw_document_id, doc.id)
    # Prime the cache with duplicates and a long fragment to trigger wrapping
    long_frag = "Phrase " * 300
    aggregated = {
        "raw_document_id": raw_key,
        "results": [
            {
                "mineures": [
                    "Fait pertinent 1",
                    "Fait pertinent 1",
                    long_frag,
                ],
                "majeures": ["Règle 1"],
            },
            {"mineures": ["Fait pertinent 2"], "majeures": []},
        ],
    }
    builder.cache.save(raw_key, "openai", aggregated)

    chunks = builder.get_fragments_for_answering(
        doc, engine="openai", field="mineures", max_chars_per_chunk=160
    )
    assert any("Fait pertinent 1" in c for c in chunks)
    assert any("Fait pertinent 2" in c for c in chunks)
    assert any(len(c) <= 160 for c in chunks)


def test_load_or_classify_document_cache_hit(
    builder: RAGClassificationBuilder, db, project: Project
):
    doc = Document.objects.create(
        project=project,
        procedure_type="ProcZ",
        raw_document_id="80801",
        raw_document_text="EN DROIT\n(x)",
    )
    raw_key = builder._safe_raw_key(doc.raw_document_id, doc.id)
    primed = {
        "raw_document_id": raw_key,
        "results": [{"majeures": ["R"], "mineures": ["F"]}],
    }
    builder.cache.save(raw_key, "openai", primed)

    loaded = builder.load_or_classify_document(doc, engine="openai")
    assert loaded == primed


@requires_openai
@pytest.mark.flaky(reruns=2, rerun_except="AssertionError")
@pytest.mark.django_db
def test_classify_whole_section_path(
    builder: RAGClassificationBuilder, short_doc: Document
):
    engine = "openai"
    aggregated = builder.classify_document_minor_major(
        short_doc, engine=engine
    )

    raw_key = builder._safe_raw_key(short_doc.raw_document_id, short_doc.id)
    # Payload should carry the raw key (not the cache key prefix)
    assert aggregated.get("raw_document_id") == raw_key
    assert "results" in aggregated

    # Verify it was persisted under the cache key
    cache_key = f"classify_doc_{raw_key}_{engine}"
    cache_file = builder.cache._document_cache()
    cached = cache_file.load(cache_key)
    assert cached is not None
    assert cached.get("raw_document_id") == raw_key


@requires_openai
@pytest.mark.flaky(reruns=2, rerun_except="AssertionError")
@pytest.mark.django_db
def test_classify_slice_fallback_path(
    builder: RAGClassificationBuilder, long_doc: Document
):
    engine = "openai"
    aggregated = builder.classify_document_minor_major(long_doc, engine=engine)

    raw_key = builder._safe_raw_key(long_doc.raw_document_id, long_doc.id)
    assert aggregated.get("raw_document_id") == raw_key
    assert "results" in aggregated

    # Ensure cache entry exists with the correct key format
    cache_key = f"classify_doc_{raw_key}_{engine}"
    cache_file = builder.cache._document_cache()
    cached = cache_file.load(cache_key)
    assert cached is not None
    assert cached.get("raw_document_id") == raw_key

    # And calling again should hit cache
    cached_again = builder.load_or_classify_document(long_doc, engine=engine)
    assert cached_again is not None
    assert cached_again.get("raw_document_id") == raw_key
