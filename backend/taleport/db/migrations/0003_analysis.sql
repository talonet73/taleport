-- Phase 3: statistical analysis (keyword stats, hot themes). Works without any AI.

-- Cached per-item analysis: extracted key phrases and hashtags (JSON lists of
-- normalized terms). NULL means "not analysed yet".
ALTER TABLE items ADD COLUMN terms TEXT;
ALTER TABLE items ADD COLUMN hashtags TEXT;

-- Daily document frequency: how many items of a topic mention a term,
-- per language and source. Feeds the Trends dashboard and PDF reports.
CREATE TABLE keyword_stats (
    topic_id INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    day      TEXT NOT NULL,  -- local date, YYYY-MM-DD
    kind     TEXT NOT NULL CHECK (kind IN ('keyword', 'hashtag')),
    term     TEXT NOT NULL,
    language TEXT NOT NULL,  -- it / en / es / '' when unknown
    source   TEXT NOT NULL,
    count    INTEGER NOT NULL,
    PRIMARY KEY (topic_id, day, kind, term, language, source)
);

CREATE INDEX idx_keyword_stats_term ON keyword_stats (topic_id, term, day);
CREATE INDEX idx_keyword_stats_day ON keyword_stats (day);

CREATE TABLE themes (
    id                     INTEGER PRIMARY KEY,
    topic_id               INTEGER NOT NULL REFERENCES topics (id) ON DELETE CASCADE,
    day                    TEXT NOT NULL,
    key                    TEXT NOT NULL,   -- normalized seed term
    title                  TEXT NOT NULL,
    summary                TEXT,            -- filled by the AI layer (phase 4)
    angle                  TEXT,            -- filled by the AI layer (phase 4)
    origin                 TEXT NOT NULL DEFAULT 'stats' CHECK (origin IN ('stats', 'ai')),
    score                  INTEGER NOT NULL,
    trend                  TEXT NOT NULL CHECK (trend IN ('up', 'down', 'flat', 'new')),
    score_details          TEXT NOT NULL DEFAULT '{}',  -- JSON components, shown as "why it's hot"
    item_count             INTEGER NOT NULL,
    source_count           INTEGER NOT NULL,
    representative_item_id INTEGER REFERENCES items (id) ON DELETE SET NULL,
    related_terms          TEXT NOT NULL DEFAULT '[]',  -- JSON
    questions              TEXT NOT NULL DEFAULT '[]',  -- JSON
    position               INTEGER NOT NULL DEFAULT 0,
    created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (topic_id, day, key)
);

CREATE INDEX idx_themes_topic_day ON themes (topic_id, day);

CREATE TABLE theme_items (
    theme_id INTEGER NOT NULL REFERENCES themes (id) ON DELETE CASCADE,
    item_id  INTEGER NOT NULL REFERENCES items (id) ON DELETE CASCADE,
    PRIMARY KEY (theme_id, item_id)
);
