# Documentation Index

Technical documentation for `literev-legal`, a French legal document analysis platform for judicial corpora.

## Source Layout

The codebase now has split application roots plus standalone per-library source roots:

- `src/backend/`: Django application code, ORM models, views, DRF endpoints, Celery tasks, app-local helpers under `literev/libs/`, static files, and configuration.
- `src/frontend/`: React frontend for the gradual hybrid migration. Public routes (`/`, `/team/`, `/product/`, `/company/`, `/blog/`) plus the authenticated `/search/`, `/running/`, `/historicalpage/`, `/project/<id>/`, `/tableselect/...`, `/contentdocument/<id>`, `/contentdocument_highlighted/<rag_id>/`, and `/rag/<project_id>/` workflows now render through a minimal Django generic template and are routed inside React. The shared navbar and shell behavior for those migrated routes also live in React, while Django/allauth pages remain server-rendered and the remaining workflow pages stay Django-template based.
- `libs/<name>/src/`: framework-free `lr_*` packages for reusable query, search, preprocessing, clustering, refinement, RAG, and legal logic.

Use `src/backend/` for anything that touches Django, settings, persistence, or HTTP. Use `src/frontend/` for React-rendered routes and client UI. Keep the shared algorithms in `libs/` free of Django imports.

## Start Here

| Document | Description |
|---|---|
| [architecture.md](architecture.md) | Current system layout, dependency boundaries, and end-to-end data flow |
| [contributing.md](contributing.md) | Local setup, coding workflow, source-root conventions, and contribution checklist |
| [services/configuration.md](services/configuration.md) | Environment variables, settings modules, and dependency-based library installation |
| [services/django.md](services/django.md) | Django service responsibilities, app-layer conventions, and test commands |

## Services & Operations

| Document | Description |
|---|---|
| [services/containers.md](services/containers.md) | Docker Compose, Sugar, and container lifecycle |
| [services/celery.md](services/celery.md) | Celery workers, async task execution, and Redis wiring |
| [services/deployment.md](services/deployment.md) | Production deployment and operational concerns |
| [services/elasticsearch.md](services/elasticsearch.md) | Elasticsearch indexing and search infrastructure |

## Test Commands

```bash
makim tests.lint
makim tests.import-boundaries
makim tests.lib --lib lr-query
makim tests.libs-all
makim tests.app
makim tests.reactjs
# frontend coverage is written to src/frontend/coverage/
```

## Quick Reference

```bash
makim containers.start
makim django.migrate
makim reactjs.install
makim reactjs.build
makim tests.reactjs
makim django.collectstatic
makim tests.app
makim tests.lib --lib lr-rag
makim tests.import-boundaries
```
