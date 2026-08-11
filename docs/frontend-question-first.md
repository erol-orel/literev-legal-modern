# Question-first frontend: the answer is the page

The design principle for the research surface: **a jurist types a question and
the answer is the page.** The general considerations (*considérations
générales*), the verdict, and the extractable tables are the first thing on
screen — not something reached by drilling into a document. Everything else
(the cited decisions, the per-decision reasoning, the export) is arranged
beneath that answer in the order a lawyer actually reads.

This is the frontend the demo feedback asked for ("show the *considérations
générales* immediately", "reinvent the frontend"). The structure below is
**shipped** — the answer-first components in `src/frontend/src/components/rag/`
— and this doc is the map: what the flow is, why, and what is left to wire.

## The problem it replaces

The pre-rebuild surface buried the answer. A lawyer who wanted the general
considerations had to walk a path roughly like:

1. Open the RAG workspace for the project.
2. Open a result.
3. Scroll past the query/composer chrome to the per-document list.
4. Open an individual decision.
5. Find, inside that decision, the section that carried the general reasoning.

Five clicks to reach the thing they came for. The *content* tested well — the
lawyers liked the *considérations générales*, the *tableau des éléments clés*,
and the *tableau des articles de loi* — but the **information architecture put
those behind the evidence instead of in front of it.** The fix is not more
features; it is inverting the reading order.

## The flow: three states, zero drilling

The research page (`src/frontend/src/pages/rag-page.tsx`) has exactly three
states, and the answer is never more than the current one:

1. **Fresh (no question yet).** The composer leads: a single question box with
   a legal-domain placeholder. Nothing else competes for attention.
2. **Analyzing.** The composer collapses to a compact one-line question bar; an
   "Analyzing N documents…" card plus skeletons *foreshadow the shape of the
   answer to come* (a summary block, then decision cards), so the layout does
   not jump when results land.
3. **Answered.** The compact question bar stays at the top (with a "New
   question" affordance and follow-up suggestions), and directly beneath it the
   **answer is rendered top-down** — no tab to select, no decision to open.

The inversion is in state 3: the composer is demoted to a bar, and the answer
occupies the page.

## Reading order (what renders, top to bottom)

`RagResult` (`components/rag/rag-result.tsx`) composes the answer in the jurist's
reading order:

| Order | Component        | Shows                                                                          |
| ----- | ---------------- | ------------------------------------------------------------------------------ |
| 1     | `AnswerVerdict`  | **General considerations** (summary) as the hero, the closed-question verdict distribution (oui/non/peut-être/mixte), aggregate answer confidence, the **key considerations** each traceable to the decision types that raised them, and the *règle de droit*. |
| 2     | `ReportPanel`    | The extractable **Éléments clés** and **Articles de loi** tables, plus one-click **Copy / Text / Word (.docx)** export of the whole memo.        |
| 3     | `SourceList`     | The cited decisions as an evidence rail — each `SourceCard` with its En fait / Subsomption / Conclusion reasoning, verbatim citation, confidence, and the "still good law?" treatment badge. |

The three things the lawyers named — *considérations générales*, *éléments
clés*, *articles de loi* — are items 1 and 2. **They are on screen the moment a
result loads: zero extra clicks.** The evidence they liked as *support* (the
per-decision detail) is item 3, beneath the answer, where support belongs.

## Why this shape

- **Answer-first matches the task.** A lawyer asks a question to get an
  answer, not to browse a corpus. The page mirrors that: conclusion first,
  evidence under it, source detail one level down.
- **Traceable, not just fast.** Surfacing the answer up front does not hide the
  work: each key consideration carries the procedure types that raised it, and
  the pinpoint verifiability (claim → source) links the summary back to the
  cited passages. Fast to read, still auditable — the property a
  professional-stakes tool needs.
- **The layout never lurches.** The analyzing-state skeletons occupy the same
  boxes the answer will, so the reading position is stable from skeleton to
  result.
- **Export is where the reading ends.** By the time a jurist has read the
  answer and skimmed the tables, the Copy / Text / Word controls are right
  there in `ReportPanel` — the memo drops straight out of the surface they just
  read.

## Terminology

The tables render in the jurists' own French vocabulary — **Éléments clés**,
**Articles de loi** — matching the terms that tested well. The *considérations
générales* map to the `AnswerVerdict` hero (general summary + key
considerations). The app chrome around the answer (navigation, buttons) is
currently English; a full fr/de/it localization of the chrome is a separate,
larger piece of work (the corpus itself is already multilingual) and is out of
scope for this IA change — the *answer content* speaks the jurist's language,
which is what the demo feedback was about.

## Status

**Shipped** (in `components/rag/`): `RagResult`, `AnswerVerdict`,
`ReportPanel`, `SourceList` / `SourceCard`, `ConfidenceMeter`, the facts
tables, follow-up suggestions, the treatment badge, and the client-side memo
export. The three-state page flow is `pages/rag-page.tsx`. All of it is covered
by the frontend test suite and validated locally (typecheck / lint / test /
build).

**Remaining wiring (data, not layout):**

- The treatment badge ("still good law?") renders from `document.treatment`,
  which is populated only once the citation graph is built on the VM and the
  answer serializer sets the field by `record_key`
  (see [adverse-authority](adverse-authority.md), Phase 3).
- The aggregate confidence and per-decision faithfulness surface whatever the
  backend provides; richer confidence depends on the evaluation work in
  [rag-evaluation](rag-evaluation.md).

The IA itself is done: the answer is the page.
