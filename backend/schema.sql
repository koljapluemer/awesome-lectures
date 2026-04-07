-- Anonymous user fingerprints (cookie UUID)
CREATE TABLE IF NOT EXISTS fingerprints (
  id         TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Per-day aggregated interaction counts
CREATE TABLE IF NOT EXISTS interaction_counts (
  slug       TEXT    NOT NULL,
  date       TEXT    NOT NULL,  -- YYYY-MM-DD
  likes      INTEGER NOT NULL DEFAULT 0,
  seen       INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (slug, date)
);

-- Dedup: one vote per fingerprint per action per lecture per day
CREATE TABLE IF NOT EXISTS votes (
  fingerprint_id TEXT NOT NULL REFERENCES fingerprints(id),
  slug           TEXT NOT NULL,
  action         TEXT NOT NULL CHECK(action IN ('like', 'seen')),
  date           TEXT NOT NULL,
  PRIMARY KEY (fingerprint_id, slug, action, date)
);

-- Future: user-suggested lectures
CREATE TABLE IF NOT EXISTS lecture_suggestions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  fingerprint_id TEXT    NOT NULL REFERENCES fingerprints(id),
  url            TEXT    NOT NULL,
  title          TEXT,
  note           TEXT,
  created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- User-suggested tag additions and removals for existing lectures
CREATE TABLE IF NOT EXISTS topic_suggestions (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  fingerprint_id TEXT    NOT NULL REFERENCES fingerprints(id),
  slug           TEXT    NOT NULL,
  topic          TEXT    NOT NULL,
  action         TEXT    NOT NULL DEFAULT 'add' CHECK(action IN ('add', 'remove')),
  created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
