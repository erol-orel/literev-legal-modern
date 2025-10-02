import concurrent.futures
import logging
import time

from datetime import datetime
from pathlib import Path
from typing import Any, Tuple

import tiktoken

from django.conf import settings
from django.core.management.base import BaseCommand
from pydantic import BaseModel, Field
from rago.extensions.cache import CacheFile
from rago.generation import OpenAIGen
from tqdm.auto import tqdm  # progress bar

from literev.libs.collectors import ElasticSearchCollector
from literev.libs.parsing import extract_after_endroit
from literev.libs.rag_classes import HactarGen

CHAMBERS_NAME = ["penal_court", "civil_court", "administrative_court"]

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

#! THE SAME EMBEDDING MODEL NEEDS TO BE USED ACROSS LITEREV
EMBEDDING_MODEL = (
    "mxbai-embed-large:latest"  # "nomic-embed-text" #suggested model
)

MAX_WORKERS = 2
TMP_DIR = Path("/tmp") / "rago"
TMP_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = CacheFile(target_dir=TMP_DIR / "documents")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

ENGINE = "openai"  # change to hactar

MODEL_CFG = {
    "openai": {
        "provider": "openai",
        "chat": "gpt-4o-mini",
        "embed": "text-embedding-ada-002",
    },
    "hactar-mistral": {
        "provider": "hactar",
        "chat": "mistral-small3.1:24b",
        "embed": "mxbai-embed-large:latest",
    },
}


class MinorMajorPair(BaseModel):
    Majeure: list[str] = Field()
    Mineure: list[str] = Field()


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def get_rag_generator(engine: str = "openai"):
    if engine not in MODEL_CFG:
        raise ValueError(f"Unknown engine: {engine}")

    text_classification_system_prompt = (
        "Tu es un expert en droit. Je te donne un texte de jurisprudence et les définitions suivantes :\n\n"
        "Majeure : C'est la règle de droit applicable au cas d'espèce. Elle peut être une loi, un règlement, un contrat, ou même une jurisprudence. "
        "La majeure énonce une règle générale et abstraite.\n"
        "Mineure : C'est la description des faits pertinents de l'affaire. Il s'agit de qualifier les faits de l'espèce et de les faire rentrer dans une catégorie juridique définie. "
        "C'est également le résultat de l'application de la règle de droit aux faits.\n\n"
        "Ta tâche :\n"
        "- Découpe le texte en segments de phrases si nécessaire.\n"
        "- Si une phrase contient à la fois des éléments de majeure et de mineure, sépare-la en segments distincts pour que chaque segment corresponde uniquement à l'une ou l'autre catégorie.\n"
        "- Ne modifie jamais le texte original : conserve les formulations exactes.\n"
        "- Pour chaque segment, indique clairement s’il relève de la majeure ou de la mineure.\n"  # noqa: RUF001
    )

    text_classification_user_prompt = 'Texte: "{context}"\n\n{query}\n'
    cfg = MODEL_CFG[engine]
    generator: HactarGen | OpenAIGen

    if cfg["provider"] == "hactar":
        generator = HactarGen(
            api_key=settings.HACTAR_API_KEY,
            model_name=cfg["chat"],
            system_message=text_classification_system_prompt,
            prompt_template=text_classification_user_prompt,
            temperature=0.0,
            output_max_length=16384,
            api_params={
                "top_p": 0.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
            },
            structured_output=MinorMajorPair,
        )

    else:
        generator = OpenAIGen(
            api_key=settings.OPENAI_API_KEY,
            model_name=cfg["chat"],
            system_message=text_classification_system_prompt,
            prompt_template=text_classification_user_prompt,
            temperature=0.0,
            output_max_length=16384,
            api_params={
                "top_p": 0.0,
                "frequency_penalty": 0.0,
                "presence_penalty": 0.0,
            },
            structured_output=MinorMajorPair,
        )

    return generator


def get_majeur_mineur_chunks(
    content_after_endroit: str,
) -> tuple[list[str], list[str]]:
    rag = (
        get_rag_generator()
    )  # set engine="hactar' in the imput to user hactar-mistral
    query = "Retourne un fichier JSON pur avec les deux listes 'mineures' et 'majeures' comme décrit ci-dessus."

    response = rag.generate(query=query, context=[content_after_endroit])
    if isinstance(response, MinorMajorPair):
        return response.Majeure, response.Mineure
    else:
        logging.warning(
            f"Error generating chunks for document content: {content_after_endroit}"
        )
        return [], []


def save_mineur_majeur_chunks(majeur_list, mineur_list, key, doc_id):
    aggregated = {
        "doc_id": doc_id,
        "Majeures": majeur_list,
        "Mineures": mineur_list,
    }

    CACHE_FILE.save(key, aggregated)
    logging.info(key)


def _log_results(
    duration: float,
    total_docs: int,
    successful: int,
    failed_docs_info: list,
    chunks: int,
    tokens: int,
) -> None:
    logging.info("-" * 50)
    logging.info(f"Processing finished in {duration:.2f} seconds.")
    logging.info(f"Total documents processed: {total_docs}")
    logging.info(f"Successfully embedded: {successful}")
    logging.info(f"Failed to process: {len(failed_docs_info)}")
    logging.info(f"Total chunks generated: {chunks}")
    logging.info(f"Total tokens estimated: {tokens}")

    if failed_docs_info:
        logging.warning("--- Failed Document Details ---")
        for doc_id, error in failed_docs_info:
            logging.warning(f"  - Document {doc_id}: {error}")
        logging.warning("-" * 50)


def process_document_worker(
    doc: Any, engine: str
) -> Tuple[str, bool, str, int, int]:
    """
    Worker function to process a single document in a separate thread.

    Args:
        doc: The document object (assuming it has doc_id and document_text attributes).
        embedder_instance: The shared instance of HactarAug.

    Returns:
        A tuple containing:
        (doc_id, success_status, message, num_chunks, num_tokens)
    """
    doc_id = getattr(doc, "doc_id", "unknown_id")

    try:
        # Removing escape characters
        key = f"classified_doc_{engine}_{doc_id}"

        if CACHE_FILE.load(key):
            logging.info(f"skipping doc_id: {doc_id} because is cached")
            return (
                doc_id,
                True,
                "Successfully processed",
                0,
                0,
            )

        clear_document_text = (
            doc.document_text.replace("\xa0", " ")
            .replace("\u202f", " ")
            .strip()
        )
        content_after_endroit = extract_after_endroit(clear_document_text)

        if not content_after_endroit:
            logging.warning(f"Document {doc_id} no text to chunk")
            return doc_id, True, "Processed (no chunks)", 0, 0

        majeur_chunks, mineur_chunks = get_majeur_mineur_chunks(
            content_after_endroit
        )

        num_tokens = count_tokens("".join(majeur_chunks + mineur_chunks))

        if not majeur_chunks or not mineur_chunks:
            logging.info(
                f"emtpy chunks lists detected for document_id: {doc_id} Majeur:{majeur_chunks}, Mineur:{mineur_chunks}"
            )
        save_mineur_majeur_chunks(majeur_chunks, mineur_chunks, key, doc_id)

        return (
            doc_id,
            True,
            "Successfully processed",
            len(majeur_chunks + mineur_chunks),
            num_tokens,
        )

    except Exception as e:
        logging.error(
            f"Error processing document {doc_id} in worker thread: {e}",
            exc_info=True,
        )
        return doc_id, False, str(e), 0, 0


def _handle_future(
    future, original_doc_id: str, failed_docs_info: list[tuple[str, str]], pbar
) -> tuple[str, bool, int, int]:
    try:
        doc_id, success, message, num_chunks, num_tokens = future.result()
        if not success:
            failed_docs_info.append((doc_id, message))

        pbar.update(1)
        pbar.set_postfix(
            {
                "Failed": len(failed_docs_info),
                "Last ID": doc_id,
                "Status": "OK" if success else "ERR",
            },
            refresh=True,
        )

        return doc_id, success, num_chunks, num_tokens

    except Exception as exc:
        logging.error(
            f"Error retrieving result for document ID {original_doc_id}: {exc}",
            exc_info=True,
        )
        failed_docs_info.append((original_doc_id, str(exc)))
        pbar.update(1)
        pbar.set_postfix(
            {
                "Failed": len(failed_docs_info),
                "Last ID": original_doc_id,
                "Status": "ERR",
            },
            refresh=True,
        )
        return original_doc_id, False, 0, 0


def _process_documents_with_threadpool(
    documents: list, engine: str, max_workers=MAX_WORKERS
) -> tuple[int, int, int, list[tuple[str, str]]]:
    failed_docs_info: list[tuple[str, str]] = []
    successful_docs_count = 0
    total_chunks_processed = 0
    total_tokens_processed = 0

    with tqdm(
        total=len(documents),
        desc="Embedding documents",
        ncols=120,
        leave=False,
        position=0,
        dynamic_ncols=False,
    ) as pbar:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers
        ) as executor:
            futures = {
                executor.submit(process_document_worker, doc, engine): getattr(
                    doc, "doc_id", f"unknown_{i}"
                )
                for i, doc in enumerate(documents)
            }
            for future in concurrent.futures.as_completed(futures):
                _, success, chunks, tokens = _handle_future(
                    future, futures[future], failed_docs_info, pbar
                )
                if success:
                    successful_docs_count += 1
                    total_chunks_processed += chunks
                    total_tokens_processed += tokens

    return (
        successful_docs_count,
        total_chunks_processed,
        total_tokens_processed,
        failed_docs_info,
    )


class Command(BaseCommand):
    help = "Extract mineur and majeur chunks for given corpus"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-workers",
            type=str,
            required=False,
            help="How many threads should work in parallel.",
            default=2,
        )

    def handle(self, *args, **options):
        index_name = options.get("index_name", "administrative_court")
        engine = ENGINE
        if index_name not in CHAMBERS_NAME:
            logging.error(
                f"index_name must be one of the following : {CHAMBERS_NAME!s}"
            )
            raise

        MAX_WORKERS = int(options["max_workers"])

        if MAX_WORKERS > 8:
            logging.error("Please provide a smaller max-workers value")
            raise

        collector = ElasticSearchCollector(index_name=index_name)

        try:
            logging.info(
                f"Collecting all documents from corpus: {collector.index_name} ..."
            )
            start_date = datetime(2023, 12, 1)
            end_date = datetime(2024, 12, 31)

            search_query = "police AND fils"

            # TODO: Update index name to "administrative_court"
            collector = ElasticSearchCollector(index_name=index_name)

            documents = collector.collect_documents(
                search_query, start_date, end_date
            )

            logging.info(f"Total documents to process: {len(documents)}")

            if not documents:
                logging.info("No documents found to process.")
                return

            start_time = time.time()
            results = _process_documents_with_threadpool(
                documents, engine, MAX_WORKERS
            )
            duration = time.time() - start_time

            (
                successful_count,
                chunks_processed,
                tokens_processed,
                failed_docs,
            ) = results
            _log_results(
                duration,
                len(documents),
                successful_count,
                failed_docs,
                chunks_processed,
                tokens_processed,
            )

        except Exception as e:
            logging.error(
                f"An critical error occurred during the process: {e}",
                exc_info=True,
            )
            raise
