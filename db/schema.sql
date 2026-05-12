-- BurnRate SQLite schema — REFERENCE ONLY for Phase 2.
-- Created: 2026-05-06
--
-- Phase 1 uses JSON file storage (db/sessions.json, db/turns.json,
-- db/daily_totals.json, db/calibration.json) because SQLite cannot
-- write to Windows FUSE mounts in the Cowork sandbox. The JSON shapes
-- mirror the SQL columns below 1:1 — this file documents the eventual
-- Phase 2 storage when the API proxy ships and runs on a real Linux
-- box (Hetzner / DSI infra).

-- ----------------------------------------------------------------------
-- sessions: one row per Cowork session
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    session_id          TEXT PRIMARY KEY,           -- e.g. local_29c4997f-...
    title               TEXT,                        -- Cowork session title
    cwd                 TEXT,                        -- Working dir at session start
    project             TEXT,                        -- Inferred ZND project (cipher / jarvis / dsi / hub / gha / other)
    project_confidence  REAL,                        -- 0.0–1.0
    first_seen_ts       TEXT,                        -- ISO 8601, when we first ingested
    last_ingest_ts      TEXT,                        -- ISO 8601
    turn_count          INTEGER,                     -- Total turns observed
    is_active           INTEGER DEFAULT 0            -- 1 if session was active at last ingest
);

CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project);
CREATE INDEX IF NOT EXISTS idx_sessions_last_ingest ON sessions(last_ingest_ts);

-- ----------------------------------------------------------------------
-- turns: one row per turn in a session
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS turns (
    session_id          TEXT NOT NULL,
    turn_index          INTEGER NOT NULL,            -- 0-based
    turn_ts             TEXT,                        -- ISO 8601 if available; else NULL
    role                TEXT NOT NULL,               -- 'user' | 'assistant'

    -- visible character counts (exact)
    user_msg_chars      INTEGER DEFAULT 0,
    assistant_msg_chars INTEGER DEFAULT 0,

    -- tool calls observed in this turn
    tool_call_count     INTEGER DEFAULT 0,
    tool_calls_json     TEXT,                        -- JSON array of tool names

    -- token estimates (this turn alone)
    est_user_tokens         INTEGER DEFAULT 0,
    est_assistant_tokens    INTEGER DEFAULT 0,
    est_tool_io_tokens      INTEGER DEFAULT 0,
    est_turn_total_tokens   INTEGER DEFAULT 0,

    -- billed-at-turn estimate (cumulative input + this turn output)
    est_input_tokens_billed     INTEGER DEFAULT 0,
    est_output_tokens_billed    INTEGER DEFAULT 0,

    PRIMARY KEY (session_id, turn_index),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_turns_session ON turns(session_id);

-- ----------------------------------------------------------------------
-- daily_totals: aggregated per project per UTC date
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS daily_totals (
    date                TEXT NOT NULL,               -- YYYY-MM-DD UTC
    project             TEXT NOT NULL,
    sessions            INTEGER DEFAULT 0,
    turns               INTEGER DEFAULT 0,
    est_input_tokens    INTEGER DEFAULT 0,
    est_output_tokens   INTEGER DEFAULT 0,
    est_total_tokens    INTEGER DEFAULT 0,
    PRIMARY KEY (date, project)
);

-- ----------------------------------------------------------------------
-- calibration: actual Anthropic-reported totals per date
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS calibration (
    date                TEXT PRIMARY KEY,            -- YYYY-MM-DD UTC
    actual_total_tokens INTEGER NOT NULL,
    estimated_total_tokens INTEGER,
    correction_factor   REAL,                        -- actual / estimated
    note                TEXT,
    captured_ts         TEXT NOT NULL
);

-- ----------------------------------------------------------------------
-- meta: schema version + global config
-- ----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta (
    key                 TEXT PRIMARY KEY,
    value               TEXT
);

INSERT OR IGNORE INTO meta (key, value) VALUES
    ('schema_version', '1'),
    ('chars_per_token', '3.5'),
    ('system_prompt_est_tokens', '12000');
