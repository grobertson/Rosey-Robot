-- UP
-- Remove deprecated 'updated_at' column using table recreation pattern
-- SQLite does not support DROP COLUMN, so we recreate the table

-- Step 1: Create new table without updated_at column
CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category TEXT DEFAULT ''
);

-- Step 2: Copy data from old table (excluding updated_at)
INSERT INTO quotes_new (id, text, author, added_by, added_at, category)
SELECT id, text, author, added_by, added_at, category FROM quotes;

-- Step 3: Drop old table
DROP TABLE quotes;

-- Step 4: Rename new table to original name
ALTER TABLE quotes_new RENAME TO quotes;

-- Step 5: Recreate all indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
CREATE INDEX idx_quotes_category ON quotes(category);

-- DOWN
-- Restore updated_at column (will be NULL for existing rows)

CREATE TABLE quotes_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,  -- Restored column, initially NULL
    category TEXT DEFAULT ''
);

-- Copy data back
INSERT INTO quotes_new (id, text, author, added_by, added_at, category)
SELECT id, text, author, added_by, added_at, category FROM quotes;

DROP TABLE quotes;
ALTER TABLE quotes_new RENAME TO quotes;

-- Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
CREATE INDEX idx_quotes_category ON quotes(category);
