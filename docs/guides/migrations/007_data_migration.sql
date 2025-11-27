-- UP
-- Migrate legacy data: normalize author names and set default category
-- This migration updates existing data without changing schema

-- Step 1: Normalize author names (trim whitespace, fix common typos)
UPDATE quotes 
SET author = TRIM(author)
WHERE author IS NOT NULL AND author != TRIM(author);

-- Step 2: Fix common author name typos
UPDATE quotes SET author = 'Anonymous' WHERE author IN ('Anon', 'anon', 'Unknown');
UPDATE quotes SET author = 'Oscar Wilde' WHERE author = 'Oscar Wild';
UPDATE quotes SET author = 'Mark Twain' WHERE author = 'Marc Twain';

-- Step 3: Set default category for uncategorized quotes
UPDATE quotes 
SET category = 'general' 
WHERE category = '' OR category IS NULL;

-- Step 4: Migrate special category names to new naming convention
UPDATE quotes SET category = 'humor' WHERE category IN ('funny', 'comedy', 'humour');
UPDATE quotes SET category = 'wisdom' WHERE category IN ('wise', 'philosophy', 'philosophical');
UPDATE quotes SET category = 'inspiration' WHERE category IN ('motivational', 'inspiring', 'motivation');

-- DOWN
-- Data migrations are typically not reversible
-- This rollback restores original values as best as possible
-- Note: Some information may be lost (e.g., original typos)

-- Revert category migrations (best effort)
UPDATE quotes SET category = 'funny' WHERE category = 'humor';
UPDATE quotes SET category = 'wise' WHERE category = 'wisdom';
UPDATE quotes SET category = 'motivational' WHERE category = 'inspiration';

-- Revert author normalizations (limited - original typos lost)
UPDATE quotes SET category = '' WHERE category = 'general' AND added_at < datetime('now', '-1 hour');

-- Note: Cannot reliably restore original author typos or whitespace
-- Consider backing up data before applying this migration
