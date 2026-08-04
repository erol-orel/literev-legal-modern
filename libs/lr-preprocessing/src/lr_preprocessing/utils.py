from __future__ import annotations

import logging
import re
import unicodedata

from pathlib import Path
from typing import Any

import spacy


# library for lemmatization nlp spacy
# remove words list of stopwords
from lingua import Language, LanguageDetectorBuilder
from sklearn.feature_extraction.text import TfidfVectorizer

from . import phrases_compat as phrases

logger = logging.getLogger(__name__)

# Swiss federal decisions are published in German, French and Italian; English
# is kept so the detector can still recognise it (and the pipeline discard it).
SUPPORTED_LANGUAGES = [
    Language.ENGLISH,
    Language.FRENCH,
    Language.GERMAN,
    Language.ITALIAN,
]
detector = LanguageDetectorBuilder.from_languages(*SUPPORTED_LANGUAGES).build()
DATA_PATH = Path(__file__).parent / "data"

# Detected lingua languages we actually preprocess, mapped to short codes.
_LANGUAGE_CODES = {
    Language.FRENCH: "fr",
    Language.GERMAN: "de",
    Language.ITALIAN: "it",
}
# Per-language spaCy model names. Only French ships by default; the German and
# Italian models are optional and loaded lazily with a graceful fallback.
_SPACY_MODELS = {
    "fr": "fr_core_news_sm",
    "de": "de_core_news_sm",
    "it": "it_core_news_sm",
}

NLP = spacy.load("fr_core_news_sm", disable=["parser", "ner"])
NLP.max_length = 10000000

# Caches keyed by language code. French is primed with the eagerly-loaded model
# above so its behaviour is unchanged; other languages populate on first use.
_NLP_CACHE: dict[str, Any] = {"fr": NLP}
_STOPWORDS_CACHE: dict[str, set[str]] = {}

_WORD_RE = re.compile(r"(?u)\b\w+\b")


def simple_preprocess(
    text: str,
    deacc: bool = False,
    min_len: int = 2,
    max_len: int = 15,
) -> list[str]:
    if deacc:
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    text = text.lower()
    toks = _WORD_RE.findall(text)
    return [t for t in toks if min_len <= len(t) <= max_len]


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


def _get_nlp(lang: str) -> Any:
    """Return a cached spaCy pipeline for ``lang`` or ``None`` if unavailable.

    French is always present; German/Italian load lazily. A missing model is
    cached as ``None`` so callers skip lemmatization rather than raising.
    """
    if lang in _NLP_CACHE:
        return _NLP_CACHE[lang]
    model_name = _SPACY_MODELS.get(lang)
    nlp: Any = None
    if model_name:
        try:
            nlp = spacy.load(model_name, disable=["parser", "ner"])
            nlp.max_length = 10000000
        except (OSError, ImportError):
            logger.warning(
                "spaCy model '%s' is not installed; lemmatization is "
                "skipped for language '%s'.",
                model_name,
                lang,
            )
            nlp = None
    _NLP_CACHE[lang] = nlp
    return nlp


def get_stopwords(lang: str = "fr") -> set[str]:
    """Return the stopword set for ``lang`` (cached).

    French uses the curated list shipped with the package; German and Italian
    reuse their spaCy model's default stopwords when the model is available,
    and an empty set otherwise.
    """
    if lang in _STOPWORDS_CACHE:
        return _STOPWORDS_CACHE[lang]
    words: set[str]
    if lang == "fr":
        words = create_stopwords()
    else:
        nlp = _get_nlp(lang)
        words = set(nlp.Defaults.stop_words) if nlp is not None else set()
    _STOPWORDS_CACHE[lang] = words
    return words


def detect_language(corpus: str) -> str | None:
    """Detect the corpus language as ``fr``/``de``/``it``, else ``None``.

    ``None`` means the text is not one of the supported preprocessing
    languages (e.g. English) and should be discarded upstream.

    Parameters
    ----------
    corpus : str
        Corpus to inspect.

    Returns
    -------
    str | None
        The two-letter language code, or ``None`` when unsupported.
    """
    detected_language = detector.detect_language_of(corpus)
    if detected_language is None:
        return None
    return _LANGUAGE_CODES.get(detected_language)


def define_languages(corpus: str) -> bool:
    """Backward-compatible check: ``True`` only when the corpus is French."""
    return detect_language(corpus) == "fr"


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


def lemmatize(
    list_words: list[str],
    allowed_postags: list[str] = ["NOUN", "ADJ", "VERB", "ADV"],
    lang: str = "fr",
) -> str:
    """
    Lemmatize a list of words in the given language.

    Parameters
    ----------
    list_words : list[str]
              A list of words of an article corpus.
    allowed_postags : list[str]
              A list of allowed POS tags.
    lang : str
              Language code (``fr``/``de``/``it``). When no spaCy model is
              available for it, the raw tokens are returned unchanged so
              downstream TF-IDF still has content.

    Returns
    -------
    list_lemmatized : str
              The lemmatized, POS-filtered words joined by spaces.
    """
    nlp = _get_nlp(lang)
    if nlp is None:
        return " ".join(list_words)

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

    bigram = phrases.Phrases(sentence_stream, min_count=2, threshold=0.85)

    trigram = phrases.Phrases(
        bigram[sentence_stream], min_count=2, threshold=0.85
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

    if len(joined_corpus) < 5:
        common_and_unique_words = TfidfVectorizer(min_df=1, max_df=1.0)
    else:
        common_and_unique_words = TfidfVectorizer(min_df=2, max_df=0.7)

    common_and_unique_words.fit(joined_corpus)

    # common_and_unique_words = TfidfVectorizer(min_df=2, max_df=0.60).fit(
    #    " ".join(list(set(doc))) for doc in list_trigrams
    # )

    # TODO: Test if is working as expected vocabulary_ attribute

    # Old code
    # list_temporary = [
    #     [
    #         word
    #         for word in doc
    #         if word not in common_and_unique_words.stop_words_
    #     ]
    #     for doc in list_trigrams
    # ]

    list_temporary = [
        [
            word
            for word in doc
            if word
            in common_and_unique_words.vocabulary_  # or vocabulary.keys() or  set(get_feature_names_out())
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
