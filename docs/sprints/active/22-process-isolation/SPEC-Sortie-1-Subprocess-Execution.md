# SPEC: Sortie 1 - Plugin Subprocess Execution

**Sprint:** 22 - Process Isolation  
**Sortie:** 1 of 5  
**Status:** Ready  
**Estimated Duration:** 10 hours  
**Created:** November 26, 2025  

---

## Objective

Implement the `_run_plugin()` subprocess entry point to actually load and run plugins in separate processes. Each plugin subprocess connects to NATS, imports its module dynamically, instantiates the plugin class, and runs the asyncio event loop.

---

## Context

**Current State**:
- `PluginProcess._run_plugin()` is a 3-line stub that sleeps
- Plugins like `DiceRollerPlugin` are correctly structured (take NATS client, use subjects)
- multiprocessing infrastructure exists but subprocess does nothing
- Plugin subprocess spawns but doesn't execute plugin code

**Target State**:
- `_run_plugin()` runs IN the subprocess
- Connects to NATS from subprocess
- Dynamically imports plugin module
- Finds and instantiates *Plugin class
- Calls `plugin.initialize()` to subscribe to subjects
- Runs asyncio event loop until interrupted
- Handles signals gracefully (SIGTERM, SIGINT)

---

## Success Criteria

### Deliverables
- [ ] `_run_plugin()` implemented with async subprocess entry point
- [ ] NATS connection established in subprocess
- [ ] Dynamic module import working
- [ ] Plugin class discovery implemented
- [ ] Plugin instantiation with NATS client
- [ ] Signal handlers for graceful shutdown
- [ ] 10 tests covering subprocess execution path

### Quality Gates
- `dice-roller` runs in separate process (visible in `ps aux`)
- `!roll 2d6` command works via NATS
- Plugin subprocess has different PID from main process
- Graceful shutdown on SIGTERM (calls `plugin.shutdown()`)
- No connection errors in logs
- All 10 tests passing

---

## Scope

### In Scope
- Implement async subprocess entry point
- NATS connection in subprocess
- Dynamic module import (`importlib.import_module`)
- Plugin class discovery (find class ending in "Plugin")
- Plugin instantiation with config
- Call `plugin.initialize()`
- Signal handlers (SIGTERM, SIGINT)
- Error handling and logging
- Test coverage for subprocess path

### Out of Scope
- Lifecycle management (start/stop) - Sortie 2
- Crash recovery - Sortie 3
- Resource monitoring - Sortie 4
- PluginManager integration - Sortie 5

---

## Requirements

### Functional Requirements

**FR1: Async Subprocess Entry Point**
```python
def _run_plugin(self) -> None:
    """
    Plugin subprocess entry point.
    This runs IN THE SUBPROCESS.
    """
    async def run_async():
        # Implementation here
        pass
    
    asyncio.run(run_async())
```

**FR2: NATS Connection**
```python
# In subprocess
import nats
nc = await nats.connect(servers=self.nats_urls)
logger.info(f"Plugin {self.plugin_name} connected to NATS")
```

**FR3: Dynamic Module Import**
```python
import importlib
import inspect

module = importlib.import_module(self.module_path)
# e.g., module_path = "plugins.dice-roller.plugin"
```

**FR4: Plugin Class Discovery**
```python
# Find class ending with "Plugin"
plugin_class = None
for name, obj in inspect.getmembers(module, inspect.isclass):
    if name.endswith("Plugin"):
        plugin_class = obj
        break

if not plugin_class:
    raise RuntimeError(f"No *Plugin class found in {self.module_path}")
```

**FR5: Plugin Instantiation**
```python
# Instantiate with NATS client and config
plugin = plugin_class(nc, config=self.config)
await plugin.initialize()
```

**FR6: Event Loop**
```python
# Run until interrupted
try:
    await asyncio.Event().wait()
except (KeyboardInterrupt, asyncio.CancelledError):
    logger.info(f"Plugin {self.plugin_name} shutting down")
    await plugin.shutdown()
    await nc.drain()
    await nc.close()
```

**FR7: Signal Handlers**
```python
import signal

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}")
    raise KeyboardInterrupt()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

### Non-Functional Requirements

**NFR1: Logging**
- Set up subprocess logging independently
- Log PID on startup
- Log all major steps (connect, import, initialize)
- Log errors with full stack traces

**NFR2: Error Handling**
- Catch import errors (module not found)
- Catch NATS connection errors
- Catch plugin initialization errors
- Exit with non-zero code on error
- Log all errors before exit

**NFR3: Performance**
- Plugin subprocess start: <500ms
- NATS connection: <200ms
- Module import: <100ms
- Total ready time: <1 second

---

## Implementation Plan

### Phase 1: Basic Structure (2h)

**Tasks**:
1. Create async wrapper in `_run_plugin()`
2. Set up subprocess logging
3. Add basic error handling
4. Test subprocess spawns and exits cleanly

**Code**:
```python
def _run_plugin(self) -> None:
    """Plugin subprocess entry point"""
    # Setup logging for subprocess
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info(f"Plugin {self.plugin_name} subprocess starting (PID {os.getpid()})")
    
    async def run_async():
        logger.info("Async entry point started")
        await asyncio.sleep(1)  # Placeholder
        logger.info("Async entry point complete")
    
    try:
        asyncio.run(run_async())
    except Exception as e:
        logger.error(f"Plugin {self.plugin_name} crashed: {e}", exc_info=True)
        sys.exit(1)
    
    logger.info(f"Plugin {self.plugin_name} exited")
```

### Phase 2: NATS Connection (2h)

**Tasks**:
1. Import nats library
2. Connect to NATS servers
3. Handle connection errors with retry
4. Log connection success

**Code**:
```python
async def run_async():
    # Connect to NATS
    import nats
    
    try:
        nc = await nats.connect(servers=self.nats_urls)
        logger.info(f"Plugin {self.plugin_name} connected to NATS")
    except Exception as e:
        logger.error(f"Failed to connect to NATS: {e}")
        raise
    
    # Rest of implementation...
```

### Phase 3: Module Import & Class Discovery (2h)

**Tasks**:
1. Dynamically import plugin module
2. Find plugin class (name ends with "Plugin")
3. Handle import errors
4. Validate class has required methods

**Code**:
```python
# Import plugin module
import importlib
import inspect

try:
    module = importlib.import_module(self.module_path)
    logger.info(f"Imported module {self.module_path}")
except ImportError as e:
    logger.error(f"Failed to import {self.module_path}: {e}")
    raise

# Find plugin class
plugin_class = None
for name, obj in inspect.getmembers(module, inspect.isclass):
    if name.endswith("Plugin"):
        plugin_class = obj
        logger.info(f"Found plugin class: {name}")
        break

if not plugin_class:
    raise RuntimeError(f"No *Plugin class found in {self.module_path}")

# Validate class has initialize method
if not hasattr(plugin_class, 'initialize'):
    raise RuntimeError(f"{plugin_class.__name__} missing initialize() method")
```

### Phase 4: Plugin Instantiation & Initialization (2h)

**Tasks**:
1. Instantiate plugin with NATS client
2. Call `plugin.initialize()`
3. Handle initialization errors
4. Verify subscriptions registered

**Code**:
```python
# Instantiate plugin
try:
    plugin = plugin_class(nc, config=self.config)
    logger.info(f"Instantiated {plugin_class.__name__}")
except Exception as e:
    logger.error(f"Failed to instantiate plugin: {e}")
    raise

# Initialize (subscribes to NATS subjects)
try:
    await plugin.initialize()
    logger.info(f"Plugin {self.plugin_name} initialized")
except Exception as e:
    logger.error(f"Failed to initialize plugin: {e}")
    raise
```

### Phase 5: Event Loop & Signal Handling (2h)

**Tasks**:
1. Set up signal handlers
2. Run asyncio event loop until interrupted
3. Call `plugin.shutdown()` on exit
4. Drain NATS connection gracefully

**Code**:
```python
import signal

# Signal handler
def signal_handler(signum, frame):
    logger.info(f"Plugin {self.plugin_name} received signal {signum}")
    raise KeyboardInterrupt()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# Run until interrupted
try:
    logger.info(f"Plugin {self.plugin_name} running")
    await asyncio.Event().wait()
except (KeyboardInterrupt, asyncio.CancelledError):
    logger.info(f"Plugin {self.plugin_name} shutting down gracefully")
    
    # Cleanup
    if hasattr(plugin, 'shutdown'):
        await plugin.shutdown()
    
    await nc.drain()
    await nc.close()
    logger.info(f"Plugin {self.plugin_name} shutdown complete")
```

---

## Testing Strategy

### Unit Tests (10 tests)

**Test 1: Subprocess Spawns**
```python
async def test_subprocess_spawns():
    """Test that subprocess is created"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    assert process.process is not None
    assert process.pid is not None
    await process.stop()
```

**Test 2: NATS Connection in Subprocess**
```python
async def test_subprocess_connects_to_nats(mock_nats):
    """Test subprocess connects to NATS"""
    # Mock NATS to track connection
    # Start plugin subprocess
    # Verify NATS.connect() was called
```

**Test 3: Module Import Success**
```python
async def test_module_import_success():
    """Test dynamic module import works"""
    # Start subprocess with valid module path
    # Check logs for "Imported module"
```

**Test 4: Module Import Failure**
```python
async def test_module_import_failure():
    """Test handling of import errors"""
    process = PluginProcess("bad", "nonexistent.module", event_bus)
    await process.start()
    # Wait for failure
    assert process.state == PluginState.FAILED
```

**Test 5: Plugin Class Found**
```python
async def test_plugin_class_discovery():
    """Test finding *Plugin class"""
    # Start subprocess with dice-roller
    # Verify DiceRollerPlugin was found
```

**Test 6: Plugin Class Not Found**
```python
async def test_plugin_class_not_found():
    """Test error when no *Plugin class exists"""
    # Start subprocess with module that has no *Plugin class
    # Verify error logged and subprocess exits
```

**Test 7: Plugin Initialization**
```python
async def test_plugin_initialize_called():
    """Test plugin.initialize() is called"""
    # Mock plugin class
    # Start subprocess
    # Verify initialize() was called
```

**Test 8: SIGTERM Graceful Shutdown**
```python
async def test_sigterm_graceful_shutdown():
    """Test SIGTERM triggers graceful shutdown"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus)
    await process.start()
    
    # Send SIGTERM
    os.kill(process.pid, signal.SIGTERM)
    
    # Wait for shutdown
    await asyncio.sleep(2)
    
    # Verify shutdown() was called
    # Verify NATS drained
    assert not process.is_alive()
```

**Test 9: SIGINT Graceful Shutdown**
```python
async def test_sigint_graceful_shutdown():
    """Test SIGINT (Ctrl+C) triggers graceful shutdown"""
    # Similar to SIGTERM test
```

**Test 10: Exception Handling**
```python
async def test_exception_exits_nonzero():
    """Test unhandled exception exits with code 1"""
    # Start subprocess that raises exception
    # Verify exit code is 1
```

---

## Validation

### Manual Testing

**Test 1: Basic Subprocess Execution**
```bash
# Terminal 1: Start bot
python rosey.py

# Terminal 2: Check processes
ps aux | grep dice-roller
# Should show subprocess with different PID

# Terminal 3: Test command
# In CyTube chat:
!roll 2d6

# Expected output:
🎲 [4, 3] = 7
```

**Test 2: Graceful Shutdown**
```bash
# Start bot
python rosey.py

# Press Ctrl+C
# Check logs for:
# "Plugin dice-roller received signal 2"
# "Plugin dice-roller shutting down gracefully"
# "Plugin dice-roller shutdown complete"

# Verify no zombie processes
ps aux | grep dice-roller
# Should be empty
```

**Test 3: Multiple Plugins**
```bash
# Start bot with multiple plugins
python rosey.py

# Check processes
ps aux | grep python
# Should show:
#   python rosey.py
#   python -c ... (dice-roller)
#   python -c ... (8ball)
#   python -c ... (trivia)

# Test all plugins work
!roll 2d6
!8ball Will this work?
!trivia start
```

---

## Dependencies

### Code Dependencies
- `core/plugin_isolation.py` - PluginProcess class
- `core/event_bus.py` - NATS connection details
- `plugins/dice-roller/plugin.py` - Reference plugin implementation

### External Dependencies
- **nats-py**: NATS client library
- **multiprocessing**: Python stdlib
- **importlib**: Python stdlib
- **inspect**: Python stdlib
- **signal**: Python stdlib

### Configuration
```json
{
  "nats": {
    "servers": ["nats://localhost:4222"]
  },
  "plugins": {
    "dice-roller": {
      "module_path": "plugins.dice-roller.plugin",
      "enabled": true
    }
  }
}
```

---

## Risks & Mitigations

### Risk 1: PYTHONPATH in Subprocess
**Impact**: High | **Likelihood**: Medium

Subprocess might not find plugin modules if PYTHONPATH not set.

**Mitigation**:
- Set PYTHONPATH explicitly before spawning
- Use absolute imports in plugins
- Add project root to sys.path in subprocess
- Test with clean environment

### Risk 2: NATS Connection Race
**Impact**: Medium | **Likelihood**: Low

Main process might send command before subprocess subscribes.

**Mitigation**:
- Add readiness check (plugin publishes "ready" event)
- Add small delay after spawn (200ms)
- Defer in Sortie 2 (proper lifecycle management)

### Risk 3: Signal Handling on Windows
**Impact**: Medium | **Likelihood**: Medium

Windows handles signals differently than Unix.

**Mitigation**:
- Test on Windows specifically
- Use `multiprocessing.Event` for cross-platform shutdown
- Document Windows-specific behavior

---

## Rollout Plan

### Implementation Steps
1. Implement basic async structure (2h)
2. Add NATS connection (2h)
3. Add module import & class discovery (2h)
4. Add plugin instantiation (2h)
5. Add event loop & signals (2h)
6. Write 10 tests
7. Manual validation with dice-roller
8. Code review
9. Commit to feature branch

### Validation Checklist
- [ ] All 10 tests passing
- [ ] dice-roller subprocess visible in ps
- [ ] !roll command works
- [ ] Graceful shutdown works
- [ ] No connection errors in logs
- [ ] Code review approved

---

## Next Steps

After Sortie 1 completion:
- **Sortie 2**: Lifecycle Management (proper start/stop/restart)
- **Sortie 3**: Crash Recovery (auto-restart with backoff)
- **Sortie 4**: Resource Monitoring (CPU/memory limits)
- **Sortie 5**: PluginManager Integration

---

**Status**: Ready  
**Prerequisites**: Sprint 21 complete, all current tests passing  
**Blocked By**: None
