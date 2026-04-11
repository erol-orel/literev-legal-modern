from __future__ import annotations

from lr_preprocessing import pre_processing, sentences_to_words


def test_pre_processing_removes_common_noise() -> None:
    cleaned = pre_processing(
        "email test@example.org http://example.org contrat_bail"
    )

    assert "@" not in cleaned
    assert "http" not in cleaned
    assert "_" not in cleaned


def test_sentences_to_words_normalizes_case() -> None:
    assert sentences_to_words("Contrat de BAIL") == [
        "contrat",
        "de",
        "bail",
    ]
