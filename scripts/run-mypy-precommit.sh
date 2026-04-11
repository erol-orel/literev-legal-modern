#!/usr/bin/env bash
set -uo pipefail

export SIGNUP_SECRET_CODE="${SIGNUP_SECRET_CODE:-pre-commit-signup-secret}"
export PYTHONUNBUFFERED=1

python -m mypy . "$@"
status=$?

if [[ "$status" -eq 137 ]]; then
  echo "mypy was killed (exit 137 / SIGKILL). This usually means the OS OOM-killed the hook." >&2
fi

exit "$status"
