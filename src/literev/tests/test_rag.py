"""Tests for the RAG implementation."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import rago

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter

from literev.libs.rag_pdf import PDFRAG, RAGAnswer
from literev.models import Document, ProjectDocumentRAG, ProjectRAG


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


@pytest.mark.flaky(reruns=3, rerun_except="AssertionError")
def test_rag(project_rag: ProjectRAG, document_real: Document) -> None:
    docs_rag = PDFRAG(project_rag.id, [document_real.id])
    docs_rag.run()
    assert docs_rag.project_rag.documents.first().answer


@pytest.mark.flaky(reruns=3, rerun_except="AssertionError")
def test_rago_text(doc2_txt) -> None:
    template_prompt = (
        "Based on the given context, answer to this question: `{query}`. "
        "If no information is available in the context, "
        "return `Réponse non disponible`, "
        "otherwise, give your answer in only one sentence in french with "
        "the most relevant information. Context: `{context}`"
    )
    query = "minimum vital en France"

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
        structured_output=RAGAnswer,
    )
    result = generation.generate(query, context=[doc2_txt])
    assert "réponse non disponible" not in result.answer.lower()


@pytest.mark.flaky(reruns=3, rerun_except="AssertionError")
def test_rago_chunks(doc2_txt_chunks) -> None:
    query = (
        "quel est le montant du minimum vital en France dans le cadre d'un "
        "divorce avec enfants?"
    )
    augmented = rago.augmented.OpenAIAug(
        api_key=settings.OPENAI_API_KEY,
        top_k=5,
        model_name="text-embedding-ada-002",
    )

    generation = rago.generation.OpenAIGen(
        api_key=settings.OPENAI_API_KEY,
        model_name="gpt-4o-mini",
        prompt_template=PDFRAG.template_prompt,
        temperature=0,
        output_max_length=16384,
        structured_output=RAGAnswer,
    )

    rag = rago.Rago(
        retrieval=rago.retrieval.StringRet(doc2_txt_chunks),
        augmented=augmented,
        generation=generation,
    )
    result = rag.prompt(query)
    assert "réponse non disponible" not in result.answer.lower()
    assert result.highlight


@pytest.mark.flaky(reruns=3, rerun_except="AssertionError")
def test_rag_aug_variation(doc2_txt_chunks) -> None:
    results = {}

    questions = [
        "minimum vital en France",
        "minimum vital en France?",
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

        augmented = rago.augmented.OpenAIAug(
            api_key=settings.OPENAI_API_KEY,
            top_k=5,
            model_name="text-embedding-ada-002",
            logs=aug_logs,
        )

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
            structured_output=RAGAnswer,
            logs=gen_logs,
        )

        rag = rago.Rago(
            retrieval=rago.retrieval.StringRet(doc2_txt_chunks, logs=ret_logs),
            augmented=augmented,
            generation=generation,
        )
        result = rag.prompt(question)

        assert "réponse non disponible" not in result.answer.lower()
        assert result.highlight


@pytest.mark.django_db
@patch("literev.libs.rag_pdf.OpenAIGen")
def test_generate_general_summary_with_valid_answers(
    mock_openai_gen, project_rag
):
    from literev.models import Document, ProjectDocumentRAG

    # Create mock documents
    doc1 = Document.objects.create(
        project=project_rag.project, procedure_type="ProcA"
    )
    doc2 = Document.objects.create(
        project=project_rag.project, procedure_type="ProcB"
    )

    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc1,
        answer="Première réponse pertinente.",
        citation="Texte cité 1.",
        confidence_score=0.9,
    )
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc2,
        answer="Deuxième réponse pertinente.",
        citation="Texte cité 2.",
        confidence_score=0.85,
    )

    mock_summary_obj = MagicMock()
    mock_summary_obj.summary = "Résumé généré basé sur les réponses."
    mock_summary_obj.considerations = ["Considération A", "Considération B"]
    mock_openai_gen.return_value.generate.return_value = mock_summary_obj

    rag_processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    rag_processor.project_rag = project_rag
    rag_processor.generate_general_summary()

    result = json.loads(rag_processor.project_rag.summary_answer)

    assert result["summary"] == "Résumé généré basé sur les réponses."
    assert "Considération A" in result["considerations"][0]["text"]
    assert "Considération B" in result["considerations"][1]["text"]


@pytest.mark.django_db
@patch("literev.libs.rag_pdf.ProjectDocumentRAG.objects.filter")
@patch("literev.libs.rag_pdf.OpenAIGen")
def test_generate_general_summary_no_valid_answers(
    mock_openai_gen, mock_doc_filter, project_rag
):
    mock_queryset = MagicMock()
    mock_queryset.exclude.return_value.values_list.return_value = []
    mock_doc_filter.return_value = mock_queryset

    rag_processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    rag_processor.project_rag = project_rag
    rag_processor.generate_general_summary()

    expected = json.dumps(
        {
            "summary": "Résumé non disponible",
            "considerations": [],
        }
    )

    assert rag_processor.project_rag.summary_answer == expected


@pytest.mark.django_db
@patch("literev.libs.rag_pdf.OpenAIGen")
def test_generate_general_summary_strips_whitespace(
    mock_openai_gen, project_rag
):
    doc = Document.objects.create(
        project=project_rag.project, procedure_type="ProcX"
    )

    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc,
        answer="Texte juridique.",
        citation="Extrait juridique.",
        confidence_score=0.95,
    )

    mock_summary_obj = MagicMock()
    mock_summary_obj.summary = "   Résumé avec des espaces.   "
    mock_summary_obj.considerations = []
    mock_openai_gen.return_value.generate.return_value = mock_summary_obj

    rag_processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    rag_processor.project_rag = project_rag
    rag_processor.generate_general_summary()

    expected = json.dumps(
        {
            "summary": "Résumé avec des espaces.",
            "considerations": [],
        }
    )

    assert rag_processor.project_rag.summary_answer == expected
