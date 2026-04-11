# lr-query

Standalone boolean-query parsing helpers with an optional
natural-language-to-boolean adapter powered by litellm.

## Layout

- `src/lr_query/`: package source code
- `tests/`: package-local test suite
- `pyproject.toml`: standalone package metadata

## Development

Install this package in editable mode from the library root when working on it
independently:

```bash
pip install -e .
pytest
```
