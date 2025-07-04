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

from literev.libs.rag_classes import HactarAug, HactarGen
from literev.libs.scoring import (
    assign_faithfulness_scores,
    sort_documents_by_es_score,
)
from literev.models import (
    Document,
    ProjectDocumentRAG,
    ProjectRAG,
    ProjectRAGStats,
)

logging.basicConfig(level=settings.LOGGING_LEVEL)
logger = logging.getLogger(__name__)


USE_HACTAR_LLM = settings.USE_HACTAR_LLM

TMP_DIR = Path("/tmp") / "rago"

MODULE_NAME = "hactar" if USE_HACTAR_LLM else "openai"

RET_CACHE = CacheFile(target_dir=TMP_DIR / f"ret_{MODULE_NAME}")
AUG_CACHE = CacheFile(target_dir=TMP_DIR / f"aug_{MODULE_NAME}")
GEN_CACHE = CacheFile(target_dir=TMP_DIR / f"gen_{MODULE_NAME}")
DOCUMENT_CACHE = CacheFile(target_dir=TMP_DIR / "documents")


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


def compute_document_cache_key(query: str, document_id: int) -> str:
    """Compute a stable cache key per document, tied to a specific query."""
    return sha256(f"{query.strip()}::{document_id}".encode()).hexdigest()


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
    """
    Run the complete RAG pipeline for a subset of selected documents.

    This includes:
    - RAG answer generation
    - Faithfulness scoring
    - General summary generation
    - Answer classification
    - Consideration tagging

    Parameters
    ----------
    max_doc_ans : int or None, optional
        Maximum number of documents to answer, by default None.
    batch_size : int, optional
        Number of documents to process per batch, by default 10.

    Notes
    -----
    Only documents from `self.document_ids` are processed.
    `project_rag.num_documents` reflects total answered documents.
    `project_rag.valid_answer_count` counts valid and confident responses.
    """

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

        This method processes documents using RAG, generates answers,
        and updates the project status throughout the pipeline.
        """
        logger.debug("Starting RAG processing for documents.")

        queryset = list(
            Document.objects.filter(id__in=self.document_ids).order_by("id")
        )

        if max_doc_ans:
            queryset = sort_documents_by_es_score(
                self.project_rag.project, queryset
            )
            self.project_rag.num_documents = max_doc_ans
        else:
            self.project_rag.num_documents = len(self.document_ids)

        queryset_count = len(queryset)

        self.project_rag.status = "questioning_documents"
        self.project_rag.save()

        counter = 0
        stop_processing = False
        counter_sent_documents = 0

        for batch_start in range(0, queryset_count, batch_size):
            batch = queryset[batch_start : batch_start + batch_size]

            for document in batch:
                success = self._process_document(document)
                counter_sent_documents += 1

                if max_doc_ans and counter_sent_documents > max_doc_ans:
                    self.project_rag.num_documents = counter_sent_documents
                    self.project_rag.save()

                if success:
                    counter += 1
                    if max_doc_ans and counter >= max_doc_ans:
                        logger.debug("Max document answers reached.")
                        stop_processing = True
                        break

            if stop_processing:
                break

        self.project_rag.status = "generating_scores"
        self.project_rag.save()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(assign_faithfulness_scores(self.project_rag))

        self.project_rag.valid_answer_count = (
            self.count_valid_answered_documents(self.project_rag)
        )
        self.project_rag.status = "generating_summary"
        self.project_rag.save()

        self.question_type = self.check_question_type()

        if self.question_type == "closed":
            self.generate_general_summary(summary_only=True)
            self.project_rag.status = "generating_statistics"
            self.project_rag.save()
            self.generate_closed_answer_statistics()
        else:
            self.generate_general_summary(summary_only=False)
            self.project_rag.status = "generating_statistics"
            self.project_rag.save()
            self.generate_open_answer_statistics()
            self.project_rag.status = "tagging_considerations"
            self.project_rag.save()
            self.tag_answers_considerations()

        self.project_rag.status = "completed"
        self.project_rag.save()

        logger.info("RAG pipeline completed for articles.")

    def _process_document(self, document: Document) -> bool:
        try:
            cache_key = compute_document_cache_key(
                self.project_rag.query, document.id
            )
            cached_result = DOCUMENT_CACHE.load(cache_key)

            if cached_result:
                logger.debug(
                    f"[RAG] Loaded cached result for doc #{document.id}"
                )
                ProjectDocumentRAG.objects.create(
                    project_rag=self.project_rag,
                    document=document,
                    citation=cached_result["citation"],
                    answer=cached_result["answer"],
                    citation_context=cached_result.get("citation_context", []),
                )

                return (
                    "réponse non disponible"
                    not in cached_result["answer"].lower()
                )

        except Exception as e:
            logger.warning(
                f"[RAG] Failed to load cache for doc #{document.id}: {e}"
            )

        try:
            chunks = self.split_text_into_chunks(document.raw_document_text)
            if not chunks:
                self._create_empty_response(document, "No content available.")
                return False

            rag = self._get_rag_instance(chunks)
            result = rag.prompt(self.project_rag.query)

            answer = result.answer.strip()
            citation = result.highlight.strip()
            citation_context = rag.logs.get("augmented", {}).get("result", [])

            # Store fallback responses but tag them with score=0 later
            ProjectDocumentRAG.objects.create(
                project_rag=self.project_rag,
                document=document,
                citation=citation,
                answer=answer,
                citation_context=citation_context,
            )

            INVALID_ANSWERS = {
                "",
                "réponse non disponible",
                "no content available.",
                "no content available",
                "error generating response.",
            }

            if answer.lower() in INVALID_ANSWERS:
                return False

            DOCUMENT_CACHE.save(
                cache_key,
                {
                    "citation": citation,
                    "answer": answer,
                    "citation_context": citation_context,
                },
            )

            logger.debug(f"[RAG] Saved result to cache for doc #{document.id}")

            return True

        except Exception as e:
            logger.error(
                f"[RAG] Error generating result for doc #{document.id}: {e}"
            )
            self._create_empty_response(document, "Error generating response.")
            return False

    def _get_rag_instance(self, chunks: list[str]):
        if settings.USE_HACTAR_LLM:
            return Rago(
                retrieval=StringRet(chunks),
                augmented=HactarAug(
                    api_key=settings.HACTAR_API_KEY,
                    top_k=5,
                    model_name="mxbai-embed-large:latest",
                    cache=AUG_CACHE,
                ),
                generation=HactarGen(
                    api_key=settings.HACTAR_API_KEY,
                    model_name="mistral-small3.1:latest",
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
        else:
            return Rago(
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

    def _get_rag_generator(
        self,
        prompt_template: str,
        structured_output: type[BaseModel],
        output_max_length: int = 2048,
        model_name: str | None = None,
    ) -> HactarGen | OpenAIGen:
        """
        Returns an LLM generator (OpenAI or Hactar) for the given prompt and output schema.
        """
        common_params = dict(
            prompt_template=prompt_template,
            temperature=0,
            output_max_length=output_max_length,
            api_params={
                "top_p": 0.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
            },
            structured_output=structured_output,
        )

        if settings.USE_HACTAR_LLM:
            return HactarGen(
                api_key=settings.HACTAR_API_KEY,
                model_name=model_name or "mistral-small3.1:latest",
                **common_params,  # type: ignore
            )
        else:
            return OpenAIGen(
                api_key=self.api_key,
                model_name=model_name or "gpt-4o-mini",
                **common_params,  # type: ignore
            )

    def _create_empty_response(self, document, message: str) -> None:
        """
        Create a fallback placeholder response for a document.

        Parameters
        ----------
        document : Document
            Document object for which RAG failed.
        message : str
            Fallback answer text to store.

        Notes
        -----
        These responses are excluded from summary and statistics.
        """

        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=document,
            citation=message,
            answer=message,
        )

    def generate_general_summary(self, summary_only: bool = False) -> None:
        """
        Generate a general summary and optional considerations.
        Uses only valid responses from `self.document_ids`.
        """
        logger.debug("Generating general summary...")

        answers = self._fetch_valid_document_answers()

        if not answers:
            logger.debug("No valid answers found. Using default summary.")
            summary_data = {
                "summary": "Résumé non disponible",
                "considerations": [],
            }
        else:
            try:
                summary_gen = self._get_rag_generator(
                    prompt_template=self.summary_template_prompt,
                    structured_output=SummaryGeneralAnswer,
                )

                self.summary_obj = summary_gen.generate(
                    query=self.project_rag.query,
                    context=answers,  # keep as list[str] for chunk-aware processing
                )
                summary_data = {
                    "summary": self.summary_obj.summary.strip(),
                    "considerations": (
                        self.summary_obj.considerations
                        if not summary_only
                        else []
                    ),
                }
                logger.debug("Summary generated.")
            except Exception as e:
                logger.error(f"Failed to generate summary: {e}")
                summary_data = {
                    "summary": "Résumé non disponible",
                    "considerations": [],
                }

        self.project_rag.summary_answer = json.dumps(summary_data)
        self.project_rag.save()
        logger.debug("Completed summary generation.")

    def check_question_type(self) -> str:
        """
        Determine whether the user query is open or closed.

        Returns
        -------
        str
            Either "open" or "closed", based on LLM classification.
        """

        logger.debug("Classifying the question type...")

        question_type_gen = self._get_rag_generator(
            prompt_template=self.prompt_check_question_type,
            structured_output=QuestionTypeClassification,
        )

        question_type_obj = question_type_gen.generate(
            query="", context=[self.project_rag.query]
        )

        result = question_type_obj.question_type

        logger.debug("Completed question type classification.")

        return result

    def generate_closed_answer_statistics(self) -> None:
        """
        Generate classification stats for closed-ended answers.

        Notes
        -----
        Only valid answers from `self.document_ids` are classified.
        Categories: 'oui', 'non', 'peut_etre', and 'mixte'.
        Stores results in ProjectRAGStats.
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
        Evaluate support for considerations across valid RAG answers.

        Notes
        -----
        Uses structured output format to detect affirmed considerations.
        Results include frequencies and supporting document IDs.
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

                consideration_gen = self._get_rag_generator(
                    prompt_template=self.evaluate_consideration_template_prompt,
                    structured_output=EvaluationModel,
                    output_max_length=1024,
                )

                consideration_obj = consideration_gen.generate(
                    query=self.project_rag.query,
                    context=[context_block],
                )

                for idx, cons_text in enumerate(considerations):
                    if getattr(
                        consideration_obj, f"argument_{idx + 1}", False
                    ):
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
        Associate considerations with top procedure types.

        Notes
        -----
        Tags up to 3 procedure types from valid affirming documents.
        Updates `summary_answer` with enriched considerations.
        """

        logger.info("Tagging considerations based on affirmed documents...")

        if (
            not getattr(self, "summary_obj", None)
            or not self.summary_obj.considerations
        ):
            logger.warning("No summary or considerations available.")
            return

        valid_rags = self.get_valid_document_rags()

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

        logger.debug("Completed tagging considerations.")

    def categorize_closed_answers(self, answers: list[str]) -> list[str]:
        """
        Classify answers into closed categories using LLM.

        Parameters
        ----------
        answers : list of str
            Valid answer texts.

        Returns
        -------
        list of str
            Categories: 'oui', 'non', 'peut_etre', 'mixte', or 'error'.
        """

        logger.debug("Classifying answers with LLM and structured output...")

        closed_answer_gen = self._get_rag_generator(
            prompt_template=self.classification_template_prompt,
            structured_output=ClosedAnswerClassification,
            output_max_length=64,
        )
        categories = []

        for answer in answers:
            try:
                closed_answer_obj = closed_answer_gen.generate(
                    query=self.project_rag.query, context=[answer]
                )

                label = closed_answer_obj.category
                categories.append(label)
            except Exception as e:
                logger.error(
                    f"LLM classification failed for answer: {answer} | {e}"
                )
                categories.append("error")  # fallback category

        logger.debug("Completed answer classification.")

        return categories

    def compute_polar_answer_stats(
        self, classified_labels: list[str]
    ) -> dict[str, Any]:
        """
        Compute statistics for closed classification labels.

        Parameters
        ----------
        classified_labels : list of str
            List of labels returned by LLM classification.

        Returns
        -------
        dict of str to Any
            Includes counts, percentages, and total size.
        """

        logger.debug("Computing statistics...")

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

        logger.debug("Completed statistics computation.")

        return {
            "counts": counts,
            "percentages": percentages,
            "total": total,
        }

    def clean_considerations_with_frequencies(self, summary_obj, frequencies):
        """
        Filter considerations with non-zero frequency values.

        Parameters
        ----------
        summary_obj : SummaryGeneralAnswer
            The parsed summary object.
        frequencies : dict
            Frequency data from RAG statistics.

        Returns
        -------
        list of str
            Considerations with frequency > 0.
        """

        return [
            c
            for c in summary_obj.considerations
            if frequencies.get(c.strip(), 0) > 0
        ]

    def _get_base_valid_document_rags_queryset(self):
        """
        Base queryset for valid ProjectDocumentRAG entries associated with this project_rag.
        Returns
        -------
        QuerySet
            Common queryset with standard filters and exclusions applied.
        """
        return ProjectDocumentRAG.objects.filter(
            project_rag=self.project_rag,
            document_id__in=self.document_ids,
            confidence_score__gt=0,
        ).exclude(
            answer__in=[
                "",
                "No content available.",
                "Error generating response.",
                "Réponse non disponible",
                "No content available",
            ]
        )

    def _fetch_valid_document_answers(self) -> list[str]:
        """
        Retrieve valid RAG answers for selected documents.
        """

        return list(
            self._get_base_valid_document_rags_queryset().values_list(
                "answer", flat=True
            )
        )

    def get_valid_document_rags(self) -> list[ProjectDocumentRAG]:
        """
        Return valid ProjectDocumentRAG entries from selected documents.
        """

        return list(
            self._get_base_valid_document_rags_queryset().select_related(
                "document"
            )
        )

    def count_valid_answered_documents(self, project_rag: ProjectRAG) -> int:
        """
        Count valid answered documents within the selected subset.
        """
        return self._get_base_valid_document_rags_queryset().count()
