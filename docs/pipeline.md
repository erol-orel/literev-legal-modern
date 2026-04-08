# Data Processing Pipeline

The pipeline orchestrates the full lifecycle from raw Elasticsearch query to clustered, visualizable document sets. Source files:

- Orchestration: [src/literev/libs/pipeline.py](../src/literev/libs/pipeline.py)
- Text preprocessing: [src/literev_core/preprocessing.py](../src/literev_core/preprocessing.py)
- Clustering: [src/literev_core/clustering.py](../src/literev_core/clustering.py)
- Async tasks: [src/literev/tasks.py](../src/literev/tasks.py)

---

## Pipeline Stages

```
Stage 1: Document Collection
Stage 2: NLP Preprocessing
Stage 3: TF-IDF Vectorization
Stage 4: Dimensionality Reduction (PaCMAP)
Stage 5: Clustering (HDBSCAN + Optuna)
Stage 6: Cluster Labeling (LLM)
Stage 7: Visualization Data Persistence
```

Each stage updates `Project.step` and `Project.step_number`. The UI polls these fields to show progress.

---

## Stage 1: Document Collection

**Module:** `src/literev/libs/collectors.py`  
**Class:** `ElasticSearchCollector`

### What it does

1. Receives the user's Boolean query + date range
2. Translates the query to an Elasticsearch boolean query (via `parsing.py`)
3. Uses ES scroll API with parallel slices to retrieve all matching documents
4. Extracts 22 metadata fields per document into `MetaData` dataclass
5. Persists each document to PostgreSQL via `pipeline.create_document_db()`

### Key functions

```python
ElasticSearchCollector(index_name: str)

# Main entry point
collect_documents(
    search: str,
    date_begin: datetime.date,
    date_end: datetime.date,
) -> list[MetaData]

# Scrolls entire index with no filters
collect_all_documents() -> list[MetaData]

# Count-only queries (fast)
get_max_documents(search, begin, end) -> int
count_all_documents() -> int
```

### MetaData dataclass

```python
@dataclass
class MetaData:
    doc_id: str           # Elasticsearch _id
    chamber: str          # coll_nom (court chamber)
    document_text: str    # full plain text
    document_html_text: str
    procedure_type: str   # procedure
    decision_type: str    # type of decision
    decision_date: str    # YYYY-MM-DD
    descriptors: str      # keywords
    summary: str          # resume
    standards: str        # normes (legal norms cited)
    result: str           # resultat
    es_score: float       # Elasticsearch relevance score
    record_key: str       # unique corpus identifier
```

### ES Scrolling

Large result sets are retrieved using ES scroll with slicing:

```python
# Parallel slices allow concurrent retrieval
# Each slice covers a disjoint subset of the index
query = {
    "slice": {"id": slice_id, "max": total_slices},
    "query": boolean_query,
    ...
}
```

This allows retrieval of tens of thousands of documents without memory overflow.

### Persistence

```python
# pipeline.py
def create_document_db(project: Project, document: MetaData) -> int:
    """Creates a Document record from MetaData. Returns new document ID."""
```

---

## Stage 2: NLP Preprocessing

**Module:** `src/literev_core/preprocessing.py`

### What it does

Cleans raw legal text into a normalized token sequence suitable for TF-IDF. Runs in parallel using Python `multiprocessing`.

### Processing steps per document

1. **Language detection** — `lingua` library detects if text is French; non-French documents are rejected
2. **spacy pipeline** — `fr_core_news_md` model:
   - Tokenization
   - Lemmatization (reduces inflected forms to lemma)
   - POS filtering (keeps nouns, verbs, adjectives; removes punctuation, stopwords)
3. **Stopword removal** — French spacy stopwords
4. **Corpus cleaning** — removes n-grams that are too common (appear in >80% of docs) or too rare (appear in <2 docs)

### Key functions

```python
def clean_corpus(corpus: str) -> str:
    """Pre-processing, tokenization, lemmatization, stopword removal.
    Returns cleaned token string."""

def clean_corpus_mp(corpus: str, pk: int) -> tuple[str, int]:
    """Multiprocessing version. Also runs language detection.
    Returns (cleaned_corpus, document_id). Returns ('', pk) if not French."""

def prepare_document(document: Document) -> Optional[str]:
    """Full preparation pipeline for one Document ORM object.
    Returns None if document is not French or results in empty corpus."""

def preprocessing_mp(pk_list: list[int], corpuses: list[str]) -> tuple[set[int], list[str]]:
    """Batch multiprocessing. Returns (rejected_ids, cleaned_corpuses)."""

def preprocess_documents(list_trigrams: list[list[str]]) -> list[str]:
    """Removes overly common and overly rare n-grams from the cleaned corpus."""
```

### Multiprocessing pattern

```python
# Uses Python multiprocessing.Pool
with Pool(NUMBER_THREADS_ALLOWED) as pool:
    results = pool.starmap(clean_corpus_mp, zip(corpuses, pk_list))

rejected_ids = {pk for corpus, pk in results if corpus == ''}
cleaned = [corpus for corpus, _ in results if corpus != '']
```

---

## Stage 3: TF-IDF Vectorization

**Module:** `src/literev_core/clustering.py`  
**Function:** `create_tfidf_matrix()`

```python
def create_tfidf_matrix(
    corpuses: list[str],
    min_df: int = 2,
    max_df: float = 0.8,
    ngram_range: tuple[int, int] = (1, 3),
    sublinear_tf: bool = True,
) -> csr_matrix:
```

- Uses `sklearn.TfidfVectorizer` with French-aware settings
- `min_df=2`: ignores terms appearing in fewer than 2 documents
- `max_df=0.8`: ignores terms appearing in more than 80% of documents
- `ngram_range=(1,3)`: unigrams, bigrams, and trigrams
- `sublinear_tf=True`: applies log normalization to term frequencies
- Returns a sparse matrix `(n_documents × n_features)`

---

## Stage 4: Dimensionality Reduction (PaCMAP)

**Module:** `src/literev_core/clustering.py`  
**Class:** `PacMapHDBScan`

PaCMAP (Pairwise Controlled Manifold Approximation) reduces the high-dimensional TF-IDF matrix to 2D. The resulting coordinates are stored in `ClusterElement.pos_x` / `ClusterElement.pos_y`.

```python
def pacmap_default(tf_idf: csr_matrix) -> npt.NDArray[np.float64]:
    """Default PaCMAP with fixed parameters. Returns (n_docs, 2) array."""
```

**Why PaCMAP over UMAP?**
PaCMAP explicitly balances near-neighbor (local structure) and far-pair (global structure) preservation, making it more stable for downstream density-based clustering.

**Key parameters (tuned by Optuna):**
- `n_components`: output dimensions (fixed to 2 for visualization)
- `n_neighbors`: local neighborhood size
- `MN_ratio`: ratio of mid-near pairs (global structure)
- `FP_ratio`: ratio of far pairs (prevents collapse)
- `distance`: distance metric (default: `euclidean`)

---

## Stage 5: Clustering (HDBSCAN + Optuna)

**Module:** `src/literev_core/clustering.py`  
**Classes:** `PacMapHDBScan`, `Objective`

### HDBSCAN

HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) groups documents into clusters based on density. Documents in low-density regions are labeled as noise (cluster -1).

**Why HDBSCAN?**
- No need to pre-specify the number of clusters
- Naturally handles noise (non-clusterable documents)
- Produces a cluster hierarchy for stability analysis

**Key parameters (tuned by Optuna):**
- `min_cluster_size`: minimum documents to form a cluster (critical parameter)
- `min_samples`: core point density threshold
- `cluster_selection_method`: `"eom"` (excess of mass) or `"leaf"`
- `metric`: distance metric in PaCMAP embedding space

### Optuna Hyperparameter Optimization

```python
def optimize(
    tf_idf: csr_matrix,
    n_trials: int = NUMBER_TRIALS,
    n_jobs: int = NUMBER_OPTUNA_JOBS,
    study_name: str = "...",
) -> tuple[float, dict]:
    """Returns (best_dbcv_score, best_parameters)."""
```

- Runs `n_trials` (default from env: `NUMBER_TRIALS`) Bayesian optimization trials
- Maximizes **DBCV** (Density-Based Clustering Validation) score — measures cluster compactness and separation
- Also computes **Silhouette score** as secondary metric
- Best parameters are used for final clustering

### Quality Score: DBCV

DBCV ranges from -1 to 1:
- `> 0.5`: well-separated clusters
- `0.2–0.5`: moderate clustering
- `< 0.2`: poor clustering (consider adjusting date range or query)

`Project.best_dbcv` stores this score for display.

### Main entry point

```python
def cluster_corpuses(
    corpuses: list[str],
    n_trials: int = NUMBER_TRIALS,
    n_jobs: int = NUMBER_OPTUNA_JOBS,
    study_name: str = "...",
) -> tuple[list[int], npt.NDArray[np.float64], dict]:
    """
    Full clustering pipeline.
    Returns:
        cluster_labels: list[int]   # HDBSCAN cluster ID per document (-1 = noise)
        embedding: ndarray          # (n_docs, 2) PaCMAP coordinates
        cluster_info: dict          # {cluster_id: {size, probabilities, ...}}
    """
```

---

## Stage 6: Cluster Labeling

**Module:** `src/literev/libs/nlp.py`

After clustering, each cluster is labeled using an LLM.

```python
def get_cluster_summary(cluster: Cluster, ...) -> str:
    """Generates a concise summary paragraph for a cluster."""

def nlp_topic_description(cluster: Cluster, ...) -> str:
    """Creates a short topic label (keyword phrase) for a cluster."""

def get_top_documents_from_cluster(cluster: Cluster, n: int = 10) -> list[Document]:
    """Returns the n most representative documents (highest HDBSCAN probability)."""
```

**Process:**
1. Select top-10 documents by HDBSCAN membership probability
2. Build a prompt with their preprocessed text
3. Call LLM (OpenAI or Hactar/Ollama) to generate topic + summary
4. Store in `Cluster.topic` and `Cluster.summary`

---

## Stage 7: Persistence

After clustering completes:

```python
# For each cluster label:
cluster = Cluster.objects.create(project=project, order=i, topic=..., summary=...)

# For each document in cluster:
ClusterElement.objects.create(
    document=doc,
    cluster=cluster,
    pos_x=embedding[i, 0],
    pos_y=embedding[i, 1],
)
```

The frontend then reads `ClusterElement.pos_x` / `pos_y` for scatter plot visualization.

---

## Pipeline Orchestration

```python
# pipeline.py
def running_restart(project_id: str) -> None:
    """Restores projects stuck in is_running=True state on server restart."""

def convert_to_target_type(value: str, target_type: type = str) -> ...:
    """Type conversion helper with None handling."""

def back_process(project: Project) -> None:
    """Placeholder for background process initiation."""
```

**Progress tracking pattern:**

```python
project.step = "collecting"
project.step_number = 1
project.is_running = True
project.save()

# ... do work ...

project.step = "preprocessing"
project.step_number = 2
project.save()

# ... etc ...

project.is_finish = True
project.is_running = False
project.save()
```

---

## Error Recovery

- If the pipeline fails mid-run, `Project.is_running` stays `True`
- `running_restart()` is called on application startup to reset stuck projects
- Celery task IDs are stored in `Project.actual_task_code` for revocation
- For manual recovery: `makim django.shell` → set `project.is_running = False; project.save()`

---

## Performance Tuning

| Parameter | Environment Variable | Effect |
|---|---|---|
| Preprocessing parallelism | `NUMBER_THREADS_ALLOWED` | Pool workers for `clean_corpus_mp` |
| Optuna trials | `NUMBER_TRIALS` | More trials = better clustering, slower |
| Optuna parallelism | `NUMBER_OPTUNA_JOBS` | Concurrent Optuna trials |
| ES scroll size | hardcoded in collectors.py | Adjust for memory vs. speed |

Typical pipeline times for 500 documents:
- Collection: ~30s (ES scroll)
- Preprocessing: ~60s (multiprocessing, 4 workers)
- TF-IDF: ~5s
- Optuna (50 trials): ~3–5 min
- Cluster labeling: ~30s (LLM calls)
