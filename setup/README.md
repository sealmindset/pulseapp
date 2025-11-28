# PULSE Analytics PostgreSQL Schema

This directory contains the canonical DDL for the **Longitudinal Analytics Store**
and **Readiness Score** backing the PULSE app.

## Files

- `schema.sql`
  - Creates the `analytics` and `api` schemas.
  - Defines core tables:
    - `analytics.session_events`
    - `analytics.user_skill_agg`
    - `analytics.user_readiness`
  - Adds `api.*` views that expose `api_id` as the external `id` column for
    PostgREST while keeping `uuid` as the internal primary key.

## Applying the schema

For a **new** analytics database (no existing data), you can apply the schema
from your local machine using `psql`.

1. Ensure the `pulse_analytics` database exists. Terraform provisions this via
   the `analytics_postgres` module.
2. Build a connection string using the analytics env vars exposed to the
   Function App / Web App, for example:

   ```bash
   export PULSE_ANALYTICS_DB_HOST="<server>.postgres.database.azure.com"
   export PULSE_ANALYTICS_DB_NAME="pulse_analytics"
   export PULSE_ANALYTICS_DB_USER="<admin-or-app-user>"
   export PULSE_ANALYTICS_DB_PASSWORD="<password>"

   psql "postgres://$PULSE_ANALYTICS_DB_USER:$PULSE_ANALYTICS_DB_PASSWORD@$PULSE_ANALYTICS_DB_HOST:5432/$PULSE_ANALYTICS_DB_NAME" \
     -f setup/schema.sql
   ```

For **existing** databases with data, treat changes to this schema as
migrations:

- Take a backup before applying breaking changes.
- Prefer incremental SQL migration files under `setup/migrations/` that
  evolve the schema while keeping `schema.sql` in sync with the current
  desired state.
