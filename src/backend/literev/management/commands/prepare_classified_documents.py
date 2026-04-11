import json
import logging
import time

from typing import Any

import joblib

from django.conf import settings
from django.core.management.base import BaseCommand
from joblib import Parallel, delayed

from .utils.classify_mineur_majeur import get_filename

THRESHOLD_SECOND_SECTION = 0.35

CACHE_DIR = settings.LITEREV_CACHE_DIR

# source dir
CACHE_CLASSIFIED_DOCUMENTS = CACHE_DIR / "classified_documents"
CACHE_CLASSIFIED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

# dest dir
CACHE_STRUCTURED_DOCUMENTS = CACHE_DIR / "structured_data_documents"
CACHE_STRUCTURED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

CHAMBER_NAMES = settings.LITEREV_CHAMBER_NAMES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def custom_log(message):
    "Write message into a log classification file."
    with open(CACHE_DIR / "preparing_logs.txt", "a") as f:
        f.write(message)


def prepare_structured_document_worker(document_path, index_name) -> None:
    """
    Rearrange the document content in order to prepare for embeddings.
    """
    with open(document_path, "r") as f:
        result = json.load(f)
    record_key = result["record_key"]
    decision_type = result["decision_type"]

    new_document_filename = get_filename(record_key, decision_type, index_name)
    new_document_path = CACHE_STRUCTURED_DOCUMENTS / new_document_filename

    if new_document_path.is_file():
        logging.info(
            f"skipping doc_id: {record_key} with decision type:{decision_type} because is already prepared."
        )
        custom_log(
            f"\nskipping doc_id: {record_key} with decision type:{decision_type} because is already prepared."
        )
        return

    structured_sentences: dict[str, Any] = {
        "Metadata": [],
        "Majeure": [],
        "Mineure-Faits": [],
        "Mineure-Subsommation": [],
        "Conclusion": [],
    }

    classified_sentences = result["classified_sentences"]

    for classified_sentence in classified_sentences:
        idx = classified_sentence["id"]
        sentence = classified_sentence["sentence"]
        predicted_label = classified_sentence["predicted_label"]
        second_label = ""
        for k, v in classified_sentence["full_probs"].items():
            if v > THRESHOLD_SECOND_SECTION and k != predicted_label:
                second_label = k

        itemx = {"id": idx, "sentence": sentence}
        structured_sentences[predicted_label].append(itemx)
        if second_label:
            structured_sentences[second_label].append(itemx)

    cleaned_structured_sentences: dict[str, list[str]] = {
        "Metadata": [],
        "Majeure": [],
        "Mineure-Faits": [],
        "Mineure-Subsommation": [],
        "Conclusion": [],
    }
    for section, chunks in structured_sentences.items():
        try:
            buffer = [chunks[0]["sentence"]]
            buffer_ids = [chunks[0]["id"]]

        except Exception as e:
            logging.info(section)
            logging.info(chunks)
            logging.info(e)
            continue

        old_id = buffer_ids[0]

        for chunk in chunks[1:]:
            idx = chunk["id"]
            sentence = chunk["sentence"]
            if old_id + 1 == idx:
                buffer.append(sentence)
                buffer_ids.append(idx)
                old_id = idx
            else:
                if buffer:
                    item = "\n".join(buffer)
                    cleaned_structured_sentences[section].append(item)
                    buffer = [sentence]
                    buffer_ids = [idx]
                    old_id = idx

        if buffer:
            item = "\n".join(buffer)
            cleaned_structured_sentences[section].append(item)

    data = {
        "record_key": record_key,
        "decision_type": decision_type,
        "structured_sentences": cleaned_structured_sentences,
    }

    with open(new_document_path, "w") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=2))


class Command(BaseCommand):
    help = (
        "Prepare documents for embedding given the index name of the chamber."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--index-name",
            type=str,
            required=True,
            help="The name of the legal chamber.",
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
        index_name: str = options["index_name"]
        max_workers: int = int(options["max_workers"])

        start_time = time.time()

        try:
            documents_paths = list(
                CACHE_CLASSIFIED_DOCUMENTS.glob(
                    f"*{index_name}_classified.json"
                )
            )

            logging.info(f"Document to process {len(documents_paths)}")
            custom_log(f"\n---------------- Logs for {index_name}")
            custom_log(f"Document to process {len(documents_paths)}")

            if not documents_paths:
                logging.error("No documents to proccess.")
                raise ValueError("No documents to process.")

            documents_paths.sort()
            # total = len(documents_paths)

            with joblib.parallel_backend("loky", n_jobs=max_workers):
                Parallel(n_jobs=max_workers)(
                    delayed(prepare_structured_document_worker)(
                        document_path, index_name
                    )
                    for document_path in documents_paths
                )

        except Exception as e:
            logging.error(f"Preparing failed {e}")

        end_time = time.time()

        total_time = (end_time - start_time) / 60

        logging.info(f"Elapsed time {total_time} min")
        custom_log(f"\nElapsed time {total_time} min")
