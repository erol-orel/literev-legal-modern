import concurrent

from .utils import (
    create_ngrams,
    create_stopwords,
    define_languages,
    lemmatization,
    pre_processing,
    remove_common_and_unique,
    remove_empty,
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


def clean_corpus_mp(corpus: str, index: int) -> tuple[str, int]:
    if not define_languages(corpus):
        print("discarding, not french: ", index)
        return "", -1

    cleaned_corpus = pre_processing(corpus)

    corpus_to_tokens = sentences_to_words(cleaned_corpus)

    lemmatized = lemmatization(corpus_to_tokens)

    corpus_without_stopwords = remove_words(lemmatized, stopwords_list)

    if not corpus_without_stopwords:
        print("discarding, emtpy after removing stopwords: ", index)
        return "", -1

    return corpus_without_stopwords, index


def preprocessing(corpuses: list[str]) -> list[str]:
    prepared_for_ngrams = []
    for index, corpus in enumerate(corpuses):
        print(f"Preprocessing corpus: {index}")
        if not define_languages(corpus):
            print("discarting, not french: ", index)
            continue

        cleaned_corpus = clean_corpus(corpus)

        if not cleaned_corpus:
            print("discarting, emtpy after removing stopwords: ", index)
            continue

        prepared_for_ngrams.append(cleaned_corpus)

    list_trigrams = create_ngrams(prepared_for_ngrams)

    # remove common and unique

    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)

    # clean empty corpus
    preprocessed_corpus = remove_empty(corpuses_wo_common_and_unique)

    return preprocessed_corpus


def preprocessing_mp(corpuses: list[str]) -> list[str]:
    prepared_for_ngrams_dict = dict()
    prepared_for_ngrams = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(clean_corpus_mp, corpus, index)
            for index, corpus in enumerate(corpuses)
        ]

        for future in concurrent.futures.as_completed(futures):
            corpus, index = future.result()
            if corpus == "":
                continue
            try:
                prepared_for_ngrams_dict[index] = corpus
                print("processed index: ", index)

            except Exception as e:
                print(f"Error processing future: {e}")

        concurrent.futures.wait(futures)

    sorted_dict = dict(sorted(prepared_for_ngrams_dict.items()))

    for k, v in sorted_dict.items():
        prepared_for_ngrams.append(v)

    list_trigrams = create_ngrams(prepared_for_ngrams)

    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)

    # preprocessed_corpuses = remove_empty(corpuses_wo_common_and_unique)

    return corpuses_wo_common_and_unique  # preprocessed_corpuses
