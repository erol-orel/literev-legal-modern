# Django Service

The Django service is the application-facing layer of `literev-legal`. It owns HTTP handling, persistence, Celery integration, and all settings-backed wiring.

## Responsibilities

Keep these concerns in `src/backend/`:

- Django models, ORM queries, migrations, and admin integration.
- Thin template views, the generic frontend entry view, and Django REST Framework endpoints.
- Celery tasks and workflow orchestration.
- Settings access and environment-backed configuration.
- App-only adapters that translate between Django models and framework-free contracts.

The `src/frontend/` folder now powers the React-owned public routes plus the authenticated `/search/`, `/running/`, `/historicalpage/`, `/project/<id>/`, `/tableselect/...`, `/contentdocument/<id>`, `/contentdocument_highlighted/<rag_id>/`, and `/rag/<project_id>/` pages through a minimal Django generic template (`generic.html`) and React Router. Shared layout chrome and navbar behavior for those migrated routes now live in React, while Django/allauth pages remain server-rendered. The remaining authenticated workflow pages still live under `src/backend/` until later migration stages land.

## App-Layer Structure

```text
src/backend/literev/
  libs/          app-local Django-aware helper modules (for example `libs/search.py`, `libs/project_listing.py`, `libs/project_overview.py`, `libs/table_selection.py`)
  api/           DRF endpoints and serializers (for example `api/search.py`, `api/project_lists.py`, `api/project_overview.py`, `api/table_selection.py`)
  templatetags/  Django template tags for frontend asset resolution
  views.py       remaining Django-template workflow views
  views_public.py generic frontend shell entry views
  tasks.py       Celery tasks
```

The reusable logic lives in standalone folders under repo-root `libs/`, while Django-specific helper modules stay under `src/backend/literev/libs/`. Django entrypoints rely on the installed environment to resolve those libraries, rather than mutating `sys.path` at startup. Frontend asset resolution now happens through `literev.templatetags.frontend`, `views_public.py` only provides minimal bootstrap context for the React app, and Django still enforces the primary login boundary through `AuthenticatedFrontendView` while the React router mirrors that boundary for in-app navigation. The search workflow exposes dedicated DRF endpoints under `/api/project/search/`, the running/historical workflow exposes dedicated DRF endpoints under `/api/project/running/`, `/api/project/historical/`, and `/api/project/projects/<id>/`, the project overview/refinement workflow exposes dedicated DRF endpoints under `/api/project/projects/<id>/overview/`, `/filters/preview/`, `/refinements/`, `/clusters/<cluster_id>/summary/`, and `/ask-top-docs/`, the table-selection workspace exposes dedicated DRF endpoints under `/api/project/tableselect/<project_id>/<refinement_id>/...` for state loading, iteration changes, selection persistence, bulk actions, export, and RAG hand-off, and the RAG workspace uses `/api/project/rag/<project_id>/context/`, `/api/project-rags-by-project/<project_id>/`, and `/api/project-documents-rag/?project_rag=<id>` for status and answers. The document content pages now consume `/api/project/documents/<id>/` and `/api/project/documents/rag/<rag_id>/highlighted/` for raw and highlighted document text.

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
makim tests.lib --lib lr-query
makim tests.libs-all
makim tests.import-boundaries
```

Guidance:

- Use `tests.app` when the change touches Django models, app-local helpers under `src/backend/literev/libs/`, views, serializers, permissions, or Celery tasks.
- Use `tests.reactjs` when the change touches browser-side code under `src/frontend/`; it now pre-runs `reactjs.install` plus `reactjs.build`, then generates frontend coverage output under `src/frontend/coverage/` while executing the unit suite.
- Use `tests.lib --lib <name>` with the kebab-case library directory name (for example `lr-query`) for framework-free package changes under `libs/lr-*/src` and `libs/lr-*/tests`; the task now records per-library coverage for the PR summary comment.
- Run `tests.import-boundaries` whenever moving logic between `src/backend/` and `libs/`.

## CI Layout

The main GitHub Actions workflow now mirrors the architecture:

- `linter`: repo-wide formatting, linting, and static analysis.
- `import_boundaries`: ensures `libs/` stays free of Django imports.
- `lib_tests`: matrix job over changed `lr-*` libraries on pull requests.
- `app_tests`: Django regression suite when app-side code or shared tooling changes.
- `coverage_report`: sticky pull-request comment that aggregates the app and per-library coverage summaries, even when one of the test jobs fails, and includes run metadata so reruns visibly refresh the same comment.

On pushes to `main`, the workflow runs the full regression set across all libraries plus the app suite.
