import json
import logging
import time

import joblib

from django.conf import settings
from django.core.management.base import BaseCommand
from joblib import Parallel, delayed

from literev.libs.collectors import ElasticSearchCollector

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

CACHE_DIR = settings.LITEREV_CACHE_DIR

RAW_DOCUMENTS_INPUT_DIR = CACHE_DIR / "structured_data_documents" / "input"
RAW_DOCUMENTS_INPUT_DIR.mkdir(parents=True, exist_ok=True)

CHAMBER_NAMES = [
    "chambre_administrative",
    "chambre_penale",
    "chambre_civile",
]

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def custom_log(message):
    """Write message in a file log."""
    with open(CACHE_DIR / "prepare_input_log.txt", "a") as f:
        f.write(message)


def get_filename_input(record_key: str, index_name: str) -> str:
    """Return a composed name."""
    return f"{record_key}__{index_name}.json"


def save_document_input(document: str, index_name: str):
    """
    Save raw document content.

    Uses documents retrieved from Elastic Search and saves the results as json
    file with its record_key (equivalent to cle fiches).
    """
    record_key = getattr(document, "record_key", "")
    document_text = getattr(document, "document_text", "")
    decision_type = getattr(document, "decision_type", "")
    chamber = getattr(document, "chamber", "")

    if not record_key:
        logging.info("There is no recdord key")
        procedure_type = getattr(document, "procedure_type", "")
        logging.info(
            f"procedure_type: {procedure_type}, decision type: {decision_type}"
        )
        return

    try:
        # check if the doc has been processed
        document_filename = get_filename_input(record_key, index_name)
        document_path = RAW_DOCUMENTS_INPUT_DIR / document_filename

        if document_path.is_file():
            logging.info(
                f"skipping doc_id: {record_key} with decision type:{decision_type} in chamber {chamber} because is cached"
            )
            custom_log(
                f"\nskipping doc_id: {record_key} with decision type:{decision_type} in chamber {chamber} because is cached"
            )
            return

        output = {
            "record_key": record_key,
            "raw_document_text": document_text,
        }

        with open(document_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logging.error(f"An error has ocurred {e}")
        logging.info(
            f"document failed to extract mineur and majeur {record_key}"
        )
        custom_log(
            f"\nAn error has ocurred {e} \ndocument failed to extract mineur and majeur {record_key}"
        )


class Command(BaseCommand):
    help = "Extract mineur and majeur from documents and saves it into a json file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--index-name",
            type=str,
            required=True,
            help="The name of the legal chamber",
        )
        parser.add_argument(
            "--max-workers",
            type=str,
            required=False,
            help="How many threads should work in parallel.",
            default=2,
        )

    def handle(
        self, *args, **options
    ) -> None:  # removed *args: Any, **options: Any because linter
        index_name = options["index_name"]

        start_time = time.time()

        if index_name == "test":
            max_workers = int(options["max_workers"])
            index_name = "chambre_administrative"
            collector = ElasticSearchCollector(index_name=index_name)
            documents = collector.collect_all_documents()
            documents = documents[:10]

            logging.info(f"Document to process {len(documents)}")
            custom_log(f"\n---------------- Logs for {index_name}")
            custom_log(f"Document to process {len(documents)}")

        else:
            if index_name not in CHAMBER_NAMES:
                logging.error(
                    f"index_name must be one of the following: {CHAMBER_NAMES}"
                )
                raise

            max_workers = int(options["max_workers"])

            collector = ElasticSearchCollector(index_name=index_name)
            documents = collector.collect_all_documents()
            logging.info(f"Document to process {len(documents)}")
            custom_log(f"\n---------------- Logs for {index_name}")
            custom_log(f"Document to process {len(documents)}")

        try:
            if not documents:
                logging.error("No documents to proccess.")
                raise

            with joblib.parallel_backend("threading", n_jobs=max_workers):
                Parallel()(
                    [
                        delayed(save_document_input)(document, index_name)
                        for document in documents
                    ]
                )

        except Exception as e:
            logging.error(f"Prepare input failed {e}")

        end_time = time.time()

        total_time = (end_time - start_time) / 60

        logging.info(f"Elapsed time {total_time} min")
        custom_log(f"\nElapsed time {total_time} min")
