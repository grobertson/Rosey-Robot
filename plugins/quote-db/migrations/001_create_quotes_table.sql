-- Migration 001: Create quotes table with initial schema
-- Purpose: Establish base table structure for quote storage
-- Version: 1.0
-- Created: 2025-11-24

-- UP
CREATE TABLE quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    author TEXT,
    added_by TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Index for searching by author
CREATE INDEX idx_quotes_author ON quotes(author);

-- Seed data: Example quotes for development and testing
INSERT INTO quotes (text, author, added_by, added_at) VALUES
('The only way to do great work is to love what you do.', 'Steve Jobs', 'system', CURRENT_TIMESTAMP),
('In the middle of difficulty lies opportunity.', 'Albert Einstein', 'system', CURRENT_TIMESTAMP),
('Life is what happens when you''re busy making other plans.', 'John Lennon', 'system', CURRENT_TIMESTAMP),
('The future belongs to those who believe in the beauty of their dreams.', 'Eleanor Roosevelt', 'system', CURRENT_TIMESTAMP),
('It is during our darkest moments that we must focus to see the light.', 'Aristotle', 'system', CURRENT_TIMESTAMP);

-- DOWN
DROP INDEX IF EXISTS idx_quotes_author;
DROP TABLE IF EXISTS quotes;
