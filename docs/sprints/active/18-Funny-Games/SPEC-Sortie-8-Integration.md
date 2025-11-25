# SPEC: Sortie 8 - Sprint Integration & Polish

**Sprint:** 18 - Funny Games  
**Sortie:** 8 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 2-3 days  
**Priority:** HIGH - Final integration and quality assurance  
**Prerequisites:** Sorties 1-7

---

## 1. Overview

### 1.1 Purpose

This sortie ensures all Sprint 18 plugins work together seamlessly:

- Cross-plugin integration testing
- Documentation polish
- README updates
- Help command integration
- Performance testing
- Bug fixes from previous sorties
- Final quality assurance

### 1.2 Scope

**In Scope:**
- Cross-plugin integration tests
- Update main `!help` command with new plugins
- Plugin discovery for help
- Update README.md with all new features
- Performance testing under load
- Bug fixes identified in sorties 1-7
- Configuration documentation
- Deployment notes

**Out of Scope:**
- New features (defer to Sprint 19)
- Major architectural changes

### 1.3 Dependencies

- All Sprint 18 sorties (1-7) complete
- Existing help system
- Documentation structure

---

## 2. Technical Design

### 2.1 Work Areas

#### 2.1.1 Help System Integration

Update the help command to discover and display all plugins:

```python
# Extend existing help handler or create new one

async def _handle_help(self, msg) -> None:
    """Handle !help [command]."""
    data = json.loads(msg.data.decode())
    args = data.get("args", "").strip()
    
    if not args:
        # Show all commands
        return await self._show_help_overview(msg)
    
    # Show specific command help
    await self._show_command_help(msg, args)


async def _show_help_overview(self, msg) -> None:
    """Show all available commands grouped by plugin."""
    help_text = """
🤖 **Rosey Commands**

**🎲 Games & Fun**
• `!roll <dice>` - Roll dice (e.g., !roll 2d6+3)
• `!flip` - Flip a coin
• `!8ball <question>` - Consult the Magic 8-Ball
• `!trivia start [N]` - Start trivia game
• `!trivia lb` - Show trivia leaderboard

**⏰ Countdowns**
• `!countdown <name> <time>` - Create countdown
• `!countdown list` - List active countdowns
• `!countdown <name>` - Check remaining time

**💬 Quotes**
• `!quote` - Random quote
• `!quote add <text>` - Add a quote
• `!quote search <term>` - Search quotes

**🔧 Admin** (admins only)
• `!inspect events` - View recent events
• `!inspect plugins` - List loaded plugins

Use `!help <command>` for detailed help.
"""
    await self._reply(msg, help_text)
```

#### 2.1.2 Plugin Help Discovery

Each plugin should expose its help text:

```python
# Add to plugin base class or mixin

class HelpMixin:
    """Mixin for plugins to provide help information."""
    
    HELP_TEXT: str = ""  # Override in plugins
    COMMANDS: list[dict] = []  # List of command definitions
    
    def get_help(self, command: str = None) -> str:
        """Get help text for this plugin or a specific command."""
        if command:
            for cmd in self.COMMANDS:
                if cmd["name"] == command or command in cmd.get("aliases", []):
                    return self._format_command_help(cmd)
            return None
        return self.HELP_TEXT
    
    def _format_command_help(self, cmd: dict) -> str:
        """Format a single command's help."""
        lines = [f"**{cmd['name']}**"]
        if cmd.get("aliases"):
            lines.append(f"Aliases: {', '.join(cmd['aliases'])}")
        lines.append(f"\n{cmd['description']}")
        if cmd.get("usage"):
            lines.append(f"\nUsage: `{cmd['usage']}`")
        if cmd.get("examples"):
            lines.append("\nExamples:")
            for ex in cmd["examples"]:
                lines.append(f"  `{ex}`")
        return "\n".join(lines)


# Example usage in dice-roller plugin
class DiceRollerPlugin(PluginBase, HelpMixin):
    COMMANDS = [
        {
            "name": "roll",
            "aliases": ["r", "dice"],
            "description": "Roll dice using standard notation",
            "usage": "!roll <dice expression>",
            "examples": [
                "!roll d20",
                "!roll 2d6+3",
                "!roll 4d6kh3",  # Keep highest 3
            ],
        },
        {
            "name": "flip",
            "aliases": ["coin"],
            "description": "Flip a coin",
            "usage": "!flip",
            "examples": ["!flip"],
        },
    ]
```

#### 2.1.3 Cross-Plugin Integration Tests

Create comprehensive integration tests:

```python
# tests/integration/test_sprint_18_integration.py

import pytest
from unittest.mock import AsyncMock, MagicMock

pytestmark = pytest.mark.asyncio


class TestSprint18Integration:
    """Integration tests for all Sprint 18 plugins working together."""
    
    async def test_all_plugins_load(self, plugin_manager):
        """Verify all Sprint 18 plugins load without errors."""
        plugins = [
            "dice-roller",
            "8ball",
            "countdown",
            "trivia",
            "inspector",
        ]
        
        for plugin_name in plugins:
            plugin = plugin_manager.get_plugin(plugin_name)
            assert plugin is not None, f"{plugin_name} not loaded"
            assert plugin.is_active, f"{plugin_name} not active"
    
    async def test_plugins_register_subscriptions(self, plugin_manager):
        """Verify all plugins register their NATS subscriptions."""
        expected_subjects = [
            "rosey.command.dice.roll",
            "rosey.command.dice.flip",
            "rosey.command.8ball.ask",
            "rosey.command.countdown.create",
            "rosey.command.trivia.start",
            "rosey.command.inspect.events",
        ]
        
        # Get all registered subjects
        registered = plugin_manager.get_all_subscriptions()
        
        for subject in expected_subjects:
            assert subject in registered, f"{subject} not registered"
    
    async def test_inspector_captures_trivia_events(
        self, 
        trivia_plugin, 
        inspector_plugin
    ):
        """Verify inspector captures trivia game events."""
        # Start a trivia game
        await trivia_plugin._handle_start(mock_message("!trivia start 1"))
        
        # Check inspector captured the event
        events = inspector_plugin.service.get_recent_events(
            pattern="trivia.*"
        )
        
        assert len(events) > 0
        assert any(e.subject == "trivia.game.started" for e in events)
    
    async def test_concurrent_games_different_channels(
        self, 
        trivia_plugin
    ):
        """Verify trivia games can run in multiple channels."""
        # Start games in two channels
        await trivia_plugin._handle_start(
            mock_message("!trivia start 1", channel="lobby")
        )
        await trivia_plugin._handle_start(
            mock_message("!trivia start 1", channel="gaming")
        )
        
        assert "lobby" in trivia_plugin.active_games
        assert "gaming" in trivia_plugin.active_games
        assert trivia_plugin.active_games["lobby"] is not \
               trivia_plugin.active_games["gaming"]
    
    async def test_countdown_and_trivia_coexist(
        self,
        countdown_plugin,
        trivia_plugin,
    ):
        """Verify countdown and trivia can run simultaneously."""
        # Create a countdown
        await countdown_plugin._handle_create(
            mock_message("!countdown test 2025-12-31 23:59", channel="lobby")
        )
        
        # Start trivia in same channel
        await trivia_plugin._handle_start(
            mock_message("!trivia start 1", channel="lobby")
        )
        
        # Both should be active
        countdown = await countdown_plugin.storage.get_by_name("lobby", "test")
        assert countdown is not None
        assert "lobby" in trivia_plugin.active_games
    
    async def test_inspector_pause_resumes_correctly(
        self,
        inspector_plugin,
        dice_plugin,
    ):
        """Verify inspector pause/resume works."""
        # Pause
        inspector_plugin.service.pause()
        
        # Roll dice (should not be captured)
        await dice_plugin._handle_roll(mock_message("!roll d20"))
        events_paused = len(inspector_plugin.buffer.get_recent(pattern="dice.*"))
        
        # Resume
        inspector_plugin.service.resume()
        
        # Roll again (should be captured)
        await dice_plugin._handle_roll(mock_message("!roll d20"))
        events_resumed = len(inspector_plugin.buffer.get_recent(pattern="dice.*"))
        
        assert events_resumed > events_paused


class TestHelpIntegration:
    """Test help system integration with all plugins."""
    
    async def test_help_lists_all_plugins(self, help_handler, plugin_manager):
        """Verify !help shows all plugin commands."""
        response = await help_handler._show_help_overview(mock_message("!help"))
        
        assert "roll" in response.lower()
        assert "8ball" in response.lower()
        assert "countdown" in response.lower()
        assert "trivia" in response.lower()
    
    async def test_help_specific_command(self, help_handler):
        """Verify !help <command> shows detailed help."""
        response = await help_handler._show_command_help(
            mock_message("!help roll"),
            "roll"
        )
        
        assert "dice" in response.lower()
        assert "usage" in response.lower()
        assert "example" in response.lower()


class TestPerformance:
    """Performance tests for Sprint 18 plugins."""
    
    async def test_inspector_buffer_under_load(self, inspector_plugin):
        """Verify inspector handles high event volume."""
        import asyncio
        
        # Simulate 1000 rapid events
        for i in range(1000):
            event = CapturedEvent(
                timestamp=datetime.utcnow(),
                subject=f"test.event.{i}",
                data=b'{"test": true}',
                size_bytes=16,
            )
            inspector_plugin.buffer.append(event)
        
        # Buffer should maintain size limit
        assert len(inspector_plugin.buffer._buffer) <= inspector_plugin.buffer.max_size
        
        # Recent query should be fast
        import time
        start = time.perf_counter()
        events = inspector_plugin.buffer.get_recent(10)
        elapsed = time.perf_counter() - start
        
        assert elapsed < 0.01  # Should be < 10ms
    
    async def test_trivia_concurrent_answers(self, trivia_plugin):
        """Verify trivia handles concurrent answer submissions."""
        import asyncio
        
        # Start a game
        await trivia_plugin._handle_start(mock_message("!trivia start 1"))
        
        # Wait for question
        await asyncio.sleep(6)  # start_delay + buffer
        
        # Submit 10 concurrent answers
        tasks = [
            trivia_plugin._handle_answer(
                mock_message(f"!a A", user=f"player{i}")
            )
            for i in range(10)
        ]
        
        await asyncio.gather(*tasks)
        
        # Should not crash, only first correct answer wins
```

#### 2.1.4 Documentation Updates

**Update main README.md:**

```markdown
## Features

### Games & Entertainment (Sprint 18) 🎲

- **Dice Roller**: Roll dice using standard notation (`!roll 2d6+3`)
- **Magic 8-Ball**: Get mystical answers to your questions
- **Trivia**: Interactive quiz game with leaderboards
- **Countdowns**: Track time until events

### Observability 🔍

- **Inspector**: Real-time event monitoring for admins

See [PLUGINS.md](docs/PLUGINS.md) for detailed documentation.
```

**Create docs/PLUGINS.md:**

```markdown
# Rosey Plugins

## Available Plugins

### dice-roller
Roll dice using standard notation.

**Commands:**
- `!roll <dice>` - Roll dice (e.g., `!roll 2d6+3`)
- `!flip` - Flip a coin

**Examples:**
- `!roll d20` - Roll a d20
- `!roll 2d6+3` - Roll 2d6 and add 3
- `!roll 4d6kh3` - Roll 4d6, keep highest 3

### 8ball
Consult the mystical Magic 8-Ball.

**Commands:**
- `!8ball <question>` - Ask a yes/no question

### countdown
Track countdowns to events.

**Commands:**
- `!countdown <name> <time>` - Create countdown
- `!countdown <name>` - Check remaining time
- `!countdown list` - List all countdowns
- `!countdown delete <name>` - Delete countdown

**Advanced (recurring):**
- `!countdown movie every friday 19:00` - Weekly countdown

### trivia
Interactive quiz game with scoring.

**Commands:**
- `!trivia start [N]` - Start game with N questions
- `!trivia stop` - End current game
- `!a <answer>` - Submit answer
- `!trivia stats` - View your stats
- `!trivia lb` - Channel leaderboard

### inspector (Admin)
Monitor NATS events in real-time.

**Commands:**
- `!inspect events [pattern]` - View recent events
- `!inspect plugins` - List loaded plugins
- `!inspect stats` - View statistics

## Plugin Development

See [PLUGIN_DEVELOPMENT.md](PLUGIN_DEVELOPMENT.md) for creating new plugins.
```

### 2.2 Bug Fix Tracking

Track and fix bugs found during integration:

```markdown
## Known Issues (to fix in Sortie 8)

### From Sortie 1 (Dice Roller)
- [ ] Edge case: `!roll 0d6` should error gracefully
- [ ] Consider: max dice limit (e.g., 100d6)

### From Sortie 3-4 (Countdown)
- [ ] Timezone display in responses
- [ ] Edge case: countdown in past should error

### From Sortie 5-6 (Trivia)
- [ ] HTML entities in some questions
- [ ] Rate limit OpenTDB requests

### From Sortie 7 (Inspector)
- [ ] Memory usage with large buffer
- [ ] Filter performance with many patterns
```

### 2.3 Configuration Documentation

Create comprehensive configuration reference:

```markdown
# Plugin Configuration Reference

## dice-roller/config.json
```json
{
  "max_dice": 100,
  "max_sides": 1000,
  "max_modifier": 1000
}
```

## 8ball/config.json
```json
{
  "cooldown_seconds": 3,
  "require_question": true
}
```

## countdown/config.json
```json
{
  "check_interval": 30.0,
  "max_countdowns_per_channel": 20,
  "max_duration_days": 365,
  "default_alerts": [5, 1]
}
```

## trivia/config.json
```json
{
  "time_per_question": 30,
  "default_questions": 10,
  "max_questions": 50,
  "points_decay": true
}
```

## inspector/config.json
```json
{
  "buffer_size": 1000,
  "admins": ["admin1", "admin2"],
  "exclude_patterns": ["_INBOX.*"]
}
```
```

---

## 3. Implementation Steps

### Step 1: Integration Test Suite (3 hours)

1. Create `tests/integration/test_sprint_18_integration.py`
2. Implement plugin loading tests
3. Implement cross-plugin tests
4. Implement performance tests
5. Run and fix any failures

### Step 2: Help System (2 hours)

1. Add `HelpMixin` to plugin base
2. Update each plugin with `COMMANDS` list
3. Implement help discovery
4. Update main help handler
5. Test `!help` and `!help <command>`

### Step 3: Bug Fixes (2-3 hours)

1. Review each sortie for known issues
2. Fix critical bugs
3. Add edge case handling
4. Add tests for fixed bugs

### Step 4: Documentation (2 hours)

1. Update main README.md
2. Create docs/PLUGINS.md
3. Create configuration reference
4. Update CHANGELOG.md
5. Review all plugin READMEs

### Step 5: Performance Testing (1 hour)

1. Run load tests
2. Profile memory usage
3. Identify bottlenecks
4. Optimize if needed

### Step 6: Final QA (1.5 hours)

1. Manual testing of all commands
2. Test in multiple channels
3. Test with multiple users
4. Verify error messages
5. Check log output

### Step 7: Release Preparation (1 hour)

1. Update VERSION file
2. Write release notes
3. Tag release
4. Update deployment docs

---

## 4. Test Cases

### 4.1 Integration Tests

| Test | Validation |
|------|------------|
| All plugins load | No errors |
| All subscriptions registered | Expected subjects |
| Cross-plugin events | Inspector sees trivia events |
| Concurrent channel games | Isolated correctly |
| Help lists all commands | All plugins represented |

### 4.2 Performance Tests

| Test | Threshold |
|------|-----------|
| Inspector buffer query | < 10ms |
| 10 concurrent answers | No errors |
| 1000 events/second | Buffer handles |
| Memory after 1hr | < 100MB growth |

### 4.3 Manual QA Checklist

| Feature | Verified |
|---------|----------|
| `!roll d20` | [ ] |
| `!flip` | [ ] |
| `!8ball question` | [ ] |
| `!countdown test tomorrow` | [ ] |
| `!countdown list` | [ ] |
| `!trivia start` | [ ] |
| `!trivia answer` | [ ] |
| `!trivia stats` | [ ] |
| `!trivia lb` | [ ] |
| `!inspect events` (admin) | [ ] |
| `!inspect plugins` (admin) | [ ] |
| `!help` | [ ] |
| `!help roll` | [ ] |

---

## 5. Acceptance Criteria

### 5.1 Integration

- [ ] All 5 Sprint 18 plugins load together
- [ ] No conflicts between plugins
- [ ] Inspector captures all plugin events
- [ ] Help system shows all commands
- [ ] Plugins work in multiple channels

### 5.2 Documentation

- [ ] README.md updated with new features
- [ ] PLUGINS.md created with all plugins
- [ ] Configuration documented
- [ ] CHANGELOG.md updated
- [ ] All plugin READMEs complete

### 5.3 Quality

- [ ] All integration tests pass
- [ ] Performance within thresholds
- [ ] No critical bugs
- [ ] Test coverage > 85% overall
- [ ] Manual QA complete

---

## 6. Deliverables

1. **Tests**
   - `tests/integration/test_sprint_18_integration.py`
   - Performance test suite

2. **Code**
   - `HelpMixin` class
   - Bug fixes from sorties 1-7
   - Help system updates

3. **Documentation**
   - Updated README.md
   - New docs/PLUGINS.md
   - Configuration reference
   - Updated CHANGELOG.md
   - Release notes

4. **Release**
   - Version bump
   - Git tag
   - Deployment notes

---

## 7. Checklist

### Pre-Implementation
- [ ] All sorties 1-7 merged
- [ ] Review all open issues
- [ ] Collect known bugs

### Implementation
- [ ] Create integration test suite
- [ ] Implement HelpMixin
- [ ] Update help system
- [ ] Fix identified bugs
- [ ] Update documentation
- [ ] Performance testing

### Post-Implementation
- [ ] All tests pass
- [ ] Manual QA complete
- [ ] Documentation reviewed
- [ ] Version bumped
- [ ] Release notes written
- [ ] Code review
- [ ] Final commit

---

**Commit Message Template:**
```
feat(sprint-18): Integration and polish

- Add cross-plugin integration tests
- Add help system with plugin discovery
- Fix bugs from sorties 1-7
- Update documentation
- Performance optimizations

Implements: SPEC-Sortie-8-Integration.md
Completes: Sprint 18 - Funny Games
```

---

## 8. Sprint Summary

Upon completion of Sortie 8, Sprint 18 delivers:

| Plugin | Commands | Status |
|--------|----------|--------|
| dice-roller | !roll, !flip | ✅ |
| 8ball | !8ball | ✅ |
| countdown | !countdown | ✅ |
| trivia | !trivia, !a | ✅ |
| inspector | !inspect | ✅ |

**Total New Commands:** 15+  
**Estimated Test Coverage:** 85%+  
**Documentation:** Complete

**Next:** Sprint 19 - Core Migrations (Playlist and LLM plugins)
