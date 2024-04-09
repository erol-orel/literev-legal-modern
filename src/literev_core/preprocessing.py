import concurrent.futures

from literev.models import Project

from .utils import (
    create_ngrams,
    create_stopwords,
    define_languages,
    lemmatization,
    pre_processing,
    remove_common_and_unique,
    remove_words,
    sentences_to_words,
)

stopwords_list = create_stopwords()


def clean_corpus(corpus: str) -> str:
    cleaned_article_corpus = pre_processing(corpus)

    corpus_to_tokens = sentences_to_words(cleaned_article_corpus)

    lemmatized = lemmatization(corpus_to_tokens)

    corpus_without_stopwords = remove_words(lemmatized, stopwords_list)

    return corpus_without_stopwords


def clean_corpus_mp(corpus: str, pk: int) -> tuple[str, int]:
    print("preprocessing: ", pk)
    if not define_languages(corpus):
        print("discarding, not french: ", pk)
        return "", pk

    cleaned_corpus = pre_processing(corpus)

    corpus_to_tokens = sentences_to_words(cleaned_corpus)

    lemmatized = lemmatization(corpus_to_tokens)

    corpus_without_stopwords = remove_words(lemmatized, stopwords_list)

    if not corpus_without_stopwords:
        print("discarding, emtpy after removing stopwords: ", pk)
        return "", pk

    return corpus_without_stopwords, pk


def preprocessing(
    project: Project, pk_list: list[int], corpuses: list[str]
) -> tuple[set[int], list[str]]:
    prepared_for_ngrams = []
    rejected_pk = set()

    print("starting preprocessing")
    print("documents: ", len(corpuses))
    for index, corpus in zip(pk_list, corpuses):
        print("Processing document:", index)
        if not define_languages(corpus):
            print("discarting, not french: ", index)
            rejected_pk.add(index)
            continue

        cleaned_corpus = clean_corpus(corpus)

        if not cleaned_corpus:
            print("discarting, emtpy after removing stopwords: ", index)
            rejected_pk.add(index)
            continue

        prepared_for_ngrams.append(cleaned_corpus)

        project.step_number += 1
        project.save()
        print("preprocessed document index: ", index)

    print("starting trigrams")

    list_trigrams = create_ngrams(prepared_for_ngrams)

    print("trigrams have been generated")
    # remove common and unique

    print("removing common an unique")
    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)

    # The web app is removing empty corpuses before clustering
    # preprocessed_corpus = remove_empty(corpuses_wo_common_and_unique)

    return rejected_pk, corpuses_wo_common_and_unique  # preprocessed_corpus


def preprocessing_mp(pk_list: list[int], corpuses: list[str]) -> list[str]:
    prepared_for_ngrams_dict = dict()
    prepared_for_ngrams = []
    rejected = set()
    print("mp started")
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
                print("processed index: ", pk)

            except Exception as e:
                print(f"Error processing future: {e}")

        concurrent.futures.wait(futures)

    sorted_dict = dict(sorted(prepared_for_ngrams_dict.items()))

    for k, v in sorted_dict.items():
        prepared_for_ngrams.append(v)

    list_trigrams = create_ngrams(prepared_for_ngrams)

    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)

    # The web app is removing empty corpuses before clustering
    # preprocessed_corpuses = remove_empty(corpuses_wo_common_and_unique)

    return rejected, corpuses_wo_common_and_unique  # preprocessed_corpuses
