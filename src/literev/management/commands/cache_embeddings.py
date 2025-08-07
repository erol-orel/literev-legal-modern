import concurrent.futures
import logging
import time

from hashlib import sha256
from http.client import RemoteDisconnected
from typing import Any, Tuple

import backoff
import tiktoken

from django.conf import settings
from django.core.management.base import BaseCommand
from rago.augmented.base import EmbeddingType
from rago.extensions.cache import CacheFile
from requests.exceptions import ConnectionError, RequestException
from tqdm.auto import tqdm  # progress bar
from urllib3.exceptions import IncompleteRead

from literev.libs.collectors import ElasticSearchCollector
from literev.libs.rag_classes import HactarAug
from literev.libs.rag_pdf import prepare_chunks

CHAMBERS_NAME = ["penal_court", "civil_court", "administrative_court"]

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

#! THE SAME EMBEDDING MODEL NEEDS TO BE USED ACROSS LITEREV
EMBEDDING_MODEL = (
    "mxbai-embed-large:latest"  # "nomic-embed-text" #suggested model
)

MAX_WORKERS = 5
CACHE_DIR = settings.LITEREV_CACHE_DIR / "rago"
MODULE_NAME = "hactar"
AUG_CACHE = CacheFile(target_dir=CACHE_DIR / f"aug_{MODULE_NAME}")


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


@backoff.on_exception(
    backoff.expo,
    (RequestException, ConnectionError, RemoteDisconnected, IncompleteRead),
    max_tries=5,
    max_time=300,  # Maximum total time to try (5 minutes)
    jitter=None,
    logger=logging.getLogger(__name__),
)
def get_embeddings_with_retry(
    embedder: HactarAug, chunks: list[str]
) -> EmbeddingType:
    """Get embeddings with retry logic."""
    try:
        return embedder.get_embedding(chunks)

    except (RequestException, ConnectionError) as e:
        logging.warning(f"Network error during embedding: {e!s}")
        raise
    except (RemoteDisconnected, IncompleteRead) as e:
        logging.warning(f"Connection interrupted: {e!s}")
        raise
    except Exception as e:
        logging.error(
            f"Unexpected error during embedding: {e!s}", exc_info=True
        )
        raise


def process_document_worker(
    doc: Any, embedder_instance: HactarAug
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
        chunks = prepare_chunks(doc.document_text)

        if not chunks:
            logging.warning(f"Document {doc_id} resulted in zero chunks.")
            return doc_id, True, "Processed (no chunks)", 0, 0

        cache_key = sha256("".join(chunks).encode("utf-8")).hexdigest()
        if embedder_instance._get_cache(cache_key) is not None:
            return doc_id, True, "Already cached", len(chunks), 0

        num_tokens = count_tokens("".join(chunks))
        get_embeddings_with_retry(embedder_instance, chunks)
        return doc_id, True, "Successfully processed", len(chunks), num_tokens

    except Exception as e:
        logging.error(
            f"Error processing document {doc_id} in worker thread: {e}",
            exc_info=True,
        )
        return doc_id, False, str(e), 0, 0


def _process_documents_with_threadpool(
    documents: list, embedder: HactarAug, max_workers=MAX_WORKERS
) -> tuple:
    failed_docs_info = []
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
                executor.submit(
                    process_document_worker, doc, embedder
                ): getattr(doc, "doc_id", f"unknown_{i}")
                for i, doc in enumerate(documents)
            }
            for future in concurrent.futures.as_completed(futures):
                doc_id, success, chunks, tokens = _handle_future(
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


def _handle_future(
    future, original_doc_id: str, failed_docs_info: list, pbar
) -> tuple:
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


class Command(BaseCommand):
    help = "Generate and cache FAISS index for document embeddings"

    def add_arguments(self, parser):
        parser.add_argument(
            "--index-name",
            type=str,
            required=True,
            help="The name of the legal chamber to generate embeddings for.",
        )
        parser.add_argument(
            "--max-workers",
            type=str,
            required=False,
            help="How many threads should work in parallel.",
            default=5,
        )

    def handle(self, *args, **options):
        index_name = options["index_name"]
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
        embedder = HactarAug(
            api_key=settings.HACTAR_API_KEY,
            model_name=EMBEDDING_MODEL,
            top_k=5,
            cache=AUG_CACHE,
        )
        try:
            logging.info(
                f"Collecting all documents from corpus: {collector.index_name} ..."
            )
            documents = collector.collect_all_documents()
            logging.info(f"Total documents to process: {len(documents)}")

            if not documents:
                logging.info("No documents found to process.")
                return

            start_time = time.time()
            results = _process_documents_with_threadpool(
                documents, embedder, MAX_WORKERS
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
