"""Add plugin KV storage table

Revision ID: b8c7d2e9f4a1
Revises: 45490ea63a06
Create Date: 2025-11-24 10:00:00.000000

Sprint: 12 (KV Storage Foundation)
Sortie: 1 (Schema & Model)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c7d2e9f4a1'
down_revision: Union[str, None] = '45490ea63a06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create plugin_kv_storage table with indexes."""
    # Create table
    op.create_table(
        'plugin_kv_storage',
        sa.Column('plugin_name', sa.String(length=100), nullable=False, comment="Plugin identifier (e.g., 'trivia', 'quote-db')"),
        sa.Column('key', sa.String(length=255), nullable=False, comment='Key name within plugin namespace'),
        sa.Column('value_json', sa.Text(), nullable=False, comment='JSON-serialized value (string, number, object, array)'),
        sa.Column('expires_at', sa.Integer(), nullable=True, comment='Expiration timestamp (Unix epoch, NULL = never expires)'),
        sa.Column('created_at', sa.Integer(), nullable=False, comment='When key was first created (Unix epoch)'),
        sa.Column('updated_at', sa.Integer(), nullable=False, comment='When key was last updated (Unix epoch)'),
        sa.PrimaryKeyConstraint('plugin_name', 'key', name='pk_plugin_kv_storage'),
        comment='Plugin key-value storage with TTL support'
    )

    # Create index for TTL cleanup queries
    op.create_index(
        'idx_plugin_kv_expires',
        'plugin_kv_storage',
        ['expires_at'],
        unique=False
    )

    # Create index for prefix queries
    op.create_index(
        'idx_plugin_kv_prefix',
        'plugin_kv_storage',
        ['plugin_name', 'key'],
        unique=False
    )


def downgrade() -> None:
    """Drop plugin_kv_storage table and indexes."""
    op.drop_index('idx_plugin_kv_prefix', table_name='plugin_kv_storage')
    op.drop_index('idx_plugin_kv_expires', table_name='plugin_kv_storage')
    op.drop_table('plugin_kv_storage')
