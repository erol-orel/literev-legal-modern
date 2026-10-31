# Configuration & Environment

All runtime configuration is driven through environment variables and Django
settings modules. The repository also uses standalone libraries under `libs/`
and now splits application code between `src/backend/` and `src/frontend/`, so
part of the configuration story is making sure the Django app and each `lr-*`
package are installed together in the active environment.

## Installed Packages

The project uses standalone library folders under `libs/` in addition to the
split application roots under `src/`.

- `./scripts/install-prod.sh` and `./scripts/install-dev.sh` install the root
  package in editable mode.
- The root `pyproject.toml` lists every `lr-*` package and resolves it from the
  local `libs/` workspace.
- `setuptools` packages the Django app from `src/backend/`.
- Each library keeps its own `pyproject.toml` and `src/<package>/` layout, so
  the app environment installs them as real packages instead of bundling them
  into the root wheel.
- `src/frontend/` is a React scaffold and is managed separately with npm-based
  tasks.
- Tooling is configured to understand the Django app root and every library root
  through `pyproject.toml`.

That means the following imports are all valid in the configured environment:

```python
from lr_query import process_search_query_elasticsearch
from lr_search import ElasticSearchCollector
from literev.libs.collectors import ElasticSearchCollector
```

## Settings Modules

Select the active settings module with `DJANGO_SETTINGS_MODULE`:

| Module | Value                  | Use case                                      |
| ------ | ---------------------- | --------------------------------------------- |
| base   | `config.settings.base` | shared settings inherited by all environments |
| dev    | `config.settings.dev`  | local development                             |
| test   | `config.settings.test` | pytest and CI                                 |
| prod   | `config.settings.prod` | production deployment                         |

Typical local value:

```bash
DJANGO_SETTINGS_MODULE=config.settings.dev
```

## High-Value Environment Variables

### Core Django

| Variable                 | Description                         |
| ------------------------ | ----------------------------------- |
| `DJANGO_SECRET_KEY`      | Django secret key                   |
| `DEBUG`                  | enable or disable Django debug mode |
| `ALLOWED_HOSTS`          | comma-separated allowed hosts       |
| `DJANGO_SETTINGS_MODULE` | active settings module              |

### PostgreSQL and Redis

| Variable                                                                              | Description                           |
| ------------------------------------------------------------------------------------- | ------------------------------------- |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | primary database connection           |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_USERNAME`, `REDIS_PASSWORD`            | Celery broker and cache configuration |

### Elasticsearch

| Variable        | Description            |
| --------------- | ---------------------- |
| `ES_HOST_URL`   | Elasticsearch base URL |
| `ES_USERNAME`   | Elasticsearch username |
| `ES_PASSWORD`   | Elasticsearch password |
| `ES_INDEX_NAME` | default search index   |

### LLM and RAG

| Variable            | Description                                        |
| ------------------- | -------------------------------------------------- |
| `OPENAI_API_KEY`    | OpenAI access key                                  |
| `USE_HACTAR_LLM`    | switch to the Hactar-compatible backend            |
| `HACTAR_API_KEY`    | Hactar authentication key                          |
| `HACTAR_BASE_URL`   | Hactar service base URL                            |
| `LITEREV_CACHE_DIR` | cache directory for retrieval/generation artifacts |

### Reranking

Cross-encoder reranking of the BM25 candidates; see
[reranking.md](../reranking.md). If the reranker fails, the BM25 order is kept.

| Variable             | Default                      | Description                                                                                                        |
| -------------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `RERANK_ENABLED`     | off                          | turn on cross-encoder reranking of the BM25 candidates                                                             |
| `RERANKER_PROVIDER`  | `local`                      | `cohere` calls the Cohere Rerank API; any other value calls the TEI-style `POST /rerank` service at `RERANKER_URL` |
| `RERANKER_URL`       | `http://literev-reranker:80` | base URL of the TEI-style reranker, local or remote                                                                |
| `RERANKER_MODEL`     | `rerank-multilingual-v3.0`   | Cohere rerank model (Cohere provider only)                                                                         |
| `COHERE_API_KEY`     | empty                        | Cohere API key (Cohere provider only)                                                                              |
| `RERANK_TOP_K`       | `50`                         | how many BM25 candidates are reranked                                                                              |
| `RERANK_MAX_CHARS`   | `2000`                       | characters of each decision sent to the cross-encoder                                                              |
| `RERANKER_TIMEOUT_S` | `20`                         | reranker request timeout, in seconds                                                                               |

### Hybrid Section Retrieval

Section RAG retrieval from the Elasticsearch `<source>_sections` indexes; see
[hybrid-retrieval.md](../hybrid-retrieval.md).

| Variable                   | Default  | Description                                                                                                                                         |
| -------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| `HYBRID_RETRIEVAL_ENABLED` | off      | read RAG section chunks from ES `<source>_sections` (dense kNN) instead of ChromaDB; build the indexes first with `manage.py embed_sections_to_es`  |
| `HYBRID_EMBED_ENGINE`      | `openai` | embedding engine (`openai` or `hactar`) used both to build the section indexes and to embed queries; must match the engine the index was built with |
| `HYBRID_TOP_K_PER_SECTION` | `8`      | chunks kept per section for each decision                                                                                                           |
| `HYBRID_SEARCH_SIZE`       | `40`     | kNN hits retrieved per decision before grouping them by section                                                                                     |

### Response Cache

Opt-in per-user cache for document-content payloads; see
[performance.md](../performance.md).

| Variable                 | Default | Description                                                                                                                   |
| ------------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `RESPONSE_CACHE_ENABLED` | off     | cache document-content payloads per user in Redis (the `documents` cache alias); when off, that alias is a no-op `DummyCache` |
| `RESPONSE_CACHE_TTL`     | `300`   | cache entry lifetime, in seconds                                                                                              |

The on/off flags in these three tables are on when set to `1`, `true`, `yes` or
`on` (case-insensitive) and off otherwise. The numeric settings fall back to
their defaults when unset, empty or not a number, because the deployment renders
`.env` from `.env.tpl` and an unset variable arrives as an empty string.

### Performance and Clustering

| Variable                 | Description                                                                                          |
| ------------------------ | ---------------------------------------------------------------------------------------------------- |
| `NUMBER_THREADS_ALLOWED` | multiprocessing and worker parallelism                                                               |
| `NUMBER_TRIALS`          | Optuna trials for clustering optimization                                                            |
| `NUMBER_OPTUNA_JOBS`     | parallel Optuna workers                                                                              |
| `NUMBA_CACHE_DIR`        | writable cache directory for Numba/PacMAP compiled functions; defaults to `/tmp/literev/numba-cache` |

## Tooling Configuration

`pyproject.toml` is configured so the dev tools understand both the Django app
and the standalone libraries:

- `setuptools` packages only the Django application from `src/backend/`.
- The root project depends on every `libs/lr-*` library through local workspace
  dependencies.
- `pytest` sets `pythonpath` to `src/backend/` plus every `libs/*/src` root.
- `ruff`, `mypy`, `coverage`, and `vulture` include both trees.
- The import-boundary suite validates that packages under `libs/` stay
  Django-free.

## Operational Notes

- Keep secrets in `.env` files or CI secrets, never in source code.
- New environment-backed behavior belongs in the relevant settings module and
  this document.
- New shared library code should prefer explicit config objects passed from the
  app layer over direct settings access.
