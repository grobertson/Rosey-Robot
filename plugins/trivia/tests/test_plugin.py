"""
Tests for trivia plugin integration.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from trivia.plugin import TriviaPlugin
from trivia.game import GameState
from trivia.question import Difficulty, Question, QuestionType


class TestTriviaPluginInit:
    """Test plugin initialization."""

    def test_init_defaults(self, mock_nats):
        """Test default initialization."""
        plugin = TriviaPlugin(mock_nats)

        assert plugin.NAMESPACE == "trivia"
        assert plugin.VERSION == "1.1.0"
        assert plugin.DESCRIPTION == "Interactive trivia game with persistence"

    def test_init_with_config(self, mock_nats, plugin_config):
        """Test initialization with custom config."""
        plugin = TriviaPlugin(mock_nats, plugin_config)

        assert plugin.time_per_question == 5
        assert plugin.default_questions == 3
        assert plugin.max_questions == 10


class TestTriviaPluginLifecycle:
    """Test plugin lifecycle methods."""

    @pytest.mark.asyncio
    async def test_initialize_subscribes(self, mock_nats):
        """Test initialize sets up subscriptions."""
        plugin = TriviaPlugin(mock_nats)

        await plugin.initialize()

        assert plugin._initialized is True
        assert mock_nats.subscribe.call_count == 7  # 4 commands + 3 stats/lb
        assert len(plugin._subscriptions) == 7

    @pytest.mark.asyncio
    async def test_shutdown_cleanup(self, mock_nats):
        """Test shutdown cleans up resources."""
        plugin = TriviaPlugin(mock_nats)
        await plugin.initialize()

        # Add a mock game
        mock_game = MagicMock()
        mock_game.stop = AsyncMock()
        plugin.active_games["test-channel"] = mock_game

        await plugin.shutdown()

        assert plugin._initialized is False
        assert len(plugin._subscriptions) == 0
        assert len(plugin.active_games) == 0
        mock_game.stop.assert_called_once()


class TestHandleStart:
    """Test !trivia start command handler."""

    @pytest.fixture
    def mock_msg(self):
        """Create mock NATS message."""
        msg = MagicMock()
        msg.reply = "reply.subject"
        msg.respond = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_start_success(self, mock_nats, plugin_config, mock_msg, sample_questions):
        """Test successful game start."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        # Mock the provider
        plugin.provider.fetch_questions = AsyncMock(return_value=sample_questions)

        # Create message
        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "3",
        }).encode()

        await plugin._handle_start(mock_msg)

        # Verify game was created
        assert "lobby" in plugin.active_games
        game = plugin.active_games["lobby"]
        assert game.channel == "lobby"

        # Verify response sent
        mock_msg.respond.assert_called_once()
        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is True
        assert "game_id" in response["result"]

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_start_game_already_active(self, mock_nats, plugin_config, mock_msg, sample_questions):
        """Test starting when game already active."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        plugin.provider.fetch_questions = AsyncMock(return_value=sample_questions)

        # Start first game
        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "",
        }).encode()
        await plugin._handle_start(mock_msg)

        # Try to start second game
        mock_msg.respond.reset_mock()
        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player2",
            "args": "",
        }).encode()
        await plugin._handle_start(mock_msg)

        # Should return error
        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is False
        assert "already in progress" in response["error"]

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_start_provider_error(self, mock_nats, plugin_config, mock_msg):
        """Test handling provider error."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        # Mock provider to raise error
        plugin.provider.fetch_questions = AsyncMock(side_effect=Exception("API error"))

        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "",
        }).encode()

        await plugin._handle_start(mock_msg)

        # Should return error
        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is False
        assert "Couldn't fetch" in response["error"]

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_start_clamps_questions(self, mock_nats, plugin_config, mock_msg, sample_questions):
        """Test question count is clamped to config limits."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        plugin.provider.fetch_questions = AsyncMock(return_value=sample_questions)

        # Request more than max
        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "100",
        }).encode()

        await plugin._handle_start(mock_msg)

        # Provider should be called with max
        call_args = plugin.provider.fetch_questions.call_args
        assert call_args[0][0] == plugin.max_questions

        await plugin.shutdown()


class TestHandleStop:
    """Test !trivia stop command handler."""

    @pytest.fixture
    def mock_msg(self):
        """Create mock NATS message."""
        msg = MagicMock()
        msg.reply = "reply.subject"
        msg.respond = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_stop_success(self, mock_nats, plugin_config, mock_msg, sample_questions):
        """Test successful game stop."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        plugin.provider.fetch_questions = AsyncMock(return_value=sample_questions)

        # Start a game
        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "",
        }).encode()
        await plugin._handle_start(mock_msg)

        # Stop the game
        mock_msg.respond.reset_mock()
        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
        }).encode()
        await plugin._handle_stop(mock_msg)

        # Should respond success
        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is True
        assert "stopped" in response["result"]["message"]

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_stop_no_active_game(self, mock_nats, plugin_config, mock_msg):
        """Test stopping when no game active."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
        }).encode()

        await plugin._handle_stop(mock_msg)

        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is False
        assert "No active game" in response["error"]

        await plugin.shutdown()


class TestHandleAnswer:
    """Test !trivia answer / !a command handler."""

    @pytest.fixture
    def mock_msg(self):
        """Create mock NATS message."""
        msg = MagicMock()
        msg.reply = "reply.subject"
        msg.respond = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_answer_no_game(self, mock_nats, plugin_config, mock_msg):
        """Test answering when no game active."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "A",
        }).encode()

        await plugin._handle_answer(mock_msg)

        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is False
        assert "No active question" in response["error"]

        await plugin.shutdown()

    @pytest.mark.asyncio
    async def test_answer_empty(self, mock_nats, plugin_config, mock_msg):
        """Test empty answer."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
            "args": "",
        }).encode()

        await plugin._handle_answer(mock_msg)

        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is False
        assert "Usage" in response["error"]

        await plugin.shutdown()


class TestHandleSkip:
    """Test !trivia skip command handler."""

    @pytest.fixture
    def mock_msg(self):
        """Create mock NATS message."""
        msg = MagicMock()
        msg.reply = "reply.subject"
        msg.respond = AsyncMock()
        return msg

    @pytest.mark.asyncio
    async def test_skip_no_game(self, mock_nats, plugin_config, mock_msg):
        """Test skipping when no game active."""
        plugin = TriviaPlugin(mock_nats, plugin_config)
        await plugin.initialize()

        mock_msg.data = json.dumps({
            "channel": "lobby",
            "user": "player1",
        }).encode()

        await plugin._handle_skip(mock_msg)

        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is False
        assert "No active question" in response["error"]

        await plugin.shutdown()


class TestGameCallbacks:
    """Test game callback handling."""

    @pytest.mark.asyncio
    async def test_on_question_sends_message(self, mock_nats, sample_questions):
        """Test question callback sends to channel."""
        plugin = TriviaPlugin(mock_nats)

        # Create game and set current question
        from trivia.game import TriviaGame, GameConfig

        config = GameConfig(num_questions=3, time_per_question=30)
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=sample_questions,
        )
        game.current_question_index = 0

        question = sample_questions[0]

        await plugin._on_question(game, question)

        # Verify message published to channel (first call is to channel, second is event)
        assert mock_nats.publish.call_count >= 1
        # Find the channel message call
        channel_call = None
        for call in mock_nats.publish.call_args_list:
            if "rosey.channel.lobby.message" in call[0][0]:
                channel_call = call
                break
        assert channel_call is not None

    @pytest.mark.asyncio
    async def test_on_answer_correct(self, mock_nats, sample_questions):
        """Test correct answer callback."""
        plugin = TriviaPlugin(mock_nats)

        from trivia.game import TriviaGame, GameConfig
        from trivia.question import Answer

        config = GameConfig(num_questions=3)
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=sample_questions,
        )

        answer = Answer(
            user="player1",
            answer="Paris",
            timestamp=3.5,
            correct=True,
            points_awarded=12,
        )

        await plugin._on_answer(game, answer)

        # Verify correct message sent - find channel message call
        assert mock_nats.publish.call_count >= 1
        channel_call = None
        for call in mock_nats.publish.call_args_list:
            if "rosey.channel.lobby.message" in call[0][0]:
                channel_call = call
                break
        assert channel_call is not None
        message_data = json.loads(channel_call[0][1])
        assert "Correct" in message_data["message"]

    @pytest.mark.asyncio
    async def test_on_answer_incorrect(self, mock_nats, sample_questions):
        """Test incorrect answer callback."""
        plugin = TriviaPlugin(mock_nats)

        from trivia.game import TriviaGame, GameConfig
        from trivia.question import Answer

        config = GameConfig(num_questions=3)
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=sample_questions,
        )

        answer = Answer(
            user="player1",
            answer="London",
            timestamp=5.0,
            correct=False,
            points_awarded=0,
        )

        await plugin._on_answer(game, answer)

        # Verify incorrect message sent - find channel message call
        assert mock_nats.publish.call_count >= 1
        channel_call = None
        for call in mock_nats.publish.call_args_list:
            if "rosey.channel.lobby.message" in call[0][0]:
                channel_call = call
                break
        assert channel_call is not None
        message_data = json.loads(channel_call[0][1])
        assert "not it" in message_data["message"]

    @pytest.mark.asyncio
    async def test_on_timeout(self, mock_nats, sample_questions):
        """Test timeout callback."""
        plugin = TriviaPlugin(mock_nats)

        from trivia.game import TriviaGame, GameConfig

        config = GameConfig(num_questions=3)
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=sample_questions,
        )
        game.current_question_index = 0

        question = sample_questions[0]

        await plugin._on_timeout(game, question)

        # Verify timeout message sent - find channel message call
        assert mock_nats.publish.call_count >= 1
        channel_call = None
        for call in mock_nats.publish.call_args_list:
            if "rosey.channel.lobby.message" in call[0][0]:
                channel_call = call
                break
        assert channel_call is not None
        message_data = json.loads(channel_call[0][1])
        assert "Time's up" in message_data["message"]

    @pytest.mark.asyncio
    async def test_on_game_end(self, mock_nats, sample_questions):
        """Test game end callback with leaderboard."""
        plugin = TriviaPlugin(mock_nats)
        plugin.active_games["lobby"] = MagicMock()

        from trivia.game import TriviaGame, GameConfig, PlayerScore

        config = GameConfig(num_questions=3)
        game = TriviaGame(
            game_id="test",
            channel="lobby",
            config=config,
            questions=sample_questions,
        )
        game.current_question_index = 2

        # Add some scores
        game.scores["player1"] = PlayerScore(user="player1", score=50, correct_answers=3)
        game.scores["player2"] = PlayerScore(user="player2", score=30, correct_answers=2)

        await plugin._on_game_end(game)

        # Verify leaderboard message sent - find channel message call
        assert mock_nats.publish.call_count >= 1
        channel_call = None
        for call in mock_nats.publish.call_args_list:
            if "rosey.channel.lobby.message" in call[0][0]:
                channel_call = call
                break
        assert channel_call is not None
        message_data = json.loads(channel_call[0][1])
        assert "Game Over" in message_data["message"]
        assert "player1" in message_data["message"]


class TestEventEmission:
    """Test NATS event emission."""

    @pytest.mark.asyncio
    async def test_events_disabled(self, mock_nats):
        """Test events can be disabled via config."""
        config = {"emit_events": False}
        plugin = TriviaPlugin(mock_nats, config)

        # Verify emit_events is False
        assert plugin.emit_events is False

        # When emit_events is False, callback methods won't call _emit_event
        # We verify this by checking the config flag is properly read

    @pytest.mark.asyncio
    async def test_events_enabled_by_default(self, mock_nats):
        """Test events enabled by default."""
        plugin = TriviaPlugin(mock_nats)
        assert plugin.emit_events is True

    @pytest.mark.asyncio
    async def test_event_format(self, mock_nats):
        """Test event data format."""
        plugin = TriviaPlugin(mock_nats)

        await plugin._emit_event("trivia.test", {"channel": "lobby", "data": "value"})

        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args
        
        # Check subject
        assert call_args[0][0] == "trivia.test"
        
        # Check data format
        data = json.loads(call_args[0][1])
        assert data["event"] == "trivia.test"
        assert "timestamp" in data
        assert data["channel"] == "lobby"
        assert data["data"] == "value"


class TestHelperMethods:
    """Test helper methods."""

    @pytest.mark.asyncio
    async def test_send_to_channel(self, mock_nats):
        """Test sending message to channel."""
        plugin = TriviaPlugin(mock_nats)

        await plugin._send_to_channel("lobby", "Hello world!")

        mock_nats.publish.assert_called_once()
        call_args = mock_nats.publish.call_args
        
        assert "rosey.channel.lobby.message" in call_args[0][0]
        
        data = json.loads(call_args[0][1])
        assert data["channel"] == "lobby"
        assert data["message"] == "Hello world!"

    @pytest.mark.asyncio
    async def test_respond(self, mock_nats):
        """Test responding to message."""
        plugin = TriviaPlugin(mock_nats)

        mock_msg = MagicMock()
        mock_msg.respond = AsyncMock()

        await plugin._respond(mock_msg, {"success": True, "result": "test"})

        mock_msg.respond.assert_called_once()
        response = json.loads(mock_msg.respond.call_args[0][0])
        assert response["success"] is True
        assert response["result"] == "test"
