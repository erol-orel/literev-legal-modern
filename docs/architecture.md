# Architecture Overview

## What The System Does

`literev-legal` helps users search, normalize, cluster, refine, and question French legal decisions.
The repository now has a split application layout: `src/backend/` contains the Django application, while `src/frontend/` is the React frontend scaffold for the future SPA. The user-facing flow is still Django-first for now, and the core reusable algorithms live in standalone libraries under repo-root `libs/` so they can be tested without importing Django.

## Source Roots

```text
src/
  backend/
    config/                  Django bootstrapping, settings, ASGI/WSGI/Celery
    literev/                 Django app: models, views, API, tasks
      services/              Django orchestration and settings-backed adapters
      repositories/          ORM/file persistence helpers
      presenters/            HTML-safe and template-facing formatting helpers
    literev_core/            compatibility wrappers during the extraction cutover
    static/                  current static assets still served by Django
  frontend/
    package.json             React application metadata and scripts
    public/                  React public assets
    src/                     React application source scaffold

libs/
  lr_contracts/
    pyproject.toml        standalone library metadata
    src/lr_contracts/     shared dataclasses and protocols
    tests/                package-local unit tests
  lr_query/
    pyproject.toml        standalone library metadata
    src/lr_query/         Boolean query parsing and Elasticsearch DSL generation
    tests/                package-local unit tests
  lr_search/
    pyproject.toml        standalone library metadata
    src/lr_search/        Elasticsearch collection and metadata extraction
    tests/                package-local unit tests
  lr_preprocessing/
    pyproject.toml        standalone library metadata
    src/lr_preprocessing/ preprocessing helpers and package data
    tests/                package-local unit tests
  lr_clustering/
    pyproject.toml        standalone library metadata
    src/lr_clustering/    TF-IDF, PaCMAP, HDBSCAN, and Optuna helpers
    tests/                package-local unit tests
  lr_refinement/
    pyproject.toml        standalone library metadata
    src/lr_refinement/    sorting, highlighting, and topic shaping helpers
    tests/                package-local unit tests
  lr_rag/
    pyproject.toml        standalone library metadata
    src/lr_rag/           framework-free RAG payload and chunking helpers
    tests/                package-local unit tests
  lr_legal/
    pyproject.toml        standalone library metadata
    src/lr_legal/         French legal sentence splitting and extraction
    tests/                package-local unit tests
```

The repository relies on the installed Python environment to expose both the Django app package and the extracted `lr_*` libraries; the entrypoints do not mutate `sys.path` at runtime.

## Dependency Direction

The intended dependency graph is one-way:

```text
src/frontend (future SPA)
        |
        v
   REST / browser calls
        |
        v
src/backend/config + src/backend/literev
        |
        v
     libs/lr_*
```

Rules:

- Code under `libs/` must not import Django, DRF, Celery, `django.conf.settings`, or modules from `src/backend/literev/`.
- Django-specific orchestration belongs in `src/backend/literev/services/`.
- ORM and file persistence belong in `src/backend/literev/repositories/`.
- HTML rendering, `mark_safe`, and template-facing helpers belong in `src/backend/literev/presenters/`.
- Compatibility wrappers may still exist in legacy modules during the cutover, but they should delegate into `libs/` rather than hosting new shared logic.

The import-boundary check in `tests/import_boundaries/` enforces this rule in CI.

## Runtime Architecture

```text
Browser / API client
        |
        v
Django views + DRF endpoints
        |
        v
Services / repositories / presenters
        |
        v
Pure libraries under libs/lr_*
        |
        +--> Elasticsearch
        +--> PostgreSQL via repositories
        +--> Redis / Celery workers
        +--> OpenAI / Hactar / Ollama backends
        +--> ChromaDB and other RAG storage
```

## End-to-End Data Flow

### 1. Query and Collection

```text
User query
  -> lr_query parses/validates Boolean syntax
  -> lr_search builds Elasticsearch requests and extracts metadata
  -> repositories persist Document rows
```

### 2. Preprocessing

```text
Document.raw_document_text
  -> lr_preprocessing language detection and cleanup
  -> repositories update prepared/preprocessed fields
```

### 3. Clustering

```text
Preprocessed corpus
  -> lr_clustering TF-IDF
  -> lr_clustering PaCMAP + HDBSCAN + Optuna
  -> Django app stores Cluster and ClusterElement rows
```

### 4. Refinement

```text
Selected documents
  -> lr_refinement highlights keywords, sorts by scores, shapes topic metadata
  -> Django app manages iterations, table-choice state, and persistence
```

### 5. RAG and Legal Extraction

```text
Question + selected corpus
  -> lr_rag prepares framework-free chunks, payload shaping, and cache keys
  -> lr_legal handles legal-domain sentence splitting and major/minor logic
  -> Django app coordinates model calls, persistence, and result presentation
```

## Testing and CI

The test split now mirrors the architecture:

- `libs/lr_*/tests/`: framework-free unit suites colocated with each extracted library.
- `src/backend/literev/tests/`: Django integration tests for views, tasks, models, and adapters.
- `tests/import_boundaries/`: enforcement that `libs/` stays Django-free.

The main GitHub Actions workflow now detects which `lr_*` packages changed, runs only the affected lib suites plus the boundary checks on pull requests, and runs the full app suite when Django-side code or shared tooling changes.
