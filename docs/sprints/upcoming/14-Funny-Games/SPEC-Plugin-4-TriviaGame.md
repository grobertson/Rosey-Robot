# Sprint 9 - Plugin 4: Trivia Game ⚡

**Complexity:** ⭐⭐⭐⭐☆ (Complex)  
**Effort:** 6 hours  
**Priority:** ⚡ HIGH - STAKEHOLDER REQUESTED  
**Status:** Specification Complete

## Overview

The Trivia Game plugin implements an interactive multiplayer trivia game with timed questions, scoring, and persistent statistics. This is a **STAKEHOLDER PRIORITY** feature that validates complex state management, async timers, event bus integration, and concurrency patterns.

### Purpose

- **User Value:** ⚡ Interactive trivia games with friends in chat
- **Architecture Value:** Validates state machines, timers, event bus, concurrency
- **Learning Value:** Complex plugin with multiple moving parts

### Features

- Timed questions (30-second default)
- Multiple choice and text answer types
- Point scoring with fast-answer bonus
- Concurrent games per channel
- Persistent player statistics
- Event bus integration (game events)
- Question database (JSON)
- Leaderboard
- Skip voting system

## Commands

### `!trivia start`

Start a new trivia game.

**Examples:**

```bash
!trivia start
🎮 Trivia Game Starting in 5 seconds!
Type !trivia answer <choice> to play

Question 1/10:
❓ What is the capital of France?
  A) London
  B) Paris
  C) Berlin
  D) Madrid

(30 seconds to answer)
```

### `!trivia answer <choice>`

Submit an answer to the current question.

**Examples:**

```bash
!trivia answer B
✅ Correct, alice! +10 points (answered in 5s, +2 bonus!)

!trivia answer A
❌ Incorrect, bob. The answer was B
```

### `!trivia skip`

Vote to skip the current question.

**Examples:**

```bash
!trivia skip
alice voted to skip (1/2 votes needed)

!trivia skip
bob voted to skip (2/2 votes needed)
⏭️ Question skipped! Moving to next question...
```

### `!trivia stop`

Stop the current game (admin only).

**Examples:**

```bash
!trivia stop
🛑 Trivia game stopped by admin

📊 Final Scores:
  1. alice: 45 points (4/5 correct)
  2. bob: 20 points (2/5 correct)
```

### `!trivia stats [username]`

View player statistics.

**Examples:**

```bash
!trivia stats alice
📊 Trivia Stats for alice:
  Games played: 12
  Total score: 450 points
  Correct answers: 85/120 (71%)
  Best game: 75 points

!trivia stats
📊 Your Trivia Stats:
  Games played: 5
  Total score: 180 points
  Correct answers: 32/50 (64%)
  Best game: 50 points
```

### `!trivia leaderboard`

View top players.

**Examples:**

```bash
!trivia leaderboard
🏆 Trivia Leaderboard:
  1. alice - 450 points (12 games)
  2. charlie - 380 points (10 games)
  3. bob - 180 points (5 games)
  4. david - 120 points (3 games)
  5. eve - 90 points (2 games)
```

## Configuration

File: `plugins/trivia/config.json`

```json
{
  "question_timeout": 30,
  "answer_reveal_duration": 5,
  "questions_per_game": 10,
  "fast_answer_threshold": 10,
  "fast_answer_bonus": 2,
  "skip_votes_required": 0.5,
  "question_database": "plugins/trivia/questions.json"
}
```

**Configuration Options:**

- `question_timeout`: Seconds to answer (default: 30)
- `answer_reveal_duration`: Seconds to show answer before next question (default: 5)
- `questions_per_game`: Number of questions per game (default: 10)
- `fast_answer_threshold`: Seconds for fast answer bonus (default: 10)
- `fast_answer_bonus`: Bonus points for fast answers (default: 2)
- `skip_votes_required`: Fraction of players needed to skip (default: 0.5)
- `question_database`: Path to questions JSON file

## Question Database Format

File: `plugins/trivia/questions.json`

```json
[
  {
    "id": "geog_001",
    "question": "What is the capital of France?",
    "type": "multiple_choice",
    "choices": ["London", "Paris", "Berlin", "Madrid"],
    "correct_answer": "Paris",
    "category": "Geography",
    "difficulty": "easy",
    "points": 10
  },
  {
    "id": "hist_001",
    "question": "In what year did World War II end?",
    "type": "text",
    "correct_answer": "1945",
    "category": "History",
    "difficulty": "medium",
    "points": 15
  }
]
```

**Question Types:**

- `multiple_choice`: A/B/C/D choices
- `text`: Free-form text answer (case-insensitive)

## Game States

The trivia game uses a state machine:

```
IDLE → STARTING → QUESTION_ACTIVE → ANSWER_SHOWN → [repeat] → FINISHED → IDLE
```

**State Descriptions:**

- `IDLE`: No game running
- `STARTING`: Game starting countdown (5 seconds)
- `QUESTION_ACTIVE`: Question displayed, waiting for answers
- `ANSWER_SHOWN`: Answer revealed, brief pause before next question
- `FINISHED`: Game complete, showing final scores

## Event Bus Integration

The trivia plugin publishes events:

**Event: `trivia.game_started`**

```python
{
    'channel': 'channel_name',
    'started_by': 'username',
    'questions_count': 10
}
```

**Event: `trivia.question_asked`**

```python
{
    'question_id': 'geog_001',
    'question_number': 1,
    'total_questions': 10,
    'category': 'Geography',
    'difficulty': 'easy'
}
```

**Event: `trivia.answer_submitted`**

```python
{
    'username': 'alice',
    'correct': True,
    'points': 12,
    'answer_time': 5.2
}
```

**Event: `trivia.game_finished`**

```python
{
    'channel': 'channel_name',
    'forced': False,
    'scores': {
        'alice': {'score': 45, 'correct': 4, 'answered': 5},
        'bob': {'score': 20, 'correct': 2, 'answered': 5}
    }
}
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS trivia_stats (
    username TEXT PRIMARY KEY,
    games_played INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    total_answers INTEGER DEFAULT 0,
    best_game INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trivia_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    score INTEGER NOT NULL,
    questions_answered INTEGER NOT NULL,
    correct_answers INTEGER NOT NULL,
    played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Implementation

### File Structure

```
plugins/trivia/
├── __init__.py
├── plugin.py
├── game.py
├── questions.json
└── config.json
```

### Code: `plugins/trivia/__init__.py`

```python
"""Trivia game plugin for cytube-bot."""

from .plugin import TriviaPlugin

__all__ = ['TriviaPlugin']
```

### Code: `plugins/trivia/game.py`

```python
"""
Trivia Game State Machine

Manages game state, players, questions, and scoring.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set


class GameState(Enum):
    """Trivia game states."""
    IDLE = "idle"
    STARTING = "starting"
    QUESTION_ACTIVE = "question_active"
    ANSWER_SHOWN = "answer_shown"
    FINISHED = "finished"


@dataclass
class Question:
    """A trivia question."""
    id: str
    question: str
    type: str  # "multiple_choice" or "text"
    correct_answer: str
    category: str
    difficulty: str
    points: int
    choices: Optional[List[str]] = None


@dataclass
class PlayerScore:
    """Player score tracking."""
    username: str
    score: int = 0
    correct: int = 0
    answered: int = 0


@dataclass
class TriviaGame:
    """Trivia game state."""
    channel: str
    questions: List[Question]
    state: GameState = GameState.IDLE
    current_question: Optional[Question] = None
    question_number: int = 0
    players: Dict[str, PlayerScore] = field(default_factory=dict)
    answered_users: Set[str] = field(default_factory=set)
    skip_votes: Set[str] = field(default_factory=set)
    question_start_time: Optional[datetime] = None
    timeout_task: Optional[asyncio.Task] = None
    
    def add_player(self, username: str):
        """Add a player to the game."""
        if username not in self.players:
            self.players[username] = PlayerScore(username)
    
    def record_answer(self, username: str, correct: bool, points: int):
        """Record a player's answer."""
        player = self.players.get(username)
        if player:
            player.answered += 1
            if correct:
                player.correct += 1
                player.score += points
    
    def add_skip_vote(self, username: str):
        """Add a skip vote."""
        self.skip_votes.add(username)
    
    def reset_question_state(self):
        """Reset state for next question."""
        self.answered_users.clear()
        self.skip_votes.clear()
        self.question_start_time = None
        if self.timeout_task:
            self.timeout_task.cancel()
            self.timeout_task = None
```

### Code: `plugins/trivia/plugin.py`

```python
"""
Trivia Game Plugin

Interactive multiplayer trivia with timed questions and scoring.
"""

import json
import sqlite3
import asyncio
import random
from datetime import datetime
from typing import Dict, Optional, List
from pathlib import Path

from lib.plugin import Plugin
from lib.channel import Channel
from lib.user import User
from .game import TriviaGame, GameState, Question, PlayerScore


class TriviaPlugin(Plugin):
    """Plugin for multiplayer trivia games."""
    
    def __init__(self, manager):
        """Initialize the trivia plugin."""
        super().__init__(manager)
        self.name = "trivia"
        self.version = "1.0.0"
        self.description = "Interactive trivia game with scoring"
        self.author = "cytube-bot"
        
        # Configuration
        self.question_timeout = 30
        self.answer_reveal_duration = 5
        self.questions_per_game = 10
        self.fast_answer_threshold = 10
        self.fast_answer_bonus = 2
        self.skip_votes_required = 0.5
        
        # Active games per channel
        self.games: Dict[str, TriviaGame] = {}
        
        # Question database
        self.questions: List[Question] = []
        
        # Database connection
        self.db = None
    
    async def setup(self):
        """Set up the plugin."""
        # Load configuration
        config = self.get_config()
        self.question_timeout = config.get('question_timeout', 30)
        self.answer_reveal_duration = config.get('answer_reveal_duration', 5)
        self.questions_per_game = config.get('questions_per_game', 10)
        self.fast_answer_threshold = config.get('fast_answer_threshold', 10)
        self.fast_answer_bonus = config.get('fast_answer_bonus', 2)
        self.skip_votes_required = config.get('skip_votes_required', 0.5)
        
        # Load questions
        question_db_path = config.get('question_database', 'plugins/trivia/questions.json')
        await self._load_questions(question_db_path)
        
        # Initialize database
        await self._init_database()
        
        # Register commands
        await self.register_command('trivia', self._handle_trivia)
        
        self.logger.info(f"Trivia plugin loaded with {len(self.questions)} questions")
    
    async def teardown(self):
        """Clean up plugin resources."""
        # Stop all active games
        for game in list(self.games.values()):
            if game.timeout_task:
                game.timeout_task.cancel()
        self.games.clear()
        
        # Close database
        if self.db:
            self.db.close()
            self.db = None
        
        self.logger.info(f"Trivia plugin unloaded")
    
    async def _init_database(self):
        """Initialize SQLite database."""
        db_path = self.get_storage_path('trivia.db')
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        
        cursor = self.db.cursor()
        
        # Player statistics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trivia_stats (
                username TEXT PRIMARY KEY,
                games_played INTEGER DEFAULT 0,
                total_score INTEGER DEFAULT 0,
                correct_answers INTEGER DEFAULT 0,
                total_answers INTEGER DEFAULT 0,
                best_game INTEGER DEFAULT 0
            )
        ''')
        
        # Game history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trivia_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                score INTEGER NOT NULL,
                questions_answered INTEGER NOT NULL,
                correct_answers INTEGER NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.db.commit()
    
    async def _load_questions(self, path: str):
        """Load questions from JSON file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.questions = [
                Question(
                    id=q['id'],
                    question=q['question'],
                    type=q['type'],
                    correct_answer=q['correct_answer'],
                    category=q['category'],
                    difficulty=q['difficulty'],
                    points=q['points'],
                    choices=q.get('choices')
                )
                for q in data
            ]
        except Exception as e:
            self.logger.error(f"Failed to load questions: {e}")
            raise
    
    async def _handle_trivia(self, channel: Channel, user: User, args: str):
        """Handle trivia commands."""
        if not args.strip():
            await self._show_help(channel)
            return
        
        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""
        
        if subcommand == "start":
            await self._handle_start(channel, user)
        elif subcommand == "answer":
            await self._handle_answer(channel, user, subargs)
        elif subcommand == "skip":
            await self._handle_skip(channel, user)
        elif subcommand == "stop":
            await self._handle_stop(channel, user)
        elif subcommand == "stats":
            await self._handle_stats(channel, user, subargs)
        elif subcommand == "leaderboard":
            await self._handle_leaderboard(channel)
        else:
            await channel.send_message(f"❌ Unknown command: {subcommand}")
            await self._show_help(channel)
    
    async def _handle_start(self, channel: Channel, user: User):
        """Start a new trivia game."""
        channel_name = channel.name
        
        # Check if game already running
        if channel_name in self.games:
            await channel.send_message("❌ A trivia game is already in progress!")
            return
        
        # Select random questions
        selected = random.sample(self.questions, min(self.questions_per_game, len(self.questions)))
        
        # Create game
        game = TriviaGame(
            channel=channel_name,
            questions=selected,
            state=GameState.STARTING
        )
        self.games[channel_name] = game
        
        # Publish event
        await self.publish_event('trivia.game_started', {
            'channel': channel_name,
            'started_by': user.username,
            'questions_count': len(selected)
        })
        
        # Starting countdown
        await channel.send_message("🎮 Trivia Game Starting in 5 seconds!")
        await channel.send_message("Type !trivia answer <choice> to play")
        await asyncio.sleep(5)
        
        # Start first question
        await self._next_question(channel, game)
    
    async def _next_question(self, channel: Channel, game: TriviaGame):
        """Display next question."""
        game.question_number += 1
        
        if game.question_number > len(game.questions):
            await self._finish_game(channel, game)
            return
        
        # Get question
        question = game.questions[game.question_number - 1]
        game.current_question = question
        game.state = GameState.QUESTION_ACTIVE
        game.reset_question_state()
        game.question_start_time = datetime.now()
        
        # Publish event
        await self.publish_event('trivia.question_asked', {
            'question_id': question.id,
            'question_number': game.question_number,
            'total_questions': len(game.questions),
            'category': question.category,
            'difficulty': question.difficulty
        })
        
        # Display question
        await channel.send_message(f"\nQuestion {game.question_number}/{len(game.questions)}:")
        await channel.send_message(f"❓ {question.question}")
        
        if question.type == "multiple_choice":
            choices = ["A", "B", "C", "D"]
            for i, choice in enumerate(question.choices):
                await channel.send_message(f"  {choices[i]}) {choice}")
        
        await channel.send_message(f"\n({self.question_timeout} seconds to answer)")
        
        # Start timeout timer
        game.timeout_task = asyncio.create_task(self._question_timeout(channel, game))
    
    async def _question_timeout(self, channel: Channel, game: TriviaGame):
        """Handle question timeout."""
        try:
            await asyncio.sleep(self.question_timeout)
            
            if game.state == GameState.QUESTION_ACTIVE:
                await channel.send_message("⏰ Time's up!")
                await self._reveal_answer(channel, game)
        except asyncio.CancelledError:
            pass
    
    async def _handle_answer(self, channel: Channel, user: User, answer: str):
        """Handle answer submission."""
        game = self.games.get(channel.name)
        
        if not game or game.state != GameState.QUESTION_ACTIVE:
            await channel.send_message("❌ No active question")
            return
        
        # Check if already answered
        if user.username in game.answered_users:
            return  # Silently ignore
        
        # Add player
        game.add_player(user.username)
        game.answered_users.add(user.username)
        
        # Check answer
        correct = self._check_answer(game.current_question, answer.strip())
        
        # Calculate points
        points = 0
        bonus = 0
        if correct:
            points = game.current_question.points
            
            # Fast answer bonus
            answer_time = (datetime.now() - game.question_start_time).total_seconds()
            if answer_time < self.fast_answer_threshold:
                bonus = self.fast_answer_bonus
                points += bonus
        
        # Record answer
        game.record_answer(user.username, correct, points)
        
        # Publish event
        await self.publish_event('trivia.answer_submitted', {
            'username': user.username,
            'correct': correct,
            'points': points,
            'answer_time': answer_time
        })
        
        # Send feedback
        if correct:
            answer_time_str = f" (answered in {int(answer_time)}s"
            if bonus > 0:
                answer_time_str += f", +{bonus} bonus!"
            answer_time_str += ")"
            await channel.send_message(f"✅ Correct, {user.username}! +{points} points{answer_time_str}")
        else:
            await channel.send_message(f"❌ Incorrect, {user.username}.")
        
        # If everyone answered, reveal immediately
        if len(game.answered_users) >= len(game.players):
            if game.timeout_task:
                game.timeout_task.cancel()
            await self._reveal_answer(channel, game)
    
    def _check_answer(self, question: Question, answer: str) -> bool:
        """Check if answer is correct."""
        if question.type == "multiple_choice":
            # Convert A/B/C/D to choice text
            choices_map = {"A": 0, "B": 1, "C": 2, "D": 3}
            if answer.upper() in choices_map:
                choice_idx = choices_map[answer.upper()]
                if choice_idx < len(question.choices):
                    answer = question.choices[choice_idx]
            
            return answer.lower() == question.correct_answer.lower()
        else:
            # Text answer (case-insensitive)
            return answer.lower() == question.correct_answer.lower()
    
    async def _reveal_answer(self, channel: Channel, game: TriviaGame):
        """Reveal the answer and move to next question."""
        if game.state != GameState.QUESTION_ACTIVE:
            return
        
        game.state = GameState.ANSWER_SHOWN
        
        # Show answer
        question = game.current_question
        if question.type == "multiple_choice":
            correct_idx = question.choices.index(question.correct_answer)
            choices = ["A", "B", "C", "D"]
            await channel.send_message(f"✅ The answer was {choices[correct_idx]}: {question.correct_answer}")
        else:
            await channel.send_message(f"✅ The answer was: {question.correct_answer}")
        
        # Brief pause
        await asyncio.sleep(self.answer_reveal_duration)
        
        # Next question
        await self._next_question(channel, game)
    
    async def _handle_skip(self, channel: Channel, user: User):
        """Handle skip vote."""
        game = self.games.get(channel.name)
        
        if not game or game.state != GameState.QUESTION_ACTIVE:
            await channel.send_message("❌ No active question")
            return
        
        # Add vote
        game.add_skip_vote(user.username)
        
        # Check if enough votes
        votes_needed = max(1, int(len(game.players) * self.skip_votes_required))
        votes_current = len(game.skip_votes)
        
        if votes_current >= votes_needed:
            await channel.send_message(f"⏭️ Question skipped! Moving to next question...")
            if game.timeout_task:
                game.timeout_task.cancel()
            await self._reveal_answer(channel, game)
        else:
            await channel.send_message(f"{user.username} voted to skip ({votes_current}/{votes_needed} votes needed)")
    
    async def _handle_stop(self, channel: Channel, user: User):
        """Stop the current game (admin only)."""
        game = self.games.get(channel.name)
        
        if not game:
            await channel.send_message("❌ No game in progress")
            return
        
        # TODO: Check if user is admin
        
        await channel.send_message(f"🛑 Trivia game stopped by {user.username}")
        await self._finish_game(channel, game, forced=True)
    
    async def _finish_game(self, channel: Channel, game: TriviaGame, forced: bool = False):
        """Finish the game and show results."""
        game.state = GameState.FINISHED
        
        # Cancel timeout if active
        if game.timeout_task:
            game.timeout_task.cancel()
        
        # Show final scores
        await channel.send_message("\n📊 Final Scores:")
        
        sorted_players = sorted(game.players.values(), key=lambda p: p.score, reverse=True)
        for i, player in enumerate(sorted_players, 1):
            await channel.send_message(
                f"  {i}. {player.username}: {player.score} points ({player.correct}/{player.answered} correct)"
            )
        
        # Save statistics
        await self._save_player_stats(game)
        
        # Publish event
        await self.publish_event('trivia.game_finished', {
            'channel': channel.name,
            'forced': forced,
            'scores': {
                p.username: {
                    'score': p.score,
                    'correct': p.correct,
                    'answered': p.answered
                }
                for p in game.players.values()
            }
        })
        
        # Remove game
        del self.games[channel.name]
    
    async def _save_player_stats(self, game: TriviaGame):
        """Save player statistics to database."""
        cursor = self.db.cursor()
        
        for player in game.players.values():
            # Update stats
            cursor.execute('''
                INSERT INTO trivia_stats (username, games_played, total_score, correct_answers, total_answers, best_game)
                VALUES (?, 1, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    games_played = games_played + 1,
                    total_score = total_score + excluded.total_score,
                    correct_answers = correct_answers + excluded.correct_answers,
                    total_answers = total_answers + excluded.total_answers,
                    best_game = MAX(best_game, excluded.best_game)
            ''', (player.username, player.score, player.correct, player.answered, player.score))
            
            # Add to history
            cursor.execute('''
                INSERT INTO trivia_history (username, score, questions_answered, correct_answers)
                VALUES (?, ?, ?, ?)
            ''', (player.username, player.score, player.answered, player.correct))
        
        self.db.commit()
    
    async def _handle_stats(self, channel: Channel, user: User, username: str):
        """Show player statistics."""
        target = username.strip() if username.strip() else user.username
        
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT * FROM trivia_stats WHERE username = ?',
            (target,)
        )
        row = cursor.fetchone()
        
        if not row:
            await channel.send_message(f"📊 No trivia stats for {target}")
            return
        
        accuracy = (row['correct_answers'] / row['total_answers'] * 100) if row['total_answers'] > 0 else 0
        
        message = f"📊 Trivia Stats for {target}:\n"
        message += f"  Games played: {row['games_played']}\n"
        message += f"  Total score: {row['total_score']} points\n"
        message += f"  Correct answers: {row['correct_answers']}/{row['total_answers']} ({accuracy:.0f}%)\n"
        message += f"  Best game: {row['best_game']} points"
        
        await channel.send_message(message)
    
    async def _handle_leaderboard(self, channel: Channel):
        """Show top players."""
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT username, total_score, games_played
            FROM trivia_stats
            ORDER BY total_score DESC
            LIMIT 5
        ''')
        rows = cursor.fetchall()
        
        if not rows:
            await channel.send_message("🏆 No players on leaderboard yet")
            return
        
        await channel.send_message("🏆 Trivia Leaderboard:")
        for i, row in enumerate(rows, 1):
            await channel.send_message(
                f"  {i}. {row['username']} - {row['total_score']} points ({row['games_played']} games)"
            )
    
    async def _show_help(self, channel: Channel):
        """Show command help."""
        await channel.send_message("Trivia Commands:")
        await channel.send_message("  !trivia start - Start a new game")
        await channel.send_message("  !trivia answer <choice> - Submit an answer")
        await channel.send_message("  !trivia skip - Vote to skip question")
        await channel.send_message("  !trivia stop - Stop the game (admin)")
        await channel.send_message("  !trivia stats [user] - View statistics")
        await channel.send_message("  !trivia leaderboard - View top players")
```

## Testing Strategy

### Unit Tests

```python
"""Tests for trivia plugin."""

import pytest
from plugins.trivia.game import TriviaGame, GameState, Question


def test_game_state_machine():
    """Test game state transitions."""
    game = TriviaGame(channel="test", questions=[])
    
    assert game.state == GameState.IDLE
    
    game.state = GameState.STARTING
    assert game.state == GameState.STARTING


def test_player_scoring():
    """Test player score tracking."""
    game = TriviaGame(channel="test", questions=[])
    
    game.add_player("alice")
    game.record_answer("alice", correct=True, points=10)
    
    assert game.players["alice"].score == 10
    assert game.players["alice"].correct == 1
```

### Integration Tests

```python
"""Integration tests for trivia plugin."""

import pytest


@pytest.mark.asyncio
async def test_full_game(bot, channel):
    """Test complete game flow."""
    # Start game
    await channel.send_chat("!trivia start")
    
    # Wait for question
    response = await channel.wait_for_message(timeout=10.0)
    assert "Question 1/" in response
    
    # Answer question
    await channel.send_chat("!trivia answer A")
    
    # Should get feedback
    response = await channel.wait_for_message(timeout=2.0)
    assert "Correct" in response or "Incorrect" in response
```

## Architecture Validation

This plugin validates:

- ✅ **State machine:** GameState enum with transitions
- ✅ **Async timers:** Question timeout with asyncio
- ✅ **Event bus (publish):** 4 event types published
- ✅ **Storage adapter:** SQLite for statistics
- ✅ **Concurrency:** Per-channel game instances
- ✅ **Complex lifecycle:** Setup/teardown with cleanup
- ✅ **Configuration:** Multiple config options

---

**Estimated Implementation:** 6 hours  
**Lines of Code:** ~800 (200 game + 600 plugin)  
**External Dependencies:** None  
**Architecture Features Validated:** 7/16

⚡ **STAKEHOLDER PRIORITY - Delivers requested trivia feature!**
