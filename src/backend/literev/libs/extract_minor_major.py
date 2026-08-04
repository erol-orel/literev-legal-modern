from __future__ import annotations

from django.conf import settings
from openai import OpenAI

# Private helpers are re-exported so tests can reach them via this shim.
# They are not referenced directly in this module — the noqa comments keep
# ruff from stripping them as "unused imports".
from lr_legal.extract_minor_major import (  # noqa: F401
    Classification,
    _fix_mojibake,
    _ftfy,
    _normalize_classif_payload,
    _shield,
    _tail_tokens,
    _tlen,
    _unshield,
    build_user_prompt,
    classify_chunks_llm,
    expected_ids,
    get_sentences,
    materialize_classification,
    normalize_text,
    pack_chunks,
    split_sentences_fr_legal,
    validate_classification,
)
from lr_legal.extract_minor_major import (
    openai_llm_call as base_openai_llm_call,
)

# Built lazily on first use. The openai SDK raises when constructed without an
# API key, so eager construction broke test collection where OPENAI_API_KEY is
# unset (e.g. CI). Tests still monkeypatch this attribute with a fake client.
_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            api_key=getattr(settings, "OPENAI_API_KEY", "")
        )
    return _openai_client


def openai_llm_call(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = "gpt-4.1-mini",
    temperature: float = 0.0,
    max_tokens: int | None = None,
    json_only: bool = True,
    retries: int = 1,
    base_backoff: float = 0.8,
) -> str:
    return base_openai_llm_call(
        system_prompt,
        user_prompt,
        client=_get_openai_client(),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_only=json_only,
        retries=retries,
        base_backoff=base_backoff,
    )


__all__ = [
    "Classification",
    "build_user_prompt",
    "classify_chunks_llm",
    "expected_ids",
    "get_sentences",
    "materialize_classification",
    "normalize_text",
    "openai_llm_call",
    "pack_chunks",
    "split_sentences_fr_legal",
    "validate_classification",
]
