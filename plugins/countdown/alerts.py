"""
T-minus alert system for countdown plugin.

This module manages alerts that fire at configured intervals before 
a countdown reaches T-0. Typical usage: "Alert at 5 minutes and 1 minute before."

Alert configurations are tracked per-countdown to prevent duplicate alerts
from firing multiple times.
"""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Dict, List, Optional, Set
import logging


# Maximum alert time (minutes before T-0)
MAX_ALERT_MINUTES = 60

# Default alert configuration
DEFAULT_ALERTS = [5, 1]


@dataclass
class AlertConfig:
    """
    Configuration for countdown alerts.
    
    Attributes:
        minutes: List of minute values when alerts should fire.
                 e.g., [5, 1] means alert at 5 min and 1 min before T-0.
    """
    minutes: List[int] = field(default_factory=lambda: DEFAULT_ALERTS.copy())
    
    def __post_init__(self):
        """Validate and sort minutes list."""
        # Ensure all values are valid
        self.minutes = [
            m for m in self.minutes 
            if isinstance(m, int) and 0 < m <= MAX_ALERT_MINUTES
        ]
        # Sort descending (largest first)
        self.minutes.sort(reverse=True)
    
    @classmethod
    def default(cls) -> 'AlertConfig':
        """
        Get default alert configuration.
        
        Returns:
            AlertConfig with default [5, 1] minute alerts.
        """
        return cls(minutes=DEFAULT_ALERTS.copy())
    
    @classmethod
    def parse(cls, config_str: str) -> 'AlertConfig':
        """
        Parse from comma-separated string.
        
        Args:
            config_str: String like "5,1" or "10,5,1".
            
        Returns:
            Parsed AlertConfig.
            
        Raises:
            ValueError: If format is invalid.
        """
        if not config_str or not config_str.strip():
            raise ValueError("Alert config cannot be empty")
        
        try:
            parts = [p.strip() for p in config_str.split(",")]
            minutes = [int(p) for p in parts if p]
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid alert format. Use: 5,1 or 10,5,1") from e
        
        if not minutes:
            raise ValueError("At least one alert time required")
        
        # Validate range
        invalid = [m for m in minutes if m <= 0 or m > MAX_ALERT_MINUTES]
        if invalid:
            raise ValueError(
                f"Alert minutes must be between 1 and {MAX_ALERT_MINUTES}. "
                f"Invalid: {invalid}"
            )
        
        return cls(minutes=minutes)
    
    def to_string(self) -> str:
        """
        Serialize for storage.
        
        Returns:
            Comma-separated string like "5,1".
        """
        return ",".join(str(m) for m in self.minutes)
    
    @classmethod
    def from_string(cls, config_str: str) -> 'AlertConfig':
        """
        Alias for parse() for consistency with RecurrenceRule.
        
        Args:
            config_str: Stored config string.
            
        Returns:
            Parsed AlertConfig.
        """
        return cls.parse(config_str)
    
    def __str__(self) -> str:
        """Human-readable representation."""
        if len(self.minutes) == 1:
            return f"{self.minutes[0]} minute{'s' if self.minutes[0] != 1 else ''} before"
        else:
            mins = ", ".join(str(m) for m in self.minutes)
            return f"{mins} minutes before"


class AlertManager:
    """
    Manages T-minus alerts for countdowns.
    
    Integrates with CountdownScheduler to send warnings
    at configured intervals before T-0.
    
    Attributes:
        on_alert: Async callback when an alert should fire.
                  Signature: async def callback(countdown_id: str, minutes: int)
    """
    
    def __init__(self, on_alert: Optional[Callable] = None):
        """
        Initialize alert manager.
        
        Args:
            on_alert: Async callback for alert events.
        """
        self.on_alert = on_alert
        self._configs: Dict[str, AlertConfig] = {}
        self._sent: Dict[str, Set[int]] = {}  # countdown_id -> sent minute values
        self.logger = logging.getLogger(f"{__name__}.AlertManager")
    
    def configure(self, countdown_id: str, config: AlertConfig) -> None:
        """
        Set alert configuration for a countdown.
        
        Args:
            countdown_id: Unique identifier for the countdown.
            config: Alert configuration.
        """
        self._configs[countdown_id] = config
        if countdown_id not in self._sent:
            self._sent[countdown_id] = set()
        self.logger.debug(f"Configured alerts for {countdown_id}: {config.minutes}")
    
    def remove(self, countdown_id: str) -> None:
        """
        Remove alert tracking for a countdown.
        
        Args:
            countdown_id: Countdown to remove.
        """
        self._configs.pop(countdown_id, None)
        self._sent.pop(countdown_id, None)
        self.logger.debug(f"Removed alert tracking for {countdown_id}")
    
    def reset(self, countdown_id: str) -> None:
        """
        Reset sent alerts for a countdown.
        
        Used when a recurring countdown resets after T-0.
        
        Args:
            countdown_id: Countdown to reset.
        """
        if countdown_id in self._sent:
            self._sent[countdown_id] = set()
            self.logger.debug(f"Reset sent alerts for {countdown_id}")
    
    def get_config(self, countdown_id: str) -> Optional[AlertConfig]:
        """
        Get alert configuration for a countdown.
        
        Args:
            countdown_id: Countdown to look up.
            
        Returns:
            AlertConfig if configured, None otherwise.
        """
        return self._configs.get(countdown_id)
    
    def has_alerts(self, countdown_id: str) -> bool:
        """
        Check if countdown has alerts configured.
        
        Args:
            countdown_id: Countdown to check.
            
        Returns:
            True if alerts are configured.
        """
        return countdown_id in self._configs
    
    def check_alerts(
        self, 
        countdown_id: str, 
        remaining: timedelta
    ) -> List[int]:
        """
        Check if any alerts should fire for current remaining time.
        
        An alert fires when:
        1. The countdown has that minute value configured
        2. The remaining time is <= that minute value
        3. The alert hasn't already been sent
        
        Args:
            countdown_id: ID of the countdown.
            remaining: Time remaining until T-0.
            
        Returns:
            List of minute values that should trigger alerts now.
            Empty list if no alerts should fire.
        """
        if countdown_id not in self._configs:
            return []
        
        config = self._configs[countdown_id]
        sent = self._sent.get(countdown_id, set())
        
        # Convert remaining to minutes (ceiling to catch the window)
        remaining_minutes = remaining.total_seconds() / 60
        
        alerts_to_fire = []
        
        for alert_minutes in config.minutes:
            # Alert fires when we're within the alert window
            # and haven't already sent this alert
            if alert_minutes not in sent and remaining_minutes <= alert_minutes:
                # Don't fire if we've already passed T-0
                if remaining_minutes >= 0:
                    alerts_to_fire.append(alert_minutes)
                    sent.add(alert_minutes)
        
        if alerts_to_fire:
            self._sent[countdown_id] = sent
            self.logger.debug(
                f"Alerts to fire for {countdown_id}: {alerts_to_fire} "
                f"(remaining: {remaining_minutes:.1f} min)"
            )
        
        return alerts_to_fire
    
    async def process_alerts(
        self, 
        countdown_id: str, 
        remaining: timedelta
    ) -> List[int]:
        """
        Check and fire alerts for a countdown.
        
        Calls the on_alert callback for each alert that should fire.
        
        Args:
            countdown_id: ID of the countdown.
            remaining: Time remaining until T-0.
            
        Returns:
            List of minute values that were fired.
        """
        alerts = self.check_alerts(countdown_id, remaining)
        
        if alerts and self.on_alert:
            for minutes in alerts:
                try:
                    await self.on_alert(countdown_id, minutes)
                except Exception as e:
                    self.logger.error(
                        f"Error in alert callback for {countdown_id} "
                        f"at T-{minutes}: {e}"
                    )
        
        return alerts
    
    def get_next_alert(
        self, 
        countdown_id: str, 
        remaining: timedelta
    ) -> Optional[int]:
        """
        Get the next alert that will fire.
        
        Args:
            countdown_id: ID of the countdown.
            remaining: Current time remaining.
            
        Returns:
            Minutes value of next alert, or None if no more alerts.
        """
        if countdown_id not in self._configs:
            return None
        
        config = self._configs[countdown_id]
        sent = self._sent.get(countdown_id, set())
        remaining_minutes = remaining.total_seconds() / 60
        
        # Find the next alert that hasn't been sent yet
        for alert_minutes in config.minutes:
            if alert_minutes not in sent and remaining_minutes > alert_minutes:
                return alert_minutes
        
        return None
    
    def pending_count(self) -> int:
        """
        Count total countdowns with alert configurations.
        
        Returns:
            Number of configured countdowns.
        """
        return len(self._configs)
    
    def clear_all(self) -> None:
        """Clear all alert configurations and sent tracking."""
        self._configs.clear()
        self._sent.clear()
        self.logger.debug("Cleared all alert configurations")
