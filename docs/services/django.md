# Django Service

The Django service is the application-facing layer of `literev-legal`. It owns HTTP handling, persistence, Celery integration, and all settings-backed wiring.

## Responsibilities

Keep these concerns in `src/backend/`:

- Django models, ORM queries, migrations, and admin integration.
- Template views and Django REST Framework endpoints.
- Celery tasks and workflow orchestration.
- Settings access and environment-backed configuration.
- App-only adapters that translate between Django models and framework-free contracts.

The new `src/frontend/` folder is reserved for the gradual React migration. Until that migration is complete, the existing HTML pages and static assets still live under `src/backend/`.

## App-Layer Structure

```text
src/backend/literev/
  services/       orchestration and settings-backed adapters
  repositories/   ORM and file persistence helpers
  presenters/     template-facing and HTML-safe formatting helpers
  api/            DRF endpoints and serializers
  views.py        template views
  tasks.py        Celery tasks
```

The reusable logic lives in standalone folders under `libs/`. Django entrypoints rely on the installed environment to resolve those libraries, rather than mutating `sys.path` at startup.

## Management Commands

Management commands still live in `src/backend/literev/management/commands/`.
Use them through Django directly or through `makim` when a task already exists. `makim django.collectstatic` now uses the same approach as the main `literev` repository and runs `reactjs.install` plus `reactjs.build` before Django collects static files.

```bash
python src/backend/manage.py <command>
makim django.migrate
makim django.makemigrations --check
```

## Test Commands

Use the split test suites that match the new architecture:

```bash
makim tests.app
makim tests.reactjs
makim tests.lib --lib lr_query
makim tests.libs-all
makim tests.import-boundaries
```

Guidance:

- Use `tests.app` when the change touches Django models, repositories, views, serializers, permissions, or Celery tasks.
- Use `tests.reactjs` when the change touches browser-side code under `src/frontend/`; it now pre-runs `reactjs.install` plus `reactjs.build`, then generates frontend coverage output under `src/frontend/coverage/` while executing the unit suite.
- Use `tests.lib --lib <name>` for framework-free package changes under `libs/lr_*/src` and `libs/lr_*/tests`; the task now records per-library coverage for the PR summary comment.
- Run `tests.import-boundaries` whenever moving logic between `src/backend/` and `libs/`.

## CI Layout

The main GitHub Actions workflow now mirrors the architecture:

- `linter`: repo-wide formatting, linting, and static analysis.
- `import_boundaries`: ensures `libs/` stays free of Django imports.
- `lib_tests`: matrix job over changed `lr_*` packages on pull requests.
- `app_tests`: Django regression suite when app-side code or shared tooling changes.
- `coverage_report`: sticky pull-request comment that aggregates the app and per-library coverage summaries, even when one of the test jobs fails, and includes run metadata so reruns visibly refresh the same comment.

On pushes to `main`, the workflow runs the full regression set across all libraries plus the app suite.
