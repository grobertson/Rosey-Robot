# SPEC: Sortie 5 - Trivia Plugin Foundation

**Sprint:** 18 - Funny Games  
**Sortie:** 5 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2-3 days  
**Priority:** HIGH - Core entertainment feature

---

## 1. Overview

### 1.1 Purpose

The Trivia plugin provides interactive quiz games, demonstrating:

- Complex state machine (game states, rounds, answers)
- Timer management (countdown to answer)
- Multi-user interaction
- Question bank management
- Event-driven architecture

This sortie establishes the **foundation** with basic trivia gameplay. Sortie 6 adds scoring persistence and leaderboards.

### 1.2 Scope

**In Scope (Sortie 5):**
- `!trivia start` - Start a trivia round
- `!trivia stop` - End current round
- `!trivia answer <answer>` or `!a <answer>` - Submit answer
- `!trivia skip` - Skip current question
- Multiple-choice and free-response questions
- Configurable time limits
- In-memory scoring (per round)
- Open Trivia Database (OpenTDB) integration

**Out of Scope (Sortie 6):**
- Persistent scoring/leaderboards
- User statistics
- Custom question sets
- Category selection

### 1.3 Dependencies

- NATS client (existing)
- Plugin base class (existing)
- Event bus (existing)
- httpx/aiohttp for OpenTDB API

---

## 2. Technical Design

### 2.1 File Structure

```
plugins/trivia/
├── __init__.py           # Package exports
├── plugin.py             # Main plugin class
├── game.py               # Game state machine
├── question.py           # Question models
├── providers/
│   ├── __init__.py
│   ├── base.py           # Provider interface
│   └── opentdb.py        # Open Trivia Database provider
├── config.json           # Default configuration
├── README.md             # User documentation
└── tests/
    ├── __init__.py
    ├── test_game.py         # Game state tests
    ├── test_question.py     # Question model tests
    ├── test_providers.py    # Provider tests
    └── test_plugin.py       # Integration tests
```

### 2.2 NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.trivia.start` | Subscribe | Handle `!trivia start` |
| `rosey.command.trivia.stop` | Subscribe | Handle `!trivia stop` |
| `rosey.command.trivia.answer` | Subscribe | Handle `!trivia answer` / `!a` |
| `rosey.command.trivia.skip` | Subscribe | Handle `!trivia skip` |
| `trivia.game.started` | Publish | Event when game starts |
| `trivia.question.asked` | Publish | Event when question posed |
| `trivia.answer.correct` | Publish | Event when correct answer |
| `trivia.answer.incorrect` | Publish | Event when wrong answer |
| `trivia.question.timeout` | Publish | Event when time expires |
| `trivia.game.ended` | Publish | Event when game ends |

### 2.3 Message Schemas

#### Start Request
```json
{
  "channel": "lobby",
  "user": "quizmaster",
  "args": "10",
  "reply_to": "rosey.reply.abc123"
}
```

#### Start Response
```json
{
  "success": true,
  "result": {
    "game_id": "abc123",
    "questions": 10,
    "time_per_question": 30,
    "message": "🎯 Trivia starting! 10 questions, 30 seconds each. First question in 5 seconds..."
  }
}
```

#### Question Announcement (to channel)
```json
{
  "channel": "lobby",
  "message": "📝 Question 1/10 (Easy - General Knowledge):\n\nWhat is the capital of France?\n\nA) London  B) Paris  C) Berlin  D) Madrid\n\n⏱️ 30 seconds to answer! Use !a <letter> or !a <answer>"
}
```

#### Answer Request
```json
{
  "channel": "lobby",
  "user": "player1",
  "args": "B",
  "reply_to": "rosey.reply.def456"
}
```

#### Correct Answer Response
```json
{
  "success": true,
  "result": {
    "correct": true,
    "user": "player1",
    "answer": "Paris",
    "points": 10,
    "time_taken": 8.5,
    "message": "✅ Correct! player1 got it in 8.5 seconds! (+10 points)"
  }
}
```

#### Game Ended Event
```json
{
  "event": "trivia.game.ended",
  "channel": "lobby",
  "game_id": "abc123",
  "scores": [
    {"user": "player1", "score": 80},
    {"user": "player2", "score": 60}
  ],
  "questions_asked": 10,
  "message": "🏆 Game Over!\n\n1. 🥇 player1 - 80 points\n2. 🥈 player2 - 60 points"
}
```

### 2.4 Game State Machine

```
┌─────────────┐
│    IDLE     │◄──────────────────────────┐
└──────┬──────┘                           │
       │ !trivia start                    │
       ▼                                  │
┌─────────────┐                           │
│  STARTING   │ (countdown to first Q)    │
└──────┬──────┘                           │
       │ after 5 sec                      │ !trivia stop
       ▼                                  │ or all questions done
┌─────────────┐                           │
│  QUESTION   │◄──────────┐               │
│  ACTIVE     │           │               │
└──────┬──────┘           │               │
       │                  │               │
       ├─── correct ──────┤               │
       │    answer        │               │
       │                  │ next question │
       ├─── timeout ──────┤               │
       │                  │               │
       └─── !skip ────────┘               │
                                          │
       │ last question                    │
       ▼                                  │
┌─────────────┐                           │
│   ENDING    │───────────────────────────┘
│  (scores)   │
└─────────────┘
```

### 2.5 Class Design

```python
# plugins/trivia/question.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import html


class Difficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(Enum):
    MULTIPLE_CHOICE = "multiple"
    TRUE_FALSE = "boolean"
    FREE_RESPONSE = "free"


@dataclass
class Question:
    """Represents a trivia question."""
    id: str
    category: str
    difficulty: Difficulty
    type: QuestionType
    question: str
    correct_answer: str
    incorrect_answers: List[str]
    
    @property
    def all_answers(self) -> List[str]:
        """All answers shuffled (for multiple choice)."""
        ...
    
    @property
    def answer_map(self) -> dict[str, str]:
        """Map of letter -> answer for multiple choice."""
        ...
    
    def check_answer(self, answer: str) -> bool:
        """
        Check if answer is correct.
        
        Handles:
        - Case insensitivity
        - Letter answers (A, B, C, D)
        - Full text answers
        - Fuzzy matching for free response
        """
        ...
    
    def format_for_display(self) -> str:
        """Format question for chat display."""
        ...
    
    @property
    def points(self) -> int:
        """Base points for this question."""
        return {
            Difficulty.EASY: 10,
            Difficulty.MEDIUM: 20,
            Difficulty.HARD: 30,
        }[self.difficulty]


@dataclass
class Answer:
    """Represents a submitted answer."""
    user: str
    answer: str
    timestamp: float
    correct: bool
    points_awarded: int
```

```python
# plugins/trivia/game.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable
import asyncio


class GameState(Enum):
    IDLE = "idle"
    STARTING = "starting"
    QUESTION_ACTIVE = "question_active"
    ENDING = "ending"


@dataclass
class PlayerScore:
    """Track a player's score in the current game."""
    user: str
    score: int = 0
    correct_answers: int = 0
    total_answers: int = 0
    fastest_time: Optional[float] = None


@dataclass
class GameConfig:
    """Configuration for a trivia game."""
    num_questions: int = 10
    time_per_question: int = 30  # seconds
    start_delay: int = 5  # seconds before first question
    between_questions: int = 3  # seconds between questions
    points_decay: bool = True  # Faster answers = more points
    

class TriviaGame:
    """
    Manages a single trivia game session.
    
    Responsible for:
    - Game state transitions
    - Question progression
    - Score tracking
    - Timer management
    """
    
    def __init__(
        self,
        game_id: str,
        channel: str,
        config: GameConfig,
        questions: List[Question],
        on_state_change: Optional[Callable] = None,
        on_question: Optional[Callable] = None,
        on_answer: Optional[Callable] = None,
        on_timeout: Optional[Callable] = None,
        on_end: Optional[Callable] = None,
    ):
        self.game_id = game_id
        self.channel = channel
        self.config = config
        self.questions = questions
        
        # Callbacks
        self.on_state_change = on_state_change
        self.on_question = on_question
        self.on_answer = on_answer
        self.on_timeout = on_timeout
        self.on_end = on_end
        
        # State
        self.state = GameState.IDLE
        self.current_question_index = 0
        self.current_question: Optional[Question] = None
        self.question_start_time: Optional[float] = None
        self.scores: Dict[str, PlayerScore] = {}
        self.answered_this_question: set[str] = set()
        
        # Timer task
        self._timer_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the game with countdown."""
        ...
    
    async def stop(self) -> None:
        """Stop the game early."""
        ...
    
    async def submit_answer(self, user: str, answer: str) -> Optional[Answer]:
        """
        Process an answer submission.
        
        Returns Answer if processed, None if invalid/duplicate.
        """
        ...
    
    async def skip_question(self) -> None:
        """Skip to next question."""
        ...
    
    async def _next_question(self) -> None:
        """Advance to next question or end game."""
        ...
    
    async def _start_question_timer(self) -> None:
        """Start countdown for current question."""
        ...
    
    async def _on_question_timeout(self) -> None:
        """Called when time runs out on a question."""
        ...
    
    def _calculate_points(self, question: Question, time_taken: float) -> int:
        """Calculate points with optional time decay."""
        ...
    
    def get_leaderboard(self) -> List[PlayerScore]:
        """Get sorted leaderboard."""
        return sorted(
            self.scores.values(),
            key=lambda p: (-p.score, -p.correct_answers)
        )
```

```python
# plugins/trivia/providers/base.py

from abc import ABC, abstractmethod
from typing import List, Optional
from ..question import Question, Difficulty


class QuestionProvider(ABC):
    """Base class for question providers."""
    
    @abstractmethod
    async def fetch_questions(
        self,
        amount: int,
        category: Optional[int] = None,
        difficulty: Optional[Difficulty] = None,
    ) -> List[Question]:
        """Fetch questions from the provider."""
        ...
    
    @abstractmethod
    async def get_categories(self) -> List[dict]:
        """Get available categories."""
        ...
```

```python
# plugins/trivia/providers/opentdb.py

import httpx
import html
from typing import List, Optional
from .base import QuestionProvider
from ..question import Question, Difficulty, QuestionType


class OpenTDBProvider(QuestionProvider):
    """
    Open Trivia Database provider.
    
    API: https://opentdb.com/api.php
    """
    
    BASE_URL = "https://opentdb.com/api.php"
    CATEGORY_URL = "https://opentdb.com/api_category.php"
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._session_token: Optional[str] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def fetch_questions(
        self,
        amount: int,
        category: Optional[int] = None,
        difficulty: Optional[Difficulty] = None,
    ) -> List[Question]:
        """Fetch questions from OpenTDB."""
        client = await self._get_client()
        
        params = {"amount": amount, "type": "multiple"}
        if category:
            params["category"] = category
        if difficulty:
            params["difficulty"] = difficulty.value
        
        response = await client.get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data["response_code"] != 0:
            raise ValueError(f"OpenTDB error: {data['response_code']}")
        
        return [self._parse_question(q) for q in data["results"]]
    
    def _parse_question(self, data: dict) -> Question:
        """Parse OpenTDB response into Question."""
        return Question(
            id=str(hash(data["question"])),
            category=html.unescape(data["category"]),
            difficulty=Difficulty(data["difficulty"]),
            type=QuestionType(data["type"]),
            question=html.unescape(data["question"]),
            correct_answer=html.unescape(data["correct_answer"]),
            incorrect_answers=[
                html.unescape(a) for a in data["incorrect_answers"]
            ],
        )
    
    async def get_categories(self) -> List[dict]:
        """Get available categories from OpenTDB."""
        client = await self._get_client()
        response = await client.get(self.CATEGORY_URL)
        response.raise_for_status()
        return response.json()["trivia_categories"]
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
```

```python
# plugins/trivia/plugin.py

import uuid
from typing import Dict, Optional
from lib.plugin.base import PluginBase
from .game import TriviaGame, GameConfig, GameState
from .providers.opentdb import OpenTDBProvider


class TriviaPlugin(PluginBase):
    """
    Trivia game plugin.
    
    Commands:
        !trivia start [N] - Start game with N questions (default 10)
        !trivia stop - End current game
        !trivia answer <answer> / !a <answer> - Submit answer
        !trivia skip - Skip current question
    """
    
    NAME = "trivia"
    VERSION = "1.0.0"
    DESCRIPTION = "Interactive trivia game"
    
    def __init__(self, nats_client, config: dict = None):
        super().__init__(nats_client, config)
        self.provider = OpenTDBProvider()
        self.active_games: Dict[str, TriviaGame] = {}  # channel -> game
    
    async def setup(self) -> None:
        """Register command handlers."""
        await self.subscribe("rosey.command.trivia.start", self._handle_start)
        await self.subscribe("rosey.command.trivia.stop", self._handle_stop)
        await self.subscribe("rosey.command.trivia.answer", self._handle_answer)
        await self.subscribe("rosey.command.trivia.skip", self._handle_skip)
        
        self.logger.info(f"{self.NAME} plugin loaded")
    
    async def teardown(self) -> None:
        """Cleanup games and provider."""
        # Stop all active games
        for game in list(self.active_games.values()):
            await game.stop()
        self.active_games.clear()
        
        # Close HTTP client
        await self.provider.close()
        
        self.logger.info(f"{self.NAME} plugin unloaded")
    
    async def _handle_start(self, msg) -> None:
        """Handle !trivia start [N]."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        
        # Check for existing game
        if channel in self.active_games:
            game = self.active_games[channel]
            if game.state != GameState.IDLE:
                return await self._reply_error(
                    msg, "A game is already in progress! Use !trivia stop to end it."
                )
        
        # Parse number of questions
        args = data.get("args", "").strip()
        num_questions = 10
        if args:
            try:
                num_questions = int(args)
                num_questions = max(1, min(50, num_questions))  # Clamp 1-50
            except ValueError:
                pass
        
        # Fetch questions
        try:
            questions = await self.provider.fetch_questions(num_questions)
        except Exception as e:
            self.logger.error(f"Failed to fetch questions: {e}")
            return await self._reply_error(
                msg, "Couldn't fetch trivia questions. Try again later."
            )
        
        # Create game
        config = GameConfig(
            num_questions=len(questions),
            time_per_question=self.config.get("time_per_question", 30),
            start_delay=self.config.get("start_delay", 5),
            between_questions=self.config.get("between_questions", 3),
        )
        
        game = TriviaGame(
            game_id=str(uuid.uuid4()),
            channel=channel,
            config=config,
            questions=questions,
            on_question=self._on_question,
            on_answer=self._on_answer,
            on_timeout=self._on_timeout,
            on_end=self._on_game_end,
        )
        
        self.active_games[channel] = game
        
        # Start game
        await game.start()
        
        # Emit event
        await self.publish("trivia.game.started", {
            "event": "trivia.game.started",
            "channel": channel,
            "game_id": game.game_id,
            "started_by": user,
            "num_questions": len(questions),
        })
    
    async def _handle_stop(self, msg) -> None:
        """Handle !trivia stop."""
        ...
    
    async def _handle_answer(self, msg) -> None:
        """Handle !trivia answer <answer> / !a <answer>."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        user = data["user"]
        answer = data.get("args", "").strip()
        
        if not answer:
            return await self._reply_usage(msg, "answer <your answer>")
        
        game = self.active_games.get(channel)
        if not game or game.state != GameState.QUESTION_ACTIVE:
            return await self._reply_error(msg, "No active question to answer!")
        
        result = await game.submit_answer(user, answer)
        
        if result is None:
            # Already answered or invalid
            return
        
        # Response handled by game callback
    
    async def _handle_skip(self, msg) -> None:
        """Handle !trivia skip."""
        ...
    
    async def _on_question(self, game: TriviaGame, question: Question) -> None:
        """Called when a new question is asked."""
        formatted = question.format_for_display()
        index = game.current_question_index + 1
        total = len(game.questions)
        
        message = (
            f"📝 Question {index}/{total} "
            f"({question.difficulty.value.title()} - {question.category}):\n\n"
            f"{formatted}\n\n"
            f"⏱️ {game.config.time_per_question} seconds! Use !a <answer>"
        )
        
        await self._send_to_channel(game.channel, message)
        
        await self.publish("trivia.question.asked", {
            "event": "trivia.question.asked",
            "channel": game.channel,
            "game_id": game.game_id,
            "question_number": index,
        })
    
    async def _on_answer(self, game: TriviaGame, answer: Answer) -> None:
        """Called when someone answers."""
        if answer.correct:
            message = (
                f"✅ Correct! {answer.user} got it in "
                f"{answer.timestamp:.1f}s! (+{answer.points_awarded} points)"
            )
            event = "trivia.answer.correct"
        else:
            message = f"❌ {answer.user} - that's not it!"
            event = "trivia.answer.incorrect"
        
        await self._send_to_channel(game.channel, message)
        await self.publish(event, {
            "event": event,
            "channel": game.channel,
            "game_id": game.game_id,
            "user": answer.user,
        })
    
    async def _on_timeout(self, game: TriviaGame, question: Question) -> None:
        """Called when question times out."""
        message = f"⏰ Time's up! The answer was: **{question.correct_answer}**"
        await self._send_to_channel(game.channel, message)
        
        await self.publish("trivia.question.timeout", {
            "event": "trivia.question.timeout",
            "channel": game.channel,
            "game_id": game.game_id,
        })
    
    async def _on_game_end(self, game: TriviaGame) -> None:
        """Called when game ends."""
        leaderboard = game.get_leaderboard()
        
        if leaderboard:
            lines = ["🏆 Game Over!\n"]
            medals = ["🥇", "🥈", "🥉"]
            
            for i, player in enumerate(leaderboard[:10]):
                medal = medals[i] if i < 3 else f"{i+1}."
                lines.append(f"{medal} {player.user} - {player.score} points")
            
            message = "\n".join(lines)
        else:
            message = "🏆 Game Over! No one scored any points."
        
        await self._send_to_channel(game.channel, message)
        
        await self.publish("trivia.game.ended", {
            "event": "trivia.game.ended",
            "channel": game.channel,
            "game_id": game.game_id,
            "scores": [
                {"user": p.user, "score": p.score}
                for p in leaderboard
            ],
        })
        
        # Cleanup
        del self.active_games[game.channel]
```

### 2.6 Configuration

```json
{
  "time_per_question": 30,
  "start_delay": 5,
  "between_questions": 3,
  "max_questions": 50,
  "default_questions": 10,
  "points_decay": true,
  "emit_events": true
}
```

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `time_per_question` | int | 30 | Seconds to answer |
| `start_delay` | int | 5 | Seconds before first question |
| `between_questions` | int | 3 | Seconds between questions |
| `max_questions` | int | 50 | Max questions per game |
| `default_questions` | int | 10 | Default number of questions |
| `points_decay` | bool | true | Faster = more points |
| `emit_events` | bool | true | Emit NATS events |

---

## 3. Implementation Steps

### Step 1: Create Plugin Structure (30 minutes)

1. Create `plugins/trivia/` directory
2. Create all files with docstrings
3. Create `config.json` with defaults
4. Create provider directory structure

### Step 2: Implement Question Model (1.5 hours)

1. Implement `Question` dataclass
2. Implement `check_answer()` with fuzzy matching
3. Implement `format_for_display()` for multiple choice
4. Implement answer mapping (A, B, C, D)
5. Write unit tests for answer checking

### Step 3: Implement OpenTDB Provider (1.5 hours)

1. Implement `OpenTDBProvider` class
2. Implement HTTP client management
3. Implement question fetching
4. Implement HTML entity decoding
5. Implement category fetching
6. Write tests with mocked HTTP

### Step 4: Implement Game State Machine (2.5 hours)

1. Implement `GameState` enum
2. Implement `TriviaGame` class
3. Implement state transitions
4. Implement timer management with asyncio
5. Implement score calculation
6. Implement callbacks
7. Write comprehensive state machine tests

### Step 5: Implement Plugin (2 hours)

1. Implement `setup()` with subscriptions
2. Implement `_handle_start()` with question fetching
3. Implement `_handle_answer()` with answer processing
4. Implement `_handle_stop()` and `_handle_skip()`
5. Implement all callbacks
6. Wire up event emission

### Step 6: Integration Testing (1.5 hours)

1. Test full game flow: start → questions → answers → end
2. Test concurrent games (different channels)
3. Test timeout behavior
4. Test multiple players
5. Test edge cases

### Step 7: Documentation (30 minutes)

1. Write README.md with examples
2. Document game flow
3. Document configuration

---

## 4. Test Cases

### 4.1 Question Model Tests

| Test | Validation |
|------|------------|
| Check "A" against first answer | Returns correct bool |
| Check "Paris" against "Paris" | Returns True (case insensitive) |
| Check "paris" against "Paris" | Returns True |
| Check "Parris" against "Paris" | Returns True (fuzzy) |
| Format multiple choice | Shows A) B) C) D) |
| Points for easy | Returns 10 |
| Points for medium | Returns 20 |
| Points for hard | Returns 30 |

### 4.2 Provider Tests

| Scenario | Expected |
|----------|----------|
| Fetch 10 questions | Returns 10 Question objects |
| Parse HTML entities | Properly decoded |
| API error | Raises appropriate exception |
| Invalid amount | Returns error or empty |
| Network timeout | Raises timeout error |

### 4.3 Game State Machine Tests

| Scenario | Expected State |
|----------|----------------|
| Initial state | IDLE |
| After start() | STARTING |
| After start delay | QUESTION_ACTIVE |
| Correct answer | Still QUESTION_ACTIVE |
| Last question answered | ENDING |
| After stop() | IDLE |
| Timeout without answer | Next question or ENDING |

### 4.4 Score Calculation Tests

| Scenario | Expected Points |
|----------|-----------------|
| Easy, fast answer | 10-15 (with decay) |
| Easy, slow answer | 5-10 (with decay) |
| Hard, fast answer | 30-45 (with decay) |
| No decay configured | Base points only |

### 4.5 Integration Tests

| Scenario | Expected |
|----------|----------|
| `!trivia start` | Starts game, asks first question |
| `!trivia start 5` | Starts with 5 questions |
| `!a B` | Processes answer |
| `!a Paris` | Processes text answer |
| Correct answer | Updates score, moves to next |
| Timeout | Shows answer, moves to next |
| `!trivia skip` | Skips to next question |
| `!trivia stop` | Ends game, shows scores |
| Last question | Shows final leaderboard |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| Start during active game | "A game is already in progress!" |
| Answer with no game | "No active question to answer!" |
| Invalid question count | Use default (10) |
| Empty answer | "Usage: !a <your answer>" |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| OpenTDB unavailable | "Couldn't fetch questions. Try again later." |
| Network timeout | Log, inform user |
| Invalid API response | Log, use fallback |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!trivia start` begins a game with 10 questions
- [ ] `!trivia start 5` begins with 5 questions
- [ ] Questions display with multiple choice options
- [ ] `!a <letter>` submits answer by letter
- [ ] `!a <answer>` submits answer by text
- [ ] Correct answers award points
- [ ] Timer enforced (30 seconds default)
- [ ] Timeout shows correct answer
- [ ] `!trivia skip` skips current question
- [ ] `!trivia stop` ends game early
- [ ] Final leaderboard displayed

### 6.2 Technical

- [ ] Plugin loads without errors
- [ ] State machine transitions correctly
- [ ] Timers work reliably
- [ ] Events emitted correctly
- [ ] Test coverage > 85%

### 6.3 Documentation

- [ ] README.md with usage examples
- [ ] Game flow documented
- [ ] Configuration documented

---

## 7. Sample Interactions

```
User: !trivia start
Rosey: 🎯 Trivia starting! 10 questions, 30 seconds each.
       First question in 5 seconds...

[5 seconds later]
Rosey: 📝 Question 1/10 (Easy - General Knowledge):

       What is the capital of France?

       A) London  B) Paris  C) Berlin  D) Madrid

       ⏱️ 30 seconds! Use !a <answer>

Player1: !a B
Rosey: ✅ Correct! Player1 got it in 3.2s! (+12 points)

[3 seconds later]
Rosey: 📝 Question 2/10 (Medium - Science):

       What planet is known as the Red Planet?

       A) Venus  B) Jupiter  C) Mars  D) Saturn

       ⏱️ 30 seconds! Use !a <answer>

Player2: !a Mars
Rosey: ✅ Correct! Player2 got it in 5.1s! (+22 points)

[... more questions ...]

[After last question]
Rosey: 🏆 Game Over!

       🥇 Player1 - 95 points
       🥈 Player2 - 82 points
       🥉 Player3 - 45 points

User: !trivia stop
Rosey: ⏹️ Game stopped by User.

       🏆 Final Scores:
       🥇 Player1 - 45 points
```

---

## 8. Future Enhancements (Sortie 6)

These are **NOT** in scope for Sortie 5:

- Persistent scoring database
- All-time leaderboards
- User statistics (games played, accuracy)
- Category selection (`!trivia start science`)
- Custom question sets
- Difficulty selection

---

## 9. Checklist

### Pre-Implementation
- [ ] Test OpenTDB API manually
- [ ] Review asyncio timer patterns
- [ ] Design state machine on paper

### Implementation
- [ ] Create plugin directory structure
- [ ] Implement Question model
- [ ] Implement OpenTDB provider
- [ ] Implement TriviaGame state machine
- [ ] Implement TriviaPlugin
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing with real games
- [ ] Verify timer accuracy
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add trivia plugin foundation

- Implement interactive trivia game
- Add OpenTDB question provider
- Add game state machine with timers
- Support multiple-choice and text answers
- Per-round scoring with time bonus

Implements: SPEC-Sortie-5-TriviaFoundation.md
Related: PRD-Funny-Games.md
```
