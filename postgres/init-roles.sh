#!/usr/bin/env bash
set -euo pipefail

: "${POSTGRES_APP_USER:?POSTGRES_APP_USER is required}"
: "${POSTGRES_APP_PASSWORD:?POSTGRES_APP_PASSWORD is required}"

psql -v ON_ERROR_STOP=1 \
    -v app_user="$POSTGRES_APP_USER" \
    -v app_password="$POSTGRES_APP_PASSWORD" \
    --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-'EOSQL'
    SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
    WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'app_user')
    \gexec
    SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'app_user')
    \gexec
    SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'app_user')
    \gexec
    SELECT format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I', :'app_user')
    \gexec
    SELECT format('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I', :'app_user')
    \gexec
    SELECT format('ALTER ROLE %I SET row_security = on', :'app_user')
    \gexec
EOSQL
