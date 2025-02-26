"""RAG workflow."""

from __future__ import annotations

import logging
import traceback as tb

from functools import wraps
from pathlib import Path
from typing import Callable, cast

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from rago import Rago
from rago.augmented import OpenAIAug
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from rago.retrieval import StringRet

from literev.libs.scoring import sort_documents_by_es_score
from literev.models import Document, ProjectDocumentRAG, ProjectRAG

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
    """Run RAG on documents."""

    template_prompt = (
        "Based on the given context, answer to this question: `{query}`. "
        "If no information is available in the context, "
        "return `Réponse non disponible`, "
        "otherwise, give your answer in only one sentence in french with"
        "the most relevant information. Context: `{context}`.\n"
        "Also return an extract of the context, approximately 5 sentences, "
        "from where in the context the answer was generated as a highlight."
    )

    def __init__(self, project_rag_id: int, document_ids: list[int]) -> None:
        """Initialize the processor with project RAG ID and document IDs."""
        self.project_rag = ProjectRAG.objects.get(id=project_rag_id)
        self.project_rag.status = "in-progress"
        self.project_rag.save()
        self.document_ids = document_ids

    @ret_cache
    def split_text_into_chunks(self, text: str) -> list[str]:
        """Split text into smaller chunks for processing."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        return text_splitter.split_text(text)

    def run(self, max_doc_ans: int | None = None) -> None:
        """Process a query with RAG on relevant chunks and store results in ProjectDocumentRAG."""
        logger.info("Starting RAG processing for each document.")
        self.status = "in-progress"

        documents = Document.objects.filter(id__in=self.document_ids)

        counter = 0
        if max_doc_ans:
            documents = sort_documents_by_es_score(
                self.project_rag.project, documents
            )

        for document in documents:
            try:
                content = document.raw_document_text
                chunks = self.split_text_into_chunks(content)

                if not chunks:
                    logger.warning(
                        f"No content chunks available for document: {document.id}"
                    )
                    ProjectDocumentRAG.objects.create(
                        project_rag=self.project_rag,
                        document=document,
                        citation="No content available.",
                        answer="No content available.",
                    )
                    continue

                augmented = OpenAIAug(
                    api_key=settings.OPENAI_API_KEY,
                    top_k=5,
                    model_name="text-embedding-ada-002",
                    cache=AUG_CACHE,
                )

                generation = OpenAIGen(
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
                )

                rag = Rago(
                    retrieval=StringRet(chunks),
                    augmented=augmented,
                    generation=generation,
                )
                result = rag.prompt(self.project_rag.query)
                answer = result.answer.strip()
                highlight = result.highlight.strip()

                ProjectDocumentRAG.objects.create(
                    project_rag=self.project_rag,
                    document=document,
                    citation=highlight,
                    answer=answer,
                )

                if "réponse non disponible" not in answer.lower():
                    counter += 1

                if max_doc_ans and counter >= max_doc_ans:
                    break

            except Exception as e:
                logger.error(
                    f"Error generating response for document '{document.id}': {e}\n"
                    f"{tb.format_exc()}"
                )
                rag_project_document, _ = (
                    ProjectDocumentRAG.objects.get_or_create(
                        project_rag=self.project_rag,
                        document=document,
                    )
                )
                rag_project_document.citation = "Error generating response."
                rag_project_document.answer = "Error generating response."
                rag_project_document.from_full_text = (
                    False  # Ensure a non-null default value
                )
                rag_project_document.save()

        self.project_rag.status = "completed"
        self.project_rag.save()
