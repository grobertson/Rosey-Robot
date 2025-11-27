# SPEC: Sortie 2 - Metrics Collection

**Sprint:** 23 - Hot-Reload & Metrics Dashboard  
**Sortie:** 2 of 5  
**Objective:** Collect and aggregate plugin metrics over time  
**Estimated Effort:** 8 hours  
**Status:** Planned  

---

## Objective

Implement continuous metrics collection for all running plugins. Track CPU usage, memory, uptime, event counts, and crash history. Maintain rolling window of historical data (1 hour) and provide aggregate calculations (avg/min/max/p95).

**Target State**:
- Background collector polls metrics every 5 seconds
- 1-hour rolling window stored in memory
- Can query current metrics or historical aggregates
- Minimal performance impact (<1% CPU overhead)

---

## Context

### Current State (Post-Sprint 22)

**What Works** ✅:
- `PluginProcess` has `get_metrics()` method
- `ResourceMonitor` tracks CPU/memory via psutil
- Crash count tracked in `PluginProcess.crash_count`
- Process PID available via `PluginProcess.process.pid`

**What's Missing** ❌:
- No continuous collection (one-shot only)
- No historical data (can't see trends)
- No aggregates (can't calculate avg/max)
- No event counting (don't know how many commands processed)
- No centralized collector (each plugin isolated)

### Why Metrics Matter

**Without Metrics**:
```
User: "Bot is slow"
Ops: "Let me check... uh... how?"
Ops: *Checks logs* "I see some errors..."
Ops: *Restarts bot* "Try now?"
User: "Still slow"
Ops: ¯\_(ツ)_/¯
```

**With Metrics**:
```
User: "Bot is slow"
Ops: *Checks dashboard* "8ball plugin using 80% CPU"
Ops: *Checks metrics* "CPU spiked 10 minutes ago"
Ops: *Restarts 8ball* "Fixed"
User: "Working now, thanks!"
```

---

## Technical Design

### MetricsCollector Class

**Core Responsibilities**:
1. Poll all plugins every 5 seconds
2. Store metrics in rolling window (1 hour)
3. Provide current metrics query
4. Calculate aggregates (avg/min/max/p95)
5. Handle plugin restarts (don't lose history)

**Implementation**:
```python
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import time

@dataclass
class MetricSnapshot:
    """Single point-in-time metric reading"""
    timestamp: datetime
    plugin_name: str
    version: str
    pid: Optional[int]
    state: str
    cpu_percent: float
    memory_mb: float
    uptime: float
    event_count: int
    crash_count: int
    
class MetricsCollector:
    """
    Continuous metrics collection for all plugins
    
    Architecture:
    - Background asyncio task polls every 5s
    - Stores last 1 hour (720 snapshots per plugin)
    - Provides query API for current + historical data
    """
    
    def __init__(
        self, 
        plugin_manager: 'PluginManager',
        poll_interval: float = 5.0,
        history_duration: timedelta = timedelta(hours=1)
    ):
        self.plugin_manager = plugin_manager
        self.poll_interval = poll_interval
        self.history_duration = history_duration
        
        # Rolling window: plugin_name -> deque of MetricSnapshot
        self.history: Dict[str, deque[MetricSnapshot]] = {}
        
        # Calculate max history size
        # history_duration / poll_interval = number of snapshots
        self.max_history_size = int(
            history_duration.total_seconds() / poll_interval
        )
        
        # Background task
        self._collector_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Bot start time (for system uptime)
        self.bot_start_time = time.time()
        
    async def start(self):
        """Start background collection loop"""
        if self._running:
            logger.warning("MetricsCollector already running")
            return
            
        self._running = True
        self._collector_task = asyncio.create_task(self._collection_loop())
        logger.info(
            f"MetricsCollector started (poll={self.poll_interval}s, "
            f"history={self.history_duration})"
        )
        
    async def stop(self):
        """Stop background collection loop"""
        self._running = False
        if self._collector_task:
            self._collector_task.cancel()
            try:
                await self._collector_task
            except asyncio.CancelledError:
                pass
        logger.info("MetricsCollector stopped")
        
    async def _collection_loop(self):
        """Background loop: collect metrics every poll_interval"""
        while self._running:
            try:
                await self._collect_snapshot()
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}", exc_info=True)
                
            await asyncio.sleep(self.poll_interval)
            
    async def _collect_snapshot(self):
        """Collect metrics from all plugins"""
        timestamp = datetime.now()
        
        for name, plugin in self.plugin_manager.plugins.items():
            try:
                # Get metrics from plugin
                metrics = await plugin.get_metrics()
                
                # Create snapshot
                snapshot = MetricSnapshot(
                    timestamp=timestamp,
                    plugin_name=name,
                    version=metrics.version,
                    pid=metrics.pid,
                    state=metrics.state,
                    cpu_percent=metrics.cpu_percent,
                    memory_mb=metrics.memory_mb,
                    uptime=metrics.uptime,
                    event_count=metrics.event_count,
                    crash_count=metrics.crash_count,
                )
                
                # Add to history
                if name not in self.history:
                    self.history[name] = deque(maxlen=self.max_history_size)
                    
                self.history[name].append(snapshot)
                
            except Exception as e:
                logger.error(
                    f"Error collecting metrics for {name}: {e}",
                    exc_info=True
                )
                
    def get_current_metrics(self, plugin_name: str) -> Optional[MetricSnapshot]:
        """Get most recent metrics for plugin"""
        if plugin_name not in self.history:
            return None
            
        if not self.history[plugin_name]:
            return None
            
        return self.history[plugin_name][-1]
        
    def get_all_current_metrics(self) -> Dict[str, MetricSnapshot]:
        """Get most recent metrics for all plugins"""
        return {
            name: snapshots[-1]
            for name, snapshots in self.history.items()
            if snapshots
        }
        
    def get_history(
        self, 
        plugin_name: str, 
        duration: Optional[timedelta] = None
    ) -> List[MetricSnapshot]:
        """
        Get historical metrics for plugin
        
        Args:
            plugin_name: Plugin to query
            duration: How far back to look (None = all available)
            
        Returns:
            List of snapshots, newest last
        """
        if plugin_name not in self.history:
            return []
            
        snapshots = list(self.history[plugin_name])
        
        if duration is None:
            return snapshots
            
        # Filter by time window
        cutoff = datetime.now() - duration
        return [s for s in snapshots if s.timestamp >= cutoff]
        
    def get_aggregates(
        self, 
        plugin_name: str, 
        duration: Optional[timedelta] = None
    ) -> Optional['MetricAggregates']:
        """
        Calculate aggregate statistics for plugin
        
        Args:
            plugin_name: Plugin to query
            duration: Time window (None = all available)
            
        Returns:
            MetricAggregates with avg/min/max/p95 or None if no data
        """
        snapshots = self.get_history(plugin_name, duration)
        
        if not snapshots:
            return None
            
        # Extract metric arrays
        cpu_values = [s.cpu_percent for s in snapshots]
        memory_values = [s.memory_mb for s in snapshots]
        
        # Calculate aggregates
        return MetricAggregates(
            plugin_name=plugin_name,
            sample_count=len(snapshots),
            time_span=snapshots[-1].timestamp - snapshots[0].timestamp,
            cpu_avg=sum(cpu_values) / len(cpu_values),
            cpu_min=min(cpu_values),
            cpu_max=max(cpu_values),
            cpu_p95=self._percentile(cpu_values, 95),
            memory_avg=sum(memory_values) / len(memory_values),
            memory_min=min(memory_values),
            memory_max=max(memory_values),
            memory_p95=self._percentile(memory_values, 95),
        )
        
    def get_system_metrics(self) -> 'SystemMetrics':
        """Get overall system metrics"""
        all_current = self.get_all_current_metrics()
        
        return SystemMetrics(
            bot_uptime=time.time() - self.bot_start_time,
            total_plugins=len(self.plugin_manager.plugins),
            plugins_running=sum(
                1 for s in all_current.values() 
                if s.state == 'RUNNING'
            ),
            plugins_crashed=sum(
                1 for s in all_current.values() 
                if s.state == 'CRASHED'
            ),
            total_events=sum(
                s.event_count for s in all_current.values()
            ),
            total_memory_mb=sum(
                s.memory_mb for s in all_current.values()
            ),
        )
        
    @staticmethod
    def _percentile(values: List[float], percentile: int) -> float:
        """Calculate percentile of values (simple implementation)"""
        if not values:
            return 0.0
            
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
```

### Data Classes

**MetricAggregates**:
```python
@dataclass
class MetricAggregates:
    """Aggregate statistics for a plugin"""
    plugin_name: str
    sample_count: int
    time_span: timedelta
    
    # CPU aggregates
    cpu_avg: float
    cpu_min: float
    cpu_max: float
    cpu_p95: float
    
    # Memory aggregates
    memory_avg: float
    memory_min: float
    memory_max: float
    memory_p95: float
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        return {
            'plugin_name': self.plugin_name,
            'sample_count': self.sample_count,
            'time_span_seconds': self.time_span.total_seconds(),
            'cpu': {
                'avg': round(self.cpu_avg, 2),
                'min': round(self.cpu_min, 2),
                'max': round(self.cpu_max, 2),
                'p95': round(self.cpu_p95, 2),
            },
            'memory_mb': {
                'avg': round(self.memory_avg, 2),
                'min': round(self.memory_min, 2),
                'max': round(self.memory_max, 2),
                'p95': round(self.memory_p95, 2),
            },
        }
```

**SystemMetrics**:
```python
@dataclass
class SystemMetrics:
    """Overall bot system metrics"""
    bot_uptime: float
    total_plugins: int
    plugins_running: int
    plugins_crashed: int
    total_events: int
    total_memory_mb: float
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization"""
        return {
            'bot_uptime_seconds': round(self.bot_uptime, 1),
            'bot_uptime_human': self._format_uptime(self.bot_uptime),
            'total_plugins': self.total_plugins,
            'plugins_running': self.plugins_running,
            'plugins_crashed': self.plugins_crashed,
            'total_events': self.total_events,
            'total_memory_mb': round(self.total_memory_mb, 2),
        }
        
    @staticmethod
    def _format_uptime(seconds: float) -> str:
        """Format uptime as human-readable string"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h"
```

### PluginProcess Changes

**Event Counting**:
```python
class PluginProcess:
    def __init__(self, ...):
        # ... existing code ...
        
        # Event tracking (NEW)
        self.event_count = 0
        self._event_count_lock = asyncio.Lock()
        
    async def increment_event_count(self):
        """Increment event counter (thread-safe)"""
        async with self._event_count_lock:
            self.event_count += 1
            
    async def get_metrics(self) -> PluginMetrics:
        """Get current plugin metrics (UPDATED)"""
        return PluginMetrics(
            name=self.name,
            version=self.version,
            pid=self.process.pid if self.process else None,
            state=self.state.name,
            uptime=time.time() - self.start_time if self.start_time else 0,
            cpu_percent=self.monitor.get_cpu_percent(),
            memory_mb=self.monitor.get_memory_mb(),
            event_count=self.event_count,  # NEW
            crash_count=self.crash_count,
            last_crash=self.last_crash_time,
        )
```

**Integration with Router** (event counting):
```python
# In Router.on_chat_message()
async def on_chat_message(self, event: dict):
    """Handle incoming chat message"""
    # ... existing routing logic ...
    
    # Find plugin for command
    plugin_name = self._find_plugin_for_command(command)
    if plugin_name:
        plugin = self.plugin_manager.plugins[plugin_name]
        
        # Increment event count (NEW)
        await plugin.increment_event_count()
        
        # Route to plugin
        await self._route_to_plugin(plugin_name, event)
```

---

## Implementation Plan

### Phase 1: Data Structures (1h)

1. Create `MetricSnapshot` dataclass
2. Create `MetricAggregates` dataclass
3. Create `SystemMetrics` dataclass
4. Add serialization methods (`to_dict()`)

### Phase 2: MetricsCollector Core (3h)

1. Create `MetricsCollector` class
2. Implement `start()` and `stop()` lifecycle
3. Implement `_collection_loop()` background task
4. Implement `_collect_snapshot()` polling
5. Test collection runs continuously

### Phase 3: Query API (2h)

1. Implement `get_current_metrics()`
2. Implement `get_all_current_metrics()`
3. Implement `get_history()` with time filtering
4. Implement `get_system_metrics()`
5. Test query methods return correct data

### Phase 4: Aggregates (1h)

1. Implement `get_aggregates()` method
2. Implement `_percentile()` helper
3. Test aggregate calculations (avg/min/max/p95)

### Phase 5: Event Counting Integration (1h)

1. Add `event_count` to `PluginProcess`
2. Add `increment_event_count()` method
3. Integrate into Router (increment on commands)
4. Test event counting increments correctly

---

## Testing Strategy

### Unit Tests (3 new tests)

**Test 1: Metrics Collection**
```python
async def test_metrics_collection():
    """MetricsCollector polls and stores metrics"""
    # Arrange: Start bot with dice-roller
    manager = PluginManager(event_bus, plugin_dir)
    await manager.load_plugin('dice-roller')
    
    collector = MetricsCollector(manager, poll_interval=1.0)
    await collector.start()
    
    # Act: Wait for 3 polls (3 seconds)
    await asyncio.sleep(3.5)
    
    # Assert: History has 3 snapshots
    history = collector.get_history('dice-roller')
    assert len(history) >= 3
    
    # Assert: Snapshots have correct data
    snapshot = history[-1]
    assert snapshot.plugin_name == 'dice-roller'
    assert snapshot.cpu_percent >= 0
    assert snapshot.memory_mb > 0
    
    await collector.stop()
```

**Test 2: Metrics Aggregation**
```python
async def test_metrics_aggregation():
    """Aggregates calculated correctly"""
    # Arrange: Create collector with known history
    manager = PluginManager(event_bus, plugin_dir)
    collector = MetricsCollector(manager)
    
    # Manually add snapshots with known values
    collector.history['test'] = deque([
        MetricSnapshot(
            timestamp=datetime.now(),
            plugin_name='test',
            version='1.0',
            pid=12345,
            state='RUNNING',
            cpu_percent=cpu,
            memory_mb=50,
            uptime=100,
            event_count=0,
            crash_count=0,
        )
        for cpu in [10, 20, 30, 40, 50]  # Known CPU values
    ])
    
    # Act: Calculate aggregates
    agg = collector.get_aggregates('test')
    
    # Assert: Correct calculations
    assert agg.cpu_avg == 30.0  # (10+20+30+40+50)/5
    assert agg.cpu_min == 10.0
    assert agg.cpu_max == 50.0
    assert agg.cpu_p95 == 50.0  # 95th percentile of [10,20,30,40,50]
    assert agg.sample_count == 5
```

**Test 3: History Retention**
```python
async def test_history_retention():
    """Old metrics pruned after duration limit"""
    # Arrange: Collector with 10-second history
    manager = PluginManager(event_bus, plugin_dir)
    await manager.load_plugin('dice-roller')
    
    collector = MetricsCollector(
        manager, 
        poll_interval=1.0,
        history_duration=timedelta(seconds=10)
    )
    await collector.start()
    
    # Act: Wait for 15 seconds (15 polls)
    await asyncio.sleep(15.5)
    
    # Assert: Only last 10 snapshots retained
    history = collector.get_history('dice-roller')
    assert len(history) <= 10  # Max history size
    
    # Assert: Oldest snapshot is ~10s old
    oldest = history[0]
    age = (datetime.now() - oldest.timestamp).total_seconds()
    assert 9 <= age <= 11  # ~10s old
    
    await collector.stop()
```

### Integration Test

**Test: Event Counting**
```python
async def test_event_counting():
    """Events counted correctly via Router"""
    # Arrange: Start bot with dice-roller
    bot = Rosey(config)
    await bot.start()
    
    # Get initial event count
    plugin = bot.plugin_manager.plugins['dice-roller']
    initial_count = plugin.event_count
    
    # Act: Send 10 commands
    for i in range(10):
        await bot.event_bus.publish('cytube.chat.message', {
            'user': 'test_user',
            'message': '!roll 2d6',
            'channel': 'test',
        })
        await asyncio.sleep(0.1)
        
    # Assert: Event count incremented by 10
    assert plugin.event_count == initial_count + 10
    
    await bot.stop()
```

---

## Quality Gates

**Must Pass Before Merge**:
- [ ] All 3 new tests passing
- [ ] Collection runs continuously (verified via logs)
- [ ] History retention works (verified via test)
- [ ] Aggregates calculated correctly (verified via test)
- [ ] Event counting increments (verified via integration test)
- [ ] CPU overhead <1% (measured via profiling)
- [ ] Memory usage <50MB for 1-hour history (measured)
- [ ] Code coverage >75% for new code

**Performance Validation**:
- [ ] Poll 10 plugins for 1 hour: <1% CPU overhead
- [ ] 1-hour history for 10 plugins: <50MB memory
- [ ] Query aggregates: <10ms response time

---

## Integration

### Wire into rosey.py

```python
class Rosey:
    async def start(self):
        # ... existing startup code ...
        
        # Start metrics collector (NEW)
        self.metrics_collector = MetricsCollector(
            self.plugin_manager,
            poll_interval=self.config.metrics.poll_interval,
            history_duration=timedelta(
                seconds=self.config.metrics.history_duration
            )
        )
        await self.metrics_collector.start()
        logger.info("✅ Metrics collector started")
        
    async def stop(self):
        # Stop metrics collector (NEW)
        if self.metrics_collector:
            await self.metrics_collector.stop()
            
        # ... existing shutdown code ...
```

### Config Schema

```json
{
  "metrics": {
    "enabled": true,
    "poll_interval": 5,
    "history_duration": 3600
  }
}
```

---

## Performance Considerations

### CPU Overhead

**Per Poll**:
- 10 plugins × 5ms each = 50ms
- Poll every 5s = 50ms / 5000ms = 1% CPU

**Optimization**:
- Parallelize plugin queries (asyncio.gather)
- Cache psutil Process objects (don't recreate)

### Memory Usage

**Per Plugin**:
- MetricSnapshot size: ~200 bytes
- 1 hour / 5s intervals = 720 snapshots
- 720 × 200 bytes = 144 KB per plugin

**Total (10 plugins)**:
- 10 × 144 KB = 1.44 MB
- Plus deque overhead: ~2 MB total

**Optimization**:
- Use `__slots__` in MetricSnapshot (save 50% memory)
- Configurable history duration
- Prune old data aggressively

---

## Rollout

**Branch**: `feature/metrics-collection`  
**Merge to**: `main` after Sortie 2 complete  
**Deployment**: Can deploy independently (no external dependencies)  

**Config Changes**: Add `metrics` section to config (with defaults)

---

## Follow-Up Work

**Sortie 3**: Expose metrics via HTTP dashboard  
**Sortie 4**: Add admin commands to query metrics  
**Sprint 24**: Longer retention (24 hours), export to external systems  

---

**End of Sortie 2 Spec**
