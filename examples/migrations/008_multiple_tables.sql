-- UP
-- Create multiple related tables for quote collections and tags
-- Demonstrates creating a complete feature with normalized relationships

-- Collections: User-created quote collections
CREATE TABLE IF NOT EXISTS quote_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_public BOOLEAN DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_collections_created_by ON quote_collections(created_by);
CREATE INDEX IF NOT EXISTS idx_collections_public ON quote_collections(is_public);

-- Collection memberships: Many-to-many relationship
CREATE TABLE IF NOT EXISTS quote_collection_items (
    collection_id INTEGER NOT NULL,
    quote_id INTEGER NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    display_order INTEGER DEFAULT 0,
    PRIMARY KEY (collection_id, quote_id),
    FOREIGN KEY (collection_id) REFERENCES quote_collections(id) ON DELETE CASCADE,
    FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_collection_items_quote ON quote_collection_items(quote_id);

-- Tags: Flexible labeling system
CREATE TABLE IF NOT EXISTS quote_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tags_name ON quote_tags(tag_name);

-- Quote-tag relationships: Many-to-many
CREATE TABLE IF NOT EXISTS quote_tag_assignments (
    quote_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (quote_id, tag_id),
    FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES quote_tags(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tag_assignments_tag ON quote_tag_assignments(tag_id);

-- DOWN
-- Remove all collection and tag tables in reverse dependency order

DROP INDEX IF EXISTS idx_tag_assignments_tag;
DROP TABLE IF EXISTS quote_tag_assignments;

DROP INDEX IF EXISTS idx_tags_name;
DROP TABLE IF EXISTS quote_tags;

DROP INDEX IF EXISTS idx_collection_items_quote;
DROP TABLE IF EXISTS quote_collection_items;

DROP INDEX IF EXISTS idx_collections_public;
DROP INDEX IF EXISTS idx_collections_created_by;
DROP TABLE IF EXISTS quote_collections;
