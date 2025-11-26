-- Migration: Add recurrence and alert columns
-- Version: 002
-- Description: Adds support for recurring countdowns and T-minus alerts

-- UP
ALTER TABLE countdowns ADD COLUMN recurrence_rule TEXT NULL;
ALTER TABLE countdowns ADD COLUMN is_paused INTEGER DEFAULT 0;
ALTER TABLE countdowns ADD COLUMN alert_minutes TEXT NULL;
ALTER TABLE countdowns ADD COLUMN last_alert_sent INTEGER NULL;

-- DOWN
-- SQLite doesn't support DROP COLUMN directly, but these can be ignored
-- For rollback, recreate table without these columns
-- ALTER TABLE countdowns DROP COLUMN recurrence_rule;
-- ALTER TABLE countdowns DROP COLUMN is_paused;
-- ALTER TABLE countdowns DROP COLUMN alert_minutes;
-- ALTER TABLE countdowns DROP COLUMN last_alert_sent;
