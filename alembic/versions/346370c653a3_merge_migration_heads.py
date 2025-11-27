"""Merge migration heads

Revision ID: 346370c653a3
Revises: 000_initial, d1e2f3a4b5c6
Create Date: 2025-11-27 02:14:18.632848

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '346370c653a3'
down_revision: Union[str, None] = ('000_initial', 'd1e2f3a4b5c6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
