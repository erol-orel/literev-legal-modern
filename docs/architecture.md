# Architecture Overview

## What The System Does

`literev-legal` helps users search, normalize, cluster, refine, and question French legal decisions.
The repository now has a split application layout: `src/backend/` contains the Django application, while `src/frontend/` contains the React frontend used for the gradual hybrid migration away from Django templates. Public marketing routes plus the authenticated `/search/`, `/running/`, `/historicalpage/`, `/project/<id>/`, `/tableselect/...`, `/contentdocument/<id>`, `/contentdocument_highlighted/<rag_id>/`, and `/rag/<project_id>/` workflows already render through a minimal Django generic template and are routed inside React. The migrated routes now share a React-owned navbar, shell, and client-side auth guard that mirrors Django login boundaries, the remaining authenticated workflow pages are still Django-first, and the core reusable algorithms live in standalone libraries under repo-root `libs/` so they can be tested without importing Django.

## Source Roots

```text
src/
  backend/
    config/                  Django bootstrapping, settings, ASGI/WSGI/Celery
    literev/                 Django app: models, views, API, tasks
      libs/                  app-local Django-aware helper modules
    literev_core/            compatibility wrappers during the extraction cutover
    static/                  Django static assets plus shared styling/images for the frontend app
  frontend/
    package.json             React application metadata and scripts
    public/                  React build-time public assets
    src/                     React routes, pages, components, and browser-side libs

libs/
  lr-contracts/
    pyproject.toml        standalone library metadata
    src/lr_contracts/     shared dataclasses and protocols
    tests/                package-local unit tests
  lr-query/
    pyproject.toml        standalone library metadata
    src/lr_query/         Boolean query parsing and Elasticsearch DSL generation
    tests/                package-local unit tests
  lr-search/
    pyproject.toml        standalone library metadata
    src/lr_search/        Elasticsearch collection and metadata extraction
    tests/                package-local unit tests
  lr-preprocessing/
    pyproject.toml        standalone library metadata
    src/lr_preprocessing/ preprocessing helpers and package data
    tests/                package-local unit tests
  lr-clustering/
    pyproject.toml        standalone library metadata
    src/lr_clustering/    TF-IDF, PaCMAP, HDBSCAN, and Optuna helpers
    tests/                package-local unit tests
  lr-refinement/
    pyproject.toml        standalone library metadata
    src/lr_refinement/    sorting, highlighting, and topic shaping helpers
    tests/                package-local unit tests
  lr-rag/
    pyproject.toml        standalone library metadata
    src/lr_rag/           framework-free RAG payload and chunking helpers
    tests/                package-local unit tests
  lr-legal/
    pyproject.toml        standalone library metadata
    src/lr_legal/         French legal sentence splitting and extraction
    tests/                package-local unit tests
```

The repository relies on the installed Python environment to expose both the Django app package and the extracted libraries (directory/distribution names like `lr-legal`, import packages like `lr_legal`); the entrypoints do not mutate `sys.path` at runtime.

## Dependency Direction

The intended dependency graph is one-way:

```text
src/frontend (React Router pages)
        |
        v
   REST / browser calls
        |
        v
src/backend/config + src/backend/literev
        |
        v
     libs/lr-*
```

Rules:

- Code under `libs/` must not import Django, DRF, Celery, `django.conf.settings`, or modules from `src/backend/literev/`.
- Django-aware, app-local helper logic belongs in `src/backend/literev/libs/`.
- Reusable framework-free code belongs in repo-root `libs/lr-*`.
- Compatibility wrappers may still exist in legacy modules during the cutover, but they should delegate into repo-root `libs/` rather than hosting new shared logic.

The import-boundary check in `tests/import_boundaries/` enforces this rule in CI.

## Runtime Architecture

```text
Browser / API client
        |
        +--> generic Django template mounting React for `/`, `/team/`, `/product/`, `/company/`, `/blog/`, `/search/`, `/running/`, `/historicalpage/`, `/project/<id>/`, `/tableselect/...`, `/contentdocument/<id>`, `/contentdocument_highlighted/<rag_id>/`, and `/rag/<project_id>/`
        +--> React-owned shared shell handles migrated-route navigation collapse, layout chrome, and client-side login redirects for authenticated route groups
        |
        v
Django views + DRF endpoints
        |
        v
App-local helpers under `literev/libs`
        |
        v
Pure libraries under libs/lr-*
        |
        +--> Elasticsearch
        +--> PostgreSQL via Django ORM and app helpers
        +--> Redis / Celery workers
        +--> OpenAI / Hactar / Ollama backends
        +--> ChromaDB and other RAG storage
```

## End-to-End Data Flow

### 1. Query and Collection

```text
User query
  -> React `/search/` page calls `/api/project/search/validate`, `/preview`, `/projects`, and `/convert-query/`
  -> `literev.libs.search` parses/validates Boolean syntax and counts Elasticsearch hits
  -> lr_search builds Elasticsearch requests and extracts metadata
  -> Django app helpers persist Document rows

Project monitoring
  -> React `/running/` and `/historicalpage/` pages call `/api/project/running/`, `/api/project/historical/`, and project lifecycle action endpoints
  -> `literev.libs.project_listing` shapes progress, filtering, sorting, and lifecycle actions for project lists

Project overview and refinement
  -> React `/project/<id>/` calls `/api/project/projects/<id>/overview/`, `/filters/preview/`, `/refinements/`, `/clusters/<cluster_id>/summary/`, and `/ask-top-docs/`
  -> `literev.libs.project_overview` shapes project details, filter configuration, refinement lifecycle actions, and cluster summary generation

Table selection workspace
  -> React `/tableselect/...` calls `/api/project/tableselect/<project_id>/<refinement_id>/state/`, `/selection/`, `/iterations/<iteration_id>/activate/`, `/iterate/`, `/reset/`, `/check-all/`, `/export/`, and `/ask-selected/`
  -> React `/contentdocument/<id>` calls `/api/project/documents/<id>/`
  -> React `/contentdocument_highlighted/<rag_id>/` calls `/api/project/documents/rag/<rag_id>/highlighted/`
  -> `literev.libs.table_selection` shapes iteration resolution, pagination, sorting, rendered filter metadata, and action URLs while `literev.libs.table_choice` keeps the low-level refinement state transitions
```

### 2. Preprocessing

```text
Document.raw_document_text
  -> lr_preprocessing language detection and cleanup
  -> Django app helpers update prepared/preprocessed fields
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

- `libs/lr-*/tests/`: framework-free unit suites colocated with each extracted library.
- `src/backend/literev/tests/`: Django integration tests for views, tasks, models, and adapters.
- `tests/import_boundaries/`: enforcement that `libs/` stays Django-free.

The main GitHub Actions workflow now detects which `lr-*` library directories changed, runs only the affected lib suites plus the boundary checks on pull requests, and runs the full app suite when Django-side code or shared tooling changes.
