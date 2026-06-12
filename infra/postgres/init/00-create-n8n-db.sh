#!/usr/bin/env bash
set -euo pipefail

N8N_DB_NAME="${N8N_DB_NAME:-n8n}"
N8N_DB_USER="${N8N_DB_USER:-n8n}"

if [ -z "${N8N_DB_PASSWORD:-}" ]; then
  echo "N8N_DB_PASSWORD is required to initialize the n8n database." >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v n8n_db="$N8N_DB_NAME" \
  -v n8n_user="$N8N_DB_USER" \
  -v n8n_password="$N8N_DB_PASSWORD" <<'EOSQL'
SELECT 'CREATE USER ' || quote_ident(:'n8n_user') || ' PASSWORD ' || quote_literal(:'n8n_password')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_roles
  WHERE rolname = :'n8n_user'
)\gexec

SELECT 'CREATE DATABASE ' || quote_ident(:'n8n_db') || ' OWNER ' || quote_ident(:'n8n_user')
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_database
  WHERE datname = :'n8n_db'
)\gexec

GRANT ALL PRIVILEGES ON DATABASE :"n8n_db" TO :"n8n_user";
EOSQL
