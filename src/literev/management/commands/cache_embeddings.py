import logging
import pickle
import faiss
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from langchain.text_splitter import RecursiveCharacterTextSplitter

from literev.libs.rag_classes import HactarAug
from literev.libs.collectors import ElasticSearchCollector
from django.conf import settings
from django.core.management.base import BaseCommand

# Constants
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
BATCH_SIZE = 32
CACHE_DIR = Path(settings.BASE_DIR) / "cache"


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

def retrieve_all_documents():
    collector = ElasticSearchCollector(index_name="penal_court")
    document = collector.collect_all_documents()
    logging.info(f"first document : {document[0]}")
    return len(document)

class Command(BaseCommand):
    help = "Generate and cache FAISS index for document embeddings"

    def handle(self, *args, **options):
        logging.info(f"HELLO SURELY THIS WORKS : {retrieve_all_documents()}")
