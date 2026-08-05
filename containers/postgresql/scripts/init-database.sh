#!/bin/bash
# Initialise the application database and role from environment variables.
#
# Runs once, on first cluster init, from the postgres image's
# /docker-entrypoint-initdb.d hook. The credentials are read from the
# environment (provided by the container's env_file / compose env) so no
# password is ever hardcoded in source control.
set -euo pipefail

DB_NAME="${POSTGRES_DB_LITEREV:-literev}"
DB_USER="${POSTGRES_USER_LITEREV:-literev}"
# Fail loudly if the password was not provided rather than creating a role
# with an empty/guessable password.
DB_PASSWORD="${POSTGRES_PASSWORD_LITEREV:?POSTGRES_PASSWORD_LITEREV must be set}"

psql -v ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER}" \
  --dbname "${POSTGRES_DB}" <<-EOSQL
    CREATE DATABASE ${DB_NAME};
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';
    ALTER ROLE ${DB_USER} SET client_encoding TO 'utf8';
    ALTER ROLE ${DB_USER} SET default_transaction_isolation TO 'read committed';
    ALTER ROLE ${DB_USER} SET timezone TO 'UTC';
    GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
    ALTER SYSTEM SET listen_addresses TO '*';
    ALTER USER ${DB_USER} CREATEDB;
EOSQL
