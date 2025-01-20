"""RAG workflow."""

from __future__ import annotations

import logging
import traceback as tb

from functools import wraps
from pathlib import Path
from typing import Callable, cast

from django.conf import settings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from rago import Rago
from rago.augmented import SpaCyAug
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from rago.retrieval import StringRet

from literev.models import Document, ProjectDocumentRAG, ProjectRAG

TMP_DIR = Path("/tmp") / "rago"

RET_CACHE = CacheFile(target_dir=TMP_DIR / "ret")
AUG_CACHE = CacheFile(target_dir=TMP_DIR / "aug")
GEN_CACHE = CacheFile(target_dir=TMP_DIR / "gen")

# from workflow.libs.pdf import PDFHandler
# TODO:update for contenttext instead fo pdf document
logging.basicConfig(level=settings.LOGGING_LEVEL)
logger = logging.getLogger(__name__)


@wraps
def ret_cache(func: Callable[str, list[str]]) -> Callable[str, list[str]]:
    cache = CacheFile(target_dir=RET_CACHE)

    def wrapper(text: str) -> list[str]:
        cached = cache.load(text)
        if cached is not None:
            return cast(list[str], cached)
        result = func(text)
        cache.save(text, result)

    return wrapper


class PDFRAG:
    def __init__(self, project_rag_id: int, document_ids: list[int]) -> None:
        """Initialize the processor with project RAG ID and document IDs."""
        self.project_rag = ProjectRAG.objects.get(id=project_rag_id)
        self.project_rag.status = "in-progress"
        self.project_rag.save()
        self.document_ids = document_ids
        # self.pdf_handler = PDFHandler()

    @ret_cache
    def split_text_into_chunks(self, text: str) -> list[str]:
        """Split text into smaller chunks for processing."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        return text_splitter.split_text(text)

    def run(self) -> None:
        """Process a query with RAG on relevant chunks and store results in ProjectDocumentRAG."""
        logger.info("Starting RAG processing for each document.")
        self.status = "in-progress"

        documents = Document.objects.filter(id__in=self.document_ids)

        template_prompt = (
            "Vous êtes un assistant de réponse aux questions."
            "Utilisez le contexte suivant pour répondre à la "
            "question posée avec précision et concision."
            "Pour les questions fermées (oui/non), répondez avec un seul mot, "
            "par exemple `Oui` ou `Non`."
            "Pour les questions ouvertes, répondez par une seule phrase "
            "concise expliquant la réponse. Si vous ne connaissez pas la "
            "réponse ou si elle n'est pas dans le contexte fourni, "
            "dites simplement `Réponse non disponible`."
            "\nQuestion: ```{query}```\nContexte: ```{context}```"
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

                augmented = SpaCyAug(
                    top_k=5, model_name="fr_core_news_lg", cache=AUG_CACHE
                )

                generation = OpenAIGen(
                    api_key=settings.OPENAI_API_KEY,
                    model_name="gpt-4o-mini",
                    prompt_template=template_prompt,
                    temperature=0,
                    cache=GEN_CACHE,
                )

                rag = Rago(
                    retrieval=StringRet(chunks),
                    augmented=augmented,
                    generation=generation,
                )
                result = rag.prompt(self.project_rag.query)

                citation: list[str] = rag.logs.get("augmented", {}).get(
                    "result", []
                )

                ProjectDocumentRAG.objects.create(
                    project_rag=self.project_rag,
                    document=document,
                    citation=citation[0] if citation else "",
                    answer=result.strip(),
                )

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
