-- Migration: remove 'seen' tracking from votes and interaction_counts
-- Run once against the existing database.

-- Recreate votes table without 'seen' action
ALTER TABLE votes RENAME TO votes_old;
CREATE TABLE votes (
  fingerprint_id TEXT NOT NULL REFERENCES fingerprints(id),
  slug           TEXT NOT NULL,
  action         TEXT NOT NULL CHECK(action IN ('like')),
  date           TEXT NOT NULL,
  PRIMARY KEY (fingerprint_id, slug, action, date)
);
INSERT INTO votes SELECT fingerprint_id, slug, action, date FROM votes_old WHERE action = 'like';
DROP TABLE votes_old;

-- Drop seen column from interaction_counts (requires SQLite 3.35+)
ALTER TABLE interaction_counts DROP COLUMN seen;
