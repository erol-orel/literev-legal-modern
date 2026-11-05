# Hybrid retrieval (BM25 + dense) → rerank

This note answers a concrete question: **how should decisions be retrieved and
ranked, which method is fastest, which recalls the most, and should the dense
side run on Hactar or on the VM?** It also specifies exactly what it would take
to turn hybrid retrieval on for the results table, because — unlike reranking —
it is **not** a flag-flip: it requires re-indexing the corpus with vectors.

One piece has already shipped: section RAG can read its chunks from
Elasticsearch instead of ChromaDB, with a plain dense kNN query (see
[Section RAG retrieval on Elasticsearch](#section-rag-retrieval-on-elasticsearch)).

## Where we are today

The retrieval pipeline for the results table is:

```
Elasticsearch BM25 (lexical)  →  cross-encoder rerank of top-K  →  top-N
```

- **BM25** is the only _candidate generator_. A decision is retrievable only if
  it shares tokens with the query (after the boolean-query parsing in
  `lr-query`). Elasticsearch stores the raw document; there is **no
  `dense_vector` field** in the search indexes (see
  `libs/etl.py::DataLoader.load_into_es`).
- **Reranking** (`libs/reranking.py`, shipped, `RERANK_ENABLED`) reorders the
  BM25 top-K by semantic relevance with a cross-encoder. See
  [`reranking.md`](./reranking.md).
- The **dense** vectors that do exist serve the RAG answer path, not candidate
  generation for the results table: the ChromaDB section embeddings
  (`libs/chroma_utils.py`, `libs/rag_classes.py`) and their copy in the
  Elasticsearch `<source>_sections` indexes, read behind
  `HYBRID_RETRIEVAL_ENABLED` (`libs/es_section_retrieval.py`).

The key consequence: **reranking cannot recover a decision BM25 never
returned.** It fixes _ordering_, not _recall_. If the query and a relevant
decision share no surface tokens — synonymy ("congé" vs "résiliation"),
paraphrase, or cross-lingual (a French query over a German BGE) — BM25 drops it
before the reranker ever sees it. That gap is exactly what a dense retriever
closes.

## The four pipelines, on speed and recall

Numbers below are order-of-magnitude, drawn from public first-stage retrieval
benchmarks (BEIR / MS MARCO style) and this stack's shape (Swiss multilingual
legal text, a top-K rerank on CPU). Treat them as _relative_ guidance; the
[benchmark harness](#measuring-it-on-the-vm) produces real numbers for this
corpus.

| Pipeline                       | Recall@50 (relative)                         | Added latency / query   | Infra needed                                                 |
| ------------------------------ | -------------------------------------------- | ----------------------- | ------------------------------------------------------------ |
| **1. BM25 only**               | baseline                                     | ~10–30 ms (ES)          | none (today)                                                 |
| **2. BM25 → rerank** (shipped) | **same candidates**, much better ordering    | +150–400 ms (CPU, K=50) | reranker on VM                                               |
| **3. Hybrid BM25+dense, RRF**  | **+10–25 pts** on paraphrase / cross-lingual | +20–60 ms (added kNN)   | dense vectors in ES; client-side fusion or a paid ES license |
| **4. Hybrid → rerank**         | best recall **and** ordering                 | +170–460 ms             | both                                                         |

Reading the table:

- **Fastest:** BM25 only. Hybrid adds a second (kNN) query. Elasticsearch's
  native `rrf` retriever runs both legs and fuses them server-side, but it is a
  paid feature: on the VM's basic license it returns 403. On the basic license
  the two legs are two searches fused in Python, so the added cost is one more
  kNN round trip — still tens of ms, small next to the reranker.
- **Highest recall:** anything with the **dense** branch (3 or 4). This is the
  only lever that raises recall; reranking (2) does not. On multilingual legal
  corpora the dense branch is worth the most precisely where BM25 is weakest —
  French↔German↔Italian and synonym-heavy legal phrasing.
- **Best overall:** **4 — hybrid → rerank.** Dense widens the candidate net, RRF
  fuses lexical + semantic robustly, and the cross-encoder gives the final
  precise ordering. Latency stays dominated by the reranker you already accepted
  for (2), so going from 2→4 is almost free on the clock while adding the recall
  that 2 can't.

### Why RRF (not a weighted score sum)

Reciprocal Rank Fusion combines the two result lists by _rank_, not by score:
`score(d) = Σ 1 / (k + rank_i(d))`. BM25 scores and cosine similarities live on
different, non-comparable scales, so a weighted sum needs per-query tuning and
is brittle. RRF needs no score normalization and is the robust default. Keep the
cross-encoder as the final precision stage on top of the fused set.

RRF does not need Elasticsearch's `rrf` retriever: the formula is a few lines
over two ranked lists. The native retriever is a licensed feature that the VM's
basic license rejects with a 403, so on this deployment the fusion has to run
client-side unless the license changes.

## Hactar or the VM for the dense vectors?

The dense branch needs an embedding model to (a) embed every decision once at
index time and (b) embed each query at search time.

**Recommendation: embed on-prem with Hactar's `mxbai-embed-large`, index the
vectors into the VM's Elasticsearch.**

- **Privacy first.** Decision text is privileged. Hactar (`hactar.unige.ch`) is
  the university's own gateway; `mxbai-embed-large` (~1024-dim) is multilingual
  and strong enough for _first-stage_ dense recall — the cross-encoder cleans up
  final ordering, so the dense model only has to get relevant docs into the
  candidate set, not rank them perfectly.
- **Cost.** On-prem embeddings are free per query; OpenAI
  `text-embedding-3-large` (used for the ChromaDB section RAG) is higher quality
  (3072-dim) but costs per token and sends the corpus off-prem — an easy no for
  bulk-embedding the whole lexical corpus.
- **Consistency.** You must use the **same** model for index-time and query-time
  embeddings, and the ES `dense_vector` `dims` must match the model (1024 for
  mxbai). Re-embedding the corpus if you later switch models is the expensive
  part — pick mxbai and stay.

Do **not** use Hactar for reranking (it has no cross-encoder endpoint; see
`reranking.md`) — only for embeddings. Reranker stays on the VM.

This recommendation is for the planned decision-level index behind the results
table, which has not been built. The section indexes that did ship use
`HYBRID_EMBED_ENGINE`, which defaults to OpenAI (`text-embedding-3-large`,
3072-dim): the Geneva chambers' Chroma section vectors were built with OpenAI,
and the migration stays in that vector space.

## What it takes to turn on for the results table (rollout)

Hybrid candidate generation is a deliberate, VM-validated project, not a config
flag, because step 2 rewrites the index:

1. **Mapping.** Add a `dense_vector` field (`dims: 1024`, `index: true`,
   `similarity: cosine`) to each search index's mapping.
2. **Re-index with vectors.** Extend the ingest (`libs/etl.py`) to embed each
   decision via Hactar at load time and write the vector alongside the document.
   This is a full re-index of the corpus — the costly, one-time step.
3. **Query.** Run the BM25 leg and a `knn` leg on the query embedding and fuse
   them with RRF. `lr_search.hybrid.build_hybrid_search_body` builds the
   single-request version (an `rrf` retriever over a `standard` BM25 retriever
   and a `knn` retriever), but that needs a paid Elasticsearch license; on the
   VM's basic license, send the two searches separately and fuse the ranked
   lists client-side. Route the results table + RAG candidate selection through
   it behind a flag of its own (`HYBRID_RETRIEVAL_ENABLED` already gates the
   section RAG path below), falling back to today's BM25 path when off or on any
   error (same safety contract as reranking).
4. **Keep the reranker last.** Feed the fused top-K into
   `reranking.rerank_documents` unchanged.

Ship it flag-gated and default-off, exactly like reranking, so it is safe to
merge before the re-index has run on a given environment.

## What is implemented

### Builders (`lr_search.hybrid`, `lr_search.indexing`)

`lr_search.hybrid` holds framework-free builders: pure dict transforms,
unit-tested without a cluster.

- `section_index_mapping(dims)` — one document carries the BM25 `text` _and_ the
  quantized (`int8_hnsw`) `section_vector`, so lexical and dense retrieval can
  hit one store.
- `build_hybrid_search_body(lexical_query, query_vector, …)` — fuses a BM25 leg
  (the `lr_query` body) and a dense `knn` leg with the native `rrf` retriever in
  a single query; `filters` constrain both legs identically (selected sources, a
  date range). **Nothing in production calls it**: the `rrf` retriever returns
  403 on the VM's basic license. It is kept for the planned candidate
  generation, which on that license needs client-side fusion instead (see the
  rollout above).

`lr_search.indexing` is the write-side companion: `section_document(…)` builds
the `_source` (BM25 `text` + the dense `section_vector` on one document),
`section_doc_id(…)` gives each chunk a stable id, `bulk_index_action(…)` and
`iter_section_bulk_actions(…)` turn chunks into ES bulk actions, and
`iter_batches(…)` streams the corpus without holding it in memory. On the read
side, `group_hits_by_section(…)` turns hits back into per-section blocks.

### Building the section indexes (`embed_sections_to_es`)

`manage.py embed_sections_to_es` is the Chroma → ES migration bridge. For each
section source it:

1. **Reads the existing section chunks.** The default `--reader sqlite` opens
   Chroma's SQLite store (`chroma.sqlite3`) read-only and streams its metadata
   segment, so it never loads the HNSW index; loading that index runs out of
   memory on large collections (`chambre_administrative` has more than 2M
   chunks). `--reader chroma` goes through the Chroma client instead.
2. **Re-embeds the text** with `settings.HYBRID_EMBED_ENGINE` (default `openai`:
   `text-embedding-3-large`, 3072-dim). `--engine openai|hactar` overrides it
   for one run.
3. **Bulk-indexes** `text` + `section_vector` into `<source>_sections`, creating
   the index on the first write with the dims of the embedded vectors.

Each chunk's id is derived from its decision, its section and its position in
that section, so a re-run overwrites in place instead of duplicating. A plain
re-run still re-embeds, and pays for, every chunk. `--skip-existing` resumes an
interrupted run instead: for each batch it asks Elasticsearch which ids are
already indexed and embeds only the missing chunks. It never recreates the
index, and on an index that does not exist yet it is a normal fresh build. The
ids match across runs because the SQLite reader always yields chunks in the same
order.

The other options are `--source` (comma-separated keys; default all section
sources), `--batch-size` (default 128), `--limit` (max chunks per source),
`--recreate` (drop and rebuild the index) and `--dry-run` (read and count only).
A source that fails is reported and skipped; the others still run.

### Section RAG retrieval on Elasticsearch

With `HYBRID_RETRIEVAL_ENABLED=true` (default off), the section-RAG worker
(`rag_pdf.get_answer_document_worker`) reads each decision's chunks from
Elasticsearch through
`literev.libs.es_section_retrieval.get_best_section_chunks_es`:

- The question is embedded once per RAG run (`embed_section_query`) with
  `HYBRID_EMBED_ENGINE`, the engine the index was built with.
- For each decision, one plain dense `knn` query runs over `section_vector` in
  `<source>_sections`, filtered to that decision's `record_key`. It returns
  `HYBRID_SEARCH_SIZE` hits (default 40, with
  `num_candidates = max(3 × size, 100)`).
- The hits are grouped into the same `{section: [text, …]}` blocks the Chroma
  path returns, with at most `HYBRID_TOP_K_PER_SECTION` chunks per section
  (default 8).

There is no BM25 leg and no RRF. The RRF retriever returned 403 on the VM's
basic license (#79), and within a single decision the dense leg already picks
out the relevant chunks; the Chroma path it replaces was dense-only too. With
the flag off, the Chroma path is used unchanged. With it on, there is no
fallback to Chroma: if retrieval fails for a decision, that decision gets the
worker's empty default answer.

### Enabling it on a deployment

ES section retrieval is one idempotent build step plus a flag, done on the
target after a normal deploy:

```bash
# 1. Build the ES section index(es). Reads Chroma's SQLite store and re-embeds
#    with HYBRID_EMBED_ENGINE (default openai: needs OPENAI_API_KEY and is
#    billed per token). Start small to smoke-test, then run the full corpus.
makim django.embed-sections --source chambre_civile --limit 200   # first look
makim django.embed-sections                                       # all sources

# 1b. If the build stops part-way (e.g. the API credits run out), resume with
#     manage.py: the makim task does not pass --skip-existing, and re-running
#     it re-embeds every chunk. From src/backend/, with .env exported:
python manage.py embed_sections_to_es --skip-existing
#     or in the app container (what the makim task does with USE_CONTAINER=true):
sugar compose run --service literev \
  --cmd "python manage.py embed_sections_to_es --skip-existing" -- --rm

# 2. Verify answer parity against the Chroma path (ask a few known questions,
#    or run the offline harness — see docs/rag-evaluation.md).

# 3. Flip the flag and redeploy once parity looks good: set
#    HYBRID_RETRIEVAL_ENABLED=true in .env (and keep HYBRID_EMBED_ENGINE equal
#    to the engine the index was built with), then
./scripts/deploy_now.sh --skip-deps --skip-build
```

The embed step is deliberately **not** run automatically by `deploy_now.sh` — it
is a large one-time job, and the flag stays a manual opt-in so retrieval only
switches to Elasticsearch after parity is confirmed. Once it is, the ChromaDB
path can be retired.

**Note on the embedding model:** the ES path uses one engine,
`HYBRID_EMBED_ENGINE` (default `openai`: `text-embedding-3-large`, 3072-dim), to
build the index and to embed queries, so the whole section corpus shares one
vector space. `HYBRID_EMBED_ENGINE=hactar` moves both sides to Hactar's
`HACTAR_EMBED_MODEL` (`mxbai-embed-large`, ~1024-dim), but an index's `dims` are
fixed when it is created, so switching engines means rebuilding with
`--recreate`. The per-source `SECTION_EMBED_ENGINE` split (OpenAI for the Geneva
chambers, `FEDERAL_EMBED_ENGINE` for the federal courts) lives only in the
Chroma path and is removed when Chroma is retired, not as a separate step.

## Measuring it on the VM

`scripts/bench_retrieval.py` is a standalone benchmark (plain `elasticsearch`
client, no Django) that reports **latency percentiles** and, given a small
labelled query→relevant-record_key set, **recall@k** for BM25 today and for the
hybrid query once vectors are indexed. Run it against the live index after each
rollout step to replace the order-of-magnitude table above with real numbers for
this corpus:

```bash
# latency only (works today, BM25):
python scripts/bench_retrieval.py --index <index> --queries scripts/bench_queries.sample.json

# with a labelled set, prints recall@k too:
python scripts/bench_retrieval.py --index <index> --queries labelled.json --k 10 20 50
```

`--mode hybrid` sends the native `rrf` retriever, so on the VM's basic license
it gets the same 403 the section path did. Until the fusion moves client-side or
the license changes, only `--mode bm25` runs there.

## Bottom line

- Reranking (shipped) was the right first move: the biggest _ordering_ win, a
  pure flag-flip, safe to leave on.
- **Hybrid → rerank is the best method** for both recall and precision, and the
  dense branch is the _only_ thing that raises recall. It is worth doing.
- It is gated on a one-time re-index of the decisions with vectors in the VM's
  Elasticsearch (the recommendation above is on-prem Hactar `mxbai-embed-large`)
  and, on the basic license, on fusing the BM25 and kNN results client-side.
  Keep the reranker as the final stage and validate the gain with
  `scripts/bench_retrieval.py`.
- Section RAG retrieval already runs on Elasticsearch, as dense kNN over the
  OpenAI section vectors migrated from Chroma, behind
  `HYBRID_RETRIEVAL_ENABLED`.
