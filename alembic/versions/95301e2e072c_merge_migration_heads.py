"""Merge migration heads

Revision ID: 95301e2e072c
Revises: 000_initial, d1e2f3a4b5c6
Create Date: 2025-11-24 23:39:13.856689

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95301e2e072c'
down_revision: Union[str, None] = ('000_initial', 'd1e2f3a4b5c6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
