# SPEC: Sortie 3 - Plugin Crash Recovery

**Sprint:** 22 - Process Isolation  
**Sortie:** 3 of 5  
**Status:** Ready  
**Estimated Duration:** 8 hours  
**Created:** November 26, 2025  

---

## Objective

Implement automatic crash detection and restart for plugin subprocesses. When a plugin crashes or exits unexpectedly, detect it immediately, log the crash, and restart the plugin with exponential backoff to prevent restart loops.

---

## Context

**Current State** (After Sortie 2):
- Plugins run in subprocesses
- Lifecycle management working (start/stop/restart)
- State tracking functional
- No crash detection
- No automatic restart
- Crashed plugins stay dead

**Target State**:
- Detect plugin crashes within 1 second
- Log crash reason (exit code, signal)
- Auto-restart with exponential backoff (1s, 2s, 4s, 8s, 16s, 30s max)
- Give up after N consecutive failures (default 5)
- Publish crash events to NATS
- Support disabling auto-restart per plugin
- Track restart attempts and timing

---

## Success Criteria

### Deliverables
- [ ] Crash detection mechanism (subprocess monitoring)
- [ ] Auto-restart implementation with exponential backoff
- [ ] Restart attempt tracking (count, timestamps)
- [ ] Failure threshold (give up after N attempts)
- [ ] Crash event publishing to NATS
- [ ] Configuration support (enable/disable, max attempts, backoff)
- [ ] 10 tests covering crash scenarios

### Quality Gates
- Crash detected within 1s of subprocess exit
- First restart happens immediately (0s delay)
- Subsequent restarts follow backoff: 1s, 2s, 4s, 8s, 16s, 30s
- Give up after 5 consecutive failures (configurable)
- Crash events published to NATS
- All 10 tests passing
- Manual crash recovery test passes

---

## Scope

### In Scope
- Subprocess monitoring (watchdog)
- Crash detection (exit code, signal)
- Exponential backoff calculation
- Auto-restart logic
- Restart attempt tracking
- Failure threshold enforcement
- Crash event publishing
- Configuration (restart policy per plugin)
- Test coverage

### Out of Scope
- Resource monitoring during runtime - Sortie 4
- Health checks while running - Sortie 4
- PluginManager integration - Sortie 5
- Crash dump collection - Future enhancement
- Alerting/notifications - Future enhancement

---

## Requirements

### Functional Requirements

**FR1: Restart Configuration**
```python
@dataclass
class RestartConfig:
    """Plugin restart policy configuration"""
    enabled: bool = True                # Auto-restart enabled
    max_attempts: int = 5               # Max consecutive failures
    backoff_multiplier: float = 2.0     # Exponential backoff multiplier
    initial_delay: float = 1.0          # Initial backoff delay (seconds)
    max_delay: float = 30.0             # Max backoff delay (seconds)
    reset_window: float = 60.0          # Reset attempt count after success for this long
```

**FR2: Restart Tracking**
```python
@dataclass
class RestartAttempt:
    """Single restart attempt record"""
    timestamp: float                    # When restart was attempted
    success: bool                       # Whether restart succeeded
    exit_code: Optional[int]            # Exit code of crashed process
    signal: Optional[int]               # Signal that killed process
```

**FR3: Crash Detection**
```python
async def _monitor_subprocess(self) -> None:
    """
    Monitor subprocess and handle crashes.
    Runs continuously while plugin should be running.
    """
    while self.state == PluginState.RUNNING:
        await asyncio.sleep(0.5)
        
        if not self.process.is_alive():
            # Crash detected
            exit_code = self.process.exitcode
            logger.error(f"Plugin {self.plugin_name} crashed (exit code {exit_code})")
            
            # Update state
            self.state = PluginState.FAILED
            
            # Log crash event
            await self._handle_crash(exit_code)
            
            # Auto-restart if enabled
            if self.restart_config.enabled:
                await self._attempt_restart()
            
            break
```

**FR4: Crash Event**
```python
async def _handle_crash(self, exit_code: int) -> None:
    """
    Handle plugin crash.
    
    Args:
        exit_code: Exit code of crashed process
    """
    crash_event = {
        "plugin": self.plugin_name,
        "pid": self.pid,
        "exit_code": exit_code,
        "timestamp": time.time(),
        "restart_attempts": len(self.restart_attempts)
    }
    
    # Publish crash event
    subject = f"rosey.plugin.{self.plugin_name}.crashed"
    await self.event_bus.publish(subject, json.dumps(crash_event).encode())
    
    logger.error(f"Plugin {self.plugin_name} crash: {crash_event}")
```

**FR5: Exponential Backoff**
```python
def _calculate_backoff(self, attempt: int) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Current attempt number (0-indexed)
        
    Returns:
        float: Delay in seconds
    """
    if attempt == 0:
        return 0.0  # First restart immediate
    
    # Exponential: initial * multiplier^(attempt-1)
    delay = self.restart_config.initial_delay * (
        self.restart_config.backoff_multiplier ** (attempt - 1)
    )
    
    # Cap at max_delay
    return min(delay, self.restart_config.max_delay)
```

**FR6: Auto-Restart Logic**
```python
async def _attempt_restart(self) -> bool:
    """
    Attempt to restart plugin with backoff.
    
    Returns:
        bool: True if restarted, False if gave up
    """
    attempt_count = len(self.restart_attempts)
    
    # Check if exceeded max attempts
    if attempt_count >= self.restart_config.max_attempts:
        logger.error(
            f"Plugin {self.plugin_name} exceeded max restart attempts "
            f"({self.restart_config.max_attempts}), giving up"
        )
        self.state = PluginState.FAILED
        return False
    
    # Calculate backoff
    delay = self._calculate_backoff(attempt_count)
    
    if delay > 0:
        logger.info(
            f"Restarting plugin {self.plugin_name} in {delay}s "
            f"(attempt {attempt_count + 1}/{self.restart_config.max_attempts})"
        )
        await asyncio.sleep(delay)
    
    # Record attempt
    attempt = RestartAttempt(
        timestamp=time.time(),
        success=False,
        exit_code=self.process.exitcode if self.process else None,
        signal=None
    )
    self.restart_attempts.append(attempt)
    
    # Attempt restart
    success = await self.restart()
    attempt.success = success
    
    if success:
        logger.info(f"Plugin {self.plugin_name} restart successful")
        # Reset attempts after successful restart
        asyncio.create_task(self._reset_attempts_after_success())
    else:
        logger.error(f"Plugin {self.plugin_name} restart failed")
    
    return success
```

**FR7: Reset Attempt Counter**
```python
async def _reset_attempts_after_success(self) -> None:
    """
    Reset restart attempt counter after sustained success.
    Waits for reset_window before clearing attempts.
    """
    await asyncio.sleep(self.restart_config.reset_window)
    
    # If still running, clear attempts
    if self.state == PluginState.RUNNING:
        logger.info(f"Plugin {self.plugin_name} stable, resetting restart attempts")
        self.restart_attempts.clear()
```

**FR8: Start Monitoring**
```python
async def start(self) -> bool:
    """Start plugin subprocess (modified to include monitoring)"""
    # ... existing start logic ...
    
    if success:
        self.state = PluginState.RUNNING
        
        # Start monitoring task
        self._monitor_task = asyncio.create_task(self._monitor_subprocess())
        
        return True
```

### Non-Functional Requirements

**NFR1: Performance**
- Crash detection: <1s after subprocess exit
- First restart: immediate (0s delay)
- Backoff calculation: <1ms
- Restart event publishing: <50ms

**NFR2: Reliability**
- 100% crash detection (no missed crashes)
- Accurate exit code/signal reporting
- Exponential backoff never exceeds max_delay
- Attempt counter accurate

**NFR3: Configurability**
- Per-plugin restart policy
- Configurable max attempts (default 5)
- Configurable backoff parameters
- Ability to disable auto-restart

---

## Implementation Plan

### Phase 1: Restart Configuration (1h)

**Tasks**:
1. Create `RestartConfig` dataclass
2. Add to `PluginProcess.__init__()`
3. Load from plugin metadata
4. Add default configuration

**Code**:
```python
@dataclass
class RestartConfig:
    enabled: bool = True
    max_attempts: int = 5
    backoff_multiplier: float = 2.0
    initial_delay: float = 1.0
    max_delay: float = 30.0
    reset_window: float = 60.0

class PluginProcess:
    def __init__(
        self,
        plugin_name: str,
        module_path: str,
        event_bus: NATS,
        restart_config: Optional[RestartConfig] = None,
        ...
    ):
        # ... existing init ...
        self.restart_config = restart_config or RestartConfig()
        self.restart_attempts: List[RestartAttempt] = []
        self._monitor_task: Optional[asyncio.Task] = None
```

### Phase 2: Crash Detection (2h)

**Tasks**:
1. Implement `_monitor_subprocess()` watchdog
2. Detect subprocess exit
3. Capture exit code/signal
4. Update state to FAILED
5. Start monitoring task on plugin start

**Code** (see FR3 above)

### Phase 3: Exponential Backoff (1h)

**Tasks**:
1. Implement `_calculate_backoff()` method
2. Test backoff calculation
3. Verify cap at max_delay
4. Document backoff sequence

**Code** (see FR5 above)

**Test backoff sequence**:
```python
def test_backoff_calculation():
    config = RestartConfig(initial_delay=1.0, backoff_multiplier=2.0, max_delay=30.0)
    process = PluginProcess(..., restart_config=config)
    
    assert process._calculate_backoff(0) == 0.0   # Immediate
    assert process._calculate_backoff(1) == 1.0   # 1s
    assert process._calculate_backoff(2) == 2.0   # 2s
    assert process._calculate_backoff(3) == 4.0   # 4s
    assert process._calculate_backoff(4) == 8.0   # 8s
    assert process._calculate_backoff(5) == 16.0  # 16s
    assert process._calculate_backoff(6) == 30.0  # 30s (capped)
    assert process._calculate_backoff(7) == 30.0  # 30s (capped)
```

### Phase 4: Auto-Restart Logic (2h)

**Tasks**:
1. Implement `_attempt_restart()` method
2. Check max attempts
3. Calculate and wait for backoff
4. Record restart attempt
5. Call `restart()` method
6. Handle restart failure

**Code** (see FR6 above)

### Phase 5: Event Publishing & Reset (2h)

**Tasks**:
1. Implement `_handle_crash()` event publishing
2. Implement `_reset_attempts_after_success()`
3. Test event publishing
4. Test attempt reset logic

**Code** (see FR4 and FR7 above)

---

## Testing Strategy

### Unit Tests (10 tests)

**Test 1: Crash Detection**
```python
async def test_crash_detection():
    """Test crash is detected"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    # Kill subprocess
    os.kill(process.pid, signal.SIGKILL)
    
    # Wait for crash detection
    await asyncio.sleep(1.5)
    
    assert process.state == PluginState.FAILED
```

**Test 2: First Restart Immediate**
```python
async def test_first_restart_immediate():
    """Test first restart has no delay"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    # Kill subprocess
    os.kill(process.pid, signal.SIGKILL)
    
    # Should restart immediately
    start_time = time.time()
    await asyncio.sleep(2.0)  # Wait for restart
    
    assert process.state == PluginState.RUNNING
    assert len(process.restart_attempts) == 1
    
    # First restart should be immediate (within 1s of crash)
    elapsed = time.time() - start_time
    assert elapsed < 2.0
```

**Test 3: Exponential Backoff**
```python
async def test_exponential_backoff():
    """Test backoff increases exponentially"""
    config = RestartConfig(initial_delay=1.0, max_delay=30.0)
    process = PluginProcess("test", "plugins.crasher.plugin", event_bus, restart_config=config)
    
    # Crash multiple times
    for i in range(5):
        await process.start()
        os.kill(process.pid, signal.SIGKILL)
        await asyncio.sleep(0.5)
    
    # Check backoff delays
    delays = [
        process.restart_attempts[i+1].timestamp - process.restart_attempts[i].timestamp
        for i in range(len(process.restart_attempts) - 1)
    ]
    
    # Should be roughly [0, 1, 2, 4]
    assert delays[0] < 0.5  # Immediate
    assert 0.8 < delays[1] < 1.2  # ~1s
    assert 1.8 < delays[2] < 2.2  # ~2s
    assert 3.8 < delays[3] < 4.2  # ~4s
```

**Test 4: Max Attempts**
```python
async def test_max_attempts():
    """Test giving up after max attempts"""
    config = RestartConfig(max_attempts=3, initial_delay=0.1)
    process = PluginProcess("test", "plugins.crasher.plugin", event_bus, restart_config=config)
    
    await process.start()
    
    # Crash 3 times
    for i in range(3):
        os.kill(process.pid, signal.SIGKILL)
        await asyncio.sleep(0.5)
    
    # Should have given up
    assert process.state == PluginState.FAILED
    assert len(process.restart_attempts) == 3
```

**Test 5: Crash Event Published**
```python
async def test_crash_event_published():
    """Test crash event published to NATS"""
    crash_events = []
    
    async def crash_handler(msg):
        crash_events.append(json.loads(msg.data.decode()))
    
    await event_bus.subscribe("rosey.plugin.test.crashed", cb=crash_handler)
    
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    # Kill subprocess
    os.kill(process.pid, signal.SIGKILL)
    await asyncio.sleep(1.5)
    
    assert len(crash_events) == 1
    assert crash_events[0]["plugin"] == "test"
    assert crash_events[0]["exit_code"] == -9  # SIGKILL
```

**Test 6: Restart Success Resets Counter**
```python
async def test_restart_success_resets_counter():
    """Test successful restart resets attempt counter"""
    config = RestartConfig(reset_window=1.0)
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, restart_config=config)
    
    # Crash once
    await process.start()
    os.kill(process.pid, signal.SIGKILL)
    await asyncio.sleep(1.5)
    
    assert len(process.restart_attempts) == 1
    
    # Wait for reset window
    await asyncio.sleep(1.5)
    
    # Counter should be reset
    assert len(process.restart_attempts) == 0
```

**Test 7: Auto-Restart Disabled**
```python
async def test_auto_restart_disabled():
    """Test disabling auto-restart"""
    config = RestartConfig(enabled=False)
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, restart_config=config)
    
    await process.start()
    os.kill(process.pid, signal.SIGKILL)
    await asyncio.sleep(1.5)
    
    # Should stay FAILED, no restarts
    assert process.state == PluginState.FAILED
    assert len(process.restart_attempts) == 0
```

**Test 8: Backoff Capped**
```python
async def test_backoff_capped():
    """Test backoff doesn't exceed max_delay"""
    config = RestartConfig(initial_delay=1.0, max_delay=5.0)
    process = PluginProcess("test", "plugins.crasher.plugin", event_bus, restart_config=config)
    
    # Many crashes
    for i in range(10):
        delay = process._calculate_backoff(i)
        assert delay <= 5.0  # Never exceeds max
```

**Test 9: Exit Code Captured**
```python
async def test_exit_code_captured():
    """Test exit code is captured and reported"""
    process = PluginProcess("test", "plugins.exit-code-plugin.plugin", event_bus)
    await process.start()
    
    # Plugin exits with code 42
    # (need to create test plugin that exits with specific code)
    
    await asyncio.sleep(1.5)
    
    assert len(process.restart_attempts) > 0
    assert process.restart_attempts[0].exit_code == 42
```

**Test 10: Monitor Task Cleanup**
```python
async def test_monitor_task_cleanup():
    """Test monitoring task is cleaned up on stop"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    assert process._monitor_task is not None
    
    await process.stop()
    
    # Monitor task should be cancelled
    assert process._monitor_task.cancelled() or process._monitor_task.done()
```

---

## Validation

### Manual Testing

**Test 1: Crash and Auto-Restart**
```bash
# Terminal 1: Start bot
python rosey.py

# Terminal 2: Monitor processes
watch -n 1 'ps aux | grep dice-roller'

# Terminal 3: Kill plugin
pkill -9 -f dice-roller

# Observe:
# - Crash detected (logs show crash event)
# - Plugin restarts immediately (new PID appears)
# - !roll still works
```

**Test 2: Multiple Crashes with Backoff**
```bash
# Start bot
python rosey.py

# Kill plugin repeatedly
pkill -9 -f dice-roller
sleep 2
pkill -9 -f dice-roller
sleep 3
pkill -9 -f dice-roller

# Observe logs:
# - First restart: immediate
# - Second restart: ~1s delay
# - Third restart: ~2s delay
# - Fourth restart: ~4s delay
```

**Test 3: Max Attempts Reached**
```bash
# Edit config to set max_attempts: 3
# Create plugin that crashes immediately on start

# Start bot
python rosey.py

# Observe logs:
# - 3 restart attempts
# - "exceeded max restart attempts, giving up"
# - Plugin stays in FAILED state
```

---

## Dependencies

### Code Dependencies
- `core/plugin_isolation.py` - PluginProcess (Sorties 1 & 2)
- `core/event_bus.py` - NATS for crash events

### External Dependencies
- **asyncio**: Task monitoring
- **time**: Timestamps and delays
- **signal**: Exit code/signal handling

### Configuration
```json
{
  "plugins": {
    "dice-roller": {
      "restart": {
        "enabled": true,
        "max_attempts": 5,
        "initial_delay": 1.0,
        "max_delay": 30.0,
        "backoff_multiplier": 2.0,
        "reset_window": 60.0
      }
    }
  }
}
```

---

## Risks & Mitigations

### Risk 1: Restart Loop
**Impact**: High | **Likelihood**: Medium

Plugin crashes immediately on start, causing infinite restart loop.

**Mitigation**:
- Max attempts limit (default 5)
- Exponential backoff slows restarts
- Log prominent warning after 3 attempts
- Disable auto-restart as last resort

### Risk 2: Monitoring Overhead
**Impact**: Low | **Likelihood**: Low

Continuous subprocess monitoring adds CPU overhead.

**Mitigation**:
- 0.5s polling interval (low overhead)
- Only monitor while RUNNING
- Cancel task when stopped

### Risk 3: Reset Window Too Short
**Impact**: Medium | **Likelihood**: Low

Attempt counter resets before plugin proven stable.

**Mitigation**:
- Default 60s reset window
- Configurable per plugin
- Only reset if state == RUNNING

---

## Rollout Plan

1. Implement restart configuration (1h)
2. Implement crash detection (2h)
3. Implement exponential backoff (1h)
4. Implement auto-restart logic (2h)
5. Implement event publishing & reset (2h)
6. Write 10 tests
7. Manual validation
8. Code review
9. Commit to feature branch

---

## Next Steps

After Sortie 3 completion:
- **Sortie 4**: Resource Monitoring (CPU/memory limits, kill violators)
- **Sortie 5**: PluginManager Integration (wire it all together)

---

**Status**: Ready  
**Prerequisites**: Sorties 1 & 2 complete  
**Blocked By**: None
