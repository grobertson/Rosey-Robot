# SPEC: Sortie 4 - Resource Monitoring

**Sprint:** 22 - Process Isolation  
**Sortie:** 4 of 5  
**Status:** Ready  
**Estimated Duration:** 8 hours  
**Created:** November 26, 2025  

---

## Objective

Activate and integrate the existing `ResourceMonitor` class to track CPU and memory usage of plugin subprocesses. Enforce configurable resource limits and terminate plugins that exceed their allocated resources to prevent system degradation.

---

## Context

**Current State** (After Sortie 3):
- Plugins run in subprocesses
- Crash recovery working
- `ResourceMonitor` class exists but is unused
- No resource enforcement
- No limits on CPU/memory usage
- Misbehaving plugins can consume all system resources

**Existing `ResourceMonitor` Class** (in `core/plugin_isolation.py`):
```python
class ResourceMonitor:
    """Monitor resource usage of a plugin subprocess"""
    
    def __init__(self, pid: int, limits: ResourceLimits):
        self.pid = pid
        self.limits = limits
        self.process = psutil.Process(pid)
        
    def check_limits(self) -> Tuple[bool, Optional[str]]:
        """
        Check if process is within resource limits.
        Returns (is_within_limits, violation_reason)
        """
        try:
            # CPU usage (percentage)
            cpu_percent = self.process.cpu_percent(interval=0.1)
            if cpu_percent > self.limits.max_cpu_percent:
                return False, f"CPU {cpu_percent:.1f}% > {self.limits.max_cpu_percent}%"
            
            # Memory usage (MB)
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            if memory_mb > self.limits.max_memory_mb:
                return False, f"Memory {memory_mb:.1f}MB > {self.limits.max_memory_mb}MB"
            
            return True, None
            
        except psutil.NoSuchProcess:
            return True, None  # Process already dead
```

**Target State**:
- `ResourceMonitor` activated for each plugin subprocess
- Periodic resource checks (every 5 seconds)
- CPU and memory limits enforced
- Plugins violating limits are killed
- Resource usage published to NATS
- Resource stats tracked and logged
- Configurable limits per plugin

---

## Success Criteria

### Deliverables
- [ ] Activate `ResourceMonitor` for each plugin
- [ ] Periodic resource checking (5s interval)
- [ ] Enforce CPU and memory limits
- [ ] Kill plugins violating limits
- [ ] Publish resource events to NATS
- [ ] Resource stats tracking (peak usage)
- [ ] Configuration support (limits per plugin)
- [ ] 10 tests covering resource scenarios

### Quality Gates
- Resource checks run every 5s
- CPU limit violations detected within 6s
- Memory limit violations detected within 6s
- Violating plugins killed within 1s of detection
- Resource stats accurate (±5%)
- All 10 tests passing
- Manual resource limit test passes

---

## Scope

### In Scope
- Activate existing `ResourceMonitor` class
- Periodic resource checking
- CPU limit enforcement
- Memory limit enforcement
- Kill plugins exceeding limits
- Resource event publishing to NATS
- Resource stats tracking
- Configuration (limits per plugin)
- Test coverage

### Out of Scope
- Resource monitoring dashboard - Future enhancement
- Historical resource data storage - Future enhancement
- Predictive resource alerts - Future enhancement
- Resource usage optimization - Future enhancement
- PluginManager integration - Sortie 5

---

## Requirements

### Functional Requirements

**FR1: Resource Limits Configuration**
```python
@dataclass
class ResourceLimits:
    """Resource limits for a plugin subprocess"""
    max_cpu_percent: float = 50.0       # Max CPU usage (%)
    max_memory_mb: float = 256.0        # Max memory (MB)
    check_interval: float = 5.0         # How often to check (seconds)
    violation_threshold: int = 2        # Consecutive violations before kill
```

**FR2: Resource Stats Tracking**
```python
@dataclass
class ResourceStats:
    """Resource usage statistics"""
    current_cpu_percent: float
    current_memory_mb: float
    peak_cpu_percent: float
    peak_memory_mb: float
    total_checks: int
    violations: int
    last_check: float  # timestamp
```

**FR3: Start Resource Monitoring**
```python
async def _start_resource_monitoring(self) -> None:
    """Start monitoring plugin resource usage"""
    if not self.resource_limits:
        logger.debug(f"No resource limits for plugin {self.plugin_name}")
        return
    
    # Create resource monitor
    self.resource_monitor = ResourceMonitor(self.pid, self.resource_limits)
    
    # Initialize stats
    self.resource_stats = ResourceStats(
        current_cpu_percent=0.0,
        current_memory_mb=0.0,
        peak_cpu_percent=0.0,
        peak_memory_mb=0.0,
        total_checks=0,
        violations=0,
        last_check=time.time()
    )
    
    # Start monitoring task
    self._resource_task = asyncio.create_task(self._monitor_resources())
    
    logger.info(
        f"Started resource monitoring for {self.plugin_name} "
        f"(CPU: {self.resource_limits.max_cpu_percent}%, "
        f"Memory: {self.resource_limits.max_memory_mb}MB)"
    )
```

**FR4: Resource Monitoring Loop**
```python
async def _monitor_resources(self) -> None:
    """Monitor plugin resource usage periodically"""
    consecutive_violations = 0
    
    while self.state == PluginState.RUNNING:
        await asyncio.sleep(self.resource_limits.check_interval)
        
        # Check limits
        within_limits, violation_reason = self.resource_monitor.check_limits()
        
        # Update stats
        self.resource_stats.current_cpu_percent = self.resource_monitor.process.cpu_percent()
        self.resource_stats.current_memory_mb = (
            self.resource_monitor.process.memory_info().rss / 1024 / 1024
        )
        self.resource_stats.peak_cpu_percent = max(
            self.resource_stats.peak_cpu_percent,
            self.resource_stats.current_cpu_percent
        )
        self.resource_stats.peak_memory_mb = max(
            self.resource_stats.peak_memory_mb,
            self.resource_stats.current_memory_mb
        )
        self.resource_stats.total_checks += 1
        self.resource_stats.last_check = time.time()
        
        # Publish resource event
        await self._publish_resource_event()
        
        if not within_limits:
            consecutive_violations += 1
            self.resource_stats.violations += 1
            
            logger.warning(
                f"Plugin {self.plugin_name} resource violation "
                f"({consecutive_violations}/{self.resource_limits.violation_threshold}): "
                f"{violation_reason}"
            )
            
            # Kill if threshold exceeded
            if consecutive_violations >= self.resource_limits.violation_threshold:
                logger.error(
                    f"Plugin {self.plugin_name} exceeded resource limits, killing"
                )
                await self._kill_for_resource_violation(violation_reason)
                break
        else:
            consecutive_violations = 0  # Reset on success
```

**FR5: Publish Resource Event**
```python
async def _publish_resource_event(self) -> None:
    """Publish current resource usage to NATS"""
    event = {
        "plugin": self.plugin_name,
        "pid": self.pid,
        "cpu_percent": self.resource_stats.current_cpu_percent,
        "memory_mb": self.resource_stats.current_memory_mb,
        "peak_cpu_percent": self.resource_stats.peak_cpu_percent,
        "peak_memory_mb": self.resource_stats.peak_memory_mb,
        "timestamp": time.time()
    }
    
    subject = f"rosey.plugin.{self.plugin_name}.resources"
    await self.event_bus.publish(subject, json.dumps(event).encode())
```

**FR6: Kill for Resource Violation**
```python
async def _kill_for_resource_violation(self, reason: str) -> None:
    """
    Kill plugin for exceeding resource limits.
    
    Args:
        reason: Description of violation
    """
    violation_event = {
        "plugin": self.plugin_name,
        "pid": self.pid,
        "reason": reason,
        "cpu_percent": self.resource_stats.current_cpu_percent,
        "memory_mb": self.resource_stats.current_memory_mb,
        "timestamp": time.time()
    }
    
    # Publish violation event
    subject = f"rosey.plugin.{self.plugin_name}.resource_violation"
    await self.event_bus.publish(subject, json.dumps(violation_event).encode())
    
    logger.error(
        f"Killing plugin {self.plugin_name} for resource violation: {reason}"
    )
    
    # Force kill (don't wait for graceful shutdown)
    if self.process and self.process.is_alive():
        self.process.kill()
        self.process.join(timeout=2)
    
    self.state = PluginState.FAILED
    
    # Crash recovery will restart plugin
```

**FR7: Update start() to Enable Monitoring**
```python
async def start(self) -> bool:
    """Start plugin subprocess (updated to include resource monitoring)"""
    # ... existing start logic ...
    
    if success:
        self.state = PluginState.RUNNING
        
        # Start subprocess monitoring (crash detection)
        self._monitor_task = asyncio.create_task(self._monitor_subprocess())
        
        # Start resource monitoring
        if self.resource_limits:
            await self._start_resource_monitoring()
        
        return True
```

**FR8: Cleanup Resource Monitoring**
```python
async def stop(self, timeout: float = 10.0) -> bool:
    """Stop plugin subprocess (updated to cleanup resource monitoring)"""
    # Cancel resource monitoring task
    if self._resource_task:
        self._resource_task.cancel()
        try:
            await self._resource_task
        except asyncio.CancelledError:
            pass
        self._resource_task = None
    
    # ... existing stop logic ...
```

### Non-Functional Requirements

**NFR1: Performance**
- Resource checks: <100ms per plugin
- Check interval: 5s (configurable)
- Minimal overhead (<1% CPU for monitoring)
- Event publishing: <50ms

**NFR2: Accuracy**
- CPU usage: ±5% accuracy
- Memory usage: ±5% accuracy
- Peak tracking: 100% accurate

**NFR3: Configurability**
- Per-plugin limits
- Configurable check interval
- Configurable violation threshold
- Ability to disable monitoring

---

## Implementation Plan

### Phase 1: Configuration & Data Structures (1h)

**Tasks**:
1. Create `ResourceStats` dataclass
2. Update `ResourceLimits` with violation threshold
3. Add to `PluginProcess.__init__()`
4. Load from plugin metadata

**Code**:
```python
@dataclass
class ResourceLimits:
    max_cpu_percent: float = 50.0
    max_memory_mb: float = 256.0
    check_interval: float = 5.0
    violation_threshold: int = 2

@dataclass
class ResourceStats:
    current_cpu_percent: float
    current_memory_mb: float
    peak_cpu_percent: float
    peak_memory_mb: float
    total_checks: int
    violations: int
    last_check: float

class PluginProcess:
    def __init__(
        self,
        plugin_name: str,
        module_path: str,
        event_bus: NATS,
        resource_limits: Optional[ResourceLimits] = None,
        ...
    ):
        # ... existing init ...
        self.resource_limits = resource_limits
        self.resource_monitor: Optional[ResourceMonitor] = None
        self.resource_stats: Optional[ResourceStats] = None
        self._resource_task: Optional[asyncio.Task] = None
```

### Phase 2: Start Resource Monitoring (2h)

**Tasks**:
1. Implement `_start_resource_monitoring()`
2. Create ResourceMonitor instance
3. Initialize ResourceStats
4. Start monitoring task
5. Update `start()` to call monitoring

**Code** (see FR3 above)

### Phase 3: Resource Monitoring Loop (2h)

**Tasks**:
1. Implement `_monitor_resources()` loop
2. Periodic resource checks
3. Update stats (current, peak)
4. Track consecutive violations
5. Kill on threshold exceeded

**Code** (see FR4 above)

### Phase 4: Event Publishing (1h)

**Tasks**:
1. Implement `_publish_resource_event()`
2. Publish to `rosey.plugin.<name>.resources`
3. Include all stats in event
4. Test event publishing

**Code** (see FR5 above)

### Phase 5: Kill for Violation (2h)

**Tasks**:
1. Implement `_kill_for_resource_violation()`
2. Publish violation event
3. Force kill subprocess
4. Update state to FAILED
5. Cleanup monitoring task

**Code** (see FR6 above)

---

## Testing Strategy

### Unit Tests (10 tests)

**Test 1: Resource Monitoring Starts**
```python
async def test_resource_monitoring_starts():
    """Test resource monitoring starts with plugin"""
    limits = ResourceLimits(max_cpu_percent=50.0, max_memory_mb=256.0)
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    
    assert process.resource_monitor is not None
    assert process.resource_stats is not None
    assert process._resource_task is not None
    
    await process.stop()
```

**Test 2: Resource Stats Updated**
```python
async def test_resource_stats_updated():
    """Test resource stats are updated periodically"""
    limits = ResourceLimits(check_interval=1.0)
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    
    # Wait for checks
    await asyncio.sleep(3.0)
    
    assert process.resource_stats.total_checks >= 2
    assert process.resource_stats.current_cpu_percent > 0
    assert process.resource_stats.current_memory_mb > 0
    
    await process.stop()
```

**Test 3: CPU Limit Violation**
```python
async def test_cpu_limit_violation():
    """Test plugin killed when CPU limit exceeded"""
    limits = ResourceLimits(
        max_cpu_percent=5.0,  # Very low limit
        check_interval=1.0,
        violation_threshold=2
    )
    process = PluginProcess("test", "plugins.cpu-hog.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    
    # Wait for violations
    await asyncio.sleep(5.0)
    
    # Should be killed for CPU violation
    assert process.state == PluginState.FAILED
    assert not process.process.is_alive()
```

**Test 4: Memory Limit Violation**
```python
async def test_memory_limit_violation():
    """Test plugin killed when memory limit exceeded"""
    limits = ResourceLimits(
        max_memory_mb=50.0,  # Very low limit
        check_interval=1.0,
        violation_threshold=2
    )
    process = PluginProcess("test", "plugins.memory-hog.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    
    # Wait for violations
    await asyncio.sleep(5.0)
    
    # Should be killed for memory violation
    assert process.state == PluginState.FAILED
```

**Test 5: Consecutive Violations Required**
```python
async def test_consecutive_violations_required():
    """Test plugin not killed for single violation"""
    limits = ResourceLimits(
        max_cpu_percent=20.0,
        violation_threshold=3  # Need 3 consecutive
    )
    process = PluginProcess("test", "plugins.spikey-plugin.plugin", event_bus, resource_limits=limits)
    
    # Plugin that spikes CPU occasionally but not sustained
    await process.start()
    
    await asyncio.sleep(10.0)
    
    # Should still be running (no consecutive violations)
    assert process.state == PluginState.RUNNING
    
    await process.stop()
```

**Test 6: Resource Events Published**
```python
async def test_resource_events_published():
    """Test resource events published to NATS"""
    resource_events = []
    
    async def resource_handler(msg):
        resource_events.append(json.loads(msg.data.decode()))
    
    await event_bus.subscribe("rosey.plugin.test.resources", cb=resource_handler)
    
    limits = ResourceLimits(check_interval=1.0)
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    await asyncio.sleep(3.0)
    await process.stop()
    
    # Should have received events
    assert len(resource_events) >= 2
    assert resource_events[0]["plugin"] == "test"
    assert "cpu_percent" in resource_events[0]
    assert "memory_mb" in resource_events[0]
```

**Test 7: Violation Event Published**
```python
async def test_violation_event_published():
    """Test violation event published when plugin killed"""
    violation_events = []
    
    async def violation_handler(msg):
        violation_events.append(json.loads(msg.data.decode()))
    
    await event_bus.subscribe("rosey.plugin.test.resource_violation", cb=violation_handler)
    
    limits = ResourceLimits(max_cpu_percent=5.0, check_interval=1.0)
    process = PluginProcess("test", "plugins.cpu-hog.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    await asyncio.sleep(5.0)
    
    # Should have received violation event
    assert len(violation_events) == 1
    assert violation_events[0]["plugin"] == "test"
    assert "reason" in violation_events[0]
```

**Test 8: Peak Usage Tracked**
```python
async def test_peak_usage_tracked():
    """Test peak CPU and memory tracked correctly"""
    limits = ResourceLimits(check_interval=0.5)
    process = PluginProcess("test", "plugins.variable-load.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    await asyncio.sleep(3.0)
    await process.stop()
    
    # Peak should be >= current
    assert process.resource_stats.peak_cpu_percent >= process.resource_stats.current_cpu_percent
    assert process.resource_stats.peak_memory_mb >= process.resource_stats.current_memory_mb
```

**Test 9: No Limits = No Monitoring**
```python
async def test_no_limits_no_monitoring():
    """Test monitoring not started when limits not provided"""
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, resource_limits=None)
    
    await process.start()
    
    assert process.resource_monitor is None
    assert process.resource_stats is None
    assert process._resource_task is None
    
    await process.stop()
```

**Test 10: Monitoring Cleanup on Stop**
```python
async def test_monitoring_cleanup_on_stop():
    """Test monitoring task cleaned up on stop"""
    limits = ResourceLimits()
    process = PluginProcess("test", "plugins.dice-roller.plugin", event_bus, resource_limits=limits)
    
    await process.start()
    assert process._resource_task is not None
    
    await process.stop()
    
    # Task should be cancelled
    assert process._resource_task.cancelled() or process._resource_task.done()
```

---

## Validation

### Manual Testing

**Test 1: Normal Resource Usage**
```bash
# Start bot with dice-roller
python rosey.py

# Subscribe to resource events
# (separate script or use NATS CLI)
nats sub "rosey.plugin.dice-roller.resources"

# Observe:
# - Resource events every 5s
# - CPU and memory within limits
# - Peak values tracked
```

**Test 2: CPU Limit Violation**
```bash
# Create CPU-hog plugin
# Set low CPU limit in config:
{
  "plugins": {
    "cpu-hog": {
      "resource_limits": {
        "max_cpu_percent": 10.0,
        "check_interval": 2.0,
        "violation_threshold": 2
      }
    }
  }
}

# Start bot
python rosey.py

# Observe logs:
# - "resource violation (1/2): CPU 45.2% > 10.0%"
# - "resource violation (2/2): CPU 47.1% > 10.0%"
# - "Killing plugin cpu-hog for resource violation"
# - Plugin restarts (crash recovery)
```

**Test 3: Memory Limit Violation**
```bash
# Similar to CPU test but with memory-hog plugin
# Set low memory limit (e.g., 50MB)
# Plugin allocates large arrays
# Observe violation and kill
```

---

## Dependencies

### Code Dependencies
- `core/plugin_isolation.py` - PluginProcess, ResourceMonitor (existing)
- `core/event_bus.py` - NATS for events

### External Dependencies
- **psutil**: Already used by ResourceMonitor
- **asyncio**: Task management

### Configuration
```json
{
  "plugins": {
    "dice-roller": {
      "resource_limits": {
        "max_cpu_percent": 50.0,
        "max_memory_mb": 256.0,
        "check_interval": 5.0,
        "violation_threshold": 2
      }
    }
  }
}
```

---

## Risks & Mitigations

### Risk 1: False Positives
**Impact**: Medium | **Likelihood**: Low

Legitimate CPU spikes trigger kills.

**Mitigation**:
- Require consecutive violations (threshold=2)
- Generous default limits (50% CPU, 256MB memory)
- Configurable per plugin
- Log warnings before killing

### Risk 2: Monitoring Overhead
**Impact**: Low | **Likelihood**: Low

Resource monitoring adds CPU overhead.

**Mitigation**:
- 5s check interval (low frequency)
- Efficient psutil calls
- Cancel task when plugin stopped

### Risk 3: psutil Compatibility
**Impact**: Low | **Likelihood**: Low

psutil behaves differently on Windows vs Linux.

**Mitigation**:
- Test on both platforms
- Handle psutil exceptions gracefully
- Use cross-platform psutil APIs

---

## Rollout Plan

1. Implement configuration & data structures (1h)
2. Implement start resource monitoring (2h)
3. Implement monitoring loop (2h)
4. Implement event publishing (1h)
5. Implement kill for violation (2h)
6. Write 10 tests
7. Manual validation
8. Code review
9. Commit to feature branch

---

## Next Steps

After Sortie 4 completion:
- **Sortie 5**: PluginManager Integration (wire everything together, update tests, documentation)

---

**Status**: Ready  
**Prerequisites**: Sorties 1-3 complete  
**Blocked By**: None
