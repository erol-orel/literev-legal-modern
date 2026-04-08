# Scoring

The scoring module provides document relevance scoring, faithfulness evaluation for RAG answers, and keyword-based sorting.

Source file: [src/literev/libs/scoring.py](../src/literev/libs/scoring.py)

---

## Faithfulness Scoring

Faithfulness measures how well an LLM-generated answer is supported by the retrieved citation context. A high score means the answer closely follows the source text; a low score suggests hallucination.

### get_faithfulness_score

```python
def get_faithfulness_score(
    query: str,
    response: str,
    citation: list[str],
    use_HHEM: bool = False,
) -> float:
    """
    Scores the faithfulness of `response` to `citation`.
    
    Parameters
    ----------
    query : str
        The original user question.
    response : str
        The LLM-generated answer.
    citation : list[str]
        Retrieved document chunks used as context.
    use_HHEM : bool
        If True, uses FaithfulnesswithHHEM (Hughes Hallucination Evaluation Model)
        instead of standard Ragas Faithfulness.
    
    Returns
    -------
    float
        Score in [0.0, 1.0]. 0.0 = unfaithful / hallucinated, 1.0 = fully supported.
    """
```

**Score interpretation:**

| Range | Interpretation |
|---|---|
| `0.8 – 1.0` | Answer is well-supported by the citation context |
| `0.5 – 0.8` | Moderate support — some claims may be inferred |
| `< 0.5` | Low support — likely contains hallucinated claims |
| `0.0` | Reserved for invalid/empty answers (not a scored answer) |

**Backend options:**
- **Ragas Faithfulness** (default): NLI-based faithfulness metric from the `ragas` library
- **FaithfulnesswithHHEM** (`use_HHEM=True`): Hughes Hallucination Evaluation Model — a cross-encoder specifically trained to detect hallucination

### HactarFaithfulnessLLM

Custom LLM wrapper for ragas when using the Hactar (Ollama) backend:

```python
class HactarFaithfulnessLLM(api_key: str, base_url: str, model: str):
    def _call(self, prompt: str) -> str:
        """Async LLM call to Hactar endpoint."""
    
    def generate(self, prompts, **_kwargs) -> LLMResult:
        """Generates using ragas LLMResult format."""
```

### Async batch scoring

```python
async def assign_faithfulness_scores(project_rag: ProjectRAG) -> None:
    """
    Assigns faithfulness scores to all ProjectDocumentRAG records for a RAG run.
    
    - Filters out records with empty/invalid answers → assigns 0.0
    - Calls get_faithfulness_score() for valid answers
    - Updates ProjectDocumentRAG.confidence_score
    - Cached via FAITH_CACHE to avoid repeated API calls
    """
```

---

## Similarity Scoring

Used for sorting documents by semantic similarity to query terms.

### get_similarity_score_phrases

```python
def get_similarity_score_phrases(string_A: str, string_B: str) -> float:
    """
    Computes semantic similarity between two text strings using spacy.
    
    Uses: fr_core_news_md model vectors
    Returns: float in [0.0, 1.0]
    """
```

### Batch similarity assignment

```python
async def assign_similarity_scores(project_rag: ProjectRAG) -> None:
    """Assigns similarity scores to ProjectDocumentRAG records.
    Similarity is computed between the RAG query and each document answer."""
```

---

## Keyword Extraction and Matching

### extract_keywords

```python
def extract_keywords(expression: str) -> list[str]:
    """
    Extracts meaningful search terms from a Boolean query expression.
    
    - Extracts quoted phrases (e.g. "faute grave")
    - Extracts bare words
    - Filters out logical operators: and, or, not (case-insensitive)
    
    Example:
        extract_keywords('emploi AND "faute grave" NOT pénale')
        → ["emploi", "faute grave", "pénale"]
    """
```

### get_most_similar_keywords

```python
def get_most_similar_keywords(
    keywords: list[str],
    columns_name: list[str],
) -> set[str]:
    """
    Finds words in `columns_name` that are semantically similar (> 0.75) to any keyword.
    Uses spacy lemmatization + fr_core_news_md vectors.
    
    Returns: set of matching column names / document field values
    """
```

Used for keyword highlighting in the document table view.

---

## Document Sorting

### By Elasticsearch score

```python
def sort_documents_by_es_score(
    project: Project,
    documents: list[Document],
) -> list[Document]:
    """Sorts Document list by Elasticsearch relevance score (descending)."""

def sort_by_es_score(
    project: Project,
    tablechoice: QuerySet[TableChoice],
) -> list[TableChoice]:
    """Sorts TableChoice queryset by document ES score (descending)."""
```

ES scores are stored when documents are collected from Elasticsearch — they reflect how well each document matches the original Boolean query.

### By keyword similarity

```python
def sort_by_keyword_score(
    project: Project,
    tablechoice: QuerySet[TableChoice],
    keyword: str,
) -> list[TableChoice]:
    """
    Sorts TableChoice by spacy similarity between document text and `keyword`.
    Uses get_similarity_score_phrases() per document.
    """
```

### By HDBSCAN topic score

```python
def get_topic_and_hdbscan_score(
    hdbscan_scores: list[float],
    project: Project,
    tablechoice: QuerySet[TableChoice],
) -> dict[int, dict[str, str | float]]:
    """
    Returns a dict mapping document_id → {topic, hdbscan_score}.
    
    hdbscan_score is the membership probability from HDBSCAN —
    higher values indicate the document is more central to its cluster.
    """
```

---

## Integration with Table Choice

The scoring module feeds into the document table rendering:

```python
# In table_choice.render_table_choice():
hdbscan_scores = get_topic_and_hdbscan_score(...)
es_sorted = sort_by_es_score(project, tablechoice)
```

Users can switch the table sort order via the UI (date / ES score / topic score).

---

## Spacy Model Dependency

All similarity and keyword functions require the French spacy model:

```bash
# Install the model (run once)
python -m spacy download fr_core_news_md

# Or via makim
makim django.install-spacy-model
```

The model is loaded lazily (on first call) to avoid startup overhead.

---

## Performance Notes

- `get_similarity_score_phrases()` loads the spacy model on first call — ~2s startup
- For batch scoring of large RAG results, `assign_faithfulness_scores()` is async — run it with `asyncio.run()` or inside a Celery task
- FAITH_CACHE prevents re-scoring documents when re-running a RAG query
- HHEM scoring (`use_HHEM=True`) is slower than standard ragas Faithfulness — use only when accuracy matters more than speed
