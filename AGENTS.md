# AGENTS.md — literev-legal

This file provides a comprehensive reference for AI agents (and humans) working
in this repository. Read it before making changes.

---

## 1. Project Overview

**literev-legal** is a legal research platform for Swiss case law: the three
Geneva chambers, the federal courts (Bundesgericht, ATF, administrative,
criminal and patent courts) and the Romandie/bilingual cantonal courts, imported
from entscheidsuche.ch. Decisions are in French, German or Italian. Its core
workflow:

1. Query Elasticsearch (boolean queries, BM25) to retrieve relevant decisions,
   optionally reranked by a cross-encoder
2. Preprocess and normalize the text per language (encoding fixes,
   abbreviations, mojibake)
3. Vectorize (TF-IDF) → reduce dimensions (PaCMAP) → cluster (HDBSCAN)
4. Optionally run section-based RAG (Retrieval-Augmented Generation) for Q&A
   with citations, answered in the decision's language

Users iteratively refine document sets, ask open-ended or closed-ended questions
against their corpus, and can export the analysis as a Word memo.

For the current state of the work and open items, read [HANDOFF.md](HANDOFF.md).

---

## 2. Technology Stack

| Layer            | Technology                                                                                                                       |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Web framework    | Django ≥5.0.3 + Django REST Framework; WhiteNoise serves `/static`                                                               |
| Frontend         | Vite 5 + React 18 + TypeScript (strict), react-router-dom 6, Tailwind CSS 3, Radix UI, TanStack Query 5 / Table 8; Node ≥20      |
| Language         | Python 3.11 (strict — do not target 3.10 or 3.12)                                                                                |
| Async tasks      | Celery ≥5.3.6 + Redis (broker + result backend)                                                                                  |
| Primary DB       | PostgreSQL (psycopg2-binary)                                                                                                     |
| Search           | Elasticsearch 8.x (Python client ≥8.12.1,<9; server version from `ES_STACK_VERSION`), basic license — no RRF                     |
| Vector store     | ChromaDB 1.3.4 for section embeddings, being replaced by Elasticsearch `<source>_sections` dense-vector indexes                  |
| Reranking        | Cross-encoder over the BM25 top-K (local, remote URL, or Cohere), behind `RERANK_ENABLED`                                        |
| NLP              | spacy 3.8 (FR/DE/IT models), scikit-learn ≥1.5, lingua-language-detector 2                                                       |
| Clustering       | HDBSCAN ≥0.8.33, PaCMAP ≥0.7.2, Optuna ≥3.6                                                                                      |
| LLM / RAG        | OpenAI API ≥1.20 (gpt-4.1-mini, text-embedding-3-large), langchain ≥0.3.6,<0.4, rago ≥0.14.3,<0.14.5 (0.14.5 broke `generate()`) |
| Hactar LLM       | UNIGE-hosted Ollama gateway (ollama ≥0.4.7) for generation, boolean-query conversion and embeddings                              |
| RAG evaluation   | ragas ≥0.2.14, plus the offline harness `scripts/eval_rag.py`                                                                    |
| Fuzzy matching   | rapidfuzz ≥3.14.3                                                                                                                |
| Report export    | python-docx (Word memo, imported lazily)                                                                                         |
| Deep learning    | PyTorch ≥2.5.1                                                                                                                   |
| Visualization    | matplotlib ≥3.9, bokeh ≥3.4 (cluster map)                                                                                        |
| Error tracking   | Sentry SDK (production)                                                                                                          |
| Task automation  | makim 1.20.0 (replaces Make); sugar for Docker Compose profiles                                                                  |
| Linter/formatter | ruff (Python), ESLint with zero warnings + prettier (frontend)                                                                   |
| Type checker     | mypy + django-stubs; `tsc` for the frontend                                                                                      |
| Security scan    | bandit, gitleaks                                                                                                                 |
| Dead code        | vulture                                                                                                                          |
| Template lint    | djlint                                                                                                                           |
| Git hooks        | pre-commit                                                                                                                       |
| Testing          | pytest + pytest-django + pytest-cov; Vitest + Testing Library (frontend)                                                         |

---

## 3. Repository Layout

```
src/
  backend/
    config/                Django project config
      settings/
        base.py            Shared settings
        dev.py             Dev overrides (debug toolbar)
        test.py            Test overrides
        prod.py            Production (Sentry, HSTS, SMTP, SSL)
      celery.py            Celery app configuration
      urls.py              Root URL routing
      wsgi.py / asgi.py
    literev/               Main Django application
      models.py            All 10 Django models
      views_public.py      Generic frontend entry views for public and React-owned authenticated pages
      templates/generic.html Minimal Django template that mounts the shared React shell; migrated workflow templates have been retired
      api/
        views.py           DRF ViewSets for ProjectRAG / ProjectDocumentRAG, plus RAG create/status per project
        search.py          DRF endpoints for search validation, preview, and project creation
        project_lists.py   DRF endpoints for running/historical project lists and lifecycle actions
        project_overview.py DRF endpoints for project overview, refinements, and cluster summary actions
        table_selection.py DRF endpoints for table-selection state, iteration actions, export, and RAG hand-off
        rag_workspace.py   DRF endpoints for RAG context, RAG deletion, and the .docx report export
        document_content.py DRF endpoints for raw and RAG-highlighted document text
        serializers.py     DRF serializers
        permissions.py     Custom permission classes
      libs/                App-local helper modules and core business logic
        collectors.py      Elasticsearch integration
        entscheidsuche.py  Federal and cantonal court importer (entscheidsuche.ch)
        etl.py             Loading documents into Elasticsearch
        extract_minor_major.py  Legal section classification
                               (Majeure / Mineure-Faits / Mineure-Subsommation / Conclusion)
        document_content.py  Text highlighting helpers
        search.py          Search sources, validation, preview, and project-launch helpers
        project_listing.py Project list serialization, progress, sorting, and lifecycle helpers
        project_overview.py Project overview, refinements, filters, and cluster summary helpers
        project_workflows.py Shared project helpers: access checks, plot data, cluster grouping, RAG history removal
        table_selection.py Table-selection state shaping, iteration actions, pagination, and rendered filter metadata
        nlp.py             NLP processing, topic descriptions
        rag_pdf.py         RAG answer generation (~1,960 lines)
        rag_classes.py     RAG wrapper classes and the Hactar (Ollama) client
        rag_workspace.py   RAG workspace context shaping
        chroma_utils.py    ChromaDB section collections and embedding engines
        es_section_retrieval.py Section-chunk retrieval from ES (dense kNN, behind HYBRID_RETRIEVAL_ENABLED)
        reranking.py       Cross-encoder reranking of the BM25 candidates
        response_cache.py  Opt-in per-user document response cache
        report_docx.py     Word memo export
        parsing.py         Re-export of lr_query.parsing (boolean query parser)
        pipeline.py        End-to-end data pipeline
        table_choice.py    Interactive selection refinement
        scoring.py         Document scoring and ranking
        utils.py           Utility functions
      tasks.py / task_clustering.py / task_plotting.py  Celery tasks
      templatetags/        Django template tags, including frontend asset lookup
      management/commands/ Django CLI commands
      migrations/          Database migrations (never edit manually)
      tests/
        api/               API endpoint and serializer tests
        etl/               Data processing tests
        test_*.py          Feature-specific tests
    literev_core/          Shared NLP/clustering utilities
      boolean_query.py     Re-export of lr_query's natural-language → boolean query conversion
      preprocessing.py     Text normalization pipeline
      clustering.py        PaCMAP + HDBSCAN implementation
    static/                Django-served static assets, including shared frontend CSS/images
    manage.py              Django entrypoint
    conftest.py            Shared pytest fixtures (user, project, document, API client, Celery worker)
  frontend/                Vite + React + TypeScript SPA
    package.json           Scripts: dev, build, typecheck, lint, test, test:coverage
    vite.config.ts         Build config, incl. the CRA-compatible asset-manifest plugin Django relies on
    index.html
    src/
      app/                 App root, router, and providers
      api/                 Typed API modules, one per backend domain
      components/          ui/, layout/, auth/, common/, project/, rag/
      hooks/               Theme, toast, and app-context hooks
      lib/                 api-client, context, csrf, query client, utils
      pages/               Route pages
      test/                Vitest setup and tests

libs/                      Framework-free packages (no Django imports), installed as a uv workspace
  lr-contracts/            Shared dataclasses and protocols
  lr-query/                Boolean query parsing and ES query construction
  lr-search/               ES collection, metadata extraction, section index mapping and hybrid query builder
  lr-preprocessing/        Language-aware preprocessing and n-grams
  lr-clustering/           TF-IDF, PaCMAP, HDBSCAN, Optuna
  lr-rag/                  RAG payload, chunking, and cache-key helpers
  lr-refinement/           Refinement, highlighting, and score shaping
  lr-legal/                Legal text splitting and minor/major extraction
tests/import_boundaries/   Checks that libs/ and src/backend/ import only in the allowed direction

containers/                Docker configuration
  literev/                 App Dockerfile (mambaforge-based)
  postgresql/ redis/ nginx/ elasticsearch_restore/  Service configs
  compose.*.yaml           Compose files (base, dev, prod, elasticsearch, jupyter)

conda/                     Conda environment specs (base.yaml for dev and CI)
docs/
  index.md                 Documentation index (start here)
  architecture.md          Source roots, dependency direction, data flow
  adr/                     Architecture Decision Records
  contributing.md          Developer setup guide
  services/                django, celery, configuration, containers, deployment, elasticsearch
  hybrid-retrieval.md      ES section retrieval and hybrid search plan
  reranking.md             Cross-encoder reranking
  rag-evaluation.md        Offline RAG quality harness
  federal-court-integration.md  Federal court import (DE/FR/IT)
  adverse-authority.md     Citation graph and "still good law?" signals
  frontend-question-first.md  Answer-first research UI
  performance.md           Response cache and other speed/cost levers
  infrastructure.md        Hosts and topology
  deployment-hetzner.md    Standalone Hetzner deployment runbook
  changelog.md             Release history
  notebooks/               Proof-of-concept Jupyter notebooks

scripts/                   Install, deploy, benchmark, evaluation, and CI helper scripts
.github/workflows/         GitHub Actions: main (CI), release, secret-scan
pyproject.toml             Package config + all tool settings
.makim.yaml                Task automation
.sugar.yaml                Docker Compose profiles (dev, prod)
.pre-commit-config.yaml    Git hook configuration
.releaserc.json            semantic-release configuration
.env.tpl                   Template for the untracked .env file
HANDOFF.md                 Current state of the work and open items
```

---

## 4. Architecture

### Data Processing Pipeline

```
User query
    │
    ▼
Elasticsearch BM25 (boolean queries) ──► Document collection
    │
    ▼
Optional: cross-encoder rerank of the top-K (RERANK_ENABLED)
    │
    ▼
Language-aware normalization, FR/DE/IT (mojibake, abbreviations, encoding)
    │
    ▼
TF-IDF vectorization
    │
    ▼
PaCMAP dimensionality reduction (2D coordinates → ClusterElement)
    │
    ▼
HDBSCAN clustering → Cluster + ClusterElement records
    │
    ▼
Optional: section-based RAG pipeline
    ├── Section chunks: ChromaDB, or ES `<source>_sections` dense kNN
    │   when HYBRID_RETRIEVAL_ENABLED (text-embedding-3-large)
    ├── LLM generation (CHAT_MODEL, default gpt-4.1-mini, or Hactar)
    ├── Citation extraction (rapidfuzz)
    └── Confidence scoring (ragas faithfulness)
```

Sources without section embeddings fall back to a generic (non-section) RAG
pipeline; `manage.py rag_section_status` shows which sources do.

### Django Models

| Model                 | Purpose                                                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `Project`             | User's analysis session — query, date range, status, progress                                                         |
| `Document`            | One decision: source/chamber, record key, decision type and date, procedure type, language, raw and preprocessed text |
| `Cluster`             | Document grouping with topic label and summary                                                                        |
| `ClusterElement`      | 2D PaCMAP coordinates per document, per cluster                                                                       |
| `TableChoice`         | User selection/exclusion flags per document                                                                           |
| `ProjectRefinement`   | Iterative filter chain on a Project                                                                                   |
| `RefinementIteration` | One iteration: included/excluded document lists                                                                       |
| `ProjectRAG`          | A RAG query execution with status (`in_progress` / `completed` / `failed`)                                            |
| `ProjectDocumentRAG`  | LLM answer for one document — includes citations and confidence score                                                 |
| `ProjectRAGStats`     | Classification statistics for closed-ended questions                                                                  |

All models live in
[src/backend/literev/models.py](src/backend/literev/models.py).

### API Design

- RESTful endpoints via Django REST Framework
- ViewSets (`ModelViewSet`) and class-based `APIView`
- Public React routes are served by Django as thin shell adapters; keep page
  data/build wiring outside the view functions
- Migrated React routes share a React-owned layout and navbar; keep
  route-specific navigation behavior in React components/hooks instead of inline
  template JS
- All endpoints require `IsAuthenticated`
- Custom permissions: `is_owner`, `is_in_shared_projects` — see
  [src/backend/literev/api/permissions.py](src/backend/literev/api/permissions.py)
- Endpoints namespaced under `/api/project/`
- Search workflow endpoints live under `/api/project/search/` for validation,
  preview, NL→boolean conversion, and project creation
- Running/historical workflow endpoints live under `/api/project/running/`,
  `/api/project/historical/`, and `/api/project/projects/<id>/`
- Project overview/refinement endpoints live under
  `/api/project/projects/<id>/overview/`, `/filters/preview/`, `/refinements/`,
  `/clusters/<cluster_id>/summary/`, and `/ask-top-docs/`
- Table-selection workspace endpoints live under
  `/api/project/tableselect/<project_id>/<refinement_id>/` for state loading,
  selection persistence, iteration activation/removal, iterate/reset actions,
  bulk selection, export, and RAG hand-off
- Document content endpoints live under `/api/project/documents/<id>/` and
  `/api/project/documents/rag/<rag_id>/highlighted/` for raw and highlighted
  document rendering
- RAG workspace endpoints live under `/api/project/rag/<project_id>/context/`
  (optionally `/context/<rag_id>/`), `/api/project/rag/<project_id>/<rag_id>/`
  (delete a RAG run), and `/api/project/rag/<project_id>/<rag_id>/report.docx/`
  (Word memo export), plus `/api/project-rags-by-project/<project_id>/`
  (create/status) and `/api/project-documents-rag/?project_rag=<id>` for answer
  lists
- Serializers: `ProjectRAGSerializer`, `ProjectDocumentRAGSerializer` — see
  [src/backend/literev/api/serializers.py](src/backend/literev/api/serializers.py)

### Authentication

- Django built-in `User` + `django-allauth` (social auth ready)
- Session-based authentication with CSRF protection
- Django/allauth pages remain server-rendered; the React router mirrors login
  redirects for migrated authenticated routes, but Django remains the source of
  truth for access control
- Per-object ownership enforced at permission layer (not just queryset)

### Celery Tasks

- `@app.task` decorates all async operations: document fetching, preprocessing,
  clustering, embedding generation, RAG generation
- Task chains and chords orchestrate multi-step workflows
- Redis as both broker and result backend
- Workers run in separate container (`literev-celery`)

### RAG Architecture

- **Embeddings**: `text-embedding-3-large` (3072-dim) section chunks in
  ChromaDB. With `HYBRID_RETRIEVAL_ENABLED=true`, chunks come from Elasticsearch
  `<source>_sections` indexes via a dense `knn` query filtered to the decision.
  Native RRF fusion is a paid ES feature and is not used. The indexes are built
  with `manage.py embed_sections_to_es` (reads Chroma's SQLite store;
  `--skip-existing` resumes an interrupted run). The Hactar embedding engine is
  optional per source (`FEDERAL_EMBED_ENGINE`, `HYBRID_EMBED_ENGINE`)
- **Generation**: `CHAT_MODEL` (default `gpt-4.1-mini`) or Hactar, the
  UNIGE-hosted Ollama gateway (`USE_HACTAR_LLM`)
- **Language**: answers are written in the decision's language (de/fr/it)
- **Orchestration**: `rago` framework with pluggable backends
- **Caching**: `rago.extensions.cache.CacheFile` — separate caches for
  retrieval, augmentation, generation, documents (path: `LITEREV_CACHE_DIR`)
- **Citations**: fuzzy-matched via `rapidfuzz`; Swiss case-law citations are
  extracted into a citation graph (`manage.py build_citation_graph`)
- **Confidence**: `ragas` faithfulness metric per answer, scored in parallel
- **Evaluation**: offline harness `scripts/eval_rag.py`, see
  [docs/rag-evaluation.md](docs/rag-evaluation.md)
- Core logic:
  [src/backend/literev/libs/rag_pdf.py](src/backend/literev/libs/rag_pdf.py),
  [src/backend/literev/libs/rag_classes.py](src/backend/literev/libs/rag_classes.py),
  [src/backend/literev/libs/es_section_retrieval.py](src/backend/literev/libs/es_section_retrieval.py),
  [src/backend/literev/libs/chroma_utils.py](src/backend/literev/libs/chroma_utils.py)

---

## 5. Configuration & Environment

### Settings Modules

Select via `DJANGO_SETTINGS_MODULE`:

| Module                 | Use                          |
| ---------------------- | ---------------------------- |
| `config.settings.base` | Shared (never used directly) |
| `config.settings.dev`  | Local development            |
| `config.settings.test` | pytest runs                  |
| `config.settings.prod` | Production deployment        |

### Key Environment Variables

| Variable                                                                      | Purpose                                                                             |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `DJANGO_SETTINGS_MODULE`                                                      | Settings module selector                                                            |
| `DJANGO_SECRET_KEY`                                                           | Django secret key                                                                   |
| `DEBUG`                                                                       | `True` / `False`                                                                    |
| `ALLOWED_HOSTS`                                                               | Comma-separated hostnames                                                           |
| `SIGNUP_SECRET_CODE`                                                          | Code required to sign up                                                            |
| `POSTGRES_HOST` / `PORT` / `DB_LITEREV` / `USER_LITEREV` / `PASSWORD_LITEREV` | App DB credentials (`POSTGRES_DB` / `USER` / `PASSWORD` are the admin account)      |
| `REDIS_HOST` / `PORT` / `DB` / `USERNAME` / `PASSWORD`                        | Celery broker and result backend                                                    |
| `ES_HOST_URL` / `ES_USERNAME` / `ES_PASSWORD` / `ES_SSL_CERTS`                | Elasticsearch                                                                       |
| `ES_STACK_VERSION`                                                            | Elasticsearch server image version for the compose stack                            |
| `LITEREV_CHAMBER_NAMES`                                                       | Extra sources (comma-separated) added to the Geneva chambers for corpus commands    |
| `OPENAI_API_KEY`                                                              | OpenAI API access                                                                   |
| `CHAT_MODEL`                                                                  | Generation model (default `gpt-4.1-mini`)                                           |
| `HACTAR_API_KEY` / `HACTAR_BASE_URL` / `HACTAR_VERIFY_SSL`                    | Hactar (UNIGE Ollama gateway) access                                                |
| `USE_HACTAR_LLM` / `USE_HACTAR_LLM_FOR_BOOLEAN_QUERY`                         | Route generation / NL→boolean conversion to Hactar                                  |
| `HACTAR_EMBED_MODEL` / `HACTAR_BOOLEAN_QUERY_MODEL`                           | Hactar model names                                                                  |
| `FEDERAL_EMBED_ENGINE`                                                        | Embedding engine for federal section collections (`openai` default, or Hactar)      |
| `RERANK_ENABLED`                                                              | Turn on cross-encoder reranking (default off)                                       |
| `RERANKER_PROVIDER` / `RERANKER_URL` / `RERANKER_MODEL` / `COHERE_API_KEY`    | Reranker backend (`local` default, remote URL, or Cohere)                           |
| `RERANK_TOP_K` / `RERANK_MAX_CHARS` / `RERANKER_TIMEOUT_S`                    | Reranker tuning (defaults 50 / 2000 / 20)                                           |
| `HYBRID_RETRIEVAL_ENABLED`                                                    | Read RAG section chunks from ES `<source>_sections` instead of Chroma (default off) |
| `HYBRID_EMBED_ENGINE`                                                         | Embedding engine for the ES section index and its queries (default `openai`)        |
| `HYBRID_TOP_K_PER_SECTION` / `HYBRID_SEARCH_SIZE`                             | ES section retrieval tuning (defaults 8 / 40)                                       |
| `RESPONSE_CACHE_ENABLED` / `RESPONSE_CACHE_TTL`                               | Opt-in per-user document response cache (TTL default 300 s)                         |
| `LITEREV_CACHE_DIR`                                                           | RAG file cache directory                                                            |
| `MIN_CONFIDENCE`                                                              | Meant as the minimum faithfulness score; currently ignored (see HANDOFF.md)         |
| `CLUSTERING_MIN_DOCUMENTS`                                                    | Minimum corpus size before clustering runs (default 20)                             |
| `NUMBER_THREADS_ALLOWED`                                                      | Parallelism for NLP/clustering                                                      |
| `NUMBER_TRIALS` / `NUMBER_OPTUNA_JOBS`                                        | Hyperparameter optimization                                                         |
| `NUMBA_CACHE_DIR`                                                             | Writable Numba/PacMAP cache dir                                                     |
| `SENTRY_DSN`                                                                  | Sentry error tracking (prod only)                                                   |
| `CERTBOT_DOMAIN` / `CERTBOT_EMAIL`                                            | SSL certificate (prod only)                                                         |
| `HOST_UID` / `HOST_GID`                                                       | Docker user mapping                                                                 |

The log level is not an environment variable: `LOGGING_LEVEL` is set per
settings module (`WARNING` in `base.py`, `INFO` in `dev.py`).

All variables are loaded from a `.env` file, which is not committed. Create it
from [.env.tpl](.env.tpl) (CI renders it with `envsubst < .env.tpl > .env`).

---

## 6. Development Workflow & Best Practices

### Task Automation

All routine tasks use **makim** (`makim <group>.<task>`). Never write ad-hoc
shell scripts for tasks that already exist.

```bash
makim --help                    # list all tasks
makim tests.lint                # run all linters (pre-commit)
makim tests.app                 # Django app suite
makim tests.lib --lib lr-query  # one framework-free lib suite
makim tests.libs-all            # all lib suites
makim tests.import-boundaries   # libs/ ↔ src/backend/ import rules
makim tests.reactjs             # frontend Vitest suite with coverage
makim django.migrate            # apply migrations
makim django.makemigrations     # create new migrations
makim reactjs.install           # install frontend dependencies
makim reactjs.build             # build frontend assets
makim django.collectstatic      # build frontend then collect Django static files
makim django.embed-sections     # build the ES <source>_sections indexes
makim federal.import            # import federal decisions from entscheidsuche
makim elasticsearch.index-json  # index documents
```

Task groups: `clean`, `tests`, `reactjs`, `django`, `federal`, `containers`,
`nginx`, `elasticsearch`, `deploy-production`, `release`.

Docker Compose services are managed with **sugar** (`.sugar.yaml`, profiles
`dev` and `prod`), for example `sugar compose-ext restart -- -d`;
`makim containers.*` covers helpers such as `host-setup` and `redis-setup`.
Production redeploys use `scripts/deploy_now.sh` (see
[docs/deployment-hetzner.md](docs/deployment-hetzner.md)).

Frontend checks run from `src/frontend/`: `npm run typecheck`, `npm run lint`
(zero warnings allowed) and `npm test`.

### Code Quality Gates

All of the following run automatically via `pre-commit` on every commit:

| Tool          | What it checks                   |
| ------------- | -------------------------------- |
| `ruff format` | Code formatting                  |
| `ruff check`  | Linting (PEP 8, imports, etc.)   |
| `mypy`        | Static types (with django-stubs) |
| `bandit`      | Security vulnerabilities         |
| `vulture`     | Dead code                        |
| `djlint`      | HTML template formatting         |
| `mccabe`      | Cyclomatic complexity (min 25)   |
| `prettier`    | JS/CSS/Markdown formatting       |
| `gitleaks`    | Committed secrets                |

Run manually: `pre-commit run --all-files`

### Coding Conventions

- **Type hints** are required on all functions and methods (Python 3.11+ syntax)
- **Docstrings** use NumPy format (Parameters / Returns / Raises sections)
- **Split `src` layout**: Django code lives under `src/backend/`, React code
  lives under `src/frontend/`, framework-free logic lives in `libs/lr-*`, and
  application code should never be imported from the repo root. `libs/` must not
  import Django or `src/backend/` (enforced by `tests/import_boundaries`)
- **Thin views only**: Django views should do request parsing, auth, shell
  selection, and response rendering only; business logic belongs in app-local
  helper modules under `src/backend/literev/libs/` or in repo-root `libs/lr-*`
  packages when it is framework-free
- **Library naming**: under `libs/`, library directories and Python distribution
  names use kebab-case (for example `libs/lr-legal/` and `name = "lr-legal"`),
  while Python package directories inside each library's `src/` folder and all
  import paths use snake_case (for example `libs/lr-legal/src/lr_legal/` and
  `from lr_legal import ...`)
- **Migrations**: always run `makim django.makemigrations` after model changes;
  never hand-edit migration files
- **Secrets**: never hardcode credentials — always read from environment or
  `.env`
- **Git-ignored files are off-limits**: never create, modify, delete, or rename
  files ignored by Git. Before editing a file, verify that it is not ignored
  (for example with `git check-ignore` or by confirming it is tracked with
  `git ls-files`). Skip ignored files entirely, even if they appear relevant to
  the task.
- **No backwards-compat shims**: if removing code, remove it completely
- **No speculative abstractions**: only abstract when you have 3+ concrete uses
- **No heredocs inside YAML automation files**: do not embed blocks such as
  `<<'PY'` inside `.github/workflows/*.yaml` or `.makim.yaml`; move non-trivial
  shell or Python logic into dedicated files under `scripts/` and call those
  from YAML

### Commit Message Convention

This project uses **Conventional Commits** for automated semantic versioning:

```
feat: add citation confidence threshold config
fix: handle empty cluster in PaCMAP reduction
perf: batch ChromaDB inserts for large corpora
```

Types `feat` / `fix` / `perf` trigger version bumps. Other types (`docs`,
`chore`, `refactor`, `test`) do not.

---

## 7. Testing

### Running Tests

```bash
makim tests.app                 # Django app suite (needs Postgres + Redis)
makim tests.lib --lib lr-rag    # one lib suite (kebab-case lib name)
makim tests.libs-all            # every lib suite
makim tests.import-boundaries   # libs/ must not import Django or literev
makim tests.reactjs             # frontend Vitest suite with coverage
makim tests.unit                # start the compose stack, then pytest with --cov-fail-under=35
```

Pick the suite that matches what you changed: `tests.app` for anything under
`src/backend/`, `tests.lib` for `libs/lr-*`, `tests.import-boundaries` when
moving code between `libs/` and `src/backend/`, and `tests.reactjs` for
`src/frontend/`.

### Test Structure

```
src/backend/conftest.py   Shared fixtures (user, project, document, API clients, Celery worker)
src/backend/literev/tests/
  api/                    DRF endpoint and serializer tests
  etl/                    Data processing tests
  test_*.py               Feature-specific tests

libs/lr-*/tests/          Per-library tests (no Django)
tests/import_boundaries/  Import rule checks for libs/

src/frontend/src/test/
  *.test.ts(x)            Vitest + Testing Library tests
```

### Test Conventions

- Use **`APITestCase`** + **`APIClient`** for REST API tests — not plain
  `TestCase`
- Use fixtures from `conftest.py` — do not create duplicate setup logic
- Celery tests use a real worker (prefork pool) — Redis is flushed before each
  test
- Flaky tests can be annotated with `pytest-rerunfailures`
- Coverage minimum: **35%**, enforced by `makim tests.unit`. CI posts app,
  per-lib and frontend coverage as a PR comment

### What to Test

- React frontend smoke tests for rendered headings, key text, and simple
  interactions
- API permissions: unauthenticated, non-owner, owner, shared-project member
- Boolean query generation edge cases (Elasticsearch query builder)
- Pipeline stages in isolation (normalization, vectorization, clustering)
- RAG answer structure (citations present, confidence in range)

---

## 8. Infrastructure

### Docker Services

| Service                           | Description                                    |
| --------------------------------- | ---------------------------------------------- |
| `literev`                         | Django app (gunicorn / runserver)              |
| `literev-postgres`                | PostgreSQL database                            |
| `literev-redis`                   | Redis broker + cache                           |
| `literev-celery`                  | Celery worker                                  |
| `literev-nginx` / `certbot`       | Reverse proxy and TLS certificates (prod)      |
| `es-legal-1..3`, `es-legal-setup` | Elasticsearch cluster and its setup job (prod) |
| `es-restore`                      | Restores an ES snapshot (prod)                 |
| `literev-elasticsearch`           | Single-node Elasticsearch (dev)                |
| `literev-jupyter`                 | Optional Jupyter notebook server (dev)         |

Image: mambaforge-based with conda environment. User isolation:
`literev:literev`.

Compose files live in `containers/` and are driven by `sugar` profiles from
`.sugar.yaml` — use `sugar` and the `makim containers.*` helpers, not raw
`docker compose` commands. Where the current deployment runs is described in
[docs/infrastructure.md](docs/infrastructure.md).

### CI/CD Pipeline

`.github/workflows/main.yaml` runs on every push and PR to `main`:

1. **Branch check**: a PR fails unless its branch contains the latest `main`
2. **Linter**: `makim tests.lint` (pre-commit: ruff, mypy, bandit, djlint,
   prettier, gitleaks, …)
3. **Import boundaries**: `makim tests.import-boundaries` (on PRs, only when
   `libs/` or related config changed)
4. **Lib tests**: `makim tests.lib` for each `lr-*` library (matrix)
5. **App tests**: frontend Vitest suite (`makim tests.reactjs`), migrations plus
   a `makemigrations --check`, then `makim tests.app` against Postgres and Redis
6. **Coverage PR comment**: collects the lib, app and frontend summaries; the
   frontend block is rendered by `scripts/render_frontend_coverage_summary.py`

Keep workflow and makim YAML files free of embedded heredocs such as `<<'PY'`;
use repo scripts for non-trivial logic instead.

`.github/workflows/secret-scan.yaml` runs gitleaks over the tree.
`.github/workflows/release.yaml` runs `semantic-release` on merge to `main`,
creating a version tag, GitHub release, and changelog entry.

### Release Process

1. Merge PR with conventional commit messages
2. `semantic-release` reads commits since last tag
3. Bumps version in `pyproject.toml` and `src/backend/config/__init__.py`
4. Creates GitHub release with generated changelog

---

## 9. Documentation

The `docs/` directory contains rich technical documentation for every key
component. **When you change code, update the corresponding doc file.**

Start at [docs/index.md](docs/index.md).

| Doc file                                                               | Covers                                                                | Update when you change                                           |
| ---------------------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------- |
| [docs/architecture.md](docs/architecture.md)                           | Source roots, dependency direction, runtime architecture, data flow   | Overall architecture, new services, new major components, models |
| [docs/adr/](docs/adr/README.md)                                        | Architecture Decision Records                                         | Any expensive-to-reverse decision (add a new ADR)                |
| [docs/services/django.md](docs/services/django.md)                     | App-layer structure, API surface, management commands, test commands  | Endpoints, app helpers, management commands, test suites         |
| [docs/services/configuration.md](docs/services/configuration.md)       | Environment variables, settings modules, library installation         | New env variables or settings modules                            |
| [docs/services/celery.md](docs/services/celery.md)                     | Celery workers, async tasks, Redis wiring                             | New tasks, task chains, Redis configuration                      |
| [docs/services/containers.md](docs/services/containers.md)             | Docker Compose, sugar, container lifecycle                            | Compose files, services, sugar profiles                          |
| [docs/services/elasticsearch.md](docs/services/elasticsearch.md)       | Elasticsearch indexing and search infrastructure                      | Index mappings, ES queries, indexing jobs                        |
| [docs/services/deployment.md](docs/services/deployment.md)             | Production deployment and operational concerns                        | Deployment process                                               |
| [docs/hybrid-retrieval.md](docs/hybrid-retrieval.md)                   | ES section retrieval, hybrid search plan, rollout, benchmark          | Section retrieval, ES section indexes, embedding engines         |
| [docs/reranking.md](docs/reranking.md)                                 | Cross-encoder reranking: providers and enabling it                    | Reranking logic or settings                                      |
| [docs/rag-evaluation.md](docs/rag-evaluation.md)                       | Offline RAG quality harness and metrics                               | RAG prompts, scoring, evaluation scripts                         |
| [docs/federal-court-integration.md](docs/federal-court-integration.md) | Federal court sources, ES schema, multilingual steps                  | Sources, importer, language handling                             |
| [docs/adverse-authority.md](docs/adverse-authority.md)                 | Citation graph and "still good law?" signals                          | Citation extraction or treatment                                 |
| [docs/frontend-question-first.md](docs/frontend-question-first.md)     | Answer-first research UI: information architecture and what's shipped | RAG result UI and research flow                                  |
| [docs/performance.md](docs/performance.md)                             | Response cache and other speed/cost levers                            | Caching, performance flags                                       |
| [docs/infrastructure.md](docs/infrastructure.md)                       | Where the deployment runs, read-only inspection checklist             | Hosts, topology                                                  |
| [docs/deployment-hetzner.md](docs/deployment-hetzner.md)               | Standalone Hetzner VM runbook                                         | `scripts/deploy_now.sh`, VM setup                                |
| [docs/contributing.md](docs/contributing.md)                           | Local setup, workflow, contribution checklist                         | Developer setup steps                                            |
| [HANDOFF.md](HANDOFF.md)                                               | Current state of the work, deployment unknowns, open items            | Finishing or starting a body of work; resolving an open item     |

### Documentation update rules

- **Model changes** → update `docs/architecture.md` and the Django Models table
  in `AGENTS.md` section 4
- **New API endpoint** → update `docs/services/django.md` and the API Design
  list in `AGENTS.md` section 4
- **New env variable** → update `docs/services/configuration.md`, `.env.tpl` and
  the variable table in `AGENTS.md` section 5
- **New management command or makim task** → update `docs/services/django.md`
  (and section 6 of this file for commonly used tasks)
- **New Celery task** → update `docs/services/celery.md`
- **Retrieval, RAG or algorithm change** → update the matching topic doc
  (`hybrid-retrieval.md`, `reranking.md`, `rag-evaluation.md`, …) and
  `docs/architecture.md` if the data flow changes
- **New dependency** → update `AGENTS.md` section 2 (technology stack table)
- **New source of truth or design decision** → add an ADR under `docs/adr/`

---

## 10. Key File Reference

| File                                                                                                                               | Purpose                                                           |
| ---------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| [src/backend/literev/models.py](src/backend/literev/models.py)                                                                     | All Django models                                                 |
| [src/backend/literev/urls.py](src/backend/literev/urls.py)                                                                         | All app and `/api/project/` routes                                |
| [src/backend/literev/api/views.py](src/backend/literev/api/views.py)                                                               | ProjectRAG / ProjectDocumentRAG ViewSets and per-project RAG API  |
| [src/backend/literev/api/search.py](src/backend/literev/api/search.py)                                                             | Search validation, preview, conversion, and project-creation APIs |
| [src/backend/literev/api/project_lists.py](src/backend/literev/api/project_lists.py)                                               | Running/historical project list and lifecycle APIs                |
| [src/backend/literev/api/project_overview.py](src/backend/literev/api/project_overview.py)                                         | Project overview, refinements, and cluster summary APIs           |
| [src/backend/literev/api/table_selection.py](src/backend/literev/api/table_selection.py)                                           | Table-selection workspace APIs                                    |
| [src/backend/literev/api/rag_workspace.py](src/backend/literev/api/rag_workspace.py)                                               | RAG context, deletion, and `.docx` report APIs                    |
| [src/backend/literev/views_public.py](src/backend/literev/views_public.py)                                                         | Generic frontend entry views and bootstrap context                |
| [src/backend/literev/templatetags/frontend.py](src/backend/literev/templatetags/frontend.py)                                       | Frontend asset lookup template tags                               |
| [src/backend/literev/templates/generic.html](src/backend/literev/templates/generic.html)                                           | Generic Django template that mounts React                         |
| [src/backend/literev/api/serializers.py](src/backend/literev/api/serializers.py)                                                   | DRF serializers                                                   |
| [src/backend/literev/api/permissions.py](src/backend/literev/api/permissions.py)                                                   | Custom permission classes                                         |
| [src/backend/literev/libs/collectors.py](src/backend/literev/libs/collectors.py)                                                   | Elasticsearch query and document collection                       |
| [src/backend/literev/libs/entscheidsuche.py](src/backend/literev/libs/entscheidsuche.py)                                           | Federal and cantonal court importer                               |
| [src/backend/literev/libs/document_content.py](src/backend/literev/libs/document_content.py)                                       | Text highlighting helpers                                         |
| [src/backend/literev/libs/search.py](src/backend/literev/libs/search.py)                                                           | Search sources, validation, preview, and project-launch helpers   |
| [src/backend/literev/libs/project_listing.py](src/backend/literev/libs/project_listing.py)                                         | Running/historical project list and lifecycle helpers             |
| [src/backend/literev/libs/project_overview.py](src/backend/literev/libs/project_overview.py)                                       | Project overview, refinements, filters, and cluster summaries     |
| [src/backend/literev/libs/nlp.py](src/backend/literev/libs/nlp.py)                                                                 | NLP processing, topic label generation                            |
| [src/backend/literev/libs/rag_pdf.py](src/backend/literev/libs/rag_pdf.py)                                                         | RAG answer generation (core, ~1,960 lines)                        |
| [src/backend/literev/libs/rag_classes.py](src/backend/literev/libs/rag_classes.py)                                                 | RAG wrapper and config classes, Hactar (Ollama) client            |
| [src/backend/literev/libs/chroma_utils.py](src/backend/literev/libs/chroma_utils.py)                                               | ChromaDB section collections and embedding engines                |
| [src/backend/literev/libs/es_section_retrieval.py](src/backend/literev/libs/es_section_retrieval.py)                               | ES section-chunk retrieval (dense kNN)                            |
| [src/backend/literev/libs/reranking.py](src/backend/literev/libs/reranking.py)                                                     | Cross-encoder reranking                                           |
| [src/backend/literev/libs/response_cache.py](src/backend/literev/libs/response_cache.py)                                           | Opt-in per-user document response cache                           |
| [src/backend/literev/libs/report_docx.py](src/backend/literev/libs/report_docx.py)                                                 | Word memo export                                                  |
| [libs/lr-query/src/lr_query/](libs/lr-query/src/lr_query/)                                                                         | Boolean query parser and ES query construction                    |
| [libs/lr-search/src/lr_search/](libs/lr-search/src/lr_search/)                                                                     | ES collection, section index mapping, bulk indexing, hybrid body  |
| [src/backend/literev/libs/pipeline.py](src/backend/literev/libs/pipeline.py)                                                       | End-to-end pipeline orchestration                                 |
| [src/backend/literev/libs/table_choice.py](src/backend/literev/libs/table_choice.py)                                               | Interactive selection/refinement logic                            |
| [src/backend/literev/libs/scoring.py](src/backend/literev/libs/scoring.py)                                                         | Document ranking and scoring                                      |
| [src/backend/literev/libs/extract_minor_major.py](src/backend/literev/libs/extract_minor_major.py)                                 | French legal text section classification                          |
| [src/backend/literev_core/preprocessing.py](src/backend/literev_core/preprocessing.py)                                             | Shared text normalization pipeline                                |
| [src/backend/literev_core/clustering.py](src/backend/literev_core/clustering.py)                                                   | PaCMAP + HDBSCAN implementation                                   |
| [src/backend/config/settings/](src/backend/config/settings/)                                                                       | All Django settings modules                                       |
| [src/backend/config/celery.py](src/backend/config/celery.py)                                                                       | Celery app and task configuration                                 |
| [src/backend/literev/management/commands/embed_sections_to_es.py](src/backend/literev/management/commands/embed_sections_to_es.py) | Chroma → ES section index migration                               |
| [src/frontend/vite.config.ts](src/frontend/vite.config.ts)                                                                         | Frontend build, incl. the asset manifest Django reads             |
| [.makim.yaml](.makim.yaml)                                                                                                         | All development and ops tasks                                     |
| [.sugar.yaml](.sugar.yaml)                                                                                                         | Docker Compose profiles                                           |
| [scripts/deploy_now.sh](scripts/deploy_now.sh)                                                                                     | One-command redeploy on the VM                                    |
| [scripts/check_import_boundaries.py](scripts/check_import_boundaries.py)                                                           | Forbids Django/app imports inside `libs/`                         |
| [scripts/render_frontend_coverage_summary.py](scripts/render_frontend_coverage_summary.py)                                         | Formats frontend Vitest coverage for CI                           |
| [pyproject.toml](pyproject.toml)                                                                                                   | Dependencies and tool configuration                               |
| [docs/contributing.md](docs/contributing.md)                                                                                       | Full developer setup guide                                        |
