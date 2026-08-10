"""Tests for the entscheidsuche.ch -> app ES schema mapper."""

from __future__ import annotations

from literev.libs.entscheidsuche import detect_language, map_hit
from literev.management.commands.import_entscheidsuche import bulk_actions

# Shape mirrors a live CH_BGer hit's ``_source`` (2026 schema).
SAMPLE = {
    "id": "CH_BGer_002_9C-130-2023_2023-03-01",
    "date": "2023-03-01",
    "canton": "CH",
    "hierarchy": ["CH", "CH_BGer", "CH_BGer_002"],
    "reference": ["9C 130/2023", "9C_130/2023"],
    "abstract": {
        "de": "Regeste (de).",
        "fr": "Regeste de la décision.",
        "it": "Regesto (it).",
    },
    "title": {
        "de": "Bundesgericht ...",
        "fr": "Tribunal fédéral, IIe Cour de droit public ...",
        "it": "Tribunale federale ...",
    },
    "meta": {
        "de": "II. ...",
        "fr": "IIe Cour de droit public",
        "it": "II ...",
    },
    "attachment": {
        "language": "fr",
        "content_type": "text/html; charset=UTF-8",
        "content_url": "https://entscheidsuche.ch/docs/CH_BGer/x.html",
        "content": "Texte complet de l'arrêt du Tribunal fédéral.",
    },
}


def test_map_hit_maps_core_fields() -> None:
    doc = map_hit(SAMPLE, collector_name="bundesgericht")
    assert doc is not None
    assert doc["record_key"] == SAMPLE["id"]
    assert doc["document_text"].startswith("Texte complet")
    assert doc["collector_name"] == "bundesgericht"
    assert doc["decision_date"] == "2023-03-01"
    assert doc["decision_type"] == "9C 130/2023"
    assert doc["procedure_type"] == "Tribunal fédéral (Bundesgericht)"
    assert doc["summary"] == "Regeste de la décision."
    assert doc["language"] == "fr"


def test_map_hit_uses_attachment_language() -> None:
    source = {
        **SAMPLE,
        "attachment": {**SAMPLE["attachment"], "language": "de"},
    }
    doc = map_hit(source, collector_name="bundesgericht")
    assert doc is not None
    assert doc["language"] == "de"
    # localized fields follow the detected language
    assert doc["summary"] == "Regeste (de)."


def test_map_hit_accepts_attachment_list() -> None:
    source = {
        **SAMPLE,
        "attachment": [{"language": "fr", "content": "Full text here."}],
    }
    doc = map_hit(source, collector_name="bundesgericht")
    assert doc is not None
    assert doc["document_text"] == "Full text here."


def test_map_hit_skips_without_text() -> None:
    source = {k: v for k, v in SAMPLE.items() if k != "attachment"}
    assert map_hit(source, collector_name="bundesgericht") is None


def test_map_hit_skips_without_signature() -> None:
    source = {k: v for k, v in SAMPLE.items() if k != "id"}
    assert map_hit(source, collector_name="bundesgericht") is None


def test_map_hit_labels_court_from_hierarchy() -> None:
    source = {
        **SAMPLE,
        "hierarchy": ["CH", "CH_BVGE", "CH_BVGE_001"],
    }
    doc = map_hit(source, collector_name="bundesverwaltungsgericht")
    assert doc is not None
    assert doc["procedure_type"] == "Tribunal administratif fédéral"


def test_detect_language() -> None:
    assert detect_language({"attachment": {"language": "de"}}) == "de"
    assert detect_language({"attachment": {"language": "IT"}}) == "it"
    assert detect_language({"language": "fr"}) == "fr"  # legacy fallback
    assert detect_language({"attachment": {"language": "rm"}}) == ""
    assert detect_language({}) == ""


def test_bulk_actions_shapes_index_requests() -> None:
    docs = [
        {"record_key": "CH_BGer_1", "document_text": "un", "language": "fr"},
        {"record_key": "CH_BGer_2", "document_text": "deux", "language": "fr"},
    ]
    actions = list(bulk_actions("bundesgericht", docs))
    assert len(actions) == 2
    assert actions[0] == {
        "_index": "bundesgericht",
        "_id": "CH_BGer_1",
        "_source": docs[0],
    }
    # the id is the record_key, so re-imports overwrite rather than duplicate
    assert actions[1]["_id"] == "CH_BGer_2"
    assert actions[1]["_index"] == "bundesgericht"


def test_bulk_actions_is_lazy() -> None:
    # Generator: nothing is consumed from the source until iterated.
    def _explode() -> object:
        raise AssertionError("bulk_actions must not eagerly consume input")
        yield  # pragma: no cover

    bulk_actions("bundesgericht", _explode())  # no iteration -> no error
