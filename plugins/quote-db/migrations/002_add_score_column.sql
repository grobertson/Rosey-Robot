-- Migration 002: Add score column for quote ratings
-- Purpose: Enable users to rate/score quotes
-- Version: 1.0
-- Created: 2025-11-24

-- UP
-- Add score column (default 0)
ALTER TABLE quotes ADD COLUMN score INTEGER DEFAULT 0 NOT NULL;

-- Data migration: Initialize scores based on text length
-- (Example pattern: longer quotes start with higher score)
-- In production, scores would start at 0 and be user-driven
UPDATE quotes SET score = LENGTH(text) / 10 WHERE score = 0;

-- Index for sorting by score
CREATE INDEX idx_quotes_score ON quotes(score DESC);

-- DOWN
-- SQLite doesn't support DROP COLUMN directly
-- Use table recreation pattern

-- Create temporary table without score column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Copy data (excluding score column)
INSERT INTO quotes_new (id, text, author, added_by, added_at)
SELECT id, text, author, added_by, added_at FROM quotes;

-- Drop indexes on old table
DROP INDEX IF EXISTS idx_quotes_score;
DROP INDEX IF EXISTS idx_quotes_author;

-- Replace old table with new
DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate author index
CREATE INDEX idx_quotes_author ON quotes(author);
