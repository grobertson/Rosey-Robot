"""Add trivia tables

Revision ID: d1e2f3a4b5c6
Revises: c5e3a1b9d7f2
Create Date: 2025-11-24 14:00:00.000000

Sprint: 18 (Funny Games)
Sortie: 6 (Trivia Scoring)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c5e3a1b9d7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create trivia tables."""
    
    # trivia_user_stats
    op.create_table(
        'trivia_user_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('total_games', sa.Integer(), server_default='0'),
        sa.Column('games_won', sa.Integer(), server_default='0'),
        sa.Column('total_questions', sa.Integer(), server_default='0'),
        sa.Column('correct_answers', sa.Integer(), server_default='0'),
        sa.Column('total_points', sa.Integer(), server_default='0'),
        sa.Column('current_answer_streak', sa.Integer(), server_default='0'),
        sa.Column('best_answer_streak', sa.Integer(), server_default='0'),
        sa.Column('current_win_streak', sa.Integer(), server_default='0'),
        sa.Column('best_win_streak', sa.Integer(), server_default='0'),
        sa.Column('fastest_answer_ms', sa.Integer(), nullable=True),
        sa.Column('favorite_category', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_trivia_user_stats_points', 'trivia_user_stats', ['total_points'])

    # trivia_channel_stats
    op.create_table(
        'trivia_channel_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('channel', sa.String(length=100), nullable=False),
        sa.Column('games_played', sa.Integer(), server_default='0'),
        sa.Column('games_won', sa.Integer(), server_default='0'),
        sa.Column('total_points', sa.Integer(), server_default='0'),
        sa.Column('correct_answers', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('user_id', 'channel', name='uq_trivia_channel_stats_user_channel')
    )
    op.create_index('idx_trivia_channel_stats_channel', 'trivia_channel_stats', ['channel'])
    op.create_index('idx_trivia_channel_stats_points', 'trivia_channel_stats', ['channel', 'total_points'])

    # trivia_games
    op.create_table(
        'trivia_games',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('game_id', sa.String(length=100), nullable=False, unique=True),
        sa.Column('channel', sa.String(length=100), nullable=False),
        sa.Column('started_by', sa.String(length=100), nullable=False),
        sa.Column('num_questions', sa.Integer(), nullable=False),
        sa.Column('num_players', sa.Integer(), nullable=False),
        sa.Column('winner_id', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active'),
    )
    op.create_index('idx_trivia_games_channel', 'trivia_games', ['channel'])

    # trivia_achievements
    op.create_table(
        'trivia_achievements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('achievement_id', sa.String(length=100), nullable=False),
        sa.Column('earned_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('user_id', 'achievement_id', name='uq_trivia_achievements_user_achievement')
    )
    op.create_index('idx_trivia_achievements_user', 'trivia_achievements', ['user_id'])

    # trivia_category_stats
    op.create_table(
        'trivia_category_stats',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('questions_seen', sa.Integer(), server_default='0'),
        sa.Column('correct_answers', sa.Integer(), server_default='0'),
        sa.UniqueConstraint('user_id', 'category', name='uq_trivia_category_stats_user_category')
    )
    op.create_index('idx_trivia_category_stats_user', 'trivia_category_stats', ['user_id'])


def downgrade() -> None:
    """Drop trivia tables."""
    op.drop_table('trivia_category_stats')
    op.drop_table('trivia_achievements')
    op.drop_table('trivia_games')
    op.drop_table('trivia_channel_stats')
    op.drop_table('trivia_user_stats')
