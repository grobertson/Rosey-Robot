-- Migration 001: Create countdowns table
-- Purpose: Establish table structure for countdown timer storage
-- Version: 1.0
-- Created: 2025-11-24

-- UP
CREATE TABLE countdowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    channel TEXT NOT NULL,
    target_time TIMESTAMP NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE NOT NULL,
    recurrence_rule TEXT NULL,
    completed BOOLEAN DEFAULT FALSE NOT NULL,
    
    -- Names must be unique within a channel
    UNIQUE(channel, name)
);

-- Index for querying by channel
CREATE INDEX idx_countdowns_channel ON countdowns(channel);

-- Index for finding pending countdowns
CREATE INDEX idx_countdowns_pending ON countdowns(target_time) WHERE completed = FALSE;

-- DOWN
DROP INDEX IF EXISTS idx_countdowns_pending;
DROP INDEX IF EXISTS idx_countdowns_channel;
DROP TABLE IF EXISTS countdowns;
