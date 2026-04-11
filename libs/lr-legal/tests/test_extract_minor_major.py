from __future__ import annotations

from lr_legal import normalize_text, pack_chunks, split_sentences_fr_legal


def test_normalize_text_merges_wrapped_lines() -> None:
    normalized = normalize_text(
        "Premiere ligne sans point\nseconde ligne.\nTroisieme ligne."
    )

    assert normalized == (
        "Premiere ligne sans point seconde ligne. Troisieme ligne."
    )


def test_split_sentences_fr_legal_handles_abbreviations() -> None:
    sentences = split_sentences_fr_legal(
        "Selon l'art. 5 CPC. La demande est admise."
    )

    assert len(sentences) == 2
    assert sentences[0] == "Selon l'art. 5 CPC."
    assert sentences[1] == "La demande est admise."


def test_pack_chunks_groups_sentences() -> None:
    chunks = pack_chunks(
        ["Premiere phrase.", "Deuxieme phrase."],
        max_tokens=40,
        overlap_tokens=0,
    )

    assert chunks
    assert "Premiere phrase." in chunks[0]
