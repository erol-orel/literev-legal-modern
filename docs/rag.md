# RAG (Retrieval-Augmented Generation)

The RAG module answers user questions against a selected corpus of legal documents. Each document is analyzed independently, then a summary is produced across all answers.

Source files:
- Core pipeline: [src/literev/libs/rag_pdf.py](../src/literev/libs/rag_pdf.py)
- LLM backends: [src/literev/libs/rag_classes.py](../src/literev/libs/rag_classes.py)
- Confidence scoring: [src/literev/libs/scoring.py](../src/literev/libs/scoring.py)

---

## Architecture Overview

```
User question + document IDs
        │
        ▼
ProjectRAG created (status: in_progress)
        │
        ▼
Celery task: RagAnswersManager.run()
        │
        ├─► For each document:
        │       │
        │       ├─ prepare_chunks(): split text into overlapping chunks
        │       ├─ ChromaDB: embed chunks (text-embedding-3-large)
        │       ├─ Retrieve top-k relevant chunks for the query
        │       ├─ Generate answer (gpt-4.1-mini or Ollama)
        │       ├─ Extract citation via fuzzy matching (rapidfuzz)
        │       ├─ Score confidence (ragas faithfulness)
        │       └─ Save ProjectDocumentRAG
        │
        ├─► Generate overall summary (OpenAISummaryGenerator)
        │
        ├─► For closed-ended questions: generate classification stats
        │       └─ Save ProjectRAGStats
        │
        └─► ProjectRAG.status = "completed"
```

---

## Caching Strategy

All expensive operations are file-cached to avoid redundant API calls on re-runs.

```python
# In rag_pdf.py
RET_CACHE      = CacheFile(cache_dir / "retrieval")     # chunk retrieval results
AUG_CACHE      = CacheFile(cache_dir / "augmentation")  # embedding results
GEN_CACHE      = CacheFile(cache_dir / "generation")    # LLM answer outputs
DOCUMENT_CACHE = CacheFile(cache_dir / "documents")     # document chunk splits
FAITH_CACHE    = CacheFile(cache_dir / "faithfulness")  # confidence scores
```

Cache location: `LITEREV_CACHE_DIR` environment variable.

Decorator pattern:
```python
@ret_cache
def retrieve(query: str) -> list[str]:
    # Only called on cache miss
    ...
```

---

## Text Chunking

```python
def prepare_chunks(text: str) -> list[str]:
    """Splits document text into overlapping chunks using LangChain's
    RecursiveCharacterTextSplitter."""
```

Uses `RecursiveCharacterTextSplitter` with:
- `chunk_size`: ~500 tokens
- `chunk_overlap`: ~50 tokens (prevents answers from spanning chunk boundaries)
- Splits on: paragraphs → sentences → words (recursive fallback)

Chunks are stored in ChromaDB with the document's `record_key` as namespace.

---

## LLM Backends

### OpenAI (default)

```python
def get_rag_generator(USE_HACTAR_LLM: bool, ...) -> Union[HactarGen, OpenAIGen]:
    """Returns the appropriate LLM generator based on settings."""
```

**Models:**
- Generation: `gpt-4.1-mini`
- Embeddings: `text-embedding-3-large`

**Configuration:**
```
OPENAI_API_KEY=sk-...
USE_HACTAR_LLM=false
```

### Hactar / Ollama (local)

```python
class HactarGen(HactarConnectionHelper, GenerationBase):
    default_model_name = "mistral-small3.1:24b"
    api_base_url = "https://hactar.unige.ch"
```

**Configuration:**
```
USE_HACTAR_LLM=true
HACTAR_API_KEY=...
HACTAR_VERIFY_SSL=true
```

Hactar is an Ollama-compatible API endpoint. The same `HactarGen` class works with any OpenAI-compatible local server.

**Available local models:**
| Model | Context | Encoding |
|---|---|---|
| `mistral-small3.1:24b` | 128,000 | cl100k_base |
| `qwen2.5:32b` | 128,000 | cl100k_base |
| `gemma3:27b` | 128,000 | cl100k_base |
| `yi:34b` | 128,000 | cl100k_base |
| `phi3:14b` | 128,000 | cl100k_base |

### HactarAug (Embeddings via Hactar)

```python
class HactarAug(HactarConnectionHelper, AugmentedBase):
    default_model_name = "mxbai-embed-large:latest"
    default_top_k = 3
```

Used when `USE_HACTAR_LLM=true` — replaces OpenAI embeddings with a local embedding model.

---

## Answer Generation

### Per-document workflow

```python
def get_answer_document_worker(document_id: int, ...) -> dict:
    """Processes a single document for RAG. Returns answer dict."""
```

Steps:
1. Load `Document` from DB
2. Split into chunks (cached)
3. Embed chunks into ChromaDB (cached)
4. Retrieve top-`RELEVANT_K` chunks for the query (cached, `RELEVANT_K=10`)
5. Build context string from retrieved chunks
6. Generate answer with LLM (cached)
7. Return `{answer, citation, citation_context}`

### Pydantic output models

Answers are structured using Pydantic models with OpenAI's structured output:

```python
class RAGAnswer(BaseModel):
    answer: str        # answer text
    citation: str      # verbatim quote from document

class SummaryGeneralAnswer(BaseModel):
    summary: str       # overall summary across all documents

class ClosedAnswerClassification(BaseModel):
    classification: str    # "yes" | "no" | "maybe"
    reasoning: str
```

If the LLM cannot find a relevant answer in the document, it returns an empty answer — these are filtered out before summary generation.

---

## Citation Extraction

Citations are extracted using fuzzy string matching:

```python
import rapidfuzz

# Find the best matching substring in the raw document
citation_match = rapidfuzz.process.extractOne(
    query=llm_citation,
    choices=document_sentences,
    scorer=rapidfuzz.fuzz.partial_ratio,
)
```

The `citation_context` JSON field stores surrounding text for display.

---

## Confidence Scoring

### Ragas Faithfulness

```python
# scoring.py
def get_faithfulness_score(
    query: str,
    response: str,
    citation: list[str],
    use_HHEM: bool = False,
) -> float:
    """
    Scores how faithful the answer is to the retrieved context.
    Returns float in [0.0, 1.0].
    """
```

- Uses `ragas.metrics.Faithfulness` by default
- Optionally uses `FaithfulnesswithHHEM` (HHEM = Hughes Hallucination Evaluation Model)
- Score interpretation:
  - `> 0.8`: high confidence, answer well-supported by citation
  - `0.5–0.8`: moderate confidence
  - `< 0.5`: low confidence, possible hallucination
  - `0.0`: invalid/empty answer (not a low-confidence valid answer)

### Async assignment

```python
async def assign_faithfulness_scores(project_rag: ProjectRAG) -> None:
    """Assigns faithfulness scores to all ProjectDocumentRAG records.
    Sets score=0.0 for invalid answers."""
```

---

## Question Classification

The RAG pipeline automatically detects whether the question is open-ended or closed-ended:

```python
class QuestionClassifier:
    """Classifies questions as open-ended or closed-ended using LLM."""
```

For **closed-ended** questions (yes/no/maybe answers):
1. Each per-document answer is classified into one of: `yes`, `no`, `maybe`
2. `StatsGenerator` aggregates counts and percentages
3. Results stored in `ProjectRAGStats.classification_stats`

For **open-ended** questions:
- No classification step
- Only per-document answers + overall summary

---

## Summary Generation

```python
class OpenAISummaryGenerator:
    """Generates an overall summary from all per-document answers."""
```

After all per-document answers are collected:
1. Filter out empty/invalid answers
2. Concatenate valid answers (respecting token limit `TOKEN_LIMIT=127,600`)
3. Generate a unified summary paragraph
4. Store in `ProjectRAG.summary_answer`

---

## Mineure / Majeure Classification (Legal Structure)

For legal texts, the RAG pipeline can optionally classify document sections:

```python
class MinorMajorPair(BaseModel):
    mineure: str    # minor premise (facts)
    majeure: str    # major premise (legal rule)
```

See [legal.md](legal.md) for the full French legal text classification documentation.

---

## Status Lifecycle

```
in_progress
    │
    ▼
questioning_documents    ← per-document LLM calls
    │
    ▼
generating_scores        ← ragas faithfulness computation
    │
    ▼
generating_summary       ← cross-document summary
    │
    ▼
generating_statistics    ← classification stats (closed-ended only)
    │
    ▼
tagging_considerations   ← optional consideration tagging
    │
    ▼
completed ─── (or) ───► failed
```

Each status transition is written to the DB immediately so the frontend can show progress.

---

## Configuration Reference

| Variable | Default | Effect |
|---|---|---|
| `OPENAI_API_KEY` | — | Required for OpenAI backend |
| `USE_HACTAR_LLM` | `false` | Switch to Hactar/Ollama backend |
| `HACTAR_API_KEY` | — | Required when `USE_HACTAR_LLM=true` |
| `HACTAR_VERIFY_SSL` | `true` | SSL verification for Hactar endpoint |
| `LITEREV_CACHE_DIR` | — | Directory for file caches |
| `MIN_CONFIDENCE` | `0.5` | Minimum confidence to include answer in summary |

---

## Token Budget

The `TOKEN_LIMIT = 127,600` constant in `nlp.py` ensures prompts stay within the context window of 128K-token models. `tiktoken` (cl100k_base encoding) counts tokens before sending to the LLM.

If the combined document context exceeds the token limit, the least relevant chunks are dropped until the prompt fits.

---

## Testing RAG

```python
# conftest.py provides:
@pytest.fixture
def celery_worker_parameters() -> dict:
    return {"pool": "prefork", "concurrency": 1}

# Example test pattern
def test_rag_creates_project_rag(authenticated_api_client, project, document):
    response = authenticated_api_client.post(
        f"/api/project/{project.id}/rag/",
        {"query": "Quel est le critère ?", "documents_ids": [document.id]},
    )
    assert response.status_code == 201
    assert response.data["status"] == "in_progress"
```

Use real Celery worker (`celery_worker` fixture) for integration tests — do not mock the task queue.
