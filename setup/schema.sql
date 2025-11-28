-- PULSE Analytics PostgreSQL schema
-- Longitudinal Analytics Store + Readiness Score

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Logical schemas
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS api;

-- ============================================================
-- analytics.session_events
-- Per-user / per-session / per-skill time-series events
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.session_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    api_id bigserial UNIQUE,

    user_id uuid,
    session_id uuid NOT NULL,

    occurred_at timestamptz NOT NULL DEFAULT now(),
    scenario_id text,
    pulse_step text NOT NULL,
    skill_tag text NOT NULL,
    score numeric(5,2) NOT NULL,

    raw_metrics jsonb,
    notes text,

    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_session_events_user_id
    ON analytics.session_events (user_id);

CREATE INDEX IF NOT EXISTS idx_session_events_session_id
    ON analytics.session_events (session_id);

CREATE INDEX IF NOT EXISTS idx_session_events_skill_tag
    ON analytics.session_events (skill_tag);

CREATE INDEX IF NOT EXISTS idx_session_events_occurred_at
    ON analytics.session_events (occurred_at);

-- ============================================================
-- analytics.user_skill_agg
-- Rolling aggregates per user & skill, for named windows
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.user_skill_agg (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    api_id bigserial UNIQUE,

    user_id uuid NOT NULL,
    skill_tag text NOT NULL,
    window text NOT NULL,

    avg_score numeric(5,2) NOT NULL,
    sample_size integer NOT NULL,

    last_updated timestamptz NOT NULL DEFAULT now(),
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_user_skill_window UNIQUE (user_id, skill_tag, window)
);

CREATE INDEX IF NOT EXISTS idx_user_skill_agg_user
    ON analytics.user_skill_agg (user_id);

CREATE INDEX IF NOT EXISTS idx_user_skill_agg_skill
    ON analytics.user_skill_agg (skill_tag);

-- ============================================================
-- analytics.user_readiness
-- Readiness snapshots over time (0–100 composite + components)
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.user_readiness (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    api_id bigserial UNIQUE,

    user_id uuid NOT NULL,
    snapshot_at timestamptz NOT NULL DEFAULT now(),

    readiness_overall numeric(5,2) NOT NULL,
    readiness_technical numeric(5,2),
    readiness_communication numeric(5,2),
    readiness_structure numeric(5,2),
    readiness_behavioral numeric(5,2),

    meta jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_readiness_user
    ON analytics.user_readiness (user_id);

CREATE INDEX IF NOT EXISTS idx_user_readiness_snapshot
    ON analytics.user_readiness (snapshot_at);

-- ============================================================
-- API-facing views for PostgREST
-- Expose numeric api_id as id, include UUID as uuid
-- ============================================================

CREATE OR REPLACE VIEW api.session_events AS
SELECT
    api_id AS id,
    id     AS uuid,
    user_id,
    session_id,
    occurred_at,
    scenario_id,
    pulse_step,
    skill_tag,
    score,
    raw_metrics,
    notes,
    created_at
FROM analytics.session_events;

CREATE OR REPLACE VIEW api.user_skill_agg AS
SELECT
    api_id AS id,
    id     AS uuid,
    user_id,
    skill_tag,
    window,
    avg_score,
    sample_size,
    last_updated,
    created_at
FROM analytics.user_skill_agg;

CREATE OR REPLACE VIEW api.user_readiness AS
SELECT
    api_id AS id,
    id     AS uuid,
    user_id,
    snapshot_at,
    readiness_overall,
    readiness_technical,
    readiness_communication,
    readiness_structure,
    readiness_behavioral,
    meta,
    created_at
FROM analytics.user_readiness;
