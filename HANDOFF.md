# Modern frontend rebuild — session handoff

This document lets a fresh Claude Code session (or any developer) pick up the
frontend modernization without the original chat history. Everything needed is
here plus the commit messages on the `claude/modern-frontend` branch.

## Goal

Rebuild the LiteRev legal frontend as a modern SPA **without touching the Django
backend**. The new app is a drop-in replacement for the previous
Create-React-App frontend: same URLs, same DRF endpoints, same Django
static-serving contract.

## Stack

- **Vite 5 + React 18 + TypeScript** (strict)
- **Tailwind CSS** design system with light/dark themes
- **TanStack Query** for server state; **TanStack Table** for grids
- **Radix UI** primitives + **lucide-react** icons +
  **class-variance-authority**
- **Vitest** for tests, **ESLint** (`--max-warnings 0`) for lint

## Repo layout

- `src/frontend/` — the **new** modern app (work here)
- `src/frontend-legacy/` — the **old** CRA app, preserved verbatim for reference
  (pure `R100` renames; safe to delete once parity is confirmed)

## Django integration (do not break this contract)

`vite.config.ts` includes a `craAssetManifest()` plugin that emits a
CRA-compatible `asset-manifest.json`, so the existing Django template tag
`literev.templatetags.frontend.frontend_static` keeps working unchanged:

- `npm run build` writes to `src/frontend/build/`
- Assets go under `build/static/`; `collectstatic` flattens them to `/static/`
- The manifest exposes `files["main.js"]` / `files["main.css"]` as `/static/...`
- Client routes mirror Django's slash-terminated URLs (`/search/`, `/rag/:id`,
  …)

Result: **zero backend changes**. The Django views/templates render the shell;
this SPA hydrates it.

## Commands (run in `src/frontend/`)

| Task              | Command             |
| ----------------- | ------------------- |
| Dev server        | `npm run dev`       |
| Production build  | `npm run build`     |
| Type-check only   | `npm run typecheck` |
| Lint (0 warnings) | `npm run lint`      |
| Tests             | `npm test`          |

Last verified state on `claude/modern-frontend`: **build ✓ · lint ✓ (0 warnings)
· tests ✓**.

## What's done

- Toolchain scaffold (Vite + TS + Tailwind), drop-in with Django
- Design system + base UI components (Radix-backed, themed)
- Typed API/context layer + TanStack Query hooks over the existing DRF endpoints
- App shell: layout, sidebar, topbar, theme toggle, auth guard, router
- **Flagship pages, fully rebuilt:**
  - **Search / new project** (`/search`)
  - **Running** (`/running`) — live-polling project cards, restart, delete
  - **History** (`/historicalpage`) — search, sort, open, delete, delete-all
  - **Project overview** (`/project/:id`) — stats, cluster summary cards with
    on-demand LLM summaries, the themed Bokeh cluster map (preserved as-is), an
    interactive refinement/filter builder (union/exclude with live preview),
    refinement list, ask-top-documents hand-off
  - **RAG workspace** (`/rag/:projectId[/:ragId]`) — open/closed questions, live
    status polling, cited per-document answers with Faits/Subsomption/
    Conclusion parsing + confidence scores, cross-document summary with
    closed-question stats, previous-questions history
- A single reusable `ConfirmDialog` replaces the three duplicated delete modals
  from the legacy app.
- **Document selection** (`/tableselect/*`) — rebuilt. Per-iteration triage of
  every retrieved decision: tri-state Yes/Maybe/No verdicts, check-all, the
  iteration trail (activate / delete), server-driven sort + pagination,
  refinement/exclusion filter summaries, processing-state polling, CSV export,
  iterate, reset, and ask-selected. (`src/api/table-selection.ts`,
  `src/pages/tableselect-page.tsx`.) Rendered as review-friendly document cards
  in the app's design system rather than a dense grid — the extracts need to be
  readable — while preserving the exact legacy DRF contract and URL scheme.
- **Document viewers** (`/contentdocument/:id`,
  `/contentdocument_highlighted/:ragId`) — rebuilt. Metadata header plus the
  full decision text, with RAG-cited passages highlighted inline on the
  highlighted view (`.legal-prose` styling). (`src/api/documents.ts`,
  `src/pages/document-page.tsx`.)

### Toolchain note (fixed)

The repo-root `.gitignore` carried the stock Python packaging section, whose
unanchored `lib/` matched at **any** depth — so `src/frontend/src/lib/` was
silently never committed and the bundle shipped a branch that could not build.
The four modules (`api-client`, `context`, `query`, `utils`) have been
reconstructed and the ignore rule anchored to the repo root (`/lib/`).

## What's left (next steps)

1. **Native cluster map (recommended backend follow-up):** the cluster map is
   still the legacy Bokeh embed. Exposing raw `ClusterElement` coordinates from
   the backend would let it become a native, themeable, interactive React
   scatter. This is a small, isolated backend change — the only backend work
   worth considering; everything else stays backend-free.
2. Final parity sweep vs `src/frontend-legacy/` across all pages, then delete
   the legacy folder. The two newly rebuilt pages have been checked against
   their legacy counterparts; the folder is kept for now so a human can confirm
   whole-app parity before it's removed (it stays recoverable from git either
   way).

## Conventions

- Path alias `@/` → `src/frontend/src/`
- Match the surrounding code's comment density and naming; comments explain
  _why_, not _what_
- Keep `npm run lint` at zero warnings and `npm test` green before every commit
- Preserve the Django asset-manifest contract above in any build-config change

## Continuing in a new session

This chat does not transfer, but nothing important is lost:

- The full code history is on branch `claude/modern-frontend`
- Commit messages document each milestone's rationale
- This file is the map — start at "What's left"
