# Django Application

The Django application is the core service of literev-legal. It provides:

- A REST API (Django REST Framework) for the frontend and external clients
- Celery-backed async task dispatch (document processing, clustering, RAG, scoring)
- Django management commands for CLI-driven pipeline operations and diagnostics
- An admin interface and Jupyter integration for exploratory work

For service startup, migrations, superuser creation, and Jupyter, see [containers.md](containers.md).

---

## Management Commands

Django management commands provide CLI access to pipeline operations, data processing, and diagnostics. All commands live in [src/literev/management/commands/](../../src/literev/management/commands/).

```bash
python manage.py <command_name> [options]
# or via makim (preferred):
makim django.run-command -- <command_name> [options]
```

---

### cache_embeddings

Generate and cache a FAISS index of document embeddings for fast nearest-neighbor search.

```bash
python manage.py cache_embeddings \
    --project-id 42 \
    [--chamber CHAMBER_NAME]
```

Loads preprocessed documents, generates embeddings, builds a FAISS index, and saves it to `LITEREV_CACHE_DIR/faiss/`. Use after initial clustering to enable fast retrieval without ChromaDB for large corpora.

---

### classify_document_sentences

Run French legal section classification (Majeure / Mineure-Faits / Mineure-Subsommation / Conclusion) on all documents in a project.

```bash
python manage.py classify_document_sentences \
    --project-id 42 \
    [--output /path/to/output.json]
```

Requires `OPENAI_API_KEY`.

---

### count_documents_chambre

Count total documents per court chamber in a given Elasticsearch index.

```bash
python manage.py count_documents_chambre \
    --index-name literev \
    [--date-from 2020-01-01] \
    [--date-to 2024-12-31]
```

Use before running a project to understand corpus size by chamber and calibrate date range.

---

### count_tokens

Display token count statistics for all documents in a project.

```bash
python manage.py count_tokens --project-id 42
```

Outputs total / mean / median / max tokens per document. Use before RAG runs to check documents fit within LLM context windows.

---

### extract_mineur_majeur

Extract minor/major premise sections from all documents in a project and save to a structured JSON file.

```bash
python manage.py extract_mineur_majeur \
    --project-id 42 \
    --output /opt/data/literev/extractions/project_42.json
```

Output format:
```json
{
  "record_key_1": {
    "majeure": "...",
    "mineure_faits": "...",
    "mineure_subsommation": "...",
    "conclusion": "..."
  }
}
```

Requires `OPENAI_API_KEY`.

---

### faithfulness_metrics

Benchmark faithfulness scoring performance — measures per-document processing time.

```bash
python manage.py faithfulness_metrics \
    --project-rag-id 15 \
    [--use-hhem]
```

Useful for capacity planning before running large RAG jobs.

---

### fetch_documents

Verify database connectivity and volume write permissions.

```bash
python manage.py fetch_documents --project-id 42
```

Tests PostgreSQL connection, write access to `CONTAINER_VOLUME_DATA_DIR`, and retrieves document count. Diagnostic command for deployment troubleshooting.

---

### fill_order_cluster

Backfill `Cluster.order` for existing clusters where order was not set during creation.

```bash
python manage.py fill_order_cluster --project-id 42
```

Orders clusters by document count (descending). Use after clustering on data that pre-dates the `order` field.

---

### get_record_keys

Extract French legal section labels for documents and store them indexed by `record_key`.

```bash
python manage.py get_record_keys \
    --project-id 42 \
    [--chamber CHAMBER_NAME]
```

Output: JSON file at `LITEREV_CACHE_DIR/record_keys/`.

---

### optimize_documents

Run clustering optimization with advanced text analysis.

```bash
python manage.py optimize_documents \
    --project-id 42 \
    [--n-trials 100] \
    [--n-jobs 4]
```

Rebuilds TF-IDF matrix and runs an extended Optuna hyperparameter search. Use when initial clustering quality (DBCV score) is unsatisfactory.

---

### prepare_classified_documents

Prepare documents for embedding by chamber before ChromaDB ingestion.

```bash
python manage.py prepare_classified_documents \
    --index-name literev \
    --chamber "Chamber I" \
    --output /opt/data/literev/prepared/
```

Run before `run_chromadb_embeddings` when chamber-specific RAG is needed.

---

### prepare_input

Extract minor/major sections in a format ready for embedding pipelines.

```bash
python manage.py prepare_input \
    --project-id 42 \
    --output /opt/data/literev/input/project_42/
```

---

### process_corpus

Manually run the full preprocessing pipeline for all documents matching an Elasticsearch index and date range.

```bash
python manage.py process_corpus \
    --index-name literev \
    --date-from 2020-01-01 \
    --date-to 2024-12-31 \
    [--n-workers 8]
```

Collects documents from ES, runs preprocessing (language detection, lemmatization), and updates `Document.preprocessed_document` in DB. Use for bulk reprocessing after pipeline changes.

---

### document_cluster_optimization

Standalone clustering optimization — runs the full clustering pipeline independently of the web UI.

```bash
python manage.py document_cluster_optimization \
    --project-id 42 \
    [--study-name custom-study-v2]
```

Use when you need to re-cluster without going through the Django UI, or with a custom Optuna study name.

---

### run_chromadb_embeddings

Generate and store document embeddings in ChromaDB for RAG retrieval.

```bash
python manage.py run_chromadb_embeddings \
    --project-id 42 \
    [--collection-name project_42_rag] \
    [--batch-size 50]
```

Splits text into chunks, generates embeddings (`text-embedding-3-large` or Hactar), and stores them in ChromaDB. Pre-populate before running RAG queries on large projects for faster response.

- `OPENAI_API_KEY` for OpenAI embeddings
- `USE_HACTAR_LLM=true` + `HACTAR_API_KEY` for local embeddings

---

## Running Commands in Production

```bash
# Via makim (recommended)
makim django.run-command -- classify_document_sentences --project-id 42

# Directly via docker exec
docker exec -it literev python manage.py classify_document_sentences --project-id 42

# Via docker compose
docker compose exec literev python manage.py fill_order_cluster --project-id 42
```

---

## Writing a New Management Command

```python
# src/literev/management/commands/my_command.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Description of what this command does"

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int, required=True)
        parser.add_argument("--output", type=str, default=None)

    def handle(self, *args, **options):
        project_id = options["project_id"]
        self.stdout.write(f"Processing project {project_id}...")
        self.stdout.write(self.style.SUCCESS("Done."))
```

Use `self.stdout.write()` (not `print()`), `self.style.SUCCESS/ERROR/WARNING` for colored output, and `--dry-run` for commands that modify data.

---

## Testing

The test suite uses pytest with the Django plugin. Integration tests use a real PostgreSQL database, real Redis, and a real Celery worker.

- Test suite: [src/literev/tests/](../../src/literev/tests/)
- Fixtures: [src/conftest.py](../../src/conftest.py)
- pytest config: [pyproject.toml](../../pyproject.toml)

### Running Tests

```bash
# All tests (recommended)
makim tests.unit

# Directly
pytest src/

# With coverage
pytest src/ --cov=src --cov-report=term-missing

# Specific file or function
pytest src/literev/tests/api/test_rag_views.py
pytest src/literev/tests/api/test_rag_views.py::test_rag_creates_project_rag

# By keyword
pytest -k "rag"
```

Minimum coverage: **35%** (enforced by CI).

### Test Structure

```
src/
  conftest.py              # project-level fixtures (user, project, document, celery)
  literev/
    tests/
      api/
        test_rag_views.py        # ProjectRAG API endpoint tests
        test_table_choice.py     # UpdateTableChoiceAPIView tests
        test_serializers.py      # Serializer output tests
        test_permissions.py      # IsProjectRAGOwner tests
      etl/
        test_parsing.py          # Boolean query parser tests
        test_preprocessing.py    # Text normalization tests
        test_clustering.py       # Clustering pipeline tests
      test_models.py             # Model field + method tests
      test_rag_pipeline.py       # End-to-end RAG task tests
```

### Key Fixtures

| Fixture | Description |
|---|---|
| `user` | Test User instance |
| `project` | Project owned by `user` |
| `document` | Document associated with `project` |
| `document_real` | Real pickled Document with French legal text |
| `api_client` | Unauthenticated DRF APIClient |
| `authenticated_api_client` | APIClient authenticated as `user` |
| `setup` | Flushes Redis and starts a real Celery worker |

### Conventions

**Do not mock Celery tasks** in integration tests. Use `task.apply()` for synchronous execution.

API permission pattern:
```python
def test_unauthenticated_returns_403(api_client, project):
    response = api_client.get(f"/api/project/{project.id}/rag/")
    assert response.status_code in (401, 403)

def test_non_owner_returns_404(authenticated_api_client, db):
    other_project = Project.objects.create(...)
    response = authenticated_api_client.get(f"/api/project/{other_project.id}/rag/")
    assert response.status_code == 404  # 404 to prevent information leakage
```

Mark flaky integration tests:
```python
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_celery_task_with_timing_sensitivity(...): ...
```

### Linters

```bash
# All checks (same as CI)
makim tests.lint

# Individual tools
ruff check src/        # linting
ruff format --check src/  # formatting
mypy src/              # type checking
bandit -r src/         # security scanning
djlint src/ --check    # template linting

# Auto-fix
ruff format src/
ruff check --fix src/
```

### CI Pipeline

GitHub Actions runs on every push and PR to `main`: linters first (`pre-commit`), then `pytest src/ --cov=src --cov-fail-under=35` against real PostgreSQL + Redis.
