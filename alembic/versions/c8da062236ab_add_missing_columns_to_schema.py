"""Add missing columns to schema

Revision ID: c8da062236ab
Revises: 346370c653a3
Create Date: 2025-11-27 02:14:23.091886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8da062236ab'
down_revision: Union[str, None] = '346370c653a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing columns to current_status table
    with op.batch_alter_table('current_status', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True, server_default='offline'))
        batch_op.add_column(sa.Column('current_users', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('connected_users', sa.Integer(), nullable=True, server_default='0'))
    
    # Rename last_error to error_message in outbound_messages table
    with op.batch_alter_table('outbound_messages', schema=None) as batch_op:
        batch_op.alter_column('last_error', new_column_name='error_message', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    # Reverse the changes
    with op.batch_alter_table('outbound_messages', schema=None) as batch_op:
        batch_op.alter_column('error_message', new_column_name='last_error', existing_type=sa.Text(), nullable=True)
    
    with op.batch_alter_table('current_status', schema=None) as batch_op:
        batch_op.drop_column('connected_users')
        batch_op.drop_column('current_users')
        batch_op.drop_column('status')
