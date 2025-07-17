import logging
import re

import joblib
import spacy

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models.query import QuerySet
from langchain.schema import Generation, LLMResult
from langchain_core.prompt_values import StringPromptValue
from langchain_openai import ChatOpenAI
from openai import OpenAI as OpenAIClient
from ragas.dataset_schema import SingleTurnSample
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, FaithfulnesswithHHEM

from literev.libs.data_files import get_dataframe_project, get_es_scores
from literev.models import (
    ClusterElement,
    Document,
    Project,
    ProjectDocumentRAG,
    ProjectRAG,
    TableChoice,
)

logging.basicConfig(level=logging.INFO)
NLP = spacy.load("fr_core_news_md")

llm = ChatOpenAI(model="gpt-4o-mini")
evaluator_llm = LangchainLLMWrapper(llm)


class HactarFaithfulnessLLM:
    """
    Minimal LLM wrapper for Ragas faithfulness scoring.
    Can point at any OpenAI-compatible endpoint (Hactar or OpenAI).
    """

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAIClient(api_key=api_key, base_url=base_url)
        self.model = model

    async def _call(self, prompt: str) -> str:
        resp = await sync_to_async(self.client.chat.completions.create)(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.0,
        )
        return resp.choices[0].message.content

    async def generate(self, prompts, **_kwargs) -> LLMResult:
        if isinstance(prompts, StringPromptValue):
            text = prompts.text
        elif isinstance(prompts, list):
            text = prompts[0]
        else:
            text = str(prompts)

        content = await self._call(text)
        return LLMResult(
            generations=[[Generation(text=content)]],
            llm_output={},
        )


async def get_faithfulness_score(
    query: str,
    response: str,
    citation: list[str],
    use_HHEM: bool = False,
) -> float:
    """
    Evaluates a sample and returns faithfulnesswithHHEM score
    given a simple sample. To generate the score uses a
    OpenAI as LLM evaluator.

    Parameters
    ----------
    query : str
        question or query used in RAG.
    response : str
        a string response from rag response
    citation : list[str]
        A portion from document which is used to generate the response
        in RAG.

    Returns
    -------
    float
        faithfulnesswithHHEM score between string_A and string_B
    """

    if settings.USE_HACTAR_LLM:
        api_key = settings.HACTAR_API_KEY
        base_url = "https://hactar.unige.ch/api"
        model = "mistral-small3.1:24b"
    else:
        api_key = settings.OPENAI_API_KEY
        base_url = "https://api.openai.com/v1"
        model = "gpt-4o-mini"

    llm = HactarFaithfulnessLLM(
        api_key=api_key, base_url=base_url, model=model
    )

    sample = SingleTurnSample(
        user_input=query,
        response=response,
        retrieved_contexts=citation,
    )

    Scorer = FaithfulnesswithHHEM if use_HHEM else Faithfulness
    scorer = Scorer(llm=llm)

    return await scorer.single_turn_ascore(sample)


async def assign_faithfulness_scores(project_rag: ProjectRAG) -> None:
    """
    Assign faithfulness scores to RAG answers for a given project_rag.

    Save the scores in the confidence_score field of ProjectDocumentRAG objects.
    Assign a score of 0.0 to invalid or placeholder answers.
    """
    rag_documents = ProjectDocumentRAG.objects.filter(project_rag=project_rag)
    query = project_rag.query.strip()

    INVALID_ANSWERS = {
        "",
        "réponse non disponible",
        "no content available.",
        "no content available",
        "error generating response.",
    }

    async for rag_document in rag_documents:
        answer = (rag_document.answer or "").strip().lower()

        # Preventing the false 1.0 score issue
        if answer in INVALID_ANSWERS:
            rag_document.confidence_score = 0.0
            await rag_document.asave()
            continue

        # Ensure citation_context is not empty
        citation_context = (
            rag_document.citation_context
            if rag_document.citation_context
            and len(rag_document.citation_context) > 0
            else [rag_document.citation]
        )

        faithfulness_score = await get_faithfulness_score(
            query, rag_document.answer.strip(), citation_context
        )

        rag_document.confidence_score = faithfulness_score
        await rag_document.asave()


def get_similarity_score_phrases(string_A: str, string_B: str) -> float:
    """
    Returns similarity score between two strings.

    Parameters
    ----------
    string_A : str
        A string to compare with string_B
    string_B : str
        A string to compare with string_A

    Returns
    -------
    float
        Similarity score between string_A and string_B
    """
    tokens_A = NLP(string_A)
    tokens_B = NLP(string_B)

    return tokens_A.similarity(tokens_B)


def assign_similarity_scores(project_rag: ProjectRAG) -> None:
    """
    Asign confidence scores to RAG answers given project_rag model object database.

    Parameters
    ----------
    project_rag : ProjectRAG
        Object used related with rag documents answers

    Returns
    -------
    None

    Notes
    Saves the scores in field confidence_score from ProjectDocumentRAG objects.
    -----
    """
    rag_documents = ProjectDocumentRAG.objects.filter(project_rag=project_rag)

    for rag_document in rag_documents:
        similarity_answer_citation = get_similarity_score_phrases(
            rag_document.citation, rag_document.answer
        )

        rag_document.confidence_score = similarity_answer_citation
        rag_document.save()


def get_most_similar_keywords(
    keywords: list[str], columns_name: list[str]
) -> set[str]:
    """
    Returns a set of words that have a similarity score greater than 0.75 with the keywords

    Parameters
    ----------
    keywords : list[str]
        list of keywords fromt he query.
    columns_name : list[str]
        List of words from the the tfidf matrix.

    Returns
    -------
    set[str]
        set of most similar to keywords.
    """
    SIMILARITY_THRESHOLD = 0.75
    tfidf_keywords = set()

    for keyword in keywords:
        target_token = NLP(keyword)[0]
        target_lemma = target_token.lemma_
        target_lemma_token = NLP(target_lemma)

        similarity_scores = {}

        for word in columns_name:
            # In bigrams and trigams words are separated by _
            if "_" in word:
                word = word.replace("_", " ")

            word_token = NLP(word)
            similarity = target_lemma_token.similarity(word_token)

            # for bigrams and trigrams go back its original separation "_"
            if " " in word:
                word = word.replace(" ", "_")

            similarity_scores[word] = similarity

        for key in similarity_scores.keys():
            if similarity_scores[key] >= SIMILARITY_THRESHOLD:
                tfidf_keywords.add(key)

    return tfidf_keywords


def extract_keywords(expression: str) -> list[str]:
    """
    Returns a list of keywords from the query

    Parameters
    ----------
    expresion : str
        A query string

    Returns
    -------
    list[str]
        list of keywords from the query
    """
    # Regular expression to match quoted phrases and standalone words
    expression = expression.lower()
    pattern = r'"([^"]+)"|(\b\w+\b)'

    # Use `findall` to extract all matches of the pattern in the expression
    matches = re.findall(pattern, expression)

    # Extract matched groups from the tuple returned by findall
    phrases = [match[0] or match[1] for match in matches]

    # Logical operators to exclude
    logical_operators = {"and", "or", "not"}

    # Filter out logical operators
    result = [phrase for phrase in phrases if phrase not in logical_operators]

    return result


def sort_documents_by_es_score(
    project: Project, documents: list[Document]
) -> list[Document]:
    """
    Sort tablechoice object by elasticsearch score.

    Parameters
    ----------
    project : Project object
        A project related with the keywords
    documents: QuerySet[Documents]
        A set of document objects.

    Returns
    -------
    list[Document]
        List of sorted document objects.
    """
    scores = get_es_scores(project)

    if scores:
        sorted_list = sorted(
            documents,
            key=lambda x: scores[x.id],
            reverse=True,
        )

        return sorted_list

    logging.warning(f"There is no es scores for project : {project.id}")

    return list(documents)


def sort_by_es_score(
    project: Project, tablechoice: QuerySet[TableChoice]
) -> list[TableChoice]:
    """
    Sort tablechoice object by elasticsearch score.

    Parameters
    ----------
    project : Project object
        A project related with the keywords
    tablechoice: QuerySet[TableChoice]
        A set of tablechoice object, used to show table select page.

    Returns
    -------
    list[TableChoice]
        List of sorted tablechoice objects.
    """
    scores = get_es_scores(project)

    if scores:
        sorted_list = sorted(
            list(tablechoice),
            key=lambda x: scores[x.document.id],
            reverse=True,
        )

        return sorted_list

    logging.warning(f"There is no es scores for project : {project.id}")

    return list(tablechoice)


def sort_by_keyword_score(
    project: Project, tablechoice: QuerySet[TableChoice], keyword: str
) -> list[TableChoice]:
    """
    Sort tablechoice object by keyword.

    Parameters
    ----------
    project : Project object
        A project related with the keywords
    tablechoice: QuerySet[TableChoice]
        A set of tablechoice object, used to show table select page.
    keyword : str
        keyword used to sort the tablechoice objects

    Returns
    -------
    list[TableChoice]
        List of sorted tablechoice objects.
    """

    df = get_dataframe_project(project)

    if keyword in df:
        scores = df[keyword]
        sorted_list = sorted(
            tablechoice,
            key=lambda x: scores.loc[x.document.id],
            reverse=True,
        )
        return sorted_list

    logging.warning(f"There is no keyword in the tf idf matrix: {keyword}")

    return list(tablechoice)


def get_topic_and_hdbscan_score(
    hdbscan_scores: list[float],
    project: Project,
    tablechoice: QuerySet[TableChoice],
) -> dict[int, dict[str, str | float]]:
    """
    Return a dict containing the scores and topic for documents.

    Parameters
    ----------
    project : Project object
        A project related with topic and scores.

    Returns
    -------
    topic_scores_dict : dict
        A dict containing the scores and topic for documents.
    """
    scores_dict = {}
    topic_scores_dict = {}

    list_id_docs = joblib.load(
        settings.ARTICLE_DATA / f"id_list_project_{project.id}.pkl"
    )

    for doc_id, score in zip(list_id_docs, hdbscan_scores):
        scores_dict[doc_id] = score

    selected_document_ids = [tc.document.id for tc in tablechoice]
    cluster_elements = ClusterElement.objects.filter(
        cluster__project=project, document_id__in=selected_document_ids
    )

    for cluster_e in cluster_elements:
        if cluster_e.cluster.order == -1:
            text_topic = cluster_e.cluster.topic

        else:
            text_topic = (
                "Topic "
                + str(cluster_e.cluster.order)
                + " : "
                + cluster_e.cluster.topic
            )

        topic_scores_dict[cluster_e.document.id] = {
            "topic": text_topic,
            "hdbscan_score": scores_dict[cluster_e.document.id] * 100,
        }

    return topic_scores_dict
