import concurrent

from utils import (
    create_stopwords,
    define_languages,
    pre_processing,
    sentences_to_words,
    lemmatization,
    remove_words,
    create_ngrams,
    remove_common_and_unique,
    remove_empty,
)

stopwords_list = create_stopwords()

def clean_corpus(
    corpus: str
) -> str:
    
    cleaned_article_corpus = pre_processing(corpus)

    corpus_to_tokens = sentences_to_words(
        cleaned_article_corpus
    )

    lemmatized = lemmatization(corpus_to_tokens)

    corpus_without_stopwords = remove_words(
        lemmatized, stopwords_list
    )

    return corpus_without_stopwords

def clean_corpus_mp(
    corpus: str
) -> str:

    if not define_languages(corpus):
        print("discarding, not french: ", index)
        return ""

    cleaned_corpus = clean_corpus(corpus)

    cleaned_article_corpus = pre_processing(corpus)

    corpus_to_tokens = sentences_to_words(
        cleaned_article_corpus
    )

    lemmatized = lemmatization(corpus_to_tokens)

    corpus_without_stopwords = remove_words(
        lemmatized, stopwords_list
    )
    
    if not corpus_without_stopwords:
        print("discarding, emtpy after removing stopwords: ", index)
        return ""

    return corpus_without_stopwords
    
def back_preprocessing(corpuses):

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
    
    #remove common and unique

    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)
    
    # clean empty corpus
    preprocessed_corpus = remove_empty(corpuses_wo_common_and_unique)
    
    return preprocessed_corpus

def back_preprocessing_mp(corpuses):
    prepared_for_ngrams = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [
            executor.submit(
                clean_corpus_mp, corpus
            )
            for corpus in corpuses
        ]

        for future in concurrent.futures.as_completed(futures):
            corpus = future.result()
            if corpus == "":
                continue
            try:
                prepared_for_ngrams.append(corpus)
               
            except Exception as e:
                print(f"Error processing future: {e}")

        concurrent.futures.wait(futures)

    list_trigrams = create_ngrams(prepared_for_ngrams)
    
    #remove common and unique

    corpuses_wo_common_and_unique = remove_common_and_unique(list_trigrams)
    
    # clean empty corpus
    preprocessed_corpuses = remove_empty(corpuses_wo_common_and_unique)
    
    return preprocessed_corpuses
    
    