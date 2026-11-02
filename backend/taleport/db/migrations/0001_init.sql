-- Base schema: app settings and the user-visible error/event log.
-- Domain tables (topics, items, themes, drafts, ...) are added by later migrations,
-- one per development phase.

CREATE TABLE settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,  -- JSON-encoded
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE logs (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    level      TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error')),
    source     TEXT NOT NULL,  -- e.g. 'scan', 'collector.youtube', 'ai.ollama'
    code       TEXT NOT NULL,  -- i18n key under errors. / log.
    params     TEXT,           -- JSON
    details    TEXT            -- technical details, shown only in the exported log
);

CREATE INDEX idx_logs_created_at ON logs (created_at);
