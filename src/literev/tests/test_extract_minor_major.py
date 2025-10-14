"""Test minor/major extraction and classification."""

import json
import re

import pytest

import literev.legal.extract_minor_major as extract_minor_major


def test_fix_mojibake_ftfy_branch(monkeypatch):
    monkeypatch.setattr(
        extract_minor_major, "_ftfy", lambda s: "OK-" + s, raising=False
    )
    assert extract_minor_major._fix_mojibake("X") == "OK-X"


def test_fix_mojibake_fallback_branch(monkeypatch):
    monkeypatch.setattr(extract_minor_major, "_ftfy", None, raising=False)
    dirty = "\u00e2\u0080\u0099"  # mojibake for RIGHT SINGLE QUOTE
    assert extract_minor_major._fix_mojibake(dirty) == "\u2019"


def test_normalize_text_merges_and_cleans():
    raw = "Ligne A\\nLigne B\\n\\tLigne C\\n"
    out = extract_minor_major.normalize_text(raw)
    assert "\n" not in out
    assert "Ligne A" in out and "Ligne B" in out and "Ligne C" in out
    assert "  " not in out


def test_get_sentences_handles_abbreviations():
    text = "Art. 1. Le test. M. Dupont. Fin."
    parts = extract_minor_major.get_sentences(text)
    # Should not split after "Art."
    assert any("Art. 1." in p for p in parts)
    assert any("Le test." in p for p in parts)


def test_split_sentences_fr_legal_core():
    text = "Consid. 1. Faits (cf. art. 5 LTF). Ensuite. 2.1. Règle."
    parts = extract_minor_major.split_sentences_fr_legal(text)
    # Must keep legal abbreviations protected
    assert any("cf. art. 5 LTF" in p for p in parts)
    # Must join 2.1. with what follows if present
    assert any(re.search(r"2\.1\.\s+Règle", p) for p in parts)


def test_shield_unshield_roundtrip():
    t = "cf. art. 5 LTF (voir p. 12.3)."
    sh = extract_minor_major._shield(t)
    # Protected areas must be dot-masked
    assert "cf⟂" in sh
    assert "art⟂" in sh
    assert "(voir p⟂ 12⟂3)." in sh  # final dot is sentence punctuation
    # No unmasked dot should remain *inside* the string (except the last)
    assert sh.endswith(".")
    assert "." not in sh[:-1]
    # Round-trip must restore the original text
    assert extract_minor_major._unshield(sh) == t


def test_tlen_tail_tokens_defined():
    # Both branches define _tlen/_tail_tokens; just sanity check
    assert callable(extract_minor_major._tlen)
    assert callable(extract_minor_major._tail_tokens)
    s = "abc def ghi jkl"
    assert extract_minor_major._tlen(s) >= 1
    tail = extract_minor_major._tail_tokens(s, keep=2)
    assert isinstance(tail, str)


def test_pack_chunks_overlap_and_wrap():
    sents = ["a " * 50, "b " * 50, "c " * 10]
    chunks = extract_minor_major.pack_chunks(
        sents, max_tokens=60, overlap_tokens=10
    )
    assert len(chunks) >= 2
    assert all(isinstance(c, str) and c.strip() for c in chunks)


def test_expected_ids_and_ids_to_indices_and_materialize():
    chunks = ["A", "B", "C"]
    result = extract_minor_major.Classification(
        majeure=["CHUNK_0", "CHUNK_2"], mineure=["CHUNK_1"]
    )
    maj, minu = extract_minor_major.materialize_classification(
        result, chunks, "document"
    )
    assert maj == ["A", "C"]
    assert minu == ["B"]


def test_validate_classification_messages():
    n = 2
    c = extract_minor_major.Classification(
        majeure=["CHUNK_0"], mineure=["CHUNK_0"]
    )
    ok, msg = extract_minor_major.validate_classification(n, c)
    assert not ok and "both" in msg.lower()

    c2 = extract_minor_major.Classification(majeure=["CHUNK_0"], mineure=[])
    ok2, msg2 = extract_minor_major.validate_classification(n, c2)
    assert not ok2 and "Missing" in msg2

    c3 = extract_minor_major.Classification(
        majeure=["CHUNK_0"], mineure=["CHUNK_1"]
    )
    ok3, _ = extract_minor_major.validate_classification(n, c3)
    assert ok3


def test_normalize_classif_payload_key_and_item_coercion():
    data = {"majeures": ["CHUNK_0", "1"], "mineures": ["CHUNK 2"]}
    fixed = extract_minor_major._normalize_classif_payload(3, data)
    assert fixed["majeure"] == ["CHUNK_0", "CHUNK_1"]
    assert fixed["mineure"] == ["CHUNK_2"]


def test_build_user_prompt_contains_all_chunks():
    chunks = ["A", "B"]
    p = extract_minor_major.build_user_prompt(chunks)
    assert "CHUNK_0" in p and "CHUNK_1" in p
    assert "«A»" in p and "«B»" in p


def test_openai_llm_call_retry_and_raise(monkeypatch):
    # Make the client always raise → should retry then raise RuntimeError
    class FakeClient:
        class chat:
            class completions:
                @staticmethod
                def create(**_):
                    raise RuntimeError("boom")

    monkeypatch.setattr(extract_minor_major, "_openai_client", FakeClient())
    with pytest.raises(RuntimeError):
        extract_minor_major.openai_llm_call(
            "sys", "user", retries=0
        )  # no retries → raise


def test_classify_chunks_llm_happy_path_and_set_policy():
    # 4 chunks: 0,1,2,3
    chunks = ["a", "b", "c", "d"]

    # LLM returns:
    # - unknown: CHUNK_9 (should be dropped)
    # - overlap: CHUNK_0 appears in both must land in mineure
    # - missing: CHUNK_2 must be appended to mineure
    payload = {
        "majeure": ["CHUNK_0", "CHUNK_1", "CHUNK_9"],
        "mineure": ["CHUNK_0", "CHUNK_3"],
    }

    def fake_llm(sys, usr):
        del sys, usr
        return json.dumps(payload, ensure_ascii=False)

    res = extract_minor_major.classify_chunks_llm(chunks, fake_llm)

    # Unknown dropped
    assert "CHUNK_9" not in res.majeure and "CHUNK_9" not in res.mineure
    # Overlap resolved to mineure
    assert "CHUNK_0" not in res.majeure and "CHUNK_0" in res.mineure
    # Missing appended to mineure
    assert "CHUNK_2" in res.mineure
    # All IDs covered
    assert set(res.majeure + res.mineure) == set(
        extract_minor_major.expected_ids(4)
    )


def test_classify_chunks_llm_bad_json_raises():
    def bad_llm(_s, _u):
        return "not-json"

    with pytest.raises(ValueError):
        extract_minor_major.classify_chunks_llm(["x"], bad_llm)
