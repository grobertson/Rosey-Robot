import pytest
import json
from unittest.mock import AsyncMock

from plugins.trivia.storage import TriviaStorage

class MockNatsResponse:
    def __init__(self, data):
        self.data = json.dumps(data).encode()

@pytest.fixture
def mock_nats():
    client = AsyncMock()
    client.request = AsyncMock()
    return client

@pytest.fixture
def storage(mock_nats):
    return TriviaStorage(mock_nats)

@pytest.mark.asyncio
async def test_get_user_stats_found(storage, mock_nats):
    # Mock response for search
    mock_nats.request.return_value = MockNatsResponse({
        "success": True,
        "rows": [{
            "user_id": "test_user",
            "total_games": 10,
            "games_won": 3,
            "total_questions": 100,
            "correct_answers": 75,
            "total_points": 500,
            "current_answer_streak": 2,
            "best_answer_streak": 5,
            "current_win_streak": 1,
            "best_win_streak": 2,
            "fastest_answer_ms": 1500,
            "favorite_category": "Science"
        }]
    })
    
    stats = await storage.get_user_stats("test_user")
    
    assert stats is not None
    assert stats.user_id == "test_user"
    assert stats.total_games == 10
    assert stats.accuracy == 75.0
    assert stats.win_rate == 30.0
    
    # Verify request subject
    args = mock_nats.request.call_args
    assert args[0][0] == "rosey.db.row.trivia.search"

@pytest.mark.asyncio
async def test_get_user_stats_not_found(storage, mock_nats):
    mock_nats.request.return_value = MockNatsResponse({
        "success": True,
        "rows": []
    })
    stats = await storage.get_user_stats("unknown")
    assert stats is None

@pytest.mark.asyncio
async def test_update_user_stats(storage, mock_nats):
    # Sequence of calls:
    # 1. ensure_user_stats -> search (fail) -> insert
    # 2. get_user_stats (for win streak logic)
    # 3. update
    # 4. get_user_stats (return)
    
    mock_nats.request.side_effect = [
        # ensure_user_stats -> search
        MockNatsResponse({"success": True, "rows": []}),
        # ensure_user_stats -> insert
        MockNatsResponse({"success": True, "id": 123}),
        # get_user_stats (for win streak logic)
        MockNatsResponse({"success": True, "rows": [{
            "user_id": "test_user",
            "current_win_streak": 1,
            "best_win_streak": 2,
            "fastest_answer_ms": 2000
        }]}),
        # get_user_stats (for fastest answer logic) - redundant call but present in code
        MockNatsResponse({"success": True, "rows": [{
            "user_id": "test_user",
            "current_win_streak": 1,
            "best_win_streak": 2,
            "fastest_answer_ms": 2000
        }]}),
        # update
        MockNatsResponse({"success": True, "id": 123, "updated": True}),
        # get_user_stats (return)
        MockNatsResponse({"success": True, "rows": [{
            "user_id": "test_user",
            "total_games": 1,
            "games_won": 1
        }]})
    ]
    
    await storage.update_user_stats(
        user_id="test_user",
        questions_answered=10,
        correct_answers=8,
        points_earned=100,
        won_game=True,
        fastest_ms=1200
    )
    
    assert mock_nats.request.call_count == 6

@pytest.mark.asyncio
async def test_update_streak_correct(storage, mock_nats):
    # 1. ensure -> search (found)
    # 2. get_user_stats
    # 3. update
    
    mock_nats.request.side_effect = [
        # ensure -> search
        MockNatsResponse({"success": True, "rows": [{"id": 123}]}),
        # get_user_stats
        MockNatsResponse({"success": True, "rows": [{
            "user_id": "test_user",
            "current_answer_streak": 5,
            "best_answer_streak": 10
        }]}),
        # update
        MockNatsResponse({"success": True, "id": 123, "updated": True})
    ]
    
    current, best = await storage.update_streak("test_user", True)
    
    assert current == 6
    assert best == 10
    
    # Verify update payload
    update_call = mock_nats.request.call_args_list[2]
    payload = json.loads(update_call[0][1])
    assert payload["data"]["current_answer_streak"] == 6

@pytest.mark.asyncio
async def test_update_streak_incorrect(storage, mock_nats):
    mock_nats.request.side_effect = [
        MockNatsResponse({"success": True, "rows": [{"id": 123}]}),
        MockNatsResponse({"success": True, "rows": [{
            "user_id": "test_user",
            "current_answer_streak": 5,
            "best_answer_streak": 10
        }]}),
        MockNatsResponse({"success": True, "id": 123, "updated": True})
    ]
    
    current, best = await storage.update_streak("test_user", False)
    
    assert current == 0
    assert best == 10
