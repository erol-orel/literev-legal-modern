# lr-rag

Standalone RAG helper package for chunk preparation, answer payload shaping, and
cache key computation.

## Layout

- `src/lr_rag/`: package source code
- `tests/`: package-local test suite
- `pyproject.toml`: standalone package metadata

## Development

Install this package in editable mode from the library root when working on it
independently:

```bash
pip install -e .
pytest
```
