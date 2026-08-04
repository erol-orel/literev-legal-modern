# LiteRev Legal — Frontend

A modern, lawyer-facing single-page application for LiteRev Legal, built to be a
**drop-in replacement** for the previous Create React App frontend: Django still
serves it through the same `generic.html` shell, and the **backend and
authentication are unchanged**.

## Stack

| Concern         | Choice                                             |
| --------------- | -------------------------------------------------- |
| Build tool      | Vite 5                                             |
| Language        | TypeScript (strict)                                |
| UI runtime      | React 18 + React Router 6                          |
| Styling         | Tailwind CSS 3 + CSS-variable design tokens        |
| Components      | shadcn/ui-style primitives on Radix UI             |
| Data fetching   | TanStack Query 5                                    |
| Tables          | TanStack Table 8                                    |
| Icons           | lucide-react                                        |
| Tests           | Vitest + Testing Library                            |

## How it integrates with Django

The build is configured to reproduce the exact layout the Django template tag
(`literev.templatetags.frontend.frontend_static`) expects — **no backend change
is required**:

- Output goes to `src/frontend/build/`.
- Assets are emitted under `build/static/js/` and `build/static/css/` with
  hashed filenames.
- A Create-React-App-compatible `build/asset-manifest.json` is written by a
  small Vite plugin (see `vite.config.ts`), mapping `main.js` / `main.css` to
  `/static/...` paths.
- `collectstatic` flattens `build/static/*` into Django's static root exactly as
  before.

The server → client handoff is unchanged: Django injects the bootstrap context
into `#context-data` and the CSRF token into `<meta name="csrf-token">`. These
are read by `src/lib/context.ts` and `src/lib/csrf.ts`.

## Commands

```bash
npm install        # install dependencies
npm run dev        # Vite dev server (proxies /api and /accounts to :8000)
npm run build      # typecheck + production build into build/
npm run lint       # ESLint
npm test           # Vitest
npm run test:coverage
```

`makim reactjs.install`, `makim reactjs.build`, and `makim django.collectstatic`
continue to work unchanged — they call `npm install` / `npm run build` here.

## Structure

```
src/
  app/            App root, router, and global providers
  api/            Typed API modules (one per backend domain)
  components/
    ui/           Design-system primitives (button, card, dialog, ...)
    layout/       App shell: sidebar, topbar, theme toggle, user menu
    auth/         Client-side auth guard mirroring Django login
    common/       Shared building blocks (page header, ...)
  hooks/          Theme, toast, and app-context hooks
  lib/            api-client, context, csrf, query client, utils
  pages/          Route pages
  test/           Vitest setup and tests
```

## Development against a running backend

Run Django on `:8000`, then `npm run dev`. The Vite dev server proxies `/api`,
`/accounts`, and `/status` to the backend. When no Django-injected context is
present, `getAppContext()` falls back to sensible defaults so the app still
renders.
