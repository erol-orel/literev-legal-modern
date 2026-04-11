import json
import logging
import time

from datetime import datetime

import joblib
import torch

from django.conf import settings
from django.core.management.base import BaseCommand
from joblib import Parallel, delayed
from torch.nn.functional import softmax
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from literev.libs.collectors import ElasticSearchCollector

from .utils.split_document import (
    get_classified_filename,
    get_splitted_filename,
    legal_sentence_split,
    merge_short_sentences,
)

CACHE_DIR = settings.LITEREV_CACHE_DIR

CACHE_SPLITTED_DOCUMENTS = CACHE_DIR / "splitted_documents"
CACHE_SPLITTED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

CACHE_CLASSIFIED_DOCUMENTS = CACHE_DIR / "classified_documents"
CACHE_CLASSIFIED_DOCUMENTS.mkdir(parents=True, exist_ok=True)

MODEL_DIR = CACHE_DIR / "merged_model"  # Specify this
LABELS = [
    "Metadata",
    "Majeure",
    "Mineure-Faits",
    "Mineure-Subsommation",
    "Conclusion",
]

CHAMBER_NAMES = settings.LITEREV_CHAMBER_NAMES

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def custom_log(message):
    "Write message into a log classification file."
    with open(CACHE_DIR / "classification_logs.txt", "a") as f:
        f.write(message)


def get_splitted_document_worker(document, index_name) -> None:
    "Split and save a splitted document."
    try:
        record_key = getattr(document, "record_key", "")
        document_text = getattr(document, "document_text", "")
        decision_type = getattr(document, "decision_type", "")
        chamber = getattr(document, "chamber", "")

        splitted_filename = get_splitted_filename(
            record_key, decision_type, index_name
        )
        splitted_document_path = CACHE_SPLITTED_DOCUMENTS / splitted_filename

        if splitted_document_path.is_file():
            logging.info(
                f"skipping doc_id: {record_key} with decision type:{decision_type} in chamber {chamber} because is splitted"
            )
            custom_log(
                f"\nskipping doc_id: {record_key} with decision type:{decision_type} in chamber {chamber} because is splitted"
            )
            return

        sentences = legal_sentence_split(document_text)
        merged_sentences = merge_short_sentences(sentences)

        document_dict = {
            "record_key": record_key,
            "decision_type": decision_type,
            "raw_sentences": merged_sentences,
        }

        with open(splitted_document_path, "w", encoding="utf-8") as f:
            json.dump(document_dict, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logging.error(
            f"Split failed for a document (record_key: {getattr(document, 'record_key', 'UNKNOWN')}): {e}"
        )


def get_splitted_documents(
    index_name: str, max_workers: int, is_test: bool = False
) -> None:
    """
    Split all document from a ElasticSearch given the index name.

    Uses parallelization from joblib library.
    """
    collector = ElasticSearchCollector(index_name=index_name)
    if not is_test:
        documents = collector.collect_all_documents()
    else:
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

    if not documents:
        logging.error("No documents to proccess.")
        raise ValueError("No documents to process.")

    with joblib.parallel_backend("loky", n_jobs=max_workers):
        Parallel(n_jobs=max_workers)(
            delayed(get_splitted_document_worker)(document, index_name)
            for document in documents
        )


_TOKENIZER = None
_MODEL = None
_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Avoid OpenMP oversubscription inside each worker
torch.set_num_threads(1)


def _get_model_and_tokenizer():
    "Return the trained model and the tokenizer."
    global _TOKENIZER, _MODEL
    if _TOKENIZER is None:
        _TOKENIZER = AutoTokenizer.from_pretrained(MODEL_DIR, use_fast=True)
        if _TOKENIZER.pad_token is None:
            _TOKENIZER.pad_token = _TOKENIZER.eos_token or _TOKENIZER.unk_token
    if _MODEL is None:
        _MODEL = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
        _MODEL.eval()
        _MODEL.to(_DEVICE)
        if getattr(_MODEL.config, "pad_token_id", None) is None:
            _MODEL.config.pad_token_id = _TOKENIZER.pad_token_id

        # Optional sanity check
        if hasattr(
            _MODEL.config, "num_labels"
        ) and _MODEL.config.num_labels != len(LABELS):
            logging.warning(
                f"Model has {_MODEL.config.num_labels} labels but LABELS has {len(LABELS)} entries."
            )

    return _TOKENIZER, _MODEL, _DEVICE


def classify_legal_document_worker(
    document_path: str, index_name: str, batch_size: int, idx, total
) -> None:
    """
    Classify a document into valid legal sections.

    This function uses a trained model to classify sentences, and saves the results into the filesystem.
    """
    if idx is not None and total is not None:
        logging.info(f"Processing document {idx + 1}/{total}")

    try:
        tokenizer, model, device = _get_model_and_tokenizer()

        with open(document_path, "r", encoding="utf-8") as f:
            document_dict = json.load(f)

        sentences = document_dict["raw_sentences"]
        record_key = document_dict["record_key"]
        decision_type = document_dict["decision_type"]

        classified_filename = get_classified_filename(
            record_key, decision_type, index_name
        )
        classified_document_path = (
            CACHE_CLASSIFIED_DOCUMENTS / classified_filename
        )

        if classified_document_path.is_file():
            logging.info(
                f"skipping doc_id: {record_key} with decision type:{decision_type} because is already classified"
            )
            custom_log(
                f"\nskipping doc_id: {record_key} with decision type:{decision_type} because is classified"
            )
            return

        results = []
        c = 0
        for start in range(0, len(sentences), batch_size):
            batch = sentences[start : start + batch_size]
            inputs = tokenizer(
                batch,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512,
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}

            with torch.no_grad():
                logits = model(**inputs).logits
                pred_ids = logits.argmax(dim=-1).tolist()
                probs = softmax(logits, dim=-1).cpu().tolist()

            for sent, pred_idx, prob_vec in zip(batch, pred_ids, probs):
                confidence = prob_vec[pred_idx]
                results.append(
                    {
                        "id": c,
                        "sentence": sent,
                        "predicted_label": LABELS[pred_idx],
                        "confidence": round(confidence, 3),
                        "full_probs": dict(
                            zip(LABELS, [round(p, 3) for p in prob_vec])
                        ),
                    }
                )
                c += 1

        document_results_dict = {
            "record_key": record_key,
            "decision_type": decision_type,
            "classified_sentences": results,
        }

        with open(classified_document_path, "w", encoding="utf-8") as f:
            json.dump(document_results_dict, f, ensure_ascii=False, indent=2)

        logging.info(
            f"classified for [Doc record_key: {record_key} {decision_type}] sentences : {len(sentences)}"
        )

    except Exception as e:
        logging.error(f"An error has ocurred {e}")
        logging.info(f"document failed to classify {record_key}")
        custom_log(
            f"\nAn error has ocurred {e} \ndocument failed to extract mineur and majeur {record_key}"
        )


class Command(BaseCommand):
    help = "Extract mineur and majeur from all documents and save it into a json file."

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
        parser.add_argument(
            "--batch-size",
            type=int,
            required=False,
            default=128,
            help="Batch size for sentence classification.",
        )

    def handle(
        self, *args, **options
    ) -> None:  # removed *args: Any, **options: Any because linter
        index_name: str = options["index_name"]
        max_workers: int = int(options["max_workers"])
        batch_size: int = int(options["batch_size"])

        start_time = time.time()
        is_test = False

        if index_name == "test":
            is_test = True
            max_workers = 2

        else:
            if index_name not in CHAMBER_NAMES:
                logging.error(
                    f"index_name must be one of the following: {CHAMBER_NAMES}"
                )
                raise ValueError("Invalid index_name")

        try:
            get_splitted_documents(index_name, max_workers, is_test)

            logging.info("Splitting documents done")

            documents_paths = list(
                CACHE_SPLITTED_DOCUMENTS.glob(f"*{index_name}_splitted.json")
            )
            documents_paths.sort()
            total = len(documents_paths)

            with joblib.parallel_backend("loky", n_jobs=max_workers):
                Parallel(n_jobs=max_workers)(
                    delayed(classify_legal_document_worker)(
                        document_path, index_name, batch_size, idx, total
                    )
                    for idx, document_path in enumerate(documents_paths)
                )

        except Exception as e:
            logging.error(f"classification failed {e}")

        end_time = time.time()

        total_time = (end_time - start_time) / 60

        logging.info(f"Elapsed time {total_time} min")
        custom_log(f"\nElapsed time {total_time} min")
