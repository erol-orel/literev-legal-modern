# Elasticsearch

Elasticsearch stores Swiss legal court decisions and is the primary document source for all downstream processing (NLP classification, clustering, and vector search via ChromaDB).

---

## Cluster Configuration

| Setting | Value |
|---------|-------|
| Nodes | `es-legal-1`, `es-legal-2`, `es-legal-3` (3-node cluster) |
| Port | `9200` |
| Docker Compose | [`containers/compose.elasticsearch.yaml`](../../containers/compose.elasticsearch.yaml) |

Three indices are maintained, one per legal chamber:

| Index | Description |
|-------|-------------|
| `chambre_penale` | Penal court decisions |
| `chambre_civile` | Civil court decisions |
| `chambre_administrative` | Administrative court decisions |

---

## Environment Variables

Stored in `.envs/.elasticsearch.env` (generated from `.envs/.elasticsearch.env.tpl`):

```bash
ES_HOST_URL=http://localhost:9200   # Elasticsearch URL
ES_USERNAME=elastic                  # Basic auth username
ES_PASSWORD=...                      # Basic auth password
ES_SSL_CERTS=False                   # Path to CA cert, or False to disable
ES_INDICES=chambre_penale,chambre_civile,chambre_administrative
```

Additional Django settings in [`src/backend/config/settings/base.py`](../../src/backend/config/settings/base.py):

```python
ES_HOST_URL  = os.environ.get("ES_HOST_URL")
ES_USERNAME  = os.environ.get("ES_USERNAME")
ES_PASSWORD  = os.environ.get("ES_PASSWORD")
ES_SSL_CERTS = os.environ.get("ES_SSL_CERTS", False)
ES_SLICES    = getattr(settings, "ES_SLICES", 1)   # scroll parallelism
```

---

## Raw Document Format

Source documents are JSONL or JSON files exported from the court data provider. Each document uses French field names internally:

| Source field (French) | Indexed as | Description |
|----------------------|------------|-------------|
| `cle_fiche` | `record_key` | Unique document ID — used as the ES `_id` |
| `coll_nom` | `collector_name` | Chamber name (`chambre_penale`, etc.) |
| `document_text` | `document_text` | Plain text content of the decision |
| `document` | `document` | HTML version of the decision |
| `datedecision` / `dt_decision` | `decision_date` | Date of decision (source: `DD.MM.YYYY`) |
| `procedure` | `procedure_type` | Type of legal procedure |
| `decision` | `decision_type` | Type of decision (e.g., `ACJC/385/2025`) |
| `resume` | `summary` | Summary text |
| `normes` | `standards` | Referenced legal standards |
| `descripteurs` | `descriptors` | Keyword descriptors |
| `parties` | `parties` | Parties involved |
| `recours` | `recours` | Appeals array — each entry contains `chambre`, `date_debut`, `date_fin`, `type_recours`, `ts_creat`, `ts_modif` |
| `importance` | `importance` | Importance level |
| `publieinternet` | `published_internet` | Whether published online |
| `rectification` | `rectification` | Correction flag |

---

## Document Loading Pipeline

The full load is handled by [`scripts/elasticsearch_loader.py`](../../scripts/elasticsearch_loader.py), which contains four cooperating classes:

### DataReader
Reads a JSONL or JSON file line-by-line and yields raw document dicts.

### DataNormalizer
Normalizes date fields from the source format (`DD.MM.YYYY` or `DD/MM/YY HH:MM:SS.ffffff`) to ISO format (`YYYY-MM-DD`).

### DataTranslator
Renames French field names to their English equivalents (see table above).

### DataLoader
Orchestrates the load into Elasticsearch:

```python
DataLoader.load_into_es(
    es_client,
    index_name,
    chamber_filter=None,   # optional: load only one chamber
    op_type="index",       # "index" allows upserts on same record_key
)
```

**What it does:**
1. Reads normalized documents via `DataReader`
2. Validates that `record_key` (`cle_fiche`) is present — skips and logs if missing
3. Calls `es_client.index(index=index_name, document=doc, id=record_key, op_type="index")`
4. Tracks and logs created, updated, and failed document counts

An intermediate normalized file `{index_name}_parsed_{TIMESTAMP}.json` is saved alongside the raw file. If it already exists, normalization is skipped (idempotent re-runs).

---

## Makim Tasks

Defined in [`.makim.yaml`](../.makim.yaml):

```bash
# Load a raw JSON/JSONL file into an Elasticsearch index
makim elasticsearch.index-json \
    --index-name chambre_penale \
    --raw-json /opt/data/json_raw/output.json \
    --path-json /opt/data/json_raw/

# Count documents in an index
makim elasticsearch.count-docs-in-index --index-name chambre_penale

# Fetch documents from ES, create a Project record, and launch Celery processing
makim elasticsearch.process-documents
```

---

## Querying from the Application

**File:** [`src/backend/literev/libs/collectors.py`](../../src/backend/literev/libs/collectors.py) — `ElasticSearchCollector`

```python
collector = ElasticSearchCollector(index_name="chambre_penale")

# Boolean query with date range — returns list[MetaData]
docs = collector.collect_documents(
    search_query="droit de propriété AND voisinage",
    date_begin="2020-01-01",
    date_end="2024-12-31",
)

# All documents — no filtering
all_docs = collector.collect_all_documents()

# Document count
n = collector.count_all_documents()
```

Uses the ES **Scroll API** (page size 1000, 15-minute timeout). `ES_SLICES` controls parallel scroll shards.

Each result is a `MetaData` dataclass with fields: `doc_id`, `chamber`, `document_text`, `document_html_text`, `procedure_type`, `decision_type`, `decision_date`, `descriptors`, `summary`, `standards`, `result`, `es_score`, `record_key`.

Boolean queries are translated to ES DSL by `process_search_query_elasticsearch()` in [`src/backend/literev/libs/parsing.py`](../../src/backend/literev/libs/parsing.py).

---

## Snapshot & Restore

**File:** [`containers/elasticsearch_restore/restore_if_missing.py`](../../containers/elasticsearch_restore/restore_if_missing.py)

On container startup:
1. Checks which configured indices are missing
2. Registers the snapshot repository from the mounted snapshots volume
3. Restores missing indices from the latest available snapshot
4. Optionally notifies via Discord webhook (`DISCORD_WEBHOOK_URL`)

---

## Data Flow

```
Raw JSONL / JSON file
        │
        ▼
scripts/elasticsearch_loader.py
  ├── DataReader      — parse file line-by-line
  ├── DataNormalizer  — DD.MM.YYYY → YYYY-MM-DD
  ├── DataTranslator  — French field names → English
  └── DataLoader      — es.index(id=record_key, op_type="index")
        │
        ▼
Elasticsearch Index
(chambre_penale | chambre_civile | chambre_administrative)
        │
        ▼
ElasticSearchCollector  (src/backend/literev/libs/collectors.py)
  └── collect_documents() — Scroll API, boolean DSL
        │
        ▼
Django Document model (PostgreSQL) + downstream NLP pipeline
(sentence splitting → classification → ChromaDB embeddings)
See: pipeline.md
```
