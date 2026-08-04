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

1. **`src/backend/literev/libs/search.py`** — add to `SEARCH_SOURCE_OPTIONS`,
   e.g. `("bundesgericht", "Tribunal fédéral / Bundesgericht")` (or one entry
   per language: `bundesgericht_de` / `_fr` / `_it`). This alone makes it appear
   in the search UI and pass validation.
2. **`src/backend/config/settings/base.py`** — add the same key(s) to
   `LITEREV_CHAMBER_NAMES` if code paths that read it need them.
3. **RAG dispatch** — `literev.tasks` (`get_nl_rag_ans`, `task_rag_result_table`)
   selects `CustomRagAnswersGenerator` only for the three Geneva chambers; a new
   source falls through to the generic `RagAnswersManager`. Add the key there if
   you want the section-based (facts / subsumption / conclusion) chamber
   pipeline for federal decisions.
4. **ChromaDB** — add a collection mapping in
   `chroma_utils.CHAMBER_COLLECTION_FALLBACKS` if using per-source vector RAG.

---

## 5. Making it multilingual

The embedding model is already multilingual; the work is in preprocessing and
persistence:

- **`Document.language`** — add the field + migration (`models.py`) and populate
  it through `lr_contracts.SearchDocumentMetadata` →
  `lr_search.collectors.extract_document_metadata` → `pipeline.create_document_db`.
- **Preprocessing** (`libs/lr-preprocessing/src/lr_preprocessing/`) — today
  `utils.define_languages` is a **French-only gate that silently discards every
  DE/IT document**. It must detect and *return* the language, and
  `utils.lemmatize` / `pipeline.clean_corpus` must select the per-language spaCy
  model + stop-word list instead of the hard-coded French ones.
- **Prompts** — RAG/summary/boolean-query prompts are hard-coded to answer in
  French (`rag_pdf.py`, `chroma_utils.py`, `nlp.py`). Thread the document/answer
  language through to answer in the decision's language.

> ⚠️ **Partial-change trap:** until preprocessing is language-aware, ingesting
> DE/IT decisions *appears* to work but drops them at the preprocessing step.
> Do the language-detection change before loading a multilingual corpus.

---

## 6. Already in place

- **Legal-article deep-linking** — cited articles in RAG answers and on the
  document page link to the official **Fedlex** text (`lr_legal.legal_refs`),
  covering the core federal codes (CC/ZGB, CO/OR, CP/StGB, Cst/BV/Cost, CPC/ZPO,
  CPP/StPO, LTF/BGG) across all three languages. Cantonal codes degrade to plain
  text.
- **Multi-source plumbing** — `selected_indices` is a list; ingestion loops over
  it; the query builder and collectors are per-index.

---

## 7. End-to-end checklist

1. Obtain the federal decisions and index them into ES with the §3 schema
   (include `language`).
2. Register the source(s) (§4).
3. Add `Document.language` + migration and thread it through (§5).
4. Make preprocessing language-aware and install the DE/IT spaCy models +
   stop-word lists (§5).
5. Run RAG/embedding ingestion (`manage.py run_chromadb_embeddings`) with
   `OPENAI_API_KEY` set, per source collection.
6. (Optional) Parameterise prompts by language for native-language answers.
