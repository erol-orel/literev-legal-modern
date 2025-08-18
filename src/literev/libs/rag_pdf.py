"""RAG workflow."""

from __future__ import annotations

import asyncio
import json
import logging

from functools import wraps
from hashlib import sha256
from typing import Any, Callable, Literal, cast

from django.conf import settings
from django.db.models.query import QuerySet
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field, create_model, field_validator
from rago import Rago
from rago.augmented import OpenAIAug
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from rago.retrieval import StringRet

from literev.libs.parsing import extract_after_endroit
from literev.libs.rag_classes import HactarAug, HactarGen
from literev.libs.scoring import (
    get_faithfulness_score,
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

USE_HACTAR_LLM: bool = getattr(settings, "USE_HACTAR_LLM", False)

CACHE_DIR = settings.LITEREV_CACHE_DIR / "rago"
MODULE_NAME = "hactar" if USE_HACTAR_LLM else "openai"
RET_CACHE = CacheFile(target_dir=CACHE_DIR / f"ret_{MODULE_NAME}")
AUG_CACHE = CacheFile(target_dir=CACHE_DIR / f"aug_{MODULE_NAME}")
GEN_CACHE = CacheFile(target_dir=CACHE_DIR / f"gen_{MODULE_NAME}")
DOCUMENT_CACHE = CacheFile(target_dir=CACHE_DIR / "documents")


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


@ret_cache
def prepare_chunks(text: str) -> list[str]:
    """Split input text into overlapping chunks for better retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    )
    text_after_endroit = extract_after_endroit(text)

    return splitter.split_text(text_after_endroit)


def get_rag_generator(
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
            api_key=settings.OPENAI_API_KEY,
            model_name=model_name or "gpt-4o-mini",
            **common_params,  # type: ignore
        )


class OpenAIAnswerClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.document_answering_system_prompt = (
            "You are a factual legal assistant. "
            "Always answer in French based solely on the provided context. "
            "If you are absolutely certain the context has no relevant information, "
            'return exactly the string "Réponse non disponible".'
        )
        self.document_answering_user_prompt = (
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

    def get_answer(self, query, chunks):
        answer_dict = {}

        if settings.USE_HACTAR_LLM:
            augmented = HactarAug(
                api_key=settings.HACTAR_API_KEY,
                top_k=5,
                model_name="mxbai-embed-large:latest",  # model_name="nomic-embed-text", #Suggested change
                cache=AUG_CACHE,
            )
            generation = HactarGen(
                api_key=settings.HACTAR_API_KEY,
                model_name="mistral-small3.1:24b",
                system_message=self.document_answering_system_prompt,
                prompt_template=self.document_answering_user_prompt,
                temperature=0.0,
                output_max_length=16384,
                api_params={
                    "top_p": 0.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                },
                structured_output=RAGAnswer,
                cache=GEN_CACHE,
            )

        else:
            augmented = OpenAIAug(
                api_key=self.api_key,
                top_k=5,
                model_name="text-embedding-ada-002",
                cache=AUG_CACHE,
            )
            generation = OpenAIGen(
                api_key=self.api_key,
                model_name="gpt-4o-mini",
                system_message=self.document_answering_system_prompt,
                prompt_template=self.document_answering_user_prompt,
                temperature=0.0,
                output_max_length=16384,
                api_params={
                    "top_p": 0.0,
                    "frequency_penalty": 0.0,
                    "presence_penalty": 0.0,
                },
                structured_output=RAGAnswer,
                cache=GEN_CACHE,
            )

        rag = Rago(
            retrieval=StringRet(chunks),
            augmented=augmented,
            generation=generation,
        )

        rag_answer = rag.prompt(query)
        citation_context = rag.logs.get("augmented", {}).get("result", [])

        if not isinstance(rag_answer, RAGAnswer):
            return None

        retrieved_answer = rag_answer.answer.strip().lower()

        not_valid_answers = [
            "réponse non disponible",
            "no content available",
            "error generating response",
            "no content available",
        ]

        if not retrieved_answer or any(
            retrieved_answer.startswith(not_valid_answer)
            for not_valid_answer in not_valid_answers
        ):
            return None

        answer_dict.update(
            {
                "answer": rag_answer.answer.strip(),
                "citation": rag_answer.highlight.strip(),
                "citation_context": citation_context,
            }
        )

        return answer_dict


class OpenAISummaryGenerator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.summary_template_prompt = (
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

    def get_summary(
        self, query: str, answers: list[str], create_considerations: bool
    ) -> dict[str, Any]:
        if not answers:
            logger.error(f"Empty valid answers list. for {query}")
            return {
                "summary": "Résumé non disponible",
                "considerations": [],
            }

        summary_gen = get_rag_generator(
            prompt_template=self.summary_template_prompt,
            structured_output=SummaryGeneralAnswer,
        )

        try:
            summary_obj = cast(
                SummaryGeneralAnswer,
                summary_gen.generate(
                    query=query,
                    context=answers,
                ),
            )
            return {
                "summary": summary_obj.summary.strip(),
                "considerations": summary_obj.considerations
                if create_considerations
                else [],
            }
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return {
                "summary": "Résumé non disponible",
                "considerations": [],
            }


class QuestionClassifier:
    def __init__(self, api_key):
        self.api_key = api_key
        self.prompt_check_question_type = (
            "You are a legal expert. Given the following query, classify it as either:\n"
            "- 'closed' if it requires a yes/no (polar) given answer\n"
            "- 'open' otherwise.\n\n"
            "Query:\n{context}"
        )

    def get_question_type(self, query: str) -> str:
        """
        Determine whether the user query is open or closed.

        Returns
        -------
        str
            Either "open" or "closed", based on LLM classification.
        """

        logger.debug("Classifying the question type...")

        question_type_gen = get_rag_generator(
            prompt_template=self.prompt_check_question_type,
            structured_output=QuestionTypeClassification,
            output_max_length=64,
        )

        result_obj: QuestionTypeClassification = cast(
            QuestionTypeClassification,
            question_type_gen.generate(query="", context=[query]),
        )

        result = result_obj.question_type

        logger.debug("Completed question type classification.")

        return result


class StatsGenerator:
    def __init__(self, api_key):
        self.api_key = api_key
        self.classification_template_prompt = (
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
        self.evaluate_consideration_template_prompt = (
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

    def generate_closed_answer_statistics(
        self, query: str, answers: list[str]
    ) -> dict[str, Any]:
        """
        Generate classification stats for closed-ended answers.

        Notes
        -----
        Only valid answers from `self.documents_ids` are classified.
        Categories: 'yes', 'no', 'maybe', and 'mixed'.
        Stores results in ProjectRAGStats.
        """

        logger.debug("Generating closed-ended statistics...")

        classified_labels = self.categorize_closed_answers(query, answers)
        stats = self.compute_polar_answer_stats(classified_labels)
        logger.debug(f"Classification stats saved: {stats}")

        return stats

    def categorize_closed_answers(
        self, query: str, answers: list[str]
    ) -> list[str]:
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

        closed_answer_gen = get_rag_generator(
            prompt_template=self.classification_template_prompt,
            structured_output=ClosedAnswerClassification,
            output_max_length=256,
        )

        categories = []

        for answer in answers:
            try:
                closed_answer_obj: ClosedAnswerClassification = cast(
                    ClosedAnswerClassification,
                    closed_answer_gen.generate(query=query, context=[answer]),
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
        self,
        classified_labels: list[str],
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

    # TODO: Check the reason for this function
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

    def generate_open_answer_statistics(
        self, query, valid_rags, considerations
    ) -> dict[str, Any]:
        """
        Evaluate support for considerations across valid RAG answers.

        Notes
        -----
        Uses structured output format to detect affirmed considerations.
        Results include frequencies and supporting document IDs.
        """

        logger.debug("Generating open-ended answer statistics...")

        if not considerations:
            logger.warning("No considerations found in summary to evaluate.")
            return {}

        considerations = [c.strip() for c in considerations]
        results = {c: 0 for c in considerations}

        docs_affirmed: dict[str, Any] = {c: set() for c in considerations}

        EvaluationModel = build_consideration_model(len(considerations))

        for doc_rag in valid_rags:
            try:
                arguments_block = "\n".join(
                    f"* argument_{i + 1}: {c}"
                    for i, c in enumerate(considerations)
                )

                context_block = (
                    f"Excerpt:\n{doc_rag.answer}\n\n"
                    f"Considerations:\n{arguments_block}"
                )

                consideration_gen = get_rag_generator(
                    prompt_template=self.evaluate_consideration_template_prompt,
                    structured_output=EvaluationModel,
                    output_max_length=1024,
                )

                consideration_obj = consideration_gen.generate(
                    query=query,
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
            "total_documents": len(valid_rags),
            "consideration_frequencies": results,
            "affirmed_docs_by_consideration": {
                k: list(v) for k, v in docs_affirmed.items()
            },
        }

        return stats

    def tag_answers_considerations(
        self,
        considerations: list[str],
        valid_rags: QuerySet[ProjectRAGStats],
        classification_stats: dict[str, Any],
    ) -> list[Any]:
        """
        Associate considerations with top procedure types.

        Notes
        -----
        Tags up to 3 procedure types from valid affirming documents.
        Updates `summary_answer` with enriched considerations.
        """

        logger.debug("Tagging considerations based on affirmed documents...")

        if not considerations:
            logger.warning("No summary or considerations available.")
            return []

        tagged_data = {
            rag.document.id: {
                "procedure_type": rag.document.procedure_type or "Inconnu"
            }
            for rag in valid_rags
        }

        total_docs = len(tagged_data)

        frequencies = classification_stats.get("consideration_frequencies", {})
        affirmed_docs: dict[str, Any] = classification_stats.get(
            "affirmed_docs_by_consideration", {}
        )

        tagged_considerations = []

        for consideration in considerations:
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

        return tagged_considerations


class RagAnswersManager:
    def __init__(self, project_rag_id: int, documents_ids: list[int]) -> None:
        """Initialize the processor with project RAG ID and document IDs."""
        self.api_key: str = getattr(settings, "OPENAI_API_KEY", "")

        self.project_rag = ProjectRAG.objects.get(id=project_rag_id)
        self.project_rag.status = "in-progress"
        self.project_rag.save()

        self.documents_ids = documents_ids
        self.answer_generator = OpenAIAnswerClient(self.api_key)
        self.summary_generator = OpenAISummaryGenerator(self.api_key)
        self.loop = asyncio.get_event_loop()
        self.query_classifier = QuestionClassifier(self.api_key)
        self.stats_generator = StatsGenerator(self.api_key)

    def save_and_cache_rag_answer(
        self,
        cache_key: str,
        document: Document,
        answer_dict: dict[str, Any],
    ):
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=document,
            citation=answer_dict["citation"],
            answer=answer_dict["answer"],
            citation_context=answer_dict["citation_context"],
        )
        DOCUMENT_CACHE.save(
            cache_key,
            {
                "citation": answer_dict["citation"],
                "answer": answer_dict["answer"],
                "citation_context": answer_dict["citation_context"],
            },
        )
        logger.info(f"[RAG] Saved result to cache for article #{document.id}")

    def _create_and_save_empty_response(
        self,
        cache_key: str,
        document: Document,
        reason: str = "Réponse non disponible",
    ) -> None:
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=document,
            citation=reason,
            answer=reason,
        )
        DOCUMENT_CACHE.save(
            cache_key,
            {
                "citation": reason,
                "answer": reason,
                "citation_context": [],
            },
        )
        logger.info(f"[RAG] Saved result to cache for article #{document.id}")

    def get_and_save_answers_from_documents(
        self, documents: list[Document], max_doc_ans: int | None = None
    ) -> None:
        # Getting individual answers per document
        if max_doc_ans:
            self.project_rag.num_documents = max_doc_ans
        else:
            self.project_rag.num_documents = len(self.documents_ids)

        self.project_rag.save()

        documents_asked = 0
        ans_counter = 0

        for document in documents:
            documents_asked += 1
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

                cached_answer = cached_result["answer"].lower()
                not_valid_answers = [
                    "réponse non disponible",
                    "no content available",
                    "error generating response",
                    "no content available",
                ]

                if cached_answer and not any(
                    cached_answer.startswith(not_valid_answer)
                    for not_valid_answer in not_valid_answers
                ):
                    ans_counter += 1
                continue

            chunks = prepare_chunks(document.raw_document_text)

            if not chunks:
                logger.info(f"There is no chunks for document: {document.id}")
                continue

            rag_answer_dict = self.answer_generator.get_answer(
                self.project_rag.query, chunks
            )

            if rag_answer_dict:
                self.save_and_cache_rag_answer(
                    cache_key, document, rag_answer_dict
                )
                ans_counter += 1
            else:
                logger.info(
                    f"There is no answer for query: {self.project_rag.query}, document: {document.id}"
                )
                self._create_and_save_empty_response(cache_key, document)

            if max_doc_ans and documents_asked > max_doc_ans:
                self.project_rag.num_documents = documents_asked
                self.project_rag.save()

            if max_doc_ans and ans_counter >= max_doc_ans:
                logger.debug("Max document answers reached.")
                break
        return

    def get_and_save_answers_scores(
        self, rag_documents_w_valid_answers: QuerySet[ProjectDocumentRAG]
    ) -> None:
        for rag_document in rag_documents_w_valid_answers:
            score = self.loop.run_until_complete(
                get_faithfulness_score(
                    self.project_rag.query,
                    rag_document.answer,
                    rag_document.citation_context,
                )
            )
            rag_document.confidence_score = score
            rag_document.save()

    def run_pipeline(
        self,
        max_doc_ans: int | None = None,
    ) -> None:
        """
        Run the complete RAG pipeline for a set of documents.

        This includes:
        - RAG answer generation
        - Faithfulness scoring
        - General summary generation
        - Answer classification
        - Consideration tagging

        Notes
        -----
        Only documents from self.documents_ids are processed.
        project_rag.num_documents reflects total answered documents.
        project_rag.valid_answer_count counts valid and confident responses.
        """

        logger.debug("Starting RAG processing for documents.")

        # Getting documents queryset
        queryset = Document.objects.filter(id__in=self.documents_ids).order_by(
            "id"
        )
        if max_doc_ans:
            queryset = sort_documents_by_es_score(
                self.project_rag.project, queryset
            )
        else:
            queryset = list(queryset)

        self.project_rag.status = "questioning_documents"
        self.project_rag.save()

        self.get_and_save_answers_from_documents(queryset, max_doc_ans)

        # Generating confidence score for answers
        self.project_rag.status = "generating_scores"
        self.project_rag.save()

        # Retrieve articles_rag
        rag_documents_w_valid_answers = (
            ProjectDocumentRAG.objects.filter(
                project_rag=self.project_rag,
                document_id__in=self.documents_ids,
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

        self.get_and_save_answers_scores(rag_documents_w_valid_answers)

        # Generating a general answer summary
        self.project_rag.status = "generating_summary"
        self.project_rag.save()

        self.question_type = self.query_classifier.get_question_type(
            self.project_rag.query
        )

        create_considerations = "closed" != self.question_type

        documents_rag_w_scores = rag_documents_w_valid_answers.filter(
            confidence_score__gt=0.0
        )
        self.project_rag.valid_answer_count = documents_rag_w_scores.count()

        if not documents_rag_w_scores:
            logger.warning("No valid documents available for evaluation.")
            return

        answers = [
            doc_rag.answer.strip() for doc_rag in documents_rag_w_scores
        ]

        summary_dict = self.summary_generator.get_summary(
            self.project_rag.query, answers, create_considerations
        )

        self.project_rag.summary_answer = json.dumps(summary_dict)
        self.project_rag.save()

        self.project_rag.status = "generating_statistics"
        self.project_rag.save()

        if self.question_type == "closed":
            stats = self.stats_generator.generate_closed_answer_statistics(
                self.project_rag.query, answers
            )
            ProjectRAGStats.objects.create(
                project_rag=self.project_rag,
                classification_stats=stats,
                user=self.project_rag.project.user,
            )
        else:
            stats = self.stats_generator.generate_open_answer_statistics(
                query=self.project_rag.query,
                valid_rags=documents_rag_w_scores,
                considerations=summary_dict["considerations"],
            )

            # TODO: Check what happens when stats are empty
            ProjectRAGStats.objects.create(
                project_rag=self.project_rag,
                classification_stats=stats,
                user=self.project_rag.project.user,
            )
            logger.debug(f"Open-ended statistics generated: {stats}")

            self.project_rag.status = "tagging_considerations"
            self.project_rag.save()

            tagged_considerations = (
                self.stats_generator.tag_answers_considerations(
                    considerations=summary_dict["considerations"],
                    valid_rags=documents_rag_w_scores,
                    classification_stats=stats,
                )
            )

            # TODO: Check what happens when tagged_considerations are empty
            summary_dict["considerations"] = tagged_considerations
            self.project_rag.summary_answer = json.dumps(summary_dict)
            self.project_rag.save()
            logger.debug("Completed tagging considerations.")

        self.project_rag.status = "completed"
        self.project_rag.save()

        logger.debug("RAG pipeline completed for documents.")
