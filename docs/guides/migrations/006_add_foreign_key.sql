-- UP
-- Add users table with foreign key constraint to track quote authors
-- Note: Foreign key must be defined at table creation time in SQLite

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create quotes_with_fk table with foreign key to users
-- We recreate the quotes table to add the constraint
CREATE TABLE quotes_with_fk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Copy existing data
INSERT INTO quotes_with_fk (id, text, author, added_by, added_at, category)
SELECT id, text, author, added_by, added_at, category FROM quotes;

-- Replace old table
DROP TABLE quotes;
ALTER TABLE quotes_with_fk RENAME TO quotes;

-- Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
CREATE INDEX idx_quotes_category ON quotes(category);
CREATE INDEX idx_quotes_category_author ON quotes(category, author);
CREATE INDEX idx_quotes_user_id ON quotes(user_id);

-- DOWN
-- Remove foreign key constraint and users table

-- Recreate quotes without foreign key
CREATE TABLE quotes_no_fk (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    category VARCHAR(50) NOT NULL DEFAULT 'general'
);

-- Copy data (excluding user_id)
INSERT INTO quotes_no_fk (id, text, author, added_by, added_at, category)
SELECT id, text, author, added_by, added_at, category FROM quotes;

DROP TABLE quotes;
ALTER TABLE quotes_no_fk RENAME TO quotes;

-- Recreate indexes
CREATE INDEX idx_quotes_author ON quotes(author);
CREATE INDEX idx_quotes_added_at ON quotes(added_at DESC);
CREATE INDEX idx_quotes_added_by ON quotes(added_by);
CREATE INDEX idx_quotes_category ON quotes(category);
CREATE INDEX idx_quotes_category_author ON quotes(category, author);

-- Drop users table
DROP TABLE IF EXISTS users;
