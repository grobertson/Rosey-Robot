# SPEC: Sortie 1 - Hot-Reload Foundation

**Sprint:** 23 - Hot-Reload & Metrics Dashboard  
**Sortie:** 1 of 5  
**Objective:** Implement blue-green deployment for zero-downtime plugin reloads  
**Estimated Effort:** 10 hours  
**Status:** Planned  

---

## Objective

Implement hot-reload capability using blue-green deployment strategy. Enable plugins to be updated with zero user-visible downtime by starting a new version, health-checking it, and atomically swapping it with the old version.

**Target State**:
- Operators can update plugin code and reload without stopping the bot
- Users don't experience any timeout errors or disruption
- Failed reloads automatically rollback to previous version
- Version tracking shows which version is running

---

## Context

### Current State (Post-Sprint 22)

**What Works** ✅:
- Plugins run in isolated subprocesses
- `PluginManager.start_plugin()` spawns subprocess
- `PluginManager.stop_plugin()` stops subprocess cleanly
- `PluginManager.restart_plugin()` does stop + start (cold restart)

**What's Missing** ❌:
- No hot-reload (cold restart has downtime)
- No health checking (can't verify new version works)
- No version tracking (can't tell what version is running)
- No staged deployment (old version stops before new starts)

### Blue-Green Deployment Pattern

```
Traditional Restart (Cold, has downtime):
1. Stop old version  ← Users get errors during this time
2. Start new version ← Users still get errors
3. New version ready

Hot-Reload (Zero downtime):
1. Old version still running
2. Start new version (in staging)
3. Health check new version
4. Atomic swap (new becomes active)
5. Drain old version (wait for in-flight requests)
6. Stop old version
```

**Key Insight**: Subprocess isolation makes this trivial. We can run both versions simultaneously because they're separate processes with separate NATS connections.

---

## Technical Design

### PluginManager Changes

**New State Tracking**:
```python
class PluginManager:
    def __init__(self, event_bus: EventBus, plugin_dir: str):
        self.plugins: Dict[str, PluginProcess] = {}          # Active plugins
        self.staging: Dict[str, PluginProcess] = {}          # Staging (blue-green)
        self.draining: Dict[str, PluginProcess] = {}         # Draining old versions
```

**Hot-Reload Method**:
```python
async def reload_plugin(self, name: str) -> ReloadResult:
    """
    Hot-reload plugin with zero downtime
    
    Steps:
    1. Validate plugin exists and is running
    2. Start new version in staging
    3. Health check new version (5s timeout)
    4. Atomic swap (update routing)
    5. Drain old version (30s timeout)
    6. Stop old version
    
    Returns:
        ReloadResult with success/failure and details
    """
    if name not in self.plugins:
        return ReloadResult(
            success=False,
            error=f"Plugin {name} not loaded",
            old_version=None,
            new_version=None,
        )
        
    old_plugin = self.plugins[name]
    old_version = old_plugin.version
    
    logger.info(f"Starting hot-reload of {name} from {old_version}")
    
    try:
        # Step 1: Start new version in staging
        new_plugin = PluginProcess(name, self.plugin_dir, self.event_bus)
        self.staging[name] = new_plugin
        await new_plugin.start()
        new_version = new_plugin.version
        
        logger.info(f"New version {new_version} started in staging")
        
        # Step 2: Health check (5s timeout)
        health_check_passed = await self._health_check(
            new_plugin, 
            timeout=5.0
        )
        
        if not health_check_passed:
            logger.error(f"Health check failed for {name} v{new_version}")
            await new_plugin.stop()
            del self.staging[name]
            return ReloadResult(
                success=False,
                error="Health check failed",
                old_version=old_version,
                new_version=new_version,
            )
            
        logger.info(f"Health check passed for {name} v{new_version}")
        
        # Step 3: Atomic swap
        self.plugins[name] = new_plugin
        self.draining[name] = old_plugin
        del self.staging[name]
        
        logger.info(f"Swapped {name}: {old_version} → {new_version}")
        
        # Step 4: Drain old version
        await self._drain_and_stop(old_plugin, timeout=30.0)
        del self.draining[name]
        
        logger.info(f"Hot-reload complete: {name} now running {new_version}")
        
        return ReloadResult(
            success=True,
            error=None,
            old_version=old_version,
            new_version=new_version,
            duration=time.time() - start_time,
        )
        
    except Exception as e:
        logger.error(f"Hot-reload failed for {name}: {e}")
        
        # Cleanup staging if exists
        if name in self.staging:
            await self.staging[name].stop()
            del self.staging[name]
            
        return ReloadResult(
            success=False,
            error=str(e),
            old_version=old_version,
            new_version=None,
        )
```

**Health Check Implementation**:
```python
async def _health_check(
    self, 
    plugin: PluginProcess, 
    timeout: float
) -> bool:
    """
    Verify new plugin version is healthy
    
    Strategy:
    1. Wait for plugin to be fully started (state=RUNNING)
    2. Send a test command specific to this plugin type
    3. Verify response within timeout
    4. Check resource usage is within limits
    
    Returns:
        True if healthy, False otherwise
    """
    start_time = time.time()
    
    # Step 1: Wait for RUNNING state (max 2s)
    while plugin.state != PluginState.RUNNING:
        if time.time() - start_time > 2.0:
            logger.error(f"Plugin {plugin.name} didn't reach RUNNING state")
            return False
        await asyncio.sleep(0.1)
        
    # Step 2: Send test command
    test_command = self._get_test_command(plugin.name)
    if test_command:
        try:
            response = await self._send_test_command(
                plugin, 
                test_command, 
                timeout=timeout - (time.time() - start_time)
            )
            
            if not response:
                logger.error(f"Plugin {plugin.name} didn't respond to test command")
                return False
                
            logger.info(f"Plugin {plugin.name} responded to test command: {response}")
            
        except asyncio.TimeoutError:
            logger.error(f"Plugin {plugin.name} test command timed out")
            return False
            
    # Step 3: Check resource usage
    metrics = await plugin.get_metrics()
    
    if metrics.memory_mb > plugin.max_memory_mb:
        logger.error(
            f"Plugin {plugin.name} using too much memory: "
            f"{metrics.memory_mb}MB > {plugin.max_memory_mb}MB"
        )
        return False
        
    if metrics.cpu_percent > 50:  # Reasonable startup CPU check
        logger.warning(
            f"Plugin {plugin.name} high CPU during health check: "
            f"{metrics.cpu_percent}%"
        )
        # Don't fail, just warn (startup can be CPU-intensive)
        
    return True
    
def _get_test_command(self, plugin_name: str) -> Optional[dict]:
    """
    Get appropriate test command for plugin type
    
    Returns command to send or None if no test available
    """
    test_commands = {
        'dice-roller': {'command': 'roll', 'args': '1d6'},
        '8ball': {'command': '8ball', 'args': 'test'},
        'trivia': {'command': 'trivia', 'args': 'categories'},
    }
    return test_commands.get(plugin_name)
    
async def _send_test_command(
    self, 
    plugin: PluginProcess, 
    command: dict, 
    timeout: float
) -> Optional[str]:
    """
    Send test command to plugin and wait for response
    
    Uses NATS request-reply pattern with timeout
    """
    subject = f"rosey.command.{plugin.name}.{command['command']}"
    
    try:
        response = await self.event_bus.request(
            subject,
            {
                'user': '_health_check_',
                'args': command['args'],
                'channel': '_test_',
            },
            timeout=timeout
        )
        return response.get('result')
        
    except asyncio.TimeoutError:
        return None
```

**Drain and Stop Implementation**:
```python
async def _drain_and_stop(
    self, 
    plugin: PluginProcess, 
    timeout: float
) -> None:
    """
    Gracefully drain old plugin version
    
    Steps:
    1. Mark plugin as draining (no new requests)
    2. Wait for in-flight requests to complete
    3. Stop plugin after drain or timeout
    
    Args:
        plugin: Plugin to drain
        timeout: Max time to wait (default 30s)
    """
    logger.info(f"Draining {plugin.name} (max {timeout}s)")
    
    start_time = time.time()
    plugin.state = PluginState.DRAINING
    
    # Wait for in-flight requests
    while time.time() - start_time < timeout:
        # Check if plugin has pending requests
        # (This requires tracking in-flight requests - see below)
        if plugin.in_flight_requests == 0:
            logger.info(f"Plugin {plugin.name} drained (no in-flight requests)")
            break
            
        await asyncio.sleep(0.5)
        
    else:
        # Timeout reached
        elapsed = time.time() - start_time
        logger.warning(
            f"Plugin {plugin.name} drain timeout ({elapsed:.1f}s), "
            f"stopping with {plugin.in_flight_requests} in-flight requests"
        )
        
    # Stop plugin
    await plugin.stop()
    logger.info(f"Plugin {plugin.name} stopped")
```

### PluginProcess Changes

**Version Tracking**:
```python
class PluginProcess:
    def __init__(self, name: str, plugin_dir: str, event_bus: EventBus):
        self.name = name
        self.plugin_dir = plugin_dir
        self.event_bus = event_bus
        
        # Version tracking (NEW)
        self.version = self._get_version()
        self.loaded_at = datetime.now()
        
        # In-flight tracking (NEW)
        self.in_flight_requests = 0
        self._in_flight_lock = asyncio.Lock()
        
    def _get_version(self) -> str:
        """
        Extract version from plugin module
        
        Checks (in order):
        1. plugins/{name}/__version__.py
        2. plugins/{name}/__init__.py (__version__ variable)
        3. Git hash (if in git repo)
        4. "unknown"
        """
        plugin_path = Path(self.plugin_dir) / self.name
        
        # Check __version__.py
        version_file = plugin_path / '__version__.py'
        if version_file.exists():
            content = version_file.read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
                
        # Check __init__.py
        init_file = plugin_path / '__init__.py'
        if init_file.exists():
            content = init_file.read_text()
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
                
        # Check git hash
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                cwd=plugin_path,
                capture_output=True,
                text=True,
                timeout=1.0
            )
            if result.returncode == 0:
                return f"git-{result.stdout.strip()}"
        except Exception:
            pass
            
        return "unknown"
```

**In-Flight Request Tracking**:
```python
async def track_request(self, request_id: str) -> AsyncContextManager:
    """
    Track in-flight request (context manager)
    
    Usage:
        async with plugin.track_request(request_id):
            await process_request()
    """
    @asynccontextmanager
    async def _tracker():
        async with self._in_flight_lock:
            self.in_flight_requests += 1
        try:
            yield
        finally:
            async with self._in_flight_lock:
                self.in_flight_requests -= 1
                
    return _tracker()
```

### ReloadResult Data Class

```python
@dataclass
class ReloadResult:
    """Result of hot-reload operation"""
    success: bool
    error: Optional[str]
    old_version: Optional[str]
    new_version: Optional[str]
    duration: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        return {
            'success': self.success,
            'error': self.error,
            'old_version': self.old_version,
            'new_version': self.new_version,
            'duration': self.duration,
        }
```

---

## Implementation Plan

### Phase 1: Version Tracking (2h)

1. Add `_get_version()` method to `PluginProcess`
2. Add `version` and `loaded_at` attributes
3. Test version extraction from different sources
4. Update tests to verify version tracking

### Phase 2: In-Flight Request Tracking (2h)

1. Add `in_flight_requests` counter to `PluginProcess`
2. Add `track_request()` context manager
3. Integrate into plugin command handlers
4. Test in-flight counting (increment/decrement)

### Phase 3: Health Check System (3h)

1. Implement `_health_check()` method
2. Implement `_get_test_command()` lookup
3. Implement `_send_test_command()` NATS request-reply
4. Test health checks (success and failure cases)

### Phase 4: Hot-Reload Implementation (2h)

1. Implement `reload_plugin()` method
2. Add staging state tracking
3. Implement atomic swap logic
4. Test reload flow (success case)

### Phase 5: Drain and Rollback (1h)

1. Implement `_drain_and_stop()` method
2. Test drain with in-flight requests
3. Test rollback on health check failure
4. Test timeout scenarios

---

## Testing Strategy

### Unit Tests (3 new tests)

**Test 1: Hot-Reload Success**
```python
async def test_reload_plugin_success():
    """Hot-reload updates plugin with zero downtime"""
    # Arrange: Start dice-roller v1.0
    manager = PluginManager(event_bus, plugin_dir)
    await manager.load_plugin('dice-roller')
    old_version = manager.plugins['dice-roller'].version
    
    # Update plugin code to v1.1
    _update_plugin_version('dice-roller', '1.1')
    
    # Act: Reload
    result = await manager.reload_plugin('dice-roller')
    
    # Assert: Success
    assert result.success is True
    assert result.old_version == '1.0'
    assert result.new_version == '1.1'
    assert result.duration < 5.0
    
    # Assert: New version running
    assert manager.plugins['dice-roller'].version == '1.1'
    
    # Assert: Old version stopped
    assert 'dice-roller' not in manager.draining
```

**Test 2: Health Check Failure Rollback**
```python
async def test_reload_health_check_failure():
    """Rollback if new version fails health check"""
    # Arrange: Start dice-roller v1.0
    manager = PluginManager(event_bus, plugin_dir)
    await manager.load_plugin('dice-roller')
    
    # Update plugin code to broken v1.1 (hangs on commands)
    _update_plugin_broken('dice-roller', '1.1')
    
    # Act: Reload (should fail health check)
    result = await manager.reload_plugin('dice-roller')
    
    # Assert: Failure
    assert result.success is False
    assert 'Health check failed' in result.error
    assert result.old_version == '1.0'
    assert result.new_version == '1.1'
    
    # Assert: Old version still running
    assert manager.plugins['dice-roller'].version == '1.0'
    
    # Assert: New version stopped
    assert 'dice-roller' not in manager.staging
```

**Test 3: Version Tracking**
```python
async def test_version_tracking():
    """Version correctly extracted and tracked"""
    # Test __version__.py
    plugin = PluginProcess('dice-roller', plugin_dir, event_bus)
    assert plugin.version == '1.0'
    
    # Test __init__.py
    plugin = PluginProcess('8ball', plugin_dir, event_bus)
    assert plugin.version == '2.1'
    
    # Test git hash
    plugin = PluginProcess('no-version', plugin_dir, event_bus)
    assert plugin.version.startswith('git-')
    
    # Test unknown
    plugin = PluginProcess('empty', plugin_dir, event_bus)
    assert plugin.version == 'unknown'
```

### Manual Testing

**Scenario 1: Hot-Reload During Load**
```bash
# Terminal 1: Start bot
./run_bot.sh

# Terminal 2: Generate load
for i in {1..100}; do
    echo "!roll 2d6"
    sleep 0.1
done

# Terminal 3: Trigger reload
# In CyTube chat:
!admin reload dice-roller

# Expected:
# - All 100 rolls complete successfully
# - No timeout errors
# - No dropped requests
# - Reload completes in <5s
```

**Scenario 2: Health Check Failure**
```bash
# 1. Break dice-roller plugin (add infinite loop)
# 2. Reload via !admin reload dice-roller
# 3. Expected:
#    - Health check fails (timeout)
#    - Old version continues running
#    - Error message: "Health check failed"
```

---

## Quality Gates

**Must Pass Before Merge**:
- [ ] All 3 new tests passing
- [ ] Hot-reload completes in <3s (measured)
- [ ] Zero dropped requests during reload (verified via load test)
- [ ] Health check rollback works (manual test with broken plugin)
- [ ] Version tracking works for all extraction methods
- [ ] Code coverage >75% for new code

**Manual Validation**:
- [ ] Reload dice-roller during live usage (no user errors)
- [ ] Reload fails correctly with broken plugin
- [ ] Check logs show version change (v1.0 → v1.1)

---

## Rollout

**Branch**: `feature/hot-reload`  
**Merge to**: `main` after Sprint 23  
**Deployment**: Requires Sprint 22 (subprocess isolation)  

**Config Changes**: None (hot-reload is API-level, no config needed)

---

## Follow-Up Work

**Sprint 24 Enhancements**:
- Multi-plugin reload (`reload_all()`)
- A/B testing (run two versions, split traffic)
- Canary deployments (gradual rollout)
- Reload scheduling (reload at specific time)

**Technical Debt**:
- In-flight tracking assumes NATS request-reply (won't track fire-and-forget)
- Health checks are plugin-specific (need generic health check method)

---

**End of Sortie 1 Spec**
