import pytest
from unittest.mock import AsyncMock

from plugins.trivia.achievements import AchievementChecker, GameResult
from plugins.trivia.storage import UserStats

@pytest.fixture
def mock_storage():
    return AsyncMock()

@pytest.fixture
def checker(mock_storage):
    return AchievementChecker(mock_storage)

@pytest.fixture
def base_stats():
    return UserStats(
        user_id="test_user",
        total_games=0,
        games_won=0,
        total_questions=0,
        correct_answers=0,
        total_points=0,
        current_answer_streak=0,
        best_answer_streak=0,
        current_win_streak=0,
        best_win_streak=0,
        fastest_answer_ms=None,
        favorite_category=None
    )

@pytest.mark.asyncio
async def test_check_first_game(checker, mock_storage, base_stats):
    mock_storage.get_user_achievements.return_value = []
    base_stats.total_games = 1
    
    new_achievements = await checker.check_and_award("test_user", base_stats)
    
    assert len(new_achievements) == 1
    assert new_achievements[0].id == "first_game"
    mock_storage.award_achievement.assert_called_with("test_user", "first_game")

@pytest.mark.asyncio
async def test_check_already_earned(checker, mock_storage, base_stats):
    mock_storage.get_user_achievements.return_value = [{"achievement_id": "first_game"}]
    base_stats.total_games = 1
    
    new_achievements = await checker.check_and_award("test_user", base_stats)
    
    assert len(new_achievements) == 0
    mock_storage.award_achievement.assert_not_called()

@pytest.mark.asyncio
async def test_check_multiple_achievements(checker, mock_storage, base_stats):
    mock_storage.get_user_achievements.return_value = []
    base_stats.total_games = 1
    base_stats.games_won = 1
    base_stats.total_points = 1000
    
    new_achievements = await checker.check_and_award("test_user", base_stats)
    
    ids = [a.id for a in new_achievements]
    assert "first_game" in ids
    assert "first_win" in ids
    assert "points_1000" in ids
    assert len(new_achievements) == 3

@pytest.mark.asyncio
async def test_check_game_result_achievements(checker, mock_storage, base_stats):
    mock_storage.get_user_achievements.return_value = []
    
    game_result = GameResult(won=True, perfect=True, score=100)
    
    new_achievements = await checker.check_and_award("test_user", base_stats, game_result)
    
    ids = [a.id for a in new_achievements]
    assert "first_perfect" in ids

@pytest.mark.asyncio
async def test_check_streak_achievements(checker, mock_storage, base_stats):
    mock_storage.get_user_achievements.return_value = []
    base_stats.best_answer_streak = 5
    
    new_achievements = await checker.check_and_award("test_user", base_stats)
    
    ids = [a.id for a in new_achievements]
    assert "streak_5" in ids
    assert "streak_10" not in ids
