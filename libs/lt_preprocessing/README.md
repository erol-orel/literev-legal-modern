# lt-preprocessing

Standalone preprocessing helpers for French legal corpora. The runtime expects
the spaCy French model used by the main application environment.

## Layout

- `src/lt_preprocessing/`: package source code
- `tests/`: package-local test suite
- `pyproject.toml`: standalone package metadata

## Development

Install this package in editable mode from the library root when working on it
independently:

```bash
pip install -e .
pytest
```
