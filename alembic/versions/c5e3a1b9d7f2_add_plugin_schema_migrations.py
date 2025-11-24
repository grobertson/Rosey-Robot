"""add plugin schema migrations tracking

Revision ID: c5e3a1b9d7f2
Revises: abbb22091089
Create Date: 2025-11-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e3a1b9d7f2'
down_revision: Union[str, None] = 'abbb22091089'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create plugin_schema_migrations table for tracking applied migrations."""
    op.create_table(
        'plugin_schema_migrations',
        sa.Column(
            'id',
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            comment='Unique migration record ID'
        ),
        sa.Column(
            'plugin_name',
            sa.String(length=100),
            nullable=False,
            comment="Plugin identifier (e.g., 'quote-db', 'trivia')"
        ),
        sa.Column(
            'version',
            sa.Integer(),
            nullable=False,
            comment='Migration version number (e.g., 1, 2, 3)'
        ),
        sa.Column(
            'name',
            sa.String(length=255),
            nullable=False,
            comment="Migration name from filename (e.g., 'create_quotes')"
        ),
        sa.Column(
            'checksum',
            sa.String(length=64),
            nullable=False,
            comment='SHA-256 checksum of migration file (for tamper detection)'
        ),
        sa.Column(
            'applied_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='When migration was applied'
        ),
        sa.Column(
            'applied_by',
            sa.String(length=100),
            nullable=False,
            comment='User or system that applied the migration'
        ),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            comment="Migration status: 'success' or 'failed'"
        ),
        sa.Column(
            'error_message',
            sa.Text(),
            nullable=True,
            comment='Error message if migration failed'
        ),
        sa.Column(
            'execution_time_ms',
            sa.Integer(),
            nullable=True,
            comment='Time taken to execute migration in milliseconds'
        ),
    )
    
    # Unique constraint: one migration per plugin per version
    op.create_index(
        'idx_plugin_schema_migrations_unique',
        'plugin_schema_migrations',
        ['plugin_name', 'version'],
        unique=True
    )
    
    # Index for querying current version (most recent applied migration)
    op.create_index(
        'idx_plugin_schema_migrations_plugin',
        'plugin_schema_migrations',
        ['plugin_name', 'applied_at']
    )


def downgrade() -> None:
    """Drop plugin_schema_migrations table."""
    op.drop_index(
        'idx_plugin_schema_migrations_plugin',
        table_name='plugin_schema_migrations'
    )
    op.drop_index(
        'idx_plugin_schema_migrations_unique',
        table_name='plugin_schema_migrations'
    )
    op.drop_table('plugin_schema_migrations')
