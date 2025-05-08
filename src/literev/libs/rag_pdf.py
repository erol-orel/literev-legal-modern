"""RAG workflow."""

from __future__ import annotations

import asyncio
import json
import logging

from functools import wraps
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Literal, cast

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field, create_model, field_validator
from rago import Rago
from rago.augmented import OpenAIAug
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from rago.retrieval import StringRet

from literev.libs.scoring import (
    assign_faithfulnesswithHHEM_scores,
    sort_documents_by_es_score,
)
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
SUMMARY_CACHE = CacheFile(target_dir=TMP_DIR / "summary")

# TODO:update for contenttext instead fo pdf document
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@wraps
def ret_cache(func: Callable[[str], list[str]]) -> Callable[[str], list[str]]:
    cache = RET_CACHE

    def wrapper(text: str) -> list[str]:
        cached = cache.load(text)
        if cached is not None:
            return cast(list[str], cached)
        result = func(text)
        cache.save(text, result)
        return result

    return wrapper


def compute_summary_cache_key(query: str, document_ids: list[int]) -> str:
    """
    Compute a deterministic hash key for summary caching based on query and document IDs.
    """
    base = f"{query.strip()}::{','.join(map(str, sorted(document_ids)))}"
    return sha256(base.encode("utf-8")).hexdigest()


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


class SummaryGeneralAnswer(BaseModel):
    summary: str = Field(
        ...,
        description="The answer",
    )

    considerations: list[str]


class ClosedAnswerClassification(BaseModel):
    answer: str = Field(..., description="Document answer")
    category: Literal["oui", "non", "peut_etre", "mixte"]

    @field_validator("category")
    def validate_category(cls, v):
        allowed = ["oui", "non", "peut_etre", "mixte"]
        if v not in allowed:
            raise ValueError(f"Invalid category: {v}")
        return v


def build_consideration_model(count: int):
    fields = {f"argument_{i + 1}": (bool, ...) for i in range(count)}
    return create_model("DynamicEvaluationModel", **fields)


class QuestionTypeClassification(BaseModel):
    question_type: Literal["open", "closed"]


class PDFRAG:
    """Run RAG on documents and generate summaries & statistics."""

    evaluate_consideration_template_prompt = (
        "You are a legal assistant reviewing a summarized legal answer.\n\n"
        "Based on the provided **excerpt** 'a one-sentence summary answer', and the list of legal **considerations**, "
        "determine whether each consideration is **explicitly supported** or **clearly contradicted** in the excerpt.\n\n"
        "Do not make assumptions beyond the excerpt. Focus only on what is directly stated.\n\n"
        "{context}\n\n"
        "**Return Format:**\n"
        "argument_1: true\n"
        "argument_2: false\n"
        "... and so on."
    )

    summary_template_prompt = (
        "Based on ALL of the given answers extracted from the documents, "
        "write a concise and coherent summary as a single sentence, in French. "
        "Summarize only the legal perspectives that are directly mentioned or clearly supported by the answers. "
        "Do not invent or infer arguments that are not explicitly stated. "
        "Avoid vague or emotional expressions. Focus on legal arguments and facts. "
        "If there is absolutely no relevant information, return exactly: `Résumé non disponible`. "
        "\n\n"
        "**Instructions:**\n"
        "1. Do NOT mention specific names or individual cases.\n"
        "2. If all answers agree on one idea, return a single-sentence summary.\n"
        "3. If there are multiple legal arguments or points of view:\n"
        "   - Provide a short summary sentence.\n"
        "The original question is: `{query}`\n\n"
        "Given Answers:\n"
        "{context}"
    )

    template_prompt = (
        "Based on the given context, answer the following question: `{query}`. "
        "If no relevant information is found in the context, return exactly: `Réponse non disponible`. "
        "Otherwise, provide a single, concise answer in French that is directly supported by the context.\n\n"
        "In addition to the answer, extract and return the portion of the context — approximately 5 consecutive sentences — "
        "from which the answer was derived. This highlight **must** explicitly contain all elements of the answer.\n\n"
        "**Important:**\n"
        "- Do not infer or imagine details.\n"
        "- Do not include information that is not explicitly stated in the context.\n"
        "- The highlight must fully justify the answer.\n\n"
        "Context:\n`{context}`"
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
        """Initialize PDFRAG with project_rag_id and document_ids."""
        self.api_key: str = getattr(settings, "OPENAI_API_KEY", "")

        self.project_rag: ProjectRAG = ProjectRAG.objects.get(
            id=project_rag_id
        )
        self.project_rag.status = "in-progress"
        self.project_rag.save()

        self.document_ids: list[int] = document_ids
        self.question_type: str | None = None

    @ret_cache
    def split_text_into_chunks(self, text: str) -> list[str]:
        """Split input text into overlapping chunks for better retrieval."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        return splitter.split_text(text)

    def run(
        self, max_doc_ans: int | None = None, batch_size: int = 10
    ) -> None:
        """
        Run the complete RAG pipeline for a set of documents.

        This method processes documents using (RAG),
        which generates answers, and updates the project status.
        """
        logger.info("Starting RAG processing for documents.")

        documents = list(Document.objects.filter(id__in=self.document_ids))

        if max_doc_ans:
            documents = sort_documents_by_es_score(
                self.project_rag.project, documents
            )

        counter = 0
        stop_processing = False

        for batch_start in range(0, len(documents), batch_size):
            batch = documents[batch_start : batch_start + batch_size]

            for document in batch:
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
                            api_key=self.api_key,
                            top_k=5,
                            model_name="text-embedding-ada-002",
                            cache=AUG_CACHE,
                        ),
                        generation=OpenAIGen(
                            api_key=self.api_key,
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
                    citation_context = rag.logs.get("augmented", {}).get(
                        "result", []
                    )

                    ProjectDocumentRAG.objects.create(
                        project_rag=self.project_rag,
                        document=document,
                        citation=result.highlight.strip(),
                        answer=result.answer.strip(),
                        citation_context=citation_context,
                    )

                    if "réponse non disponible" not in result.answer.lower():
                        counter += 1

                    if max_doc_ans and counter >= max_doc_ans:
                        logger.info("Max document answers reached.")
                        stop_processing = True
                        break

                except Exception as e:
                    logger.error(
                        f"Error processing document {document.id}: {e}"
                    )
                    self._create_empty_response(
                        document, "Error generating response."
                    )

            if stop_processing:
                break

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            assign_faithfulnesswithHHEM_scores(self.project_rag)
        )

        self.question_type = self.check_question_type()

        if self.question_type == "closed":
            self.generate_general_summary(summary_only=True)
            self.generate_closed_answer_statistics()
        else:
            self.generate_general_summary(summary_only=False)
            self.generate_open_answer_statistics()
            self.tag_answers_considerations()

        self.project_rag.status = "completed"
        self.project_rag.save()

    def _create_empty_response(self, document, message: str) -> None:
        """Create a fallback response for a document when processing fails."""
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=document,
            citation=message,
            answer=message,
        )

    def generate_general_summary(self, summary_only: bool = False) -> None:
        """Generate a one-sentence summary and considerations, cached using a hash key."""
        logger.info("Generating general summary...")

        valid_rags = [
            doc
            for doc in self.get_valid_document_rags()
            if doc.confidence_score and doc.confidence_score > 0
        ]
        answers = [f"- {doc_rag.answer.strip()}" for doc_rag in valid_rags]

        if not answers:
            summary_data = {
                "summary": "Résumé non disponible",
                "considerations": [],
            }
            logger.info("No valid answers found. Using default summary.")
        else:
            cache_key = compute_summary_cache_key(
                self.project_rag.query, self.document_ids
            )
            cached = SUMMARY_CACHE.load(cache_key)

            if cached:
                logger.info("Summary loaded from cache.")
                summary_data = cached
                self.summary_obj = SummaryGeneralAnswer(**summary_data)
            else:
                try:
                    summary_gen = OpenAIGen(
                        api_key=self.api_key,
                        model_name="gpt-4o-mini",
                        prompt_template=self.summary_template_prompt,
                        temperature=0,
                        output_max_length=2048,
                        api_params={
                            "top_p": 0.0,
                            "frequency_penalty": 0.0,
                            "presence_penalty": 0.0,
                        },
                        structured_output=SummaryGeneralAnswer,
                    )
                    self.summary_obj = summary_gen.generate(
                        query=self.project_rag.query,
                        context=["\n".join(answers)],
                    )
                    summary_data = {
                        "summary": self.summary_obj.summary.strip(),
                        "considerations": self.summary_obj.considerations
                        if not summary_only
                        else [],
                    }
                    SUMMARY_CACHE.save(cache_key, summary_data)
                    logger.info("Summary generated and cached.")
                except Exception as e:
                    logger.error(f"Failed to generate summary: {e}")
                    summary_data = {
                        "summary": "Résumé non disponible",
                        "considerations": [],
                    }

        self.project_rag.summary_answer = json.dumps(summary_data)
        self.project_rag.save()
        logger.info(f"Summary saved to ProjectRAG: {summary_data}")

    def check_question_type(self) -> str:
        """Classify whether the question is closed (yes/no) or open-ended."""
        logger.info("Classifying the question type...")

        classification_gen = OpenAIGen(
            api_key=self.api_key,
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
        """
        Generate classification statistics for closed-ended questions.

        This computes counts and percentages of 'oui', 'non', 'peut_etre', and 'mixte' labels,
        and stores them in the `ProjectRAGStats` model.
        """
        logger.info("Generating closed-ended statistics...")

        answers = self._fetch_valid_document_answers()

        if not answers:
            logger.warning("No valid answers for classification.")
            return

        classified_labels = self.categorize_closed_answers(answers)
        stats = self.compute_polar_answer_stats(classified_labels)

        ProjectRAGStats.objects.update_or_create(
            project_rag=self.project_rag,
            defaults={"classification_stats": stats},
        )

        logger.info(f"Classification stats saved: {stats}")

    def generate_open_answer_statistics(self) -> None:
        """
        Generate evaluation statistics for open-ended answers.

        This method runs evaluation using OpenAI's GPT-4o model for each document
        answer, and stores the results in the `ProjectRAGStats` model.
        """
        logger.info("Generating open-ended answer statistics...")

        if (
            not getattr(self, "summary_obj", None)
            or not self.summary_obj.considerations
        ):
            logger.warning("No considerations found in summary to evaluate.")
            return

        valid_docs = self.get_valid_document_rags()
        if not valid_docs:
            logger.warning("No valid documents available for evaluation.")
            return

        considerations = [c.strip() for c in self.summary_obj.considerations]
        results = {c: 0 for c in considerations}
        docs_affirmed = {c: set() for c in considerations}

        EvaluationModel = build_consideration_model(len(considerations))

        for doc_rag in valid_docs:
            try:
                arguments_block = "\n".join(
                    f"* argument_{i + 1}: {c}"
                    for i, c in enumerate(considerations)
                )

                context_block = (
                    f"Excerpt:\n{doc_rag.answer}\n\n"
                    f"Considerations:\n{arguments_block}"
                )

                prompt = OpenAIGen(
                    api_key=self.api_key,
                    model_name="gpt-4o-mini",
                    prompt_template=self.evaluate_consideration_template_prompt,
                    temperature=0,
                    output_max_length=1024,
                    api_params={
                        "top_p": 0.0,
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0,
                    },
                    structured_output=EvaluationModel,
                )

                evaluation = prompt.generate(
                    query=self.project_rag.query,
                    context=[context_block],
                )

                for idx, cons_text in enumerate(considerations):
                    if getattr(evaluation, f"argument_{idx + 1}", False):
                        results[cons_text] += 1
                        docs_affirmed[cons_text].add(doc_rag.document.id)

            except Exception as e:
                logger.warning(
                    f"Evaluation failed for doc {doc_rag.document.id}: {e}"
                )

        stats = {
            "total_documents": len(valid_docs),
            "consideration_frequencies": results,
            "affirmed_docs_by_consideration": {
                k: list(v) for k, v in docs_affirmed.items()
            },
        }

        logger.info(f"Open-ended statistics generated: {stats}")
        ProjectRAGStats.objects.update_or_create(
            project_rag=self.project_rag,
            defaults={"classification_stats": stats},
        )

    def tag_answers_considerations(self) -> None:
        """
        Tag RAG answers with consideration texts and associate procedure types
        without using faithfulness scores. Simply takes the last three procedure types
        from documents affirming the consideration.
        """
        logger.info("Tagging considerations based on affirmed documents...")

        if (
            not getattr(self, "summary_obj", None)
            or not self.summary_obj.considerations
        ):
            logger.warning("No summary or considerations available.")
            return

        valid_rags = (
            ProjectDocumentRAG.objects.filter(project_rag=self.project_rag)
            .select_related("document")
            .exclude(
                answer__in=(
                    "no content available.",
                    "réponse non disponible",
                    "error generating response.",
                )
            )
            .exclude(confidence_score=0.0)
        )

        tagged_data = {
            rag.document.id: {
                "procedure_type": rag.document.procedure_type or "Inconnu"
            }
            for rag in valid_rags
        }

        total_docs = len(tagged_data)

        stats_obj = ProjectRAGStats.objects.filter(
            project_rag=self.project_rag
        ).first()
        classification_stats = (
            stats_obj.classification_stats if stats_obj else {}
        )

        frequencies = classification_stats.get("consideration_frequencies", {})
        affirmed_docs = classification_stats.get(
            "affirmed_docs_by_consideration", {}
        )

        tagged_considerations = []

        for consideration in self.summary_obj.considerations:
            consideration_text = consideration.strip()
            doc_ids = affirmed_docs.get(consideration_text, [])

            procedure_types = [
                tagged_data[doc_id]["procedure_type"]
                for doc_id in doc_ids
                if doc_id in tagged_data
            ]

            top_procedure_types = procedure_types[:3] or ["Inconnu"]

            count = frequencies.get(consideration_text, 0)
            percent = (
                round((count / total_docs) * 100, 1) if total_docs else 0.0
            )

            tagged_considerations.append(
                {
                    "text": consideration_text,
                    "procedure_types": top_procedure_types,
                    "tagged": f"{consideration_text} ({', '.join(top_procedure_types)})",
                    "frequency": count,
                    "percent": percent,
                }
            )

        summary_data = json.loads(self.project_rag.summary_answer)
        summary_data["considerations"] = tagged_considerations
        self.project_rag.summary_answer = json.dumps(summary_data)
        self.project_rag.save()

        logger.info(f"Tagged considerations: {tagged_considerations}")

    def categorize_closed_answers(self, answers: list[str]) -> list[str]:
        """
        Classify a list of answers into closed categories using (RAG).
        """
        logger.info("Classifying answers with LLM and structured output...")

        classification_gen = OpenAIGen(
            api_key=self.api_key,
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
                categories.append("error")  # fallback category

        return categories

    def compute_polar_answer_stats(
        self, classified_labels: list[str]
    ) -> dict[str, Any]:
        """
        Compute count and percentage statistics for classified labels.
        """
        logger.info("Computing statistics...")

        error_count = 0
        total = len(classified_labels)
        counts = {"oui": 0, "non": 0, "peut_etre": 0, "mixte": 0}

        for label in classified_labels:
            label = label.strip().lower()
            if label in counts:
                counts[label] += 1
            else:
                logger.warning(
                    f"Unexpected label '{label}' found in classification results."
                )
                if label == "error":
                    error_count += 1

        if error_count > 0:
            logger.warning(
                f"{error_count} document answers failed classification and were marked as 'error'"
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
        """Retrieve valid document answers, excluding placeholders and errors."""
        return list(
            ProjectDocumentRAG.objects.filter(project_rag=self.project_rag)
            .exclude(
                answer__in=(
                    "No content available.",
                    "Error generating response.",
                    "Réponse non disponible",
                )
            )
            .exclude(confidence_score=0.0)
            .values_list("answer", flat=True)
        )

    def get_valid_document_rags(self) -> list[ProjectDocumentRAG]:
        """
        Retrieve ProjectDocumentRAG objects with non-empty, valid answers.
        """
        return [
            doc
            for doc in ProjectDocumentRAG.objects.filter(
                project_rag=self.project_rag
            )
            .exclude(confidence_score=0.0)
            .select_related("document")
            if doc.answer.strip().lower()
            not in (
                "no content available.",
                "réponse non disponible",
                "error generating response.",
            )
        ]

    def clean_considerations_with_frequencies(self, summary_obj, frequencies):
        return [
            c
            for c in summary_obj.considerations
            if frequencies.get(c.strip(), 0) > 0
        ]
