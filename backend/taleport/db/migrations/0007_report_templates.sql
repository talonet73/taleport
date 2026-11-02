-- Phase 8: saved custom report templates ("regenerate with one click").

CREATE TABLE report_templates (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    params      TEXT NOT NULL,                -- JSON: topics, period, languages, sections, theme
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_run_at TEXT
);
