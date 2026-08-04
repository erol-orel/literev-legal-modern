import json
import logging
import time

from typing import Any

import joblib

from chromadb import PersistentClient
from django.conf import settings
from django.core.management.base import BaseCommand
from joblib import Parallel, delayed
from openai import OpenAI

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

CACHE_DIR = settings.LITEREV_CACHE_DIR

CACHE_STRUCTURED_DOCUMENTS = CACHE_DIR / "structured_data_documents"
CACHE_STRUCTURED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

CHAMBER_NAMES = [
    "chambre_administrative",
    "chambre_penale",
    "chambre_civile",
    "test",
]

OPENAI_API_KEY = settings.OPENAI_API_KEY
EMBEDDING_MODEL = "text-embedding-3-large"
CHAT_MODEL = "gpt-4.1-mini"

CHROMA_DIR = CACHE_DIR / "chroma_db"

ENGINE = "openai"
EMBED_BATCH = 128  # number of texts per embedding request
UPSERT_BATCH = 200  # number of docs per upsert to Chroma


# Built lazily: the openai SDK raises when constructed without an API key, so
# eager construction made importing this module require OPENAI_API_KEY.
_openai_client: OpenAI | None = None


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


chroma = PersistentClient(
    path=CHROMA_DIR,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def custom_log(message):
    with open(CACHE_DIR / "embedding_logs.txt", "a") as f:
        f.write(message)


def prepare_docs_from_item(document, decision_type):
    """
    Prepare docs from item.

    Prepare document to do the embeddings.
    Prepares unique id, metadata containing:
    decition_type, record_key, section, position, and raw sentence.
    """
    docs: list[str] = []
    embedded_ids: list[str | int] = []
    metas: list[dict[str, Any]] = []
    record_key = document["record_key"]

    if not record_key:
        return docs, embedded_ids, metas

    for section, sentence_list in document["structured_sentences"].items():
        for idx, raw in enumerate(sentence_list):
            text = (raw or "").strip()
            if not text:
                continue
            embedded_sentence_doc_id = f"{record_key}|{section}|{idx}"
            embedded_ids.append(embedded_sentence_doc_id)
            docs.append(text)
            metas.append(
                {
                    "decision_type": decision_type,
                    "record_key": record_key,
                    "section": section,
                    "position": idx,
                }
            )

    return docs, embedded_ids, metas


def existing_ids_in_collection(
    collection, candidate_ids: list[str]
) -> set[str]:
    """
    Check if ids are already present in the chroma db.

    It returns the found ids.
    """
    found: set[str] = set()
    BATCH = 1000
    for i in range(0, len(candidate_ids), BATCH):
        batch = candidate_ids[i : i + BATCH]
        res = collection.get(ids=batch, include=["metadatas"])
        for _id in res.get("ids", []):
            found.add(_id)
    return found


def embed_batch_request(texts_batch: list[str]):
    """
    Embed one batch of texts with retries and backoff.

    Run inside worker threads (create client per thread).
    """
    try:
        resp = _get_openai_client().embeddings.create(
            model=EMBEDDING_MODEL, input=texts_batch
        )
        return [d.embedding for d in resp.data]

    except Exception as e:
        logging.info(f"Error trying to embedd {e}")
        raise


def embed_texts_parallel(
    texts: list[str],
    max_workers: int,
    batch_size: int = EMBED_BATCH,
) -> list[list[float]]:
    """
    Embed texts in parallel.

    Split texts into batches, embed batches in parallel (threading backend),
    and return embeddings aligned to the input order.
    """
    # Build batches (start_idx, end_idx)
    indices = []
    for i in range(0, len(texts), batch_size):
        indices.append((i, min(i + batch_size, len(texts))))

    # Run parallel embedding for each batch
    with joblib.parallel_backend("threading", n_jobs=max_workers):
        batch_results = Parallel(prefer="threads")(
            delayed(embed_batch_request)(texts[s:e]) for (s, e) in indices
        )

    # Flatten back to the original order
    embs: list[list[float]] = [None] * len(texts)  # type: ignore
    for (s, e), emb_list in zip(indices, batch_results):
        for off, emb in enumerate(emb_list):
            embs[s + off] = emb

    return embs


def upsert_document_chunks(document_path, collection, max_workers):
    """
    Upsert Cocument chunks.

    Save the embedded version of document (from document_path) into chroma db.
    """
    with open(document_path, "r", encoding="utf-8") as f:
        document = json.load(f)

    _, decision_type, __ = document_path.name.split("__")

    decision_type = decision_type.replace("_", "/")

    docs, ids, metas = prepare_docs_from_item(document, decision_type)

    # Skip already indexed chunks
    found = existing_ids_in_collection(collection, ids)
    if len(found) == len(ids):
        logging.info(
            f"Document {document['record_key']} decision type: {decision_type} already fully indexed; skipping."
        )
        custom_log(
            f"\nDocument: {document['record_key']} decision type: {decision_type} is already indexed"
        )
        return

    missing_docs, missing_ids, missing_metas = [], [], []

    for d, i, m in zip(docs, ids, metas):
        if i not in found:
            missing_docs.append(d)
            missing_ids.append(i)
            missing_metas.append(m)

    logging.info(
        f"Embedding {len(missing_docs)} docs for item {document['record_key']}"
    )

    embs = embed_texts_parallel(texts=missing_docs, max_workers=max_workers)

    # Upsert to Chroma (single-threaded, batched)
    for i in range(0, len(missing_ids), UPSERT_BATCH):
        collection.upsert(
            ids=missing_ids[i : i + UPSERT_BATCH],
            documents=missing_docs[i : i + UPSERT_BATCH],
            metadatas=missing_metas[i : i + UPSERT_BATCH],
            embeddings=embs[i : i + UPSERT_BATCH],
        )

    logging.info(
        f"Upserted {len(embs)} sentences for document record key ={document['record_key']}, decision type: {decision_type}"
    )


class Command(BaseCommand):
    help = "Loads documents to embedd into chromadb."

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
            default=2,
        )

    def handle(self, *args, **options):
        index_name = options["index_name"]
        max_workers = int(options["max_workers"])

        start_time = time.time()

        collection = chroma.get_or_create_collection(name=index_name)

        documents_paths = list(
            CACHE_STRUCTURED_DOCUMENTS.glob(f"*{index_name}_structured.json")
        )

        logging.info(f"Documents to embbed {len(documents_paths)}")

        for document_path in documents_paths:
            try:
                upsert_document_chunks(document_path, collection, max_workers)
            except Exception as e:
                logging.error(
                    f"An critical error occurred during the process: {e}",
                    exc_info=True,
                )
                custom_log(
                    f"\nAn critical error occurred during the process: {e}"
                )
                custom_log(f"\ndocument: {document_path}")

        end_time = time.time()

        logging.info(f"Total time elapsed {(end_time - start_time) / 60} min")
        custom_log(f"\nTotal time elapsed {(end_time - start_time) / 60} min")
