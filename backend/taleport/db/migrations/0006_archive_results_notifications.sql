-- Phase 7: post results, notifications, full-text search for the archive.

CREATE TABLE post_results (
    draft_id   INTEGER PRIMARY KEY REFERENCES drafts (id) ON DELETE CASCADE,
    likes      INTEGER CHECK (likes >= 0),
    comments   INTEGER CHECK (comments >= 0),
    shares     INTEGER CHECK (shares >= 0),
    views      INTEGER CHECK (views >= 0),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    kind       TEXT NOT NULL,             -- spike, scan_completed, scan_recovered, ...
    params     TEXT NOT NULL DEFAULT '{}',
    link       TEXT,                      -- in-app route opened from the bell
    dedupe_key TEXT UNIQUE,               -- e.g. "spike:3:2026-11-02": at most one per key
    read       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_notifications_created ON notifications (created_at);

-- Archive search: external-content FTS5 tables kept in sync by triggers.

CREATE VIRTUAL TABLE drafts_fts USING fts5 (
    text, source_label, theme_title,
    content = 'drafts', content_rowid = 'id', tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER drafts_fts_ai AFTER INSERT ON drafts BEGIN
    INSERT INTO drafts_fts (rowid, text, source_label, theme_title)
    VALUES (new.id, new.text, new.source_label, new.theme_title);
END;

CREATE TRIGGER drafts_fts_ad AFTER DELETE ON drafts BEGIN
    INSERT INTO drafts_fts (drafts_fts, rowid, text, source_label, theme_title)
    VALUES ('delete', old.id, old.text, old.source_label, old.theme_title);
END;

CREATE TRIGGER drafts_fts_au AFTER UPDATE OF text, source_label, theme_title ON drafts BEGIN
    INSERT INTO drafts_fts (drafts_fts, rowid, text, source_label, theme_title)
    VALUES ('delete', old.id, old.text, old.source_label, old.theme_title);
    INSERT INTO drafts_fts (rowid, text, source_label, theme_title)
    VALUES (new.id, new.text, new.source_label, new.theme_title);
END;

INSERT INTO drafts_fts (drafts_fts) VALUES ('rebuild');

CREATE VIRTUAL TABLE themes_fts USING fts5 (
    title, summary, angle,
    content = 'themes', content_rowid = 'id', tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER themes_fts_ai AFTER INSERT ON themes BEGIN
    INSERT INTO themes_fts (rowid, title, summary, angle)
    VALUES (new.id, new.title, new.summary, new.angle);
END;

CREATE TRIGGER themes_fts_ad AFTER DELETE ON themes BEGIN
    INSERT INTO themes_fts (themes_fts, rowid, title, summary, angle)
    VALUES ('delete', old.id, old.title, old.summary, old.angle);
END;

CREATE TRIGGER themes_fts_au AFTER UPDATE OF title, summary, angle ON themes BEGIN
    INSERT INTO themes_fts (themes_fts, rowid, title, summary, angle)
    VALUES ('delete', old.id, old.title, old.summary, old.angle);
    INSERT INTO themes_fts (rowid, title, summary, angle)
    VALUES (new.id, new.title, new.summary, new.angle);
END;

INSERT INTO themes_fts (themes_fts) VALUES ('rebuild');
