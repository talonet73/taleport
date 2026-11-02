-- Phase 2: topics, scans and collected items.

CREATE TABLE topics (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1,
    editions    TEXT NOT NULL DEFAULT '[]',  -- JSON list of edition codes, e.g. ["it-IT", "en-US"]
    audience    TEXT NOT NULL DEFAULT '',
    tone        TEXT NOT NULL DEFAULT '',
    platforms   TEXT NOT NULL DEFAULT '[]',  -- JSON list: linkedin, instagram, facebook, youtube, tiktok
    position    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- include: per language (it/en/es); exclude and hashtag: language 'any'.
CREATE TABLE topic_keywords (
    id       INTEGER PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    kind     TEXT NOT NULL CHECK (kind IN ('include', 'exclude', 'hashtag')),
    language TEXT NOT NULL CHECK (language IN ('it', 'en', 'es', 'any')),
    value    TEXT NOT NULL,
    UNIQUE (topic_id, kind, language, value)
);

-- "Watched" sources, always followed regardless of keywords.
CREATE TABLE topic_sources (
    id       INTEGER PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    kind     TEXT NOT NULL CHECK (kind IN ('rss', 'youtube_channel', 'subreddit')),
    value    TEXT NOT NULL,
    resolved TEXT,  -- cached lookup, e.g. a channel's uploads playlist id
    UNIQUE (topic_id, kind, value)
);

CREATE TABLE style_examples (
    id       INTEGER PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    text     TEXT NOT NULL
);

CREATE TABLE scans (
    id          INTEGER PRIMARY KEY,
    trigger     TEXT NOT NULL CHECK (trigger IN ('manual', 'scheduled', 'catchup')),
    topic_id    INTEGER REFERENCES topics (id) ON DELETE SET NULL,  -- NULL: all active topics
    status      TEXT NOT NULL CHECK (status IN ('running', 'completed', 'partial', 'failed', 'cancelled')),
    started_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    finished_at TEXT,
    items_found INTEGER NOT NULL DEFAULT 0,
    items_new   INTEGER NOT NULL DEFAULT 0,
    errors      INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_scans_started_at ON scans (started_at);

-- Only metadata and short excerpts are stored, never full article text.
CREATE TABLE items (
    id            INTEGER PRIMARY KEY,
    source        TEXT NOT NULL CHECK (source IN ('news', 'rss', 'youtube', 'reddit', 'trends', 'x_grok')),
    url           TEXT NOT NULL,
    canonical_url TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    title_key     TEXT NOT NULL,  -- normalized title for near-duplicate detection
    excerpt       TEXT NOT NULL DEFAULT '',
    language      TEXT,
    publisher     TEXT NOT NULL DEFAULT '',
    published_at  TEXT,
    metrics       TEXT NOT NULL DEFAULT '{}',  -- JSON, e.g. views/likes/comments/score
    extra         TEXT NOT NULL DEFAULT '{}',  -- JSON, e.g. {"comments": [...]} (text only, no user names)
    first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    last_seen_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_items_title_key ON items (title_key);
CREATE INDEX idx_items_first_seen ON items (first_seen_at);

CREATE TABLE item_topics (
    item_id  INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    scan_id  INTEGER REFERENCES scans (id) ON DELETE SET NULL,
    linked_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (item_id, topic_id)
);

CREATE INDEX idx_item_topics_topic ON item_topics (topic_id, linked_at);

-- Daily usage of quota-limited APIs (YouTube). `day` follows the provider's reset clock.
CREATE TABLE api_quota (
    service TEXT NOT NULL,
    day     TEXT NOT NULL,
    units   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (service, day)
);
