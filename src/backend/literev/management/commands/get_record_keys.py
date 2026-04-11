# New command to extract mineur majeur

import logging
import time

from datetime import datetime

from chromadb import PersistentClient
from chromadb.config import Settings
from django.conf import settings
from django.core.management.base import BaseCommand

from literev.libs.collectors import ElasticSearchCollector

CACHE_DIR = settings.LITEREV_CACHE_DIR

CACHE_STRUCTURED_DOCUMENTS = CACHE_DIR / "structured_data_documents"
CACHE_STRUCTURED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

CHAMBER_NAMES = settings.LITEREV_CHAMBER_NAMES

CHROMA_DIR = CACHE_DIR / "chroma_db"

BATCH_SIZE = 1000


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

chroma = PersistentClient(
    path=CHROMA_DIR, settings=Settings(anonymized_telemetry=False)
)


def custom_log(message):
    with open(CACHE_DIR / "renaming_logs.txt", "a") as f:
        f.write(message)


class Command(BaseCommand):
    help = "Extract mineur and majeur from documents"

    def add_arguments(self, parser):
        parser.add_argument(
            "--index-name",
            type=str,
            required=True,
            help="The name of the legal chamber to generate embeddings for.",
        )

    def handle(
        self, *args, **options
    ) -> None:  # removed *args: Any, **options: Any because linter
        index_name = options["index_name"]

        start_time = time.time()

        if index_name == "test":
            start_date = datetime(2023, 6, 1)
            end_date = datetime(2023, 6, 10)

            search_query = "police AND fils"

            collector = ElasticSearchCollector(index_name="chambre_penale")

            es_documents = collector.collect_documents(
                search_query, start_date, end_date
            )
        else:
            if index_name not in CHAMBER_NAMES:
                logging.error(
                    f"index_name must be one of the following: {CHAMBER_NAMES}"
                )
                raise

            collector = ElasticSearchCollector(index_name=index_name)
            es_documents = collector.collect_all_documents()

        logging.info(f"Document to process {len(es_documents)}")
        custom_log(f"\n---------------- Logs for {index_name}")
        custom_log(f"\nDocument to process {len(es_documents)}")

        decision_records = {}

        for es_document in es_documents:
            decision_type = getattr(
                es_document, "decision_type", "there is no decision type"
            )
            decision_records[decision_type] = getattr(
                es_document, "record_key", "there is no record key"
            )

        logging.info(f"Number of decision records: {len(decision_records)}")
        custom_log(f"\nNumber of decision records: {len(decision_records)}")

        collection = chroma.get_or_create_collection(name=index_name)

        total = collection.count()

        for offset in range(0, total, BATCH_SIZE):
            batch = collection.get(
                offset=offset,
                limit=BATCH_SIZE,
                include=["embeddings", "documents", "metadatas"],
            )
            old_ids = batch["ids"]
            embeddings = batch.get("embeddings")
            documents = batch.get("documents")
            metadatas = batch.get("metadatas")

            new_ids = []
            new_metas = []
            for old_id, meta in zip(old_ids, metadatas):  # type: ignore
                # Parse old id
                try:
                    decision_type, section, idx = old_id.split("|", 3)
                    record_key = decision_records[decision_type]
                    new_id = f"{record_key}|{section}|{idx}"
                except Exception as e:
                    logging.info(
                        f"Unexpected error with id: {old_id} Error: {e}"
                    )
                    custom_log(
                        f"Unexpected error with id: {old_id} Error: {e}"
                    )
                    continue

                # Add/overwrite record_id in metadata
                new_meta = dict(meta or {})
                new_meta["record_key"] = record_key

                new_ids.append(new_id)
                new_metas.append(new_meta)

            try:
                # Upsert new records with the same embeddings/documents but new ids and metadatas
                collection.upsert(
                    ids=new_ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=new_metas,  # type: ignore
                )

                # After successful upsert, delete the old ids
                collection.delete(ids=old_ids)
            except Exception as e:
                logging.info(f"An error ocurred {e}")
                custom_log(f"An error ocurred {e}")
                continue

        end_time = time.time()

        total_time = (end_time - start_time) / 60

        logging.info(f"Elapsed time {total_time} min")
        custom_log(f"\nElapsed time {total_time} min")
