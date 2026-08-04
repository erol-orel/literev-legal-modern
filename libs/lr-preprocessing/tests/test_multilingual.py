"""Tests for multilingual (DE/FR/IT) preprocessing support.

The German/Italian spaCy models are optional and may be absent in CI, so these
tests exercise the language-agnostic behaviour and the graceful fallback that
kicks in when a model is missing — never assuming DE/IT models are installed.
"""

from __future__ import annotations

from lr_preprocessing import (
    clean_corpus,
    define_languages,
    detect_language,
)
from lr_preprocessing.utils import get_stopwords, lemmatize


def test_detect_language_supported() -> None:
    assert (
        detect_language("Le contrat de bail est résilié par le bailleur.")
        == "fr"
    )
    assert (
        detect_language("Der Mietvertrag wird vom Vermieter gekündigt.")
        == "de"
    )
    assert (
        detect_language("Il contratto di locazione è disdetto dal locatore.")
        == "it"
    )


def test_detect_language_unsupported_returns_none() -> None:
    # English is recognised but not a preprocessing language -> discarded.
    assert (
        detect_language("The lease agreement is terminated by the landlord.")
        is None
    )


def test_define_languages_backwards_compatible() -> None:
    assert define_languages("Le contrat de bail est résilié.") is True
    assert define_languages("Der Mietvertrag wird gekündigt.") is False


def test_lemmatize_falls_back_to_tokens_without_model() -> None:
    # An unknown code has no registered spaCy model -> tokens returned as-is.
    assert lemmatize(["contrat", "bail"], lang="xx") == "contrat bail"


def test_get_stopwords_unknown_language_is_empty() -> None:
    assert get_stopwords("xx") == set()


def test_get_stopwords_french_is_non_empty() -> None:
    french = get_stopwords("fr")
    assert isinstance(french, set) and french


def test_clean_corpus_without_model_keeps_content() -> None:
    # With no model/stopwords for 'xx', words survive (lowercased, denoised).
    out = clean_corpus("Contrat de bail résilié", lang="xx")
    assert "contrat" in out
    assert "bail" in out


def test_clean_corpus_french_is_non_empty() -> None:
    # The French model ships by default, so lemmatization runs and stopwords
    # are stripped, but substantive tokens remain.
    out = clean_corpus("Les contrats de bail sont résiliés par le bailleur")
    assert isinstance(out, str) and out.strip()
