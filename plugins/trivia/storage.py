import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Any, Dict

logger = logging.getLogger(__name__)

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
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy percentage."""
        if self.total_questions == 0:
            return 0.0
        return (self.correct_answers / self.total_questions) * 100
    
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
    """Database operations for trivia persistence via NATS."""
    
    PLUGIN_NAME = "trivia"
    
    # Schemas matching Alembic migration
    SCHEMAS = {
        "user_stats": {
            "fields": [
                {"name": "user_id", "type": "string", "required": True},
                {"name": "total_games", "type": "integer"},
                {"name": "games_won", "type": "integer"},
                {"name": "total_questions", "type": "integer"},
                {"name": "correct_answers", "type": "integer"},
                {"name": "total_points", "type": "integer"},
                {"name": "current_answer_streak", "type": "integer"},
                {"name": "best_answer_streak", "type": "integer"},
                {"name": "current_win_streak", "type": "integer"},
                {"name": "best_win_streak", "type": "integer"},
                {"name": "fastest_answer_ms", "type": "integer"},
                {"name": "favorite_category", "type": "string"},
            ]
        },
        "channel_stats": {
            "fields": [
                {"name": "user_id", "type": "string", "required": True},
                {"name": "channel", "type": "string", "required": True},
                {"name": "games_played", "type": "integer"},
                {"name": "games_won", "type": "integer"},
                {"name": "total_points", "type": "integer"},
                {"name": "correct_answers", "type": "integer"},
            ]
        },
        "games": {
            "fields": [
                {"name": "game_id", "type": "string", "required": True},
                {"name": "channel", "type": "string", "required": True},
                {"name": "started_by", "type": "string", "required": True},
                {"name": "num_questions", "type": "integer", "required": True},
                {"name": "num_players", "type": "integer"},
                {"name": "winner_id", "type": "string"},
                {"name": "started_at", "type": "datetime", "required": True},
                {"name": "ended_at", "type": "datetime"},
                {"name": "status", "type": "string"},
            ]
        },
        "achievements": {
            "fields": [
                {"name": "user_id", "type": "string", "required": True},
                {"name": "achievement_id", "type": "string", "required": True},
                {"name": "earned_at", "type": "datetime"},
            ]
        },
        "category_stats": {
            "fields": [
                {"name": "user_id", "type": "string", "required": True},
                {"name": "category", "type": "string", "required": True},
                {"name": "questions_seen", "type": "integer"},
                {"name": "correct_answers", "type": "integer"},
            ]
        }
    }
    
    def __init__(self, nats_client):
        self.nc = nats_client
        
    async def register_schemas(self) -> None:
        """Register all table schemas."""
        for table, schema in self.SCHEMAS.items():
            try:
                await self._request(
                    f"rosey.db.row.{self.PLUGIN_NAME}.schema.register",
                    {"table": table, "schema": schema}
                )
            except Exception as e:
                logger.error("Failed to register schema for %s: %s", table, e)

    async def _request(self, subject: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send NATS request and parse response."""
        try:
            response = await self.nc.request(
                subject,
                json.dumps(payload).encode(),
                timeout=5.0
            )
            result = json.loads(response.data.decode())
            
            if not result.get("success"):
                error = result.get("error", {})
                raise RuntimeError(f"DB Error: {error.get('message', 'Unknown error')}")
                
            return result
        except Exception as e:
            logger.error("NATS request failed (%s): %s", subject, e)
            raise

    async def _get_row_id(self, table: str, filters: Dict[str, Any]) -> Optional[int]:
        """Find row ID matching filters."""
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.search",
            {
                "table": table,
                "filters": filters,
                "limit": 1
            }
        )
        rows = result.get("rows", [])
        if rows:
            return rows[0]["id"]
        return None

    async def get_user_stats(self, user_id: str) -> Optional[UserStats]:
        """Get user statistics."""
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.search",
            {
                "table": "user_stats",
                "filters": {"user_id": user_id},
                "limit": 1
            }
        )
        rows = result.get("rows", [])
        if not rows:
            return None
            
        row = rows[0]
        return UserStats(
            user_id=row["user_id"],
            total_games=row.get("total_games", 0),
            games_won=row.get("games_won", 0),
            total_questions=row.get("total_questions", 0),
            correct_answers=row.get("correct_answers", 0),
            total_points=row.get("total_points", 0),
            current_answer_streak=row.get("current_answer_streak", 0),
            best_answer_streak=row.get("best_answer_streak", 0),
            current_win_streak=row.get("current_win_streak", 0),
            best_win_streak=row.get("best_win_streak", 0),
            fastest_answer_ms=row.get("fastest_answer_ms"),
            favorite_category=row.get("favorite_category")
        )
    
    async def ensure_user_stats(self, user_id: str) -> int:
        """Ensure a user stats record exists and return its ID."""
        row_id = await self._get_row_id("user_stats", {"user_id": user_id})
        if row_id:
            return row_id
            
        # Create new
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.insert",
            {
                "table": "user_stats",
                "data": {
                    "user_id": user_id,
                    "total_games": 0,
                    "games_won": 0,
                    "total_questions": 0,
                    "correct_answers": 0,
                    "total_points": 0,
                    "current_answer_streak": 0,
                    "best_answer_streak": 0,
                    "current_win_streak": 0,
                    "best_win_streak": 0
                }
            }
        )
        return result["id"]

    async def update_user_stats(
        self,
        user_id: str,
        questions_answered: int,
        correct_answers: int,
        points_earned: int,
        won_game: bool,
        fastest_ms: Optional[int] = None,
    ) -> Optional[UserStats]:
        """Update user stats after a game."""
        row_id = await self.ensure_user_stats(user_id)
        
        # Prepare atomic updates
        operations = {
            "total_games": {"$inc": 1},
            "games_won": {"$inc": 1 if won_game else 0},
            "total_questions": {"$inc": questions_answered},
            "correct_answers": {"$inc": correct_answers},
            "total_points": {"$inc": points_earned},
        }
        
        # For streaks, we need to read current state first because logic is complex
        # (reset on loss vs increment on win)
        # But wait, this method is called at GAME END.
        # Win streak logic:
        if won_game:
            # We can't do "current_win_streak + 1" and "max(best, current)" atomically easily
            # without reading.
            # Let's read the current stats first.
            stats = await self.get_user_stats(user_id)
            if stats:
                new_current = stats.current_win_streak + 1
                new_best = max(stats.best_win_streak, new_current)
                operations["current_win_streak"] = {"$set": new_current}
                operations["best_win_streak"] = {"$set": new_best}
        else:
            operations["current_win_streak"] = {"$set": 0}
            
        if fastest_ms is not None:
            # We want min(existing, new) but existing might be null.
            # $min operator handles null? Probably not safely.
            # Let's read stats.
            stats = await self.get_user_stats(user_id)
            if stats:
                if stats.fastest_answer_ms is None or fastest_ms < stats.fastest_answer_ms:
                    operations["fastest_answer_ms"] = {"$set": fastest_ms}

        await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.update",
            {
                "table": "user_stats",
                "id": row_id,
                "operations": operations
            }
        )
        
        return await self.get_user_stats(user_id)
    
    async def update_streak(
        self, 
        user_id: str, 
        correct: bool
    ) -> Tuple[int, int]:
        """
        Update answer streak.
        Returns (current_streak, best_streak).
        """
        row_id = await self.ensure_user_stats(user_id)
        
        # Read current stats to calculate new streaks
        # (Atomic operations for "set to 0 if X else inc" are hard)
        stats = await self.get_user_stats(user_id)
        if not stats:
            return 0, 0
            
        if correct:
            new_current = stats.current_answer_streak + 1
            new_best = max(stats.best_answer_streak, new_current)
        else:
            new_current = 0
            new_best = stats.best_answer_streak
            
        await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.update",
            {
                "table": "user_stats",
                "id": row_id,
                "data": {
                    "current_answer_streak": new_current,
                    "best_answer_streak": new_best
                }
            }
        )
        
        return new_current, new_best
    
    async def update_channel_stats(
        self,
        user_id: str,
        channel: str,
        points: int,
        correct: int,
        won: bool,
    ) -> None:
        """Update channel-specific stats."""
        row_id = await self._get_row_id("channel_stats", {"user_id": user_id, "channel": channel})
        
        if row_id:
            # Update existing
            await self._request(
                f"rosey.db.row.{self.PLUGIN_NAME}.update",
                {
                    "table": "channel_stats",
                    "id": row_id,
                    "operations": {
                        "games_played": {"$inc": 1},
                        "games_won": {"$inc": 1 if won else 0},
                        "total_points": {"$inc": points},
                        "correct_answers": {"$inc": correct}
                    }
                }
            )
        else:
            # Create new
            await self._request(
                f"rosey.db.row.{self.PLUGIN_NAME}.insert",
                {
                    "table": "channel_stats",
                    "data": {
                        "user_id": user_id,
                        "channel": channel,
                        "games_played": 1,
                        "games_won": 1 if won else 0,
                        "total_points": points,
                        "correct_answers": correct
                    }
                }
            )
    
    async def get_channel_leaderboard(
        self, 
        channel: str, 
        limit: int = 10
    ) -> List[LeaderboardEntry]:
        """Get top players for a channel."""
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.search",
            {
                "table": "channel_stats",
                "filters": {"channel": channel},
                "sort": {"field": "total_points", "order": "desc"},
                "limit": limit
            }
        )
        rows = result.get("rows", [])
        
        return [
            LeaderboardEntry(
                rank=i+1,
                user_id=row["user_id"],
                total_points=row["total_points"],
                games_played=row["games_played"],
                correct_answers=row["correct_answers"]
            )
            for i, row in enumerate(rows)
        ]
    
    async def get_global_leaderboard(
        self, 
        limit: int = 10
    ) -> List[LeaderboardEntry]:
        """Get top players globally."""
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.search",
            {
                "table": "user_stats",
                "sort": {"field": "total_points", "order": "desc"},
                "limit": limit
            }
        )
        rows = result.get("rows", [])
        
        return [
            LeaderboardEntry(
                rank=i+1,
                user_id=row["user_id"],
                total_points=row["total_points"],
                games_played=row["total_games"],
                correct_answers=row["correct_answers"]
            )
            for i, row in enumerate(rows)
        ]
    
    async def record_game_start(
        self,
        game_id: str,
        channel: str,
        started_by: str,
        num_questions: int,
    ) -> None:
        """Record a new game starting."""
        await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.insert",
            {
                "table": "games",
                "data": {
                    "game_id": game_id,
                    "channel": channel,
                    "started_by": started_by,
                    "num_questions": num_questions,
                    "num_players": 0,
                    "started_at": datetime.utcnow().isoformat(),
                    "status": "active"
                }
            }
        )
    
    async def record_game_end(
        self,
        game_id: str,
        num_players: int,
        winner_id: Optional[str],
    ) -> None:
        """Record game completion."""
        row_id = await self._get_row_id("games", {"game_id": game_id})
        if row_id:
            await self._request(
                f"rosey.db.row.{self.PLUGIN_NAME}.update",
                {
                    "table": "games",
                    "id": row_id,
                    "data": {
                        "num_players": num_players,
                        "winner_id": winner_id,
                        "ended_at": datetime.utcnow().isoformat(),
                        "status": "completed"
                    }
                }
            )
    
    async def get_user_achievements(
        self, 
        user_id: str
    ) -> List[dict]:
        """Get all achievements for a user."""
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.search",
            {
                "table": "achievements",
                "filters": {"user_id": user_id}
            }
        )
        return result.get("rows", [])
    
    async def award_achievement(
        self, 
        user_id: str, 
        achievement_id: str
    ) -> None:
        """Award an achievement to a user."""
        # Check if already exists
        existing = await self._get_row_id("achievements", {"user_id": user_id, "achievement_id": achievement_id})
        if existing:
            return
            
        await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.insert",
            {
                "table": "achievements",
                "data": {
                    "user_id": user_id,
                    "achievement_id": achievement_id,
                    "earned_at": datetime.utcnow().isoformat()
                }
            }
        )
    
    async def update_category_stats(
        self,
        user_id: str,
        category: str,
        correct: bool,
    ) -> None:
        """Update category-specific stats."""
        row_id = await self._get_row_id("category_stats", {"user_id": user_id, "category": category})
        
        if row_id:
            await self._request(
                f"rosey.db.row.{self.PLUGIN_NAME}.update",
                {
                    "table": "category_stats",
                    "id": row_id,
                    "operations": {
                        "questions_seen": {"$inc": 1},
                        "correct_answers": {"$inc": 1 if correct else 0}
                    }
                }
            )
        else:
            await self._request(
                f"rosey.db.row.{self.PLUGIN_NAME}.insert",
                {
                    "table": "category_stats",
                    "data": {
                        "user_id": user_id,
                        "category": category,
                        "questions_seen": 1,
                        "correct_answers": 1 if correct else 0
                    }
                }
            )
        
        # Update favorite category
        # Find category with most questions seen
        result = await self._request(
            f"rosey.db.row.{self.PLUGIN_NAME}.search",
            {
                "table": "category_stats",
                "filters": {"user_id": user_id},
                "sort": {"field": "questions_seen", "order": "desc"},
                "limit": 1
            }
        )
        rows = result.get("rows", [])
        if rows:
            fav_cat = rows[0]["category"]
            user_row_id = await self.ensure_user_stats(user_id)
            await self._request(
                f"rosey.db.row.{self.PLUGIN_NAME}.update",
                {
                    "table": "user_stats",
                    "id": user_row_id,
                    "data": {"favorite_category": fav_cat}
                }
            )
