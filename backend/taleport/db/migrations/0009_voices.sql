-- Tone-of-voice profiles: how posts should sound, learned from reference documents or
-- written by hand, optionally linked to topics (used by default for their themes).

CREATE TABLE voice_profiles (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    guide       TEXT NOT NULL DEFAULT '',   -- the voice described as instructions
    examples    TEXT NOT NULL DEFAULT '[]', -- JSON: short verbatim excerpts in that voice
    topic_ids   TEXT NOT NULL DEFAULT '[]', -- JSON: topics that use this voice by default
    sources     TEXT NOT NULL DEFAULT '[]', -- JSON: names of the reference documents
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
