"""Tests for the RAG implementation."""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any

import pytest
import rago

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import ValidationError

from literev.libs.rag_pdf import (
    PDFRAG,
    RAGAnswer,
    SummaryGeneralAnswer,
    build_consideration_model,
)
from literev.models import (
    Document,
    ProjectDocumentRAG,
    ProjectRAG,
    ProjectRAGStats,
)


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
        # 'param': 'max_tokens', 'code': None
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
def test_generate_general_summary_with_valid_answers(project_rag):
    doc1 = Document.objects.create(
        project=project_rag.project,
        procedure_type="ProcA",
        raw_document_text="La responsabilité civile découle d'une faute.",
    )
    doc2 = Document.objects.create(
        project=project_rag.project,
        procedure_type="ProcB",
        raw_document_text="Un dommage psychologique peut justifier une compensation.",
    )

    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc1,
        answer="Une faute entraîne la responsabilité civile.",
        citation="Citation document 1.",
        confidence_score=0.9,
    )
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc2,
        answer="La compensation pour dommages psychologiques est possible.",
        citation="Citation document 2.",
        confidence_score=0.85,
    )

    rag_processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])

    rag_processor.generate_general_summary()

    result = json.loads(rag_processor.project_rag.summary_answer)

    assert isinstance(result["summary"], str)
    assert result["summary"].strip() != ""
    assert isinstance(result["considerations"], list)

    if result["considerations"]:
        assert all(isinstance(c, str) for c in result["considerations"])


@pytest.mark.django_db
def test_generate_general_summary_no_valid_answers(project_rag):
    doc1 = Document.objects.create(
        project=project_rag.project,
        procedure_type="ProcX",
        raw_document_text="Texte vide ou non pertinent.",
    )
    doc2 = Document.objects.create(
        project=project_rag.project,
        procedure_type="ProcY",
        raw_document_text="Document sans contenu utile.",
    )

    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc1,
        answer="Réponse non disponible",
        citation="Pas de citation.",
        confidence_score=0.0,
    )
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc2,
        answer="No content available.",
        citation="Empty citation.",
        confidence_score=0.0,
    )

    rag_processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    rag_processor.generate_general_summary()

    result = json.loads(rag_processor.project_rag.summary_answer)

    assert result == {
        "summary": "Résumé non disponible",
        "considerations": [],
    }


@pytest.mark.django_db
def test_generate_general_summary_strips_whitespace(project_rag):
    doc = Document.objects.create(
        project=project_rag.project,
        procedure_type="ProcX",
        raw_document_text=(
            "   Le tribunal a confirmé la responsabilité civile "
            "du défendeur en raison d'une faute prouvée.   "
        ),
    )

    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc,
        answer="La responsabilité est engagée.",
        citation="Décision du tribunal.",
        confidence_score=0.95,
    )

    rag_processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    rag_processor.generate_general_summary()

    result = json.loads(rag_processor.project_rag.summary_answer)

    assert isinstance(result["summary"], str)
    assert result["summary"] == result["summary"].strip()
    assert isinstance(result["considerations"], list)


@pytest.mark.django_db
def test_generate_open_answer_statistics(project_rag, document_real):
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=document_real,
        citation="Extrait A",
        answer="Ce document montre que la mesure est précise et évolutive.",
        confidence_score=0.9,
    )
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=document_real,
        citation="Extrait B",
        answer="Cette réponse ne soutient pas les points mentionnés.",
        confidence_score=0.95,
    )

    processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])

    processor.summary_obj = SummaryGeneralAnswer(
        summary="Résumé être generale",
        considerations=[
            "La mesure doit être précise.",
            "Elle doit être évolutive.",
        ],
    )

    processor.generate_open_answer_statistics()

    stats = ProjectRAGStats.objects.get(project_rag=project_rag)
    output = stats.classification_stats

    assert output["total_documents"] == 2
    assert (
        "La mesure doit être précise." in output["consideration_frequencies"]
    )
    assert "Elle doit être évolutive." in output["consideration_frequencies"]
    assert isinstance(
        output["affirmed_docs_by_consideration"][
            "La mesure doit être précise."
        ],
        list,
    )


def test_build_consideration_model_validation_success():
    model = build_consideration_model(2)
    data = model(argument_1=True, argument_2=False)

    assert data.argument_1 is True
    assert data.argument_2 is False


def test_build_consideration_model_validation_missing_field():
    model = build_consideration_model(2)

    with pytest.raises(ValidationError) as exc:
        model(argument_1=True)

    assert "argument_2" in str(exc.value)


def test_build_consideration_model_validation_wrong_type():
    EvaluationModel = build_consideration_model(2)

    with pytest.raises(ValidationError):
        EvaluationModel(argument_1="not a bool", argument_2=True)


@pytest.mark.django_db
def test_check_question_type_open_and_closed(project_rag):
    project_rag.query = "Est-ce que la garde partagée est accordée ?"
    project_rag.save()
    processor_closed = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    processor_closed.project_rag = project_rag
    assert processor_closed.check_question_type() == "closed"

    project_rag.query = (
        "Quels sont les critères pour obtenir une réparation morale ?"
    )
    project_rag.save()
    processor_open = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    processor_open.project_rag = project_rag
    assert processor_open.check_question_type() == "open"


@pytest.mark.django_db
def test_fetch_valid_document_answers(project_rag, document_real):
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=document_real,
        answer="Réponse pertinente",
        citation="Extrait A",
        confidence_score=0.9,
    )
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=document_real,
        answer="Réponse non disponible",
        citation="Extrait B",
        confidence_score=0.0,
    )

    processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    valid = processor._fetch_valid_document_answers()
    assert valid == ["Réponse pertinente"]


@pytest.mark.django_db
def test_tag_answers_considerations(project_rag, document_real):
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=document_real,
        answer="Le parent doit subvenir aux besoins de l'enfant.",
        citation="Extrait loi A",
        citation_context=["Extrait loi A"],
        confidence_score=0.9,
    )

    ProjectRAGStats.objects.create(
        project_rag=project_rag,
        classification_stats={
            "consideration_frequencies": {
                "Obligation alimentaire": 1,
            },
            "affirmed_docs_by_consideration": {
                "Obligation alimentaire": [document_real.id],
            },
        },
    )

    processor = PDFRAG(project_rag_id=project_rag.id, document_ids=[])
    processor.summary_obj = SummaryGeneralAnswer(
        summary="Résumé général",
        considerations=["Obligation alimentaire"],
    )

    processor.project_rag.summary_answer = json.dumps(
        {
            "summary": "Résumé général",
            "considerations": [],
        }
    )

    processor.tag_answers_considerations()

    enriched = json.loads(processor.project_rag.summary_answer)
    tagged_considerations = enriched.get("considerations", [])

    assert tagged_considerations
    tagged = tagged_considerations[0]

    assert tagged["text"] == "Obligation alimentaire"
    assert isinstance(tagged["procedure_types"], list)
    assert isinstance(tagged["frequency"], int)
    assert "Obligation alimentaire" in tagged["tagged"]
