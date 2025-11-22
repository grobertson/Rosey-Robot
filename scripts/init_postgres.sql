-- PostgreSQL initialization script for Rosey Bot
-- Runs automatically via docker-compose on first startup

-- Create extensions (if needed in future)
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Trigram similarity for FTS
-- CREATE EXTENSION IF NOT EXISTS btree_gin;  -- GIN indexes on scalar types

-- Set timezone (optional)
SET timezone = 'UTC';

-- Grant privileges (already done by POSTGRES_USER, but explicit)
GRANT ALL PRIVILEGES ON DATABASE rosey_dev TO rosey;

-- Performance tuning for development (optional)
ALTER DATABASE rosey_dev SET log_statement = 'all';  -- Log all statements
ALTER DATABASE rosey_dev SET log_duration = on;      -- Log query duration

-- Tables are created by Alembic migrations (not here)
-- Run: alembic upgrade head

-- Print confirmation
SELECT 'PostgreSQL initialized for Rosey Bot' AS status;
