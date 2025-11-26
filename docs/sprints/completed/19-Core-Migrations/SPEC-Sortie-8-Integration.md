# SPEC: Sortie 8 - Integration & Cleanup

**Sprint:** 19 - Core Migrations  
**Sortie:** 8 of 8  
**Status:** Ready for Implementation  
**Estimated Effort:** 1.5 days  
**Priority:** HIGH - Sprint completion  
**Prerequisites:** Sorties 1-7 complete

---

## 1. Overview

### 1.1 Purpose

Complete the Sprint 19 migration with final integration:

- Remove deprecated `lib/` code
- Update all consumers to use new plugins
- Cross-plugin integration testing
- Documentation updates
- Performance validation
- Sprint retrospective

### 1.2 Scope

**In Scope:**
- Remove `lib/playlist.py`
- Remove `lib/llm/` directory
- Update bot core to use plugins
- Integration tests across plugins
- Documentation updates
- Performance benchmarks

**Out of Scope:**
- New features
- Bug fixes unrelated to migration

### 1.3 Dependencies

- ALL previous sorties (1-7) - MUST be complete
- Sprint 18 plugins (for cross-plugin testing)

---

## 2. Migration Checklist

### 2.1 Files to Remove

```
lib/
├── playlist.py          # REMOVE - migrated to plugins/playlist/
├── llm/                  # REMOVE - migrated to plugins/llm/
│   ├── __init__.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── claude.py
│   │   └── ollama.py
│   ├── chat.py
│   └── prompts.py
```

### 2.2 Files to Update

```
bot/rosey/bot.py              # Remove lib imports, use plugins
bot/rosey/rosey_controller.py # Update to use plugin services
common/config.py              # Add plugin configuration
tests/                        # Update test imports
```

### 2.3 Migration Mapping

| Old Location | New Location | Notes |
|--------------|--------------|-------|
| `lib/playlist.py` | `plugins/playlist/` | Full functionality |
| `lib/llm/__init__.py` | `plugins/llm/` | Enhanced |
| `lib/llm/providers/` | `plugins/llm/providers/` | Same structure |
| `lib/llm/chat.py` | `plugins/llm/service.py` | Expanded API |
| `lib/llm/prompts.py` | `plugins/llm/prompts.py` | Same content |

---

## 3. Implementation Steps

### Step 1: Pre-Migration Validation (30 minutes)

1. Run full test suite
2. Document current test coverage
3. Verify all sorties complete
4. Create backup branch

```powershell
# Run tests before migration
pytest tests/ -v --cov=plugins --cov-report=html
git checkout -b backup/pre-cleanup-sprint-19
git push origin backup/pre-cleanup-sprint-19
```

### Step 2: Update Bot Core (1 hour)

#### 2.1 Update Bot Imports

```python
# bot/rosey/bot.py

# BEFORE:
from lib.llm import LLMChat
from lib.playlist import Playlist

# AFTER:
# LLM is now a plugin - use NATS for communication
# Playlist is now a plugin - use NATS for communication

# Add helper for plugin communication
async def request_llm(self, message: str, channel: str, user: str) -> str:
    """Request LLM response via plugin."""
    response = await self._nc.request(
        "rosey.llm.chat",
        json.dumps({
            "channel": channel,
            "user": user,
            "message": message,
        }).encode(),
        timeout=30.0
    )
    data = json.loads(response.data.decode())
    return data.get("content", "") if data.get("success") else None
```

#### 2.2 Update Controller

```python
# bot/rosey/rosey_controller.py

# Remove direct imports
# from lib.llm import LLMChat  # REMOVE
# from lib.playlist import Playlist  # REMOVE

# Use NATS-based plugin services instead
class RoseyController:
    def __init__(self, nc):
        self._nc = nc
        # No longer need direct references
        # self._llm = LLMChat(...)  # REMOVE
        # self._playlist = Playlist(...)  # REMOVE
```

### Step 3: Remove Deprecated Code (30 minutes)

```powershell
# Remove deprecated lib code
Remove-Item -Recurse -Force lib/llm
Remove-Item -Force lib/playlist.py

# Verify removal
Get-ChildItem lib/ -Recurse

# Run tests to verify nothing breaks
pytest tests/ -v
```

### Step 4: Update Tests (1 hour)

#### 4.1 Update Test Imports

```python
# tests/test_llm.py (if exists)

# BEFORE:
from lib.llm import LLMChat

# AFTER:
from plugins.llm.service import LLMService
from plugins.llm.providers.base import Provider
```

#### 4.2 Update Test Fixtures

```python
# tests/conftest.py

import pytest
from plugins.llm.plugin import LLMPlugin
from plugins.playlist.plugin import PlaylistPlugin


@pytest.fixture
async def llm_plugin(mock_nats, mock_db):
    """Create LLM plugin for testing."""
    plugin = LLMPlugin()
    await plugin.setup(mock_nats, mock_db)
    yield plugin
    await plugin.teardown()


@pytest.fixture
async def playlist_plugin(mock_nats, mock_db):
    """Create playlist plugin for testing."""
    plugin = PlaylistPlugin()
    await plugin.setup(mock_nats, mock_db)
    yield plugin
    await plugin.teardown()
```

### Step 5: Integration Tests (2 hours)

#### 5.1 Cross-Plugin Tests

```python
# tests/integration/test_plugin_integration.py

import pytest
import json


@pytest.mark.integration
class TestPluginIntegration:
    """Test plugins working together."""
    
    @pytest.mark.asyncio
    async def test_trivia_uses_llm_for_hints(
        self, 
        trivia_plugin, 
        llm_plugin, 
        mock_nats
    ):
        """Test trivia can get hints from LLM."""
        # Start trivia game
        await mock_nats.publish(
            "rosey.command.trivia.start",
            json.dumps({
                "channel": "#test",
                "user": "alice",
                "args": "",
            }).encode()
        )
        
        # Request hint (should use LLM)
        await mock_nats.publish(
            "rosey.command.trivia.hint",
            json.dumps({
                "channel": "#test",
                "user": "alice",
            }).encode()
        )
        
        # Verify LLM was called
        assert llm_plugin._request_count > 0
    
    @pytest.mark.asyncio
    async def test_inspector_observes_llm_events(
        self,
        inspector_plugin,
        llm_plugin,
        mock_nats
    ):
        """Test inspector sees LLM events."""
        # Enable inspector on LLM events
        await mock_nats.publish(
            "rosey.command.inspect.watch",
            json.dumps({
                "channel": "#test",
                "user": "admin",
                "args": "rosey.event.llm.*",
            }).encode()
        )
        
        # Trigger LLM request
        await mock_nats.publish(
            "rosey.command.chat",
            json.dumps({
                "channel": "#test",
                "user": "alice",
                "args": "Hello!",
            }).encode()
        )
        
        # Verify inspector received event
        assert inspector_plugin._captured_events > 0
    
    @pytest.mark.asyncio
    async def test_playlist_integration(
        self,
        playlist_plugin,
        mock_nats
    ):
        """Test playlist plugin basic operations."""
        # Add to playlist
        response = await mock_nats.request(
            "rosey.playlist.add",
            json.dumps({
                "channel": "#test",
                "user": "alice",
                "url": "https://youtube.com/watch?v=test",
            }).encode(),
            timeout=5.0
        )
        
        data = json.loads(response.data.decode())
        assert data["success"] is True
        
        # Get queue
        response = await mock_nats.request(
            "rosey.playlist.queue",
            json.dumps({"channel": "#test"}).encode(),
            timeout=5.0
        )
        
        data = json.loads(response.data.decode())
        assert len(data["queue"]) > 0
```

#### 5.2 End-to-End Tests

```python
# tests/integration/test_e2e.py

@pytest.mark.e2e
class TestEndToEnd:
    """End-to-end tests simulating real usage."""
    
    @pytest.mark.asyncio
    async def test_full_chat_session(self, bot, mock_channel):
        """Test complete chat interaction."""
        # User asks a question
        await mock_channel.send_message("alice", "!chat Hello Rosey!")
        
        # Wait for response
        response = await mock_channel.wait_for_reply(timeout=10.0)
        
        assert response is not None
        assert len(response) > 0
    
    @pytest.mark.asyncio
    async def test_dice_and_8ball_sequence(self, bot, mock_channel):
        """Test multiple plugin interactions."""
        # Roll dice
        await mock_channel.send_message("alice", "!roll 2d6")
        dice_response = await mock_channel.wait_for_reply()
        assert "🎲" in dice_response
        
        # Ask 8ball
        await mock_channel.send_message("alice", "!8ball Will I win?")
        ball_response = await mock_channel.wait_for_reply()
        assert "🎱" in ball_response
    
    @pytest.mark.asyncio
    async def test_countdown_persistence(self, bot, mock_channel, db):
        """Test countdown survives restart."""
        # Create countdown
        await mock_channel.send_message(
            "alice", 
            "!countdown set test 2025-12-31 New Year"
        )
        
        # Restart bot
        await bot.stop()
        await bot.start()
        
        # Check countdown still exists
        await mock_channel.send_message("alice", "!countdown list")
        response = await mock_channel.wait_for_reply()
        
        assert "New Year" in response
```

### Step 6: Documentation Updates (1 hour)

#### 6.1 Update Architecture Docs

```markdown
# docs/ARCHITECTURE.md - Add section

## Plugin Architecture

As of Sprint 19, core functionality has been migrated to plugins:

### Playlist Plugin
Location: `plugins/playlist/`
- Manages media queue
- Exposes PlaylistService via NATS
- Database persistence for queue

### LLM Plugin  
Location: `plugins/llm/`
- AI chat capabilities
- Memory and context management
- MCP tool support
- Multiple provider support (Claude, Ollama)
```

#### 6.2 Update Migration Guide

```markdown
# docs/guides/MIGRATION.md

## Sprint 19 Migration Notes

### Breaking Changes

1. **lib/playlist.py removed**
   - Use `plugins/playlist/` instead
   - Access via NATS: `rosey.playlist.*`

2. **lib/llm/ removed**
   - Use `plugins/llm/` instead
   - Access via NATS: `rosey.llm.*`

### Migration Steps

If you had code importing from lib/:

```python
# OLD
from lib.llm import LLMChat
chat = LLMChat()
response = await chat.complete("Hello")

# NEW
response = await nc.request(
    "rosey.llm.chat",
    json.dumps({"channel": "#test", "user": "bot", "message": "Hello"}).encode()
)
```
```

#### 6.3 Update README

```markdown
# README.md - Update plugins section

## Available Plugins

### Core Plugins (Sprint 19)
- **playlist** - Media queue management
- **llm** - AI chat with memory and tools

### Fun Plugins (Sprint 18)
- **dice-roller** - Dice rolling with standard notation
- **8ball** - Magic 8-ball responses
- **countdown** - Event countdowns with recurring support
- **trivia** - Trivia games with scoring
- **inspector** - Event observability
```

### Step 7: Performance Validation (30 minutes)

```python
# tests/performance/test_benchmarks.py

import pytest
import time


@pytest.mark.performance
class TestPerformance:
    """Performance benchmarks."""
    
    @pytest.mark.asyncio
    async def test_llm_response_time(self, llm_plugin, mock_nats):
        """LLM should respond within acceptable time."""
        start = time.monotonic()
        
        response = await mock_nats.request(
            "rosey.llm.chat",
            json.dumps({
                "channel": "#test",
                "user": "alice",
                "message": "Hello!",
            }).encode(),
            timeout=30.0
        )
        
        elapsed = time.monotonic() - start
        
        # Should respond within 5 seconds (excluding network to provider)
        assert elapsed < 5.0, f"LLM response took {elapsed:.2f}s"
    
    @pytest.mark.asyncio
    async def test_playlist_operations_fast(self, playlist_plugin, mock_nats):
        """Playlist operations should be fast."""
        times = []
        
        for i in range(10):
            start = time.monotonic()
            await mock_nats.request(
                "rosey.playlist.add",
                json.dumps({
                    "channel": "#test",
                    "user": "alice",
                    "url": f"https://youtube.com/watch?v=test{i}",
                }).encode(),
                timeout=5.0
            )
            times.append(time.monotonic() - start)
        
        avg_time = sum(times) / len(times)
        assert avg_time < 0.1, f"Average add time: {avg_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_memory_usage(self, all_plugins):
        """Memory usage should be reasonable."""
        import tracemalloc
        
        tracemalloc.start()
        
        # Simulate activity
        for _ in range(100):
            # Various operations
            pass
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Peak memory should be under 100MB
        assert peak < 100 * 1024 * 1024, f"Peak memory: {peak / 1024 / 1024:.1f}MB"
```

### Step 8: Final Validation (30 minutes)

```powershell
# Run complete test suite
pytest tests/ -v --cov=plugins --cov=bot --cov-report=html --cov-report=term

# Check coverage meets threshold
# Should be > 85%

# Run linting
ruff check plugins/ bot/

# Run type checking
mypy plugins/ bot/ --ignore-missing-imports

# Final sanity check
python -c "from plugins.llm.plugin import LLMPlugin; print('LLM OK')"
python -c "from plugins.playlist.plugin import PlaylistPlugin; print('Playlist OK')"
```

---

## 4. Test Cases Summary

### 4.1 Unit Tests
- All existing tests pass after migration
- New plugin tests pass
- No import errors

### 4.2 Integration Tests
- Plugins communicate via NATS
- Cross-plugin features work
- Events flow correctly

### 4.3 End-to-End Tests
- Bot starts correctly
- Commands work as expected
- Data persists correctly

### 4.4 Performance Tests
- Response times acceptable
- Memory usage reasonable
- No resource leaks

---

## 5. Rollback Plan

If migration fails:

```powershell
# Restore backup branch
git checkout backup/pre-cleanup-sprint-19

# Or restore specific files
git checkout main -- lib/playlist.py
git checkout main -- lib/llm/
```

---

## 6. Acceptance Criteria

### 6.1 Migration Complete

- [ ] `lib/playlist.py` removed
- [ ] `lib/llm/` directory removed
- [ ] No remaining imports from old locations
- [ ] Bot starts without errors

### 6.2 Functionality Preserved

- [ ] All LLM features work via plugin
- [ ] All playlist features work via plugin
- [ ] Memory and context preserved
- [ ] MCP tools functional

### 6.3 Quality Standards

- [ ] Test coverage > 85%
- [ ] No linting errors
- [ ] Documentation updated
- [ ] Performance acceptable

### 6.4 Sprint Complete

- [ ] All 8 sorties merged
- [ ] CHANGELOG updated
- [ ] Version bumped
- [ ] Sprint retrospective complete

---

## 7. Sprint Retrospective Template

### What Went Well
- _To be filled after sprint_

### What Could Be Improved
- _To be filled after sprint_

### Action Items for Next Sprint
- _To be filled after sprint_

### Metrics
- Total commits: _
- Test coverage: _%
- Lines added: _
- Lines removed: _
- Days elapsed: _

---

**Commit Message Template:**
```
feat(plugins): Complete Sprint 19 migration

- Remove deprecated lib/playlist.py
- Remove deprecated lib/llm/ directory
- Update bot core to use plugin services
- Add cross-plugin integration tests
- Update documentation

Implements: SPEC-Sortie-8-Integration.md
Completes: Sprint 19 - Core Migrations
Related: PRD-Core-Migrations.md

BREAKING CHANGE: lib/playlist.py and lib/llm/ removed.
Use plugins/playlist/ and plugins/llm/ instead.
```
