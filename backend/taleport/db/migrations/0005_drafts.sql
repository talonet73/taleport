-- Phase 5: post drafts and publications.

CREATE TABLE drafts (
    id             INTEGER PRIMARY KEY,
    batch_id       TEXT NOT NULL,                     -- one generation request
    topic_id       INTEGER REFERENCES topics (id) ON DELETE SET NULL,
    theme_id       INTEGER REFERENCES themes (id) ON DELETE SET NULL,
    theme_key      TEXT,                              -- kept to detect "already covered" across days
    theme_title    TEXT,
    origin         TEXT NOT NULL CHECK (origin IN ('theme', 'long_content')),
    source_label   TEXT NOT NULL DEFAULT '',          -- theme title or long-content title
    platform       TEXT NOT NULL CHECK (platform IN ('linkedin', 'instagram', 'facebook', 'youtube', 'tiktok')),
    language       TEXT NOT NULL CHECK (language IN ('it', 'en', 'es')),
    variant        INTEGER NOT NULL DEFAULT 1,
    series_index   INTEGER,                           -- position in a long-content series
    content        TEXT NOT NULL DEFAULT '{}',        -- structured post (JSON)
    text           TEXT NOT NULL,                     -- full text to copy (editable)
    edited         INTEGER NOT NULL DEFAULT 0,
    sources        TEXT NOT NULL DEFAULT '[]',        -- JSON [{title, url}]
    fact_warnings  TEXT NOT NULL DEFAULT '[]',        -- JSON [{kind, value}]
    image_idea     TEXT NOT NULL DEFAULT '',
    image_prompt   TEXT NOT NULL DEFAULT '',
    context        TEXT NOT NULL DEFAULT '{}',        -- sources snapshot: regenerate + fact-check later
    status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'published')),
    scheduled_at   TEXT,                              -- local date-time, read by the calendar (phase 7)
    ai_mode        TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_drafts_created ON drafts (created_at);
CREATE INDEX idx_drafts_topic ON drafts (topic_id, status);

CREATE TABLE publications (
    id           INTEGER PRIMARY KEY,
    draft_id     INTEGER NOT NULL REFERENCES drafts (id) ON DELETE CASCADE,
    platform     TEXT NOT NULL,
    published_at TEXT NOT NULL,
    url          TEXT
);

CREATE INDEX idx_publications_date ON publications (published_at);
