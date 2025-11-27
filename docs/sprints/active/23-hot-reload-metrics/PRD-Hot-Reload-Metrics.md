# PRD: Sprint 23 - Hot-Reload & Metrics Dashboard

**Sprint:** 23 - Hot-Reload & Metrics Dashboard  
**Status:** Planned  
**Created:** November 26, 2025  
**Target Completion:** December 2025 (1 week)  

---

## Executive Summary

**Problem**: After Sprint 22, plugins run in isolated subprocesses with crash recovery. However, updating a plugin requires stopping the entire bot, deploying code, and restarting. There's also no visibility into plugin health, resource usage, or performance. Operators have no way to answer "Is dice-roller working?" or "Why did 8ball crash 5 times?"

**Solution**: Implement hot-reload capability using blue-green deployment (zero-downtime plugin restart) and add a metrics dashboard (HTTP server on port 8080) with Prometheus endpoints. Add admin commands (`!admin reload dice-roller`, `!admin status`) for runtime operations.

**Opportunity**: Sprint 22's subprocess isolation makes hot-reload trivial - we can spin up a new plugin subprocess while the old one continues serving requests, then swap them atomically. The existing `ResourceMonitor` already tracks CPU/memory, we just need to expose it via HTTP.

**Timeline**: 1 week (5 sorties) to production-ready hot-reload and metrics with admin commands.

---

## Background

### Current State (Post-Sprint 22)

**What Works** ✅:
- Plugins run in isolated subprocesses
- Crash recovery with exponential backoff
- Resource monitoring via `ResourceMonitor`
- Clean lifecycle management (start/stop/restart)
- 54 tests passing, 75%+ coverage
- Commands work end-to-end (`!roll 2d6`)

**What's Missing** ❌:
- No hot-reload (must stop bot to update plugins)
- No metrics dashboard (blind operation)
- No admin commands (manual file edits to configure)
- No Prometheus integration (no external monitoring)
- No historical data (can't see trends)

**Critical Insight**: Subprocess isolation enables zero-downtime deployments. We can start a new version, verify it's healthy, drain traffic from the old version, and swap atomically.

### Why Hot-Reload & Metrics Now

**Operational Pain**:
```
Dev: "I need to update dice-roller"
Ops: "Bot is serving 50 users, we can't restart"
Dev: "When's the next maintenance window?"
Ops: "3am Sunday"
Dev: "That's 4 days away..."
```

**Observability Gap**:
```
User: "8ball isn't responding"
Ops: "Let me check... uh... how do I check?"
Ops: "I guess I'll restart the bot?"
User: "It's been down for 30 minutes"
```

**Benefit With Hot-Reload**:
- Deploy during peak hours (zero downtime)
- A/B test plugin changes
- Instant rollback if new version fails
- No user-visible disruption

**Benefit With Metrics**:
- Real-time plugin health dashboard
- Historical resource usage trends
- Crash/restart events logged
- Prometheus alerts for problems

---

## Goals & Success Criteria

### Primary Goals

1. **Hot-Reload**: Zero-downtime plugin updates via blue-green deployment
2. **Metrics Dashboard**: HTTP server on port 8080 with JSON metrics
3. **Prometheus Integration**: `/metrics` endpoint for external monitoring
4. **Admin Commands**: `!admin reload`, `!admin status`, `!admin restart`
5. **Production Ready**: 65 total tests, 80%+ coverage, operational runbook

### Success Criteria

**Functional**:
- [ ] `!admin reload dice-roller` updates plugin with zero downtime
- [ ] Dashboard shows: uptime, CPU%, memory, event counts, crash history
- [ ] Prometheus endpoint exposes all metrics in standard format
- [ ] Admin commands work: `reload`, `status`, `restart`, `list`
- [ ] Rollback works: if new version crashes, revert to old version

**Quality**:
- [ ] 11 new tests (all passing, 65 total)
- [ ] New modules coverage: 75%+
- [ ] Zero flaky tests
- [ ] Documentation updated (admin guide, metrics guide)

**Performance**:
- [ ] Hot-reload time: <3s (includes health check)
- [ ] Metrics dashboard response: <100ms
- [ ] Zero dropped events during reload
- [ ] Dashboard handles 100 req/sec

**User Experience**:
- [ ] Users don't notice plugin reloads (no timeout errors)
- [ ] Dashboard is easy to read (clear status indicators)
- [ ] Admin commands have confirmation prompts
- [ ] Errors are actionable ("Plugin X failed health check: ...")

---

## Architecture

### Hot-Reload Flow (Blue-Green Deployment)

```
Step 1: Normal operation
PluginManager
  └── PluginProcess("dice-roller", version="v1.0")  ← Active, serving requests

Step 2: Start new version
PluginManager
  ├── PluginProcess("dice-roller", version="v1.0")  ← Still active
  └── PluginProcess("dice-roller-new", version="v1.1")  ← Starting, not serving

Step 3: Health check new version
- Send test command: !roll 1d20
- Verify response within 5s
- Check resource usage < limits

Step 4: Swap (atomic)
PluginManager
  ├── PluginProcess("dice-roller", version="v1.0")  ← Stop accepting new requests
  └── PluginProcess("dice-roller-new", version="v1.1")  ← Now active

Step 5: Drain old version
- Wait for in-flight requests to complete (max 30s)
- Stop old version
- Rename "dice-roller-new" → "dice-roller"

PluginManager
  └── PluginProcess("dice-roller", version="v1.1")  ← Only version running
```

**Rollback**: If health check fails in Step 3, kill new version, keep old version.

### Metrics Dashboard Architecture

```
HTTP Server (port 8080)
├── GET /
│   └── HTML dashboard with refresh
├── GET /api/metrics
│   └── JSON: {plugins: [...], system: {...}}
├── GET /metrics
│   └── Prometheus format
└── GET /api/plugin/{name}
    └── JSON: detailed plugin stats

Data Collection
├── MetricsCollector
│   ├── poll_interval: 5s
│   ├── history: 1 hour (deque)
│   └── aggregates: avg/min/max/p95
└── Prometheus Exporter
    ├── Counter: rosey_events_total{plugin="dice-roller", type="command"}
    ├── Gauge: rosey_plugin_cpu_percent{plugin="dice-roller"}
    ├── Gauge: rosey_plugin_memory_mb{plugin="dice-roller"}
    └── Histogram: rosey_plugin_response_time_seconds{plugin="dice-roller"}
```

### Admin Commands Architecture

```
Admin Plugin (new)
├── Permissions: Only bot owner or configured admins
├── Commands:
│   ├── !admin reload <plugin>     → Hot-reload via PluginManager
│   ├── !admin status [plugin]     → Show plugin status
│   ├── !admin restart <plugin>    → Cold restart (stop + start)
│   ├── !admin list                → List all plugins
│   └── !admin metrics             → Link to dashboard
└── Confirmation:
    !admin reload dice-roller
    → "Reload dice-roller v1.0 → v1.1? Type 'yes' to confirm"
```

**Safety**: Admin commands require:
1. Sender is in `config.admins` list
2. Confirmation for destructive operations
3. Audit log of all admin actions

---

## Technical Design

### Hot-Reload Implementation

**PluginManager Changes**:
```python
class PluginManager:
    def __init__(self, event_bus: EventBus, plugin_dir: str):
        self.plugins: Dict[str, PluginProcess] = {}
        self.staging: Dict[str, PluginProcess] = {}  # New: blue-green staging
        
    async def reload_plugin(self, name: str) -> bool:
        """Hot-reload plugin with zero downtime"""
        if name not in self.plugins:
            raise ValueError(f"Plugin {name} not loaded")
            
        old = self.plugins[name]
        
        # 1. Start new version in staging
        new = PluginProcess(name, self.plugin_dir, self.event_bus)
        self.staging[name] = new
        await new.start()
        
        # 2. Health check (5s timeout)
        healthy = await self._health_check(new, timeout=5.0)
        if not healthy:
            await new.stop()
            del self.staging[name]
            return False
            
        # 3. Atomic swap
        self.plugins[name] = new
        
        # 4. Drain old version
        await self._drain_and_stop(old, timeout=30.0)
        del self.staging[name]
        
        return True
        
    async def _health_check(self, plugin: PluginProcess, timeout: float) -> bool:
        """Send test command, verify response"""
        # Implementation in Sortie 1
        
    async def _drain_and_stop(self, plugin: PluginProcess, timeout: float) -> None:
        """Wait for in-flight requests, then stop"""
        # Implementation in Sortie 1
```

**Version Tracking**:
```python
class PluginProcess:
    def __init__(self, name: str, plugin_dir: str, event_bus: EventBus):
        self.name = name
        self.version = self._get_version()  # Read from plugin/__version__.py
        self.loaded_at = datetime.now()
        
    def _get_version(self) -> str:
        """Extract version from plugin module"""
        # Read plugins/{name}/__version__.py or __init__.py
        # Return version string or "unknown"
```

### Metrics Collection Implementation

**MetricsCollector**:
```python
class MetricsCollector:
    """Collects and aggregates plugin metrics"""
    
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self.history: Dict[str, deque] = {}  # 1 hour rolling window
        self.poll_interval = 5  # seconds
        
    async def start(self):
        """Start background collection loop"""
        while True:
            await self._collect_snapshot()
            await asyncio.sleep(self.poll_interval)
            
    async def _collect_snapshot(self):
        """Collect metrics from all plugins"""
        timestamp = datetime.now()
        for name, plugin in self.plugin_manager.plugins.items():
            metrics = await plugin.get_metrics()
            self.history[name].append({
                'timestamp': timestamp,
                'cpu_percent': metrics.cpu_percent,
                'memory_mb': metrics.memory_mb,
                'uptime': metrics.uptime,
                'event_count': metrics.event_count,
                'crash_count': metrics.crash_count,
            })
            
    def get_aggregates(self, plugin_name: str, duration: timedelta) -> dict:
        """Get avg/min/max/p95 for time window"""
        # Implementation in Sortie 2
```

**PluginProcess Metrics**:
```python
class PluginProcess:
    async def get_metrics(self) -> PluginMetrics:
        """Get current plugin metrics"""
        return PluginMetrics(
            name=self.name,
            version=self.version,
            pid=self.process.pid if self.process else None,
            state=self.state.name,
            uptime=time.time() - self.start_time,
            cpu_percent=self.monitor.get_cpu_percent(),
            memory_mb=self.monitor.get_memory_mb(),
            event_count=self.event_count,  # New: track events processed
            crash_count=self.crash_count,
            last_crash=self.last_crash_time,
        )
```

### Dashboard Implementation

**HTTP Server**:
```python
from aiohttp import web

class MetricsDashboard:
    """HTTP metrics dashboard"""
    
    def __init__(self, collector: MetricsCollector, port: int = 8080):
        self.collector = collector
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        
    def _setup_routes(self):
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/metrics', self.api_metrics)
        self.app.router.add_get('/metrics', self.prometheus_metrics)
        self.app.router.add_get('/api/plugin/{name}', self.api_plugin)
        
    async def index(self, request):
        """HTML dashboard"""
        html = await self._render_dashboard()
        return web.Response(text=html, content_type='text/html')
        
    async def api_metrics(self, request):
        """JSON metrics endpoint"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'plugins': [
                await self._plugin_summary(name)
                for name in self.collector.plugin_manager.plugins
            ],
            'system': {
                'bot_uptime': time.time() - self.collector.bot_start_time,
                'total_events': sum(p.event_count for p in self.collector.plugin_manager.plugins.values()),
            }
        }
        return web.json_response(metrics)
        
    async def prometheus_metrics(self, request):
        """Prometheus format"""
        # Implementation in Sortie 3
```

**Dashboard HTML** (simple, responsive):
```html
<!DOCTYPE html>
<html>
<head>
    <title>Rosey Metrics</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: sans-serif; margin: 20px; }
        .plugin { border: 1px solid #ccc; margin: 10px; padding: 10px; }
        .healthy { background: #d4edda; }
        .warning { background: #fff3cd; }
        .error { background: #f8d7da; }
        .metric { display: inline-block; margin-right: 20px; }
    </style>
</head>
<body>
    <h1>🤖 Rosey Metrics Dashboard</h1>
    <div id="plugins">
        <!-- Auto-refresh via meta tag every 5s -->
        <div class="plugin healthy">
            <h2>dice-roller v1.0 ✅</h2>
            <span class="metric">Uptime: 2h 34m</span>
            <span class="metric">CPU: 1.2%</span>
            <span class="metric">Memory: 45 MB</span>
            <span class="metric">Events: 1,234</span>
        </div>
    </div>
</body>
</html>
```

### Admin Commands Implementation

**AdminPlugin**:
```python
class AdminPlugin(Plugin):
    """Admin commands for bot management"""
    
    def __init__(self, event_bus: EventBus, config: dict):
        super().__init__(event_bus)
        self.admins = config.get('admins', [])
        self.pending_confirmations = {}
        
    async def on_command(self, event: dict):
        """Handle admin commands"""
        user = event['user']
        message = event['message']
        
        # Permission check
        if user not in self.admins:
            await self.send_message("❌ Admin permission required")
            return
            
        # Parse command
        if message.startswith('!admin reload '):
            plugin_name = message.split()[2]
            await self.handle_reload(user, plugin_name)
        elif message.startswith('!admin status'):
            await self.handle_status(message)
        # ... other commands
        
    async def handle_reload(self, user: str, plugin_name: str):
        """Hot-reload plugin with confirmation"""
        # Request confirmation
        confirmation_id = f"{user}:{plugin_name}:{time.time()}"
        self.pending_confirmations[confirmation_id] = {
            'user': user,
            'plugin': plugin_name,
            'expires': time.time() + 30,
        }
        
        await self.send_message(
            f"🔄 Reload {plugin_name}? Type 'yes' to confirm (30s timeout)"
        )
        
    async def on_confirmation(self, user: str, message: str):
        """Handle confirmation response"""
        if message.lower() == 'yes':
            # Find matching confirmation
            for conf_id, conf in self.pending_confirmations.items():
                if conf['user'] == user and time.time() < conf['expires']:
                    plugin_name = conf['plugin']
                    await self._do_reload(plugin_name)
                    del self.pending_confirmations[conf_id]
                    return
```

---

## Sorties Overview

### Sortie 1: Hot-Reload Foundation (10h)
**Objective**: Implement blue-green deployment for zero-downtime plugin reloads

**Deliverables**:
1. `PluginManager.reload_plugin()` method
2. Health check system (send test command, verify response)
3. Drain and swap logic (wait for in-flight, atomic swap)
4. Version tracking (`_get_version()`)
5. Rollback on health check failure

**Tests**: 3 new tests (hot-reload success, health check failure, version tracking)

**Acceptance**: `!admin reload dice-roller` updates plugin with zero user-visible downtime

### Sortie 2: Metrics Collection (8h)
**Objective**: Collect and aggregate plugin metrics over time

**Deliverables**:
1. `MetricsCollector` class with background poll loop
2. Rolling window history (1 hour, 5s intervals)
3. Aggregate calculations (avg/min/max/p95)
4. Event counting in `PluginProcess`
5. `get_metrics()` method on `PluginProcess`

**Tests**: 3 new tests (collection, aggregation, history retention)

**Acceptance**: Can query metrics for any plugin over the last hour

### Sortie 3: Metrics Dashboard (8h)
**Objective**: HTTP server with dashboard and JSON API

**Deliverables**:
1. `MetricsDashboard` class with aiohttp server
2. HTML dashboard (auto-refresh every 5s)
3. `/api/metrics` JSON endpoint
4. `/api/plugin/{name}` detailed endpoint
5. Prometheus `/metrics` endpoint (standard format)

**Tests**: 2 new tests (HTTP endpoints, Prometheus format)

**Acceptance**: Navigate to `http://localhost:8080`, see all plugin metrics

### Sortie 4: Admin Commands (6h)
**Objective**: Runtime management commands for operators

**Deliverables**:
1. `AdminPlugin` class
2. Commands: `reload`, `status`, `restart`, `list`, `metrics`
3. Permission system (check `config.admins`)
4. Confirmation prompts for destructive operations
5. Audit logging (all admin actions logged)

**Tests**: 2 new tests (permission checks, commands work)

**Acceptance**: Type `!admin reload dice-roller`, plugin reloads without downtime

### Sortie 5: Integration & Documentation (8h)
**Objective**: Wire everything together and document operations

**Deliverables**:
1. Integrate `MetricsCollector` into `rosey.py`
2. Integrate `MetricsDashboard` into `rosey.py`
3. Integrate `AdminPlugin` into plugin loader
4. Operational runbook (`docs/OPERATIONS.md`)
5. Metrics guide (`docs/METRICS.md`)
6. Update `README.md` with dashboard/admin info

**Tests**: 1 new integration test (full reload flow with metrics)

**Acceptance**: Full end-to-end: reload plugin via admin command, see metrics update on dashboard

---

## Dependencies & Risks

### External Dependencies

**New Python Packages**:
- `aiohttp` (HTTP server) - Popular, stable, async-native
- `prometheus-client` (Prometheus exporter) - Official library

**Installation**:
```bash
pip install aiohttp prometheus-client
```

**Risk**: None (both are mature, well-maintained libraries)

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Health check flaky | Reload fails unnecessarily | Multiple attempts, configurable timeout |
| Drain timeout | Old version killed mid-request | Graceful timeout (30s default), configurable |
| Dashboard overload | Too many requests slow bot | Rate limit, cache metrics for 5s |
| Admin command abuse | Malicious reload spam | Confirmation prompts, audit log, cooldown |
| Prometheus bloat | Metrics consume too much memory | 1-hour retention, configurable history size |

### Backward Compatibility

**Breaking Changes**: None

**Migration Path**: Existing deployments continue working. New features are opt-in:
- Dashboard requires config: `dashboard.enabled = true, dashboard.port = 8080`
- Admin commands require config: `admins = ["user1", "user2"]`
- Prometheus endpoint always enabled (can be ignored)

---

## Testing Strategy

### Unit Tests (8 new tests)

**Hot-Reload Tests**:
```python
async def test_reload_plugin_success():
    """Hot-reload updates plugin with zero downtime"""
    # Arrange: Start dice-roller v1.0
    # Act: Reload to v1.1
    # Assert: New version running, old version stopped

async def test_reload_health_check_failure():
    """Rollback if new version fails health check"""
    # Arrange: Start dice-roller v1.0
    # Act: Reload to broken v1.1 (fails health check)
    # Assert: v1.0 still running, v1.1 stopped

async def test_reload_version_tracking():
    """Version correctly tracked after reload"""
    # Arrange: Start dice-roller v1.0
    # Act: Reload to v1.1
    # Assert: plugin.version == "1.1"
```

**Metrics Tests**:
```python
async def test_metrics_collection():
    """MetricsCollector polls and stores metrics"""
    # Arrange: Start collector
    # Act: Wait 10s (2 polls)
    # Assert: History has 2 snapshots

async def test_metrics_aggregation():
    """Aggregates calculated correctly"""
    # Arrange: History with known values
    # Act: Calculate aggregates
    # Assert: avg/min/max/p95 correct

async def test_metrics_retention():
    """Old metrics pruned after 1 hour"""
    # Arrange: History with 2-hour-old data
    # Act: Prune old data
    # Assert: Only last 1 hour retained
```

**Dashboard Tests**:
```python
async def test_dashboard_json_endpoint():
    """GET /api/metrics returns valid JSON"""
    # Arrange: Start dashboard
    # Act: HTTP GET /api/metrics
    # Assert: Valid JSON, has 'plugins' and 'system' keys

async def test_prometheus_format():
    """GET /metrics returns valid Prometheus format"""
    # Arrange: Start dashboard with 2 plugins
    # Act: HTTP GET /metrics
    # Assert: Valid Prometheus format, all metrics present
```

**Admin Command Tests**:
```python
async def test_admin_permission_denied():
    """Non-admin can't run admin commands"""
    # Arrange: User not in config.admins
    # Act: Send !admin reload dice-roller
    # Assert: "Admin permission required"

async def test_admin_reload_command():
    """Admin can reload plugin via command"""
    # Arrange: Admin user, dice-roller v1.0 running
    # Act: !admin reload dice-roller → yes
    # Assert: Plugin reloaded (see logs)
```

### Integration Tests (3 new tests)

**End-to-End Reload**:
```python
async def test_hot_reload_end_to_end():
    """Full hot-reload flow with metrics"""
    # 1. Start bot with dice-roller v1.0
    # 2. Send !roll 2d6 (verify works)
    # 3. Deploy dice-roller v1.1
    # 4. Reload via !admin reload dice-roller
    # 5. Send !roll 2d6 again (verify works)
    # 6. Check metrics (reload event logged)
    # Assert: Zero errors, zero downtime
```

**Dashboard Integration**:
```python
async def test_dashboard_integration():
    """Dashboard shows correct metrics"""
    # 1. Start bot with dashboard
    # 2. Run plugins for 30s (generate load)
    # 3. Fetch /api/metrics
    # Assert: CPU%, memory, event counts present
```

**Admin Command Integration**:
```python
async def test_admin_commands_integration():
    """All admin commands work end-to-end"""
    # 1. Start bot with admin plugin
    # 2. !admin list (verify shows plugins)
    # 3. !admin status dice-roller (verify shows status)
    # 4. !admin restart dice-roller (verify restarts)
    # 5. !admin metrics (verify shows dashboard link)
```

### Coverage Goals

**Target Coverage**:
- Overall: 80% (up from 75% after Sprint 22)
- New modules:
  - `hot_reload.py`: 75%
  - `metrics_collector.py`: 75%
  - `metrics_dashboard.py`: 70% (HTTP routes harder to test)
  - `plugins/admin.py`: 80%

**Coverage Report** (expected post-Sprint 23):
```
Name                                Stmts   Miss  Cover
--------------------------------------------------------
core/plugin_manager.py                150     25    83%
core/plugin_isolation.py              200     40    80%
core/hot_reload.py                     80     20    75%    ← New
monitoring/metrics_collector.py       100     25    75%    ← New
monitoring/metrics_dashboard.py       120     36    70%    ← New
plugins/admin.py                       90     18    80%    ← New
--------------------------------------------------------
TOTAL                                2500    450    82%
```

---

## Performance Targets

### Hot-Reload Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Reload time | <3s | Time from `reload_plugin()` call to new version active |
| Health check timeout | 5s | Time to detect new version is healthy |
| Drain timeout | 30s | Max time to wait for in-flight requests |
| Zero dropped events | 100% | No events lost during reload |

### Dashboard Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Response time | <100ms | Time for `/api/metrics` to return |
| Throughput | 100 req/sec | Dashboard can handle load |
| Memory overhead | <50MB | Dashboard + history storage |
| Poll interval | 5s | How often metrics collected |

### Resource Limits

| Resource | Per Plugin | Bot Total |
|----------|------------|-----------|
| Dashboard memory | N/A | <50MB |
| History storage | <5MB | <50MB (10 plugins) |
| HTTP connections | N/A | 100 concurrent |
| Admin commands | N/A | 10/min (rate limit) |

---

## Rollout Plan

### Phase 1: Development (Sprint 23)
- Implement all 5 sorties
- Run tests continuously (65 total)
- Manual testing on development branch

### Phase 2: Testing (End of Sprint 23)
- Deploy to staging environment
- Test hot-reload under load (50 users)
- Test dashboard with multiple plugins
- Test admin commands (all scenarios)

### Phase 3: Production Rollout (Post-Sprint 23)
**Week 1**: Dashboard only
- Enable metrics collection
- Enable dashboard on port 8080
- Monitor for performance issues
- Do NOT enable admin commands yet

**Week 2**: Admin commands
- Add bot owner to `config.admins`
- Enable admin plugin
- Test reload in production (low-traffic hours)
- Monitor for issues

**Week 3**: Full rollout
- Add additional admins
- Use hot-reload for plugin updates
- Monitor metrics dashboard regularly

### Rollback Plan

If issues arise:
1. **Dashboard issues**: Disable via config (`dashboard.enabled = false`)
2. **Admin command abuse**: Remove from `config.admins`, restart bot
3. **Hot-reload failures**: Use old deployment method (stop bot, update, restart)

---

## Success Metrics

### Operational Metrics (1 month post-deployment)

| Metric | Target | Tracking |
|--------|--------|----------|
| Plugin reloads | >10 successful | Count reload events |
| Reload success rate | >95% | Successful / total reloads |
| Zero-downtime deployments | 100% | No user-visible errors during reload |
| Dashboard uptime | >99% | Dashboard availability |
| Admin command usage | >20/month | Count admin commands executed |

### Developer Experience

| Metric | Before | After |
|--------|--------|-------|
| Deployment time | 5 minutes (stop bot, deploy, restart) | 3 seconds (hot-reload) |
| Deployment window | 3am maintenance window | Anytime (zero downtime) |
| Observability | None (blind operation) | Real-time dashboard |
| Debugging time | 30 minutes (no metrics) | 5 minutes (check dashboard) |

### User Experience

| Metric | Before | After |
|--------|--------|-------|
| Downtime during updates | 5 minutes | 0 seconds |
| Plugin errors visible | No (blind) | Yes (dashboard) |
| Response to "Is bot working?" | "Let me check..." (5 min) | "Yes, see dashboard" (instant) |

---

## Documentation Plan

### New Documentation

**`docs/OPERATIONS.md`** (Operational Runbook):
- How to reload a plugin
- How to read the dashboard
- How to use admin commands
- Troubleshooting guide (reload failures, dashboard issues)
- Rollback procedures

**`docs/METRICS.md`** (Metrics Guide):
- What metrics are collected
- How to interpret metrics
- Prometheus integration guide
- Grafana dashboard setup (optional)
- Alerting recommendations

**`docs/guides/ADMIN_COMMANDS.md`** (Admin Guide):
- Full command reference
- Permission system explained
- Confirmation workflow
- Audit log location
- Security best practices

### Updated Documentation

**`README.md`**:
- Add "Metrics Dashboard" section
- Add link to `http://localhost:8080`
- Add admin commands example

**`docs/ARCHITECTURE.md`**:
- Add hot-reload architecture diagram
- Add metrics collection architecture
- Add admin plugin architecture

**`QUICKSTART.md`**:
- Add dashboard access instructions
- Add admin setup (optional)

---

## Open Questions

### Configuration
**Q**: Should dashboard be enabled by default?
**A**: No. Opt-in via config to avoid unexpected port binding.

**Q**: Default admin users?
**A**: Bot owner only (from `config.owner`). Others must be explicitly added to `config.admins`.

**Q**: Prometheus port configurable?
**A**: Yes. Dashboard port configurable (`dashboard.port`), Prometheus on same port (`/metrics` endpoint).

### Operations
**Q**: Can reload all plugins at once?
**A**: Not in Sprint 23. Too risky. Future enhancement: `!admin reload --all` (sortie in Sprint 24).

**Q**: Automatic rollback if reload fails?
**A**: Yes. If health check fails, old version continues running.

**Q**: Can hot-reload the admin plugin itself?
**A**: No. Admin plugin reloaded via bot restart only (to avoid locking yourself out).

### Performance
**Q**: Impact on bot performance?
**A**: Minimal. Metrics collected every 5s (low overhead). Dashboard is separate HTTP server (no impact on bot).

**Q**: Can dashboard handle Grafana scraping?
**A**: Yes. Prometheus endpoint designed for external scrapers (Grafana, Prometheus, etc).

---

## Future Enhancements (Post-Sprint 23)

### Sprint 24 Ideas
- **Multi-plugin reload**: `!admin reload --all` (reload all plugins)
- **A/B testing**: Run two versions, split traffic 50/50
- **Canary deployments**: Roll out to 10% of users first
- **Historical trends**: 24-hour/7-day metrics (longer retention)
- **Grafana dashboards**: Pre-built Grafana dashboard templates
- **Slack integration**: Post reload notifications to Slack
- **Automatic rollback**: If error rate spikes, auto-rollback

### Observability Enhancements
- **Distributed tracing**: OpenTelemetry integration
- **Log aggregation**: Ship logs to Elasticsearch/Splunk
- **APM integration**: DataDog/New Relic integration
- **Custom metrics**: Plugin authors can define custom metrics

---

## Appendices

### Appendix A: Config Schema

```json
{
  "dashboard": {
    "enabled": true,
    "port": 8080,
    "host": "0.0.0.0"
  },
  "metrics": {
    "poll_interval": 5,
    "history_duration": 3600,
    "prometheus_enabled": true
  },
  "admins": [
    "bot_owner",
    "operator1",
    "operator2"
  ]
}
```

### Appendix B: Prometheus Metrics

**Counters**:
- `rosey_events_total{plugin, type}`: Total events processed
- `rosey_plugin_reloads_total{plugin, status}`: Total reload attempts
- `rosey_admin_commands_total{command, user}`: Total admin commands

**Gauges**:
- `rosey_plugin_cpu_percent{plugin}`: Current CPU usage
- `rosey_plugin_memory_mb{plugin}`: Current memory usage
- `rosey_plugin_uptime_seconds{plugin}`: Time since plugin started
- `rosey_plugin_crash_count{plugin}`: Total crashes

**Histograms**:
- `rosey_plugin_response_time_seconds{plugin}`: Command response time
- `rosey_reload_duration_seconds{plugin}`: Time to complete reload

### Appendix C: Dashboard API

**GET `/api/metrics`**:
```json
{
  "timestamp": "2025-12-01T10:30:00Z",
  "bot_uptime": 86400,
  "plugins": [
    {
      "name": "dice-roller",
      "version": "1.1",
      "state": "running",
      "pid": 12345,
      "uptime": 3600,
      "cpu_percent": 1.2,
      "memory_mb": 45,
      "event_count": 1234,
      "crash_count": 0
    }
  ],
  "system": {
    "total_events": 5000,
    "total_plugins": 3,
    "plugins_running": 3,
    "plugins_crashed": 0
  }
}
```

**GET `/api/plugin/dice-roller`**:
```json
{
  "name": "dice-roller",
  "version": "1.1",
  "loaded_at": "2025-12-01T09:30:00Z",
  "state": "running",
  "pid": 12345,
  "metrics": {
    "current": {
      "cpu_percent": 1.2,
      "memory_mb": 45,
      "uptime": 3600
    },
    "aggregates_1h": {
      "cpu_avg": 1.5,
      "cpu_max": 3.2,
      "memory_avg": 42,
      "memory_max": 48
    }
  },
  "history": [
    {"timestamp": "2025-12-01T10:25:00Z", "cpu": 1.1, "memory": 44},
    {"timestamp": "2025-12-01T10:30:00Z", "cpu": 1.2, "memory": 45}
  ]
}
```

---

**End of PRD**
