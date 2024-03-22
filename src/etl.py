"""ETL - Extract, Transform, Load

This module contains utility functions for extracting, transforming, and loading data from judiciary JSONL data files.

Classes:
    - DataReader: A helper class for reading large data from files.
    - DataNormalizer: A helper class for normalizing data, specifically date and timestamp normalization.
    - DataTranslator: A class for translating key names from French to standardized English.

Usage:
    To use this module, import it into your script or application and utilize its classes for handling jsonl data.

Example:
    ```python
    from etl import DataReader, DataNormalizer, DataTranslator

    # Example usage of DataReader
    reader = DataReader("example.jsonl")
    for doc in reader.read_data():
        print(doc)

    # Example usage of DataNormalizer
    normalizer = DataNormalizer()
    normalized_data = normalizer.normalize_document(doc)

    # Example usage of DataTranslator
    translator = DataTranslator()
    translated_data = translator.translate_document_fields(doc)
    ```
"""
from __future__ import annotations
import json
from datetime import datetime
from elasticsearch import Elasticsearch
from pathlib import Path
from typing import Any, Generator


class DataReader:
    """Helper class for reading large data from files."""

    SUPPORTED_EXTENSIONS = ["jsonl"]

    def __init__(self, file_path: str):
        if not Path(file_path).is_file():
            raise FileNotFoundError(f"File {file_path} does not exist")
        self.file_path = Path(file_path)
    
    def _read_jsonl_lines(self) -> Generator[dict, None, None]:
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line_number, line in enumerate(f):
                try:
                    json_obj = json.loads(line.strip()) # remove \n
                    yield  line_number, json_obj
                except Exception as e:
                    raise e
    
    def read_data(self) -> Generator[dict, None, None]:
        if self.file_path.suffix == ".jsonl":
            return self._read_jsonl_lines()
        else:
            raise NotImplementedError(
                f"DataReader doesn't support {self.file_path.suffix} file extension. "
                f"Supported extensions: {self.SUPPORTED_EXTENSIONS}"
                )


class DataNormalizer:
    """
    Helper class for normalizing data
    """

    DECISION_DATE = "decision_date"
    APPEALS_KEY = "appeals"
    CREATION_TIMESTAMP = "creation_timestamp"
    MODIFICATION_TIMESTAMP = "modification_timestamp"
    START_DATE = "start_date"
    END_DATE = "end_date"
    MODIFICATION_DATE = "modification_date"


    def normalize_document(self, doc: dict[str, Any]) -> dict[str, Any]:
        for key, value in doc.items():

            # normalize decision date
            if key == self.DECISION_DATE and value is not None:
                doc[key] = self._normalize_date(value)

            # normalize appeals if exists
            if key == self.APPEALS_KEY and value:

                for appeal in value:
                    if appeal[self.CREATION_TIMESTAMP] is not None:
                        appeal[self.CREATION_TIMESTAMP] = self._normalize_date_timestamp(
                            appeal[self.CREATION_TIMESTAMP])

                    if appeal[self.MODIFICATION_TIMESTAMP] is not None:
                        appeal[self.MODIFICATION_TIMESTAMP] = self._normalize_date_timestamp(
                            appeal[self.MODIFICATION_TIMESTAMP])
                    
                    if appeal[self.START_DATE] is not None:
                        appeal[self.START_DATE] = self._normalize_date(appeal[self.START_DATE])
                    
                    if appeal[self.END_DATE] is not None:
                        appeal[self.END_DATE] = self._normalize_date(appeal[self.END_DATE])
                    
                    if appeal[self.MODIFICATION_DATE] is not None:
                        appeal[self.MODIFICATION_DATE] = self._normalize_date(appeal[self.MODIFICATION_DATE])
        return doc
                    


    def _normalize_date(self, raw_date: str) -> str:
        """Normalizes the date format."""
        date = datetime.strptime(raw_date, "%d.%m.%Y")
        return date.strftime("%Y-%m-%d")

    def _normalize_date_timestamp(sef, raw_date_timestamp: str) -> str:
        """Normalizes the date timestamp format."""
        timestamp = datetime.strptime(raw_date_timestamp, "%d/%m/%y %H:%M:%S.%f")
        return timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")


class DataTranslator:

    # translation for field names
    ROOT_FIELD_MAP: dict[str, str] = {
        'resume': 'summary',
        'normes': 'standards',
        'proc_year': 'procedure_year',
        'parties': 'parties_involved',
        'recours': 'appeals',
        'publieinternet': 'published_internet',
        'rectification': 'correction',
        'cle_fiche': 'record_key', #(or file_key)
        'datedecision': 'decision_date',
        'procedure': 'procedure_type',
        'decision': 'decision_type',
        'importance': 'importance',
        'n_ext_proc': 'external_procedure_number',
        'document': 'document',
        'nature': 'nature',
        'dt_decision': 'decision_date',
        'coll_nom': 'collector_name',
        'relations': 'relations',
        'source': 'source',
        'fichierword': 'word_file',
        'arretdeprincipe': 'stopped_from_begin', #()
        'n_ext_jur_attr': 'external_jurisdiction_attribute',
        'resultat': 'result',
        'document_text': 'document_text',
        'descripteurs': 'descriptors',
        'id': 'id'
    }

    # translation for appeal field names
    APPEAL_FIELD_MAP: dict[str, str] = {
        'date_fin': 'end_date',
        'type_recours': 'appeal_type',
        't_modif': 'modification_time',
        'oper_modif': 'modified_by',
        'etat_action': 'action_status',
        'cle_fiche': 'record_key',
        'resultat': 'result',
        'oper_creat': 'created_by',
        'ts_creat': 'creation_timestamp',
        'chambre': 'chamber',
        'd_modif': 'modification_date',
        'type': 'case_type',
        'date_debut': 'start_date',
        'cle_decis_recours': 'decision_appeal_key',
        'no_decis': 'decision_number',
        'no_atf': 'atf_number',
        'ts_modif': 'modification_timestamp',
        'nature': 'case_nature',
        'cle_action': 'action_key',
        'no_procedure': 'procedure_number',
    }

    def translate_document_fields(self,doc: dict[str, Any]) -> dict[str, Any]:
        """Translates the field names in a document/record."""

        APPEAL_KEY = "recours"
        QUERY_KEY = "query"

        # Create a copy of the keys to avoid dictionary size change during iteration
        for field, translation in list(self.ROOT_FIELD_MAP.items()):
            if field in doc:
                doc[translation] = doc.pop(field)
            else:
                if field == APPEAL_KEY:
                    doc[translation] = []
                else:
                    doc[translation] = None
            
            # handle appeals
            if field == APPEAL_KEY:
                appeals = []
                for appeal in doc[self.ROOT_FIELD_MAP[APPEAL_KEY]]:
                    for field, translation in list(self.APPEAL_FIELD_MAP.items()):
                        if field in appeal:
                            appeal[translation] = appeal.pop(field)
                        else:
                            appeal[translation] = None
                    appeals.append(appeal)
                doc[self.ROOT_FIELD_MAP[APPEAL_KEY]] = appeals
        
        # delete noise or unused fields
        # delete query key if exists
        if QUERY_KEY in doc:
            del doc[QUERY_KEY]

        return doc


class DataLoader:
    """Utility class for loading data into some given storage."""


    def __init__(self, reader: DataReader) -> None:
        self.reader = reader


    def load_into_es(self, es_client: Elasticsearch, index_name: str) -> None:
        """Loads data into a Elasticsearch index."""

        try:
            for line, document in self.reader.read_data():
                del document["document"]
                es_client.index(index=index_name, document=document, id=document["record_key"])
        except Exception as e:
            raise type(e)(f"{e}, record is at line number {line}") from e
    

    def load_into_jsonl_file(self, export_path: str) -> None:
        """Loads data into a JSONL file."""
        
        translator, normalizer = DataTranslator(), DataNormalizer()
    
        with open(export_path, "w", encoding="utf-8") as f:
            for _, doc in self.reader.read_data():
                doc =  translator.translate_document_fields(doc)
                doc = normalizer.normalize_document(doc)
                record = json.dumps(doc, ensure_ascii=False)
                f.write(record + '\n')
