# Session handoff

This file lets a fresh Claude Code session (or any developer) pick up work on
LiteRev Legal without the earlier chat history. Read [AGENTS.md](AGENTS.md) for
conventions and the code map; this file covers **where the work stands** and
**what is open**.

Last updated: 2026-10-30. `main` at `f0136ca` — PR #79, merged 2026-09-02. There
is no unmerged feature work: the only open PRs are from Dependabot.

## What the product is now

A research tool for **Swiss case law**: the three Geneva chambers plus the
federal courts (Bundesgericht, ATF, administrative, criminal, patent) and the
Romandie/bilingual cantonal courts, imported from entscheidsuche.ch. Decisions
are in French, German or Italian; the pipeline detects and stores each
decision's language and answers in it.

Flow: boolean query → Elasticsearch BM25 → optional cross-encoder rerank →
TF-IDF / PaCMAP / HDBSCAN clustering → iterative refinement → section-based RAG
(Majeure / Mineure-Faits / Mineure-Subsommation / Conclusion) with citations,
faithfulness scores and a Word memo export.

## What shipped since the previous handoff (2026-08-04 → 2026-09-02)

The previous handoff covered the frontend rebuild on `claude/modern-frontend`.
That work is merged, and `src/frontend-legacy/` was deleted in #69.

- **Sources and languages:** entscheidsuche importer for federal decisions (#11,
  #42–#44), ATF and patent court (#46), Romandie cantonal courts (#47), DE/FR/IT
  preprocessing and spaCy models (#13, #14), stored document language (#16),
  answers in the decision's language (#17), federal sources in section RAG
  (#18), deep links to Fedlex and silgeneve.ch (#9, #15).
- **Legal features:** Swiss citation extraction and a corpus citation graph
  (#63), "is this still good law?" citation treatment (#66).
- **RAG UX:** answer-first result page with an evidence rail (#52), one-click
  claim-to-source (#61), follow-up question suggestions (#64), `.docx` memo
  export (#58), citation filter/search/copy (#12), sanitised injected HTML and
  route code-splitting (#53).
- **Retrieval:** cross-encoder reranking behind `RERANK_ENABLED` (#51); ES
  section index foundation (#68); section RAG on Elasticsearch behind
  `HYBRID_RETRIEVAL_ENABLED` (#71, #73); Chroma → ES migration that reads
  Chroma's SQLite store and embeds with OpenAI (#77); `--skip-existing` resume
  (#78); dense kNN instead of RRF because RRF needs a paid ES license (#79).
- **Quality and performance:** offline RAG evaluation harness (#62), parallel
  faithfulness scoring (#50), leaner RAG queries and a `TableChoice` index
  (#49), surfacing silent section → generic RAG fallback (#48), optional Hactar
  embeddings (#45), opt-in per-user document response cache (#65).
- **Ops:** Hetzner runbook and federal import/embed makim wrappers (#41),
  `scripts/deploy_now.sh` (#59), infrastructure guide (#36), secret hardening
  plus gitleaks (#19), WhiteNoise for `/static` (#76), health-check fix (#75),
  lazy `python-docx` import (#74).
- **Cleanup and design docs:** removed orphaned legacy code (#69, #70),
  consolidation ADR and question-first frontend spec (#67).

## Deployment state the repo cannot tell you

These live on the Hetzner VM, not in git. Confirm with the project owner before
relying on them:

1. **Has the Chroma → ES section migration finished?** PR #78 was written after
   a run stopped when the OpenAI credits ran out. To resume without paying again
   for chunks already indexed, run
   `python manage.py embed_sections_to_es --skip-existing` directly:
   `makim django.embed-sections` does not pass that flag. (Its help text also
   still says "through Hactar"; the engine now defaults to OpenAI.)
   `manage.py rag_section_status` shows which sources have a usable Chroma
   section collection; it does not inspect the ES indexes.
2. **Is `HYBRID_RETRIEVAL_ENABLED=true` set on the VM, and was answer parity
   with the Chroma path checked?** See `docs/hybrid-retrieval.md` and
   `docs/rag-evaluation.md`.
3. **Is `RERANK_ENABLED` on, and with which provider** (`local`, a remote URL,
   or Cohere)?
4. **Which sources have section embeddings?** Sources without them fall back to
   generic RAG; that is expected, not a bug.

## Open items

1. **`docs/hybrid-retrieval.md` is behind the code.** It still describes section
   retrieval as an RRF query on Hactar embeddings. Since #77 and #79 it is a
   dense kNN query on OpenAI `text-embedding-3-large` vectors
   (`HYBRID_EMBED_ENGINE=openai`), filtered to one decision.
2. **RRF is not usable on the current ES license.** `lr_search.hybrid`
   `build_hybrid_search_body` still builds an RRF retriever. Nothing calls it in
   production today, but the planned BM25 + dense candidate generation for the
   results table would get a 403 the same way. It needs client-side fusion or a
   licence decision before it is built.
3. **Retire ChromaDB** once the ES path has parity: the Chroma retrieval path,
   `chroma_utils`, and the `SECTION_EMBED_ENGINE` split go with it.
4. **Native cluster map.** `/project/:id` still embeds the Bokeh plot
   (`src/frontend/src/components/common/bokeh-plot.tsx`). Exposing
   `ClusterElement` coordinates from the backend would allow a themeable React
   scatter. Carried over from the previous handoff.
5. **Stale commands in other docs.** `docs/index.md` and
   `docs/services/containers.md` reference `makim containers.start` and
   `makim containers.start-celery`, which do not exist (containers are managed
   with `sugar`). `docs/services/configuration.md` is missing the rerank, hybrid
   and response-cache variables (they are listed in `AGENTS.md`).
6. **`MIN_CONFIDENCE` has no effect.** `settings/base.py` reads it into
   `settings.MIN_CONFIDENCE`, but `libs/rag_pdf.py` filters answers on
   `getattr(settings, "RAG_MIN_CONFIDENCE", 0.0)`, which is never defined, so
   the threshold is always 0.0. Decide which name wins before fixing it: turning
   it on will hide low-confidence answers that users currently see.
   (`LITEREV_CACHE_ACTIVE` is similarly read into settings and never used.)
7. **Dependabot backlog: 20 open PRs**, several of them major bumps (vite 5 → 8,
   `@eslint/js` 10, jsdom 30, tailwind-merge 3, langchain < 1.4, setuptools <
   84, `actions/download-artifact` 8). Do **not** merge the rago bump (#32)
   as-is: `pyproject.toml` pins `rago < 0.14.5` on purpose because 0.14.5
   renamed `generate(context=)` to `generate(data=)`.

## Frontend contract (still applies)

`src/frontend/` is a Vite + React + TypeScript SPA that Django serves through
`literev/templates/generic.html`. `vite.config.ts` has a `craAssetManifest()`
plugin that writes a Create-React-App-style `build/asset-manifest.json`, so the
`literev.templatetags.frontend.frontend_static` tag works unchanged. Keep that
plugin, the `build/static/` output layout and the slash-terminated client routes
intact when changing the build. Commands, from `src/frontend/`: `npm run dev`,
`npm run build`, `npm run typecheck`, `npm run lint` (zero warnings),
`npm test`.

## Working in a fresh cloud session

- The container does not come with `makim`, `pre-commit`, `sugar` or Python
  3.11. Create the env from `conda/base.yaml`, then run
  `scripts/install-dev.sh`.
- No secrets are set (`OPENAI_API_KEY`, `ES_*`, Postgres). Code changes, lib
  tests and frontend tests work without them; the app suite needs Postgres and
  Redis (see the "App Tests" job in `.github/workflows/main.yaml`).
- CI rejects a PR whose branch is not up to date with `main`, so rebase before
  pushing. PRs are squash-merged with Conventional Commit titles, which drive
  semantic-release.
