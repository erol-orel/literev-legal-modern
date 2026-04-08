# Management Commands

Django management commands provide CLI access to pipeline operations, data processing, and diagnostics. All commands live in [src/literev/management/commands/](../src/literev/management/commands/).

Run any command via:
```bash
python manage.py <command_name> [options]
# or via makim (preferred):
makim django.run-command -- <command_name> [options]
```

---

## Command Reference

### cache_embeddings

**Purpose:** Generate and cache a FAISS index of document embeddings for fast nearest-neighbor search.

```bash
python manage.py cache_embeddings \
    --project-id 42 \
    [--chamber CHAMBER_NAME]
```

**What it does:**
1. Loads preprocessed documents from a project
2. Generates embeddings using the configured embedding model
3. Builds a FAISS index
4. Saves the index to `LITEREV_CACHE_DIR/faiss/`

**When to use:** After initial clustering, to enable fast document retrieval without ChromaDB for large corpora.

---

### classify_document_sentences

**Purpose:** Run French legal section classification (Majeure / Mineure-Faits / Mineure-Subsommation / Conclusion) on all documents in a project.

```bash
python manage.py classify_document_sentences \
    --project-id 42 \
    [--output /path/to/output.json]
```

**What it does:**
1. Loads raw document text for all project documents
2. Normalizes and splits text into sentences (`split_sentences_fr_legal`)
3. Packs sentences into chunks (`pack_chunks`)
4. Calls OpenAI with structured output for classification
5. Saves results (record_key → section mapping)

**Dependencies:** `OPENAI_API_KEY` must be set.

---

### count_documents_chambre

**Purpose:** Count total documents per court chamber in a given Elasticsearch index.

```bash
python manage.py count_documents_chambre \
    --index-name literev \
    [--date-from 2020-01-01] \
    [--date-to 2024-12-31]
```

**Output example:**
```
Chamber I: 4,521 documents
Chamber II: 3,108 documents
Chamber pénale: 2,874 documents
...
```

**When to use:** Before running a project, to understand corpus size by chamber and calibrate date range.

---

### count_tokens

**Purpose:** Display token count statistics for all documents in a project.

```bash
python manage.py count_tokens --project-id 42
```

**Output includes:**
- Total tokens across all documents
- Mean / median / max tokens per document
- Distribution histogram (for planning chunk sizes)

**When to use:** Before RAG runs, to understand if documents fit within LLM context windows.

---

### extract_mineur_majeur

**Purpose:** Extract minor/major premise sections from all documents in a project and save to a structured JSON file.

```bash
python manage.py extract_mineur_majeur \
    --project-id 42 \
    --output /opt/data/literev/extractions/project_42.json
```

**Output format:**
```json
{
  "record_key_1": {
    "majeure": "...",
    "mineure_faits": "...",
    "mineure_subsommation": "...",
    "conclusion": "..."
  }
}
```

**Dependencies:** `OPENAI_API_KEY`, classification module.

---

### faithfulness_metrics

**Purpose:** Benchmark faithfulness scoring performance — measures per-document processing time.

```bash
python manage.py faithfulness_metrics \
    --project-rag-id 15 \
    [--use-hhem]
```

**Output:** Per-document timing + aggregate statistics. Useful for capacity planning before running large RAG jobs.

---

### fetch_documents

**Purpose:** Verify database connectivity and volume write permissions.

```bash
python manage.py fetch_documents --project-id 42
```

**What it does:**
1. Tests PostgreSQL connection
2. Tests write access to `CONTAINER_VOLUME_DATA_DIR`
3. Retrieves and counts documents from DB

**When to use:** Diagnostic command for deployment troubleshooting.

---

### fill_order_cluster

**Purpose:** Backfill `Cluster.order` field for existing clusters where order was not set during creation.

```bash
python manage.py fill_order_cluster --project-id 42
```

**Algorithm:** Orders clusters by document count (descending) — largest cluster gets `order=0`.

**When to use:** After running clustering on existing data that pre-dates the `order` field.

---

### get_record_keys

**Purpose:** Extract French legal section labels for documents and store them indexed by `record_key`.

```bash
python manage.py get_record_keys \
    --project-id 42 \
    [--chamber CHAMBER_NAME]
```

**Output:** JSON file at `LITEREV_CACHE_DIR/record_keys/` mapping record_key → section labels.

---

### optimize_documents

**Purpose:** Run clustering optimization with advanced text analysis techniques.

```bash
python manage.py optimize_documents \
    --project-id 42 \
    [--n-trials 100] \
    [--n-jobs 4]
```

**What it does:**
1. Loads preprocessed documents
2. Rebuilds TF-IDF matrix
3. Runs Optuna hyperparameter search (more trials than default)
4. Updates clustering results in DB

**When to use:** When the initial clustering quality (DBCV score) is unsatisfactory.

---

### prepare_classified_documents

**Purpose:** Prepare documents for embedding by chamber — groups documents by court chamber before ChromaDB ingestion.

```bash
python manage.py prepare_classified_documents \
    --index-name literev \
    --chamber "Chamber I" \
    --output /opt/data/literev/prepared/
```

**When to use:** Before `run_chromadb_embeddings` when chamber-specific RAG is needed.

---

### prepare_input

**Purpose:** Extract minor/major sections and save in a format ready for embedding pipelines.

```bash
python manage.py prepare_input \
    --project-id 42 \
    --output /opt/data/literev/input/project_42/
```

---

### process_corpus

**Purpose:** Manually run the full preprocessing pipeline for all documents matching an Elasticsearch index and date range.

```bash
python manage.py process_corpus \
    --index-name literev \
    --date-from 2020-01-01 \
    --date-to 2024-12-31 \
    [--n-workers 8]
```

**What it does:**
1. Collects all documents from ES in the date range
2. Runs `literev_core.preprocessing` (language detection, lemmatization)
3. Updates `Document.preprocessed_document` in DB

**When to use:** For bulk reprocessing after changes to the preprocessing pipeline.

---

### document_cluster_optimization

**Purpose:** Standalone clustering optimization — runs the full clustering pipeline independently of the web UI.

```bash
python manage.py document_cluster_optimization \
    --project-id 42 \
    [--study-name custom-study-v2]
```

**When to use:** When you need to re-cluster without going through the Django UI, or to use a custom Optuna study name.

---

### run_chromadb_embeddings

**Purpose:** Generate and store document embeddings in ChromaDB for RAG retrieval.

```bash
python manage.py run_chromadb_embeddings \
    --project-id 42 \
    [--collection-name project_42_rag] \
    [--batch-size 50]
```

**What it does:**
1. Loads documents from the project
2. Splits text into chunks (`prepare_chunks`)
3. Generates embeddings (`text-embedding-3-large` or Hactar)
4. Stores in ChromaDB collection

**When to use:** Before running RAG queries, to pre-populate the vector store. The RAG pipeline also does this on-demand, but pre-populating is faster for large projects.

**Configuration:**
- `OPENAI_API_KEY` for OpenAI embeddings
- `USE_HACTAR_LLM=true` + `HACTAR_API_KEY` for local embeddings

---

## Running Commands in Production

In production (Docker), run commands via the app container:

```bash
# Using makim (recommended)
makim django.run-command -- classify_document_sentences --project-id 42

# Directly via docker exec
docker exec -it literev python manage.py classify_document_sentences --project-id 42

# Via docker compose
docker compose exec literev python manage.py fill_order_cluster --project-id 42
```

---

## Writing a New Management Command

All commands extend `BaseCommand`:

```python
# src/literev/management/commands/my_command.py
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Description of what this command does"

    def add_arguments(self, parser):
        parser.add_argument("--project-id", type=int, required=True)
        parser.add_argument("--output", type=str, default=None)

    def handle(self, *args, **options):
        project_id = options["project_id"]
        self.stdout.write(f"Processing project {project_id}...")
        
        # ... do work ...
        
        self.stdout.write(self.style.SUCCESS("Done."))
```

**Conventions:**
- Always use `self.stdout.write()` (not `print()`) — supports `--no-color` and output capture
- Use `self.style.SUCCESS`, `self.style.ERROR`, `self.style.WARNING` for colored output
- Long-running commands should print progress updates
- Accept `--dry-run` for commands that modify data
