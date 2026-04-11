# Contributing

Contributions are welcome. The project now splits application code between `src/backend/` and `src/frontend/`, alongside reusable framework-free libraries under `libs/`, so the main goal when contributing is to keep those boundaries clean.

## Local Setup

The supported runtime is Python `3.11`.

1. Clone the repository.
2. Create the conda environment from `conda/base.yaml`.
3. Activate the environment.
4. Install the project in editable mode with the development dependencies.

```bash
git clone git@github.com:thegraphnetwork-literev/literev-legal.git
cd literev-legal
mamba env create --file conda/base.yaml
conda activate literev-legal
./scripts/install-dev.sh
```

5. Create a feature branch.

```bash
git checkout -b name-of-your-change
```

## Source-Root Rules

The repository has split application roots plus per-library source roots:

- `src/backend/` for Django configuration, ORM code, views, API endpoints, Celery wiring, app-local helpers under `literev/libs/`, templates, and static files.
- `src/frontend/` for the React frontend application as the UI is migrated away from server-rendered pages, with routes/pages/components/browser-side libs owned by React.
- `libs/<name>/src/` for each `lr_*` package that must remain free of Django imports and settings access.

When moving logic around, use this split:

- Put pure algorithms, contracts, and reusable helpers in `libs/`.
- Put Django-aware, app-local helper logic in `src/backend/literev/libs/`.
- Put new browser-side application code in `src/frontend/`.

Install the project in editable mode before running Django entrypoints; the root package now resolves every `lr-*` library from `libs/` as a production dependency, and each library keeps its own `src/` layout.

## Development Workflow

Run the quality gates before opening a pull request:

```bash
makim tests.lint
makim tests.import-boundaries
makim tests.libs-all
makim tests.app
makim tests.reactjs
```

`makim tests.reactjs` also generates frontend coverage output under `src/frontend/coverage/`. GitHub Actions renders that JSON report into the PR coverage summary via `scripts/render_frontend_coverage_summary.py`. When editing `.github/workflows/*.yaml` or `.makim.yaml`, do not embed heredocs such as `<<'PY'`; put non-trivial shell or Python snippets in `scripts/` and call them from YAML.

Useful focused commands:

```bash
makim tests.lib --lib lr-query
makim tests.lib --lib lr-rag
makim django.migrate
makim reactjs.install
makim reactjs.build
makim tests.reactjs
makim django.collectstatic
makim containers.start
```

## Pull Request Checklist

Before opening or merging a pull request:

- Add or update tests for every behavior change.
- Update the relevant documentation in `docs/` when you change architecture, workflow, or public behavior.
- Keep `libs/` free of Django imports; the import-boundary suite should stay green.
- Run `makim tests.lint` and the relevant test commands locally.
- Use Conventional Commit style for the final commit or PR title.

## Commit Messages

Each standalone library now follows `libs/<name>/{pyproject.toml,README.md,src/<package>,tests}` so it can be moved into its own repository with minimal reshaping.

Examples:

```text
feat: add frontend unit tests and CI task wiring
fix: avoid eager lr_query boolean-query dependency during lib imports
docs: document the frontend/backend source-root split
```

## Documentation

The most commonly updated documents are:

- `docs/architecture.md` for high-level structure and dependency direction.
- `docs/services/configuration.md` for settings and dependency-based library installation.
- `docs/services/django.md` for Django-side workflow and test commands.
- `docs/index.md` for navigation and quick-start commands.

## Release Notes

The project uses semantic-release. Pull request titles and squash-merge commit messages should follow Conventional Commits so versioning and changelog generation stay predictable.
