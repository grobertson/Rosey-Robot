"""Initial schema for fresh database

Revision ID: 000_initial
Revises: 
Create Date: 2025-11-24

This migration creates all tables from scratch for a fresh database.
It should be run on empty databases before any other migrations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '000_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_stats table
    op.create_table('user_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('first_seen', sa.Integer(), nullable=False),
        sa.Column('last_seen', sa.Integer(), nullable=False),
        sa.Column('total_chat_lines', sa.Integer(), nullable=False),
        sa.Column('total_time_connected', sa.Integer(), nullable=False),
        sa.Column('current_session_start', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_user_stats_username'), 'user_stats', ['username'], unique=True)

    # Create user_actions table
    op.create_table('user_actions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_actions_username'), 'user_actions', ['username'], unique=False)
    op.create_index(op.f('ix_user_actions_timestamp'), 'user_actions', ['timestamp'], unique=False)

    # Create channel_stats table
    op.create_table('channel_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stat_name', sa.String(length=100), nullable=False),
        sa.Column('stat_value', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stat_name')
    )
    op.create_index(op.f('ix_channel_stats_stat_name'), 'channel_stats', ['stat_name'], unique=True)

    # Create user_count_history table
    op.create_table('user_count_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=False),
        sa.Column('chat_count', sa.Integer(), nullable=False),
        sa.Column('connected_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_count_history_timestamp'), 'user_count_history', ['timestamp'], unique=False)

    # Create recent_chat table
    op.create_table('recent_chat',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recent_chat_timestamp'), 'recent_chat', ['timestamp'], unique=False)

    # Create current_status table
    op.create_table('current_status',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.Integer(), nullable=False),
        sa.Column('status_type', sa.String(length=50), nullable=False),
        sa.Column('status_data', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('status_type')
    )
    op.create_index(op.f('ix_current_status_status_type'), 'current_status', ['status_type'], unique=True)

    # Create outbound_messages table
    op.create_table('outbound_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('sent', sa.Boolean(), nullable=False),
        sa.Column('sent_at', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_outbound_messages_sent'), 'outbound_messages', ['sent'], unique=False)
    op.create_index(op.f('ix_outbound_messages_created_at'), 'outbound_messages', ['created_at'], unique=False)

    # Create api_tokens table
    op.create_table('api_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_id', sa.String(length=255), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('last_used_at', sa.Integer(), nullable=True),
        sa.Column('expires_at', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_id')
    )
    op.create_index(op.f('ix_api_tokens_token_id'), 'api_tokens', ['token_id'], unique=True)

    # Create plugin_kv_storage table  
    op.create_table('plugin_kv_storage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin_name', sa.String(length=100), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plugin_name', 'key', name='uix_plugin_key')
    )
    op.create_index(op.f('ix_plugin_kv_storage_plugin_name'), 'plugin_kv_storage', ['plugin_name'], unique=False)
    op.create_index(op.f('ix_plugin_kv_storage_expires_at'), 'plugin_kv_storage', ['expires_at'], unique=False)

    # Create plugin_table_schemas table
    op.create_table('plugin_table_schemas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plugin_name', sa.String(length=100), nullable=False),
        sa.Column('table_name', sa.String(length=100), nullable=False),
        sa.Column('schema_json', sa.Text(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('plugin_name', 'table_name', name='uix_plugin_table')
    )
    op.create_index(op.f('ix_plugin_table_schemas_plugin_name'), 'plugin_table_schemas', ['plugin_name'], unique=False)


def downgrade() -> None:
    # Drop all tables
    op.drop_table('plugin_table_schemas')
    op.drop_table('plugin_kv_storage')
    op.drop_table('api_tokens')
    op.drop_table('outbound_messages')
    op.drop_table('current_status')
    op.drop_table('recent_chat')
    op.drop_table('user_count_history')
    op.drop_table('channel_stats')
    op.drop_table('user_actions')
    op.drop_table('user_stats')
