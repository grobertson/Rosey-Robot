-- UP
-- Complex transformation: Add full-text search support and audit tracking
-- This demonstrates a multi-step migration with data preservation

-- Step 1: Enable full-text search for quotes
-- Create FTS5 virtual table for quote text searching
CREATE VIRTUAL TABLE IF NOT EXISTS quotes_fts USING fts5(
    quote_id UNINDEXED,
    text,
    author,
    category,
    content='quotes',
    content_rowid='id'
);

-- Populate FTS table with existing quotes
INSERT INTO quotes_fts(quote_id, text, author, category)
SELECT id, text, COALESCE(author, ''), category FROM quotes;

-- Create trigger to keep FTS in sync with quotes table
CREATE TRIGGER IF NOT EXISTS quotes_fts_insert AFTER INSERT ON quotes BEGIN
    INSERT INTO quotes_fts(quote_id, text, author, category)
    VALUES (NEW.id, NEW.text, COALESCE(NEW.author, ''), NEW.category);
END;

CREATE TRIGGER IF NOT EXISTS quotes_fts_update AFTER UPDATE ON quotes BEGIN
    DELETE FROM quotes_fts WHERE quote_id = OLD.id;
    INSERT INTO quotes_fts(quote_id, text, author, category)
    VALUES (NEW.id, NEW.text, COALESCE(NEW.author, ''), NEW.category);
END;

CREATE TRIGGER IF NOT EXISTS quotes_fts_delete AFTER DELETE ON quotes BEGIN
    DELETE FROM quotes_fts WHERE quote_id = OLD.id;
END;

-- Step 2: Add audit log table for tracking quote modifications
CREATE TABLE IF NOT EXISTS quote_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL,
    action TEXT NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
    old_text TEXT,
    new_text TEXT,
    old_author TEXT,
    new_author TEXT,
    old_category TEXT,
    new_category TEXT,
    modified_by TEXT NOT NULL,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (quote_id) REFERENCES quotes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_audit_quote ON quote_audit_log(quote_id);
CREATE INDEX IF NOT EXISTS idx_audit_date ON quote_audit_log(modified_at DESC);

-- Create audit triggers
CREATE TRIGGER IF NOT EXISTS quotes_audit_update AFTER UPDATE ON quotes BEGIN
    INSERT INTO quote_audit_log(
        quote_id, action, 
        old_text, new_text,
        old_author, new_author,
        old_category, new_category,
        modified_by
    ) VALUES (
        NEW.id, 'UPDATE',
        OLD.text, NEW.text,
        OLD.author, NEW.author,
        OLD.category, NEW.category,
        NEW.added_by  -- Using added_by as modifier (would be improved with session tracking)
    );
END;

CREATE TRIGGER IF NOT EXISTS quotes_audit_delete BEFORE DELETE ON quotes BEGIN
    INSERT INTO quote_audit_log(
        quote_id, action,
        old_text, old_author, old_category,
        modified_by
    ) VALUES (
        OLD.id, 'DELETE',
        OLD.text, OLD.author, OLD.category,
        'system'
    );
END;

-- DOWN
-- Remove full-text search and audit tracking
-- This is a complex rollback that removes multiple features

-- Remove audit triggers
DROP TRIGGER IF EXISTS quotes_audit_delete;
DROP TRIGGER IF EXISTS quotes_audit_update;

-- Remove audit table
DROP INDEX IF EXISTS idx_audit_date;
DROP INDEX IF EXISTS idx_audit_quote;
DROP TABLE IF EXISTS quote_audit_log;

-- Remove FTS triggers
DROP TRIGGER IF EXISTS quotes_fts_delete;
DROP TRIGGER IF EXISTS quotes_fts_update;
DROP TRIGGER IF EXISTS quotes_fts_insert;

-- Remove FTS table
DROP TABLE IF EXISTS quotes_fts;
