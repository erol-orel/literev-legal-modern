#!/usr/bin/env bash
set -ex
poetry config virtualenvs.create false

if [[ "$ENV" == "prod" ]]; then
  poetry install --no-root --only main
else
  poetry install --no-root
fi
set +ex
