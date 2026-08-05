# Infrastructure & Deployment Topology

Where the **current** LiteRev Legal deployment runs, how it is deployed, and a
non-destructive checklist for inspecting it. This document contains **no
secrets** — only hostnames and public DNS facts. Real credentials live in the
`.env` on each server and with the team (see [SECURITY.md](../SECURITY.md)).

> The facts below were derived from the repository's production compose/nginx
> config and from public DNS of the project's own domains. Confirm anything
> operational against the live boxes before acting on it.

---

## Topology

| Component                                     | Domain                | Resolves to                                  | Hosting                               |
| --------------------------------------------- | --------------------- | -------------------------------------------- | ------------------------------------- |
| Web app + Celery + PostgreSQL + Redis + nginx | `literev.unige.ch`    | `129.194.212.21` (PTR `lmedapp746.unige.ch`) | **University of Geneva, on-premises** |
| Elasticsearch (the decision corpus)           | `es.literev.com:9201` | `95.217.176.32` (PTR `*.your-server.de`)     | **Hetzner (Finland)**                 |
| LLM proxy (optional, `USE_HACTAR_LLM`)        | `hactar.unige.ch`     | University of Geneva                         | University of Geneva                  |

Two distinct machines, two owners:

- **App box (`lmedapp746.unige.ch`, UNIGE on-prem)** runs _everything except the
  corpus_ — the Django app (gunicorn), Celery worker, PostgreSQL, Redis and the
  nginx TLS terminator, all as Docker containers via the compose `prod` profile.
- **ES box (Hetzner, `es.literev.com`)** hosts the Elasticsearch corpus over
  plain HTTP on `:9201` with basic-auth (`elastic`). It is **shared** — CI and
  any other consumer point at it.

```
                 Internet
                    │  443/80 (Let's Encrypt via certbot)
                    ▼
        ┌───────────────────────────────┐            ┌──────────────────────┐
        │  lmedapp746.unige.ch (UNIGE)   │   9201     │  es.literev.com      │
        │  nginx → gunicorn (Django)     │  ───────▶  │  (Hetzner, Finland)  │
        │  Celery · PostgreSQL · Redis   │  http/es   │  Elasticsearch corpus│
        └───────────────────────────────┘            └──────────────────────┘
                    │
                    └── hactar.unige.ch (optional LLM proxy)  ·  OpenAI API (embeddings/RAG)
```

---

## How it is deployed

Deployment is **manual and local to the app box** — there is no CI/CD pipeline
and no SSH/remote host in the repository. Someone with access logs into the app
box and runs:

```bash
makim deploy-production.all-containers
# = sugar --profile prod compose-ext build && ... restart -- -d
```

- **TLS:** Let's Encrypt via the certbot container; domain from `CERTBOT_DOMAIN`
  (`literev.unige.ch`).
- **Ports exposed publicly:** only `80` and `443` (nginx). PostgreSQL, Redis and
  the app port stay on the internal Docker network.
- **Data & backups:** persistent data under `/opt/data/literev`; database dumps
  via `makim containers.postgres-dump-database` → `/opt/data/literev/backup`
  (`pg_dumpall`, gzipped).

---

## What is _not_ in the repository

These live only on the boxes / with the team and cannot be recovered from git:

- SSH access to `lmedapp746.unige.ch` (accounts, keys) — managed by UNIGE IT /
  the maintainers.
- The production `.env` on the app box (the real PostgreSQL / Redis / ES
  passwords).
- The Hetzner account that owns the ES box.

---

## Read-only inspection checklist

Run these **on the app box** once you have SSH access. All are non-destructive —
they read state, change nothing. Do not paste their output anywhere it could be
seen; the `.env` in particular holds live credentials.

```bash
docker ps                       # running containers (app / celery / postgres / redis / nginx)
docker compose ls               # which compose project & profile is live
# locate the deployment checkout and its .env (path may vary):
docker inspect "$(docker ps -qf name=literev)" \
  --format '{{ range .Mounts }}{{ .Source }} -> {{ .Destination }}{{ println }}{{ end }}'
ls -lh /opt/data/literev/backup # confirm a RECENT backup exists BEFORE any change
```

To confirm which Elasticsearch the app is actually bound to (reads the env of
the running container, not a file):

```bash
docker exec "$(docker ps -qf name=literev)" printenv \
  | grep -E '^ES_HOST_URL=|^ES_USERNAME='   # note: not ES_PASSWORD
```

---

## Running a new version safely (isolation)

To trial the modernised app **without any risk to the live deployment**, run it
on a **separate host with its own PostgreSQL, Redis and Elasticsearch** (e.g. a
fresh Hetzner VM). Import decisions into _that_ Elasticsearch — never point a
test instance at `es.literev.com` (shared) or the UNIGE app box. Nothing above
is touched until you deliberately choose to promote the new version.

### Credential-rotation impact (for when you do rotate)

- **PostgreSQL** password → change inside the postgres container on the app box
  and its `.env`; affects only that box.
- **Elasticsearch** password → change on the Hetzner ES box **and** update every
  consumer (the app box `.env`, the `ES_PASSWORD` CI secret, any other client).
  Because the ES box is shared, rotate it as a coordinated change, not in
  isolation.
