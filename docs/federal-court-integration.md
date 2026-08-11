# Integrating Swiss Federal Court decisions (DE / FR / IT)

This guide explains how to add **Swiss Federal Supreme Court**
(_Tribunal fédéral / Bundesgericht / Tribunale federale_) decisions to
`literev-legal` as a multilingual source, and what is already in place versus
what still needs data/infrastructure.

> **Language note.** The Federal Court publishes in **German, French and
> Italian** — not English. "Native language" here means DE/FR/IT. Optional
> English machine-translation is a separate, additive feature.

---

## 1. How a "source" works today

A *source* in the search UI is **one Elasticsearch index name**. The list is a
hard-coded allow-list:

- `src/backend/literev/libs/search.py` — `SEARCH_SOURCE_OPTIONS` /
  `SEARCH_SOURCE_VALUES` (the frontend list **and** the validation gate).
- `src/backend/config/settings/base.py` — `LITEREV_CHAMBER_NAMES`
  (overridable via the `LITEREV_CHAMBER_NAMES` env var).

At search time, `literev.tasks.back_get_documents` loops over
`project.selected_indices` and runs one `ElasticSearchCollector(index_name)`
per index (`src/backend/literev/libs/collectors.py`), mapping each ES hit into
a per-project `Document` row (`src/backend/literev/libs/pipeline.py`
`create_document_db`). The design is already **multi-source**: adding a source
that behaves like the existing Geneva chambers is a few lines — the real work is
getting the corpus into an ES index and handling language.

Per-chamber RAG additionally maps the source string to a ChromaDB collection in
`src/backend/literev/libs/chroma_utils.py` (`CHAMBER_COLLECTION_FALLBACKS`).

---

## 2. Prerequisites (the operational blockers)

These are **not** in the repository and must be supplied by the deployment:

| Prerequisite | Why | Where |
|---|---|---|
| **The decision corpus** in Elasticsearch | The FR corpus is assumed to already live in an external ES cluster; there is no bundled scraper/dataset. | `ES_HOST_URL`, `ES_USERNAME`, `ES_PASSWORD`, `ES_SSL_CERTS` in `settings/base.py` |
| **`OPENAI_API_KEY`** | Embeddings (`text-embedding-3-large`) + RAG answers (`gpt-4.1-mini`). The model is already multilingual — no swap needed. | `settings/base.py`; read lazily by `chroma_utils` / `lr_legal` |
| **spaCy models** `de_core_news_sm`, `it_core_news_sm` (and `fr_core_news_sm`) | Lemmatisation for clustering preprocessing per language. | installed in the conda/pip environment |
| **DE / IT stop-word lists** | Preprocessing currently ships only the French list. | `libs/lr-preprocessing/.../data/` |

**Data sources for the corpus.** The Federal Court's own decisions are public;
the community project [entscheidsuche.ch](https://entscheidsuche.ch) provides a
free bulk/API feed of Swiss court decisions (federal + cantonal) that can be
shaped into the ES schema below. Confirm licensing/attribution for your
deployment before ingesting.

---

## 3. The Elasticsearch document schema

`lr_search.collectors.get_all_documents_from_es_response` reads these `_source`
fields (see `libs/lr-search/src/lr_search/collectors.py`). Populate them when
indexing federal decisions:

| ES field | Maps to `Document.` | Notes |
|---|---|---|
| `document_text` | `raw_document_text` | **Required** — docs without it are skipped. Full plain text used for search + NLP. |
| `document` | `document_html_text` | HTML for rendering |
| `collector_name` | `chamber` | Set to the source key, e.g. `bundesgericht` |
| `record_key` | `record_key` | Stable unique id (e.g. the ATF/BGE or dossier number) |
| `decision_type`, `decision_date`, `procedure_type`, `descriptors`, `standards`, `result` | same names | `decision_date` drives the date-range filter |
| `language` *(new — see §5)* | `language` | `de` / `fr` / `it` |

The offline loader `src/backend/literev/libs/etl.py` (`DataLoader.load_into_es`,
`DataTranslator.ROOT_FIELD_MAP`) is the intended tool for pushing a JSONL corpus
into ES; its field map is French-oriented and should be extended for the federal
feed.

### `standards` (normes) — keep it structured

Store cited articles in the compact token form the app already understands, e.g.
`CC.8;CO.336c.al1.letb;Cst.29.al2`. These are parsed and **deep-linked to
Fedlex** automatically (see `lr_legal.legal_refs` and §6). Multilingual code
abbreviations are handled (`ZGB`→CC, `OR`→CO, `StGB`→CP, `BV`→Cst, …).

---

## 4. Registering the source

### Registered federal sources

All five federal courts are registered in `SEARCH_SOURCE_OPTIONS` /
`SECTION_SOURCES`. Import each with `import_entscheidsuche` using the matching
spider → source-key pair:

| Spider (`hierarchy[1]`) | Source key (`--index`) | Court |
|---|---|---|
| `CH_BGer` | `bundesgericht` | Tribunal fédéral (Bundesgericht) |
| `CH_BGE` | `atf` | Tribunal fédéral — arrêts principaux (ATF, leading decisions) |
| `CH_BVGE` | `bundesverwaltungsgericht` | Tribunal administratif fédéral |
| `CH_BSTG` | `bundesstrafgericht` | Tribunal pénal fédéral |
| `CH_PATG` | `bundespatentgericht` | Tribunal fédéral des brevets |

`atf` (`CH_BGE`) is the officially published leading-decisions series of the
Tribunal fédéral — a curated subset with its own record keys, registered as a
distinct source so it can be searched on its own.

### To register a *new* source

1. **`src/backend/literev/libs/search.py`** — add to `SEARCH_SOURCE_OPTIONS`,
   e.g. `("bundesgericht", "Tribunal fédéral / Bundesgericht")` (or one entry
   per language: `bundesgericht_de` / `_fr` / `_it`). This alone makes it appear
   in the search UI and pass validation.
2. **`src/backend/config/settings/base.py`** — add the same key(s) to
   `LITEREV_CHAMBER_NAMES` if code paths that read it need them.
3. **RAG dispatch** — **done for the federal sources.** `literev.tasks`
   (`get_nl_rag_ans`, `task_rag_result_table`) now dispatches via
   `_section_source_for(selected_indices)`, which picks the section-based
   `CustomRagAnswersGenerator` for any source in
   `search.SECTION_SOURCES` (the three Geneva chambers **plus** the five
   federal courts: `bundesgericht` / `atf` / `bundesverwaltungsgericht` /
   `bundesstrafgericht` / `bundespatentgericht`) — but
   only when that source's section-embedded Chroma collection actually exists
   (`chroma_utils.has_section_collection`). Until federal section embeddings are
   built, federal projects fall back automatically to the generic
   `RagAnswersManager`, so they always yield answers. To make a further source
   eligible, add its key to `search.SECTION_SOURCES`.
4. **ChromaDB** — add a collection mapping in
   `chroma_utils.CHAMBER_COLLECTION_FALLBACKS` only if a source's collection is
   stored under a legacy/alias name; a collection named after the source key is
   found directly.

---

## 5. Making it multilingual

The embedding model is already multilingual; the remaining work is in the
preprocessing runtime and (optionally) persistence:

- **Preprocessing** (`libs/lr-preprocessing/src/lr_preprocessing/`) — **done.**
  `utils.detect_language` now returns `fr`/`de`/`it` (or `None` for unsupported
  text), and `utils.lemmatize` / `pipeline.clean_corpus` select the per-language
  spaCy model and stopwords. German/Italian decisions are no longer discarded.
  **The only remaining step is installing the optional spaCy models** —
  `de_core_news_sm` and `it_core_news_sm` — in the runtime; without them the
  pipeline still ingests DE/IT text but skips lemmatization (lower cluster
  quality, no data loss).
- **Prompts** — **done for per-document RAG.** `rag_pdf.py` detects the
  decision's language and answers/summarises in DE/FR/IT accordingly. The
  section-based summary prompts in `chroma_utils.py` and the boolean-query
  helper in `nlp.py` remain French-oriented (optional follow-up).
- **`Document.language`** *(optional)* — the preprocessing pipeline detects
  language per document at clean-time, so a persisted column is only needed if
  you want to filter/display by language in the UI. Add the field + migration
  and populate it through `lr_contracts.SearchDocumentMetadata` →
  `lr_search.collectors.extract_document_metadata` →
  `pipeline.create_document_db` (the entscheidsuche importer already emits a
  `language` field on each ES document).

---

## 6. Already in place

- **Legal-article deep-linking** — cited articles in RAG answers and on the
  document page link to the official **Fedlex** text (`lr_legal.legal_refs`),
  covering the core federal codes (CC/ZGB, CO/OR, CP/StGB, Cst/BV/Cost, CPC/ZPO,
  CPP/StPO, LTF/BGG) across all three languages, plus the common **Geneva
  cantonal** codes (Cst-GE, LPA, LOJ, LPAC/RPAC, LIPAD, LaLP …) linking to their
  rsGE act page on silgeneve.ch. Unmapped codes degrade to plain text.
- **Multi-source plumbing** — `selected_indices` is a list; ingestion loops over
  it; the query builder and collectors are per-index.
- **entscheidsuche.ch importer** — `manage.py import_entscheidsuche` pulls
  Federal Court decisions (DE/FR/IT) into an ES index (see §2–§4).
- **Language-aware preprocessing** — DE/FR/IT are detected and preprocessed;
  non-supported languages are discarded, DE/IT are kept (§5).
- **Section-based RAG for federal sources** — the federal sources are wired into
  the chamber (facts / subsumption / conclusion) pipeline and use it as soon as
  their section embeddings exist, falling back to the generic manager until then
  (§4). No code change is needed to switch a federal source over — only the
  section embeddings.

---

## 7. End-to-end checklist

1. Import the federal decisions into an ES index —
   `manage.py import_entscheidsuche --spider CH_BGer --index bundesgericht`
   (§2–§4). The source is already registered.
2. Install the optional DE/IT spaCy models (`de_core_news_sm`,
   `it_core_news_sm`) for best clustering quality on German/Italian (§5).
   Without them, ingestion still works (lemmatization is skipped).
3. Run RAG/embedding ingestion (`manage.py run_chromadb_embeddings`) with
   `OPENAI_API_KEY` set, per source collection. Once a federal source's
   collection carries per-section (`Majeure` / `Mineure-Faits` /
   `Mineure-Subsommation` / `Conclusion`) chunks, it automatically uses the
   section-based chamber RAG pipeline (§4); until then it uses the generic one.
4. `Document.language` is persisted and surfaced in the UI (done).
5. Per-document RAG answers are already returned in the decision's language
   (done); the section-summary/boolean-query prompts remain an optional
   follow-up (§5).

---

## 8. Cantonal sources (Romandie)

The same `import_entscheidsuche` path handles **cantonal** courts — they use
the identical entscheidsuche schema, only with a canton-level `hierarchy[1]`
code (canton == the two-letter prefix). The registered cantonal sources (see
`entscheidsuche.CANTONAL_SPIDERS` and `search.SEARCH_SOURCE_OPTIONS`) use the
lower-cased code as the source key:

| Spider (`hierarchy[1]`) | Source key (`--index`) | Court | FR docs (source) |
|---|---|---|---|
| `VD_TC` | `vd_tc` | Vaud — Tribunal cantonal | ~152,900 |
| `FR_TC` | `fr_tc` | Fribourg — Tribunal cantonal | ~22,000 |
| `NE_TC` | `ne_tc` | Neuchâtel — Tribunal cantonal | ~14,150 |
| `VS_BZG` | `vs_bzg` | Valais — Tribunaux de district | ~5,500 |
| `GE_TAPI` | `ge_tapi` | Genève — Tribunal administratif de première instance | ~3,600 |
| `BE_VG` | `be_vg` | Berne — Tribunal administratif | ~2,100 |
| `JU_TC` | `ju_tc` | Jura — Tribunal cantonal | ~2,000 |
| `VS_TC` | `vs_tc` | Valais — Tribunal cantonal | ~1,240 |
| `GE_TP` | `ge_tp` | Genève — Tribunal pénal | ~1,020 |

```
manage.py import_entscheidsuche --spider VD_TC --index vd_tc --language fr --insecure
```

**`GE_CJ` (Genève — Cour de justice, ~156k FR) is intentionally not
registered.** Its chambers already ship as the `chambre_administrative` /
`chambre_penale` / `chambre_civile` sources (loaded from the internal Geneva
corpus), so importing `GE_CJ` from entscheidsuche would duplicate them via a
different pipeline. Registering it is a deliberate, separate decision.

Registration only makes a source **searchable** (and section-RAG-eligible with
graceful fallback). Building its section embeddings is a separate, per-source
step (`federal.embed`) whose cost/quality should be weighed per court.
