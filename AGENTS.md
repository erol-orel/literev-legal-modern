# AGENTS.md — literev-legal

This file provides a comprehensive reference for AI agents (and humans) working
in this repository. Read it before making changes.

---

## 1. Project Overview

**literev-legal** is a legal document analysis platform for French judicial
texts. Its core workflow:

1. Query Elasticsearch to retrieve relevant legal documents
2. Preprocess and normalize French text (encoding fixes, abbreviations,
   mojibake)
3. Vectorize (TF-IDF) → reduce dimensions (PaCMAP) → cluster (HDBSCAN)
4. Optionally run RAG (Retrieval-Augmented Generation) for Q&A with citations

Users iteratively refine document sets and can ask open-ended or closed-ended
questions against their corpus via LLM integration.

---

## 2. Technology Stack

| Layer            | Technology                                                                              |
| ---------------- | --------------------------------------------------------------------------------------- |
| Web framework    | Django 5.0.3 + Django REST Framework                                                    |
| Frontend         | React 18 + react-router-dom 6                                                           |
| Language         | Python 3.11 (strict — do not target 3.10 or 3.12)                                       |
| Async tasks      | Celery 5.3.6 + Redis 7 (broker + result backend)                                        |
| Primary DB       | PostgreSQL (psycopg2-binary)                                                            |
| Search           | Elasticsearch 8.12.1                                                                    |
| Vector DB        | ChromaDB 1.3.4                                                                          |
| NLP              | spacy 3.8, scikit-learn 1.5, lingua-language-detector 2                                 |
| Clustering       | HDBSCAN 0.8.33, PaCMAP 0.7.2, Optuna 3.6                                                |
| LLM / RAG        | OpenAI API ≥1.20 (gpt-4.1-mini, text-embedding-3-large), langchain ≥0.3.6, rago ≥0.14.3 |
| Local LLM        | ollama ≥0.4.7                                                                           |
| RAG evaluation   | ragas ≥0.2.14                                                                           |
| Fuzzy matching   | rapidfuzz ≥3.14.3                                                                       |
| Deep learning    | PyTorch ≥2.5.1                                                                          |
| Visualization    | matplotlib ≥3.9, bokeh ≥3.4                                                             |
| Error tracking   | Sentry SDK (production)                                                                 |
| Task automation  | makim 1.27.0 (replaces Make)                                                            |
| Linter/formatter | ruff                                                                                    |
| Type checker     | mypy + django-stubs                                                                     |
| Security scan    | bandit                                                                                  |
| Dead code        | vulture                                                                                 |
| Template lint    | djlint                                                                                  |
| Git hooks        | pre-commit                                                                              |
| Testing          | pytest + pytest-django + pytest-cov                                                     |

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
      views.py             Legacy/template-heavy workflow views
      views_public.py      Minimal generic frontend entry view for public pages
      api/
        views.py           DRF API endpoints (viewsets + APIView)
        serializers.py     DRF serializers
        permissions.py     Custom permission classes
      libs/                App-local helper modules and core business logic
        collectors.py      Elasticsearch integration
        extract_minor_major.py  French legal text classification
                               (Majeure / Mineure-Faits / Mineure-Subsommation / Conclusion)
        document_content.py  Text highlighting helpers
        nlp.py             NLP processing, topic descriptions
        rag_pdf.py         RAG answer generation (~1,945 lines)
        rag_classes.py     RAG wrapper classes
        parsing.py         Document parsing (~1,331 lines)
        pipeline.py        End-to-end data pipeline
        table_choice.py    Interactive selection refinement
        scoring.py         Document scoring and ranking
        utils.py           Utility functions
      templatetags/        Django template tags, including frontend asset lookup
      management/commands/ Django CLI commands
      migrations/          Database migrations (never edit manually)
      tests/
        api/               API endpoint and serializer tests
        etl/               Data processing tests
        conftest.py        Shared fixtures
    literev_core/          Shared NLP/clustering utilities
      preprocessing.py     Text normalization pipeline
      clustering.py        PaCMAP + HDBSCAN implementation
      utils.py             Core utilities
      data/                Static data files
    static/                Django-served static assets, including shared frontend CSS/images
    manage.py              Django entrypoint
    conftest.py            Pytest fixtures for app tests
  frontend/
    package.json           React application metadata and scripts
    public/                React build-time public assets
    src/                   React routes, pages, components, and browser-side libs

containers/                Docker configuration
  literev/                 App Dockerfile (mambaforge-based)
  postgresql/              DB container
  docker-compose*.yaml     Compose files (dev, prod, elasticsearch, jupyter)

conda/                     Conda environment specs
docs/
  index.md                 Documentation index (start here)
  architecture.md          System overview and data flow
  models.md                Django models reference
  api.md                   REST API endpoints and serializers
  pipeline.md              End-to-end data pipeline
  clustering.md            TF-IDF + PaCMAP + HDBSCAN
  rag.md                   RAG pipeline and LLM backends
  parsing.md               Boolean query parser
  nlp.md                   NLP and cluster labeling
  refinement.md            Document refinement workflow
  scoring.md               Faithfulness and similarity scoring
  legal.md                 French legal text classification
  celery.md                Async tasks and Redis
  configuration.md         Environment variables reference
  testing.md               Test suite and conventions
  management_commands.md   Django CLI commands
  contributing.md          Developer setup guide
  changelog.md             Release history
  notebooks/               Proof-of-concept Jupyter notebooks

scripts/                   Install and utility scripts
.github/workflows/         GitHub Actions CI/CD
pyproject.toml             Package config + all tool settings
.makim.yaml                Task automation (50+ tasks)
.pre-commit-config.yaml    Git hook configuration
.releaserc.json            semantic-release configuration
```

---

## 4. Architecture

### Data Processing Pipeline

```
User query
    │
    ▼
Elasticsearch (boolean queries) ──► Document collection
    │
    ▼
French text normalization (mojibake, abbreviations, encoding)
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
Optional: RAG pipeline
    ├── ChromaDB embeddings (text-embedding-3-large)
    ├── LLM generation (gpt-4.1-mini or Ollama)
    ├── Citation extraction (rapidfuzz)
    └── Confidence scoring (ragas faithfulness)
```

### Django Models

| Model                 | Purpose                                                                                                |
| --------------------- | ------------------------------------------------------------------------------------------------------ |
| `Project`             | User's analysis session — query, date range, status, progress                                          |
| `Document`            | Individual legal document with 22 metadata fields (chamber, decision type, date, procedure type, etc.) |
| `Cluster`             | Document grouping with topic label and summary                                                         |
| `ClusterElement`      | 2D PaCMAP coordinates per document, per cluster                                                        |
| `TableChoice`         | User selection/exclusion flags per document                                                            |
| `ProjectRefinement`   | Iterative filter chain on a Project                                                                    |
| `RefinementIteration` | One iteration: included/excluded document lists                                                        |
| `ProjectRAG`          | A RAG query execution with status (`in_progress` / `completed` / `failed`)                             |
| `ProjectDocumentRAG`  | LLM answer for one document — includes citations and confidence score                                  |
| `ProjectRAGStats`     | Classification statistics for closed-ended questions                                                   |

All models live in
[src/backend/literev/models.py](src/backend/literev/models.py).

### API Design

- RESTful endpoints via Django REST Framework
- ViewSets (`ModelViewSet`) and class-based `APIView`
- Public React routes are served by Django as thin shell adapters; keep page
  data/build wiring outside the view functions
- All endpoints require `IsAuthenticated`
- Custom permissions: `is_owner`, `is_in_shared_projects` — see
  [src/backend/literev/api/permissions.py](src/backend/literev/api/permissions.py)
- Endpoints namespaced under `/api/project/`
- Serializers: `ProjectRAGSerializer`, `ProjectDocumentRAGSerializer` — see
  [src/backend/literev/api/serializers.py](src/backend/literev/api/serializers.py)

### Authentication

- Django built-in `User` + `django-allauth` (social auth ready)
- Session-based authentication with CSRF protection
- Per-object ownership enforced at permission layer (not just queryset)

### Celery Tasks

- `@app.task` decorates all async operations: document fetching, preprocessing,
  clustering, embedding generation, RAG generation
- Task chains and chords orchestrate multi-step workflows
- Redis as both broker and result backend
- Workers run in separate container (`literev-celery`)

### RAG Architecture

- **Embeddings**: `text-embedding-3-large` → ChromaDB vector store
- **Generation**: `gpt-4.1-mini` (default) or Ollama (local, set
  `USE_HACTAR_LLM`)
- **Orchestration**: `rago` framework with pluggable backends
- **Caching**: `rago.extensions.cache.CacheFile` — separate caches for
  retrieval, augmentation, generation, documents (path: `LITEREV_CACHE_DIR`)
- **Citations**: fuzzy-matched via `rapidfuzz`
- **Confidence**: `ragas` faithfulness metric per answer
- Core logic:
  [src/backend/literev/libs/rag_pdf.py](src/backend/literev/libs/rag_pdf.py),
  [src/backend/literev/libs/rag_classes.py](src/backend/literev/libs/rag_classes.py)

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

| Variable                                              | Purpose                           |
| ----------------------------------------------------- | --------------------------------- |
| `DJANGO_SETTINGS_MODULE`                              | Settings module selector          |
| `DJANGO_SECRET_KEY`                                   | Django secret key                 |
| `DEBUG`                                               | `True` / `False`                  |
| `ALLOWED_HOSTS`                                       | Comma-separated hostnames         |
| `POSTGRES_HOST` / `PORT` / `DB` / `USER` / `PASSWORD` | App DB credentials                |
| `REDIS_HOST` / `PORT`                                 | Celery broker                     |
| `ES_HOST_URL` / `ES_USERNAME` / `ES_PASSWORD`         | Elasticsearch                     |
| `OPENAI_API_KEY`                                      | OpenAI API access                 |
| `HACTAR_API_KEY` / `USE_HACTAR_LLM`                   | Alternative LLM backend           |
| `LITEREV_CACHE_DIR`                                   | RAG file cache directory          |
| `NUMBER_THREADS_ALLOWED`                              | Parallelism for NLP/clustering    |
| `NUMBER_TRIALS` / `NUMBER_OPTUNA_JOBS`                | Hyperparameter optimization       |
| `SENTRY_DSN`                                          | Sentry error tracking (prod only) |
| `CERTBOT_DOMAIN` / `CERTBOT_EMAIL`                    | SSL certificate (prod only)       |
| `LOGGING_LEVEL`                                       | `INFO` or `DEBUG`                 |
| `HOST_UID` / `HOST_GID`                               | Docker user mapping               |

All variables are loaded from a `.env` file (not committed — copy from template
in `docs/contributing.md`).

---

## 6. Development Workflow & Best Practices

### Task Automation

All routine tasks use **makim** (`makim <group>.<task>`). Never write ad-hoc
shell scripts for tasks that already exist.

```bash
makim --help                    # list all tasks
makim tests.lint                # run all linters
makim tests.unit                # run pytest
makim django.migrate            # apply migrations
makim django.makemigrations     # create new migrations
makim reactjs.install           # install frontend dependencies
makim reactjs.build             # build frontend assets
makim tests.reactjs              # run frontend unit tests with coverage
makim django.collectstatic       # build frontend then collect Django static files
makim containers.start          # start Docker services
makim containers.stop           # stop Docker services
makim elasticsearch.index       # index documents
```

Task groups: `clean`, `tests`, `reactjs`, `django`, `containers`,
`elasticsearch`, `deploy-production`.

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
| `mccabe`      | Cyclomatic complexity            |
| `prettier`    | JS/CSS formatting                |

Run manually: `pre-commit run --all-files`

### Coding Conventions

- **Type hints** are required on all functions and methods (Python 3.11+ syntax)
- **Docstrings** use NumPy format (Parameters / Returns / Raises sections)
- **Split `src` layout**: Django code lives under `src/backend/`, React code
  lives under `src/frontend/`, and application code should never be imported
  from the repo root
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
makim tests.unit                # recommended
makim tests.reactjs              # frontend unit tests with coverage
# or directly:
pytest src/backend --cov=src/backend --cov-fail-under=35
```

### Test Structure

```
src/backend/literev/tests/
  conftest.py          Shared fixtures (user, project, document, celery_worker)
  api/                 DRF endpoint and serializer tests
  etl/                 Data processing tests
  test_*.py            Feature-specific tests

src/frontend/tests/
  *.test.js            React unit tests

src/frontend/src/
  tests.entry.test.js  react-scripts bootstrap for frontend tests
  setupTests.js        Jest / Testing Library setup
```

### Test Conventions

- Use **`APITestCase`** + **`APIClient`** for REST API tests — not plain
  `TestCase`
- Use fixtures from `conftest.py` — do not create duplicate setup logic
- Celery tests use a real worker (prefork pool) — Redis is flushed before each
  test
- Flaky tests can be annotated with `pytest-rerunfailures`
- Coverage minimum: **35%** — the CI will fail below this

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

| Service            | Description                       |
| ------------------ | --------------------------------- |
| `literev`          | Django app (gunicorn / runserver) |
| `literev-postgres` | PostgreSQL database               |
| `literev-redis`    | Redis broker + cache              |
| `literev-celery`   | Celery worker                     |
| `jupyter`          | Optional Jupyter notebook server  |
| `elasticsearch`    | Optional Elasticsearch node       |

Image: mambaforge-based with conda environment. User isolation:
`literev:literev`.

Compose files in `containers/` — use `makim containers.*` tasks, not raw
`docker compose` commands.

### CI/CD Pipeline

GitHub Actions (`.github/workflows/main.yaml`) runs on every push and PR to
`main`:

1. Pre-commit checks (ruff, mypy, bandit, djlint, etc.)
2. pytest with coverage (fail under 35%) plus React unit tests with Jest
   coverage; the frontend coverage comment block is rendered by
   `scripts/render_frontend_coverage_summary.py`. Keep workflow and makim YAML
   files free of embedded heredocs such as `<<'PY'`; use repo scripts for
   non-trivial logic instead
3. On merge to `main`: `semantic-release` creates a version tag, GitHub release,
   and changelog entry

### Release Process

1. Merge PR with conventional commit messages
2. `semantic-release` reads commits since last tag
3. Bumps version in `pyproject.toml` and `src/backend/config/__init__.py`
4. Creates GitHub release with generated changelog

---

## 9. Documentation

The `docs/` directory contains rich technical documentation for every key
component. **When you change code, update the corresponding doc file.**

| Doc file                                                   | Covers                                                             | Update when you change                                         |
| ---------------------------------------------------------- | ------------------------------------------------------------------ | -------------------------------------------------------------- |
| [docs/architecture.md](docs/architecture.md)               | System overview, component diagram, data flow, technology choices  | Overall architecture, new services, new major components       |
| [docs/models.md](docs/models.md)                           | All Django models, fields, relationships, migration strategy       | Any model field added/removed/renamed, new models              |
| [docs/api.md](docs/api.md)                                 | REST endpoints, serializers, permissions, request/response formats | New endpoints, changed serializer fields, new permissions      |
| [docs/pipeline.md](docs/pipeline.md)                       | 7-stage pipeline from ES collection to clustering                  | Pipeline stages, preprocessing steps, orchestration logic      |
| [docs/clustering.md](docs/clustering.md)                   | TF-IDF, PaCMAP, HDBSCAN, Optuna, DBCV scoring                      | Clustering algorithm, hyperparameter search, quality metrics   |
| [docs/rag.md](docs/rag.md)                                 | RAG pipeline: chunking, embedding, generation, citation, scoring   | RAG workflow, LLM backends, caching strategy, status lifecycle |
| [docs/parsing.md](docs/parsing.md)                         | Boolean query parser: lexer, AST, ES DSL generation                | Query syntax, tokenizer, validation rules, ES query structure  |
| [docs/nlp.md](docs/nlp.md)                                 | Cluster labeling, LLM backends, token budget management            | LLM models, prompt construction, embedding models              |
| [docs/refinement.md](docs/refinement.md)                   | TableChoice workflow, iterations, neighbor expansion               | Refinement logic, iteration management, selection states       |
| [docs/scoring.md](docs/scoring.md)                         | Faithfulness scoring, similarity scoring, document sorting         | Scoring algorithms, ragas integration, sort strategies         |
| [docs/legal.md](docs/legal.md)                             | French legal section classifier (Majeure/Mineure/Conclusion)       | Sentence splitting, classification prompts, section labels     |
| [docs/celery.md](docs/celery.md)                           | Async tasks, Redis config, task chaining, worker setup             | New tasks, task chains, Redis configuration                    |
| [docs/configuration.md](docs/configuration.md)             | All env variables, settings modules, Docker env                    | New env variables, new settings modules                        |
| [docs/testing.md](docs/testing.md)                         | Test structure, fixtures, conventions, CI pipeline                 | New fixtures, test conventions, CI changes                     |
| [docs/management_commands.md](docs/management_commands.md) | All 15 Django CLI commands                                         | New commands, changed command arguments                        |

### Documentation update rules

- **Model changes** → update `docs/models.md` (fields table) and
  `docs/architecture.md` (ER diagram if relationships changed)
- **New API endpoint** → update `docs/api.md` (endpoint spec, request/response)
  and `AGENTS.md` section 9
- **New env variable** → update `docs/configuration.md` (variable table) and
  `AGENTS.md` section 5
- **New management command** → update `docs/management_commands.md`
- **New Celery task** → update `docs/celery.md` (task inventory table)
- **Algorithm change** → update the corresponding component doc (clustering,
  rag, parsing, etc.)
- **New dependency** → update `AGENTS.md` section 2 (technology stack table)

---

## 10. Key File Reference

| File                                                                                               | Purpose                                     |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------- |
| [src/backend/literev/models.py](src/backend/literev/models.py)                                     | All Django models                           |
| [src/backend/literev/api/views.py](src/backend/literev/api/views.py)                               | DRF API endpoints                           |
| [src/backend/literev/views_public.py](src/backend/literev/views_public.py)                         | Minimal generic frontend entry view         |
| [src/backend/literev/templatetags/frontend.py](src/backend/literev/templatetags/frontend.py)       | Frontend asset lookup template tags         |
| [src/backend/literev/templates/generic.html](src/backend/literev/templates/generic.html)           | Generic Django template that mounts React   |
| [src/backend/literev/api/serializers.py](src/backend/literev/api/serializers.py)                   | DRF serializers                             |
| [src/backend/literev/api/permissions.py](src/backend/literev/api/permissions.py)                   | Custom permission classes                   |
| [src/backend/literev/libs/collectors.py](src/backend/literev/libs/collectors.py)                   | Elasticsearch query and document collection |
| [src/backend/literev/libs/document_content.py](src/backend/literev/libs/document_content.py)       | Text highlighting helpers                   |
| [src/backend/literev/libs/nlp.py](src/backend/literev/libs/nlp.py)                                 | NLP processing, topic label generation      |
| [src/backend/literev/libs/rag_pdf.py](src/backend/literev/libs/rag_pdf.py)                         | RAG answer generation (core, ~1,945 lines)  |
| [src/backend/literev/libs/rag_classes.py](src/backend/literev/libs/rag_classes.py)                 | RAG wrapper and config classes              |
| [src/backend/literev/libs/parsing.py](src/backend/literev/libs/parsing.py)                         | Document parsing (~1,331 lines)             |
| [src/backend/literev/libs/pipeline.py](src/backend/literev/libs/pipeline.py)                       | End-to-end pipeline orchestration           |
| [src/backend/literev/libs/table_choice.py](src/backend/literev/libs/table_choice.py)               | Interactive selection/refinement logic      |
| [src/backend/literev/libs/scoring.py](src/backend/literev/libs/scoring.py)                         | Document ranking and scoring                |
| [src/backend/literev/libs/extract_minor_major.py](src/backend/literev/libs/extract_minor_major.py) | French legal text section classification    |
| [src/backend/literev_core/preprocessing.py](src/backend/literev_core/preprocessing.py)             | Shared text normalization pipeline          |
| [src/backend/literev_core/clustering.py](src/backend/literev_core/clustering.py)                   | PaCMAP + HDBSCAN implementation             |
| [src/backend/config/settings/](src/backend/config/settings/)                                       | All Django settings modules                 |
| [src/backend/config/celery.py](src/backend/config/celery.py)                                       | Celery app and task configuration           |
| [.makim.yaml](.makim.yaml)                                                                         | All development and ops tasks               |
| [scripts/render_frontend_coverage_summary.py](scripts/render_frontend_coverage_summary.py)         | Formats frontend Jest coverage for CI       |
| [pyproject.toml](pyproject.toml)                                                                   | Dependencies and tool configuration         |
| [docs/contributing.md](docs/contributing.md)                                                       | Full developer setup guide                  |
