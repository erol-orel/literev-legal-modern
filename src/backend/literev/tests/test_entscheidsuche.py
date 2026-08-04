"""Tests for the entscheidsuche.ch -> app ES schema mapper."""

from __future__ import annotations

from literev.libs.entscheidsuche import detect_language, map_hit

SAMPLE = {
    "Signatur": "CH_BGer_001_6B-1234-2024_2024-06-07",
    "Spider": "CH_BGer",
    "Sprache": "fr",
    "Datum": "2024-06-07",
    "Kanton": "CH",
    "Gericht": "Tribunal fédéral",
    "Num": ["6B_1234/2024"],
    "Rechtsgebiet": "Droit pénal",
    "Abstract": "Résumé de la décision.",
    "attachment": {"content": "Texte complet de l'arrêt du Tribunal fédéral."},
}


def test_map_hit_maps_core_fields() -> None:
    doc = map_hit(SAMPLE, collector_name="bundesgericht")
    assert doc is not None
    assert doc["record_key"] == SAMPLE["Signatur"]
    assert doc["document_text"].startswith("Texte complet")
    assert doc["document"] == doc["document_text"]
    assert doc["collector_name"] == "bundesgericht"
    assert doc["decision_date"] == "2024-06-07"
    assert doc["decision_type"] == "6B_1234/2024"
    assert doc["procedure_type"] == "Tribunal fédéral (Bundesgericht)"
    assert doc["descriptors"] == "Droit pénal"
    assert doc["summary"] == "Résumé de la décision."
    assert doc["language"] == "fr"


def test_map_hit_accepts_attachment_list() -> None:
    source = {**SAMPLE, "attachment": [{"content": "Full text here."}]}
    doc = map_hit(source, collector_name="bundesgericht")
    assert doc is not None
    assert doc["document_text"] == "Full text here."


def test_map_hit_skips_without_text() -> None:
    source = {k: v for k, v in SAMPLE.items() if k != "attachment"}
    assert map_hit(source, collector_name="bundesgericht") is None


def test_map_hit_skips_without_signature() -> None:
    source = {k: v for k, v in SAMPLE.items() if k != "Signatur"}
    assert map_hit(source, collector_name="bundesgericht") is None


def test_map_hit_falls_back_to_spider_label_for_unknown_court() -> None:
    source = {**SAMPLE, "Gericht": "", "Spider": "CH_BVGer"}
    doc = map_hit(source, collector_name="bundesverwaltungsgericht")
    assert doc is not None
    assert doc["procedure_type"] == "Tribunal administratif fédéral"


def test_detect_language() -> None:
    assert detect_language({"Sprache": "de"}) == "de"
    assert detect_language({"Sprache": "IT"}) == "it"
    assert detect_language({"language": "fr"}) == "fr"
    assert detect_language({"Sprache": "rm"}) == ""  # Romansh unsupported here
    assert detect_language({}) == ""
