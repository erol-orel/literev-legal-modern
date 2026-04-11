# Contributing

Contributions are welcome. The project mixes a Django application under `src/` with reusable framework-free libraries under `libs/`, so the main goal when contributing is to keep those boundaries clean.

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

The repository has one application root plus per-library source roots:

- `src/` for Django configuration, ORM code, views, API endpoints, Celery wiring, repositories, services, and presenters.
- `libs/<name>/src/` for each `lt_*` package that must remain free of Django imports and settings access.

When moving logic around, use this split:

- Put pure algorithms, contracts, and reusable helpers in `libs/`.
- Put settings-backed wiring and ORM/file persistence in `src/literev/services/` and `src/literev/repositories/`.
- Put HTML-safe formatting and template-facing helpers in `src/literev/presenters/`.

Install the project in editable mode before running Django entrypoints; the root package now resolves every `lt-*` library from `libs/` as a production dependency, and each library keeps its own `src/` layout.

## Development Workflow

Run the quality gates before opening a pull request:

```bash
makim tests.lint
makim tests.import-boundaries
makim tests.libs-all
makim tests.app
```

Useful focused commands:

```bash
makim tests.lib --lib lt_query
makim tests.lib --lib lt_rag
makim django.migrate
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
feat: extract refinement helpers into root libs
fix: avoid eager lt_query boolean-query dependency during lib imports
docs: document the src and per-lib source-root split
```

## Documentation

The most commonly updated documents are:

- `docs/architecture.md` for high-level structure and dependency direction.
- `docs/services/configuration.md` for settings and dependency-based library installation.
- `docs/services/django.md` for Django-side workflow and test commands.
- `docs/index.md` for navigation and quick-start commands.

## Release Notes

The project uses semantic-release. Pull request titles and squash-merge commit messages should follow Conventional Commits so versioning and changelog generation stay predictable.
