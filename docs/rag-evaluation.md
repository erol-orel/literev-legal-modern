# Measuring RAG answer quality

In legal work a wrong answer is a liability, not a bug ticket. You cannot
improve — or safely change — what you do not measure, so every change to
retrieval, prompts, the embedding model or the reranker should be scored
against a **fixed gold set** before it ships. `scripts/eval_rag.py` is that
scorer: standalone (no Django, no app imports), it reports the three axes a
jurist actually cares about.

## What it measures

| Metric | Question it answers |
| --- | --- |
| **Verdict accuracy** | Did the closed-question verdict (oui / non / peut-être / mixte) match the labelled answer? |
| **Citation precision / recall** | Of the decisions cited, how many were relevant; of the relevant decisions, how many were surfaced? (micro = pooled, macro = per-case average) |
| **Faithfulness** | Mean Ragas grounding score across the cited answers (already stored as `confidence_score`). |

Citation **recall** is the retrieval-quality signal — it is exactly what
hybrid retrieval (see [hybrid-retrieval.md](hybrid-retrieval.md)) is meant to
move. Citation **precision** and **verdict accuracy** are the answering-quality
signals — what prompt and model changes move. Watching them separately tells
you *which* stage a change helped or hurt.

## The two inputs

Two JSON files, joined by a case `id`:

- **`gold.json`** — the labels, written once by hand: `{id, question,
  expected_verdict?, relevant_ids?}`. See `scripts/eval_gold.sample.json`.
  Everything but `id` is optional; a case with no `expected_verdict` is simply
  skipped for verdict accuracy, etc., so a partial gold set still works.
- **`predictions.json`** — one run of the pipeline over those same cases:
  `{id, verdict|counts, cited_ids, confidence_scores?}`. See
  `scripts/eval_predictions.sample.json`.

`relevant_ids` / `cited_ids` should use whatever stable id you trust to compare
decisions — the Elasticsearch `record_key` is the natural choice.

## Producing a predictions dump

Run the pipeline over each gold question (same document set as the case), then
for each `ProjectRAG` read its `stats.classification_stats.counts` for the
verdict and its `ProjectDocumentRAG` rows for the cited decisions and
`confidence_score`s. A short management command or a loop over the RAG API
(`/api/project-documents-rag/?project_rag=<id>`) emits the `predictions.json`
shape directly. Keep the gold set in the repo; regenerate predictions per
change.

## The loop

```bash
# 1. Baseline on the current main:
python scripts/eval_rag.py --gold gold.json --predictions before.json --json before.metrics.json

# 2. Make a change (e.g. enable reranking, swap the prompt), re-run the pipeline,
#    dump after.json, then:
python scripts/eval_rag.py --gold gold.json --predictions after.json --json after.metrics.json

# 3. Compare before.metrics.json / after.metrics.json — ship only if the axis
#    you targeted improved and nothing else regressed.
```

Start with 20–50 hand-labelled cases spanning the chambers and the Tribunal
fédéral, in all three languages; grow the set whenever a real answer is wrong
(add it as a case so the mistake can't silently return). Pair this with
`scripts/bench_retrieval.py` (latency + recall on the raw index) and you can
measure both halves of the system — retrieval and answering — on every change.
