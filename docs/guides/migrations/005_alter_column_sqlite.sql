-- UP
-- Change 'category' column type from TEXT to VARCHAR(50) with NOT NULL constraint
-- SQLite does not support ALTER COLUMN, so use table recreation pattern

-- Step 1: Create new table with modified column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(50) NOT NULL DEFAULT 'general'  -- Modified column
);

-- Step 2: Copy data with type conversion
INSERT INTO quotes_new (id, text, author, added_by, added_at, category)
SELECT 
    id, 
    text, 
    author, 
    added_by, 
    added_at, 
    COALESCE(NULLIF(category, ''), 'general')  -- Convert empty to 'general'
FROM quotes;

-- Step 3: Replace old table
DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Step 4: Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
CREATE INDEX idx_quotes_category ON quotes(category);
CREATE INDEX idx_quotes_category_author ON quotes(category, author);

-- DOWN
-- Revert to original column type (TEXT with DEFAULT '')

CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category TEXT DEFAULT ''  -- Original column type
);

INSERT INTO quotes_new (id, text, author, added_by, added_at, category)
SELECT id, text, author, added_by, added_at, category FROM quotes;

DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
CREATE INDEX idx_quotes_category ON quotes(category);
CREATE INDEX idx_quotes_category_author ON quotes(category, author);
