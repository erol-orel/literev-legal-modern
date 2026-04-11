# Documentation Index

Technical documentation for `literev-legal`, a French legal document analysis platform for judicial corpora.

## Source Layout

The codebase now has one application source root plus standalone per-library source roots:

- `src/`: Django application code, ORM models, views, Celery tasks, repositories, services, presenters, and configuration.
- `libs/<name>/src/`: framework-free `lt_*` packages for reusable query, search, preprocessing, clustering, refinement, RAG, and legal logic.

Use the `src/` layer for anything that touches Django, settings, persistence, or HTTP. Keep the shared algorithms in `libs/` free of Django imports.

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
makim tests.lib --lib lt_query
makim tests.libs-all
makim tests.app
```

## Quick Reference

```bash
makim containers.start
makim django.migrate
makim tests.app
makim tests.lib --lib lt_rag
makim tests.import-boundaries
```
