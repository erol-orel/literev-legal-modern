import json
import logging
import time

from datetime import datetime

import joblib

from django.conf import settings
from django.core.management.base import BaseCommand
from joblib import Parallel, delayed

from literev.libs.collectors import ElasticSearchCollector

from .utils.classify_mineur_majeur import (
    classify_decision,
    get_filename,
)

CACHE_DIR = settings.LITEREV_CACHE_DIR

CACHE_STRUCTURED_DOCUMENTS = CACHE_DIR / "structured_data_documents"
CACHE_STRUCTURED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

CHAMBER_NAMES = settings.LITEREV_CHAMBER_NAMES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def custom_log(message):
    with open(CACHE_DIR / "chunking_logs.txt", "a") as f:
        f.write(message)


def extract_mineur_majeur(document: str, index_name: str):
    """
    Extract Majeures, Mineure-Fait, Mineure-subsommation and conclusion.

    Uses documents retrieved from Elastic Search and saves the results as json
    file with its record_key (equivalent to cle fiches).
    """
    record_key = getattr(document, "record_key", "")
    document_text = getattr(document, "document_text", "")
    decision_type = getattr(document, "decision_type", "")
    chamber = getattr(document, "chamber", "")

    if not record_key:
        logging.info("There is no doc_id")
        procedure_type = getattr(document, "procedure_type", "")
        logging.info(
            f"procedure_type: {procedure_type}, decision type: {decision_type}"
        )
        return

    if not decision_type:
        logging.info("There is no decision type code")
        procedure_type = getattr(document, "procedure_type", "")
        logging.info(
            f"record key: {record_key}, procedure_type: {procedure_type}, decision type: {decision_type}"
        )
        return

    try:
        # check if the doc has been processed
        document_filename = get_filename(record_key, decision_type, index_name)
        document_path = CACHE_STRUCTURED_DOCUMENTS / document_filename

        if document_path.is_file():
            logging.info(
                f"skipping doc_id: {record_key} with decision type:{decision_type} in chamber {chamber} because is cached"
            )
            custom_log(
                f"\nskipping doc_id: {record_key} with decision type:{decision_type} in chamber {chamber} because is cached"
            )
            return

        struct_json_doc = classify_decision(document_text)

        output = {
            "record_key": record_key,
            "structured_sentences": struct_json_doc,
        }

        logging.info(
            f"Extracted chunks for [Doc record_key: {record_key} {decision_type}]"
        )

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
            help="The name of the legal chamber to generate embeddings for.",
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
        max_workers_test: int = 2

        start_time = time.time()

        if index_name == "test":
            max_workers = max_workers_test
            start_date = datetime(2023, 6, 1)
            end_date = datetime(2023, 6, 10)

            search_query = "police AND fils"

            collector = ElasticSearchCollector(index_name="chambre_penale")

            documents = collector.collect_documents(
                search_query, start_date, end_date
            )

            logging.info(f"Document to process {len(documents)}")
            custom_log(f"\n---------------- Logs for {index_name}")
            custom_log(f"Document to process {len(documents)}")

        elif index_name == "run_100":
            max_workers = int(options["max_workers"])
            index_name = "chambre_penale"
            collector = ElasticSearchCollector(index_name=index_name)
            documents = collector.collect_all_documents()
            documents = documents[:100]

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
                        delayed(extract_mineur_majeur)(document, index_name)
                        for document in documents
                    ]
                )

        except Exception as e:
            logging.error(f"Chunking failed {e}")

        end_time = time.time()

        total_time = (end_time - start_time) / 60

        if index_name in ["test", "run_100"]:
            ALL_STRUCTURED_FILENAME = (
                f"all_structured_judgments_{index_name}.json"
            )
            ALL_STRUCTURED_PATH = (
                CACHE_STRUCTURED_DOCUMENTS / ALL_STRUCTURED_FILENAME
            )

            all_structured = []

            for file in CACHE_STRUCTURED_DOCUMENTS.glob(
                f"*{index_name}_structured.json"
            ):
                with open(file, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                    all_structured.append(doc)

            # Sauvegarder la version globale
            with open(ALL_STRUCTURED_PATH, "w", encoding="utf-8") as f:
                json.dump(all_structured, f, ensure_ascii=False, indent=2)

            logging.info(
                f"Aggregated {len(all_structured)} structured judgments → {ALL_STRUCTURED_PATH}"
            )

        logging.info(f"Elapsed time {total_time} min")
        custom_log(f"\nElapsed time {total_time} min")
