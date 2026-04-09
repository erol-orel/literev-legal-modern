# Documentation Index

Technical documentation for literev-legal — a French legal document analysis platform.

---

## Start Here

| Document | Description |
|---|---|
| [architecture.md](architecture.md) | System overview, component diagram, full data flow, technology choices |
| [contributing.md](contributing.md) | Developer setup guide (environment, Docker, git workflow) |

---

## Operations & Infrastructure

| Document | Description |
|---|---|
| [services/containers.md](services/containers.md) | Docker Compose, sugar, makim tasks, build/start/stop/redis |
| [services/configuration.md](services/configuration.md) | Environment variables, settings modules, Docker env setup |
| [services/django.md](services/django.md) | Django app: management commands, testing, CI pipeline |
| [services/celery.md](services/celery.md) | Async task queue, Redis, task chaining, worker configuration |
| [services/deployment.md](services/deployment.md) | Production deployment, DB backup/restore, SSL, hardening |
| [services/elasticsearch.md](services/elasticsearch.md) | ES cluster config, data loading, snapshots, makim ES tasks |

---

## Quick Reference

### Run the test suite
```bash
makim tests.unit
```

### Start services locally
```bash
makim containers.start
```

### Apply database migrations
```bash
makim django.migrate
```

### Run linting
```bash
makim tests.lint
```

### Check all tasks
```bash
makim --help
```
