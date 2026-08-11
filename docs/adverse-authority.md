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

## Phase 2 — classify the treatment (implemented)

An edge says A cites B; it does not say *how*. `lr_legal.classify_treatment`
labels each citing passage — the window around the citation — as **followed**,
**distinguished**, **criticized** or **overruled** (else neutral **cited**). It
is a deterministic, multilingual (fr/de/it) keyword classifier, chosen over an
LLM on purpose: a treatment label drives a professional-stakes warning, so it
must be reproducible and its evidence (the matched cue + passage) inspectable.
`build_citation_edges(records, with_treatment=True)` attaches the label to each
edge, and `build_citation_graph` aggregates the **`treated_negatively`** set —
decisions with incoming *overruled*/*criticized* edges, the "verify: still good
law?" list. (An LLM pass can later refine the ambiguous middle; the heuristic
is the dependable floor.)

## Phase 3 — surface it in the product

- **In the RAG result** *(component shipped)*: the `TreatmentBadge` renders a
  "still good law?" badge on each cited decision from `document.treatment`
  (overruled → destructive, criticized → warning, distinguished → outline,
  followed → success), with an explanatory tooltip. It shows nothing until the
  field is populated — the **remaining wiring** is: build the graph on the VM,
  store it, and have the answer serializer set `document.treatment` from the
  `treated_negatively` / edge data by the decision's `record_key`.
- **In the document view** *(next)*: a "cited by / cites" panel with treatment
  icons.
- **In search** *(next)*: rank by authority (in-degree) or filter out
  negatively-treated decisions.

## Why a graph, not just per-answer prompting

Asking the LLM "is this overruled?" per answer is unreliable and can't see
beyond the documents in the current question. A precomputed graph over the
**whole corpus** is deterministic, explainable (you can show the citing
passage), and complete — exactly the properties a professional-stakes tool
needs. Phase 1 is the foundation the rest builds on.
