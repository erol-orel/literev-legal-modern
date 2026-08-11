# ADR 0001 — Consolidate retrieval and inference

- **Status:** Proposed
- **Date:** 2026-08-11
- **Deciders:** LiteRev maintainers
- **Supersedes:** —

## Context

The platform answers Swiss legal-research questions over a corpus of court
decisions (Geneva chambers + Tribunal fédéral, fr/de/it). Today the retrieval
and inference stack is spread across four moving parts that were each added for
a good reason but no longer earn their keep as separate pieces:

1. **Elasticsearch** holds the decisions and serves **lexical** (BM25) search.
   Pinned `>=8.12.1,<9.0.0` (`pyproject.toml`, `libs/lr-search/pyproject.toml`).
2. **ChromaDB** holds the **dense** vectors for the section-based RAG
   collections — a *second* store, kept in sync by a separate embed pass
   (`run_chromadb_embeddings`), queried by `chroma_utils` / `search.py`.
3. **Embeddings** come from **two incompatible vector spaces**: OpenAI
   `text-embedding-3-large` (3072-dim) for the Geneva chambers, and optionally
   Hactar `mxbai-embed-large` (~1024-dim) for the federal courts. A collection
   embedded with one engine *must* be queried with the same engine
   (`SECTION_EMBED_ENGINE`) — a sharp edge that has already needed guard rails.
4. **The answer LLM** is `gpt-4.1-mini` by default (`CHAT_MODEL`), or Hactar
   `mistral-small3.1:24b` behind `USE_HACTAR_LLM`. Reranking
   (`reranking.py`, `RERANK_ENABLED`) is wired but off by default.

This works, but it carries structural cost:

- **Two stores, one meaning.** The lexical index and the vector index describe
  the same decisions and must be kept consistent by two ingestion paths. Every
  new source (a cantonal court, a new federal chamber) is onboarded twice.
- **Split vector spaces.** OpenAI-3072 and Hactar-1024 cannot be compared,
  reranked, or fused with each other. "Which engine embedded this collection?"
  is load-bearing configuration, not an implementation detail.
- **A metered external dependency on the read path.** OpenAI embeddings price
  and rate-limit every query and every ingested document, and send corpus text
  off-premises — a concern for a professional-stakes legal tool whose users
  care about confidentiality and reproducibility.
- **Hybrid search is not actually running.** The dense signal lives in a store
  the lexical query never touches, so today's answers are effectively BM25 +
  a separate Chroma lookup, not a single fused hybrid ranking.

The [hybrid-retrieval](../hybrid-retrieval.md) and [reranking](../reranking.md)
docs already describe the target retrieval *quality* (BM25 + dense, RRF-fused,
then cross-encoder rerank). This ADR is about the *topology* underneath it.

## Decision

Consolidate to **one hybrid store and self-hosted inference**, in four moves.
Each is independently shippable and behind the existing flags, so the corpus is
never down during the migration.

### 1. One store: dense vectors move into Elasticsearch, retire ChromaDB

Elasticsearch 8.x is already a vector database: `dense_vector` fields with HNSW
kNN, and — crucially — a native `retriever` + `rrf` API that fuses a BM25 query
and a kNN query into a **single reciprocal-rank-fused ranking in one round
trip**. Put the section embeddings on the same documents that already carry the
BM25 text, and the "two stores, one meaning" problem disappears: one ingestion
path, one query, one ranking.

- Add a `section_vector` (`dense_vector`, `index: true`, `similarity: cosine`)
  field to the section index mapping.
- The existing embed pass writes the vector to ES instead of Chroma.
- Retrieval becomes one `retriever: { rrf: { retrievers: [ {standard: BM25},
  {knn: section_vector} ] } }` query; the reranker (already built) reorders the
  fused top-k.
- **ChromaDB is removed** once parity is verified: `chroma_utils`,
  `run_chromadb_embeddings`, and the Chroma paths in `search.py` / `nlp.py` /
  `rag_pdf.py` retire. One fewer service to run, back up, and keep in sync.

Storage stays modest with ES built-in **int8 / BBQ quantization** on the
`dense_vector` field (see move 4).

### 2. One vector space: self-host BGE-M3 for embeddings

Replace both OpenAI-3072 and Hactar-mxbai-1024 with a single self-hosted
**BGE-M3** embedding model (1024-dim, explicitly multilingual — fr/de/it in one
space, which the Swiss corpus needs). One engine means:

- No `SECTION_EMBED_ENGINE` per-source branching; no "query with the same
  engine you embedded with" foot-gun.
- Vectors are comparable across the *whole* corpus — Geneva and federal
  decisions rank against each other honestly.
- No per-query, per-document metering; no corpus text leaving the premises.

Re-embedding the corpus once is the cost. It is a batch job, runnable off the
ingestion path (see [performance](../performance.md)), and it is the last time
the vector space changes.

### 3. One reranker, self-hosted: BGE-reranker-v2-m3

Keep the reranking stage the code already supports, served locally by
**BGE-reranker-v2-m3** (the natural cross-encoder companion to BGE-M3,
multilingual). It reorders the fused top-k by true query–passage relevance —
the step that most improves *ordering* once hybrid has fixed *recall*. It stays
behind `RERANK_ENABLED` so it can be rolled out and measured independently.

### 4. Topology: a modular monolith + a GPU inference node (two tiers)

Do **not** split the application into a fleet of microservices (search service,
answer service, ingestion service, similarity service, clustering service, …).
At this corpus size and team size that is operational overhead without benefit:
five services that all fail if the one GPU box is down are not more available
than one, only harder to deploy and reason about. Keep the Django app a
**modular monolith** with clean internal boundaries (the `lr_*` libs already
enforce this) and separate along the one axis that actually has different
hardware needs:

- **Tier A — application + data.** The Django app, Postgres, Redis, and the
  **Elasticsearch data node** (BM25 + vectors). CPU/RAM box, generous disk,
  no GPU. ES lives here, *not* on the GPU box — its memory and disk profile has
  nothing to do with inference, and coupling them wastes GPU RAM and couples
  two very different failure and scaling curves.
- **Tier B — GPU inference.** A small internal service that serves the three
  models over HTTP: the answer LLM, BGE-M3 embeddings, and BGE-reranker-v2-m3.
  The app calls it the same way it calls OpenAI/Hactar today (an OpenAI-compatible
  endpoint), so the switch is a base-URL change, not a rewrite.

Suggested GPU layout for a two-GPU box (matches the sizing already sketched):

| GPU  | Serves                                        | Role                          |
| ---- | --------------------------------------------- | ----------------------------- |
| GPU0 | Answer/overview LLM + boolean-query translator | generation                    |
| GPU1 | BGE-M3 embeddings + BGE-reranker-v2-m3         | retrieval (embed + rerank)    |

The **answer LLM size is an open question to settle with data, not taste.**
The [rag-evaluation](../rag-evaluation.md) harness (verdict accuracy, citation
precision/recall, faithfulness) is exactly the instrument for it: run the gold
set against a 14B (e.g. a Ministral-class model) and against the current
`gpt-4.1-mini` baseline, and let the faithfulness/accuracy numbers pick the
smallest model that holds quality. Ship whatever passes.

## Consequences

**Positive**

- One store, one vector space, one ingestion path. New sources onboard once.
- Hybrid (RRF) and reranking run for real, on comparable vectors — the retrieval
  quality the other docs describe becomes reachable, not aspirational.
- No corpus text or query text leaves the premises; no per-call metering on the
  read path. Better confidentiality story and predictable cost — a
  fixed-cost GPU box instead of a variable API bill.
- Fewer services to operate. ES scales on its own curve; the GPU box scales on
  another.
- Model choices become measurable: the eval harness, not vibes, sets LLM size.

**Negative / cost**

- A **one-time full re-embed** of the corpus into the new BGE-M3 space.
- **Capital/opex for the GPU box** and the work to serve three models on it
  reliably (health checks, batching, warm start). This is the line item that
  needs funding; the payoff is no ongoing API bill and data staying in-house.
- Someone owns model serving now. Mitigated by using an off-the-shelf
  OpenAI-compatible server (vLLM / TGI / Ollama) rather than bespoke glue.

**Neutral**

- ES stays on the 8.x line (the `<9.0.0` pin holds); the `retriever`/`rrf` and
  `dense_vector` quantization features this ADR relies on are all 8.x. Moving to
  9.x later is a separate, unforced decision.

## Alternatives considered

- **Keep ChromaDB, keep two stores.** Rejected: it is the source of the
  split-brain (two ingestion paths, split vector spaces) this ADR exists to
  remove. Nothing Chroma does here ES 8.x does not do on the documents it
  already holds.
- **Add [turbovec](https://github.com/RyanCodrai/turbovec) (or any new vector
  DB).** Rejected. It is a neat, fast in-memory vector index, but adopting it
  *reintroduces the exact problem we are removing* — a second store beside ES,
  separately populated and kept in sync — to solve a speed problem we do not
  have at this corpus size. If vector storage/latency ever bites, the first
  lever is **ES built-in int8/BBQ quantization** on the existing
  `dense_vector` field, not a new datastore. One store is the point.
- **Full microservices split (5–6 services).** Rejected as premature: it
  multiplies deployment and failure surface without buying availability or
  independent scaling that this workload actually needs. The two-tier split
  (app+data / GPU inference) captures the only real hardware boundary. Revisit
  if and when a single component's scaling genuinely diverges from the rest.
- **Stay on OpenAI embeddings + hosted LLM.** Rejected for the read-path
  metering, the off-premises data flow, and the split vector space. A one-time
  GPU capex buys a fixed cost, on-prem data, and a single comparable space.
- **Self-host embeddings but keep Chroma as the vector store.** Rejected:
  fixes the vector-space problem but keeps the second store and its sync path.
  Half the win for most of the work.

## Rollout (flag-gated, corpus never down)

1. Add `section_vector` to the ES mapping; dual-write embeddings to ES **and**
   Chroma during transition.
2. Stand up Tier B (GPU inference) serving BGE-M3; re-embed into ES in the new
   space as a batch job.
3. Flip retrieval to the ES `rrf` retriever behind a flag; A/B against the
   Chroma path with the [rag-evaluation](../rag-evaluation.md) harness.
4. Turn on `RERANK_ENABLED` with BGE-reranker-v2-m3; measure the ordering lift.
5. Swap the answer LLM to the eval-selected model via its OpenAI-compatible
   base URL.
6. When parity/quality holds, delete the Chroma paths and decommission the
   OpenAI embedding dependency.

Each step is observable, reversible until the last one, and gated — the
migration is a sequence of measured switches, not a big-bang cutover.
