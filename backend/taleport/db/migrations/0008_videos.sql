-- Phase 11: video analysis for clients (their videos and their competitors').

CREATE TABLE video_projects (
    id           INTEGER PRIMARY KEY,
    client_name  TEXT NOT NULL,
    notes        TEXT NOT NULL DEFAULT '',
    analysis     TEXT,                 -- JSON: validated AI analysis (VideoAnalysis)
    analysis_via TEXT,                 -- provider id or 'chat'
    analyzed_at  TEXT,
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE videos (
    id          INTEGER PRIMARY KEY,
    project_id  INTEGER NOT NULL REFERENCES video_projects(id) ON DELETE CASCADE,
    owner_kind  TEXT NOT NULL CHECK (owner_kind IN ('client', 'competitor')),
    owner_name  TEXT NOT NULL DEFAULT '',
    platform    TEXT NOT NULL DEFAULT 'other',
    file_name   TEXT NOT NULL,         -- name shown to the user
    stored_name TEXT NOT NULL,         -- file inside the project folder
    size        INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'queued'
                CHECK (status IN ('queued', 'processing', 'ready', 'failed')),
    step        TEXT,                  -- current processing step (shown while processing)
    error_code  TEXT,
    features    TEXT NOT NULL DEFAULT '{}',  -- JSON: offline measurements
    transcript  TEXT,                  -- JSON: [{start, end, text}]
    stats       TEXT NOT NULL DEFAULT '{}',  -- JSON: VideoStats
    stats_via   TEXT,                  -- 'manual', 'screenshot'
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_videos_project ON videos(project_id, owner_kind, owner_name);
