# SPEC: Sortie 5 - Integration & Bot Validation

**Sprint:** 22 - Process Isolation  
**Sortie:** 5 of 5  
**Status:** Ready  
**Estimated Duration:** 8 hours  
**Created:** November 26, 2025  

---

## Objective

Integrate all subprocess isolation features into `PluginManager` and **deliver a fully functioning bot**. Validate complete end-to-end flow: bot starts via script → connects to CyTube → receives events → translates to normalized model → broadcasts via NATS → plugins respond → output to CyTube. Ensure Sprint 22 ends with a runnable, working bot, not just infrastructure.

---

## Context

**Current State** (After Sortie 4):
- `PluginProcess` fully implemented with:
  - Subprocess execution
  - Lifecycle management (start/stop/restart)
  - Crash detection and auto-restart
  - Resource monitoring and enforcement
- `PluginManager` has stub methods that don't use `PluginProcess` fully
- Tests cover `PluginProcess` but not integration
- Documentation doesn't cover subprocess isolation
- **Bot not validated end-to-end with subprocess isolation**

**Target State**:
- `PluginManager` uses `PluginProcess` for all plugin operations
- **Bot runs via `run_bot.sh` / `run_bot.bat` scripts**
- **Complete flow works: CyTube → EventBus → NATS → Plugins → Response**
- **`!roll 2d6` command works end-to-end in subprocess**
- All existing tests updated and passing
- New integration tests covering full bot lifecycle
- Documentation complete (architecture, setup, troubleshooting)
- Configuration examples for resource limits

---

## Success Criteria

### Deliverables
- [ ] Update `PluginManager.start_plugin()` integration
- [ ] Update `PluginManager.stop_plugin()` integration
- [ ] Update `PluginManager.restart_plugin()` integration
- [ ] Update `PluginManager.stop_all()` for cleanup
- [ ] Add plugin status API (get state, stats)
- [ ] **Create `run_bot.sh` shell script**
- [ ] **Create `run_bot.bat` batch script**
- [ ] **Validate rosey.py orchestrator works**
- [ ] **Validate CytubeConnector → NATS flow**
- [ ] **Validate dice-roller plugin in subprocess**
- [ ] Fix all existing tests (43 → 43 passing)
- [ ] Add 22 new integration tests
- [ ] Write architecture documentation
- [ ] Write setup guide
- [ ] Write troubleshooting guide

### Quality Gates
- All 65 tests passing (43 existing + 22 new)
- **Bot runs via shell/batch script**
- **Connects to CyTube successfully**
- **Receives and translates CyTube events**
- **Broadcasts events via NATS**
- **Plugins consume NATS events**
- **`!roll 2d6` works end-to-end**
- **Clean shutdown (no zombies)**
- No breaking changes to plugin API
- Documentation complete and reviewed
- Code coverage ≥ 80%

---

## Scope

### In Scope
- `PluginManager` integration with `PluginProcess`
- **Bot startup scripts (run_bot.sh, run_bot.bat)**
- **End-to-end validation (CyTube → NATS → Plugins → Response)**
- **Verify dice-roller works in subprocess**
- Update existing tests
- New integration tests
- Architecture documentation
- Setup guide
- Troubleshooting guide
- Configuration examples

### Out of Scope
- New plugin features - Future sprints
- Hot-reload - Sprint 23
- Metrics dashboard - Sprint 23
- Plugin marketplace - Out of scope
- Performance optimization - Future sprint
- Production deployment - Separate sprint
- Multi-channel support - Future sprint

---

## Requirements

### Functional Requirements

**FR1: Update PluginManager.start_plugin()**
```python
async def start_plugin(self, name: str) -> bool:
    """
    Start a loaded plugin.
    
    Args:
        name: Plugin name
        
    Returns:
        bool: True if started successfully
    """
    if name not in self.plugins:
        logger.error(f"Plugin {name} not loaded")
        return False
    
    if name in self.running:
        logger.warning(f"Plugin {name} already running")
        return False
    
    entry = self.plugins[name]
    
    # Create plugin process
    process = PluginProcess(
        plugin_name=name,
        module_path=entry.metadata.module_path,
        event_bus=self.event_bus,
        config=entry.metadata.config,
        restart_config=entry.metadata.restart_config,
        resource_limits=entry.metadata.resource_limits
    )
    
    # Start subprocess
    success = await process.start()
    
    if success:
        self.running[name] = process
        logger.info(f"Started plugin {name}")
        return True
    else:
        logger.error(f"Failed to start plugin {name}")
        return False
```

**FR2: Update PluginManager.stop_plugin()**
```python
async def stop_plugin(self, name: str, timeout: float = 10.0) -> bool:
    """
    Stop a running plugin.
    
    Args:
        name: Plugin name
        timeout: Max seconds to wait for graceful shutdown
        
    Returns:
        bool: True if stopped successfully
    """
    if name not in self.running:
        logger.warning(f"Plugin {name} not running")
        return True
    
    process = self.running[name]
    
    # Stop subprocess
    success = await process.stop(timeout=timeout)
    
    # Remove from running
    del self.running[name]
    
    logger.info(f"Stopped plugin {name}")
    return success
```

**FR3: Update PluginManager.restart_plugin()**
```python
async def restart_plugin(self, name: str) -> bool:
    """
    Restart a running plugin.
    
    Args:
        name: Plugin name
        
    Returns:
        bool: True if restarted successfully
    """
    if name not in self.running:
        logger.error(f"Plugin {name} not running")
        return False
    
    process = self.running[name]
    
    # Restart subprocess
    success = await process.restart()
    
    if success:
        logger.info(f"Restarted plugin {name}")
    else:
        logger.error(f"Failed to restart plugin {name}")
        # Remove from running if restart failed
        del self.running[name]
    
    return success
```

**FR4: Update PluginManager.stop_all()**
```python
async def stop_all(self, timeout: float = 10.0) -> None:
    """
    Stop all running plugins.
    
    Args:
        timeout: Max seconds to wait per plugin
    """
    logger.info(f"Stopping {len(self.running)} plugins")
    
    # Stop all plugins concurrently
    stop_tasks = [
        process.stop(timeout=timeout)
        for process in self.running.values()
    ]
    
    results = await asyncio.gather(*stop_tasks, return_exceptions=True)
    
    # Log any errors
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Error stopping plugin: {result}")
    
    # Clear running dict
    self.running.clear()
    
    logger.info("All plugins stopped")
```

**FR5: Add Plugin Status API**
```python
def get_plugin_status(self, name: str) -> Optional[Dict[str, Any]]:
    """
    Get current status of a plugin.
    
    Args:
        name: Plugin name
        
    Returns:
        dict: Status information or None if not running
    """
    if name not in self.running:
        return None
    
    process = self.running[name]
    
    status = {
        "name": name,
        "state": process.state.value,
        "pid": process.pid,
        "uptime": time.time() - process.start_time if process.start_time else 0,
        "restart_attempts": len(process.restart_attempts),
    }
    
    # Add resource stats if available
    if process.resource_stats:
        status["resources"] = {
            "cpu_percent": process.resource_stats.current_cpu_percent,
            "memory_mb": process.resource_stats.current_memory_mb,
            "peak_cpu_percent": process.resource_stats.peak_cpu_percent,
            "peak_memory_mb": process.resource_stats.peak_memory_mb,
        }
    
    return status

def get_all_plugin_status(self) -> Dict[str, Dict[str, Any]]:
    """
    Get status of all running plugins.
    
    Returns:
        dict: Plugin name → status dict
    """
    return {
        name: self.get_plugin_status(name)
        for name in self.running.keys()
    }
```

**FR6: Add PluginProcess.start_time Tracking**
```python
# In PluginProcess class
async def start(self) -> bool:
    """Start plugin subprocess (add start_time tracking)"""
    # ... existing start logic ...
    
    if success:
        self.start_time = time.time()
        self.state = PluginState.RUNNING
        # ...
```

### Non-Functional Requirements

**NFR1: Backward Compatibility**
- No breaking changes to plugin API
- Existing plugins work without modification
- Configuration backward compatible

**NFR2: Performance**
- Plugin start: <2s
- Plugin stop: <11s
- stop_all(): <12s (concurrent)
- Status API: <10ms

**NFR3: Reliability**
- 100% test coverage for integration points
- No resource leaks
- Clean shutdown every time

---

## Implementation Plan

### Phase 1: PluginManager Integration (2h)

**Tasks**:
1. Update `start_plugin()` to use PluginProcess
2. Update `stop_plugin()` to use PluginProcess
3. Update `restart_plugin()` to use PluginProcess
4. Update `stop_all()` with concurrent stop
5. Add `get_plugin_status()` methods
6. Add `start_time` tracking to PluginProcess

**Validation**: Manually start/stop dice-roller plugin

### Phase 2: Bot Startup Scripts (1h)

**Tasks**:
1. Create `run_bot.sh` for Unix/Linux/Mac
2. Create `run_bot.bat` for Windows
3. Add Python environment checks
4. Add NATS server check
5. Add proper error handling
6. Test on Windows and Linux

**Shell Script** (`run_bot.sh`):
```bash
#!/bin/bash
# Rosey Bot Startup Script

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found"
    exit 1
fi

# Check NATS server
if ! nc -z localhost 4222 2>/dev/null; then
    echo "Warning: NATS server not running on localhost:4222"
    echo "Starting NATS server..."
    nats-server &
    sleep 2
fi

# Start bot
echo "Starting Rosey Bot..."
python3 rosey.py
```

**Batch Script** (`run_bot.bat`):
```batch
@echo off
REM Rosey Bot Startup Script for Windows

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found
    exit /b 1
)

REM Start bot
echo Starting Rosey Bot...
python rosey.py
pause
```

### Phase 3: End-to-End Validation (2h)

**Tasks**:
1. Validate `rosey.py` orchestrator works
2. Validate EventBus (NATS) connectivity
3. Validate CytubeConnector receives events
4. Validate event translation to normalized model
5. Validate NATS broadcast
6. Validate dice-roller subprocess receives events
7. Validate dice-roller responds via NATS
8. Validate response reaches CyTube

**Validation Flow**:
```
User types: !roll 2d6

CyTube Server
    ↓ (WebSocket)
CytubeConnector.on_chat_message()
    ↓
Translate to normalized event:
{
  "type": "chat.message",
  "user": "alice",
  "message": "!roll 2d6",
  "channel": "test-channel"
}
    ↓
EventBus.publish("cytube.chat.message", event)
    ↓
Router.on_chat_message() receives
    ↓
Parse command: "roll" with args "2d6"
    ↓
EventBus.publish("rosey.command.dice.roll", {args: "2d6"})
    ↓
DiceRollerPlugin subprocess receives via NATS
    ↓
Process roll: [4, 3] = 7
    ↓
EventBus.publish("rosey.event.dice.rolled", {result: ...})
    ↓
Router receives, formats response
    ↓
EventBus.publish("cytube.send.message", {text: "🎲 [4, 3] = 7"})
    ↓
CytubeConnector.on_send_message() receives
    ↓
Send to CyTube via WebSocket
    ↓
User sees: 🎲 [4, 3] = 7
```

**Manual Test**:
```bash
# Terminal 1: Start NATS server
nats-server

# Terminal 2: Start bot
./run_bot.sh

# Terminal 3: Connect to CyTube channel
# Open browser to cytube channel

# Type in chat:
!roll 2d6

# Expected output:
🎲 [4, 3] = 7

# Verify subprocess:
ps aux | grep dice-roller
# Should show subprocess with different PID
```

### Phase 4: Update Existing Tests (1h)

**Tasks**:
1. Review 43 existing tests
2. Update tests for subprocess model
3. Add mocks where needed
4. Fix any broken tests
5. Verify all 43 tests passing

**Common Updates Needed**:
- Mock `PluginProcess` in unit tests
- Add delays for async subprocess operations
- Update assertions for subprocess behavior

### Phase 5: Integration Tests (1h)

**Tasks**:
1. Write 22 new integration tests
2. Cover full plugin lifecycle
3. Test crash recovery scenarios
4. Test resource violations
5. Test concurrent operations

**Tests** (see Testing Strategy below)

### Phase 6: Documentation (1h)

**Tasks**:
1. Write architecture documentation
2. Write setup guide
3. Write troubleshooting guide
4. Add configuration examples
5. Update README

---

## Testing Strategy

### Integration Tests (22 new tests)

**Test 1: Load and Start Plugin**
```python
async def test_load_and_start_plugin():
    """Test loading and starting a plugin"""
    pm = PluginManager(event_bus, config)
    
    # Load plugin
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    
    # Start plugin
    success = await pm.start_plugin("dice-roller")
    assert success
    assert "dice-roller" in pm.running
    
    # Verify subprocess
    process = pm.running["dice-roller"]
    assert process.state == PluginState.RUNNING
    assert process.pid is not None
    
    await pm.stop_all()
```

**Test 2: Stop Plugin**
```python
async def test_stop_plugin():
    """Test stopping a plugin"""
    pm = PluginManager(event_bus, config)
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    await pm.start_plugin("dice-roller")
    
    # Stop plugin
    success = await pm.stop_plugin("dice-roller")
    assert success
    assert "dice-roller" not in pm.running
```

**Test 3: Restart Plugin**
```python
async def test_restart_plugin():
    """Test restarting a plugin"""
    pm = PluginManager(event_bus, config)
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    await pm.start_plugin("dice-roller")
    
    old_pid = pm.running["dice-roller"].pid
    
    # Restart plugin
    success = await pm.restart_plugin("dice-roller")
    assert success
    
    new_pid = pm.running["dice-roller"].pid
    assert new_pid != old_pid
    
    await pm.stop_all()
```

**Test 4: Start Multiple Plugins**
```python
async def test_start_multiple_plugins():
    """Test starting multiple plugins concurrently"""
    pm = PluginManager(event_bus, config)
    
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    pm.load_plugin("8ball", "plugins.8ball.plugin")
    pm.load_plugin("trivia", "plugins.trivia.plugin")
    
    # Start all
    await pm.start_plugin("dice-roller")
    await pm.start_plugin("8ball")
    await pm.start_plugin("trivia")
    
    assert len(pm.running) == 3
    
    await pm.stop_all()
```

**Test 5: Stop All Plugins**
```python
async def test_stop_all_plugins():
    """Test stopping all plugins at once"""
    pm = PluginManager(event_bus, config)
    
    # Start multiple plugins
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    pm.load_plugin("8ball", "plugins.8ball.plugin")
    await pm.start_plugin("dice-roller")
    await pm.start_plugin("8ball")
    
    # Stop all
    await pm.stop_all(timeout=5.0)
    
    assert len(pm.running) == 0
```

**Test 6: Plugin Status API**
```python
async def test_plugin_status():
    """Test getting plugin status"""
    pm = PluginManager(event_bus, config)
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    await pm.start_plugin("dice-roller")
    
    # Get status
    status = pm.get_plugin_status("dice-roller")
    
    assert status is not None
    assert status["name"] == "dice-roller"
    assert status["state"] == "running"
    assert status["pid"] is not None
    assert status["uptime"] > 0
    
    await pm.stop_all()
```

**Test 7: All Plugin Status**
```python
async def test_all_plugin_status():
    """Test getting status of all plugins"""
    pm = PluginManager(event_bus, config)
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    pm.load_plugin("8ball", "plugins.8ball.plugin")
    await pm.start_plugin("dice-roller")
    await pm.start_plugin("8ball")
    
    # Get all status
    all_status = pm.get_all_plugin_status()
    
    assert len(all_status) == 2
    assert "dice-roller" in all_status
    assert "8ball" in all_status
    
    await pm.stop_all()
```

**Test 8: Plugin Auto-Restart After Crash**
```python
async def test_plugin_auto_restart_after_crash():
    """Test plugin auto-restarts after crash"""
    pm = PluginManager(event_bus, config)
    pm.load_plugin("dice-roller", "plugins.dice-roller.plugin")
    await pm.start_plugin("dice-roller")
    
    old_pid = pm.running["dice-roller"].pid
    
    # Kill subprocess
    os.kill(old_pid, signal.SIGKILL)
    
    # Wait for auto-restart
    await asyncio.sleep(2.0)
    
    # Should have restarted
    assert pm.running["dice-roller"].state == PluginState.RUNNING
    assert pm.running["dice-roller"].pid != old_pid
    
    await pm.stop_all()
```

**Test 9: Plugin Gives Up After Max Attempts**
```python
async def test_plugin_gives_up_after_max_attempts():
    """Test plugin gives up after max restart attempts"""
    restart_config = RestartConfig(max_attempts=3, initial_delay=0.1)
    
    pm = PluginManager(event_bus, config)
    pm.load_plugin("crasher", "plugins.crasher.plugin", restart_config=restart_config)
    await pm.start_plugin("crasher")
    
    # Wait for crashes and restarts
    await asyncio.sleep(3.0)
    
    # Should have given up
    assert pm.running["crasher"].state == PluginState.FAILED
```

**Test 10: Resource Violation Triggers Restart**
```python
async def test_resource_violation_triggers_restart():
    """Test resource violation triggers restart"""
    limits = ResourceLimits(max_cpu_percent=5.0, check_interval=1.0)
    
    pm = PluginManager(event_bus, config)
    pm.load_plugin("cpu-hog", "plugins.cpu-hog.plugin", resource_limits=limits)
    await pm.start_plugin("cpu-hog")
    
    old_pid = pm.running["cpu-hog"].pid
    
    # Wait for resource violation and restart
    await asyncio.sleep(5.0)
    
    # Should have been killed and restarted
    new_pid = pm.running["cpu-hog"].pid
    assert new_pid != old_pid
    
    await pm.stop_all()
```

**Test 11-22**: Cover edge cases:
- Starting already running plugin
- Stopping not running plugin
- Restarting not running plugin
- Resource stats in status API
- Uptime calculation
- Concurrent start/stop
- Graceful shutdown timeout
- Force kill on timeout
- Plugin without resource limits
- Plugin without restart config
- Status API for non-existent plugin
- Empty running list

---

## Documentation

### Architecture Documentation

**File**: `docs/ARCHITECTURE.md` (update existing)

**New Section**: "Plugin Subprocess Isolation"

```markdown
## Plugin Subprocess Isolation

### Overview
Each plugin runs in its own subprocess, isolated from the main bot process and other plugins. Communication happens exclusively via NATS messaging.

### Architecture
```
Main Process (rosey.py)
├── EventBus (NATS)
├── PluginManager
│   ├── PluginProcess (dice-roller)
│   │   ├── State: RUNNING
│   │   ├── PID: 12345
│   │   ├── ResourceMonitor
│   │   └── CrashRecovery
│   ├── PluginProcess (8ball)
│   └── PluginProcess (trivia)
└── CytubeConnector
```

### Lifecycle
1. **Load**: PluginManager discovers plugin metadata
2. **Start**: Spawn subprocess, wait for ready event
3. **Run**: Plugin subscribes to NATS subjects, processes messages
4. **Monitor**: Track resources, detect crashes
5. **Stop**: Send SIGTERM, wait for graceful shutdown

### Communication
- All communication via NATS subjects
- No shared memory
- No direct function calls
- Subjects: `rosey.command.*`, `rosey.event.*`, `rosey.plugin.*`

### Crash Recovery
- Auto-restart with exponential backoff (1s, 2s, 4s, 8s, 16s, 30s)
- Give up after N consecutive failures (default 5)
- Reset counter after 60s of success

### Resource Limits
- CPU: default 50%, configurable per plugin
- Memory: default 256MB, configurable per plugin
- Violations: Kill after 2 consecutive checks exceeding limit
- Check interval: 5s
```

### Setup Guide

**File**: `docs/guides/PLUGIN-ISOLATION.md` (new)

```markdown
# Plugin Subprocess Isolation Guide

## Overview
This guide covers setting up and configuring plugin subprocess isolation.

## Configuration

### Basic Configuration
```json
{
  "plugins": {
    "dice-roller": {
      "enabled": true,
      "module_path": "plugins.dice-roller.plugin",
      "restart": {
        "enabled": true,
        "max_attempts": 5
      },
      "resource_limits": {
        "max_cpu_percent": 50.0,
        "max_memory_mb": 256.0
      }
    }
  }
}
```

### Restart Configuration
- `enabled`: Auto-restart on crash (default: true)
- `max_attempts`: Max consecutive restart attempts (default: 5)
- `initial_delay`: First backoff delay (default: 1.0s)
- `max_delay`: Max backoff delay (default: 30.0s)

### Resource Limits
- `max_cpu_percent`: Max CPU usage % (default: 50.0)
- `max_memory_mb`: Max memory in MB (default: 256.0)
- `check_interval`: How often to check (default: 5.0s)
- `violation_threshold`: Consecutive violations before kill (default: 2)

## Monitoring

### Status API
```python
pm = PluginManager(...)
status = pm.get_plugin_status("dice-roller")
print(status)
# {
#   "name": "dice-roller",
#   "state": "running",
#   "pid": 12345,
#   "uptime": 3600.5,
#   "restart_attempts": 0,
#   "resources": {
#     "cpu_percent": 2.3,
#     "memory_mb": 45.2,
#     "peak_cpu_percent": 8.7,
#     "peak_memory_mb": 52.1
#   }
# }
```

### NATS Events
- `rosey.plugin.<name>.ready`: Plugin started
- `rosey.plugin.<name>.crashed`: Plugin crashed
- `rosey.plugin.<name>.resources`: Resource stats (every 5s)
- `rosey.plugin.<name>.resource_violation`: Resource limit exceeded

## Best Practices
1. Set realistic resource limits based on plugin workload
2. Enable auto-restart for production
3. Monitor resource events for capacity planning
4. Test crash recovery during development
```

### Troubleshooting Guide

**File**: `docs/guides/TROUBLESHOOTING.md` (update existing)

**New Section**: "Plugin Subprocess Issues"

```markdown
## Plugin Subprocess Issues

### Plugin Won't Start
**Symptoms**: Plugin state is FAILED immediately after start

**Causes**:
1. Module import error (module not found)
2. No *Plugin class found
3. Plugin crashes during initialize()
4. Readiness timeout (plugin doesn't publish ready event)

**Solutions**:
1. Check module_path in config matches actual path
2. Ensure plugin class name ends with "Plugin"
3. Check plugin logs for errors during initialize()
4. Verify plugin publishes to `rosey.plugin.<name>.ready`

### Plugin Keeps Restarting
**Symptoms**: Plugin crashes and restarts repeatedly

**Causes**:
1. Plugin has logic error causing crash
2. Resource limits too low
3. NATS connection issues

**Solutions**:
1. Check plugin logs for crash reason
2. Increase resource limits if violations reported
3. Verify NATS connection from subprocess
4. Disable auto-restart temporarily to debug

### Plugin Killed for Resource Violation
**Symptoms**: "resource violation" in logs, plugin killed

**Causes**:
1. Plugin using too much CPU or memory
2. Resource limits too restrictive

**Solutions**:
1. Check resource events to see actual usage
2. Increase limits if usage is legitimate
3. Optimize plugin if usage is excessive
4. Check for memory leaks or infinite loops

### Zombie Processes
**Symptoms**: Plugin processes remain after bot shutdown

**Causes**:
1. Improper shutdown (killed before cleanup)
2. Bug in stop() method

**Solutions**:
1. Always use `await pm.stop_all()` before exit
2. Check that SIGTERM handlers work
3. Use `pkill -9 -f rosey` as last resort

### Resource Monitoring Not Working
**Symptoms**: No resource events published

**Causes**:
1. No resource_limits in config
2. psutil not installed
3. Platform compatibility issue

**Solutions**:
1. Add resource_limits to plugin config
2. Install psutil: `pip install psutil`
3. Check psutil works: `python -c "import psutil; print(psutil.cpu_percent())"`
```

---

## Dependencies

### Code Dependencies
- `core/plugin_manager.py` - PluginManager class
- `core/plugin_isolation.py` - PluginProcess class
- All existing tests in `tests/`

---

## Risks & Mitigations

### Risk 1: Breaking Changes
**Impact**: High | **Likelihood**: Low

Integration changes break existing plugins.

**Mitigation**:
- Run all 43 existing tests
- Test with all current plugins (dice-roller, 8ball, trivia)
- Manual end-to-end testing

### Risk 2: Test Failures
**Impact**: Medium | **Likelihood**: Medium

Existing tests fail due to subprocess model.

**Mitigation**:
- Review tests before changes
- Add mocks where needed
- Update assertions for async behavior

### Risk 3: Documentation Incomplete
**Impact**: Low | **Likelihood**: Low

Documentation doesn't cover all scenarios.

**Mitigation**:
- Review with user
- Add examples for common scenarios
- Include troubleshooting for known issues

---

## Rollout Plan

1. Phase 1: PluginManager integration (3h)
2. Phase 2: Update existing tests (2h)
3. Phase 3: Integration tests (2h)
4. Phase 4: Documentation (1h)
5. Code review
6. Manual end-to-end testing
7. Commit to feature branch
8. Sprint review
9. Merge to main

---

## Validation Checklist

### Code
- [ ] All 65 tests passing (43 existing + 22 new)
- [ ] No breaking changes to plugin API
- [ ] Code coverage ≥ 80%
- [ ] No pylint/mypy errors

### Functionality
- [ ] dice-roller works in subprocess
- [ ] 8ball works in subprocess
- [ ] trivia works in subprocess
- [ ] Crash recovery works
- [ ] Resource monitoring works
- [ ] Status API works

### Documentation
- [ ] Architecture updated
- [ ] Setup guide complete
- [ ] Troubleshooting guide complete
- [ ] Configuration examples included
- [ ] README updated

### Manual Testing
- [ ] Start all plugins
- [ ] Test all plugin commands
- [ ] Kill plugin, verify restart
- [ ] Trigger resource violation
- [ ] Stop bot, verify no zombies
- [ ] Check status API

---

## Success Metrics

- **Tests**: 65/65 passing (100%)
- **Coverage**: ≥80%
- **Performance**: Plugin start <2s
- **Reliability**: No crashes during 24h run
- **Documentation**: All guides complete and reviewed

---

**Status**: Ready  
**Prerequisites**: Sorties 1-4 complete  
**Blocked By**: None

---

## Sprint Completion

After this sortie, **Sprint 22** is complete! 🎉

**Deliverables**:
- ✅ Subprocess execution
- ✅ Lifecycle management
- ✅ Crash recovery
- ✅ Resource monitoring
- ✅ Full integration

**Next Sprint**: Sprint 23 - Hot-Reload & Metrics
