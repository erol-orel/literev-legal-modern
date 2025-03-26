"""RAG workflow."""

from __future__ import annotations

import logging

from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal, cast

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field, field_validator
from rago import Rago
from rago.augmented import OpenAIAug
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from rago.retrieval import StringRet

from literev.libs.scoring import sort_documents_by_es_score
from literev.models import (
    Document,
    ProjectDocumentRAG,
    ProjectRAG,
    ProjectRAGStats,
)

TMP_DIR = Path("/tmp") / "rago"

RET_CACHE = CacheFile(target_dir=TMP_DIR / "ret")
AUG_CACHE = CacheFile(target_dir=TMP_DIR / "aug")
GEN_CACHE = CacheFile(target_dir=TMP_DIR / "gen")

# TODO:update for contenttext instead fo pdf document
logging.basicConfig(level=settings.LOGGING_LEVEL)
logger = logging.getLogger(__name__)


class RAGAnswer(BaseModel):
    """Model for RAG Answers."""

    answer: str = Field(
        ...,
        description="The answer",
    )
    highlight: str = Field(
        ...,
        description="The most relevant context.",
    )


class ClosedAnswerClassification(BaseModel):
    answer: str = Field(..., description="Document answer")
    category: Literal["oui", "non", "peut_etre", "mixte"]

    @field_validator("category")
    def validate_category(cls, v):
        allowed = ["oui", "non", "peut_etre", "mixte"]
        if v not in allowed:
            raise ValueError(f"Invalid category: {v}")
        return v


class QuestionTypeClassification(BaseModel):
    question_type: Literal["open", "closed"]


class GeneralSummary(BaseModel):
    summary: str = Field(
        ..., description="Concise and coherent summary in French."
    )


@wraps
def ret_cache(func: Callable[str, list[str]]) -> Callable[str, list[str]]:
    cache = RET_CACHE

    def wrapper(text: str) -> list[str]:
        cached = cache.load(text)
        if cached is not None:
            return cast(list[str], cached)
        result = func(text)
        cache.save(text, result)
        return result

    return wrapper


class PDFRAG:
    """Run RAG on documents and generate summaries & statistics."""

    summary_template_prompt = (
        "Based on ALL of the given answers extracted from the documents, "
        "write a concise and coherent summary as a single sentence, in French. "
        "Summarize the different perspectives, even if they are contradictory. "
        "If there is absolutely no relevant information at all, return exactly: `Résumé non disponible`.\n\n"
        "The original question is: `{query}`\n\n"
        "Given Answers:\n"
        "{context}"
    )

    template_prompt = (
        "Based on the given context, answer to this question: `{query}`. "
        "If no information is available in the context, "
        "return `Réponse non disponible`. "
        "Otherwise, give your answer in only one sentence in French with "
        "the most relevant information. "
        "Also return an extract of the context, approximately 5 sentences, "
        "from where the given answer was generated as a highlight.\n\n"
        "Context: `{context}`"
    )

    classification_template_prompt = (
        "You are a legal assistant. Classify the given answer to a closed-ended question "
        "into one of the following categories:\n\n"
        "- 'oui': Clear confirmation, either direct or indirect, including cases involving someone related to the subject.\n"
        "- 'non': Refusal, contradiction, or a clear absence of affirmation.\n"
        "- 'peut_etre': Ambiguous, conditional, or partial response.\n"
        "- 'mixte': Contradictory response or no clear stance.\n\n"
        "Respond ONLY with the exact label in French, in lowercase: "
        "'oui', 'non', 'peut_etre', or 'mixte'. No explanations or translations.\n\n"
        "Question: {query}\n"
        "Given Answer: {context}"
    )

    prompt_check_question_type = (
        "You are a legal expert. Given the following query, classify it as either:\n"
        "- 'closed' if it requires a yes/no (polar) given answer\n"
        "- 'open' otherwise.\n\n"
        "Query:\n{context}"
    )

    def __init__(self, project_rag_id: int, document_ids: list[int]) -> None:
        self.project_rag = ProjectRAG.objects.get(id=project_rag_id)
        self.project_rag.status = "in-progress"
        self.project_rag.save()

        self.document_ids = document_ids
        self.question_type = None

    @ret_cache
    def split_text_into_chunks(self, text: str) -> list[str]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        return splitter.split_text(text)

    def run(self, max_doc_ans: int | None = None) -> None:
        logger.info("Starting RAG processing for documents.")

        documents = Document.objects.filter(id__in=self.document_ids)

        if max_doc_ans:
            documents = sort_documents_by_es_score(
                self.project_rag.project, documents
            )

        counter = 0
        for document in documents:
            try:
                chunks = self.split_text_into_chunks(
                    document.raw_document_text
                )

                if not chunks:
                    self._create_empty_response(
                        document, "No content available."
                    )
                    continue

                rag = Rago(
                    retrieval=StringRet(chunks),
                    augmented=OpenAIAug(
                        api_key=settings.OPENAI_API_KEY,
                        top_k=5,
                        model_name="text-embedding-ada-002",
                        cache=AUG_CACHE,
                    ),
                    generation=OpenAIGen(
                        api_key=settings.OPENAI_API_KEY,
                        model_name="gpt-4o-mini",
                        prompt_template=self.template_prompt,
                        temperature=0,
                        output_max_length=16384,
                        api_params={
                            "top_p": 0.0,
                            "frequency_penalty": 0.0,
                            "presence_penalty": 0.0,
                        },
                        structured_output=RAGAnswer,
                        cache=GEN_CACHE,
                    ),
                )

                result = rag.prompt(self.project_rag.query)

                ProjectDocumentRAG.objects.create(
                    project_rag=self.project_rag,
                    document=document,
                    citation=result.highlight.strip(),
                    answer=result.answer.strip(),
                )

                if "réponse non disponible" not in result.answer.lower():
                    counter += 1

                if max_doc_ans and counter >= max_doc_ans:
                    break

            except Exception as e:
                logger.error(f"Error processing document {document.id}: {e}")
                self._create_empty_response(
                    document, "Error generating response."
                )

        self.project_rag.status = "completed"
        self.project_rag.save()

        self.generate_general_summary()

        self.question_type = self.check_question_type()

        if self.question_type == "closed":
            logger.info(
                "Closed-ended question. Generating closed answer stats."
            )
            self.generate_closed_answer_statistics()
        else:
            logger.info("Open-ended question. Skipping closed answer stats.")

    def _create_empty_response(self, document, message: str) -> None:
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=document,
            citation=message,
            answer=message,
            from_full_text=False,
        )

    def generate_general_summary(self) -> None:
        logger.info("Generating general summary...")

        answers = self._fetch_valid_document_answers()

        if not answers:
            summary_answer = "Résumé non disponible"
            logger.info("No valid answers found. Using default summary.")
        else:
            logger.info(f"Combining {len(answers)} answers for summarization.")

            answers_bullet_points = "\n".join(
                f"- {answer.strip()}" for answer in answers if answer.strip()
            )

            try:
                summary_gen = OpenAIGen(
                    api_key=settings.OPENAI_API_KEY,
                    model_name="gpt-4o-mini",
                    prompt_template=self.summary_template_prompt,
                    temperature=0,
                    output_max_length=2048,
                    api_params={
                        "top_p": 0.0,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0,
                    },
                    structured_output=GeneralSummary,
                )

                summary_obj: GeneralSummary = summary_gen.generate(
                    query=self.project_rag.query,
                    context=[answers_bullet_points],
                )
                summary_answer = summary_obj.summary.strip()

            except Exception as e:
                logger.error(f"Failed to generate general summary: {e}")
                summary_answer = "Résumé non disponible"

        self.project_rag.summary_answer = summary_answer
        self.project_rag.save()

        logger.info(f"Summary saved: {summary_answer}")

    def check_question_type(self) -> str:
        logger.info("Classifying the question type...")

        classification_gen = OpenAIGen(
            api_key=settings.OPENAI_API_KEY,
            model_name="gpt-4o-mini",
            prompt_template=self.prompt_check_question_type,
            temperature=0,
            output_max_length=64,
            cache=GEN_CACHE,
            structured_output=QuestionTypeClassification,
        )

        result_obj: QuestionTypeClassification = classification_gen.generate(
            query="", context=[self.project_rag.query]
        )

        result = result_obj.question_type

        logger.info(f"Question classified as: {result}")

        return result

    def generate_closed_answer_statistics(self) -> None:
        logger.info("Generating closed-ended statistics...")

        answers = self._fetch_valid_document_answers()

        if not answers:
            logger.warning("No valid answers for classification.")
            return

        classified_labels = self.classify_answers_with_llm(answers)
        stats = self.compute_classification_statistics(classified_labels)

        ProjectRAGStats.objects.update_or_create(
            project_rag=self.project_rag,
            defaults={"classification_stats": stats},
        )

        logger.info(f"Classification stats saved: {stats}")

    def classify_answers_with_llm(self, answers: list[str]) -> list[str]:
        logger.info("Classifying answers with LLM and structured output...")

        classification_gen = OpenAIGen(
            api_key=settings.OPENAI_API_KEY,
            model_name="gpt-4o-mini",
            prompt_template=self.classification_template_prompt,
            temperature=0,
            output_max_length=64,
            cache=GEN_CACHE,
            structured_output=ClosedAnswerClassification,
        )

        categories = []

        for answer in answers:
            try:
                classification_obj: ClosedAnswerClassification = (
                    classification_gen.generate(
                        query=self.project_rag.query, context=[answer]
                    )
                )
                label = classification_obj.category
                categories.append(label)
            except Exception as e:
                logger.error(
                    f"LLM classification failed for answer: {answer} | {e}"
                )
                categories.append("mixed")  # fallback category

        return categories

    def compute_classification_statistics(
        self, classified_labels: list[str]
    ) -> dict[str, Any]:
        logger.info("Computing statistics...")

        total = len(classified_labels)
        counts = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}

        for label in classified_labels:
            label = label.strip().lower()
            if label in counts:
                counts[label] += 1
            else:
                logger.warning(
                    f"Unexpected label {label} found in classification results."
                )

        percentages = {
            k: round((v / total) * 100, 2) if total > 0 else 0
            for k, v in counts.items()
        }

        return {
            "counts": counts,
            "percentages": percentages,
            "total": total,
        }

    def _fetch_valid_document_answers(self) -> list[str]:
        return list(
            ProjectDocumentRAG.objects.filter(project_rag=self.project_rag)
            .exclude(
                answer__in=[
                    "No content available.",
                    "Error generating response.",
                    "Réponse non disponible",
                ]
            )
            .values_list("answer", flat=True)
        )
