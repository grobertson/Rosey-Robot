"""
Tests for countdown alert system.
"""

import pytest
from datetime import timedelta
from unittest.mock import AsyncMock

from countdown.alerts import (
    AlertConfig, AlertManager, DEFAULT_ALERTS, MAX_ALERT_MINUTES
)


class TestAlertConfig:
    """Tests for AlertConfig class."""
    
    def test_default_config(self):
        """Default config has [5, 1] alerts."""
        config = AlertConfig.default()
        assert config.minutes == [5, 1]
    
    def test_custom_config(self):
        """Custom config sorted descending."""
        config = AlertConfig(minutes=[1, 10, 5])
        assert config.minutes == [10, 5, 1]
    
    def test_invalid_values_filtered(self):
        """Invalid values (0, negative, too large) are filtered."""
        config = AlertConfig(minutes=[5, 0, -1, 100, 1])
        assert config.minutes == [5, 1]  # 0, -1, 100 removed
    
    def test_parse_simple(self):
        """Parse '5,1' format."""
        config = AlertConfig.parse("5,1")
        assert config.minutes == [5, 1]
    
    def test_parse_with_spaces(self):
        """Parse '10, 5, 1' with spaces."""
        config = AlertConfig.parse("10, 5, 1")
        assert config.minutes == [10, 5, 1]
    
    def test_parse_single_value(self):
        """Parse single value '5'."""
        config = AlertConfig.parse("5")
        assert config.minutes == [5]
    
    def test_parse_empty_raises(self):
        """Empty string raises ValueError."""
        with pytest.raises(ValueError):
            AlertConfig.parse("")
    
    def test_parse_invalid_raises(self):
        """Non-numeric raises ValueError."""
        with pytest.raises(ValueError):
            AlertConfig.parse("five,one")
    
    def test_parse_out_of_range_raises(self):
        """Values out of range raise ValueError."""
        with pytest.raises(ValueError) as exc:
            AlertConfig.parse("100")
        assert "must be between 1 and" in str(exc.value)
    
    def test_to_string(self):
        """Serialize to string."""
        config = AlertConfig(minutes=[10, 5, 1])
        assert config.to_string() == "10,5,1"
    
    def test_from_string_alias(self):
        """from_string is alias for parse."""
        config = AlertConfig.from_string("5,1")
        assert config.minutes == [5, 1]
    
    def test_str_single(self):
        """String representation for single alert."""
        config = AlertConfig(minutes=[1])
        assert str(config) == "1 minute before"
    
    def test_str_multiple(self):
        """String representation for multiple alerts."""
        config = AlertConfig(minutes=[5, 1])
        assert "5" in str(config)
        assert "1" in str(config)


class TestAlertManager:
    """Tests for AlertManager class."""
    
    def test_init(self):
        """Initialize with callback."""
        callback = AsyncMock()
        manager = AlertManager(on_alert=callback)
        assert manager.on_alert == callback
        assert manager.pending_count() == 0
    
    def test_configure(self):
        """Configure alerts for countdown."""
        manager = AlertManager()
        config = AlertConfig(minutes=[5, 1])
        
        manager.configure("channel:countdown", config)
        
        assert manager.has_alerts("channel:countdown")
        assert manager.get_config("channel:countdown") == config
    
    def test_remove(self):
        """Remove alert configuration."""
        manager = AlertManager()
        manager.configure("channel:countdown", AlertConfig(minutes=[5]))
        
        manager.remove("channel:countdown")
        
        assert not manager.has_alerts("channel:countdown")
    
    def test_reset(self):
        """Reset clears sent alerts."""
        manager = AlertManager()
        config = AlertConfig(minutes=[5, 1])
        manager.configure("test", config)
        
        # Fire an alert
        manager.check_alerts("test", timedelta(minutes=5))
        
        # Reset
        manager.reset("test")
        
        # Should fire again
        alerts = manager.check_alerts("test", timedelta(minutes=5))
        assert 5 in alerts
    
    def test_check_alerts_fires(self):
        """Alert fires when remaining <= configured minutes."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[5, 1]))
        
        # At 4 minutes 30 seconds remaining (within 5-minute window)
        alerts = manager.check_alerts("test", timedelta(minutes=4, seconds=30))
        
        assert 5 in alerts
    
    def test_check_alerts_not_yet(self):
        """Alert doesn't fire when remaining > configured minutes."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[5]))
        
        # At 10 minutes remaining
        alerts = manager.check_alerts("test", timedelta(minutes=10))
        
        assert alerts == []
    
    def test_check_alerts_no_duplicate(self):
        """Alert fires only once."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[5]))
        
        # First check at 5 minutes
        alerts1 = manager.check_alerts("test", timedelta(minutes=5))
        assert 5 in alerts1
        
        # Second check at 4 minutes
        alerts2 = manager.check_alerts("test", timedelta(minutes=4))
        assert 5 not in alerts2
    
    def test_check_alerts_multiple(self):
        """Multiple alerts fire in sequence."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[5, 1]))
        
        # At 5 minutes
        alerts1 = manager.check_alerts("test", timedelta(minutes=5))
        assert 5 in alerts1
        assert 1 not in alerts1
        
        # At 1 minute
        alerts2 = manager.check_alerts("test", timedelta(minutes=1))
        assert 1 in alerts2
        assert 5 not in alerts2
    
    def test_check_alerts_no_config(self):
        """No alerts for unconfigured countdown."""
        manager = AlertManager()
        
        alerts = manager.check_alerts("unknown", timedelta(minutes=5))
        
        assert alerts == []
    
    def test_check_alerts_past_zero(self):
        """No alerts after T-0 (negative remaining)."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[5, 1]))
        
        alerts = manager.check_alerts("test", timedelta(seconds=-10))
        
        assert alerts == []
    
    def test_get_next_alert(self):
        """Get next upcoming alert."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[10, 5, 1]))
        
        # At 12 minutes - next is 10
        next_alert = manager.get_next_alert("test", timedelta(minutes=12))
        assert next_alert == 10
        
        # At 6 minutes - next is 5
        next_alert = manager.get_next_alert("test", timedelta(minutes=6))
        assert next_alert == 5
    
    def test_get_next_alert_none(self):
        """No next alert when all have fired."""
        manager = AlertManager()
        manager.configure("test", AlertConfig(minutes=[5, 1]))
        
        # Fire all alerts
        manager.check_alerts("test", timedelta(minutes=5))
        manager.check_alerts("test", timedelta(minutes=1))
        
        next_alert = manager.get_next_alert("test", timedelta(minutes=0, seconds=30))
        assert next_alert is None
    
    @pytest.mark.asyncio
    async def test_process_alerts(self):
        """Process alerts calls callback."""
        callback = AsyncMock()
        manager = AlertManager(on_alert=callback)
        manager.configure("test", AlertConfig(minutes=[5]))
        
        await manager.process_alerts("test", timedelta(minutes=5))
        
        callback.assert_called_once_with("test", 5)
    
    @pytest.mark.asyncio
    async def test_process_alerts_callback_error(self):
        """Callback error doesn't crash."""
        callback = AsyncMock(side_effect=Exception("test error"))
        manager = AlertManager(on_alert=callback)
        manager.configure("test", AlertConfig(minutes=[5]))
        
        # Should not raise
        alerts = await manager.process_alerts("test", timedelta(minutes=5))
        
        assert 5 in alerts
    
    def test_pending_count(self):
        """Count configured countdowns."""
        manager = AlertManager()
        manager.configure("a", AlertConfig(minutes=[5]))
        manager.configure("b", AlertConfig(minutes=[5]))
        
        assert manager.pending_count() == 2
    
    def test_clear_all(self):
        """Clear all configurations."""
        manager = AlertManager()
        manager.configure("a", AlertConfig(minutes=[5]))
        manager.configure("b", AlertConfig(minutes=[5]))
        
        manager.clear_all()
        
        assert manager.pending_count() == 0
        assert not manager.has_alerts("a")
        assert not manager.has_alerts("b")


class TestAlertConfigConstants:
    """Test module constants."""
    
    def test_default_alerts_value(self):
        assert DEFAULT_ALERTS == [5, 1]
    
    def test_max_alert_minutes(self):
        assert MAX_ALERT_MINUTES == 60
