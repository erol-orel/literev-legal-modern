# Frontend

This folder is the new React frontend root.

For now it is only a minimal scaffold so the repository is split into `src/frontend` and `src/backend` like the main LiteRev repository. The current user-facing pages are still served by Django templates from `src/backend` until the SPA migration is completed.

## Commands

```bash
makim reactjs.install
makim tests.reactjs
makim reactjs.build
makim django.collectstatic
```

`makim tests.reactjs` now pre-runs `reactjs.install` plus `reactjs.build`, then runs the frontend unit suite with coverage output. Coverage artifacts are written under `src/frontend/coverage/`, and GitHub Actions formats the frontend coverage section with `scripts/render_frontend_coverage_summary.py`. `makim django.collectstatic` follows the same approach before collecting Django static assets.


Frontend test files live under `src/frontend/tests/`. A small bootstrap file remains under `src/frontend/src/tests.entry.test.js` so `react-scripts test` can discover and run them.
