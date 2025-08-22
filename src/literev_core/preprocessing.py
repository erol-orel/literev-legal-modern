import concurrent.futures
import logging

from typing import Optional

from literev.models import Document

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

    corpus_without_stopwords = remove_words(lemmatized, stopwords_list)

    return corpus_without_stopwords


def clean_corpus_mp(corpus: str, pk: int) -> tuple[str, int]:
    logging.info(f"preprocessing: {pk}")
    if not define_languages(corpus):
        logging.info(f"discarding, not french: {pk}")
        return "", pk

    cleaned_corpus = pre_processing(corpus)

    corpus_to_tokens = sentences_to_words(cleaned_corpus)

    lemmatized = lemmatize(corpus_to_tokens)

    corpus_without_stopwords = remove_words(lemmatized, stopwords_list)

    if not corpus_without_stopwords:
        logging.info("discarding, emtpy after removing stopwords: ", pk)
        return "", pk

    return corpus_without_stopwords, pk


def update_prepared_document(
    document: Document, prepared_document: str
) -> None:
    document.prepared_for_ngrams = prepared_document
    document.save()


def prepare_document(document: Document) -> Optional[str]:
    corpus = document.raw_document_text or ""
    if not define_languages(corpus):
        logging.info(
            f"discarting, not french: {document.raw_document_id} pk: {document.raw_document_id}"
        )
        return None

    cleaned_corpus = clean_corpus(corpus)

    if not cleaned_corpus:
        logging.info(
            f"discarting, empty after removing stopwords: {document.raw_document_id} pk: {document.raw_document_id}"
        )
        return None

    logging.info(
        f"prepared document index: {document.raw_document_id} pk: {document.pk}"
    )

    return cleaned_corpus


def preprocess_documents(list_trigrams: list[list[str]]) -> list[str]:
    logging.info("trigrams have been generated")
    # remove common and unique

    logging.info("removing common an unique")
    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)

    # The web app is removing empty corpuses before clustering
    # Keeping this piece of code to check if we need to remove remove_empty function
    # preprocessed_corpus = remove_empty(corpuses_wo_common_and_unique)

    return corpuses_wo_common_and_unique


def preprocessing_mp(
    pk_list: list[int], corpuses: list[str]
) -> tuple[set[int], list[str]]:
    prepared_for_ngrams_dict = {}
    prepared_for_ngrams = []
    rejected = set()
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
            try:
                prepared_for_ngrams_dict[pk] = corpus
                logging.info(f"processed index: {pk} ")

            except Exception as e:
                logging.info(f"Error processing future: {e}")

        concurrent.futures.wait(futures)

    sorted_dict = dict(sorted(prepared_for_ngrams_dict.items()))

    for k, v in sorted_dict.items():
        prepared_for_ngrams.append(v)

    list_trigrams = create_ngrams(prepared_for_ngrams)

    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)

    # The web app is removing empty corpuses before clustering
    # preprocessed_corpuses = remove_empty(corpuses_wo_common_and_unique)

    return rejected, corpuses_wo_common_and_unique  # preprocessed_corpuses
