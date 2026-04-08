# NLP Module

The NLP module handles topic generation, cluster summarization, LLM prompting, and LLM backend abstraction.

Source file: [src/literev/libs/nlp.py](../src/literev/libs/nlp.py)

---

## Responsibilities

1. **Cluster labeling** — generate topic phrases and summary paragraphs for each cluster using LLM
2. **LLM backend abstraction** — unified interface for OpenAI and Hactar (Ollama) backends
3. **Token budget management** — respect context window limits using tiktoken
4. **Vector search** — find relevant document chunks from ChromaDB

---

## Model Configuration

```python
# Embedding model
EMBEDDING_MODEL = "text-embedding-3-large"

# Default LLM for local (Ollama/Hactar) backend
LLM_MODEL = "mistral-small3.1:24b"
LLM_MODEL_MAX_TOKENS = 128000
TOKEN_LIMIT = 127600   # leave 400 tokens of headroom

# Number of chunks to retrieve per query
RELEVANT_K = 10
```

### Supported local models

| Model | Context size | Encoding |
|---|---|---|
| `mistral-small3.1:24b` | 128,000 | cl100k_base |
| `qwen2.5:32b` | 128,000 | cl100k_base |
| `gemma3:27b` | 128,000 | cl100k_base |
| `yi:34b` | 128,000 | cl100k_base |
| `phi3:14b` | 128,000 | cl100k_base |

Token counting uses `tiktoken` with `cl100k_base` encoding for all models.

---

## Cluster Representative Documents

```python
def get_top_documents_from_cluster(
    cluster: Cluster,
    n: int = 10,
) -> list[Document]:
    """
    Returns the n most representative documents for a cluster.
    
    Algorithm:
    1. Load HDBSCAN membership probabilities for all cluster documents
    2. Load document ID list in cluster order
    3. Return n documents with highest membership probability
    
    These documents are the most "central" to the cluster's topic.
    """
```

HDBSCAN membership probability ranges from 0 to 1. Documents with probability close to 1 are dense cluster members; those close to 0 are borderline.

---

## LLM Backend Functions

### OpenAI backend

```python
def call_chatgpt(
    prompt: str,
    api_key: str = settings.OPENAI_API_KEY,
) -> str:
    """
    Calls OpenAI Chat Completions API.
    Model: gpt-4.1-mini
    Returns: response text string
    """
```

### Hactar/Ollama backend

```python
def call_model(
    prompt: str,
    api_key: str,
) -> str:
    """
    Calls Hactar or Open WebUI API endpoints.
    Compatible with any OpenAI-compatible local server.
    
    Sets headers, sends prompt, returns LLM response text.
    Model: LLM_MODEL (default: mistral-small3.1:24b)
    """
```

Backend selection is controlled by `USE_HACTAR_LLM` in Django settings:

```python
if settings.USE_HACTAR_LLM:
    response = call_model(prompt, settings.HACTAR_API_KEY)
else:
    response = call_chatgpt(prompt, settings.OPENAI_API_KEY)
```

---

## Prompt Construction

```python
def build_prompt(
    cluster: Cluster,
    USE_HACTAR_LLM: bool,
) -> str:
    """
    Builds a prompt for cluster summarization.
    
    Includes:
    - System instruction (role: French legal expert)
    - Top-10 representative document texts (truncated to TOKEN_LIMIT)
    - Task: generate topic label + summary paragraph
    
    Returns: complete prompt string
    """
```

The prompt is truncated to `TOKEN_LIMIT` tokens using tiktoken before sending. If the top-10 documents exceed the limit, the least representative documents are dropped first.

---

## Cluster Labeling Functions

### Topic description

```python
def nlp_topic_description(
    cluster: Cluster,
    USE_HACTAR_LLM: bool = settings.USE_HACTAR_LLM,
) -> str:
    """
    Generates a short topic label (keyword phrase) for a cluster.
    
    Example output: "licenciement abusif — faute grave — contrat de travail"
    
    The topic is stored in Cluster.topic.
    """
```

### Cluster summary

```python
def get_cluster_summary(
    cluster: Cluster,
    USE_HACTAR_LLM: bool = settings.USE_HACTAR_LLM,
) -> str:
    """
    Generates a descriptive summary paragraph for a cluster.
    Summarizes the common legal themes, rules, and patterns
    across the cluster's representative documents.
    
    The summary is stored in Cluster.summary.
    """
```

---

## Vector Search (ChromaDB)

```python
def get_best_chunk_documents(
    collection,           # ChromaDB collection
    embedded_query,       # query embedding vector
    record_keys: list[str],
) -> ...:
    """
    Searches ChromaDB for the most relevant chunks given an embedded query.
    Filters by record_keys (document scope).
    Returns top-RELEVANT_K chunks.
    """

def create_context(documents: list) -> str:
    """
    Builds a single context string from multiple document chunks.
    Used as input to the LLM for answer generation.
    """
```

---

## Token Budget Management

The module uses `tiktoken` to ensure prompts stay within context window limits:

```python
import tiktoken

ENCODING = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text))

def truncate_to_limit(text: str, limit: int = TOKEN_LIMIT) -> str:
    """Truncates text to fit within token limit."""
    tokens = ENCODING.encode(text)
    if len(tokens) <= limit:
        return text
    return ENCODING.decode(tokens[:limit])
```

This is critical for large document sets where concatenated context might exceed the model's context window.

---

## Integration with Pipeline

The NLP module is called at the end of the clustering stage:

```python
# In Celery task (tasks.py)
@app.task
def generate_cluster_labels_task(project_id: int) -> None:
    project = Project.objects.get(pk=project_id)
    for cluster in Cluster.objects.filter(project=project):
        cluster.topic = nlp_topic_description(cluster)
        cluster.summary = get_cluster_summary(cluster)
        cluster.save()
```

---

## Adding a New LLM Backend

To add a new LLM backend:

1. Add a new function following the `call_chatgpt` / `call_model` signature:
   ```python
   def call_my_llm(prompt: str, api_key: str) -> str:
       ...
   ```

2. Add the backend selection to `settings.py`:
   ```python
   USE_MY_LLM = env.bool("USE_MY_LLM", default=False)
   ```

3. Update the backend dispatch in `nlp.py`:
   ```python
   if settings.USE_MY_LLM:
       response = call_my_llm(prompt, settings.MY_LLM_API_KEY)
   elif settings.USE_HACTAR_LLM:
       response = call_model(prompt, settings.HACTAR_API_KEY)
   else:
       response = call_chatgpt(prompt, settings.OPENAI_API_KEY)
   ```

For RAG-specific backends, also update `rag_classes.py` (see [rag.md](rag.md)).
