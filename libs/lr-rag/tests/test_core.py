from __future__ import annotations

import json

from lr_rag import (
    MinorMajorPair,
    build_consideration_model,
    compute_document_cache_key,
    compute_faithfulness_cache_key,
    flatten_and_sanitize,
    prepare_chunks,
    sanitize_replace,
)


def test_sanitize_replace_removes_null_characters_recursively() -> None:
    sanitized = sanitize_replace(
        {"ke\x00y": ["va\x00lue"], "nested": {"a": "b\x00"}}
    )

    assert sanitized == {
        "key": ["value"],
        "nested": {"a": "b"},
    }


def test_flatten_and_sanitize_flattens_json_payload() -> None:
    flattened = json.loads(
        flatten_and_sanitize('{"section": {"a": "b"}, "items": ["x", "y"]}')
    )

    assert flattened == {"section": "a: b", "items": "x\ny"}


def test_cache_keys_are_stable_and_input_sensitive() -> None:
    assert compute_document_cache_key(
        "question", 1
    ) == compute_document_cache_key(
        "question",
        1,
    )
    assert compute_document_cache_key(
        "question", 1
    ) != compute_document_cache_key(
        "question",
        2,
    )
    assert compute_faithfulness_cache_key(
        "question",
        1,
        "answer",
        ["ctx"],
    ) != compute_faithfulness_cache_key(
        "question",
        1,
        "other",
        ["ctx"],
    )


def test_minor_major_pair_normalizes_aliases() -> None:
    pair = MinorMajorPair.model_validate(
        {"Majeures": ["A"], "Mineures": ["B"]}
    )

    assert pair.majeure == ["A"]
    assert pair.mineure == ["B"]


def test_build_consideration_model_creates_boolean_fields() -> None:
    model = build_consideration_model(2)
    parsed = model(argument_1=True, argument_2=False)

    assert parsed.argument_1 is True
    assert parsed.argument_2 is False


def test_prepare_chunks_uses_en_droit_tail() -> None:
    text = "FAITS\nEN DROIT\n" + ("contrat " * 200)
    chunks = prepare_chunks(text, chunk_size=80, chunk_overlap=10)

    assert chunks
    assert all("FAITS" not in chunk for chunk in chunks)
