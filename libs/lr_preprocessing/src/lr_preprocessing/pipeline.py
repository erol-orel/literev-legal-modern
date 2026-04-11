from __future__ import annotations

import concurrent.futures
import logging

from .utils import (
    create_ngrams,
    create_stopwords,
    define_languages,
    lemmatize,
    pre_processing,
    remove_common_and_unique,
    remove_words,
    sentences_to_words,
)

stopwords_list = create_stopwords()


def clean_corpus(corpus: str) -> str:
    cleaned_article_corpus = pre_processing(corpus)
    corpus_to_tokens = sentences_to_words(cleaned_article_corpus)
    lemmatized = lemmatize(corpus_to_tokens)
    return remove_words(lemmatized, stopwords_list)


def clean_corpus_mp(corpus: str, pk: int) -> tuple[str, int]:
    logging.info(f"preprocessing: {pk}")
    if not define_languages(corpus):
        logging.info(f"discarding, not french: {pk}")
        return "", pk
    cleaned_corpus = clean_corpus(corpus)
    if not cleaned_corpus:
        logging.info(f"discarding, empty after removing stopwords: {pk}")
        return "", pk
    return cleaned_corpus, pk


def prepare_document(
    raw_document_text: str,
    raw_document_id: str | int | None = None,
    document_pk: int | None = None,
) -> str | None:
    corpus = raw_document_text or ""
    if not define_languages(corpus):
        logging.info(
            f"discarding, not french: {raw_document_id} pk: {document_pk}"
        )
        return None
    cleaned_corpus = clean_corpus(corpus)
    if not cleaned_corpus:
        logging.info(
            f"discarding, empty after removing stopwords: {raw_document_id} pk: {document_pk}"
        )
        return None
    logging.info(
        f"prepared document index: {raw_document_id} pk: {document_pk}"
    )
    return cleaned_corpus


def preprocess_documents(list_trigrams: list[list[str]]) -> list[str]:
    logging.info("trigrams have been generated")
    logging.info("removing common and unique")
    return remove_common_and_unique(list_trigrams)


def preprocessing_mp(
    pk_list: list[int],
    corpuses: list[str],
) -> tuple[set[int], list[str]]:
    prepared_for_ngrams_dict: dict[int, str] = {}
    prepared_for_ngrams: list[str] = []
    rejected: set[int] = set()
    logging.info("mp started")
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(clean_corpus_mp, corpus, index)
            for index, corpus in zip(pk_list, corpuses)
        ]
        for future in concurrent.futures.as_completed(futures):
            corpus, pk = future.result()
            if corpus == "":
                rejected.add(pk)
                continue
            prepared_for_ngrams_dict[pk] = corpus
        concurrent.futures.wait(futures)
    for _, value in sorted(prepared_for_ngrams_dict.items()):
        prepared_for_ngrams.append(value)
    list_trigrams = create_ngrams(prepared_for_ngrams)
    return rejected, remove_common_and_unique(list_trigrams)
