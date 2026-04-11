"""Tests for RAGClassificationBuilder and DocumentCache."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import literev.libs.rag_pdf as rag_pdf  # <— add this import

from literev.libs.rag_pdf import (
    DocumentCache,
    RAGClassificationBuilder,
)
from literev.models import Document, Project


@pytest.fixture
def project(db) -> Project:
    return Project.objects.create(name="RAG Test Project")


@pytest.fixture
def tmp_cache(monkeypatch, tmp_path) -> Path:
    monkeypatch.setenv("LITEREV_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(rag_pdf, "CACHE_DIR", tmp_path, raising=True)
    return tmp_path


@pytest.fixture
def builder(tmp_cache) -> RAGClassificationBuilder:
    _builder = RAGClassificationBuilder()
    _builder.cache = DocumentCache()
    return _builder


@pytest.fixture
def sample_doc(db, project: Project) -> Document:
    text = (
        "FAITS\nLe père n’a pas payé.\n\n"  # noqa: RUF001
        "EN DROIT\nSelon l’art. 371-2 du Code civil, "  # noqa: RUF001
        "chaque parent contribue à l’entretien des enfants. "  # noqa: RUF001
        "En l’espèce, les paiements ont cessé en janvier 2024."  # noqa: RUF001
    )
    return Document.objects.create(
        project=project,
        raw_document_text=text,
        raw_document_id=None,
        procedure_type="ProcTest",
    )


def test_document_cache_save_and_load(tmp_cache):
    cache = DocumentCache()
    engine = "openai"
    payload = {
        "raw_document_id": "80801",
        "results": [{"majeures": [], "mineures": []}],
    }

    cache.save("80801", engine, payload)
    loaded = cache.load("80801", engine)
    assert loaded == payload

    miss = cache.load("404", engine)
    assert miss is None


def test_safe_raw_key_and_normalization(
    builder: RAGClassificationBuilder, project: Project, db
):
    doc = Document.objects.create(
        project=project,
        procedure_type="Proc",
        raw_document_text="x",
        raw_document_id=None,
    )
    assert builder._safe_raw_key(None, doc.id) == f"doc_{doc.id}"
    assert builder._safe_raw_key("ABC", doc.id) == "ABC"
    assert builder._safe_raw_key("   ", doc.id).startswith("doc_")


def test_normalize_field_to_list_and_invalid(
    builder: RAGClassificationBuilder,
):
    assert builder.normalize_field_to_list(None) == []
    assert builder.normalize_field_to_list("X") == ["X"]
    assert builder.normalize_field_to_list([" a ", "", "b"]) == ["a", "b"]

    assert builder.is_invalid_list([]) is True
    assert builder.is_invalid_list(["", "réponse non disponible"]) is True
    assert builder.is_invalid_list(["Valid"]) is False


def test_classify_by_sentences(monkeypatch, builder: RAGClassificationBuilder):
    """Test one-shot classification path (sentence mode)."""
    fake_chunks = ["chunk1", "chunk2"]
    fake_result = MagicMock()
    fake_result.majeure = ["CHUNK_0"]
    fake_result.mineure = ["CHUNK_1"]

    with (
        patch("literev.libs.rag_pdf.get_sentences", return_value=fake_chunks),
        patch(
            "literev.libs.rag_pdf.classify_chunks_llm",
            return_value=fake_result,
        ),
        patch(
            "literev.libs.rag_pdf.materialize_classification",
            return_value=(["maj"], ["min"]),
        ),
    ):
        rows = builder._classify_by_sentences("openai", "doc_1", "EN DROIT...")
        assert isinstance(rows, list)
        assert rows and set(rows[0].keys()) == {"majeures", "mineures"}


def test_classify_by_sentences_invalid_list(
    monkeypatch, builder: RAGClassificationBuilder
):
    """Return empty if both majeure and mineure invalid."""
    fake_chunks = ["chunk1"]
    fake_result = MagicMock(majeure=["CHUNK_0"], mineure=[])

    with (
        patch("literev.libs.rag_pdf.get_sentences", return_value=fake_chunks),
        patch(
            "literev.libs.rag_pdf.classify_chunks_llm",
            return_value=fake_result,
        ),
        patch(
            "literev.libs.rag_pdf.materialize_classification",
            return_value=([], []),
        ),
    ):
        rows = builder._classify_by_sentences("openai", "doc_2", "EN DROIT...")
        assert rows == []


def test_classify_by_slices_fallback(
    monkeypatch, builder: RAGClassificationBuilder
):
    """Test fallback using legal-aware sentence splitting."""
    fake_chunks = ["c1", "c2"]
    fake_result = MagicMock(majeure=["CHUNK_0"], mineure=["CHUNK_1"])

    with (
        patch(
            "literev.libs.rag_pdf.split_sentences_fr_legal",
            return_value=["A", "B"],
        ),
        patch("literev.libs.rag_pdf.pack_chunks", return_value=fake_chunks),
        patch(
            "literev.libs.rag_pdf.classify_chunks_llm",
            return_value=fake_result,
        ),
        patch(
            "literev.libs.rag_pdf.materialize_classification",
            return_value=(["maj"], ["min"]),
        ),
    ):
        rows = builder._classify_by_slices("doc_X", "text...")
        assert rows and "mineures" in rows[0]


def test_classify_by_slices_empty(
    monkeypatch, builder: RAGClassificationBuilder
):
    """No chunks → returns [] without errors."""
    with patch("literev.libs.rag_pdf.pack_chunks", return_value=[]):
        rows = builder._classify_by_slices("doc_empty", "text...")
        assert rows == []


def test_classify_by_slices_exception(
    monkeypatch, builder: RAGClassificationBuilder
):
    """If internal exception occurs, logs warning and continues."""
    with patch(
        "literev.libs.rag_pdf.split_sentences_fr_legal",
        side_effect=RuntimeError("fail"),
    ):
        rows = builder._classify_by_slices("doc_err", "text...")
        assert isinstance(rows, list)


def test_classify_document_minor_major_sentence_path(
    monkeypatch, builder: RAGClassificationBuilder, sample_doc: Document
):
    """Validate that classification is saved to cache and returned."""
    fake_result = [{"majeures": ["maj"], "mineures": ["min"]}]
    with patch.object(
        builder, "_classify_by_sentences", return_value=fake_result
    ):
        aggregated = builder.classify_document_minor_major(
            sample_doc, engine="openai"
        )
        assert aggregated["results"] == fake_result

        raw_key = builder._safe_raw_key(
            sample_doc.raw_document_id, sample_doc.id
        )
        key = f"classify_doc_{raw_key}_openai"
        cached = builder.cache._document_cache().load(key)
        assert cached and cached["results"] == fake_result


def test_classify_document_minor_major_fallback(
    monkeypatch, builder: RAGClassificationBuilder, sample_doc: Document
):
    """If sentence path empty, fallback to slices."""
    with (
        patch.object(builder, "_classify_by_sentences", return_value=[]),
        patch.object(
            builder,
            "_classify_by_slices",
            return_value=[{"majeures": ["m"], "mineures": ["n"]}],
        ),
    ):
        agg = builder.classify_document_minor_major(
            sample_doc, engine="openai"
        )
        assert "results" in agg and agg["results"][0]["majeures"] == ["m"]


def test_load_or_classify_document_cache_hit(
    builder: RAGClassificationBuilder, sample_doc: Document
):
    """load_or_classify_document should use cache when available."""
    raw_key = builder._safe_raw_key(sample_doc.raw_document_id, sample_doc.id)
    cached = {
        "raw_document_id": raw_key,
        "results": [{"majeures": ["A"], "mineures": ["B"]}],
    }
    builder.cache.save(raw_key, "openai", cached)

    result = builder.load_or_classify_document(sample_doc, engine="openai")
    assert result == cached


def test_load_or_classify_document_cache_miss(
    builder: RAGClassificationBuilder, sample_doc: Document
):
    with patch.object(
        builder, "classify_document_minor_major", return_value={"ok": True}
    ) as mocked:
        out = builder.load_or_classify_document(sample_doc, engine="openai")
    assert out == {"ok": True}
    mocked.assert_called_once()


def test_cache_file_creation_and_reload(
    builder: RAGClassificationBuilder, sample_doc: Document
):
    """Ensure cache files are created correctly."""
    fake_data = {
        "raw_document_id": "x",
        "results": [{"majeures": ["M"], "mineures": ["N"]}],
    }
    builder.cache.save("x", "openai", fake_data)
    loaded = builder.cache.load("x", "openai")
    assert loaded == fake_data
    dir_path = builder.cache.cache_dir / "documents"
    assert any(f.suffix == ".pkl" for f in dir_path.iterdir())
