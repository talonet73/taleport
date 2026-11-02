-- Phase 4: AI usage log (feeds the monthly API spend counter).

CREATE TABLE ai_usage (
    id            INTEGER PRIMARY KEY,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    feature       TEXT NOT NULL,       -- e.g. theme_insights, topic_suggestion, x_search
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL,                -- NULL when the price of the model is unknown
    cost_source   TEXT NOT NULL CHECK (cost_source IN ('provider', 'estimate', 'free', 'unknown'))
);

CREATE INDEX idx_ai_usage_created ON ai_usage (created_at);
