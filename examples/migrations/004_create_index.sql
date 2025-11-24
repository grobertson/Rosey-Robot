-- UP
-- Add composite index for efficient filtering by category and author
-- Useful for queries like "find all quotes by Alice in the 'humor' category"

CREATE INDEX IF NOT EXISTS idx_quotes_category_author ON quotes(category, author);

-- DOWN
-- Remove the composite index

DROP INDEX IF EXISTS idx_quotes_category_author;
