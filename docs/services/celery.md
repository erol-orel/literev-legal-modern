# Celery & Async Tasks

All long-running NLP and ML operations run as Celery tasks, decoupled from the HTTP request cycle. The application uses Redis as both the message broker and the result backend.

Source files:
- Celery app: [src/config/celery.py](../src/config/celery.py)
- Tasks: [src/literev/tasks.py](../src/literev/tasks.py)

---

## Configuration

```python
# src/config/celery.py
app = Celery("literev-celery")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["literev.tasks"])
```

Settings are read from Django settings with the `CELERY_` prefix (defined in `config/settings/base.py`):

```python
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
```

---

## Redis Connection

```python
def get_redis_client() -> redis.Redis:
    """
    Creates a Redis client from environment variables.
    
    Supports:
    - REDIS_URL (full URL string, takes precedence)
    - REDIS_HOST + REDIS_PORT + REDIS_DB + REDIS_USERNAME + REDIS_PASSWORD
    """
```

Redis ACL configuration restricts access to broker data only. See the contributing guide for Redis ACL setup details.

---

## Task Overview

Tasks are defined in `src/literev/tasks.py` and decorated with `@app.task`. They are triggered either:
- By API views (e.g. RAG task after POST to `/api/project/{id}/rag/`)
- By Django views (e.g. pipeline task after project creation)
- By management commands (e.g. embedding generation)

### Pipeline tasks

| Task | Triggered by | What it does |
|---|---|---|
| `fetch_and_process_documents` | Project creation | ES collection → preprocessing → clustering |
| `preprocess_documents_task` | Pipeline task | Run `literev_core.preprocessing` on all documents |
| `cluster_documents_task` | Pipeline task | TF-IDF → PaCMAP → HDBSCAN → Optuna |
| `generate_cluster_labels_task` | Pipeline task | LLM topic + summary generation per cluster |

### RAG tasks

| Task | Triggered by | What it does |
|---|---|---|
| `run_rag_task` | `POST /api/project/{id}/rag/` | Full RAG pipeline for a ProjectRAG |
| `score_rag_answers_task` | After `run_rag_task` | Faithfulness scoring for all answers |
| `generate_rag_summary_task` | After scoring | Overall summary generation |

### Embedding tasks

| Task | Management commands | What it does |
|---|---|---|
| `run_chromadb_embeddings_task` | `run_chromadb_embeddings` | Embed documents into ChromaDB |
| `cache_embeddings_task` | `cache_embeddings` | Pre-generate FAISS index |

---

## Task Chaining

Complex workflows use Celery canvas (chain, chord):

```python
from celery import chain, chord

# Pipeline chain: preprocessing → clustering → labeling
pipeline = chain(
    preprocess_documents_task.s(project_id),
    cluster_documents_task.s(),
    generate_cluster_labels_task.s(),
)
pipeline.apply_async()

# RAG chord: process all documents in parallel, then score
rag_workflow = chord(
    [get_answer_document_worker.s(doc_id) for doc_id in document_ids],
    score_rag_answers_task.s(project_rag_id),
)
rag_workflow.apply_async()
```

**chain**: tasks run sequentially, each passing its result to the next.  
**chord**: a group of parallel tasks whose results are collected and passed to a callback.

---

## Progress Tracking

Tasks update `Project.step` and `Project.step_number` during execution so the frontend can show progress:

```python
@app.task
def cluster_documents_task(project_id: int) -> None:
    project = Project.objects.get(pk=project_id)
    project.step = "clustering"
    project.step_number = 3
    project.save()
    
    # ... do clustering ...
    
    project.step = "labeling"
    project.step_number = 4
    project.save()
```

The frontend polls `GET /project/{id}/status/` to read these fields.

Task IDs are stored in `Project.actual_task_code` for task revocation:

```python
result = fetch_and_process_documents.apply_async(args=[project_id])
project.actual_task_code = result.id
project.save()
```

---

## Worker Configuration

### Development (local)

```bash
# Start worker (from project root, conda env active)
makim containers.start-celery
# or directly:
celery -A config.celery worker --loglevel=info --pool=prefork --concurrency=4
```

### Production (Docker)

The `literev-celery` service in `docker-compose.prod.yaml` runs:

```
celery -A config.celery worker \
  --loglevel=info \
  --pool=prefork \
  --concurrency=${NUMBER_THREADS_ALLOWED}
```

The worker process shares the same Docker image as the Django app but runs a separate entrypoint.

### Pool selection

| Pool | Use case |
|---|---|
| `prefork` | CPU-bound tasks (NLP, clustering) — default |
| `threads` | I/O-bound tasks (API calls) |
| `gevent` | High-concurrency I/O (not used by default) |

---

## Task Monitoring

### Celery Flower (optional)

```bash
celery -A config.celery flower --port=5555
# Access at http://localhost:5555
```

### Django admin task status

`ProjectRAG.status` shows the current state of each RAG task. Failed tasks appear with `status="failed"` — check Sentry or the Celery worker logs for the traceback.

### Revoking a stuck task

```python
# In Django shell: makim django.shell
from config.celery import app
app.control.revoke(task_id, terminate=True)

# Then reset the project state:
project.is_running = False
project.save()
```

---

## Testing with Celery

Tests use a real Celery worker (not mocked):

```python
# conftest.py
@pytest.fixture
def celery_worker_parameters() -> dict:
    return {"pool": "prefork", "concurrency": 1}

@pytest.fixture
def setup(celery_worker_parameters):
    """Sets up Redis + Celery test worker."""
    redis_flush()
    # worker is started by pytest-celery
    yield
```

**Do not mock Celery tasks** in integration tests — the project was burned by mock/real divergence in the past (see feedback memories). Use the real task runner with `task.apply()` (synchronous) for unit tests of task logic.

```python
# Synchronous execution for unit tests
result = fetch_and_process_documents.apply(args=[project_id])
assert result.successful()
```

---

## Error Handling in Tasks

```python
@app.task(bind=True, max_retries=3)
def run_rag_task(self, project_rag_id: int) -> None:
    try:
        project_rag = ProjectRAG.objects.get(pk=project_rag_id)
        # ... do work ...
    except SomeTransientError as exc:
        # Exponential backoff retry
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
    except Exception as exc:
        # Non-retryable failure
        project_rag.status = "failed"
        project_rag.save()
        raise  # re-raise for Sentry capture
```

Sentry SDK is configured in `prod.py` and automatically captures unhandled task exceptions.

---

## Environment Variables

| Variable | Description |
|---|---|
| `REDIS_HOST` | Redis hostname (default: `literev-redis`) |
| `REDIS_PORT` | Redis port (default: `6379`) |
| `REDIS_DB` | Redis database index (default: `0`) |
| `REDIS_URL` | Full Redis URL (overrides HOST/PORT/DB if set) |
| `REDIS_USERNAME` | Redis ACL username |
| `REDIS_PASSWORD` | Redis ACL password |
| `NUMBER_THREADS_ALLOWED` | Celery worker concurrency |
