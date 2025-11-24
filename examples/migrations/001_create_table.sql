-- UP
-- Create quotes table with indexes for common lookups
-- This is the foundational schema for the quote-db plugin

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for author searches
CREATE INDEX IF NOT EXISTS idx_quotes_author ON quotes(author);

-- Index for chronological queries
CREATE INDEX IF NOT EXISTS idx_quotes_added_at ON quotes(added_at DESC);

-- Index for user attribution
CREATE INDEX IF NOT EXISTS idx_quotes_added_by ON quotes(added_by);

-- DOWN
-- Remove all quote-related structures

DROP INDEX IF EXISTS idx_quotes_added_by;
DROP INDEX IF EXISTS idx_quotes_added_at;
DROP INDEX IF EXISTS idx_quotes_author;
DROP TABLE IF EXISTS quotes;
