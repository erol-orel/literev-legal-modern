"""Tests for RAG."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import rago

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from literev.libs.rag_pdf import PDFRAG
from literev.models import Document, ProjectRAG


@pytest.fixture
def project_rag(project) -> ProjectRAG:
    query = (
        "Quelles sont les conditions nécessaires pour qu'une victime puisse "
        "obtenir une réparation morale selon l'art. 22 LAVI?"
    )
    project_rag = ProjectRAG(
        project=project,
        query=query,
        status="completed",
    )
    project_rag.save()
    return project_rag


@pytest.fixture
def doc2_txt() -> str:
    txt_path = Path(__file__).parent / "data" / "doc2_raw_document_text.txt"
    with open(txt_path) as f:
        return f.read()


@pytest.fixture
def doc2_txt_chunks(doc2_txt) -> list[str]:
    """Split text into smaller chunks for processing."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    )
    return text_splitter.split_text(doc2_txt)


def test_rag(project_rag: ProjectRAG, document_real: Document) -> None:
    docs_rag = PDFRAG(project_rag.id, [document_real.id])
    docs_rag.run()
    assert docs_rag.project_rag.documents.first().answer


def test_rago_text(doc2_txt) -> None:
    template_prompt = (
        "Based on the given context, answer to this question: `{query}`. "
        "If no information is available in the context, "
        "return `Réponse non disponible`, "
        "otherwise, give your answer in only one sentence in french with "
        "the most relevant information. Context: `{context}`"
    )
    query = (
        "quel est le montant du minimum vital en France dans le cadre d'un "
        "divorce avec enfants?"
    )

    api_params = {
        "top_p": 0.0,
        "frequency_penalty": 0.0,
        "presence_penalty": 0.0,
    }

    generation = rago.generation.OpenAIGen(
        api_key=settings.OPENAI_API_KEY,
        model_name="gpt-4o-mini",
        prompt_template=template_prompt,
        temperature=0,
        output_max_length=16384,
        api_params=api_params,
    )
    result = generation.generate(query, context=[doc2_txt])
    assert result not in [None, "", "Réponse non disponible"]


def test_rago_chunks(doc2_txt_chunks) -> None:
    query = (
        "quel est le montant du minimum vital en France dans le cadre d'un "
        "divorce avec enfants?"
    )
    augmented = rago.augmented.SpaCyAug(top_k=5, model_name="fr_core_news_lg")

    generation = rago.generation.OpenAIGen(
        api_key=settings.OPENAI_API_KEY,
        model_name="gpt-4o-mini",
        prompt_template=PDFRAG.template_prompt,
        temperature=0,
        output_max_length=16384,
    )

    rag = rago.Rago(
        retrieval=rago.retrieval.StringRet(doc2_txt_chunks),
        augmented=augmented,
        generation=generation,
    )
    result = rag.prompt(query)
    assert "réponse non disponible" not in result.lower()


def test_rag_aug_variation(doc2_txt_chunks) -> None:
    results = {}

    questions = [
        "minimum vital en France",
        "minimum vital en France?",
        "a combien se monte le",
        "Minimum vital en France?",
        "a combien se monte le minimum vital en France dans le cas d'un divorce?",
        "a combien se monte le minimum vital en France dans le cas d'un divorce avec enfant?",
        "montant minimum vital france divorce enfant",
    ]

    for q_id, question in enumerate(questions):
        results[q_id] = {"question": question}

        ret_logs: dict[str, Any] = {}
        aug_logs: dict[str, Any] = {}
        gen_logs: dict[str, Any] = {}

        augmented = rago.augmented.SpaCyAug(
            top_k=10,
            model_name="fr_core_news_lg",
            logs=aug_logs,
        )

        # augmented = rago.augmented.OpenAIAug(
        #     api_key=settings.OPENAI_API_KEY,
        #     top_k=10,
        #     model_name="text-embedding-ada-002",
        #     logs=aug_logs,
        # )

        # 'max_tokens is too large: 100000.
        # This model supports at most 16384 completion tokens,
        # whereas you provided 100000.',
        # 'type': 'invalid_request_error',
        # 'param': 'max_tokens', 'code': None}}
        generation = rago.generation.OpenAIGen(
            api_key=settings.OPENAI_API_KEY,
            model_name="gpt-4o-mini",
            prompt_template=PDFRAG.template_prompt,
            temperature=0,
            output_max_length=16384,
            api_params={
                "top_p": 0.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
            },
            logs=gen_logs,
        )

        rag = rago.Rago(
            retrieval=rago.retrieval.StringRet(doc2_txt_chunks, logs=ret_logs),
            augmented=augmented,
            generation=generation,
        )
        result = rag.prompt(question)

        results[q_id]["answer"] = result
        results[q_id]["aug_log"] = rag.logs["augmented"]
    import joblib

    joblib.dump(results, "/tmp/test_list.pkl")
