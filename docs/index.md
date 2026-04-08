# Documentation Index

Technical documentation for literev-legal — a French legal document analysis platform.

---

## Start Here

| Document | Description |
|---|---|
| [architecture.md](architecture.md) | System overview, component diagram, full data flow, technology choices |
| [contributing.md](contributing.md) | Developer setup guide (environment, Docker, git workflow) |

---

## Core Components

| Document | Description |
|---|---|
| [pipeline.md](pipeline.md) | End-to-end data pipeline: ES collection → preprocessing → clustering |
| [models.md](models.md) | All 10 Django database models with field descriptions and relationships |
| [api.md](api.md) | REST API endpoints, serializers, permissions, request/response formats |
| [clustering.md](clustering.md) | TF-IDF → PaCMAP → HDBSCAN + Optuna hyperparameter optimization |
| [rag.md](rag.md) | RAG Q&A pipeline: chunking, embedding, generation, citation, confidence scoring |
| [parsing.md](parsing.md) | Boolean query parser: lexer, AST, Elasticsearch DSL generation |
| [nlp.md](nlp.md) | NLP module: cluster labeling, LLM backends, token budget management |

---

## User-Facing Features

| Document | Description |
|---|---|
| [refinement.md](refinement.md) | Document refinement workflow: TableChoice, iterations, neighbor expansion |
| [scoring.md](scoring.md) | Faithfulness scoring, similarity scoring, document sorting |
| [legal.md](legal.md) | French legal text classification: Majeure / Mineure-Faits / Conclusion |

---

## Operations & Infrastructure

| Document | Description |
|---|---|
| [configuration.md](configuration.md) | Environment variables, settings modules, Docker env setup |
| [celery.md](celery.md) | Async task queue, Redis, task chaining, worker configuration |
| [testing.md](testing.md) | Test suite, fixtures, conventions, CI pipeline |
| [management_commands.md](management_commands.md) | All 15 Django CLI commands with usage examples |

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
