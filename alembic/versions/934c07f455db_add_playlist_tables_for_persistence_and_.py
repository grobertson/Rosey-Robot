"""Add playlist tables for persistence and history

Revision ID: 934c07f455db
Revises: 95301e2e072c
Create Date: 2025-11-24 23:39:19.167001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '934c07f455db'
down_revision: Union[str, None] = '95301e2e072c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create playlist tables for persistence, history, and user stats."""
    
    # Queue persistence table
    op.execute("""
        CREATE TABLE IF NOT EXISTS playlist_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            position INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            media_id TEXT NOT NULL,
            title TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            added_by TEXT NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel, position)
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_playlist_queue_channel 
        ON playlist_queue(channel, position)
    """)
    
    # Play history table
    op.execute("""
        CREATE TABLE IF NOT EXISTS playlist_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT NOT NULL,
            media_type TEXT NOT NULL,
            media_id TEXT NOT NULL,
            title TEXT NOT NULL,
            duration INTEGER DEFAULT 0,
            added_by TEXT NOT NULL,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            play_duration INTEGER DEFAULT 0,
            skipped BOOLEAN DEFAULT FALSE
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_playlist_history_channel 
        ON playlist_history(channel)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_playlist_history_user 
        ON playlist_history(added_by)
    """)
    
    # User statistics table
    op.execute("""
        CREATE TABLE IF NOT EXISTS playlist_user_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            items_added INTEGER DEFAULT 0,
            items_played INTEGER DEFAULT 0,
            items_skipped INTEGER DEFAULT 0,
            total_duration_added INTEGER DEFAULT 0,
            total_duration_played INTEGER DEFAULT 0,
            last_add TIMESTAMP NULL
        )
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_playlist_user_stats_user 
        ON playlist_user_stats(user_id)
    """)


def downgrade() -> None:
    """Drop playlist tables."""
    op.execute("DROP INDEX IF EXISTS idx_playlist_user_stats_user")
    op.execute("DROP TABLE IF EXISTS playlist_user_stats")
    
    op.execute("DROP INDEX IF EXISTS idx_playlist_history_user")
    op.execute("DROP INDEX IF EXISTS idx_playlist_history_channel")
    op.execute("DROP TABLE IF EXISTS playlist_history")
    
    op.execute("DROP INDEX IF EXISTS idx_playlist_queue_channel")
    op.execute("DROP TABLE IF EXISTS playlist_queue")

