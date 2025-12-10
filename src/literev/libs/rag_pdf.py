"""RAG workflow."""

from __future__ import annotations

import asyncio
import json
import logging

from functools import wraps
from hashlib import sha256
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    cast,
)

import joblib

from django.conf import settings
from django.db.models import F
from django.db.models.query import QuerySet
from joblib import Parallel, delayed
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    field_validator,
    model_validator,
)
from rago import Rago
from rago.augmented import OpenAIAug
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from rago.retrieval import StringRet

from literev.legal.extract_minor_major import (
    Classification,
    classify_chunks_llm,
    get_sentences,
    materialize_classification,
    normalize_text,
    openai_llm_call,
    pack_chunks,
    split_sentences_fr_legal,
)
from literev.libs.chroma_utils import (
    chroma_client,
    get_best_section_chunks,
    llm_answer,
    openai_client,
)
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

MODEL_CHAT = "gpt-4.1-mini"

logging.basicConfig(level=settings.LOGGING_LEVEL)
logger = logging.getLogger(__name__)

USE_HACTAR_LLM: bool = getattr(settings, "USE_HACTAR_LLM", False)
MIN_CONFIDENCE = getattr(settings, "RAG_MIN_CONFIDENCE", 0.0)

CACHE_DIR = settings.LITEREV_CACHE_DIR / "rago"
MODULE_NAME = "hactar" if USE_HACTAR_LLM else "openai"
RET_CACHE = CacheFile(target_dir=CACHE_DIR / f"ret_{MODULE_NAME}")
AUG_CACHE = CacheFile(target_dir=CACHE_DIR / f"aug_{MODULE_NAME}")
GEN_CACHE = CacheFile(target_dir=CACHE_DIR / f"gen_{MODULE_NAME}")
DOCUMENT_CACHE = CacheFile(target_dir=CACHE_DIR / "documents")
FAITH_CACHE = CacheFile(target_dir=CACHE_DIR / f"faith_{MODULE_NAME}")

EMBEDDING_MODEL = "text-embedding-3-large"
MAX_WORKERS_RAG = 10


def ret_cache(func: Callable[[str], list[str]]) -> Callable[[str], list[str]]:
    cache = RET_CACHE

    @wraps(func)
    def wrapper(text: str) -> list[str]:
        cached = cache.load(text)
        if cached is not None:
            return cast(list[str], cached)
        result = func(text)
        cache.save(text, result)
        return result

    return wrapper


INVALID_CHARS = ["\x00"]


def sanitize_text_replace(s: str) -> str:
    """Remove null chars from a string."""
    if not isinstance(s, str):
        return s
    for ch in INVALID_CHARS:
        s = s.replace(ch, "")  # or ' ' or '\uFFFD'
    return s


def flatten_and_sanitize(answer):
    """
    Transform list and dicts to its equivalent string.

    Every string is sanitized(removes null chars in the text).
    """
    answer = sanitize_replace(answer)
    json_value = json.loads(answer)
    flatten = flatten_json_values(json_value)

    return json.dumps(flatten)


def flatten_json_values(d):
    """Flatten values from a dictionary."""
    for k, v in d.items():
        if isinstance(v, dict):
            # Join inner dict as lines of key: value
            d[k] = "\n".join(f"{ik}: {iv}" for ik, iv in v.items())
        elif isinstance(v, list):
            # Join list as a single string (comma or bullet points)
            d[k] = "\n".join(str(item) for item in v)
        else:
            d[k] = str(v)
    return d


def sanitize_replace(obj):
    """Sanitize string from object."""
    if isinstance(obj, str):
        return sanitize_text_replace(obj)
    if isinstance(obj, list):
        return [sanitize_replace(x) for x in obj]
    if isinstance(obj, dict):
        return {
            (
                sanitize_text_replace(k) if isinstance(k, str) else k
            ): sanitize_replace(v)
            for k, v in obj.items()
        }
    return obj


def compute_document_cache_key(query: str, document_id: int) -> str:
    """Compute a stable cache key per document, tied to a specific query."""
    return sha256(f"{query.strip()}::{document_id}".encode()).hexdigest()


def compute_faithfulness_cache_key(
    query: str,
    document_id: int,
    answer: str,
    citation_context: list[str] | list[dict] | None,
) -> str:
    payload = {
        "query": query.strip(),
        "document_id": document_id,
        "answer": (answer or "").strip(),
        "citation_context": citation_context or [],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return sha256(blob.encode("utf-8")).hexdigest()


class MinorMajorPair(BaseModel):
    """
    Structured output for Minor/Major classification.

    Accepts several key variants from LLMs and normalizes to:
    - majeure: List[str]
    - mineure: List[str]
    """

    model_config = ConfigDict(extra="ignore")

    majeure: List[str] = Field(
        default_factory=list,
    )
    mineure: List[str] = Field(
        default_factory=list,
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_aliases(cls, incoming: Dict[str, Any]) -> Dict[str, Any]:
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
    Return an LLM generator (OpenAI or Hactar).

    The result is according to the given prompt and output schema.
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
            model_name=model_name or "gpt-4.1-mini",
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
                top_k=30,
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
                top_k=30,
                model_name="text-embedding-3-large",
                cache=AUG_CACHE,
            )
            generation = OpenAIGen(
                api_key=self.api_key,
                model_name="gpt-4.1-mini",
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

        if isinstance(rag_answer, RAGAnswer):
            answer_dict.update(
                {
                    "answer": rag_answer.answer.strip(),
                    "citation": rag_answer.highlight.strip(),
                    "citation_context": citation_context,
                }
            )
        else:
            answer_dict.update(
                {
                    "answer": "Error generating response",
                    "citation": "",
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

    def generate_open_answer_statistics_fait(
        self, query, subsommation_dict, considerations
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

        for d_id, ans in subsommation_dict.items():
            try:
                arguments_block = "\n".join(
                    f"* argument_{i + 1}: {c}"
                    for i, c in enumerate(considerations)
                )

                context_block = (
                    f"Excerpt:\n{ans}\n\nConsiderations:\n{arguments_block}"
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
                        docs_affirmed[cons_text].add(d_id)

            except Exception as e:
                logger.warning(f"Evaluation failed for doc {d_id}: {e}")

        stats = {
            "total_documents": len(subsommation_dict),
            "consideration_frequencies": results,
            "affirmed_docs_by_consideration": {
                k: list(v) for k, v in docs_affirmed.items()
            },
        }

        return stats

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

    def tag_answers_considerations_v2(
        self,
        considerations: list[str],
        procedure_type_dict,
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
            d_id: {"procedure_type": procedure_type or "Inconnu"}
            for d_id, procedure_type in procedure_type_dict.items()  # valid_rags
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
        logger.debug(f"[RAG] Saved result to cache for article #{document.id}")

    def _create_and_save_empty_response(
        self,
        cache_key: str,
        document: Document,
        answer_dict: dict[str, str],
        reason: str = "Réponse non disponible",
    ) -> None:
        ProjectDocumentRAG.objects.create(
            project_rag=self.project_rag,
            document=document,
            citation=answer_dict["citation_context"],
            answer=answer_dict["answer"],
        )
        DOCUMENT_CACHE.save(
            cache_key,
            {
                "citation": reason,
                "answer": answer_dict["answer"],
                "citation_context": answer_dict["citation_context"],
            },
        )
        logger.debug(f"[RAG] Saved result to cache for article #{document.id}")

    def get_and_save_answers_from_documents(
        self, documents: list[Document], max_doc_ans: int | None = None
    ) -> None:
        """Generate and store answers for each document in the project."""
        if max_doc_ans:
            self.project_rag.num_documents = max_doc_ans
        else:
            self.project_rag.num_documents = len(self.documents_ids)
        self.project_rag.save()

        documents_asked = 0
        ans_counter = 0
        builder = RAGClassificationBuilder()

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
                cached_answer = (cached_result["answer"] or "").lower()
                not_valid_answers = [
                    "réponse non disponible",
                    "no content available",
                    "error generating response",
                    "no content available",
                ]
                if cached_answer and not any(
                    cached_answer.startswith(bad) for bad in not_valid_answers
                ):
                    ans_counter += 1
                continue

            try:
                aggregated = builder.load_or_classify_document(
                    document, engine="openai"
                )
                rows = aggregated.get("results", [])
                chunks = [
                    frag.strip()
                    for row in rows
                    for frag in row.get("mineures", [])
                    if frag and isinstance(frag, str)
                ]
            except Exception as exc:
                logger.warning(
                    f"Classification failed for doc {document.id}: {exc}"
                )
                chunks = []

            if not chunks:
                logger.warning(
                    f"There are no chunks for document: {document.id}"
                )
                self._create_and_save_empty_response(
                    cache_key,
                    document,
                    {
                        "answer": "Réponse non disponible",
                        "citation": "",
                        "citation_context": [],
                    },
                )
                continue

            rag_answer_dict = self.answer_generator.get_answer(
                self.project_rag.query, chunks
            )
            llm_answer = (rag_answer_dict.get("answer") or "").lower()
            not_valid_answers = [
                "réponse non disponible",
                "no content available",
                "error generating response",
                "no content available",
            ]

            if llm_answer and not any(
                llm_answer.startswith(bad) for bad in not_valid_answers
            ):
                self.save_and_cache_rag_answer(
                    cache_key, document, rag_answer_dict
                )
                ans_counter += 1
            else:
                logger.warning(
                    f"No valid answer for query: {self.project_rag.query}, document: {document.id}"
                )
                self._create_and_save_empty_response(
                    cache_key, document, rag_answer_dict
                )

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
            cache_key = compute_faithfulness_cache_key(
                self.project_rag.query,
                rag_document.document_id,
                rag_document.answer,
                rag_document.citation_context,
            )

            cached = FAITH_CACHE.load(cache_key)
            if cached is not None:
                score = float(cached.get("score", 0.0))
            else:
                # Always compute with a fresh loop per call in workers
                score = asyncio.run(
                    get_faithfulness_score(
                        self.project_rag.query,
                        rag_document.answer,
                        rag_document.citation_context,
                    )
                )
                FAITH_CACHE.save(cache_key, {"score": float(score)})

            # Persist to DB regardless of cache path
            rag_document.confidence_score = score
            rag_document.save(update_fields=["confidence_score"])

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

        # Retrieve documents_rag
        rag_documents_w_valid_answers = (
            ProjectDocumentRAG.objects.filter(
                project_rag=self.project_rag,
                document_id__in=self.documents_ids,
            )
            .exclude(
                answer__in=[
                    "",
                    "No content available.",
                    "No content available",
                    "Error generating response.",
                    "Error generating response",
                    "Réponse non disponible",
                    "No content available",
                ]
            )
            .select_related("document")
        )

        self.get_and_save_answers_scores(rag_documents_w_valid_answers)

        # Generating a general answer summary
        self.project_rag.status = "generating_summary"
        self.project_rag.save(update_fields=["status"])

        self.question_type = self.query_classifier.get_question_type(
            self.project_rag.query
        )
        create_considerations = self.question_type != "closed"

        documents_rag_w_scores = rag_documents_w_valid_answers.filter(
            confidence_score__gte=MIN_CONFIDENCE
        )

        self.project_rag.valid_answer_count = (
            rag_documents_w_valid_answers.filter(
                confidence_score__isnull=False
            )
            .exclude(confidence_score=0.0)
            .count()
        )
        self.project_rag.save(update_fields=["valid_answer_count"])

        if not documents_rag_w_scores.exists():
            logger.warning("No valid documents available for evaluation.")

            empty_summary = {
                "summary": "Résumé non disponible",
                "considerations": [],
            }
            self.project_rag.summary_answer = json.dumps(empty_summary)
            self.project_rag.status = "completed"
            self.project_rag.save(update_fields=["summary_answer", "status"])
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


class DocumentCache:
    """Cache for document classifications."""

    def __init__(self) -> None:
        self.cache_dir: Path = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _document_cache(self) -> CacheFile:
        return CacheFile(target_dir=self.cache_dir / "documents")

    def load(
        self, raw_document_key: str, engine: str
    ) -> Optional[Dict[str, Any]]:
        """Load aggregated classification by raw key + engine, with logging."""
        key = f"classify_doc_{raw_document_key}_{engine}"
        dir_path = self.cache_dir / "documents"
        data = self._document_cache().load(key)
        if data is not None:
            logger.debug(f"[CLASSIFY][CACHE-HIT]: key={key} dir={dir_path}")
        else:
            logger.debug(f"[CLASSIFY][CACHE-MISS]: key={key} dir={dir_path}")
        return data

    def save(
        self, raw_document_key: str, engine: str, aggregated: Dict[str, Any]
    ) -> None:
        """Save aggregated classification by raw key + engine, with logging."""
        key = f"classify_doc_{raw_document_key}_{engine}"
        dir_path = self.cache_dir / "documents"
        self._document_cache().save(key, aggregated)
        logger.debug(
            f"[CLASSIFY][CACHE-SAVE]: key={key} dir={dir_path} "
            f"items={len(aggregated.get('results', []))}"
        )


JuridicField = Literal["majeures", "mineures"]


class RAGClassificationBuilder:
    """Minor/Major classification with sentence-first, legal-split fallback."""

    def __init__(self) -> None:
        self.cache_dir: Path = CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = DocumentCache()

        self.model_config: Dict[str, Dict[str, str]] = {
            "openai": {"provider": "openai", "chat": "gpt-4.1-mini"},
            "hactar": {"provider": "hactar", "chat": "mistral-small3.1:24b"},
        }

        self.invalid_answers: set[str] = {
            "",
            "réponse non disponible",
            "reponse non disponible",
            "no content available",
            "error generating response",
        }

    @staticmethod
    def _safe_raw_key(raw_id: Optional[str], doc_id: Optional[int]) -> str:
        raw_id = (raw_id or "").strip()
        return raw_id if raw_id else f"doc_{int(doc_id or 0)}"

    @staticmethod
    def normalize_field_to_list(value: Any) -> List[str]:
        """Normalize input value to a list of non-empty, stripped strings."""
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            out: List[str] = []
            for item in value:
                if isinstance(item, str):
                    s = item.strip()
                    if s:
                        out.append(s)
            return out
        return []

    def is_invalid_list(self, texts: List[str]) -> bool:
        """True if the list is empty or only contains invalid placeholders."""
        if not texts:
            return True
        lowered = [t.strip().lower() for t in texts if isinstance(t, str)]
        return all((not t) or (t in self.invalid_answers) for t in lowered)

    def _classify_by_sentences(
        self,
        engine: str,
        raw_key: str,
        raw_text: str,
    ) -> list[dict[str, list[str]]]:
        """Primary path: sentence split → one-shot chunk-ID classification."""
        logger.debug(
            f"[CLASSIFY]: start sentence classification raw_id={raw_key}"
        )

        text = normalize_text(raw_text or "")
        chunks = get_sentences(text)

        if not chunks:
            return []

        result: Classification = classify_chunks_llm(chunks, openai_llm_call)
        maj_texts, min_texts = materialize_classification(
            result, chunks, "document"
        )

        majeures = self.normalize_field_to_list(maj_texts)
        mineures = self.normalize_field_to_list(min_texts)

        if self.is_invalid_list(majeures) and self.is_invalid_list(mineures):
            return []

        rows = [{"majeures": majeures, "mineures": mineures}]
        logger.debug(
            f"[CLASSIFY]: done sentence classification raw_id={raw_key} results={len(rows)}"
        )
        return rows

    def _classify_by_slices(
        self,
        raw_key: str,
        raw_text: str,
    ) -> list[dict[str, list[str]]]:
        """Fallback: legal-aware split → token packer → one classification."""
        logger.debug(f"[CLASSIFY]: start raw_id={raw_key}")

        rows: list[dict[str, list[str]]] = []
        try:
            text = normalize_text(raw_text or "")
            sents = split_sentences_fr_legal(text)
            chunks = pack_chunks(sents, max_tokens=900, overlap_tokens=80)

            if not chunks:
                logger.debug(
                    f"[CLASSIFY]: raw_id={raw_key} no chunks produced"
                )
                return rows

            result: Classification = classify_chunks_llm(
                chunks, openai_llm_call
            )
            maj_texts, min_texts = materialize_classification(
                result, chunks, "document"
            )

            majeures = self.normalize_field_to_list(maj_texts)
            mineures = self.normalize_field_to_list(min_texts)

            if self.is_invalid_list(majeures) and self.is_invalid_list(
                mineures
            ):
                logger.debug(
                    f"[CLASSIFY]: raw_id={raw_key} empty classification"
                )
                return rows

            rows.append({"majeures": majeures, "mineures": mineures})

        except Exception as exc:
            logger.warning(f"[CLASSIFY]: raw_id={raw_key} skipped: {exc}")

        logger.debug(
            f"[CLASSIFY]: done by slice raw_id={raw_key} results={len(rows)}",
        )

        return rows

    def classify_document_minor_major(
        self,
        document,
        *,
        engine: str = "openai",
    ) -> Dict[str, Any]:
        """Classify a document into 'majeures' and 'mineures' using LLM."""
        raw_key = self._safe_raw_key(
            getattr(document, "raw_document_id", None),
            getattr(document, "id", None),
        )

        rows = self._classify_by_sentences(
            engine=engine, raw_key=raw_key, raw_text=document.raw_document_text
        )
        if rows:
            aggregated = {"raw_document_id": raw_key, "results": rows}
            self.cache.save(raw_key, engine, aggregated)
            logger.debug(
                f"[CLASSIFY]: finish by sentence raw_id={raw_key} results={len(rows)}"
            )
            return aggregated

        # Fallback to legal-aware slices
        logger.warning(f"[CLASSIFY]: fallback to slicing raw_id={raw_key}")
        rows = self._classify_by_slices(
            raw_key=raw_key, raw_text=document.raw_document_text
        )

        aggregated = {"raw_document_id": raw_key, "results": rows}
        self.cache.save(raw_key, engine, aggregated)

        logger.debug(
            f"[CLASSIFY]: finish slicing raw_id={raw_key} results={len(rows)}"
        )
        return aggregated

    def load_or_classify_document(
        self,
        document,
        *,
        engine: str = "openai",
    ) -> Dict[str, Any]:
        """Load cached classification or run it if not cached."""
        raw_key = self._safe_raw_key(
            getattr(document, "raw_document_id", None),
            getattr(document, "id", None),
        )
        cached = self.cache.load(raw_key, engine)
        if cached:
            logger.debug(
                f"[CLASSIFY]: using cached classification raw_id={raw_key} results={len(cached.get('results', []))}"
            )
            return cached

        logger.debug(
            f"[CLASSIFY]: cache miss, running classification raw_id={raw_key}"
        )
        return self.classify_document_minor_major(document, engine=engine)


def get_answer_document_worker(
    payload, question, embedded_question, collection
):
    record_key = payload["record_key"]
    try:
        block_section = get_best_section_chunks(
            record_key, question, embedded_question, collection
        )
        answer = llm_answer(question, block_section)
        _ = json.loads(answer)
    except Exception as e:
        logging.info(f"Error during generating answer: {e}")

        answer = """{
            "Examen des faits": [],
            "Analyse juridique (subsomption)": [],
            "Décision finale": []
            }"""
        block_section = {
            "Majeure": [],
            "Mineure-Faits": [],
            "Mineure-Subsommation": [],
            "Conclusion": [],
        }

    return payload["id"], block_section, answer


class CustomRagAnswersGenerator:
    def __init__(
        self, project_rag_id: int, documents_ids: list[int], chambre_name: str
    ) -> None:
        self.api_key: str = getattr(settings, "OPENAI_API_KEY")

        self.project_rag = ProjectRAG.objects.get(id=project_rag_id)
        self.project_rag.status = "in-progress"
        self.project_rag.save()

        self.documents_ids = documents_ids

        self.query_classifier = QuestionClassifier(self.api_key)

        self.stats_generator = StatsGenerator(self.api_key)

        self.summary_generator = OpenAISummaryGenerator(self.api_key)

        self.chambre_name = chambre_name

    def get_mineures_faits_answers(self, answers_block):
        """Return the list of answers from the fait section."""
        ALTERNATIVES_MINEURES_KEY = [
            "Mineure-Faits",
            "Faits",
            "Examen des faits",
        ]
        for key in ALTERNATIVES_MINEURES_KEY:
            if key in answers_block:
                fait = answers_block[key]
                if isinstance(fait, list):
                    return fait
                elif isinstance(fait, dict):
                    return [value for value in fait.values()]
                else:
                    return [fait]
        return []

    def get_mineure_subsommation_ans(self, answers_block):
        """Return the list of answers from the Subsommation section."""
        ALTERNATIVES_MINEURES_SUBSOMPTION_KEYS = [
            "Mineure-Subsommation",
            "Subsommation",
            "Mineure-Subsomption",
            "Subsomption",
            "Analyse juridique (subsomption)",
        ]
        for key in ALTERNATIVES_MINEURES_SUBSOMPTION_KEYS:
            if key in answers_block:
                subsomption = answers_block[key]
                if isinstance(subsomption, list):
                    return subsomption
                elif isinstance(subsomption, dict):
                    return [value for value in subsomption.values()]
                else:
                    return [subsomption]
        return []

    def get_conclusion_ans(self, answers_block):
        """Return the list of answers from the Conclusion section."""
        ALTERNATIVES_CONCLUSION_KEYS = [
            "Conclusion",
            "Décision finale",
        ]
        for key in ALTERNATIVES_CONCLUSION_KEYS:
            if key in answers_block:
                conclusion = answers_block[key]
                return (
                    conclusion
                    if isinstance(conclusion, list)
                    else [conclusion]
                )
        return []

    def count_valid_rags(self, documents_rags):
        """Count valid rag answers to display."""
        counter = 0
        for rag in documents_rags:
            try:
                answers_block = json.loads(rag.answer)
            except:
                continue
            if (
                self.get_mineures_faits_answers(answers_block)
                or self.get_mineure_subsommation_ans(answers_block)
                or self.get_conclusion_ans(answers_block)
            ):
                counter += 1
        return counter

    def valid_rags(self, documents_rags):
        """Return valid document rags."""
        valid_rags = []
        for rag in documents_rags:
            try:
                answers_block = json.loads(rag.answer)
            except:
                continue
            if (
                self.get_mineures_faits_answers(answers_block)
                or self.get_mineure_subsommation_ans(answers_block)
                or self.get_conclusion_ans(answers_block)
            ):
                valid_rags.append(rag)

        return valid_rags

    def get_prompt_summary(
        self,
        question: str,
        subsommation_dict: dict[str | int, str],
        majeures_dict: dict[str | int, str],
    ):
        """
        Return a prompt to create general summary and summary tables.

        Create a general summary from subsommation sections answers,
        create a table with key_elements from the cases and another table with
        key article law from majueres sections.
        """
        text = ""
        majeures_text = ""
        for doc_id, resp in subsommation_dict.items():
            text += f"[{doc_id}]:\n{resp}\n\n"

        for doc_id, content in majeures_dict.items():
            majeures_text += f"[{doc_id}]:\n{content}\n\n"

        return (
            f"Question: {question}\n\n"
            f"Réponses des experts:\n{text}\n"
            f"Contexte supplémentaire (Majeure) par document:\n{majeures_text}\n ---\n\n"
            "Instructions :\n"
            "- Utilise UNIQUEMENT les réponses ci-dessus ET les phrases majeures associées à chaque document ci-dessus.\n"
            "- Pour chaque élément produit dans 'key_elements' et 'law_articles', la clé 'references' doit être une LISTE des doc_id utilisés, choisis uniquement parmi ceux présents dans les réponses ou la majeure ci-dessus. Même s'il n'y a qu'un seul doc_id, la liste doit contenir un élément.\n"
            "- Pour les 'law_articles', prends en compte à la fois la réponse et la majeure liée au doc_id.\n"
            "- Réponds strictement au format suivant :\n"
            "{\n"
            '  "summary": "Résumé synthétique en un paragraphe répondant à la question. Pas d\'exemple.",\n'
            '  "key_elements": [\n'
            "     {\n"
            '       "element": "Nom de l\'élément clé",\n'
            '       "description": "Description de l\'élément en relation avec la question",\n'
            '       "references": [1,3,5]    // Liste (array) de doc_id UNIQUEMENT issus des réponses/majeure ci-dessus\n'
            "     }, ...\n"
            "   ],\n"
            '  "law_articles": [\n'
            "     {\n"
            '       "article": "Numéro ou titre d\'article",\n'
            '       "content": "Contenu pertinent résumé ou extrait, basé sur la question, les réponses et la majeure du ou des doc_id référencés.",\n'
            '       "references": [2,4]    // Liste (array) de doc_id UNIQUEMENT issus des réponses/majeure ci-dessus\n'
            "     }, ...\n"
            "   ]\n"
            "}\n"
            "\nIMPORTANT :\n"
            "- Donne uniquement l'objet JSON, sans rien avant ni après.\n"
            "- Les champs 'references' sont TOUJOURS une liste, même avec un seul élément.\n"
            "- Utilise seulement les doc_id explicitement présentés ci-dessus dans les réponses ou la majeure comme références.\n"
            "- Toutes les réponses doivent être rédigées en français.\n"
        )

    def create_table_summary(
        self,
        question: str,
        subsommation_dict: dict[str | int, str],
        majeures_dict: dict[str | int, str],
    ) -> str:
        """Return a json with a general summary and summary table."""
        prompt = self.get_prompt_summary(
            question, subsommation_dict, majeures_dict
        )

        try:
            resp = openai_client.chat.completions.create(
                model=MODEL_CHAT,
                messages=[
                    {
                        "role": "system",
                        "content": "Expert juridique specialise en synthese jurisprudentielle.",
                    },
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            summary = resp.choices[0].message.content.strip()
            logging.info("[OK] Summary generated")

        except Exception as e:
            logging.info(f"[ERROR] {e}")
            summary = "[ERROR]"

        return summary

    def get_and_save_answers_from_documents(self, max_doc_ans=None):
        """
        Save answers from openai in database.

        Get answers from documents given a query,
        Get a summary from all subsommation section answers
        and summary tables showing key elements and key articles law.
        """
        self.project_rag.status = "questioning_documents"
        self.project_rag.save()
        question = self.project_rag.query

        documents = Document.objects.filter(
            id__in=self.documents_ids
        ).order_by("id")
        if max_doc_ans:
            documents = sort_documents_by_es_score(
                self.project_rag.project, documents
            )[:max_doc_ans]
            self.project_rag.num_documents = max_doc_ans
        else:
            documents = list(documents)
            self.project_rag.num_documents = len(self.documents_ids)

        self.project_rag.save()

        payloads = [
            {"id": d.id, "record_key": d.record_key} for d in documents
        ]

        embedded_query = (
            openai_client.embeddings.create(
                model=EMBEDDING_MODEL, input=[question]
            )
            .data[0]
            .embedding
        )

        collection = chroma_client.get_collection(name=self.chambre_name)

        with joblib.parallel_backend("threading", n_jobs=MAX_WORKERS_RAG):
            results = Parallel()(
                delayed(get_answer_document_worker)(
                    pl, question, embedded_query, collection
                )
                for pl in payloads
            )

        for doc_id, block_section, answer in results:
            ProjectDocumentRAG.objects.create(
                project_rag=self.project_rag,
                document_id=doc_id,  # or document=Document.objects.get(id=doc_id)
                citation_context=sanitize_replace(block_section),
                answer=flatten_and_sanitize(answer),
            )
            # Update de counter safely
            ProjectRAG.objects.filter(pk=self.project_rag.pk).update(
                valid_answer_count=F("valid_answer_count") + 1
            )

        # Implement answers for missing
        documents_rags = ProjectDocumentRAG.objects.filter(
            project_rag=self.project_rag
        )

        self.project_rag.valid_answer_count = self.count_valid_rags(
            documents_rags
        )
        self.project_rag.save(update_fields=["valid_answer_count"])

        # Generating a general answer summary
        self.project_rag.status = "generating_summary"
        self.project_rag.save(update_fields=["status"])

        subsommation_dict = {}
        majueres_dict = {}

        for doc_rag in self.valid_rags(documents_rags):
            answer_block = json.loads(doc_rag.answer)
            subsomption_doc_ans = self.get_mineure_subsommation_ans(
                answer_block
            )
            subsommation_dict[doc_rag.document.id] = "\n".join(
                subsomption_doc_ans
            )
            majueres_dict[doc_rag.document.id] = "\n".join(
                doc_rag.citation_context.get("Majeure", [])
            )

        # Résultats obtenus à partir des documents.
        summary_dict_str = self.create_table_summary(
            self.project_rag.query, subsommation_dict, majueres_dict
        )

        try:
            _ = json.loads(summary_dict_str)
            self.project_rag.summary_answer = summary_dict_str
            self.project_rag.save()
        except:
            empty_summary = {
                "summary": "Error getting answer from openai",
                "key_elements": [],
                "law_articles": [],
            }
            self.project_rag.summary_answer = json.dumps(empty_summary)
            self.project_rag.save()

        self.project_rag.status = "completed"
        self.project_rag.save()
