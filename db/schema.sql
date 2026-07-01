-- Sistem v1.0 — Postgres schema (Sprint 0)
-- Требуется: PostgreSQL 16 + расширение pgvector
--
-- Установить в /opt/sistem/db/init/01_schema.sql
-- Docker сам применит при первом старте контейнера db.

BEGIN;

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────────────────────────
-- USERS + AUTH
-- ─────────────────────────────────────────────────────────────

CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,           -- bcrypt
    display_name  TEXT,
    role          TEXT NOT NULL DEFAULT 'owner'
                       CHECK (role IN ('owner','admin','operator','viewer')),
    locale        TEXT DEFAULT 'ru',
    status        TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active','suspended','deleted')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX users_email_idx ON users (lower(email));

-- API tokens (для интеграций/CLI)
CREATE TABLE api_tokens (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    token_hash   TEXT NOT NULL,            -- sha256(token)
    scopes       TEXT[] NOT NULL DEFAULT '{}',
    last_used_at TIMESTAMPTZ,
    expires_at   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX api_tokens_user_idx ON api_tokens (user_id);
CREATE UNIQUE INDEX api_tokens_hash_idx ON api_tokens (token_hash);

-- ─────────────────────────────────────────────────────────────
-- PROJECT REGISTRY
-- ─────────────────────────────────────────────────────────────

CREATE TABLE projects (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug         TEXT NOT NULL,            -- project.id из пака
    name         TEXT NOT NULL,
    niche        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active'
                       CHECK (status IN ('active','paused','archived')),
    pack         JSONB NOT NULL,           -- полный Project Pack (секреты уже шифрованы AES-GCM)
    pack_version INT NOT NULL DEFAULT 1,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, slug)
);
CREATE INDEX projects_user_status_idx ON projects (user_id, status);
CREATE INDEX projects_niche_idx ON projects (niche);
CREATE INDEX projects_pack_gin ON projects USING GIN (pack jsonb_path_ops);

-- ─────────────────────────────────────────────────────────────
-- MEMORY LAYER (3 уровня)
-- ─────────────────────────────────────────────────────────────

-- Universal — про пользователя
CREATE TABLE memory_universal (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,               -- profile / preference / feedback / reference
    title      TEXT,
    body       TEXT NOT NULL,
    tags       TEXT[] NOT NULL DEFAULT '{}',
    embedding  vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_universal_user_idx ON memory_universal (user_id);
CREATE INDEX memory_universal_embedding_idx
    ON memory_universal USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Project-scoped
CREATE TABLE memory_project (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,               -- fact / event / note / result / insight
    title      TEXT,
    body       TEXT NOT NULL,
    tags       TEXT[] NOT NULL DEFAULT '{}',
    source     TEXT,                        -- skill/task/user
    embedding  vector(1536),
    active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_project_pid_idx ON memory_project (project_id, active);
CREATE INDEX memory_project_kind_idx ON memory_project (project_id, kind);
CREATE INDEX memory_project_embedding_idx
    ON memory_project USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Cross-project insights (batch-generated)
CREATE TABLE memory_insights (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    projects     UUID[] NOT NULL,           -- какие проекты сравнивались
    kind         TEXT NOT NULL,             -- pattern / opportunity / warning
    title        TEXT NOT NULL,
    body         TEXT NOT NULL,
    confidence   NUMERIC(3,2),              -- 0.00-1.00
    embedding    vector(1536),
    generated_by TEXT,                      -- имя job'а/скилла
    valid_until  TIMESTAMPTZ,               -- default: created_at + 90 days
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_insights_user_idx ON memory_insights (user_id);
CREATE INDEX memory_insights_valid_idx ON memory_insights (user_id, valid_until DESC);

-- ─────────────────────────────────────────────────────────────
-- SKILLS
-- ─────────────────────────────────────────────────────────────

CREATE TABLE skills (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT UNIQUE NOT NULL,      -- niche-content, lead-outreach, ...
    version      TEXT NOT NULL DEFAULT '1.0',
    description  TEXT,
    input_schema JSONB,                     -- JSON Schema параметров
    output_schema JSONB,
    handler      TEXT NOT NULL,             -- 'cowork:sistem-power-pack-universal:niche-content'
                                            -- или 'cc:bin/skills/lead-outreach'
    project_agnostic BOOLEAN NOT NULL DEFAULT TRUE,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────
-- TASKS + AUDIT
-- ─────────────────────────────────────────────────────────────

CREATE TABLE tasks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id   UUID REFERENCES projects(id) ON DELETE SET NULL,
    channel      TEXT NOT NULL,             -- cowork / dispatch / telegram / web / api
    input_text   TEXT NOT NULL,
    resolved_skill TEXT,
    resolved_params JSONB,
    bridge       TEXT,                      -- vps / cc / pc / n8n / null
    status       TEXT NOT NULL DEFAULT 'queued'
                       CHECK (status IN ('queued','running','done','failed','cancelled')),
    result       JSONB,
    error        TEXT,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX tasks_user_status_idx ON tasks (user_id, status, created_at DESC);
CREATE INDEX tasks_project_idx ON tasks (project_id, created_at DESC);

CREATE TABLE audit_log (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    task_id    UUID REFERENCES tasks(id) ON DELETE SET NULL,
    event      TEXT NOT NULL,               -- 'auth.login', 'bridge.vps.run', 'skill.invoke', ...
    payload    JSONB,
    ip         INET,
    ua         TEXT,
    ok         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_user_time_idx ON audit_log (user_id, created_at DESC);
CREATE INDEX audit_log_event_idx ON audit_log (event, created_at DESC);

-- ─────────────────────────────────────────────────────────────
-- BRIDGES (реестр таргетов)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE bridge_vps_hosts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    host          TEXT NOT NULL,             -- '152.53.231.15' | 'globria-vps'
    ssh_user      TEXT NOT NULL,
    ssh_key_ref   TEXT NOT NULL,             -- путь/имя в vault
    allow_cmds    TEXT[] NOT NULL DEFAULT '{}',
    enabled       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, host)
);

CREATE TABLE bridge_pcs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    pc_id          TEXT NOT NULL,             -- 'taras-desktop'
    tunnel_url     TEXT,
    public_key_pem TEXT,                      -- mTLS
    allow_cmds     TEXT[] NOT NULL DEFAULT '{}',
    last_seen_at   TIMESTAMPTZ,
    enabled        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, pc_id)
);

CREATE TABLE bridge_n8n_workflows (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_id  TEXT NOT NULL,               -- id внутри n8n
    name         TEXT NOT NULL,
    webhook_url  TEXT NOT NULL,
    description  TEXT,
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, workflow_id)
);

-- ─────────────────────────────────────────────────────────────
-- BILLING (SaaS-ready заглушки)
-- ─────────────────────────────────────────────────────────────

CREATE TABLE subscriptions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan              TEXT NOT NULL DEFAULT 'personal',
    status            TEXT NOT NULL DEFAULT 'active',
    stripe_customer   TEXT,
    stripe_sub_id     TEXT,
    current_period_end TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE billing_events (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID REFERENCES users(id) ON DELETE SET NULL,
    event      TEXT NOT NULL,
    payload    JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────────────────────
-- SEED (bootstrap Тарас)
-- ─────────────────────────────────────────────────────────────

INSERT INTO users (email, password_hash, display_name, role, locale)
VALUES ('sullenlar4@gmail.com', 'BOOTSTRAP_ME', 'Тарас', 'owner', 'ru')
ON CONFLICT (email) DO NOTHING;

INSERT INTO subscriptions (user_id, plan, status)
SELECT id, 'personal', 'active' FROM users WHERE email='sullenlar4@gmail.com'
ON CONFLICT (user_id) DO NOTHING;

COMMIT;
