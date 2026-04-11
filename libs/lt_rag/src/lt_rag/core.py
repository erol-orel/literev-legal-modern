from __future__ import annotations

import json

from hashlib import sha256
from typing import Any, Literal, cast

from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    field_validator,
    model_validator,
)

from lt_query import extract_after_endroit

INVALID_CHARS = ("\x00",)


class MinorMajorPair(BaseModel):
    model_config = ConfigDict(extra="ignore")

    majeure: list[str] = Field(default_factory=list)
    mineure: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_aliases(cls, incoming: Any) -> Any:
        if not isinstance(incoming, dict):
            return incoming

        maj = (
            incoming.get("majeure")
            or incoming.get("Majeure")
            or incoming.get("majeures")
            or incoming.get("Majeures")
        )
        minr = (
            incoming.get("mineure")
            or incoming.get("Mineure")
            or incoming.get("mineures")
            or incoming.get("Mineures")
        )

        if maj is not None:
            incoming["majeure"] = maj
        if minr is not None:
            incoming["mineure"] = minr
        return incoming


class RAGAnswer(BaseModel):
    answer: str = Field(..., description="The answer")
    highlight: str = Field(..., description="The most relevant context.")


class SummaryGeneralAnswer(BaseModel):
    summary: str = Field(..., description="The answer")
    considerations: list[str]


class ClosedAnswerClassification(BaseModel):
    answer: str = Field(..., description="Document answer")
    category: Literal["oui", "non", "peut_etre", "mixte"]

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        allowed = {"oui", "non", "peut_etre", "mixte"}
        if value not in allowed:
            raise ValueError(f"Invalid category: {value}")
        return value


class QuestionTypeClassification(BaseModel):
    question_type: Literal["open", "closed"]


def sanitize_text_replace(value: str) -> str:
    for invalid_char in INVALID_CHARS:
        value = value.replace(invalid_char, "")
    return value


def sanitize_replace(obj: Any) -> Any:
    if isinstance(obj, str):
        return sanitize_text_replace(obj)
    if isinstance(obj, list):
        return [sanitize_replace(item) for item in obj]
    if isinstance(obj, dict):
        return {
            (
                sanitize_text_replace(key) if isinstance(key, str) else key
            ): sanitize_replace(value)
            for key, value in obj.items()
        }
    return obj


def flatten_json_values(value: dict[str, Any]) -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            flattened[key] = "\n".join(
                f"{inner_key}: {inner_value}"
                for inner_key, inner_value in item.items()
            )
        elif isinstance(item, list):
            flattened[key] = "\n".join(str(entry) for entry in item)
        else:
            flattened[key] = str(item)
    return flattened


def flatten_and_sanitize(
    answer: str | dict[str, Any] | list[Any],
) -> str:
    sanitized_answer = sanitize_replace(answer)
    if isinstance(sanitized_answer, str):
        payload = json.loads(sanitized_answer)
    else:
        payload = sanitized_answer

    if not isinstance(payload, dict):
        raise TypeError("flatten_and_sanitize expects a JSON object payload")

    return json.dumps(flatten_json_values(payload), ensure_ascii=False)


def compute_document_cache_key(query: str, document_id: int) -> str:
    return sha256(f"{query.strip()}::{document_id}".encode()).hexdigest()


def compute_faithfulness_cache_key(
    query: str,
    document_id: int,
    answer: str,
    citation_context: list[str] | list[dict[str, Any]] | None,
) -> str:
    payload = {
        "query": query.strip(),
        "document_id": document_id,
        "answer": (answer or "").strip(),
        "citation_context": citation_context or [],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(blob.encode("utf-8")).hexdigest()


def build_consideration_model(count: int) -> type[BaseModel]:
    fields: dict[str, Any] = {
        f"argument_{index + 1}": (bool, ...) for index in range(count)
    }
    return cast(
        type[BaseModel],
        create_model("DynamicEvaluationModel", **fields),
    )


def prepare_chunks(
    text: str,
    *,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_text(extract_after_endroit(text))
