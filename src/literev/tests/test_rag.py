"""Tests for the RAG implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest import skip

import pytest
import rago

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import ValidationError

from literev.libs.rag_pdf import (
    RAGAnswer,
    RagAnswersManager,
    SummaryGeneralAnswer,
    build_consideration_model,
)
from literev.models import (
    Document,
    ProjectDocumentRAG,
    ProjectRAG,
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
    docs_rag = RagAnswersManager(project_rag.id, [document_real.id])
    docs_rag.run_pipeline()
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
    document_answering_system_prompt = (
        "You are a factual legal assistant. "
        "Always answer in French based solely on the provided context. "
        "If you are absolutely certain the context has no relevant information, "
        'return exactly the string "Réponse non disponible".'
    )
    document_answering_user_prompt = (
        'Question: "{query}"\n\n'
        "Context:\n{context}\n\n"
        "Please respond in JSON format with two fields:\n"
        "{{\n"
        '  "answer": "<your concise answer here>",\n'
        '  "highlight": "<up to 5 consecutive sentences from context>"\n'
        "}}\n\n"
        "Rules:\n"
        "- Do not infer or imagine details.\n"
        "- Do not include information that is not explicitly stated in the context.\n"
        "- The highlight must fully justify the answer.\n"
    )
    augmented = rago.augmented.OpenAIAug(
        api_key=settings.OPENAI_API_KEY,
        top_k=5,
        model_name="text-embedding-ada-002",
    )

    generation = rago.generation.OpenAIGen(
        api_key=settings.OPENAI_API_KEY,
        model_name="gpt-4o-mini",
        system_message=document_answering_system_prompt,
        prompt_template=document_answering_user_prompt,
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
    document_answering_system_prompt = (
        "You are a factual legal assistant. "
        "Always answer in French based solely on the provided context. "
        "If you are absolutely certain the context has no relevant information, "
        'return exactly the string "Réponse non disponible".'
    )
    document_answering_user_prompt = (
        'Question: "{query}"\n\n'
        "Context:\n{context}\n\n"
        "Please respond in JSON format with two fields:\n"
        "{{\n"
        '  "answer": "<your concise answer here>",\n'
        '  "highlight": "<up to 5 consecutive sentences from context>"\n'
        "}}\n\n"
        "Rules:\n"
        "- Do not infer or imagine details.\n"
        "- Do not include information that is not explicitly stated in the context.\n"
        "- The highlight must fully justify the answer.\n"
    )

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
            system_message=document_answering_system_prompt,
            prompt_template=document_answering_user_prompt,
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
    rag_documents_w_valid_answers = (
        ProjectDocumentRAG.objects.filter(
            project_rag=project_rag,
            document_id__in=[doc1.id, doc2.id],
        )
        .exclude(
            answer__in=[
                "",
                "No content available.",
                "Error generating response.",
                "Réponse non disponible",
                "No content available",
            ]
        )
        .select_related("document")
    )
    documents_rag_w_scores = rag_documents_w_valid_answers.filter(
        confidence_score__gt=0.0
    )

    answers = [doc_rag.answer.strip() for doc_rag in documents_rag_w_scores]
    rag_processor = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[doc1.id, doc2.id]
    )

    result = rag_processor.summary_generator.get_summary(
        project_rag.query, answers, False
    )

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
    rag_documents_w_valid_answers = (
        ProjectDocumentRAG.objects.filter(
            project_rag=project_rag,
            document_id__in=[doc1.id, doc2.id],
        )
        .exclude(
            answer__in=[
                "",
                "No content available.",
                "Error generating response.",
                "Réponse non disponible",
                "No content available",
            ]
        )
        .select_related("document")
    )
    documents_rag_w_scores = rag_documents_w_valid_answers.filter(
        confidence_score__gt=0.0
    )

    answers = [doc_rag.answer.strip() for doc_rag in documents_rag_w_scores]

    rag_processor = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[doc1.id, doc2.id]
    )

    result = rag_processor.summary_generator.get_summary(
        project_rag.query, answers, False
    )

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

    rag_documents_w_valid_answers = (
        ProjectDocumentRAG.objects.filter(
            project_rag=project_rag,
            document_id__in=[doc.id],
        )
        .exclude(
            answer__in=[
                "",
                "No content available.",
                "Error generating response.",
                "Réponse non disponible",
                "No content available",
            ]
        )
        .select_related("document")
    )
    documents_rag_w_scores = rag_documents_w_valid_answers.filter(
        confidence_score__gt=0.0
    )

    answers = [doc_rag.answer.strip() for doc_rag in documents_rag_w_scores]

    rag_processor = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[doc.id]
    )
    result = rag_processor.summary_generator.get_summary(
        project_rag.query, answers, False
    )

    assert isinstance(result["summary"], str)
    assert result["summary"] == result["summary"].strip()
    assert isinstance(result["considerations"], list)


@pytest.mark.django_db
def test_generate_open_answer_statistics(project_rag, document_real):
    doc = document_real

    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc,
        citation="Extrait A",
        answer="Ce document montre que la mesure est précise et évolutive.",
        confidence_score=0.9,
    )
    ProjectDocumentRAG.objects.create(
        project_rag=project_rag,
        document=doc,
        citation="Extrait B",
        answer="Cette réponse ne soutient pas les points mentionnés.",
        confidence_score=0.95,
    )

    processor = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[doc.id]
    )

    summary_obj = SummaryGeneralAnswer(
        summary="Résumé être generale",
        considerations=[
            "La mesure doit être précise.",
            "Elle doit être évolutive.",
        ],
    )

    rag_documents_w_valid_answers = (
        ProjectDocumentRAG.objects.filter(
            project_rag=project_rag,
            document_id__in=[doc.id],
        )
        .exclude(
            answer__in=[
                "",
                "No content available.",
                "Error generating response.",
                "Réponse non disponible",
                "No content available",
            ]
        )
        .select_related("document")
    )

    documents_rag_w_scores = rag_documents_w_valid_answers.filter(
        confidence_score__gt=0.0
    )

    stats = processor.stats_generator.generate_open_answer_statistics(
        project_rag.query, documents_rag_w_scores, summary_obj.considerations
    )

    assert stats["total_documents"] == 2
    assert "La mesure doit être précise." in stats["consideration_frequencies"]
    assert "Elle doit être évolutive." in stats["consideration_frequencies"]


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
    processor_closed = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[]
    )
    assert (
        processor_closed.query_classifier.get_question_type(project_rag.query)
        == "closed"
    )

    project_rag.query = (
        "Quels sont les critères pour obtenir une réparation morale ?"
    )
    project_rag.save()
    processor_open = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[]
    )
    processor_open.project_rag = project_rag
    assert (
        processor_open.query_classifier.get_question_type(project_rag.query)
        == "open"
    )


@skip("removed function")
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

    processor = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[document_real.id]
    )
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

    processor = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=[]
    )

    stats = {
        "consideration_frequencies": {
            "Obligation alimentaire": 1,
        },
        "affirmed_docs_by_consideration": {
            "Obligation alimentaire": [document_real.id],
        },
    }
    considerations = ["Obligation alimentaire"]

    rag_documents_w_valid_answers = (
        ProjectDocumentRAG.objects.filter(
            project_rag=project_rag,
            document_id__in=[document_real.id],
        )
        .exclude(
            answer__in=[
                "",
                "No content available.",
                "Error generating response.",
                "Réponse non disponible",
                "No content available",
            ]
        )
        .select_related("document")
    )

    documents_rag_w_scores = rag_documents_w_valid_answers.filter(
        confidence_score__gt=0.0
    )

    tagged_considerations = (
        processor.stats_generator.tag_answers_considerations(
            considerations=considerations,
            valid_rags=documents_rag_w_scores,
            classification_stats=stats,
        )
    )

    assert tagged_considerations
    tagged = tagged_considerations[0]

    assert tagged["text"] == "Obligation alimentaire"
    assert isinstance(tagged["procedure_types"], list)
    assert isinstance(tagged["frequency"], int)
    assert "Obligation alimentaire" in tagged["tagged"]


import pytest

from literev.libs.rag_pdf import (
    DOCUMENT_CACHE,
    compute_document_cache_key,
)
from literev.models import Project


@pytest.mark.django_db
def test_document_level_cache(project_factory, document_factory):
    project = project_factory(
        natural_language_query="Quels sont les critères d'un harcèlement au travail ?"
    )
    document = document_factory(
        project=project,
        raw_document_text="Extrait : un comportement hostile et répété.",
    )

    project_rag = ProjectRAG.objects.create(
        project=project,
        query=project.natural_language_query,
        status="in-progress",
    )

    documents_ids = [document.id]

    cache_key = compute_document_cache_key(
        query=project_rag.query,
        document_id=document.id,
    )

    # Ensure cache is empty before test
    cache_entry = Path(DOCUMENT_CACHE.target_dir) / f"{cache_key}.pkl"
    cache_entry.unlink(missing_ok=True)

    assert DOCUMENT_CACHE.load(cache_key) is None

    # First run: triggers generation and saves to cache
    rag = RagAnswersManager(
        project_rag_id=project_rag.id, documents_ids=documents_ids
    )
    rag.run_pipeline()

    cached = DOCUMENT_CACHE.load(cache_key)
    assert cached is not None
    assert "citation" in cached
    assert "answer" in cached

    # Second run: should load from cache
    project_rag_2 = ProjectRAG.objects.create(
        project=project,
        query=project.natural_language_query,
        status="in-progress",
    )

    rag2 = RagAnswersManager(
        project_rag_id=project_rag_2.id, documents_ids=documents_ids
    )
    rag2.run_pipeline()

    # Ensure ProjectDocumentRAG is created again from cache
    assert ProjectDocumentRAG.objects.filter(
        project_rag=project_rag_2, document=document
    ).exists()


@pytest.fixture
def project_factory(db):
    def make_project(natural_language_query="Quel est le droit au repos ?"):
        return Project.objects.create(
            name="Test Project", natural_language_query=natural_language_query
        )

    return make_project


@pytest.fixture
def document_factory(db):
    def make_doc(project, raw_document_text):
        return Document.objects.create(
            project=project,
            raw_document_text=raw_document_text,
            procedure_type="TestProc",
        )

    return make_doc
