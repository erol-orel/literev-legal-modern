"""Unit tests for per-source embedding-engine routing in ``chroma_utils``.

These are network-free: the OpenAI and Hactar backends are mocked so the tests
assert only on *which* engine is chosen and *how* the Hactar request is shaped.
"""

from __future__ import annotations

from unittest import mock

from django.test import override_settings

from literev.libs import chroma_utils

FEDERAL_ENGINE_MAP = {
    "chambre_civile": "openai",
    "chambre_penale": "openai",
    "chambre_administrative": "openai",
    "bundesgericht": "hactar",
    "bundesverwaltungsgericht": "hactar",
    "bundesstrafgericht": "hactar",
}


@override_settings(SECTION_EMBED_ENGINE=FEDERAL_ENGINE_MAP)
def test_get_section_embed_engine_known_sources() -> None:
    assert chroma_utils.get_section_embed_engine("chambre_civile") == "openai"
    assert chroma_utils.get_section_embed_engine("bundesgericht") == "hactar"
    assert (
        chroma_utils.get_section_embed_engine("bundesstrafgericht") == "hactar"
    )


@override_settings(SECTION_EMBED_ENGINE=FEDERAL_ENGINE_MAP)
def test_get_section_embed_engine_defaults_to_openai() -> None:
    # Anything not registered keeps the historical OpenAI behaviour.
    assert chroma_utils.get_section_embed_engine("unknown_source") == "openai"


@override_settings(
    HACTAR_BASE_URL="https://hactar.example/",
    HACTAR_API_KEY="secret-token",
    HACTAR_EMBED_MODEL="mxbai-embed-large:latest",
    HACTAR_VERIFY_SSL=False,
)
def test_hactar_embed_request_shape() -> None:
    fake_response = mock.Mock()
    fake_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3]]}
    fake_response.raise_for_status.return_value = None

    with mock.patch.object(
        chroma_utils.requests, "post", return_value=fake_response
    ) as post:
        result = chroma_utils.hactar_embed(["bonjour"])

    assert result == [[0.1, 0.2, 0.3]]
    post.assert_called_once()
    _, kwargs = post.call_args
    # Trailing slash on the base URL must be collapsed, not doubled.
    assert post.call_args[0][0] == "https://hactar.example/ollama/api/embed"
    assert kwargs["json"] == {
        "model": "mxbai-embed-large:latest",
        "input": ["bonjour"],
    }
    assert kwargs["headers"]["Authorization"] == "Bearer secret-token"
    assert kwargs["verify"] is False


@override_settings(HACTAR_BASE_URL="https://hactar.example")
def test_hactar_embed_rejects_unexpected_payload() -> None:
    fake_response = mock.Mock()
    fake_response.json.return_value = {"unexpected": "shape"}
    fake_response.raise_for_status.return_value = None

    with mock.patch.object(
        chroma_utils.requests, "post", return_value=fake_response
    ):
        try:
            chroma_utils.hactar_embed(["x"])
        except ValueError:
            pass
        else:  # pragma: no cover - defensive
            raise AssertionError("expected ValueError on unexpected payload")


@override_settings(SECTION_EMBED_ENGINE=FEDERAL_ENGINE_MAP)
def test_embed_query_routes_federal_to_hactar() -> None:
    with (
        mock.patch.object(
            chroma_utils, "hactar_embed", return_value=[[9.0, 9.0]]
        ) as hactar,
        mock.patch.object(chroma_utils, "openai_client") as openai,
    ):
        vector = chroma_utils.embed_query("q", "bundesgericht")

    assert vector == [9.0, 9.0]
    hactar.assert_called_once_with(["q"])
    openai.embeddings.create.assert_not_called()


@override_settings(SECTION_EMBED_ENGINE=FEDERAL_ENGINE_MAP)
def test_embed_query_routes_chamber_to_openai() -> None:
    fake_openai_response = mock.Mock()
    fake_openai_response.data = [mock.Mock(embedding=[1.0, 2.0])]

    with (
        mock.patch.object(chroma_utils, "hactar_embed") as hactar,
        mock.patch.object(chroma_utils, "openai_client") as openai,
    ):
        openai.embeddings.create.return_value = fake_openai_response
        vector = chroma_utils.embed_query("q", "chambre_civile")

    assert vector == [1.0, 2.0]
    hactar.assert_not_called()
    openai.embeddings.create.assert_called_once()


def test_embed_texts_empty_is_noop() -> None:
    assert chroma_utils.embed_texts([], "hactar") == []
    assert chroma_utils.embed_texts([], "openai") == []
