#!/usr/bin/env bash


set -ex

if [[ "$ENV" != "dev" ]]; then
  # if in prod or staging environment: collectstatic and start wsgi
  python manage.py collectstatic --no-input
  gunicorn config.wsgi:application -w ${GUNICORN_WORKERS:-1} -b 0.0.0.0:${DJANGO_PORT:-8000}
else
  # if in dev environment: forget about uwsgi and
  # collectstatic, just run the Django dev server
  python manage.py runserver 0.0.0.0:${DJANGO_PORT:-8000}
fi

set +ex
