-- Sentinel schema v1
-- Applied by app/db.py::init_db(). All statements are idempotent.

PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS schema_version (
    version    INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orgs (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    org_id        TEXT NOT NULL REFERENCES orgs(id),
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'operator',
    totp_secret   TEXT,
    totp_enabled  INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id              TEXT PRIMARY KEY,
    org_id          TEXT NOT NULL REFERENCES orgs(id),
    label           TEXT NOT NULL,
    owner_name      TEXT NOT NULL,
    owner_email     TEXT,
    enroll_code     TEXT,
    enroll_expires  INTEGER,
    device_token    TEXT UNIQUE,
    platform        TEXT DEFAULT 'android',
    model           TEXT,
    os_version      TEXT,
    app_version     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    consent_at      INTEGER,
    consent_version TEXT,
    consent_ip      TEXT,
    consent_withdrawn_at INTEGER,
    last_seen       INTEGER,
    battery         INTEGER,
    created_at      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_devices_org ON devices(org_id);
CREATE INDEX IF NOT EXISTS idx_devices_token ON devices(device_token);

CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   TEXT NOT NULL REFERENCES devices(id),
    kind        TEXT NOT NULL,
    ts          INTEGER NOT NULL,
    received_at INTEGER NOT NULL,
    direction   TEXT,
    counterpart TEXT,
    body        TEXT,
    duration    INTEGER,
    lat         REAL,
    lon         REAL,
    accuracy    REAL,
    payload     TEXT,
    dedupe_key  TEXT NOT NULL,
    UNIQUE(device_id, dedupe_key)
);

CREATE INDEX IF NOT EXISTS idx_events_device_ts ON events(device_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);

CREATE TABLE IF NOT EXISTS audit_log (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id  TEXT,
    user_id TEXT,
    action  TEXT NOT NULL,
    target  TEXT,
    ip      TEXT,
    detail  TEXT,
    ts      INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    org_id     TEXT NOT NULL,
    device_id  TEXT NOT NULL,
    rule       TEXT NOT NULL,
    severity   TEXT NOT NULL DEFAULT 'info',
    message    TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    acked_at   INTEGER,
    acked_by   TEXT,
    dedupe_key TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_org ON alerts(org_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe ON alerts(device_id, dedupe_key)
    WHERE dedupe_key IS NOT NULL;

-- ---------------------------------------------------------------- geofencing
CREATE TABLE IF NOT EXISTS zones (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL,
    device_id    TEXT NOT NULL,
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL DEFAULT 'other',   -- home | school | other
    lat          REAL NOT NULL,
    lon          REAL NOT NULL,
    radius_m     INTEGER NOT NULL DEFAULT 200,
    notify_enter INTEGER NOT NULL DEFAULT 1,
    notify_exit  INTEGER NOT NULL DEFAULT 1,
    created_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_zones_device ON zones(device_id);

CREATE TABLE IF NOT EXISTS zone_state (
    zone_id    TEXT PRIMARY KEY REFERENCES zones(id) ON DELETE CASCADE,
    inside     INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL
);

-- ---------------------------------------------------------------- command channel
CREATE TABLE IF NOT EXISTS commands (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL,
    device_id    TEXT NOT NULL,
    kind         TEXT NOT NULL,             -- locate_now | ring | sync_now
    args         TEXT,
    status       TEXT NOT NULL DEFAULT 'pending', -- pending | delivered | acked | failed | expired
    created_by   TEXT,
    created_at   INTEGER NOT NULL,
    delivered_at INTEGER,
    acked_at     INTEGER,
    result       TEXT,
    expires_at   INTEGER
);

CREATE INDEX IF NOT EXISTS idx_commands_device ON commands(device_id, status);

-- ---------------------------------------------------------------- job queue
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    kind         TEXT NOT NULL,
    payload      TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',  -- queued | running | done | failed
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    run_after    INTEGER NOT NULL,
    locked_by    TEXT,
    locked_until INTEGER,
    last_error   TEXT,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, run_after);

-- ---------------------------------------------------------------- child policy
CREATE TABLE IF NOT EXISTS device_policy (
    device_id        TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    screen_time_start TEXT,                  -- "07:00"
    screen_time_end   TEXT,                  -- "21:30"
    blocked_apps     TEXT,                   -- JSON array of package names
    bedtime_notify   INTEGER NOT NULL DEFAULT 1,
    updated_at       INTEGER NOT NULL
);
