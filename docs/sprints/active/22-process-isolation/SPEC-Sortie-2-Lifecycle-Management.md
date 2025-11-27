# SPEC: Sortie 2 - Plugin Lifecycle Management

**Sprint:** 22 - Process Isolation  
**Sortie:** 2 of 5  
**Status:** Ready  
**Estimated Duration:** 8 hours  
**Created:** November 26, 2025  

---

## Objective

Implement robust plugin lifecycle management to properly start, stop, and restart plugin subprocesses. Ensure graceful shutdown without zombie processes, proper cleanup of resources, and reliable state tracking.

---

## Context

**Current State** (After Sortie 1):
- `_run_plugin()` can spawn subprocess and run plugin
- Basic signal handling exists
- No formal lifecycle management
- `start()` and `stop()` methods incomplete
- State tracking minimal
- Restart not implemented

**Target State**:
- `start()` method fully implemented with readiness check
- `stop()` method gracefully shuts down subprocess
- `restart()` method properly implemented
- State machine tracking (STOPPED, STARTING, RUNNING, STOPPING, FAILED)
- No zombie processes after shutdown
- Resource cleanup guaranteed
- Timeout handling for unresponsive plugins

---

## Success Criteria

### Deliverables
- [ ] Complete `start()` implementation with readiness check
- [ ] Complete `stop()` implementation with graceful shutdown
- [ ] Implement `restart()` method
- [ ] State machine with 5 states
- [ ] Zombie process prevention
- [ ] Timeout handling (5s for start, 10s for stop)
- [ ] 12 tests covering lifecycle operations

### Quality Gates
- Start plugin: completes in <2s, state = RUNNING
- Stop plugin: completes in <11s, state = STOPPED, no zombies
- Restart plugin: completes in <13s, state = RUNNING
- Force kill unresponsive plugin after timeout
- All 12 tests passing
- No resource leaks (file descriptors, memory)

---

## Scope

### In Scope
- `start()` implementation
- `stop()` implementation with graceful shutdown
- `restart()` implementation
- State machine (STOPPED, STARTING, RUNNING, STOPPING, FAILED)
- Readiness check (plugin publishes "ready" event)
- Timeout handling (SIGTERM → SIGKILL escalation)
- Zombie process cleanup
- Resource cleanup (NATS, file handles)
- Test coverage

### Out of Scope
- Crash recovery/auto-restart - Sortie 3
- Resource monitoring - Sortie 4
- PluginManager integration - Sortie 5
- Health checks while running - Sortie 4

---

## Requirements

### Functional Requirements

**FR1: State Machine**
```python
from enum import Enum

class PluginState(Enum):
    STOPPED = "stopped"      # Not running
    STARTING = "starting"    # Spawning subprocess
    RUNNING = "running"      # Subprocess active
    STOPPING = "stopping"    # Graceful shutdown in progress
    FAILED = "failed"        # Crashed or failed to start
```

**FR2: Start Method**
```python
async def start(self) -> bool:
    """
    Start the plugin subprocess.
    
    Returns:
        bool: True if started successfully, False otherwise
    """
    if self.state != PluginState.STOPPED:
        logger.warning(f"Plugin {self.plugin_name} already running")
        return False
    
    self.state = PluginState.STARTING
    
    # Spawn subprocess
    self.process = multiprocessing.Process(
        target=self._run_plugin,
        name=f"plugin-{self.plugin_name}"
    )
    self.process.start()
    self.pid = self.process.pid
    
    # Wait for readiness (up to 2s)
    ready = await self._wait_for_ready(timeout=2.0)
    
    if ready:
        self.state = PluginState.RUNNING
        logger.info(f"Plugin {self.plugin_name} started (PID {self.pid})")
        return True
    else:
        self.state = PluginState.FAILED
        logger.error(f"Plugin {self.plugin_name} failed to start")
        await self.stop()  # Clean up
        return False
```

**FR3: Readiness Check**
```python
async def _wait_for_ready(self, timeout: float) -> bool:
    """
    Wait for plugin to publish ready event.
    
    Args:
        timeout: Max seconds to wait
        
    Returns:
        bool: True if ready event received, False if timeout
    """
    ready_subject = f"rosey.plugin.{self.plugin_name}.ready"
    
    ready_event = asyncio.Event()
    
    async def ready_handler(msg):
        ready_event.set()
    
    sub = await self.event_bus.subscribe(ready_subject, cb=ready_handler)
    
    try:
        await asyncio.wait_for(ready_event.wait(), timeout=timeout)
        return True
    except asyncio.TimeoutError:
        logger.warning(f"Plugin {self.plugin_name} ready timeout")
        return False
    finally:
        await sub.unsubscribe()
```

**FR4: Stop Method**
```python
async def stop(self, timeout: float = 10.0) -> bool:
    """
    Stop the plugin subprocess gracefully.
    
    Args:
        timeout: Max seconds to wait before force kill
        
    Returns:
        bool: True if stopped cleanly, False if force killed
    """
    if self.state == PluginState.STOPPED:
        return True
    
    if not self.process or not self.process.is_alive():
        self.state = PluginState.STOPPED
        return True
    
    self.state = PluginState.STOPPING
    logger.info(f"Stopping plugin {self.plugin_name} (PID {self.pid})")
    
    # Send SIGTERM for graceful shutdown
    self.process.terminate()
    
    # Wait for graceful exit
    try:
        await asyncio.wait_for(
            asyncio.to_thread(self.process.join),
            timeout=timeout
        )
        logger.info(f"Plugin {self.plugin_name} stopped gracefully")
        self.state = PluginState.STOPPED
        return True
        
    except asyncio.TimeoutError:
        # Force kill
        logger.warning(f"Plugin {self.plugin_name} timeout, force killing")
        self.process.kill()
        self.process.join(timeout=2)
        self.state = PluginState.STOPPED
        return False
```

**FR5: Restart Method**
```python
async def restart(self) -> bool:
    """
    Restart the plugin subprocess.
    
    Returns:
        bool: True if restarted successfully
    """
    logger.info(f"Restarting plugin {self.plugin_name}")
    
    # Stop current instance
    await self.stop()
    
    # Small delay for cleanup
    await asyncio.sleep(0.5)
    
    # Start new instance
    success = await self.start()
    
    if success:
        logger.info(f"Plugin {self.plugin_name} restarted")
    else:
        logger.error(f"Plugin {self.plugin_name} restart failed")
    
    return success
```

**FR6: Cleanup on Exit**
```python
async def cleanup(self) -> None:
    """Cleanup resources"""
    if self.process and self.process.is_alive():
        await self.stop()
    
    self.process = None
    self.pid = None
    self.state = PluginState.STOPPED
```

**FR7: Ready Event in Plugin**
```python
# In _run_plugin() subprocess, after initialize()
async def run_async():
    # ... connect, import, initialize ...
    
    await plugin.initialize()
    
    # Publish ready event
    ready_subject = f"rosey.plugin.{self.plugin_name}.ready"
    await nc.publish(ready_subject, b"ready")
    logger.info(f"Plugin {self.plugin_name} ready")
    
    # Run event loop
    await asyncio.Event().wait()
```

### Non-Functional Requirements

**NFR1: Performance**
- Start: <2s including readiness check
- Stop (graceful): <11s (10s timeout + 1s cleanup)
- Restart: <13s (stop + start + delays)
- Force kill: <3s after timeout

**NFR2: Reliability**
- No zombie processes after stop
- 100% process cleanup
- No resource leaks (file descriptors, memory)
- State machine always accurate

**NFR3: Observability**
- Log all state transitions
- Log PID on start
- Log shutdown reason (graceful vs forced)
- Log timing for each operation

---

## Implementation Plan

### Phase 1: State Machine (2h)

**Tasks**:
1. Create `PluginState` enum
2. Add state tracking to `PluginProcess`
3. Log state transitions
4. Update tests to check state

**Code**:
```python
class PluginState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"

class PluginProcess:
    def __init__(self, ...):
        # ... existing init ...
        self._state = PluginState.STOPPED
    
    @property
    def state(self) -> PluginState:
        return self._state
    
    @state.setter
    def state(self, new_state: PluginState):
        old_state = self._state
        self._state = new_state
        logger.info(f"Plugin {self.plugin_name} state: {old_state.value} → {new_state.value}")
```

### Phase 2: Start Method (2h)

**Tasks**:
1. Implement `start()` method
2. Spawn subprocess
3. Track PID
4. Update state to STARTING → RUNNING
5. Handle failures

**Code**:
```python
async def start(self) -> bool:
    """Start plugin subprocess"""
    if self.state != PluginState.STOPPED:
        logger.warning(f"Plugin {self.plugin_name} cannot start from {self.state}")
        return False
    
    self.state = PluginState.STARTING
    
    try:
        self.process = multiprocessing.Process(
            target=self._run_plugin,
            name=f"plugin-{self.plugin_name}"
        )
        self.process.start()
        self.pid = self.process.pid
        
        logger.info(f"Spawned plugin {self.plugin_name} (PID {self.pid})")
        
        # Wait for ready (will implement in Phase 3)
        await asyncio.sleep(0.5)  # Temporary delay
        
        if self.process.is_alive():
            self.state = PluginState.RUNNING
            return True
        else:
            self.state = PluginState.FAILED
            return False
            
    except Exception as e:
        logger.error(f"Failed to start plugin {self.plugin_name}: {e}")
        self.state = PluginState.FAILED
        return False
```

### Phase 3: Readiness Check (2h)

**Tasks**:
1. Implement `_wait_for_ready()` method
2. Subscribe to ready subject
3. Use asyncio.Event for signaling
4. Add timeout handling
5. Update plugin subprocess to publish ready event

**Code**:
```python
async def _wait_for_ready(self, timeout: float) -> bool:
    """Wait for plugin ready event"""
    ready_subject = f"rosey.plugin.{self.plugin_name}.ready"
    ready_event = asyncio.Event()
    
    async def ready_handler(msg):
        ready_event.set()
    
    sub = await self.event_bus.subscribe(ready_subject, cb=ready_handler)
    
    try:
        await asyncio.wait_for(ready_event.wait(), timeout=timeout)
        logger.info(f"Plugin {self.plugin_name} ready")
        return True
    except asyncio.TimeoutError:
        logger.warning(f"Plugin {self.plugin_name} ready timeout ({timeout}s)")
        return False
    finally:
        await sub.unsubscribe()

# Update start() to use readiness check
async def start(self) -> bool:
    # ... spawn subprocess ...
    
    ready = await self._wait_for_ready(timeout=2.0)
    if ready:
        self.state = PluginState.RUNNING
        return True
    else:
        self.state = PluginState.FAILED
        await self.stop()
        return False
```

**Update _run_plugin()**:
```python
# In subprocess, after plugin.initialize()
ready_subject = f"rosey.plugin.{self.plugin_name}.ready"
await nc.publish(ready_subject, b"ready")
logger.info(f"Plugin {self.plugin_name} published ready event")
```

### Phase 4: Stop Method (1h)

**Tasks**:
1. Implement `stop()` method
2. Send SIGTERM
3. Wait with timeout
4. Force kill if timeout
5. Cleanup resources

**Code** (see FR4 above)

### Phase 5: Restart Method (1h)

**Tasks**:
1. Implement `restart()` method
2. Call stop() then start()
3. Handle failures
4. Log restart

**Code** (see FR5 above)

---

## Testing Strategy

### Unit Tests (12 tests)

**Test 1: Start from STOPPED**
```python
async def test_start_from_stopped():
    """Test starting plugin from STOPPED state"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    assert process.state == PluginState.STOPPED
    
    success = await process.start()
    assert success
    assert process.state == PluginState.RUNNING
    assert process.pid is not None
    
    await process.stop()
```

**Test 2: Start Already Running**
```python
async def test_start_already_running():
    """Test starting plugin that's already running"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    # Try to start again
    success = await process.start()
    assert not success  # Should fail
    assert process.state == PluginState.RUNNING
    
    await process.stop()
```

**Test 3: Start Failure**
```python
async def test_start_failure():
    """Test handling of start failure"""
    process = PluginProcess("bad", "nonexistent.module", event_bus)
    
    success = await process.start()
    assert not success
    assert process.state == PluginState.FAILED
```

**Test 4: Readiness Timeout**
```python
async def test_readiness_timeout():
    """Test timeout when plugin doesn't publish ready event"""
    # Mock plugin that doesn't publish ready
    process = PluginProcess("slow", "plugins.slow-plugin.plugin", event_bus)
    
    success = await process.start()
    assert not success
    assert process.state == PluginState.FAILED
```

**Test 5: Graceful Stop**
```python
async def test_graceful_stop():
    """Test graceful plugin shutdown"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    success = await process.stop()
    assert success  # Graceful stop
    assert process.state == PluginState.STOPPED
    assert not process.process.is_alive()
```

**Test 6: Force Kill**
```python
async def test_force_kill_on_timeout():
    """Test force kill when plugin doesn't respond to SIGTERM"""
    # Mock plugin that ignores SIGTERM
    process = PluginProcess("stubborn", "plugins.stubborn-plugin.plugin", event_bus)
    await process.start()
    
    success = await process.stop(timeout=1.0)
    assert not success  # Forced kill
    assert process.state == PluginState.STOPPED
    assert not process.process.is_alive()
```

**Test 7: Stop Already Stopped**
```python
async def test_stop_already_stopped():
    """Test stopping plugin that's already stopped"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    
    success = await process.stop()
    assert success
    assert process.state == PluginState.STOPPED
```

**Test 8: Restart Success**
```python
async def test_restart_success():
    """Test successful plugin restart"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    old_pid = process.pid
    
    success = await process.restart()
    assert success
    assert process.state == PluginState.RUNNING
    assert process.pid != old_pid  # New process
```

**Test 9: Restart Failure**
```python
async def test_restart_failure():
    """Test restart when plugin fails to start"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    # Break module path
    process.module_path = "nonexistent.module"
    
    success = await process.restart()
    assert not success
    assert process.state == PluginState.FAILED
```

**Test 10: No Zombie Processes**
```python
async def test_no_zombies():
    """Test that stopped plugins don't leave zombies"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    pid = process.pid
    
    await process.stop()
    
    # Check if process still exists
    try:
        os.kill(pid, 0)  # Signal 0 checks existence
        assert False, "Process still exists (zombie)"
    except OSError:
        pass  # Process doesn't exist (good)
```

**Test 11: State Transitions**
```python
async def test_state_transitions():
    """Test state machine transitions"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    
    # STOPPED → STARTING → RUNNING
    assert process.state == PluginState.STOPPED
    start_task = asyncio.create_task(process.start())
    await asyncio.sleep(0.1)
    assert process.state == PluginState.STARTING
    await start_task
    assert process.state == PluginState.RUNNING
    
    # RUNNING → STOPPING → STOPPED
    stop_task = asyncio.create_task(process.stop())
    await asyncio.sleep(0.1)
    assert process.state == PluginState.STOPPING
    await stop_task
    assert process.state == PluginState.STOPPED
```

**Test 12: Cleanup on Exit**
```python
async def test_cleanup():
    """Test resource cleanup"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    await process.cleanup()
    
    assert process.state == PluginState.STOPPED
    assert process.process is None
    assert process.pid is None
```

---

## Validation

### Manual Testing

**Test 1: Lifecycle Operations**
```bash
# Start bot
python rosey.py

# Check plugin running
ps aux | grep dice-roller

# Stop bot (Ctrl+C)
# Verify no zombies
ps aux | grep dice-roller
# Should be empty
```

**Test 2: Restart Plugin**
```python
# In Python REPL
import asyncio
from core.plugin_isolation import PluginProcess

async def test():
    pm = PluginManager(...)
    await pm.start_plugin("dice-roller")
    
    # Test restart
    process = pm.get_process("dice-roller")
    old_pid = process.pid
    
    await process.restart()
    new_pid = process.pid
    
    print(f"Old PID: {old_pid}, New PID: {new_pid}")
    assert old_pid != new_pid
    
    await pm.stop_all()

asyncio.run(test())
```

**Test 3: Force Kill**
```python
# Create plugin that ignores SIGTERM
# Start it
# Call stop with short timeout
# Verify it gets killed
```

---

## Dependencies

### Code Dependencies
- `core/plugin_isolation.py` - PluginProcess class (Sortie 1)
- `core/event_bus.py` - NATS connection
- `plugins/*/plugin.py` - Must publish ready event

### External Dependencies
- **multiprocessing**: Process management
- **asyncio**: Async operations
- **signal**: SIGTERM/SIGKILL

---

## Risks & Mitigations

### Risk 1: Readiness Timeout Too Short
**Impact**: Medium | **Likelihood**: Medium

Slow-starting plugins fail to start due to timeout.

**Mitigation**:
- Make timeout configurable per plugin
- Default to 2s but allow override
- Log warning if close to timeout

### Risk 2: Zombie Processes
**Impact**: High | **Likelihood**: Low

Improper cleanup leaves zombie processes.

**Mitigation**:
- Always call `process.join()` after terminate/kill
- Add cleanup in `__del__`
- Test extensively on all platforms

### Risk 3: Resource Leaks
**Impact**: Medium | **Likelihood**: Low

File descriptors or memory not cleaned up.

**Mitigation**:
- Ensure NATS connection closed in subprocess
- Test for file descriptor leaks
- Add explicit cleanup method

---

## Rollout Plan

1. Implement state machine (2h)
2. Implement start method (2h)
3. Implement readiness check (2h)
4. Implement stop method (1h)
5. Implement restart method (1h)
6. Write 12 tests
7. Manual validation
8. Code review
9. Commit to feature branch

---

## Next Steps

After Sortie 2 completion:
- **Sortie 3**: Crash Recovery (auto-restart with backoff)
- **Sortie 4**: Resource Monitoring (CPU/memory limits)
- **Sortie 5**: PluginManager Integration

---

**Status**: Ready  
**Prerequisites**: Sortie 1 complete  
**Blocked By**: None
