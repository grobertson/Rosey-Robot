-- UP
-- Add category column to allow organizing quotes by topic
-- Default to empty string for existing rows

ALTER TABLE quotes ADD COLUMN category TEXT DEFAULT '';

-- Add index for category filtering
CREATE INDEX IF NOT EXISTS idx_quotes_category ON quotes(category);

-- DOWN
-- SQLite does not support DROP COLUMN directly
-- This rollback uses table recreation pattern

-- Create new table without category column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Copy data (excluding category column)
INSERT INTO quotes_new (id, text, author, added_by, added_at, updated_at)
SELECT id, text, author, added_by, added_at, updated_at FROM quotes;

-- Replace old table
DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate original indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
