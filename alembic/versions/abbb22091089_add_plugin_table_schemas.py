"""add plugin table schemas

Revision ID: abbb22091089
Revises: b8c7d2e9f4a1
Create Date: 2025-11-24 05:03:33.536682

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abbb22091089'
down_revision: Union[str, None] = 'b8c7d2e9f4a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create plugin_table_schemas table
    op.create_table(
        'plugin_table_schemas',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True, comment='Unique schema ID'),
        sa.Column('plugin_name', sa.String(length=100), nullable=False, comment="Plugin identifier (e.g., 'quote-db', 'trivia')"),
        sa.Column('table_name', sa.String(length=100), nullable=False, comment='Table name within plugin namespace'),
        sa.Column('schema_json', sa.Text(), nullable=False, comment="JSON schema: {'fields': [{'name': 'text', 'type': 'text', 'required': true}]}"),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1', comment='Schema version (for migrations)'),
        sa.Column('created_at', sa.Integer(), nullable=False, comment='Schema creation timestamp (Unix epoch)'),
        sa.Column('updated_at', sa.Integer(), nullable=False, comment='Schema last updated timestamp (Unix epoch)'),
        sa.PrimaryKeyConstraint('id'),
        comment='Plugin table schemas for row-based storage'
    )

    # Create indexes
    op.create_index('idx_plugin_name', 'plugin_table_schemas', ['plugin_name'], unique=False)
    op.create_index('idx_plugin_table_unique', 'plugin_table_schemas', ['plugin_name', 'table_name'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_plugin_table_unique', table_name='plugin_table_schemas')
    op.drop_index('idx_plugin_name', table_name='plugin_table_schemas')

    # Drop table
    op.drop_table('plugin_table_schemas')
