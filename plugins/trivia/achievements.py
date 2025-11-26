from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .storage import UserStats, TriviaStorage

@dataclass
class GameResult:
    """Result of a single game for a user."""
    won: bool
    perfect: bool
    score: int

@dataclass
class Achievement:
    """Definition of an achievement."""
    id: str
    name: str
    description: str
    icon: str
    hidden: bool = False  # Hidden until earned
    
    def check(self, stats: 'UserStats', game_result: Optional[GameResult] = None) -> bool:
        """Check if this achievement should be awarded."""
        raise NotImplementedError

class SimpleAchievement(Achievement):
    """Achievement with a simple lambda check."""
    def __init__(self, check_fn, **kwargs):
        super().__init__(**kwargs)
        self.check_fn = check_fn
        
    def check(self, stats: 'UserStats', game_result: Optional[GameResult] = None) -> bool:
        return self.check_fn(stats, game_result)

class Achievements:
    """All available achievements."""
    
    # First milestones
    FIRST_GAME = SimpleAchievement(
        id="first_game",
        name="Newcomer",
        description="Play your first trivia game",
        icon="🎮",
        check_fn=lambda s, g: s.total_games >= 1
    )
    
    FIRST_WIN = SimpleAchievement(
        id="first_win",
        name="First Win",
        description="Win your first trivia game",
        icon="🏆",
        check_fn=lambda s, g: s.games_won >= 1
    )
    
    FIRST_PERFECT = SimpleAchievement(
        id="first_perfect",
        name="Perfectionist",
        description="Get all questions right in a game",
        icon="💯",
        check_fn=lambda s, g: g and g.perfect
    )
    
    # Streak achievements
    STREAK_5 = SimpleAchievement(
        id="streak_5",
        name="On a Roll",
        description="Answer 5 questions correctly in a row",
        icon="🔥",
        check_fn=lambda s, g: s.best_answer_streak >= 5
    )
    
    STREAK_10 = SimpleAchievement(
        id="streak_10",
        name="Hot Streak",
        description="Answer 10 questions correctly in a row",
        icon="🔥🔥",
        check_fn=lambda s, g: s.best_answer_streak >= 10
    )
    
    STREAK_20 = SimpleAchievement(
        id="streak_20",
        name="Unstoppable",
        description="Answer 20 questions correctly in a row",
        icon="🔥🔥🔥",
        check_fn=lambda s, g: s.best_answer_streak >= 20
    )
    
    # Speed achievements
    QUICK_DRAW = SimpleAchievement(
        id="quick_draw",
        name="Quick Draw",
        description="Answer correctly in under 3 seconds",
        icon="⚡",
        check_fn=lambda s, g: s.fastest_answer_ms is not None and s.fastest_answer_ms <= 3000
    )
    
    LIGHTNING = SimpleAchievement(
        id="lightning",
        name="Lightning Fast",
        description="Answer correctly in under 1 second",
        icon="⚡⚡",
        check_fn=lambda s, g: s.fastest_answer_ms is not None and s.fastest_answer_ms <= 1000
    )
    
    # Volume achievements
    GAMES_10 = SimpleAchievement(
        id="games_10",
        name="Regular",
        description="Play 10 trivia games",
        icon="📚",
        check_fn=lambda s, g: s.total_games >= 10
    )
    
    GAMES_50 = SimpleAchievement(
        id="games_50",
        name="Dedicated",
        description="Play 50 trivia games",
        icon="📖",
        check_fn=lambda s, g: s.total_games >= 50
    )
    
    GAMES_100 = SimpleAchievement(
        id="games_100",
        name="Trivia Master",
        description="Play 100 trivia games",
        icon="🎓",
        check_fn=lambda s, g: s.total_games >= 100
    )
    
    # Points achievements
    POINTS_1000 = SimpleAchievement(
        id="points_1000",
        name="Rising Star",
        description="Earn 1,000 total points",
        icon="⭐",
        check_fn=lambda s, g: s.total_points >= 1000
    )
    
    POINTS_10000 = SimpleAchievement(
        id="points_10000",
        name="All-Star",
        description="Earn 10,000 total points",
        icon="🌟",
        check_fn=lambda s, g: s.total_points >= 10000
    )
    
    # Hidden achievements
    COMEBACK = SimpleAchievement(
        id="comeback",
        name="Comeback Kid",
        description="Win after being in last place",
        icon="🔄",
        hidden=True,
        # This one is tricky to check with just stats/game_result as defined.
        # It requires game history context. For now, we'll leave it as always false
        # or implement a specific check if we pass more data.
        # The spec says "Win after being in last place".
        # We'll skip implementation for now or make it manual trigger.
        check_fn=lambda s, g: False 
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
        game_result: Optional[GameResult] = None
    ) -> List[Achievement]:
        """
        Check all achievements and award any newly earned.
        
        Returns list of newly earned achievements.
        """
        earned_dicts = await self.storage.get_user_achievements(user_id)
        earned_ids = {a['achievement_id'] for a in earned_dicts}
        
        newly_earned = []
        
        for achievement in Achievements.all():
            if achievement.id in earned_ids:
                continue
            
            if achievement.check(stats, game_result):
                await self.storage.award_achievement(user_id, achievement.id)
                newly_earned.append(achievement)
        
        return newly_earned
