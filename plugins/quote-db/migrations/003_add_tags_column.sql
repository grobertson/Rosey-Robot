-- Migration 003: Add tags column for categorization
-- Purpose: Enable tagging quotes with categories (motivational, funny, wisdom, etc.)
-- Version: 1.0
-- Created: 2025-11-24

-- UP
-- Add tags column (JSON array)
ALTER TABLE quotes ADD COLUMN tags TEXT DEFAULT '[]' NOT NULL;

-- Example: Add tags to seed quotes
UPDATE quotes SET tags = '["motivational", "work"]' WHERE author = 'Steve Jobs';
UPDATE quotes SET tags = '["wisdom", "opportunity"]' WHERE author = 'Albert Einstein';
UPDATE quotes SET tags = '["life", "philosophy"]' WHERE author = 'John Lennon';
UPDATE quotes SET tags = '["dreams", "motivation"]' WHERE author = 'Eleanor Roosevelt';
UPDATE quotes SET tags = '["wisdom", "adversity"]' WHERE author = 'Aristotle';

-- DOWN
-- SQLite doesn't support DROP COLUMN directly
-- Use table recreation pattern

-- Create temporary table without tags column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    score INTEGER DEFAULT 0 NOT NULL
);

-- Copy data (excluding tags column)
INSERT INTO quotes_new (id, text, author, added_by, added_at, score)
SELECT id, text, author, added_by, added_at, score FROM quotes;

-- Drop indexes
DROP INDEX IF EXISTS idx_quotes_score;
DROP INDEX IF EXISTS idx_quotes_author;

-- Replace old table
DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_score ON quotes(score DESC);
