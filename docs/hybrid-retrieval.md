# Hybrid retrieval (BM25 + dense, RRF-fused) → rerank

This note answers a concrete question: **how should decisions be retrieved and
ranked, which method is fastest, which recalls the most, and should the dense
side run on Hactar or on the VM?** It also specifies exactly what it would take
to turn hybrid retrieval on, because — unlike reranking — it is **not** a
flag-flip: it requires re-indexing the corpus with vectors.

## Where we are today

The retrieval pipeline is:

```
Elasticsearch BM25 (lexical)  →  cross-encoder rerank of top-K  →  top-N
```

- **BM25** is the only *candidate generator*. A decision is retrievable only if
  it shares tokens with the query (after the boolean-query parsing in
  `lr-query`). Elasticsearch stores the raw document; there is **no
  `dense_vector` field** in the index (see `libs/etl.py::DataLoader.load_into_es`).
- **Reranking** (`libs/reranking.py`, shipped, `RERANK_ENABLED`) reorders the
  BM25 top-K by semantic relevance with a cross-encoder. See
  [`reranking.md`](./reranking.md).
- The **dense** vectors that do exist live in a *separate* store — ChromaDB
  section embeddings used by the RAG answer path (`libs/chroma_utils.py`,
  `libs/rag_classes.py`), not by candidate generation for the results table.

The key consequence: **reranking cannot recover a decision BM25 never
returned.** It fixes *ordering*, not *recall*. If the query and a relevant
decision share no surface tokens — synonymy ("congé" vs "résiliation"),
paraphrase, or cross-lingual (a French query over a German BGE) — BM25 drops it
before the reranker ever sees it. That gap is exactly what a dense retriever
closes.

## The four pipelines, on speed and recall

Numbers below are order-of-magnitude, drawn from public first-stage retrieval
benchmarks (BEIR / MS MARCO style) and this stack's shape (Swiss multilingual
legal text, a top-K rerank on CPU). Treat them as *relative* guidance; the
[benchmark harness](#measuring-it-on-the-vm) produces real numbers for this
corpus.

| Pipeline | Recall@50 (relative) | Added latency / query | Infra needed |
|---|---|---|---|
| **1. BM25 only** | baseline | ~10–30 ms (ES) | none (today) |
| **2. BM25 → rerank** (shipped) | **same candidates**, much better ordering | +150–400 ms (CPU, K=50) | reranker on VM |
| **3. Hybrid BM25+dense, RRF** | **+10–25 pts** on paraphrase / cross-lingual | +20–60 ms (added kNN) | dense vectors in ES |
| **4. Hybrid → rerank** | best recall **and** ordering | +170–460 ms | both |

Reading the table:

- **Fastest:** BM25 only. Hybrid adds a second (kNN) query but ES 8.x runs both
  branches concurrently and fuses server-side, so the *added* cost is small
  (tens of ms) relative to the reranker.
- **Highest recall:** anything with the **dense** branch (3 or 4). This is the
  only lever that raises recall; reranking (2) does not. On multilingual legal
  corpora the dense branch is worth the most precisely where BM25 is weakest —
  French↔German↔Italian and synonym-heavy legal phrasing.
- **Best overall:** **4 — hybrid → rerank.** Dense widens the candidate net,
  RRF fuses lexical + semantic robustly, and the cross-encoder gives the final
  precise ordering. Latency stays dominated by the reranker you already
  accepted for (2), so going from 2→4 is almost free on the clock while adding
  the recall that 2 can't.

### Why RRF (not a weighted score sum)

Reciprocal Rank Fusion combines the two result lists by *rank*, not by score:
`score(d) = Σ 1 / (k + rank_i(d))`. BM25 scores and cosine similarities live on
different, non-comparable scales, so a weighted sum needs per-query tuning and
is brittle. RRF needs no score normalization, is a documented native
Elasticsearch `retriever`, and is the robust default. Keep the cross-encoder as
the final precision stage on top of the fused set.

## Hactar or the VM for the dense vectors?

The dense branch needs an embedding model to (a) embed every decision once at
index time and (b) embed each query at search time.

**Recommendation: embed on-prem with Hactar's `mxbai-embed-large`, index the
vectors into the VM's Elasticsearch.**

- **Privacy first.** Decision text is privileged. Hactar (`hactar.unige.ch`)
  is the university's own gateway; `mxbai-embed-large` (~1024-dim) is
  multilingual and strong enough for *first-stage* dense recall — the
  cross-encoder cleans up final ordering, so the dense model only has to get
  relevant docs into the candidate set, not rank them perfectly.
- **Cost.** On-prem embeddings are free per query; OpenAI `text-embedding-3-large`
  (used for the ChromaDB section RAG) is higher quality (3072-dim) but costs per
  token and sends the corpus off-prem — an easy no for bulk-embedding the whole
  lexical corpus.
- **Consistency.** You must use the **same** model for index-time and
  query-time embeddings, and the ES `dense_vector` `dims` must match the model
  (1024 for mxbai). Re-embedding the corpus if you later switch models is the
  expensive part — pick mxbai and stay.

Do **not** use Hactar for reranking (it has no cross-encoder endpoint; see
`reranking.md`) — only for embeddings. Reranker stays on the VM.

## What it takes to turn on (rollout)

Hybrid is a deliberate, VM-validated project, not a config flag, because step 2
rewrites the index:

1. **Mapping.** Add a `dense_vector` field (`dims: 1024`, `index: true`,
   `similarity: cosine`) to each search index's mapping.
2. **Re-index with vectors.** Extend the ingest (`libs/etl.py`) to embed each
   decision via Hactar at load time and write the vector alongside the document.
   This is a full re-index of the corpus — the costly, one-time step.
3. **Query.** Build an ES 8.x `retriever: { rrf: { retrievers: [ {standard:
   BM25}, {knn: query-embedding} ] } }` and route the results table +
   RAG candidate selection through it, behind a `HYBRID_RETRIEVAL_ENABLED`
   flag, falling back to today's BM25 path when off or on any error (same
   safety contract as reranking).
4. **Keep the reranker last.** Feed the fused top-K into
   `reranking.rerank_documents` unchanged.

Ship it flag-gated and default-off, exactly like reranking, so it is safe to
merge before the re-index has run on a given environment.

## Implementation: the query builder (`lr_search.hybrid`)

The framework-free core is shipped: `lr_search.hybrid` builds the Elasticsearch
8.x `retriever`/`rrf` search body and the section-index mapping as pure dict
transforms (no cluster, unit-tested).

- `section_index_mapping(dims)` — one document carries the BM25 `text` *and* the
  quantized (`int8_hnsw`) `section_vector`, so lexical and dense retrieval hit
  one store.
- `build_hybrid_search_body(lexical_query, query_vector, …)` — fuses the BM25
  leg (the `lr_query` body) and the dense `knn` leg with RRF in a single query;
  `filters` constrain both legs identically (selected sources, a date range).

`lr_search.indexing` is the write-side companion: `section_document(…)` builds
the `_source` (BM25 `text` + the dense `section_vector` on one document),
`iter_section_bulk_actions(…)` turns a stream of those into ES bulk actions with
stable, idempotent ids, and `iter_batches(…)` streams the corpus without holding
it in memory. The `embed_sections_to_es` management command wires these together
on the VM: it reads each source's existing section chunks from Chroma, re-embeds
the text through Hactar into one vector space, and bulk-indexes them into a
`<source>_sections` index — the Chroma → ES migration bridge. It is idempotent
(re-runnable) and supports `--source`, `--recreate`, `--limit`, `--dry-run`.

The section RAG *retrieval* is now wired onto this path, behind the
`HYBRID_RETRIEVAL_ENABLED` flag (default off). When enabled,
`literev.libs.es_section_retrieval.get_best_section_chunks_es` retrieves a
decision's most relevant section chunks from `<source>_sections` with one hybrid
RRF query (BM25 on the question, dense kNN on a Hactar query embedding, filtered
to that decision) and groups them into the same `{section: [text, …]}` blocks
the Chroma path returned — a drop-in inside the section-RAG worker
(`rag_pdf.get_answer_document_worker`). With the flag off, the Chroma path is
used unchanged, so this is inert until a section index exists on the target and
`HYBRID_RETRIEVAL_ENABLED=true` is set. `HYBRID_TOP_K_PER_SECTION` and
`HYBRID_SEARCH_SIZE` tune chunks-per-section and the RRF pool.

### Enabling it on a deployment (the one command)

Hybrid retrieval is one idempotent step behind a flag, done on the target after
a normal deploy:

```bash
# 1. Build the ES section index(es) — re-embeds section chunks via Hactar.
#    Idempotent; start small to smoke-test, then run the full corpus.
makim django.embed-sections --source chambre_civile --limit 200   # first look
makim django.embed-sections                                       # all sources

# 2. Verify answer parity against the Chroma path (ask a few known questions,
#    or run the offline harness — see docs/rag-evaluation.md).

# 3. Flip the flag and redeploy once parity looks good:
#    set HYBRID_RETRIEVAL_ENABLED=true in .env, then
./scripts/deploy_now.sh --skip-deps --skip-build
```

The embed step is deliberately **not** run automatically by `deploy_now.sh` — it
is a large one-time job, and the flag stays a manual opt-in so retrieval only
switches to Elasticsearch after parity is confirmed. Once it is, the ChromaDB
path can be retired.

**Note on the embedding model:** the ES path already uses a single Hactar model
(`HACTAR_EMBED_MODEL`) for the whole corpus, build- and query-time — so the
"one vector space" goal is met here. The remaining OpenAI-vs-Hactar
`SECTION_EMBED_ENGINE` split lives only in the Chroma path and is removed when
Chroma is retired, not as a separate step.

## Measuring it on the VM

`scripts/bench_retrieval.py` is a standalone benchmark (plain `elasticsearch`
client, no Django) that reports **latency percentiles** and, given a small
labelled query→relevant-record_key set, **recall@k** for BM25 today and for the
hybrid query once vectors are indexed. Run it against the live index after each
rollout step to replace the order-of-magnitude table above with real numbers
for this corpus:

```bash
# latency only (works today, BM25):
python scripts/bench_retrieval.py --index <index> --queries scripts/bench_queries.sample.json

# with a labelled set, prints recall@k too:
python scripts/bench_retrieval.py --index <index> --queries labelled.json --k 10 20 50
```

## Bottom line

- Reranking (shipped) was the right first move: the biggest *ordering* win, a
  pure flag-flip, safe to leave on.
- **Hybrid → rerank is the best method** for both recall and precision, and the
  dense branch is the *only* thing that raises recall. It is worth doing.
- It is gated on a one-time re-index with on-prem (Hactar `mxbai-embed-large`)
  vectors in the VM's Elasticsearch — do that, keep the reranker as the final
  stage, and validate the gain with `scripts/bench_retrieval.py`.
