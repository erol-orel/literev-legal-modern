#!/usr/bin/env bash
#
# deploy_now.sh — redeploy the latest `main` onto an already-provisioned VM.
#
# Idempotent "pull & restart" for an instance stood up per
# docs/deployment-hetzner.md. Run it on the VM, from the repo root, inside the
# activated micromamba env (`micromamba activate literev-legal`). It fetches
# main, refreshes Python + frontend dependencies, applies migrations, rebuilds
# and collects the frontend assets, restarts the app + Celery, and waits for
# the health endpoint to answer.
#
# Usage:
#   ./scripts/deploy_now.sh                # full redeploy from origin/main
#   BRANCH=some-branch ./scripts/deploy_now.sh
#   ./scripts/deploy_now.sh --skip-deps    # skip dependency reinstall (fast)
#   ./scripts/deploy_now.sh --skip-build   # skip the frontend rebuild
#
set -euo pipefail

BRANCH="${BRANCH:-main}"
SKIP_DEPS=0
SKIP_BUILD=0
for arg in "$@"; do
  case "$arg" in
    --skip-deps) SKIP_DEPS=1 ;;
    --skip-build) SKIP_BUILD=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Repo root (this script lives in scripts/).
cd "$(cd "$(dirname "${BASH_SOURCE:-$0}")" && pwd)/.."

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$1"; }

if ! command -v makim >/dev/null 2>&1; then
  echo "makim not found — activate the env first: micromamba activate literev-legal" >&2
  exit 1
fi

step "Fetching origin/$BRANCH"
OLD_SHA="$(git rev-parse --short HEAD)"
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git merge --ff-only "origin/$BRANCH"
NEW_SHA="$(git rev-parse --short HEAD)"
if [ "$OLD_SHA" = "$NEW_SHA" ]; then
  echo "Already at $NEW_SHA — redeploying anyway to pick up any local rebuild."
else
  echo "Updated $OLD_SHA -> $NEW_SHA"
  git --no-pager log --oneline "$OLD_SHA..$NEW_SHA" | sed 's/^/    /'
fi

if [ "$SKIP_DEPS" -eq 0 ]; then
  step "Refreshing Python dependencies (install-dev.sh)"
  ./scripts/install-dev.sh
else
  echo "Skipping dependency reinstall (--skip-deps)."
fi

step "Applying database migrations"
makim django.migrate

if [ "$SKIP_BUILD" -eq 0 ]; then
  step "Installing + building the frontend, collecting static assets"
  makim reactjs.install
  makim reactjs.build
  makim django.collectstatic
else
  echo "Skipping frontend rebuild (--skip-build)."
fi

step "Restarting the app + Celery"
# Reloads the running containers so new backend code and settings take effect.
sugar compose-ext restart -- -d

step "Waiting for the health endpoint"
PORT="$(grep -E '^FRONTEND_HOST_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')"
PORT="${PORT:-8000}"
URL="http://localhost:${PORT}/status/"
for attempt in $(seq 1 20); do
  if curl -fsS "$URL" >/dev/null 2>&1; then
    printf '\n\033[1;32m✓ Deployed %s — %s is healthy.\033[0m\n' "$NEW_SHA" "$URL"
    exit 0
  fi
  sleep 3
done

echo "Health check did not pass at $URL after ~60s." >&2
echo "Inspect logs: sugar compose-ext logs -- --tail 100 literev" >&2
exit 1
