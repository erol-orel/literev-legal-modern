# lt-clustering

Standalone clustering primitives and orchestration built around TF-IDF, PaCMAP,
HDBSCAN, and Optuna.

## Layout

- `src/lt_clustering/`: package source code
- `tests/`: package-local test suite
- `pyproject.toml`: standalone package metadata

## Development

Install this package in editable mode from the library root when working on it
independently:

```bash
pip install -e .
pytest
```
