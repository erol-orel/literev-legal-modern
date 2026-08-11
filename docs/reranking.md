# Retrieval reranking (cross-encoder)

Elasticsearch ranks results by **BM25** (lexical). A **cross-encoder reranker**
reorders the top-K of that candidate set by semantic relevance to the
natural-language query — the single biggest retrieval-quality win, catching
paraphrase / synonymy / conceptual and cross-lingual matches BM25 misses.

The pipeline is: **BM25 (Elasticsearch) → cross-encoder rerank of the top‑K →
top‑N** for answering and display. It is applied in three places
(`libs/reranking.rerank_documents`): the two RAG answer-selection paths
(`rag_pdf.py`) and the results table (`table_choice.py`).

## Disabled by default

With `RERANK_ENABLED=false` (the default) nothing changes — pure BM25 order.
Any reranker error (down, timeout, malformed response) also falls back to BM25,
so reranking is always safe to leave wired in.

## Where to run it — the VM, not Hactar

Hactar (`hactar.unige.ch`) only serves **chat** (mistral) and **embeddings**
(`mxbai-embed-large`) through its Ollama gateway; it has **no cross-encoder
rerank endpoint**, and using an LLM as a reranker is slow and lower quality.
Run a small dedicated cross-encoder **on the VM**: it keeps the privileged
decision text on-prem, costs nothing per query, and a reranker is a small model
that runs fine on CPU for a top-K rerank.

### Recommended: `bge-reranker-v2-m3` via Text Embeddings Inference (TEI)

`BAAI/bge-reranker-v2-m3` is multilingual (strong on French legal text) and TEI
exposes a `POST /rerank` endpoint the app speaks natively. Run it next to the
other services (CPU image shown; add a GPU if you have one):

```bash
docker run -d --name literev-reranker --restart unless-stopped \
  --network literev \
  -p 127.0.0.1:8080:80 \
  -v /opt/data/literev/tei:/data \
  ghcr.io/huggingface/text-embeddings-inference:cpu-latest \
  --model-id BAAI/bge-reranker-v2-m3
```

Then in the VM `.env`:

```
RERANK_ENABLED=true
RERANKER_PROVIDER=local
RERANKER_URL=http://literev-reranker:80      # or http://host.docker.internal:8080
RERANK_TOP_K=50
```

Restart the app/celery so the settings load, then run a natural-language search
and confirm the ordering improves. Watch latency in the logs — reranking 50
decisions on CPU is typically a few hundred ms; lower `RERANK_TOP_K` if needed.

### Managed alternative: Cohere Rerank

If you'd rather not self-host (accepting per-query cost and sending text to a
third party):

```
RERANK_ENABLED=true
RERANKER_PROVIDER=cohere
RERANKER_MODEL=rerank-multilingual-v3.0
COHERE_API_KEY=...
```

## Tuning

| Setting | Default | Meaning |
|---|---|---|
| `RERANK_ENABLED` | `false` | Master on/off. |
| `RERANKER_PROVIDER` | `local` | `local` (TEI `/rerank`) or `cohere`. |
| `RERANKER_URL` | `http://literev-reranker:80` | Local reranker base URL. |
| `RERANK_TOP_K` | `50` | How many BM25 candidates to rerank. |
| `RERANK_MAX_CHARS` | `2000` | Chars of each decision sent to the cross-encoder. |
| `RERANKER_TIMEOUT_S` | `20` | Per-request timeout before falling back to BM25. |

## Next step (phase 2): hybrid retrieval

Reranking improves the *ordering* of the BM25 candidate set but not its
*recall*. To also improve recall (find decisions BM25 never surfaced), add a
dense retriever and fuse with BM25 via **RRF** — natively supported by the
`retriever` API in the deployed Elasticsearch 8.14: index a document-level
`dense_vector` (a multilingual embedding — **not** ELSER, which is English
only) and combine a `standard` (BM25) and a `knn` retriever with `rrf`, then
rerank the fused top-K exactly as above. That is a separate change (an ES
mapping + a corpus embedding pass) best landed with a live index to test on.
