# PRD: Sprint 22 - Process Isolation

**Sprint:** 22 - Process Isolation  
**Status:** Planned  
**Created:** November 26, 2025  
**Target Completion:** December 2025 (1 week)  

---

## Executive Summary

**Problem**: Plugins currently run in-process. The `PluginProcess` class exists with subprocess management methods, but `_run_plugin()` is a stub that just sleeps. A plugin crash can take down the entire bot. The architecture promises "plugins can run in separate processes via NATS" but this isn't implemented.

**Solution**: Complete the `PluginProcess` implementation to spawn actual plugin subprocesses. Each plugin connects to NATS independently and communicates via event subjects. Add crash recovery, resource monitoring, and graceful lifecycle management.

**Opportunity**: The architecture is already NATS-first. Plugins like `DiceRollerPlugin` are designed to take a NATS client and communicate entirely via subjects. We just need to make them run in separate OS processes instead of the main process.

**Timeline**: 1 week (5 sorties) to production-ready subprocess isolation with auto-restart and resource limits.

---

## Background

### Current State (Post-Sprint 21)

**What Works** ✅:
- Plugin architecture is NATS-first (no direct dependencies)
- `DiceRollerPlugin` demonstrates correct pattern (takes NATS client, uses subjects)
- `PluginProcess` class exists with lifecycle methods
- `ResourceMonitor` exists with psutil integration
- `PluginIPC` wraps EventBus for plugin communication
- 43 tests passing (100% pass rate)
- Test coverage: 46% overall

**What's Missing** ❌:
- `_run_plugin()` is a 3-line stub that sleeps
- Plugins run in main process (not isolated)
- No subprocess spawning
- No crash recovery
- No resource limit enforcement
- `plugin_isolation.py` coverage: 34%

**Critical Insight**: All the infrastructure exists. We just need to implement the subprocess entry point that loads a plugin module and runs its NATS event loop.

### Why Process Isolation Now

**Architectural Promise**:
```markdown
# From docs/ARCHITECTURE.md:
### Future: Process Isolation
Architecture supports plugins in separate processes:
- Plugin connects to same NATS server
- Subscribes to plugin.my-plugin.* subjects
- Publishes to cytube.send.* for responses
```

**Risk Without Isolation**:
- Plugin infinite loop → bot hangs
- Plugin memory leak → bot crashes
- Plugin segfault → bot dies
- No resource limits → one plugin starves others

**Benefit With Isolation**:
- Plugin crashes don't affect bot
- Resource limits per plugin
- Can run plugins on different servers (future)
- Easier debugging (separate PIDs/logs)

---

## Goals & Success Criteria

### Primary Goals

1. **Subprocess Execution**: Plugins run as separate OS processes
2. **Crash Recovery**: Automatic restart with exponential backoff
3. **Resource Monitoring**: Track and enforce CPU/memory limits
4. **Lifecycle Management**: Clean start/stop/restart without zombies
5. **Production Ready**: 54 tests, 75%+ coverage, zero manual supervision

### Success Criteria

**Functional**:
- [ ] `dice-roller` runs in separate process (visible in `ps aux`)
- [ ] Commands work via NATS (`!roll 2d6` responds correctly)
- [ ] Plugin crash triggers auto-restart (1s, 2s, 4s backoff)
- [ ] Resource limits enforced (kill plugin if >limit)
- [ ] No zombie processes after stop

**Quality**:
- [ ] 54 new tests (all passing)
- [ ] `plugin_isolation.py` coverage: 34% → 75%
- [ ] Zero flaky tests
- [ ] Documentation updated

**Performance**:
- [ ] Plugin spawn time: <500ms
- [ ] Memory overhead: <20MB per plugin
- [ ] Crash recovery: <2s (first attempt)
- [ ] Support 10+ plugins concurrently

---

## Architecture

### Subprocess Model

```
Main Process (rosey.py)
├── EventBus (NATS client → localhost:4222)
├── PluginManager
│   ├── PluginProcess("dice-roller")  ← Spawns subprocess
│   ├── PluginProcess("8ball")
│   └── PluginProcess("trivia")
└── CytubeConnector

---

Subprocess: dice-roller (PID 12345)
├── NATS client (connects to localhost:4222)
├── DiceRollerPlugin instance
└── asyncio event loop
    ├── Subscribes: rosey.command.dice.*
    └── Publishes: rosey.event.dice.*

Subprocess: 8ball (PID 12346)
├── NATS client
├── EightBallPlugin instance
└── asyncio event loop
```

**Key Point**: Both processes connect to the same NATS server. They communicate via subjects, not IPC pipes or sockets.

### Plugin Subprocess Entry Point

**Current Stub**:
```python
def _run_plugin(self) -> None:
    """Plugin subprocess entry point (STUB)"""
    logger.info(f"Plugin {self.plugin_name} subprocess started")
    try:
        while True:
            time.sleep(1)  # TODO: Actually run plugin
    except KeyboardInterrupt:
        pass
```

**Target Implementation**:
```python
def _run_plugin(self) -> None:
    """
    Plugin subprocess entry point.
    Runs IN THE SUBPROCESS - loads plugin and runs NATS event loop.
    """
    async def run_async():
        # 1. Connect to NATS
        nc = await nats.connect(self.nats_urls)
        
        # 2. Import plugin module dynamically
        module = importlib.import_module(self.module_path)
        
        # 3. Find *Plugin class
        plugin_class = next(
            obj for name, obj in inspect.getmembers(module)
            if inspect.isclass(obj) and name.endswith("Plugin")
        )
        
        # 4. Instantiate with NATS client
        plugin = plugin_class(nc, config=self.config)
        
        # 5. Initialize (subscribes to NATS subjects)
        await plugin.initialize()
        
        # 6. Run until interrupted
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, asyncio.CancelledError):
            await plugin.shutdown()
            await nc.drain()
    
    asyncio.run(run_async())
```

### Crash Recovery Strategy

```python
# Exponential backoff sequence
attempt_1: 1.0 second
attempt_2: 2.0 seconds
attempt_3: 4.0 seconds
attempt_4: 8.0 seconds
attempt_5: 16.0 seconds
attempt_6+: 30.0 seconds (max)

# Circuit breaker
max_retries: 3 (configurable)
reset_after: 300 seconds stable runtime
```

### Resource Monitoring

```python
# ResourceMonitor tracks (via psutil):
- cpu_percent: Per-core CPU usage
- memory_mb: RSS memory in megabytes
- num_threads: Thread count
- num_fds: File descriptors (Unix only)

# Limits (configurable per plugin):
max_cpu_percent: 50%
max_memory_mb: 100MB
max_threads: 10
```

---

## Sorties Overview

### Sortie 1: Plugin Subprocess Execution (10h)
**Goal**: Make `_run_plugin()` actually run plugins in subprocesses

**Deliverables**:
- Implement subprocess entry point
- NATS connection in subprocess
- Dynamic module import
- Plugin instantiation
- Signal handlers (SIGTERM, SIGINT)
- 10 tests

**Validation**: `dice-roller` runs in separate process, responds to `!roll 2d6`

---

### Sortie 2: Lifecycle Management (8h)
**Goal**: Robust start/stop/restart

**Deliverables**:
- Complete `start()` with process spawning
- Complete `stop()` with timeout escalation (SIGTERM → SIGKILL)
- Implement `restart()` (stop + start)
- Zombie process cleanup
- 12 tests

**Validation**: Plugins start/stop cleanly, no zombies in `ps aux`

---

### Sortie 3: Crash Recovery (8h)
**Goal**: Auto-restart failed plugins

**Deliverables**:
- Crash detection (process exit monitoring)
- Auto-restart with exponential backoff
- Circuit breaker (max retries → FAILED state)
- Restart counter reset after stable period
- 12 tests

**Validation**: `kill -9 <pid>` → plugin restarts in 1s → commands work

---

### Sortie 4: Resource Monitoring (6h)
**Goal**: Track and enforce resource limits

**Deliverables**:
- Activate `ResourceMonitor` for subprocesses
- Start monitoring loop on plugin start
- Kill plugins exceeding limits
- Add resource stats to plugin info API
- 10 tests

**Validation**: Plugin killed and restarted if exceeds memory limit

---

### Sortie 5: Integration & Bot Validation (8h)
**Goal**: Fully functioning bot with subprocess isolation

**Deliverables**:
- Update `PluginManager.start_plugin()` for subprocesses
- Update `PluginManager.stop_plugin()` for subprocesses
- Add plugin status API (uptime, PID, restarts, resources)
- Create `run_bot.sh` and `run_bot.bat` scripts
- End-to-end validation (connect → receive → translate → broadcast → respond)
- Integration tests with full bot lifecycle
- Documentation updates
- 10 tests

**Validation**: 
1. Bot runs via shell script
2. Connects to CyTube successfully
3. Receives CyTube events (chat messages, user joins, media changes)
4. Translates events to normalized model
5. Broadcasts via NATS
6. Plugins consume NATS events
7. `!roll 2d6` works end-to-end
8. Clean shutdown (no zombies)

---

## Dependencies

### External
- **psutil** (5.9.0+): Already in requirements.txt
- **nats-py** (0.13.0+): Already in requirements.txt
- **multiprocessing**: Python stdlib

### Internal
- Sprint 21 complete (test coverage at 80%+)
- All 43 current tests passing
- NATS server running

---

## Risks & Mitigations

### Risk 1: Platform-Specific Multiprocessing
**Impact**: High | **Likelihood**: Medium

Windows/Linux/macOS have different multiprocessing behavior.

**Mitigation**:
- Use multiprocessing "spawn" mode (most portable)
- Test on all platforms in CI
- Document platform-specific quirks
- Use psutil for cross-platform process management

### Risk 2: NATS Connection in Subprocess
**Impact**: High | **Likelihood**: Low

Subprocess might fail to connect to NATS.

**Mitigation**:
- Retry with exponential backoff
- Clear error logging
- Fail plugin start if NATS unavailable
- Document connection requirements

### Risk 3: Module Import Path
**Impact**: Medium | **Likelihood**: Low

Subprocess might not find plugin modules.

**Mitigation**:
- Set PYTHONPATH in subprocess
- Use absolute imports
- Test all existing plugins
- Document import requirements

### Risk 4: Increased Memory Usage
**Impact**: Medium | **Likelihood**: High

Each subprocess adds ~30MB overhead.

**Mitigation**:
- Monitor memory during development
- Set reasonable limits per plugin
- Document memory requirements
- Optimize for production

---

## Timeline

**Total Duration**: 40 hours (1 week @ 8 hours/day)

| Sortie | Duration | Tests | Dependencies |
|--------|----------|-------|--------------|
| 1: Subprocess Execution | 10h | +10 | None |
| 2: Lifecycle Management | 8h | +12 | Sortie 1 |
| 3: Crash Recovery | 8h | +12 | Sortie 1, 2 |
| 4: Resource Monitoring | 6h | +10 | Sortie 1 |
| 5: PluginManager Integration | 8h | +10 | All |

**Critical Path**: Sortie 1 → 2 → 3 → 5 (34h)  
**Parallel Work**: Sortie 4 can start after Sortie 1

---

## Success Validation

### Demo Scenario 1: Basic Subprocess Execution
```bash
# Start bot
python rosey.py

# Check processes
ps aux | grep python
# Output should show:
#   python rosey.py         (main process)
#   python -c '...'         (dice-roller subprocess)
#   python -c '...'         (8ball subprocess)

# Test commands
!roll 2d6
# Output: 🎲 [4, 3] = 7
```

### Demo Scenario 2: Crash Recovery
```bash
# Terminal 1: Run bot
python rosey.py

# Terminal 2: Kill plugin
ps aux | grep dice-roller  # Get PID: 12345
kill -9 12345

# Terminal 1: Bot logs show
# [ERROR] Plugin dice-roller crashed
# [INFO] Restarting dice-roller in 1.0s (attempt 1)
# [INFO] Plugin dice-roller started with PID 12346

# Terminal 3: Verify recovery
!roll 2d6
# Works immediately after restart
```

### Demo Scenario 3: Resource Limits
```bash
# config.json: Set dice-roller max_memory_mb: 50

# Start bot, trigger memory issue
python rosey.py

# Bot logs:
# [WARNING] Plugin dice-roller exceeded memory limit (52.3MB > 50MB)
# [INFO] Killing plugin dice-roller (PID 12345)
# [INFO] Restarting dice-roller in 1.0s

# Commands work after restart
!roll 2d6
```

---

## Rollout Plan

### Branch Strategy
1. Create `feature/sprint-22-process-isolation`
2. Daily commits (one per sortie)
3. PR after Sortie 5
4. Code review focus:
   - Process cleanup (no zombies)
   - Signal handling correctness
   - Error handling completeness
5. Merge to `main`
6. Tag as `v1.1.0-alpha`

### Rollback Plan
If subprocess isolation causes issues:
1. Add feature flag: `use_subprocess_isolation: false`
2. Revert to in-process execution (keep NATS)
3. Fix issues in separate branch
4. Re-enable once stable

---

## Future Enhancements (Sprint 23+)

- **Hot-reload**: Reload plugins without stopping bot
- **Remote plugins**: Plugins on different servers
- **Plugin sandboxing**: seccomp, cgroups
- **GPU monitoring**: Track GPU resources
- **Container isolation**: One Docker container per plugin

---

**Status**: Planned  
**Next Steps**: Write individual sortie specs (SPEC-Sortie-1.md through SPEC-Sortie-5.md)
