# Architecture Overview

## What literev-legal Does

literev-legal is a legal document analysis platform for French judicial texts. It lets users:

1. Search a corpus of French legal decisions in Elasticsearch
2. Automatically cluster documents by topic using NLP + HDBSCAN
3. Iteratively refine their document set through a UI-driven selection workflow
4. Ask open-ended or closed-ended questions against their corpus using RAG (Retrieval-Augmented Generation)

---

## System Components

```
┌───────────────────────────────────────────────────────────────────────┐
│                          Browser / API Client                         │
└─────────────────────────────┬─────────────────────────────────────────┘
                              │ HTTP (Django)
┌─────────────────────────────▼─────────────────────────────────────────┐
│                          Django Application                            │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐   │
│  │  Template     │  │  REST API    │  │  Management Commands      │   │
│  │  Views        │  │  (DRF)       │  │  (CLI tools)              │   │
│  └──────┬───────┘  └──────┬───────┘  └────────────┬──────────────┘   │
│         │                 │                        │                   │
│  ┌──────▼─────────────────▼────────────────────────▼──────────────┐  │
│  │                     Business Logic (libs/)                       │  │
│  │  collectors │ pipeline │ nlp │ clustering │ rag_pdf │ parsing   │  │
│  │  table_choice │ scoring │ legal/ extraction                     │  │
│  └─────────┬──────────────────────────────────────────────────────┘  │
│            │                                                           │
│  ┌─────────▼──────────────────────────┐                              │
│  │             Celery Workers          │                              │
│  │   (async tasks: process, cluster,   │                              │
│  │    embed, generate, score)          │                              │
│  └─────────────────────────────────────┘                              │
└──────────┬──────────────┬─────────────────┬──────────────────────────┘
           │              │                 │
    ┌──────▼──────┐ ┌─────▼──────┐ ┌───────▼────────────────────────┐
    │ PostgreSQL  │ │   Redis    │ │  External Services              │
    │ (primary DB)│ │ (broker +  │ │  ┌────────────┐ ┌───────────┐  │
    │             │ │  cache)    │ │  │Elasticsearch│ │ OpenAI    │  │
    └─────────────┘ └────────────┘ │  │(doc search) │ │(LLM/embed)│  │
                                   │  └────────────┘ └───────────┘  │
                                   │  ┌────────────┐                 │
                                   │  │ ChromaDB   │                 │
                                   │  │(vector DB) │                 │
                                   │  └────────────┘                 │
                                   └─────────────────────────────────┘
```

---

## Data Flow: Full Pipeline

### 1. Document Collection

```
User submits query + date range
        │
        ▼
parsing.py: tokenize + validate Boolean query
        │
        ▼
collectors.py: ElasticSearchCollector
  └── scroll ES index with boolean query
  └── extract MetaData (22 fields) per document
        │
        ▼
pipeline.py: create_document_db()
  └── persist Document records to PostgreSQL
```

### 2. NLP Preprocessing

```
Documents in PostgreSQL
        │
        ▼
literev_core/preprocessing.py
  └── lingua: detect French language
  └── spacy fr_core_news_md: tokenize + lemmatize
  └── remove stopwords, rare/common n-grams
  └── update Document.preprocessed_document
```

### 3. Clustering

```
Preprocessed corpus (list of strings)
        │
        ▼
literev_core/clustering.py: create_tfidf_matrix()
  └── TfidfVectorizer (French, min_df, max_df, ngram_range)
        │
        ▼
PacMapHDBScan (via Optuna hyperparameter search)
  └── PaCMAP: high-dim → 2D embedding
  └── HDBSCAN: assign cluster labels
  └── DBCV score: cluster quality metric
        │
        ▼
Django DB:
  └── Cluster records (topic, summary)
  └── ClusterElement records (pos_x, pos_y, document, cluster)
```

### 4. Interactive Refinement

```
User views clustered documents in table
        │
        ▼
table_choice.py:
  └── render_table_choice(): display docs with highlights
  └── sort_table_choice(): by date, ES score
  └── neighbour_document(): find 10 nearest in 2D space
        │
        ▼
User marks docs: YES / NO / MAYBE
        │
        ▼
UpdateTableChoiceAPIView (PUT /api/project/{id}/table-choice/)
  └── update_checked_document_page()
  └── iterate_check_list()
        │
        ▼
RefinementIteration stored with checked/excluded/new-neighbor IDs
```

### 5. RAG Q&A

```
User submits question + selects document subset
        │
        ▼
ProjectRAGbyProjectIdAPIView (POST /api/project/{id}/rag/)
  └── creates ProjectRAG record (status: in_progress)
  └── triggers Celery task
        │
        ▼
rag_pdf.py: RagAnswersManager
  └── prepare_chunks(): split docs into chunks (LangChain splitter)
  └── ChromaDB: embed chunks (text-embedding-3-large)
  └── For each document:
      ├── retrieve relevant chunks (top-k similarity)
      ├── generate answer (gpt-4.1-mini or Ollama)
      ├── extract citation via fuzzy matching (rapidfuzz)
      └── score confidence (ragas faithfulness)
        │
        ▼
ProjectDocumentRAG records (answer, citation, confidence_score)
ProjectRAG status → completed
```

---

## Directory Structure (annotated)

```
src/
  config/
    settings/
      base.py          # shared settings (installed apps, middleware, auth)
      dev.py           # debug toolbar, INTERNAL_IPS, django-extensions
      test.py          # fast password hasher, sqlite or test postgres
      prod.py          # Sentry, HSTS, SECURE_*, SMTP email
    celery.py          # Celery app + Redis connection helper
    urls.py            # root URL conf

  literev/             # main Django application
    models.py          # 10 models: Project, Document, Cluster, ClusterElement,
                       #            TableChoice, ProjectRefinement,
                       #            RefinementIteration, ProjectRAG,
                       #            ProjectDocumentRAG, ProjectRAGStats
    views.py           # template views (home, project detail, cluster view, etc.)
    api/
      views.py         # DRF APIView + ModelViewSet endpoints
      serializers.py   # ProjectRAG + ProjectDocumentRAG serializers
      permissions.py   # IsProjectRAGOwner, IsProjectRAGDocumentOwner
    libs/              # ALL business logic lives here
      collectors.py    # Elasticsearch integration + MetaData dataclass
      nlp.py           # NLP topic generation, LLM prompting, cluster summaries
      clustering.py    # orchestration glue between literev_core and Django models
      rag_pdf.py       # RAG pipeline: chunking, embedding, generation, scoring
      rag_classes.py   # HactarAug, HactarGen (pluggable LLM backend)
      parsing.py       # Boolean query parser (tokenizer → AST → ES query)
      pipeline.py      # top-level pipeline orchestration helpers
      table_choice.py  # document selection UI logic + refinement iteration mgmt
      scoring.py       # faithfulness scoring, similarity scoring, keyword extraction
      utils.py         # general utilities
    legal/
      extract_minor_major.py  # French legal section classifier
                              # (Majeure / Mineure-Faits / Mineure-Subsommation /
                              #  Conclusion)
    management/commands/      # 15 Django CLI tools
    migrations/               # database schema history
    tests/                    # pytest test suite
    templates/                # HTML templates (allauth + custom)

  literev_core/        # shared, application-independent NLP utilities
    preprocessing.py   # text normalization + multiprocessing pipeline
    clustering.py      # TF-IDF, PaCMAP, HDBSCAN, Optuna
    utils.py

containers/            # Docker images and compose files
.github/workflows/     # CI/CD (GitHub Actions)
docs/                  # developer documentation (you are here)
pyproject.toml         # dependencies + ruff/mypy/pytest/bandit config
.makim.yaml            # task automation (run with `makim <group>.<task>`)
```

---

## Dependency Graph (key modules)

```
views.py
  └── libs/pipeline.py
        └── libs/collectors.py  ──► Elasticsearch
        └── literev_core/preprocessing.py
        └── literev_core/clustering.py  ──► PaCMAP, HDBSCAN, Optuna
        └── libs/nlp.py  ──► OpenAI / Ollama
        └── libs/rag_pdf.py  ──► ChromaDB, OpenAI, ragas

api/views.py
  └── libs/rag_pdf.py
  └── libs/table_choice.py
        └── libs/scoring.py  ──► ragas, spacy
  └── libs/parsing.py  (query → ES dict)

models.py  ◄── all modules (read/write Django ORM)
```

---

## Technology Choices and Rationale

| Choice | Rationale |
|---|---|
| **Django** | Mature ORM, admin interface, allauth for auth, DRF for API |
| **Elasticsearch** | Full-text search over large French legal corpus with boolean operators |
| **HDBSCAN** | Density-based clustering — handles noise (non-cluster documents), no need to pre-specify cluster count |
| **PaCMAP** | Better neighborhood preservation than UMAP for high-dimensional TF-IDF vectors |
| **Optuna** | Bayesian hyperparameter optimization for HDBSCAN (min_cluster_size, min_samples, etc.) |
| **ChromaDB** | Lightweight vector store — no separate service required for moderate document counts |
| **rago** | Pluggable RAG framework supporting both OpenAI and local Ollama backends |
| **ragas** | Domain-agnostic faithfulness evaluation without labeled data |
| **Celery + Redis** | Decouples long-running NLP/ML jobs from HTTP request cycle |
| **spacy (fr_core_news_md)** | French-aware lemmatization, named entity recognition, similarity scoring |

---

## Scalability Considerations

- **Elasticsearch scrolling**: documents retrieved in parallel slices (ES slicing API) to handle large corpora
- **Celery**: all NLP/ML operations run asynchronously — progress tracked via `Project.step` and `Project.is_running`
- **Multiprocessing**: `preprocessing_mp()` runs text cleaning in parallel using Python multiprocessing
- **Optuna parallelism**: `NUMBER_OPTUNA_JOBS` controls concurrent hyperparameter trials
- **RAG caching**: `rago.extensions.cache.CacheFile` caches embeddings, retrieval results, and LLM outputs to avoid redundant API calls
- **ChromaDB**: in-process vector store — for very large corpora, consider migrating to a hosted vector DB

---

## Production Hardening

- Sentry SDK for error tracking (`SENTRY_DSN`)
- HSTS (`SECURE_HSTS_SECONDS`) and secure cookies in `prod.py`
- CSRF protection enabled globally
- Per-object permission checks (not just queryset filtering)
- `bandit` security scanning in pre-commit hooks
- Secrets exclusively via environment variables / `.env`
- Certbot-managed SSL certificates
- Redis ACL rules limiting access to broker data
