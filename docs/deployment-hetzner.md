# Deploying a standalone instance on a Hetzner VM

This runbook stands up the modern LiteRev Legal app as a **self-contained,
independent instance** ("entity #2") on a single Hetzner VM: its own PostgreSQL,
Redis, Elasticsearch and app — decoupled from the production UNIGE stack
(entity #1, see [infrastructure.md](infrastructure.md)). It also shows how to
seed the new instance with a **read-only copy** of the Geneva corpus and add the
**Tribunal fédéral** decisions, so both are searchable together.

Contains **no secrets** — fill credentials into the VM's git-ignored `.env`.

## Why one ES per instance

`literev.libs.collectors.ElasticSearchCollector` builds every connection from a
single `ES_HOST_URL` / `ES_USERNAME` / `ES_PASSWORD`. **One app instance talks
to exactly one Elasticsearch cluster.** To search Geneva **and** federal
together they must live in the **same** ES. So this instance runs its own ES
holding a copy of Geneva + the federal indices — nothing is written to the
shared production ES.

## Machine legend

- 🌐 **[BROWSER]** — Hetzner Cloud console
- 🖥️ **[LAPTOP]** — your machine
- ☁️ **[VM]** — the new Hetzner server (over SSH)
- 🏛️ **[UNIGE]** — the existing production box (one optional read-only step)

> **Shell tip:** if a password contains `!`, interactive bash tries history
> expansion ("event not found"). Read secrets into a variable instead of typing
> them on the command line — `read -rs VAR` — or single-quote the value, or
> `set +H` first.

---

## Phase 0 — Size it 🖥️ [LAPTOP]

Check the corpus size so you size disk/RAM (the `!`-safe way):

```bash
read -rs ES_RO_PW           # paste the read-only ES password, Enter
curl -u "elastic:$ES_RO_PW" \
  "http://es.literev.com:9201/_cat/indices/chambre_*?v&h=index,docs.count,store.size"
```

- **Federal-French test only:** CPX41 (8 vCPU / 16 GB / 240 GB) is plenty.
- **Copying the full Geneva corpus too:** RAM/disk ≳ 2–3× the summed `store.size`
  — e.g. CCX33 (8 dedicated vCPU / 32 GB) plus a Hetzner Volume. ES heap wants
  about half the RAM.

## Phase 1 — Create the server 🌐 [BROWSER]

Add Server → Ubuntu 24.04 → the type from Phase 0 → **attach your SSH key** →
(optional) attach a Volume for ES data → Create. Note the public IP.

## Phase 2 — Harden the OS ☁️ [VM] (`ssh root@<IP>`)

```bash
adduser deploy && usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
apt update && apt -y upgrade && apt -y install ufw fail2ban unattended-upgrades
ufw default deny incoming && ufw default allow outgoing
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
systemctl enable --now fail2ban
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/; s/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
  /etc/ssh/sshd_config && systemctl restart ssh
```

Reconnect as the non-root user: 🖥️ `ssh deploy@<IP>`. Only 80/443 are public;
ES/DB/Redis stay on the internal Docker network.

## Phase 3 — Tooling, code, env ☁️ [VM]

```bash
curl -fsSL https://get.docker.com | sudo sh && sudo usermod -aG docker $USER && newgrp docker
"${SHELL}" <(curl -L micro.mamba.pm/install.sh)
git clone https://github.com/erol-orel/literev-legal-modern.git && cd literev-legal-modern
micromamba env create -f conda/base.yaml && micromamba activate literev-legal
./scripts/install-dev.sh
cp .env.tpl .env
```

Edit `.env` — point it at the VM's **own** ES (built next). Generate secrets with
`openssl rand -base64 30`:

```
USE_CONTAINER=True
OPENAI_API_KEY=<your key>
DJANGO_SECRET_KEY=<openssl rand -base64 48>
POSTGRES_PASSWORD_LITEREV=<openssl rand -base64 30>
ES_HOST_URL=http://literev-elasticsearch:9200
ES_USERNAME=elastic
ES_PASSWORD=<openssl rand -base64 30>     # this VM's OWN es password
ES_SSL_CERTS=False
FRONTEND_HOST_PORT=8000
```

## Phase 4 — Data services + the VM's own ES ☁️ [VM]

```bash
makim containers.host-setup
makim containers.redis-setup
sugar compose build && sugar compose-ext restart --services literev-postgres literev-redis -- -d

# Single-node ES for this instance; whitelist the prod ES so we can pull from it.
docker run -d --name literev-elasticsearch --network literev \
  -e discovery.type=single-node -e xpack.security.enabled=true \
  -e "ELASTIC_PASSWORD=$(grep ^ES_PASSWORD .env | cut -d= -f2)" \
  -e "reindex.remote.whitelist=es.literev.com:9201" \
  -e "ES_JAVA_OPTS=-Xms4g -Xmx4g" \
  -v /opt/data/literev/esdata:/usr/share/elasticsearch/data \
  docker.elastic.co/elasticsearch/elasticsearch:8.14.3
```

## Phase 5 — Copy the Geneva corpus in (read-only pull from prod) ☁️ [VM]

`reindex-from-remote` makes the **new** ES scan the production ES; production is
only read. Use a read-only prod user if you created one.

```bash
read -rs ES_RO_PW           # prod read-only password (!-safe)
NEWES="http://elastic:$(grep ^ES_PASSWORD .env | cut -d= -f2)@literev-elasticsearch:9200"

for idx in chambre_administrative chambre_penale chambre_civile; do
  docker run --rm --network literev curlimages/curl -s \
    -X POST "$NEWES/_reindex?wait_for_completion=false" \
    -H 'Content-Type: application/json' -d "{
      \"source\":{\"remote\":{\"host\":\"http://es.literev.com:9201\",
        \"username\":\"elastic\",\"password\":\"$ES_RO_PW\"},
        \"index\":\"$idx\",\"size\":1000},
      \"dest\":{\"index\":\"$idx\"}}"
done

# Watch until doc counts match production:
docker run --rm --network literev curlimages/curl -s "$NEWES/_cat/indices/chambre_*?v"
```

Huge corpus? Add a date-range `"query"` to copy a subset for a first look.

## Phase 6 — Initialise the app ☁️ [VM]

```bash
makim django.migrate
makim django.createsuperuser --email you@example.com
makim reactjs.install && makim reactjs.build && makim django.collectstatic
sugar compose-ext restart -- -d
```

## Phase 7 — Geneva RAG embeddings (choose one)

Section-based RAG for the chambers needs their ChromaDB collections, which live
as files on the prod box (`/opt/data/literev/cache/chroma_db`), **not** in ES.
Search and clustering work without this; only chamber RAG answers need it.

- **Copy from prod (fast, cheap)** 🏛️ [UNIGE] → ☁️ [VM] (needs SSH to the prod box):

  ```bash
  rsync -avz deploy@lmedapp746.unige.ch:/opt/data/literev/cache/chroma_db/ \
    /opt/data/literev/cache/chroma_db/
  ```

- **Or rebuild on the VM** (no prod access, but re-runs OpenAI embeddings — time
  and cost): `makim federal.embed --index chambre_administrative` and the same
  for `chambre_penale` / `chambre_civile`.

## Phase 8 — Add the Tribunal fédéral (French first) ☁️ [VM]

Using the `federal` makim wrappers:

```bash
makim federal.import --spider CH_BGer --index bundesgericht --language fr --limit 200
makim federal.embed  --index bundesgericht --max-workers 4
```

`federal.import` writes the decisions into the `bundesgericht` ES index;
`federal.embed` runs the same section-classification + `text-embedding-3-large`
pipeline the chambers use, producing a section-embedded Chroma collection. The
app then routes federal RAG through the section pipeline automatically. Start
with `--limit 200` to check quality/cost, then drop the limit and repeat with
`--language de` / `--language it`.

## Phase 9 — Use it 🖥️ [LAPTOP]

```bash
ssh -L 8000:localhost:8000 deploy@<IP>     # then open http://localhost:8000
```

New project → select the Geneva chambers **and** "Tribunal fédéral" as sources →
search / cluster / RAG across everything. For a public URL later, use the repo's
`compose.prod.yaml` nginx + certbot with a domain.

## Phase 10 — Redeploying after a merge ☁️ [VM]

Once the instance is up, shipping the latest `main` is a one-liner. From the
repo root, inside the activated env (`micromamba activate literev-legal`):

```bash
git fetch origin main && git merge --ff-only origin/main   # or just: ./scripts/deploy_now.sh
./scripts/deploy_now.sh
```

`scripts/deploy_now.sh` is idempotent: it fast-forwards to `origin/main`,
refreshes Python deps (`install-dev.sh` — picks up new packages such as
`python-docx`), applies migrations, reinstalls + rebuilds the frontend (picks up
new packages such as `dompurify`) and collects static assets, restarts the app
+ Celery, then polls `/status/` until healthy. Flags: `--skip-deps` and
`--skip-build` for fast, code-only restarts; `BRANCH=<name>` to deploy a branch.

### What each merged change needs on redeploy

| Change | What the redeploy must do | Covered by `deploy_now.sh`? |
| --- | --- | --- |
| Frontend (UI, sanitize, code-split) | `reactjs.install` + `reactjs.build` + `collectstatic` | ✅ |
| New backend dependency (e.g. `python-docx`) | `install-dev.sh` | ✅ |
| New/changed Django model | `django.migrate` | ✅ (no new migrations in the current batch) |
| New settings flag (e.g. `RERANK_ENABLED`, `SECTION_EMBED_ENGINE`) | edit `.env`, then restart | ⚠️ set the flag in `.env` first |

### Verification checklist 🖥️ [LAPTOP]

Tunnel in (`ssh -L 8000:localhost:8000 deploy@<IP>`) and confirm:

- [ ] `curl -fsS http://localhost:8000/status/` → `OK` (the script already waits on this).
- [ ] Landing page loads; **network tab** shows per-route JS chunks
      (`rag-page.*.js`, `tableselect-page.*.js`, …) loading on navigation — the
      code-split is live.
- [ ] Open a document with HTML content — it renders formatted (sanitizer keeps
      headings/lists/`<mark>`), and `<script>`-bearing content is stripped.
- [ ] Run a RAG question → the answer-first view shows the summary/verdict hero,
      the evidence rail, and the report panel.
- [ ] In the report panel, **Word** downloads a `.docx` that opens in Word with
      the question, summary, verdict, tables and cited decisions.
- [ ] (If reranking is enabled) `RERANK_ENABLED=true` in `.env` and the
      reranker container is reachable — a natural-language search reorders
      sensibly. See [reranking.md](reranking.md).

Rollback: `git checkout <previous-sha> && ./scripts/deploy_now.sh` (add
`--skip-deps` if dependencies did not change).

---

## Two separate entities

This design already yields two independent entities:

- **Entity #1** — the untouched UNIGE production stack (Geneva).
- **Entity #2** — this VM: its own ES (a copy of Geneva + federal), own DB, own
  app. Fully decoupled; experiment freely without affecting production.

To later run the **federal corpus as its own entity**, repeat this runbook on
another VM importing only `bundesgericht*` and skip the Phase 5 Geneva copy — no
architecture change needed.

## Safety notes

- Never point a test instance's `ES_HOST_URL` at `es.literev.com` for writes. The
  only interaction with production here is the **read-only** reindex pull in
  Phase 5. Confirm a fresh prod backup exists first (see
  [infrastructure.md](infrastructure.md)).
- Prefer a **read-only** ES user for the Phase 0 / Phase 5 pulls so the new box
  cannot modify the live corpus.
- Rotating the shared ES password is a coordinated change across every consumer;
  see the rotation notes in [infrastructure.md](infrastructure.md).
