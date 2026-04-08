# Testing

The test suite uses pytest with the Django plugin. Integration tests use a real PostgreSQL database, real Redis, and a real Celery worker.

Source files:
- Test suite: [src/literev/tests/](../src/literev/tests/)
- Fixtures: [src/conftest.py](../src/conftest.py)
- pytest config: [pyproject.toml](../pyproject.toml)

---

## Running Tests

```bash
# Run all tests (recommended via makim)
makim tests.unit

# Or directly
pytest src/

# With coverage report
pytest src/ --cov=src --cov-report=term-missing

# Run a specific test file
pytest src/literev/tests/api/test_rag_views.py

# Run a specific test function
pytest src/literev/tests/api/test_rag_views.py::test_rag_creates_project_rag

# Run tests matching a keyword
pytest -k "rag"
```

---

## Coverage Requirement

Minimum coverage: **35%** (enforced by CI).

```toml
# pyproject.toml
[tool.coverage.report]
fail_under = 35
```

CI fails if coverage drops below this threshold. The threshold is intentionally conservative — contributions should add tests, not rely on the low floor.

---

## Test Structure

```
src/
  conftest.py              # project-level fixtures (user, project, document, celery)
  literev/
    tests/
      conftest.py          # app-level fixtures if any
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

---

## Fixtures (conftest.py)

All fixtures are defined in [src/conftest.py](../src/conftest.py):

### user

```python
@pytest.fixture
def user(db) -> User:
    """Creates and returns a test User instance."""
```

`db` is a pytest-django fixture that enables database access.

### project

```python
@pytest.fixture
def project(user) -> Project:
    """Creates a Project owned by `user` with default field values."""
```

### document

```python
@pytest.fixture
def document(project) -> Document:
    """Creates a Document associated with `project`."""
```

### document_real

```python
@pytest.fixture
def document_real(project) -> Document:
    """Loads a real pickled Document from test data files.
    Use for tests that need realistic French legal text."""
```

### api_client

```python
@pytest.fixture
def api_client() -> APIClient:
    """Returns an unauthenticated DRF APIClient."""
```

### authenticated_api_client

```python
@pytest.fixture
def authenticated_api_client(api_client, user) -> APIClient:
    """Returns an APIClient authenticated as `user`."""
```

### Celery fixtures

```python
@pytest.fixture
def celery_worker_parameters() -> dict:
    """Configures the Celery test worker: prefork pool, 1 worker."""
    return {"pool": "prefork", "concurrency": 1}

@pytest.fixture
def setup(celery_worker_parameters):
    """Flushes Redis and starts the Celery test worker.
    Use for tests that exercise async tasks."""
    redis_flush()
    yield
```

### redis_flush helper

```python
def redis_flush() -> None:
    """Clears all Redis keys. Falls back gracefully if ACL restricts FLUSHALL."""
```

---

## Test Conventions

### API tests

Use `APITestCase` (Django REST Framework) or pytest with the `authenticated_api_client` fixture:

```python
# Using pytest fixtures (preferred)
def test_get_project_rag(authenticated_api_client, project):
    response = authenticated_api_client.get(f"/api/project/{project.id}/rag/")
    assert response.status_code == 200
    assert response.data["status"] == "completed"

# Permission test pattern
def test_unauthenticated_returns_403(api_client, project):
    response = api_client.get(f"/api/project/{project.id}/rag/")
    assert response.status_code in (401, 403)

def test_non_owner_returns_404(authenticated_api_client, db):
    other_project = Project.objects.create(...)
    response = authenticated_api_client.get(f"/api/project/{other_project.id}/rag/")
    assert response.status_code == 404  # 404 to prevent information leakage
```

### Parsing tests

```python
def test_and_query():
    es_query = process_search_query_elasticsearch(
        "emploi AND licenciement",
        date(2020, 1, 1),
        date(2024, 12, 31),
    )
    assert "must" in es_query["bool"]
    assert es_query["bool"]["must"][0]["match"]["document_text"] == "emploi"

def test_empty_query_raises():
    with pytest.raises(EmptyQueryError):
        process_search_query_elasticsearch("", date(2020, 1, 1), date(2024, 12, 31))

def test_unmatched_parens():
    with pytest.raises(UnmatchedParenthesesError):
        tokenize_expression("(emploi AND travail")
```

### Celery / async task tests

```python
@pytest.mark.usefixtures("setup")  # starts real Celery worker + Redis
def test_rag_task_completes(project, document):
    project_rag = ProjectRAG.objects.create(
        project=project,
        query="Quel est le critère ?",
    )
    
    # Run task synchronously for testing
    run_rag_task.apply(args=[project_rag.id])
    
    project_rag.refresh_from_db()
    assert project_rag.status == "completed"
    assert ProjectDocumentRAG.objects.filter(project_rag=project_rag).exists()
```

**Do not mock Celery tasks** in integration tests. Use `task.apply()` for synchronous execution in unit tests.

### Boolean query edge cases to always test

The parsing module has a comprehensive test suite. Key cases:

```python
# All of these should work
"emploi"                                    # single term
"emploi AND licenciement"                   # AND
"emploi OR travail"                         # OR
"NOT pénale"                                # NOT at start
"(emploi OR travail) AND licenciement"      # nested
'"faute grave"'                             # quoted phrase
'"faute grave" AND emploi'                  # mixed
'(A AND B) NOT (C OR D)'                    # complex

# All of these should raise
""                                          # EmptyQueryError
"()"                                        # EmptyParenthesisError
'"unclosed'                                 # UnmatchedQuotesError
"(emploi AND travail"                       # UnmatchedParenthesesError
"AND emploi"                                # LogicalOperatorError
"emploi licenciement"                       # LogicalOperatorError (missing AND/OR)
```

---

## Flaky Tests

Some integration tests that depend on Celery worker startup or Redis timing can be flaky. Mark them with `pytest-rerunfailures`:

```python
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_celery_task_with_timing_sensitivity(...):
    ...
```

---

## Linters as Test Gates

Code quality tools run in CI before pytest. A failing linter blocks the test run:

```bash
# Run all code quality checks (same as CI)
makim tests.lint

# Individual tools
ruff check src/             # linting
ruff format --check src/    # formatting
mypy src/                   # type checking
bandit -r src/              # security scanning
djlint src/ --check         # template linting
```

Fix linting issues before running tests:

```bash
ruff format src/   # auto-format
ruff check --fix src/  # auto-fix safe issues
```

---

## CI Pipeline

GitHub Actions runs on every push and PR to `main`:

```yaml
# .github/workflows/main.yaml
jobs:
  quality:
    steps:
      - pre-commit run --all-files   # ruff, mypy, bandit, djlint, etc.
  
  test:
    needs: quality
    steps:
      - pytest src/ --cov=src --cov-fail-under=35
```

Tests run against a real PostgreSQL + Redis instance spun up by GitHub Actions.

---

## Test Data

Real document data for integration tests is stored as pickled Python objects in `src/literev/tests/` (git-tracked). The `document_real` fixture loads these.

For tests that exercise the classification pipeline, sample normalized French legal texts are in `docs/preprocessed_text0.txt`.

---

## Adding Tests for New Features

1. Create a test file in the appropriate directory:
   - API changes → `src/literev/tests/api/test_<feature>.py`
   - Pipeline/ETL → `src/literev/tests/etl/test_<feature>.py`
   - Model behavior → `src/literev/tests/test_models.py`

2. Use fixtures from `conftest.py` — do not recreate `user`, `project`, or `document` in each test

3. Test at minimum:
   - The happy path
   - Permission checks (unauthenticated, non-owner)
   - Invalid input (validation errors)

4. Run `makim tests.unit` and verify coverage did not drop
