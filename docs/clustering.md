# Clustering

The clustering module transforms preprocessed legal text into topic groups using a TF-IDF → PaCMAP → HDBSCAN pipeline with Optuna-driven hyperparameter optimization.

Source files:
- Core algorithms: [src/literev_core/clustering.py](../src/literev_core/clustering.py)
- Django orchestration: [src/literev/libs/clustering.py](../src/literev/libs/clustering.py)

---

## Algorithm Pipeline

```
Preprocessed text corpus (list[str])
        │
        ▼
1. TF-IDF Vectorization  →  sparse matrix (n_docs × n_terms)
        │
        ▼
2. PaCMAP Projection     →  dense array (n_docs × 2)
        │
        ▼
3. HDBSCAN Clustering    →  cluster labels (n_docs,)
        │
        ▼
4. Quality Evaluation    →  DBCV score, Silhouette score
        │
        ▼
5. Django Persistence    →  Cluster + ClusterElement records
```

Steps 2–4 run inside an Optuna hyperparameter optimization loop — the best-scoring parameter combination is selected.

---

## TF-IDF Vectorization

```python
def create_tfidf_matrix(
    corpuses: list[str],
    min_df: int = 2,
    max_df: float = 0.8,
    ngram_range: tuple[int, int] = (1, 3),
    sublinear_tf: bool = True,
) -> csr_matrix:
```

Uses `sklearn.TfidfVectorizer`:

| Parameter | Value | Rationale |
|---|---|---|
| `min_df=2` | ignore terms in <2 docs | removes hapax legomena |
| `max_df=0.8` | ignore terms in >80% docs | removes near-stopwords |
| `ngram_range=(1,3)` | unigrams through trigrams | captures legal phrases like "faute grave" |
| `sublinear_tf=True` | log(tf) instead of raw tf | dampens effect of very frequent terms |

Returns a `scipy.sparse.csr_matrix` — memory-efficient for large vocabularies.

---

## PaCMAP Dimensionality Reduction

### Why PaCMAP?

PaCMAP (Pairwise Controlled Manifold Approximation) maps high-dimensional TF-IDF vectors to 2D while explicitly balancing:
- **Local structure** (near-neighbor pairs) — preserves cluster shape
- **Global structure** (far pairs) — prevents collapse into a single blob
- **Mid-range structure** (mid-near pairs) — controlled by `MN_ratio`

This makes it more stable than UMAP for density-based clustering as a downstream step.

### Class interface

```python
class PacMapHDBScan:
    def __init__(
        self,
        Matrix: csr_matrix,                        # TF-IDF input
        # PaCMAP parameters
        n_components: int = 2,
        n_neighbors: int = 10,
        MN_ratio: float = 0.5,
        FP_ratio: float = 2.0,
        init: str = "pca",
        distance: str = "euclidean",
        # HDBSCAN parameters
        min_cluster_size: int = 5,
        min_samples: int = 1,
        cluster_selection_method: str = "eom",
        metric: str = "euclidean",
    ) -> None
    
    def evaluate(self) -> float:
        """Run PaCMAP + HDBSCAN. Returns DBCV score."""
    
    def _project_with_pacmap_and_cluster(self) -> None:
        """Internal: runs PaCMAP then HDBSCAN, stores results."""
    
    def _compute_coherence_value(self) -> None:
        """Computes DBCV and Silhouette scores from clustering result."""
```

### Default PaCMAP (no optimization)

```python
def pacmap_default(tf_idf: csr_matrix) -> npt.NDArray[np.float64]:
    """Fixed-parameter PaCMAP. Returns (n_docs, 2) array.
    Used when Optuna optimization is skipped."""
```

---

## HDBSCAN Clustering

HDBSCAN (Hierarchical Density-Based Spatial Clustering of Applications with Noise) works in 2D PaCMAP space.

### Key properties

- **No cluster count needed** — automatically determines how many clusters exist
- **Noise handling** — low-density documents get label `-1` (noise cluster)
- **Hierarchy** — builds a complete cluster hierarchy, then extracts flat clusters at the optimal level
- **Soft clustering** — each document has a membership probability for its cluster (used to select representative docs)

### Parameters tuned by Optuna

| Parameter | Search space | Effect |
|---|---|---|
| `min_cluster_size` | 5–50 | Minimum documents to form a cluster; higher = fewer, larger clusters |
| `min_samples` | 1–20 | Core point density threshold; higher = more noise points |
| `cluster_selection_method` | `"eom"`, `"leaf"` | EOM = stable large clusters; leaf = many small clusters |
| `metric` | `"euclidean"` | Distance metric in PaCMAP embedding space |

---

## Hyperparameter Optimization (Optuna)

```python
class Objective:
    """Optuna objective function. Wraps PacMapHDBScan.evaluate()."""
    
    def __call__(self, trial: optuna.trial.Trial) -> float:
        """One trial: sample parameters, run clustering, return DBCV score."""

def optimize(
    tf_idf: csr_matrix,
    n_trials: int = NUMBER_TRIALS,      # from env: NUMBER_TRIALS
    n_jobs: int = NUMBER_OPTUNA_JOBS,   # from env: NUMBER_OPTUNA_JOBS
    study_name: str = "...",
) -> tuple[float, dict]:
    """
    Run Bayesian hyperparameter search.
    Returns: (best_dbcv_score, best_parameters_dict)
    """
```

### Optuna strategy

Optuna uses **Tree-structured Parzen Estimators (TPE)** — a Bayesian optimization algorithm that:
1. Samples parameter combinations based on past trial results
2. Prioritizes regions of parameter space that historically score well
3. Converges faster than random search for 50+ trials

```python
study = optuna.create_study(direction="maximize")  # maximize DBCV
study.optimize(objective, n_trials=n_trials, n_jobs=n_jobs, callbacks=[logging_callback])
```

### Loading best study

```python
def retrieve_best_study(study_name: str) -> optuna.study.Study:
    """Loads a completed Optuna study from storage."""
```

---

## Quality Metrics

### DBCV (Density-Based Clustering Validation)

The primary optimization target. Measures:
- **Intra-cluster density**: how tightly packed cluster members are
- **Inter-cluster separation**: how empty the space between clusters is

Range: `-1` (worst) to `1` (best). Stored in `Project.best_dbcv`.

| Score | Interpretation |
|---|---|
| `> 0.5` | Well-separated clusters — good result |
| `0.2 – 0.5` | Moderate quality |
| `< 0.2` | Poor clustering — consider narrower query or date range |

### Silhouette Score

Secondary metric. Measures how similar each point is to its own cluster compared to other clusters. Computed alongside DBCV but not used for optimization.

---

## Main Entry Point

```python
def cluster_corpuses(
    corpuses: list[str],
    n_trials: int = NUMBER_TRIALS,
    n_jobs: int = NUMBER_OPTUNA_JOBS,
    study_name: str = "...",
) -> tuple[list[int], npt.NDArray[np.float64], dict]:
    """
    Full clustering pipeline: TF-IDF → optimize → cluster.
    
    Returns:
        cluster_labels: list[int]
            HDBSCAN cluster ID per document.
            -1 = noise (document doesn't belong to any cluster)
        embedding: ndarray of shape (n_docs, 2)
            PaCMAP 2D coordinates per document
        cluster_info: dict
            {cluster_id: {size, member_probabilities, member_doc_ids, ...}}
    """
```

---

## Persistence (Django Layer)

After `cluster_corpuses()` returns, the Django orchestration layer ([src/literev/libs/clustering.py](../src/literev/libs/clustering.py)) persists results:

```python
# For each unique cluster label (excluding -1 noise):
cluster = Cluster.objects.create(
    project=project,
    order=i,
    topic="",       # filled later by LLM
    summary="",     # filled later by LLM
)

# For each document in this cluster:
ClusterElement.objects.create(
    document=document,
    cluster=cluster,
    pos_x=embedding[doc_idx, 0],
    pos_y=embedding[doc_idx, 1],
)
```

Noise documents (label `-1`) get their own "noise" cluster or are excluded from visualization, depending on configuration.

---

## Cluster Labeling

After clustering, each cluster is labeled by an LLM. See [nlp.md](nlp.md) for details. The process:

1. Retrieve top-10 most representative documents per cluster (highest HDBSCAN membership probability)
2. Build LLM prompt with their preprocessed text
3. Generate `Cluster.topic` (short keyword phrase)
4. Generate `Cluster.summary` (descriptive paragraph)

```python
# nlp.py
def get_top_documents_from_cluster(cluster: Cluster, n: int = 10) -> list[Document]:
    """Returns n documents with highest HDBSCAN membership probability."""
```

---

## Nearest-Neighbor Lookup

The 2D embedding enables spatial queries:

```python
# table_choice.py
def neighbour_document(document: Document, project: Project) -> list[Document]:
    """Returns the 10 nearest documents to `document` in 2D PaCMAP space.
    Uses Euclidean distance on (pos_x, pos_y) from ClusterElement."""
```

This powers the "expand selection to neighbors" feature in the refinement UI — when a user marks a document as relevant, nearby documents are surfaced as candidates.

---

## Performance Tuning

| Env Variable | Default | Effect |
|---|---|---|
| `NUMBER_TRIALS` | 50 | Optuna trials; more trials = better clustering, slower |
| `NUMBER_OPTUNA_JOBS` | 4 | Parallel Optuna workers (`n_jobs`) |
| `NUMBER_THREADS_ALLOWED` | 4 | Pool workers for preprocessing (before clustering) |

**Scaling guidance:**
- `NUMBER_TRIALS=20` for quick exploration
- `NUMBER_TRIALS=100` for production-quality clustering
- `NUMBER_OPTUNA_JOBS` should not exceed available CPU cores

---

## Management Commands for Clustering

| Command | Purpose |
|---|---|
| `optimize_documents` | Run clustering optimization with advanced text analysis |
| `document_cluster_optimization` | Standalone clustering optimization |
| `fill_order_cluster` | Backfill `Cluster.order` for existing clusters |
| `run_chromadb_embeddings` | Pre-compute ChromaDB embeddings for clustered documents |

```bash
# Example: re-optimize clustering for a project
python manage.py optimize_documents --project-id 42
```
