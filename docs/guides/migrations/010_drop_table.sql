-- UP
-- Drop deprecated quote_collection_items table
-- Collections feature being replaced with simpler tagging system
-- WARNING: This will delete all collection data

-- Step 1: Drop foreign key indexes
DROP INDEX IF EXISTS idx_collection_items_quote;

-- Step 2: Drop the table (CASCADE will fail in SQLite, handle manually)
DROP TABLE IF EXISTS quote_collection_items;

-- Step 3: Also drop the collections table since items are gone
DROP INDEX IF EXISTS idx_collections_public;
DROP INDEX IF EXISTS idx_collections_created_by;
DROP TABLE IF EXISTS quote_collections;

-- DOWN
-- Restore collections tables (data cannot be recovered)

CREATE TABLE quote_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_public BOOLEAN DEFAULT 0
);

CREATE INDEX idx_collections_created_by ON quote_collections(created_by);
CREATE INDEX idx_collections_public ON quote_collections(is_public);

CREATE TABLE quote_collection_items (
    collection_id INTEGER NOT NULL,
    quote_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    display_order INTEGER DEFAULT 0,
    PRIMARY KEY (collection_id, quote_id),
    FOREIGN KEY (collection_id) REFERENCES quote_collections(id) ON DELETE CASCADE,
    FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE
);

CREATE INDEX idx_collection_items_quote ON quote_collection_items(quote_id);

-- Note: Original data cannot be restored by this rollback
-- Backup database before applying migration 010 if data recovery is needed
