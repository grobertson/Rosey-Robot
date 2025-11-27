# SPEC: Sortie 5 - Integration & Documentation

**Sprint:** 23 - Hot-Reload & Metrics Dashboard  
**Sortie:** 5 of 5  
**Objective:** Wire everything together and document operations  
**Estimated Effort:** 8 hours  
**Status:** Planned  

---

## Objective

Integrate all Sprint 23 features into `rosey.py`, create comprehensive operational documentation, and validate the complete hot-reload + metrics system works end-to-end in production scenarios.

**Target State**:
- All Sprint 23 features integrated and working together
- Operational runbook documenting all procedures
- Metrics guide explaining all metrics
- Admin guide for using admin commands
- End-to-end validation complete

---

## Context

### Sprint 23 Deliverables (Sorties 1-4)

**Sortie 1: Hot-Reload** ✅
- Blue-green deployment
- Health checks
- Version tracking
- Rollback on failure

**Sortie 2: Metrics Collection** ✅
- Background polling every 5s
- 1-hour rolling window
- Aggregate calculations
- Event counting

**Sortie 3: Metrics Dashboard** ✅
- HTTP server on port 8080
- HTML dashboard
- JSON API endpoints
- Prometheus `/metrics` endpoint

**Sortie 4: Admin Commands** ✅
- `!admin reload`, `!admin restart`, `!admin status`, etc.
- Permission system
- Confirmation prompts
- Audit logging

### Integration Goals

**Wire Together**:
1. `rosey.py` starts all components in correct order
2. Components communicate via EventBus
3. Admin commands trigger hot-reload
4. Hot-reload updates shown on dashboard
5. Metrics track reload events

**Document**:
1. How to use admin commands
2. How to read dashboard
3. How to troubleshoot issues
4. How to integrate with Prometheus/Grafana

---

## Technical Design

### rosey.py Integration

**Updated Startup Sequence**:
```python
class Rosey:
    """
    Rosey Bot - Main orchestrator
    
    Startup sequence:
    1. EventBus (NATS)
    2. DatabaseService
    3. PluginManager
    4. MetricsCollector (NEW - Sprint 23)
    5. MetricsDashboard (NEW - Sprint 23)
    6. AdminPlugin (NEW - Sprint 23)
    7. Router
    8. CytubeConnector
    """
    
    def __init__(self, config: Config):
        self.config = config
        
        # Core components
        self.event_bus: Optional[EventBus] = None
        self.database: Optional[DatabaseService] = None
        self.plugin_manager: Optional[PluginManager] = None
        self.router: Optional[Router] = None
        self.cytube: Optional[CytubeConnector] = None
        
        # Monitoring components (NEW - Sprint 23)
        self.metrics_collector: Optional[MetricsCollector] = None
        self.metrics_dashboard: Optional[MetricsDashboard] = None
        self.admin_plugin: Optional[AdminPlugin] = None
        
    async def start(self):
        """Start bot and all components"""
        logger.info("Starting Rosey Bot v1.0...")
        
        try:
            # 1. Event Bus (NATS)
            logger.info("Connecting to NATS...")
            self.event_bus = EventBus(self.config.nats_url)
            await self.event_bus.connect()
            logger.info("✅ EventBus connected")
            
            # 2. Database Service
            logger.info("Starting database service...")
            self.database = DatabaseService(
                self.event_bus,
                self.config.database
            )
            await self.database.start()
            logger.info("✅ Database service started")
            
            # 3. Plugin Manager
            logger.info("Starting plugin manager...")
            plugin_dir = self.config.plugin_dir or 'plugins'
            self.plugin_manager = PluginManager(
                self.event_bus,
                plugin_dir
            )
            await self.plugin_manager.start()
            logger.info("✅ Plugin manager started")
            
            # 4. Metrics Collector (NEW)
            if self.config.metrics.enabled:
                logger.info("Starting metrics collector...")
                self.metrics_collector = MetricsCollector(
                    self.plugin_manager,
                    poll_interval=self.config.metrics.poll_interval,
                    history_duration=timedelta(
                        seconds=self.config.metrics.history_duration
                    )
                )
                await self.metrics_collector.start()
                logger.info("✅ Metrics collector started")
            
            # 5. Metrics Dashboard (NEW)
            if self.config.dashboard.enabled and self.metrics_collector:
                logger.info("Starting metrics dashboard...")
                self.metrics_dashboard = MetricsDashboard(
                    self.metrics_collector,
                    host=self.config.dashboard.host,
                    port=self.config.dashboard.port
                )
                await self.metrics_dashboard.start()
                logger.info(
                    f"✅ Dashboard: http://{self.config.dashboard.host}:"
                    f"{self.config.dashboard.port}"
                )
            
            # 6. Admin Plugin (NEW)
            if self.config.admins:
                logger.info("Starting admin plugin...")
                self.admin_plugin = AdminPlugin(
                    self.event_bus,
                    self.config,
                    self  # Pass Rosey instance for access to components
                )
                await self.admin_plugin.start()
                logger.info("✅ Admin plugin started")
            
            # 7. Router
            logger.info("Starting router...")
            self.router = Router(
                self.event_bus,
                self.plugin_manager
            )
            await self.router.start()
            logger.info("✅ Router started")
            
            # 8. CyTube Connector
            logger.info("Connecting to CyTube...")
            self.cytube = CytubeConnector(
                self.event_bus,
                self.config.cytube
            )
            await self.cytube.connect()
            logger.info(f"✅ Connected to: {self.config.cytube.channel}")
            
            logger.info("🎉 Rosey v1.0 started successfully!")
            
        except Exception as e:
            logger.error(f"Failed to start Rosey: {e}", exc_info=True)
            await self.stop()
            raise
            
    async def stop(self):
        """Stop bot and all components (reverse order)"""
        logger.info("Stopping Rosey Bot...")
        
        # Stop in reverse order
        if self.cytube:
            await self.cytube.disconnect()
            
        if self.router:
            await self.router.stop()
            
        if self.admin_plugin:
            # Admin plugin doesn't have stop() yet, just cleanup
            pass
            
        if self.metrics_dashboard:
            await self.metrics_dashboard.stop()
            
        if self.metrics_collector:
            await self.metrics_collector.stop()
            
        if self.plugin_manager:
            await self.plugin_manager.stop_all()
            
        if self.database:
            await self.database.stop()
            
        if self.event_bus:
            await self.event_bus.disconnect()
            
        logger.info("✅ Rosey v1.0 stopped")
```

### Config Schema Updates

**Complete config.json**:
```json
{
  "owner": "bot_owner_username",
  "admins": [
    "operator1",
    "operator2"
  ],
  
  "nats_url": "nats://localhost:4222",
  
  "database": {
    "url": "postgresql://user:pass@localhost/rosey",
    "pool_size": 10
  },
  
  "cytube": {
    "server": "https://cytu.be",
    "channel": "your-channel",
    "username": "Rosey",
    "password": "your-password"
  },
  
  "plugin_dir": "plugins",
  
  "metrics": {
    "enabled": true,
    "poll_interval": 5,
    "history_duration": 3600
  },
  
  "dashboard": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8080
  }
}
```

---

## Documentation Plan

### 1. Operational Runbook (`docs/OPERATIONS.md`)

**Content**:
```markdown
# Rosey Bot Operations Guide

## Quick Start

### Starting the Bot
```bash
./run_bot.sh
```

### Accessing the Dashboard
Navigate to: http://localhost:8080

### Admin Commands
See "Admin Commands" section below

---

## Dashboard

### Overview
The dashboard shows real-time metrics for all plugins:
- **CPU Usage**: Percentage of CPU used by plugin
- **Memory**: Memory usage in MB
- **Uptime**: How long plugin has been running
- **Events**: Number of events processed
- **Crashes**: Number of times plugin crashed

### Status Indicators
- 🟢 **Green**: Healthy (normal CPU/memory)
- 🟡 **Yellow**: Warning (high CPU or memory)
- 🔴 **Red**: Error (crashed or not responding)

### Auto-Refresh
Dashboard auto-refreshes every 5 seconds. Manually refresh: F5

---

## Hot-Reload

### What is Hot-Reload?
Hot-reload updates a plugin without stopping the bot or interrupting users.

### When to Use
- Deploying bug fixes
- Updating plugin features
- Testing new plugin versions

### How to Hot-Reload

**Via Admin Command** (recommended):
```
!admin reload <plugin>
yes
```

**Via Python**:
```python
from rosey import bot
await bot.plugin_manager.reload_plugin('dice-roller')
```

### Reload Process
1. New version starts in staging
2. Health check (5s timeout)
3. If healthy: swap versions (atomic)
4. Old version drains (30s timeout)
5. Old version stops

### If Reload Fails
- Old version continues running (no downtime)
- Error message shows failure reason
- Check logs: `tail -f logs/rosey.log`

---

## Admin Commands

### Available Commands

**!admin help**
- Shows command help

**!admin list**
- Lists all loaded plugins with versions

**!admin status [plugin]**
- Shows plugin status (or all plugins if no name)

**!admin reload <plugin>**
- Hot-reload plugin (zero downtime)
- Requires confirmation

**!admin restart <plugin>**
- Cold restart plugin (brief downtime)
- Requires confirmation

**!admin metrics**
- Shows dashboard link

### Permission System
Only users in `config.admins` or `config.owner` can run admin commands.

### Confirmation Flow
Destructive commands require confirmation:
```
User: !admin reload dice-roller
Bot: Reload dice-roller v1.0 → v1.1? Type yes to confirm (30s timeout)
User: yes
Bot: ✅ Reloaded dice-roller v1.0 → v1.1 (3.2s)
```

### Rate Limiting
5-second cooldown between commands per user.

---

## Troubleshooting

### Bot Won't Start

**Check NATS server**:
```bash
nc -z localhost 4222
```
If fails: Start NATS server

**Check database**:
```bash
psql -h localhost -U user -d rosey
```
If fails: Start PostgreSQL

**Check logs**:
```bash
tail -f logs/rosey.log
```

### Plugin Crashed

**Check dashboard**:
- Plugin card will be red
- Crash count incremented

**Check logs**:
```bash
grep "dice-roller" logs/rosey.log | tail -20
```

**Restart plugin**:
```
!admin restart dice-roller
```

### Reload Failed

**Common Causes**:
1. Health check timeout (plugin not responding)
2. Syntax error in new version
3. Resource limits exceeded

**Check reload error**:
Bot will show error message, e.g.:
```
❌ Reload failed: Health check failed
```

**Rollback**:
Reload automatically rolls back to old version. No manual action needed.

**Fix and Retry**:
1. Fix code issue
2. Retry reload: `!admin reload <plugin>`

### Dashboard Not Loading

**Check dashboard is enabled**:
```json
{
  "dashboard": {
    "enabled": true
  }
}
```

**Check port not in use**:
```bash
lsof -i :8080
```

**Check firewall**:
```bash
sudo ufw allow 8080
```

---

## Monitoring

### Prometheus Integration
Prometheus endpoint: `http://localhost:8080/metrics`

**Example scrape_config**:
```yaml
scrape_configs:
  - job_name: 'rosey'
    static_configs:
      - targets: ['localhost:8080']
```

### Grafana Dashboard
(See docs/METRICS.md for Grafana dashboard JSON)

### Alerts
Recommended alerts:
- Plugin CPU > 80% for 5 minutes
- Plugin memory > 200MB
- Plugin crashed (crash_count incremented)
- Bot uptime < 60s (frequent restarts)
```

### 2. Metrics Guide (`docs/METRICS.md`)

**Content**:
```markdown
# Rosey Bot Metrics Guide

## Collected Metrics

### Plugin Metrics
Collected every 5 seconds for each plugin:

| Metric | Type | Description |
|--------|------|-------------|
| `cpu_percent` | Gauge | CPU usage (0-100%) |
| `memory_mb` | Gauge | Memory usage in MB |
| `uptime` | Gauge | Seconds since plugin started |
| `event_count` | Counter | Total events processed |
| `crash_count` | Counter | Total crashes |

### System Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `bot_uptime` | Gauge | Seconds since bot started |
| `total_plugins` | Gauge | Number of loaded plugins |
| `plugins_running` | Gauge | Number of running plugins |
| `plugins_crashed` | Gauge | Number of crashed plugins |
| `total_events` | Counter | Total events across all plugins |

## Prometheus Metrics

### Endpoint
`GET http://localhost:8080/metrics`

### Format
Standard Prometheus exposition format:
```
# HELP rosey_plugin_cpu_percent Plugin CPU usage percent
# TYPE rosey_plugin_cpu_percent gauge
rosey_plugin_cpu_percent{plugin="dice-roller"} 1.2

# HELP rosey_plugin_memory_mb Plugin memory usage MB
# TYPE rosey_plugin_memory_mb gauge
rosey_plugin_memory_mb{plugin="dice-roller"} 45.3
```

### Available Metrics

**Gauges**:
- `rosey_plugin_cpu_percent{plugin}`
- `rosey_plugin_memory_mb{plugin}`
- `rosey_plugin_uptime_seconds{plugin}`
- `rosey_bot_uptime_seconds`
- `rosey_total_plugins`
- `rosey_plugins_running`

**Counters**:
- `rosey_plugin_events_total{plugin}`
- `rosey_plugin_crashes_total{plugin}`

## JSON API

### GET /api/metrics
Returns all current metrics:
```json
{
  "timestamp": "2025-12-01T10:30:00Z",
  "plugins": [
    {
      "name": "dice-roller",
      "version": "1.0",
      "pid": 12345,
      "state": "RUNNING",
      "uptime_seconds": 3600,
      "cpu_percent": 1.2,
      "memory_mb": 45.3,
      "event_count": 1234,
      "crash_count": 0
    }
  ],
  "system": {
    "bot_uptime_seconds": 86400,
    "bot_uptime_human": "1d 0h",
    "total_plugins": 3,
    "plugins_running": 3,
    "plugins_crashed": 0,
    "total_events": 5000
  }
}
```

### GET /api/plugin/{name}
Returns detailed metrics for one plugin including history.

## Grafana Dashboard

### Import Dashboard
1. Open Grafana
2. Import dashboard from JSON
3. Use `docs/grafana-dashboard.json`

### Panels
- **Bot Uptime**: Gauge showing bot uptime
- **Plugin States**: Pie chart (running/crashed)
- **CPU Usage**: Time series per plugin
- **Memory Usage**: Time series per plugin
- **Event Rate**: Graph of events/sec
- **Crash Timeline**: Annotation showing crash events
```

### 3. Admin Guide (`docs/guides/ADMIN_COMMANDS.md`)

**Content**: (Detailed command reference, examples, security best practices)

### 4. Update README.md

**Add sections**:
- Metrics Dashboard
- Hot-Reload
- Admin Commands
- Monitoring Integration

---

## Implementation Plan

### Phase 1: rosey.py Integration (2h)

1. Update `Rosey.__init__()` with new components
2. Update `Rosey.start()` with startup sequence
3. Update `Rosey.stop()` with shutdown sequence
4. Add config validation
5. Test complete startup/shutdown

### Phase 2: Config Schema (1h)

1. Update `common/config.py` with new fields
2. Add validation for dashboard/metrics config
3. Create example config files (dev, prod)
4. Update setup script to generate config

### Phase 3: Documentation Writing (4h)

1. Write `docs/OPERATIONS.md` (2h)
2. Write `docs/METRICS.md` (1h)
3. Write `docs/guides/ADMIN_COMMANDS.md` (30min)
4. Update `README.md` (30min)

### Phase 4: End-to-End Validation (1h)

1. Start bot with all features enabled
2. Test hot-reload via admin command
3. Verify metrics update on dashboard
4. Test Prometheus scraping
5. Test all admin commands
6. Generate load, watch metrics

---

## Testing Strategy

### Integration Test

**Test: Complete Hot-Reload Flow with Metrics**
```python
async def test_hot_reload_with_metrics():
    """End-to-end: reload plugin, verify metrics updated"""
    # 1. Start bot (all components)
    config = load_test_config()
    config.dashboard.enabled = True
    config.metrics.enabled = True
    bot = Rosey(config)
    await bot.start()
    
    # Wait for startup
    await asyncio.sleep(2)
    
    # 2. Verify dashboard accessible
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8080/') as resp:
            assert resp.status == 200
            
    # 3. Send command (verify bot works)
    await bot.event_bus.publish('cytube.chat.message', {
        'user': 'test_user',
        'message': '!roll 2d6',
        'channel': 'test',
    })
    
    await asyncio.sleep(0.5)
    
    # 4. Check event count incremented
    plugin = bot.plugin_manager.plugins['dice-roller']
    assert plugin.event_count >= 1
    
    # 5. Update plugin code (v1.0 → v1.1)
    _update_plugin_version('dice-roller', '1.1')
    
    # 6. Reload via admin command
    await bot.event_bus.publish('rosey.command.admin.reload', {
        'user': 'admin_user',
        'message': '!admin reload dice-roller',
        'channel': 'test',
    })
    
    await asyncio.sleep(0.1)
    
    # 7. Confirm reload
    await bot.event_bus.publish('rosey.command.admin.reload', {
        'user': 'admin_user',
        'message': 'yes',
        'channel': 'test',
    })
    
    # Wait for reload
    await asyncio.sleep(5)
    
    # 8. Verify new version running
    plugin = bot.plugin_manager.plugins['dice-roller']
    assert plugin.version == '1.1'
    
    # 9. Verify dashboard shows new version
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8080/api/metrics') as resp:
            data = await resp.json()
            dice_plugin = next(
                p for p in data['plugins'] 
                if p['name'] == 'dice-roller'
            )
            assert dice_plugin['version'] == '1.1'
            
    # 10. Send command again (verify still works)
    await bot.event_bus.publish('cytube.chat.message', {
        'user': 'test_user',
        'message': '!roll 3d8',
        'channel': 'test',
    })
    
    await asyncio.sleep(0.5)
    
    # 11. Verify event count incremented again
    assert plugin.event_count >= 2
    
    # Cleanup
    await bot.stop()
```

### Manual Validation Checklist

**Startup**:
- [ ] Bot starts without errors
- [ ] All components start in correct order
- [ ] Dashboard accessible at http://localhost:8080
- [ ] Dashboard shows all plugins
- [ ] Prometheus endpoint returns metrics

**Hot-Reload**:
- [ ] `!admin reload dice-roller` prompts for confirmation
- [ ] Confirmation `yes` triggers reload
- [ ] Reload completes in <5s
- [ ] Dashboard shows new version
- [ ] No user errors during reload

**Metrics**:
- [ ] Dashboard auto-refreshes every 5s
- [ ] CPU/memory metrics update
- [ ] Event counts increment
- [ ] System uptime shown correctly

**Admin Commands**:
- [ ] All commands work (`list`, `status`, `reload`, `restart`, `metrics`, `help`)
- [ ] Non-admin user denied
- [ ] Confirmation prompts show
- [ ] Audit log populated

**Prometheus**:
- [ ] `/metrics` endpoint accessible
- [ ] Valid Prometheus format
- [ ] Prometheus can scrape successfully
- [ ] Grafana can display metrics

---

## Quality Gates

**Must Pass Before Sprint 23 Complete**:
- [ ] Integration test passes
- [ ] All manual validation items checked
- [ ] Documentation complete (operations, metrics, admin guide)
- [ ] README updated
- [ ] Example configs provided
- [ ] Zero errors in logs during normal operation
- [ ] Dashboard loads in <1s
- [ ] Prometheus scrape successful

**Performance**:
- [ ] Bot starts in <5s
- [ ] Dashboard responds in <100ms
- [ ] Hot-reload completes in <3s
- [ ] Metrics collection <1% CPU overhead

**Documentation**:
- [ ] Operations guide complete
- [ ] Metrics guide complete
- [ ] Admin commands guide complete
- [ ] All examples tested
- [ ] Troubleshooting section complete

---

## Rollout Plan

### Phase 1: Internal Testing (Day 1)
- Deploy to development environment
- Run integration tests
- Manual validation of all features
- Fix any issues

### Phase 2: Staging Deployment (Day 2-3)
- Deploy to staging with real CyTube connection
- Monitor for 24 hours
- Test hot-reload under load
- Verify dashboard with real traffic

### Phase 3: Production Rollout (Day 4-5)
- Deploy to production during low-traffic hours
- Enable metrics collection only (dashboard disabled)
- Monitor for issues
- Enable dashboard after 24h stable
- Enable admin commands after 48h stable

### Phase 4: Documentation Release (Day 6)
- Publish operations guide
- Train operators on admin commands
- Create runbook for common issues
- Set up Grafana dashboards

---

## Success Metrics

### Operational Efficiency (1 month post-deployment)

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Plugin deployment time | 5 min | 3 sec | <5 sec |
| Deployment downtime | 5 min | 0 sec | 0 sec |
| Time to debug issues | 30 min | 5 min | <10 min |
| Admin SSH sessions | 50/month | 5/month | <10/month |
| Successful reloads | N/A | 95% | >90% |

### Developer Experience

| Metric | Before | After |
|--------|--------|-------|
| Can see plugin CPU usage? | No | Yes (dashboard) |
| Can see memory usage? | No | Yes (dashboard) |
| Can see event counts? | No | Yes (dashboard) |
| Can reload without SSH? | No | Yes (admin command) |
| Can check status remotely? | No | Yes (admin command + dashboard) |

### User Experience

| Metric | Before | After |
|--------|--------|-------|
| Downtime during updates | 5 min | 0 sec |
| Visible errors during reload | Yes | No |
| Bot responsiveness | Unknown | Visible (dashboard) |

---

## Appendices

### A. Example Config Files

**`config-dev.json`** (development):
```json
{
  "owner": "dev_user",
  "admins": ["dev_user"],
  "nats_url": "nats://localhost:4222",
  "database": {
    "url": "postgresql://localhost/rosey_dev"
  },
  "cytube": {
    "server": "https://cytu.be",
    "channel": "test-channel",
    "username": "RoseyDev",
    "password": "dev_password"
  },
  "metrics": {
    "enabled": true,
    "poll_interval": 5,
    "history_duration": 3600
  },
  "dashboard": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 8080
  }
}
```

**`config-prod.json`** (production):
```json
{
  "owner": "bot_owner",
  "admins": ["operator1", "operator2"],
  "nats_url": "nats://localhost:4222",
  "database": {
    "url": "postgresql://user:pass@localhost/rosey",
    "pool_size": 20
  },
  "cytube": {
    "server": "https://cytu.be",
    "channel": "production-channel",
    "username": "Rosey",
    "password": "secure_password"
  },
  "metrics": {
    "enabled": true,
    "poll_interval": 5,
    "history_duration": 3600
  },
  "dashboard": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8080
  }
}
```

### B. Grafana Dashboard JSON

(Complete Grafana dashboard configuration - see separate file)

---

**End of Sortie 5 Spec**
**End of Sprint 23**
