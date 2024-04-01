from __future__ import annotations

import re

from pathlib import Path

import spacy

from gensim.models import phrases
from gensim.utils import simple_preprocess

# library for lemmatization nlp spacy
# remove words list of stopwords
from lingua import Language, LanguageDetectorBuilder
from sklearn.feature_extraction.text import TfidfVectorizer

SUPPORTED_LANGUAGES = [Language.ENGLISH, Language.FRENCH]
detector = LanguageDetectorBuilder.from_languages(*SUPPORTED_LANGUAGES).build()
DATA_PATH = Path(__file__).parent / "data"


def create_stopwords() -> set[str]:
    """Create a new set of stopwords from a file.

    Returns
    -------
    stopwords : set[str]
              A set of stopwords.
    Ref: https://github.com/stopwords-iso/stopwords-fr
    """
    with open(DATA_PATH / "stopwords.txt", "r") as f:
        reader = f.read()

    return set(reader.splitlines())


def define_languages(corpus: str) -> bool:
    """Given an article corpus, determine if the article belongs to
    the list of valid languages

    Parameters
    ----------
    article_corpus : str
                    Corpus to be preprocessed

    Returns
    -------
    boolean : bool
            Returns True if the corpus is in English, False otherwise

    """
    # Detect the language of the given corpus
    detected_language = detector.detect_language_of(corpus)

    # Check if the detected language is English
    return detected_language == Language.FRENCH


def pre_processing(corpus: str) -> str:
    """Preprocess a string by removing special characters and digits.

    Parameters
    ----------
    corpus : str
              A abstract of an article corpus.

    Returns
    -------
    corpus : str
              A preprocessed article corpus.
    """
    pattern_replacement = [
        (r"\S*@\S*\s?", ""),  # to remove emails
        (r"\s+", " "),  # remove new line characters
        # ("'", " "),  # remove distracting single quotes
        ("_", ""),  # remove underscores
        (r"http[s]?://\S+", ""),  # remove http remants in the text
        (r"www\.*[\r\n]*\S+", ""),  # remove www remnants in the text
        (
            r"([a-zA-Z\s])\1{2,}",
            r"\1\1",
        ),  # change aaa into aa (or any other letter)
        (r"\b\w{0}\b", ""),  # remove zero characters words !Check it
    ]

    for pattern, replacement in pattern_replacement:
        corpus = re.sub(pattern, replacement, corpus)

    return corpus


def sentences_to_words(corpus: str) -> list[str]:
    """Receive a corpus to convert it into tokens.

    Parameters
    ----------
    article_corpus : str
                    Corpus to be preprocessed

    Returns
    -------
    list of tokens : list[str]
                    Returns a list of lowercase words tokens,
                    ignoring tokens that are too short or
                    too long (remove accents as well).

    """
    tokens_list: list[str] = simple_preprocess(
        corpus, deacc=False
    )  # by default min_len=2, max_len=15
    return tokens_list


def lemmatization(
    list_words: list[str],
    allowed_postags: list[str] = ["NOUN", "ADJ", "VERB", "ADV"],
) -> str:
    """
    Lemmatize a list of words.

    Parameters
    ----------
    list_words : list[str]
              A list of words of an article corpus.
    allowed_postags : list[str]
              A list of allowed POS tags.

    Returns
    -------
    list_lemmatized : list[str]
              A list of lemmatized words.
    """

    nlp = spacy.load("fr_core_news_sm", disable=["parser", "ner"])
    nlp.max_length = 10000000

    doc = nlp(" ".join(list_words))
    list_lemmatized = " ".join(
        token.lemma_ for token in doc if token.pos_ in allowed_postags
    )
    return list_lemmatized


def remove_words(list_lemmatized: str, list_stopwords: set[str]) -> str:
    """
    Remove stopwords from a article corpus

    Parameters
    ----------
    list_lemmatized : str
                    A preprocessed article corpus

    Returns
    -------
    corpus without stopwords : str
              A preprocessed article corpus without stopwords.
    """

    words = list_lemmatized.split()
    list_stopped = []

    for word in words:
        if word not in list_stopwords:
            list_stopped.append(word)

    return " ".join(list_stopped)


def create_ngrams(
    corpus_list: list[str],
) -> list[list[str]]:
    """Trains models to to identify bigrams and trigrams using
    the whole corpus of articles. And use those models to include into
    the article corpus bigram and trigrams
    i.e. convert the serie of words "new", "work" to  -> "new_york"
    "cooccurrence", "alpha", "gamma" to -> "cooccurrence_alpha_gamma"

    Parameters
    ----------
    corpus_list: list[str]
                A list of article corpus.

    Returns
    -------
    list_trigrams: list[list[str]]
                A list of article corpus, every article corpus
                as a list of words. This list of words contains
                bigrams and trigrams.
    """

    sentence_stream = [doc.split(" ") for doc in corpus_list]
    # threshold to 0.85
    # threshold to 0.85
    bigram = phrases.Phrases(
        sentence_stream, min_count=2, threshold=0.85, scoring="npmi"
    )

    trigram = phrases.Phrases(
        bigram[sentence_stream], min_count=2, threshold=0.85, scoring="npmi"
    )

    bigram_frozen = phrases.FrozenPhrases(bigram)
    trigram_frozen = phrases.FrozenPhrases(trigram)

    list_trigrams = [
        trigram_frozen[bigram_frozen[doc]] for doc in sentence_stream
    ]

    return list_trigrams


def remove_common_and_unique(list_trigrams: list[list[str]]) -> list[str]:
    # present the results
    # WORKAROUND
    # common_words = TfidfVectorizer(min_df=1, max_df=0.50)
    # .fit(" ".join(doc) for doc in list_trigrams)
    # unique_words = TfidfVectorizer(min_df=2, max_df=1.00)
    # .fit(" ".join(doc) for doc in list_trigrams)
    joined_corpus = [" ".join(corpus) for corpus in list_trigrams]
    # threshold max_df to 0.70
    common_and_unique_words = TfidfVectorizer(min_df=2, max_df=0.7)
    common_and_unique_words.fit(joined_corpus)
    # common_and_unique_words = TfidfVectorizer(min_df=2, max_df=0.60).fit(
    #    " ".join(list(set(doc))) for doc in list_trigrams
    # )

    list_temporary = [
        [
            word
            for word in doc
            if word not in common_and_unique_words.stop_words_
        ]
        for doc in list_trigrams
    ]
    list_final = [" ".join(doc) for doc in list_temporary]

    return list_final


def remove_empty(list_final: list[str]) -> list[str]:
    return_final_list: list[str] = []

    for corpus in list_final:
        if corpus:
            return_final_list.append(corpus)

    return return_final_list
