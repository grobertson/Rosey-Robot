# SPEC: Sortie 6 - Trivia Scoring & Persistence

**Sprint:** 18 - Funny Games  
**Sortie:** 6 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2 days  
**Priority:** MEDIUM - Enhances trivia engagement  
**Prerequisites:** Sortie 5 (Trivia Foundation)

---

## 1. Overview

### 1.1 Purpose

Extend the Trivia plugin with persistent scoring and leaderboards:

- All-time leaderboards (channel and global)
- User statistics (games played, accuracy, streaks)
- Achievement system
- Category preferences
- Historical game data

### 1.2 Scope

**In Scope:**
- `!trivia stats [user]` - Show user statistics
- `!trivia leaderboard` / `!trivia lb` - Show channel leaderboard
- `!trivia global` - Show global leaderboard
- Database persistence for scores
- Win streaks and answer streaks
- Basic achievements
- Category selection (`!trivia start science`)

**Out of Scope:**
- Cross-channel tournaments
- Custom question sets
- Question rating/feedback
- LLM-generated questions (Sprint 19)

### 1.3 Dependencies

- Sortie 5 (Trivia Foundation) - MUST be complete
- Database service (Sprint 17)
- Event bus (existing)

---

## 2. Technical Design

### 2.1 Extended File Structure

Additions to existing plugin:

```
plugins/trivia/
├── ...existing files...
├── storage.py            # Database operations
├── stats.py              # Statistics calculations
├── achievements.py       # Achievement definitions and tracking
└── tests/
    ├── ...existing tests...
    ├── test_storage.py      # Storage tests
    ├── test_stats.py        # Stats calculation tests
    └── test_achievements.py # Achievement tests
```

### 2.2 New NATS Subjects

| Subject | Direction | Purpose |
|---------|-----------|---------|
| `rosey.command.trivia.stats` | Subscribe | Handle `!trivia stats` |
| `rosey.command.trivia.leaderboard` | Subscribe | Handle `!trivia lb` |
| `rosey.command.trivia.global` | Subscribe | Handle `!trivia global` |
| `trivia.achievement.earned` | Publish | Event when achievement earned |
| `trivia.streak.updated` | Publish | Event when streak changes |

### 2.3 Message Schemas

#### Stats Response
```json
{
  "success": true,
  "result": {
    "user": "player1",
    "total_games": 42,
    "total_questions": 378,
    "correct_answers": 289,
    "accuracy": 76.5,
    "total_points": 4250,
    "current_streak": 5,
    "best_streak": 12,
    "favorite_category": "Science",
    "achievements": ["First Win", "Quick Draw", "Streaker"],
    "message": "📊 Stats for player1:\n• Games: 42 | Questions: 378\n• Accuracy: 76.5% (289/378)\n• Total Points: 4,250\n• Current Streak: 🔥5 | Best: 12\n• 🏆 3 achievements earned"
  }
}
```

#### Leaderboard Response
```json
{
  "success": true,
  "result": {
    "scope": "channel",
    "channel": "lobby",
    "leaderboard": [
      {"rank": 1, "user": "player1", "points": 4250, "games": 42},
      {"rank": 2, "user": "player2", "points": 3100, "games": 35}
    ],
    "message": "🏆 Trivia Leaderboard (lobby):\n\n1. 🥇 player1 - 4,250 pts (42 games)\n2. 🥈 player2 - 3,100 pts (35 games)"
  }
}
```

#### Achievement Earned Event
```json
{
  "event": "trivia.achievement.earned",
  "timestamp": "2025-12-01T20:00:00Z",
  "channel": "lobby",
  "user": "player1",
  "achievement": {
    "id": "first_win",
    "name": "First Win",
    "description": "Win your first trivia game",
    "icon": "🏆"
  }
}
```

### 2.4 Database Schema

```sql
-- User statistics table
CREATE TABLE trivia_user_stats (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    total_games INTEGER DEFAULT 0,
    games_won INTEGER DEFAULT 0,
    total_questions INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    current_answer_streak INTEGER DEFAULT 0,
    best_answer_streak INTEGER DEFAULT 0,
    current_win_streak INTEGER DEFAULT 0,
    best_win_streak INTEGER DEFAULT 0,
    fastest_answer_ms INTEGER NULL,
    favorite_category TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_trivia_user_stats_points ON trivia_user_stats(total_points DESC);
CREATE INDEX idx_trivia_user_stats_user ON trivia_user_stats(user_id);

-- Channel-specific leaderboard (for channel rankings)
CREATE TABLE trivia_channel_stats (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    games_played INTEGER DEFAULT 0,
    games_won INTEGER DEFAULT 0,
    total_points INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, channel)
);

CREATE INDEX idx_trivia_channel_stats_channel ON trivia_channel_stats(channel);
CREATE INDEX idx_trivia_channel_stats_points ON trivia_channel_stats(channel, total_points DESC);

-- Game history for analytics
CREATE TABLE trivia_games (
    id INTEGER PRIMARY KEY,
    game_id TEXT NOT NULL UNIQUE,
    channel TEXT NOT NULL,
    started_by TEXT NOT NULL,
    num_questions INTEGER NOT NULL,
    num_players INTEGER NOT NULL,
    winner_id TEXT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NULL,
    status TEXT DEFAULT 'active'  -- active, completed, cancelled
);

CREATE INDEX idx_trivia_games_channel ON trivia_games(channel);

-- User achievements
CREATE TABLE trivia_achievements (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    achievement_id TEXT NOT NULL,
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, achievement_id)
);

CREATE INDEX idx_trivia_achievements_user ON trivia_achievements(user_id);

-- Category statistics (for favorite category)
CREATE TABLE trivia_category_stats (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    category TEXT NOT NULL,
    questions_seen INTEGER DEFAULT 0,
    correct_answers INTEGER DEFAULT 0,
    
    UNIQUE(user_id, category)
);

CREATE INDEX idx_trivia_category_stats_user ON trivia_category_stats(user_id);
```

### 2.5 Achievement System

```python
# plugins/trivia/achievements.py

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Callable


@dataclass
class Achievement:
    """Definition of an achievement."""
    id: str
    name: str
    description: str
    icon: str
    hidden: bool = False  # Hidden until earned
    
    def check(self, stats: 'UserStats', game_result: 'GameResult' = None) -> bool:
        """Check if this achievement should be awarded."""
        ...


class Achievements:
    """All available achievements."""
    
    # First milestones
    FIRST_GAME = Achievement(
        id="first_game",
        name="Newcomer",
        description="Play your first trivia game",
        icon="🎮"
    )
    
    FIRST_WIN = Achievement(
        id="first_win",
        name="First Win",
        description="Win your first trivia game",
        icon="🏆"
    )
    
    FIRST_PERFECT = Achievement(
        id="first_perfect",
        name="Perfectionist",
        description="Get all questions right in a game",
        icon="💯"
    )
    
    # Streak achievements
    STREAK_5 = Achievement(
        id="streak_5",
        name="On a Roll",
        description="Answer 5 questions correctly in a row",
        icon="🔥"
    )
    
    STREAK_10 = Achievement(
        id="streak_10",
        name="Hot Streak",
        description="Answer 10 questions correctly in a row",
        icon="🔥🔥"
    )
    
    STREAK_20 = Achievement(
        id="streak_20",
        name="Unstoppable",
        description="Answer 20 questions correctly in a row",
        icon="🔥🔥🔥"
    )
    
    # Speed achievements
    QUICK_DRAW = Achievement(
        id="quick_draw",
        name="Quick Draw",
        description="Answer correctly in under 3 seconds",
        icon="⚡"
    )
    
    LIGHTNING = Achievement(
        id="lightning",
        name="Lightning Fast",
        description="Answer correctly in under 1 second",
        icon="⚡⚡"
    )
    
    # Volume achievements
    GAMES_10 = Achievement(
        id="games_10",
        name="Regular",
        description="Play 10 trivia games",
        icon="📚"
    )
    
    GAMES_50 = Achievement(
        id="games_50",
        name="Dedicated",
        description="Play 50 trivia games",
        icon="📖"
    )
    
    GAMES_100 = Achievement(
        id="games_100",
        name="Trivia Master",
        description="Play 100 trivia games",
        icon="🎓"
    )
    
    # Points achievements
    POINTS_1000 = Achievement(
        id="points_1000",
        name="Rising Star",
        description="Earn 1,000 total points",
        icon="⭐"
    )
    
    POINTS_10000 = Achievement(
        id="points_10000",
        name="All-Star",
        description="Earn 10,000 total points",
        icon="🌟"
    )
    
    # Hidden achievements
    COMEBACK = Achievement(
        id="comeback",
        name="Comeback Kid",
        description="Win after being in last place",
        icon="🔄",
        hidden=True
    )
    
    @classmethod
    def all(cls) -> List[Achievement]:
        """Get all achievements."""
        return [
            cls.FIRST_GAME, cls.FIRST_WIN, cls.FIRST_PERFECT,
            cls.STREAK_5, cls.STREAK_10, cls.STREAK_20,
            cls.QUICK_DRAW, cls.LIGHTNING,
            cls.GAMES_10, cls.GAMES_50, cls.GAMES_100,
            cls.POINTS_1000, cls.POINTS_10000,
            cls.COMEBACK,
        ]


class AchievementChecker:
    """Check for newly earned achievements."""
    
    def __init__(self, storage: 'TriviaStorage'):
        self.storage = storage
    
    async def check_and_award(
        self, 
        user_id: str, 
        stats: 'UserStats',
        game_result: 'GameResult' = None
    ) -> List[Achievement]:
        """
        Check all achievements and award any newly earned.
        
        Returns list of newly earned achievements.
        """
        earned = await self.storage.get_user_achievements(user_id)
        earned_ids = {a.achievement_id for a in earned}
        
        newly_earned = []
        
        for achievement in Achievements.all():
            if achievement.id in earned_ids:
                continue
            
            if self._check_achievement(achievement, stats, game_result):
                await self.storage.award_achievement(user_id, achievement.id)
                newly_earned.append(achievement)
        
        return newly_earned
    
    def _check_achievement(
        self, 
        achievement: Achievement, 
        stats: 'UserStats',
        game_result: 'GameResult' = None
    ) -> bool:
        """Check if a specific achievement condition is met."""
        ...
```

### 2.6 Storage Class

```python
# plugins/trivia/storage.py

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime
from common.database_service import DatabaseService


@dataclass
class UserStats:
    """User statistics snapshot."""
    user_id: str
    total_games: int
    games_won: int
    total_questions: int
    correct_answers: int
    total_points: int
    current_answer_streak: int
    best_answer_streak: int
    current_win_streak: int
    best_win_streak: int
    fastest_answer_ms: Optional[int]
    favorite_category: Optional[str]
    accuracy: float  # Calculated
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_games == 0:
            return 0.0
        return (self.games_won / self.total_games) * 100


@dataclass
class LeaderboardEntry:
    """Single entry on a leaderboard."""
    rank: int
    user_id: str
    total_points: int
    games_played: int
    correct_answers: int


@dataclass
class GameRecord:
    """Record of a completed game."""
    game_id: str
    channel: str
    started_by: str
    num_questions: int
    num_players: int
    winner_id: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]


class TriviaStorage:
    """Database operations for trivia persistence."""
    
    def __init__(self, db_service: DatabaseService):
        self.db = db_service
    
    async def create_tables(self) -> None:
        """Create all trivia tables if not exists."""
        ...
    
    # User stats operations
    async def get_user_stats(self, user_id: str) -> Optional[UserStats]:
        """Get user statistics."""
        ...
    
    async def update_user_stats(
        self,
        user_id: str,
        questions_answered: int,
        correct_answers: int,
        points_earned: int,
        won_game: bool,
        fastest_ms: Optional[int] = None,
    ) -> UserStats:
        """Update user stats after a game."""
        ...
    
    async def update_streak(
        self, 
        user_id: str, 
        correct: bool
    ) -> tuple[int, int]:
        """
        Update answer streak.
        
        Returns (current_streak, best_streak).
        """
        ...
    
    async def reset_streak(self, user_id: str) -> None:
        """Reset current streak to 0."""
        ...
    
    # Channel stats operations
    async def update_channel_stats(
        self,
        user_id: str,
        channel: str,
        points: int,
        correct: int,
        won: bool,
    ) -> None:
        """Update channel-specific stats."""
        ...
    
    async def get_channel_leaderboard(
        self, 
        channel: str, 
        limit: int = 10
    ) -> List[LeaderboardEntry]:
        """Get top players for a channel."""
        ...
    
    async def get_global_leaderboard(
        self, 
        limit: int = 10
    ) -> List[LeaderboardEntry]:
        """Get top players globally."""
        ...
    
    # Game history
    async def record_game_start(
        self,
        game_id: str,
        channel: str,
        started_by: str,
        num_questions: int,
    ) -> None:
        """Record a new game starting."""
        ...
    
    async def record_game_end(
        self,
        game_id: str,
        num_players: int,
        winner_id: Optional[str],
    ) -> None:
        """Record game completion."""
        ...
    
    # Achievements
    async def get_user_achievements(
        self, 
        user_id: str
    ) -> List[dict]:
        """Get all achievements for a user."""
        ...
    
    async def award_achievement(
        self, 
        user_id: str, 
        achievement_id: str
    ) -> None:
        """Award an achievement to a user."""
        ...
    
    # Category stats
    async def update_category_stats(
        self,
        user_id: str,
        category: str,
        correct: bool,
    ) -> None:
        """Update category-specific stats."""
        ...
    
    async def get_favorite_category(
        self, 
        user_id: str
    ) -> Optional[str]:
        """Get user's most-played category."""
        ...
```

### 2.7 Extended Plugin Class

```python
# plugins/trivia/plugin.py (additions)

class TriviaPlugin(PluginBase):
    """Extended with persistence and leaderboards."""
    
    async def setup(self) -> None:
        """Extended setup with storage."""
        # Initialize storage
        db_service = await get_database_service()
        self.storage = TriviaStorage(db_service)
        await self.storage.create_tables()
        
        # Initialize achievement checker
        self.achievement_checker = AchievementChecker(self.storage)
        
        # ... existing setup ...
        
        # Subscribe to new commands
        await self.subscribe("rosey.command.trivia.stats", self._handle_stats)
        await self.subscribe("rosey.command.trivia.leaderboard", self._handle_leaderboard)
        await self.subscribe("rosey.command.trivia.global", self._handle_global)
    
    async def _handle_start(self, msg) -> None:
        """Extended to support category selection."""
        data = json.loads(msg.data.decode())
        args = data.get("args", "").strip().split()
        
        num_questions = 10
        category = None
        
        for arg in args:
            # Check if it's a number
            if arg.isdigit():
                num_questions = max(1, min(50, int(arg)))
            # Check if it's a category
            elif arg.lower() in CATEGORY_MAP:
                category = CATEGORY_MAP[arg.lower()]
        
        # Fetch with category
        questions = await self.provider.fetch_questions(
            num_questions, 
            category=category
        )
        
        # ... rest of start logic ...
        
        # Record game start
        await self.storage.record_game_start(
            game.game_id,
            channel,
            user,
            len(questions),
        )
    
    async def _on_answer(self, game: TriviaGame, answer: Answer) -> None:
        """Extended to update streaks and category stats."""
        # ... existing answer handling ...
        
        # Update streak
        current, best = await self.storage.update_streak(
            answer.user, 
            answer.correct
        )
        
        # Update category stats
        await self.storage.update_category_stats(
            answer.user,
            game.current_question.category,
            answer.correct,
        )
        
        # Check for achievements
        stats = await self.storage.get_user_stats(answer.user)
        new_achievements = await self.achievement_checker.check_and_award(
            answer.user, stats
        )
        
        for achievement in new_achievements:
            await self._announce_achievement(game.channel, answer.user, achievement)
    
    async def _on_game_end(self, game: TriviaGame) -> None:
        """Extended to persist scores."""
        leaderboard = game.get_leaderboard()
        winner = leaderboard[0] if leaderboard else None
        
        # Update all player stats
        for player in leaderboard:
            await self.storage.update_user_stats(
                user_id=player.user,
                questions_answered=player.total_answers,
                correct_answers=player.correct_answers,
                points_earned=player.score,
                won_game=(player.user == winner.user if winner else False),
                fastest_ms=int(player.fastest_time * 1000) if player.fastest_time else None,
            )
            
            await self.storage.update_channel_stats(
                user_id=player.user,
                channel=game.channel,
                points=player.score,
                correct=player.correct_answers,
                won=(player.user == winner.user if winner else False),
            )
        
        # Record game end
        await self.storage.record_game_end(
            game.game_id,
            num_players=len(leaderboard),
            winner_id=winner.user if winner else None,
        )
        
        # Check achievements for all players
        for player in leaderboard:
            stats = await self.storage.get_user_stats(player.user)
            game_result = GameResult(
                won=(player.user == winner.user if winner else False),
                perfect=(player.correct_answers == player.total_answers),
                score=player.score,
            )
            new_achievements = await self.achievement_checker.check_and_award(
                player.user, stats, game_result
            )
            
            for achievement in new_achievements:
                await self._announce_achievement(game.channel, player.user, achievement)
        
        # ... existing end game logic ...
    
    async def _handle_stats(self, msg) -> None:
        """Handle !trivia stats [user]."""
        data = json.loads(msg.data.decode())
        args = data.get("args", "").strip()
        
        # Default to requesting user
        target_user = args if args else data["user"]
        
        stats = await self.storage.get_user_stats(target_user)
        
        if not stats:
            return await self._reply(msg, f"📊 No stats found for {target_user}")
        
        achievements = await self.storage.get_user_achievements(target_user)
        
        message = (
            f"📊 Stats for {target_user}:\n"
            f"• Games: {stats.total_games} | Won: {stats.games_won}\n"
            f"• Questions: {stats.correct_answers}/{stats.total_questions} "
            f"({stats.accuracy:.1f}%)\n"
            f"• Total Points: {stats.total_points:,}\n"
            f"• Streak: 🔥{stats.current_answer_streak} | Best: {stats.best_answer_streak}\n"
            f"• 🏆 {len(achievements)} achievements earned"
        )
        
        await self._reply(msg, message)
    
    async def _handle_leaderboard(self, msg) -> None:
        """Handle !trivia leaderboard / !trivia lb."""
        data = json.loads(msg.data.decode())
        channel = data["channel"]
        
        leaderboard = await self.storage.get_channel_leaderboard(channel)
        
        if not leaderboard:
            return await self._reply(msg, "📊 No trivia has been played in this channel yet!")
        
        lines = [f"🏆 Trivia Leaderboard ({channel}):\n"]
        medals = ["🥇", "🥈", "🥉"]
        
        for entry in leaderboard[:10]:
            medal = medals[entry.rank - 1] if entry.rank <= 3 else f"{entry.rank}."
            lines.append(
                f"{medal} {entry.user_id} - {entry.total_points:,} pts "
                f"({entry.games_played} games)"
            )
        
        await self._reply(msg, "\n".join(lines))
    
    async def _handle_global(self, msg) -> None:
        """Handle !trivia global."""
        leaderboard = await self.storage.get_global_leaderboard()
        
        if not leaderboard:
            return await self._reply(msg, "📊 No trivia has been played yet!")
        
        lines = ["🌍 Global Trivia Leaderboard:\n"]
        medals = ["🥇", "🥈", "🥉"]
        
        for entry in leaderboard[:10]:
            medal = medals[entry.rank - 1] if entry.rank <= 3 else f"{entry.rank}."
            lines.append(
                f"{medal} {entry.user_id} - {entry.total_points:,} pts"
            )
        
        await self._reply(msg, "\n".join(lines))
    
    async def _announce_achievement(
        self, 
        channel: str, 
        user: str, 
        achievement: Achievement
    ) -> None:
        """Announce newly earned achievement."""
        message = (
            f"🎉 {user} earned an achievement!\n"
            f"{achievement.icon} **{achievement.name}**\n"
            f"_{achievement.description}_"
        )
        
        await self._send_to_channel(channel, message)
        
        await self.publish("trivia.achievement.earned", {
            "event": "trivia.achievement.earned",
            "channel": channel,
            "user": user,
            "achievement": {
                "id": achievement.id,
                "name": achievement.name,
                "icon": achievement.icon,
            },
        })


# Category mapping for !trivia start <category>
CATEGORY_MAP = {
    "general": 9,
    "science": 17,
    "computers": 18,
    "math": 19,
    "geography": 22,
    "history": 23,
    "sports": 21,
    "animals": 27,
    "vehicles": 28,
}
```

### 2.8 Extended Configuration

```json
{
  "time_per_question": 30,
  "start_delay": 5,
  "between_questions": 3,
  "max_questions": 50,
  "default_questions": 10,
  "points_decay": true,
  "emit_events": true,
  "track_stats": true,
  "enable_achievements": true,
  "leaderboard_size": 10
}
```

---

## 3. Implementation Steps

### Step 1: Database Migration (45 minutes)

1. Create Alembic migration for all tables
2. Run migration
3. Verify table structure

### Step 2: Implement Storage Class (2 hours)

1. Implement `TriviaStorage` class
2. Implement user stats CRUD
3. Implement channel stats operations
4. Implement leaderboard queries
5. Implement achievement storage
6. Write comprehensive tests

### Step 3: Implement Stats Module (1 hour)

1. Implement `UserStats` dataclass
2. Implement accuracy/win rate calculations
3. Implement streak logic
4. Write tests

### Step 4: Implement Achievement System (1.5 hours)

1. Define all achievements
2. Implement `AchievementChecker`
3. Implement condition checking
4. Write tests for each achievement

### Step 5: Extend Plugin (2 hours)

1. Initialize storage in `setup()`
2. Update `_on_answer()` for streaks
3. Update `_on_game_end()` for persistence
4. Implement `_handle_stats()`
5. Implement `_handle_leaderboard()`
6. Implement `_handle_global()`
7. Implement achievement announcements

### Step 6: Add Category Selection (1 hour)

1. Add category parsing to `_handle_start()`
2. Update provider to accept category
3. Add category stats tracking
4. Test category filtering

### Step 7: Integration Testing (1.5 hours)

1. Test full persistence flow
2. Test leaderboard accuracy
3. Test achievement earning
4. Test streak tracking
5. Test across multiple games

### Step 8: Documentation (30 minutes)

1. Update README.md with new commands
2. Document achievements
3. Document category options

---

## 4. Test Cases

### 4.1 Storage Tests

| Operation | Validation |
|-----------|------------|
| Create user stats | Stats created with defaults |
| Update user stats | Values updated correctly |
| Get channel leaderboard | Sorted by points, limited |
| Get global leaderboard | Aggregated across channels |
| Award achievement | Recorded with timestamp |
| Prevent duplicate achievement | Second award fails silently |

### 4.2 Stats Calculation Tests

| Scenario | Expected |
|----------|----------|
| 10 games, 3 won | Win rate 30% |
| 100 questions, 75 correct | Accuracy 75% |
| Correct, correct, wrong | Streak resets to 0 |
| 5 correct in a row | Streak = 5 |

### 4.3 Achievement Tests

| Achievement | Trigger |
|-------------|---------|
| Newcomer | First game played |
| First Win | First game won |
| Perfectionist | All correct in a game |
| On a Roll | 5-streak |
| Quick Draw | Answer < 3 seconds |
| Games 10 | 10 games played |

### 4.4 Integration Tests

| Scenario | Expected |
|----------|----------|
| Complete game | Stats persisted for all players |
| Win game | Winner's games_won incremented |
| Answer streak | Tracked across questions |
| New achievement | Announced in chat |
| `!trivia stats` | Shows accurate stats |
| `!trivia lb` | Shows channel rankings |
| `!trivia global` | Shows global rankings |

---

## 5. Error Handling

### 5.1 User Errors

| Error | Response |
|-------|----------|
| Stats for unknown user | "No stats found for {user}" |
| Empty leaderboard | "No trivia played in this channel yet!" |

### 5.2 System Errors

| Error | Handling |
|-------|----------|
| Database unavailable | Log, continue without persistence |
| Migration fails | Roll back, alert admin |

---

## 6. Acceptance Criteria

### 6.1 Functional

- [ ] `!trivia stats` shows user statistics
- [ ] `!trivia stats <user>` shows other user's stats
- [ ] `!trivia lb` shows channel leaderboard
- [ ] `!trivia global` shows global leaderboard
- [ ] Scores persist across bot restarts
- [ ] Streaks tracked correctly
- [ ] Achievements awarded appropriately
- [ ] Achievement announcements in chat
- [ ] `!trivia start science` filters by category

### 6.2 Technical

- [ ] Database migration runs cleanly
- [ ] Stats update atomically
- [ ] Leaderboards are accurate
- [ ] No duplicate achievements
- [ ] Test coverage > 85%

### 6.3 Documentation

- [ ] README.md updated with new commands
- [ ] All achievements documented
- [ ] Category options documented

---

## 7. Sample Interactions

```
User: !trivia stats
Rosey: 📊 Stats for User:
       • Games: 42 | Won: 15
       • Questions: 289/378 (76.5%)
       • Total Points: 4,250
       • Streak: 🔥5 | Best: 12
       • 🏆 8 achievements earned

User: !trivia lb
Rosey: 🏆 Trivia Leaderboard (lobby):

       🥇 Player1 - 4,250 pts (42 games)
       🥈 Player2 - 3,100 pts (35 games)
       🥉 Player3 - 2,800 pts (28 games)
       4. Player4 - 1,500 pts (12 games)

User: !trivia global
Rosey: 🌍 Global Trivia Leaderboard:

       🥇 Player1 - 8,500 pts
       🥈 Player5 - 7,200 pts
       🥉 Player2 - 6,100 pts

[During a game]
Player1: !a Paris
Rosey: ✅ Correct! Player1 got it in 2.1s! (+15 points)

Rosey: 🎉 Player1 earned an achievement!
       ⚡ **Quick Draw**
       _Answer correctly in under 3 seconds_

[After game]
Rosey: 🏆 Game Over!
       🥇 Player1 - 95 points
       🥈 Player2 - 82 points

Rosey: 🎉 Player1 earned an achievement!
       💯 **Perfectionist**
       _Get all questions right in a game_

User: !trivia start science 5
Rosey: 🎯 Trivia starting! 5 Science questions, 30 seconds each.
       First question in 5 seconds...
```

---

## 8. Checklist

### Pre-Implementation
- [ ] Sortie 5 complete and tested
- [ ] Review achievement conditions
- [ ] Plan database indexes

### Implementation
- [ ] Create database migration
- [ ] Implement storage class
- [ ] Implement stats module
- [ ] Implement achievement system
- [ ] Extend plugin class
- [ ] Add category selection
- [ ] Write unit tests
- [ ] Write integration tests

### Post-Implementation
- [ ] Run all tests (must pass)
- [ ] Manual testing with real games
- [ ] Verify leaderboards accurate
- [ ] Verify achievements fire correctly
- [ ] Code review
- [ ] Commit with proper message

---

**Commit Message Template:**
```
feat(plugins): Add trivia scoring persistence

- Add persistent score tracking
- Add channel and global leaderboards
- Add achievement system (14 achievements)
- Add user statistics (!trivia stats)
- Add category selection (!trivia start science)
- Track answer streaks and win streaks

Implements: SPEC-Sortie-6-TriviaScoring.md
Related: PRD-Funny-Games.md
```
