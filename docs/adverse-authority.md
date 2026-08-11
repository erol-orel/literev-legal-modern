# Adverse authority & the citation graph

The feature no generic RAG has and every litigator needs: proactively surface
the decisions **against** a position (adverse and distinguishing authority) and
flag when a cited decision has itself been **overturned or criticised** ("is
this still good law?"). A tool that only confirms is worth less than one that
warns.

This is built in phases; each is independently useful.

## Phase 1 — extract citations, build the graph (this repo)

Every Swiss decision cites others by a stable, language-independent form —
`ATF`/`BGE`/`DTF <vol> <part> <page>` for the published leading cases and the
Federal Court docket `<chamber>_<seq>/<year>` for the rest.
`lr_legal.extract_citations` recognises both (see
[`case_citations.py`](../libs/lr-legal/src/lr_legal/case_citations.py)); it is
pure and unit-tested, and deliberately conservative — a wrong citation edge is
worse than a missing one.

`build_citation_graph` runs that over the corpus:

```bash
python manage.py build_citation_graph --index bundesgericht --output graph.json
# or across chambers, capped for a first look:
python manage.py build_citation_graph \
    --index chambre_administrative,chambre_penale --limit 5000
```

The output is a directed graph — the edge list plus each decision's **in-degree**
(how often it is cited). In-degree alone already gives you "leading decisions"
(the most-cited authorities in a topic) to rank or badge in search and RAG
results. It runs on the VM, where Elasticsearch holds the decisions.

## Phase 2 — classify the treatment

An edge says A cites B; it does not yet say *how*. Classify each citing passage
as **affirming**, **distinguishing**, **criticising** or **overruling** — a
short-context classification over the sentence around each citation (the same
section-classification machinery the RAG pipeline already uses for
faits/subsomption/conclusion). A decision with incoming *overruling* or
*criticising* edges is flagged "treated negatively — verify it is still good
law."

## Phase 3 — surface it in the product

- **In the RAG result**: for each cited decision, show a "still good law?"
  badge from its incoming treatment, and a "distinguishing authority" section
  listing decisions that went the other way on the same question.
- **In the document view**: an "cited by / cites" panel with treatment icons.
- **In search**: let a jurist rank by authority (in-degree) or filter out
  negatively-treated decisions.

## Why a graph, not just per-answer prompting

Asking the LLM "is this overruled?" per answer is unreliable and can't see
beyond the documents in the current question. A precomputed graph over the
**whole corpus** is deterministic, explainable (you can show the citing
passage), and complete — exactly the properties a professional-stakes tool
needs. Phase 1 is the foundation the rest builds on.
