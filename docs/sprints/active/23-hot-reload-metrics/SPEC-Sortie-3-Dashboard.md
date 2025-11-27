# SPEC: Sortie 3 - Metrics Dashboard

**Sprint:** 23 - Hot-Reload & Metrics Dashboard  
**Sortie:** 3 of 5  
**Objective:** HTTP server with dashboard and JSON API  
**Estimated Effort:** 8 hours  
**Status:** Planned  

---

## Objective

Create an HTTP server (aiohttp) on port 8080 with an HTML dashboard, JSON API endpoints, and Prometheus `/metrics` endpoint. Provide real-time visibility into plugin health and resource usage.

**Target State**:
- Navigate to `http://localhost:8080` → See HTML dashboard
- GET `/api/metrics` → JSON with all plugin metrics
- GET `/metrics` → Prometheus format for external monitoring
- Dashboard auto-refreshes every 5 seconds
- Response time <100ms for all endpoints

---

## Context

### Current State (Post-Sortie 2)

**What Works** ✅:
- `MetricsCollector` polls metrics every 5s
- 1-hour rolling window history available
- Can query current metrics and aggregates
- Event counting integrated

**What's Missing** ❌:
- No HTTP server (metrics only accessible internally)
- No dashboard UI (operators are blind)
- No Prometheus integration (can't use Grafana)
- No external monitoring capability

### Why Dashboard Matters

**Before Dashboard**:
```
Ops: "Is the bot working?"
Dev: "Let me SSH in and check logs..."
Dev: *10 minutes later* "Yeah, looks fine"
Ops: "Can you check if dice-roller is using too much memory?"
Dev: *5 minutes later* "45MB, seems normal"
Ops: "What about CPU?"
Dev: *sigh*
```

**With Dashboard**:
```
Ops: "Is the bot working?"
Ops: *Opens http://localhost:8080* "Yes, all green"
Ops: "Dice-roller memory?" 
Ops: *Looks at dashboard* "45MB, normal"
Ops: "CPU?"
Ops: *Looks at dashboard* "1.2%, normal"
Total time: 10 seconds
```

---

## Technical Design

### HTTP Server Architecture

```
aiohttp Web Server (port 8080)
├── GET /                      → HTML dashboard
├── GET /api/metrics           → JSON: all plugins
├── GET /api/plugin/{name}     → JSON: single plugin detail
├── GET /metrics               → Prometheus format
└── GET /health                → Simple health check
```

### MetricsDashboard Class

```python
from aiohttp import web
from datetime import datetime, timedelta
from typing import Dict, Optional
import json

class MetricsDashboard:
    """
    HTTP metrics dashboard
    
    Provides:
    - HTML dashboard (auto-refresh)
    - JSON API endpoints
    - Prometheus /metrics endpoint
    """
    
    def __init__(
        self, 
        collector: MetricsCollector,
        host: str = '0.0.0.0',
        port: int = 8080
    ):
        self.collector = collector
        self.host = host
        self.port = port
        
        # aiohttp app
        self.app = web.Application()
        self._setup_routes()
        
        # Server runner
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
    def _setup_routes(self):
        """Configure HTTP routes"""
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/metrics', self.handle_api_metrics)
        self.app.router.add_get('/api/plugin/{name}', self.handle_api_plugin)
        self.app.router.add_get('/metrics', self.handle_prometheus)
        self.app.router.add_get('/health', self.handle_health)
        
    async def start(self):
        """Start HTTP server"""
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        
        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()
        
        logger.info(f"✅ Metrics dashboard: http://{self.host}:{self.port}")
        
    async def stop(self):
        """Stop HTTP server"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Metrics dashboard stopped")
        
    # ========== Route Handlers ==========
    
    async def handle_index(self, request: web.Request) -> web.Response:
        """HTML dashboard (auto-refresh every 5s)"""
        html = await self._render_dashboard()
        return web.Response(text=html, content_type='text/html')
        
    async def handle_api_metrics(self, request: web.Request) -> web.Response:
        """
        JSON API: all plugins
        
        Response:
        {
          "timestamp": "2025-12-01T10:30:00Z",
          "plugins": [...],
          "system": {...}
        }
        """
        current_metrics = self.collector.get_all_current_metrics()
        system_metrics = self.collector.get_system_metrics()
        
        response = {
            'timestamp': datetime.now().isoformat(),
            'plugins': [
                self._format_plugin_summary(snapshot)
                for snapshot in current_metrics.values()
            ],
            'system': system_metrics.to_dict(),
        }
        
        return web.json_response(response)
        
    async def handle_api_plugin(self, request: web.Request) -> web.Response:
        """
        JSON API: single plugin detail
        
        Response:
        {
          "name": "dice-roller",
          "version": "1.0",
          "current": {...},
          "aggregates_1h": {...},
          "history": [...]
        }
        """
        plugin_name = request.match_info['name']
        
        # Get current metrics
        current = self.collector.get_current_metrics(plugin_name)
        if not current:
            return web.json_response(
                {'error': f'Plugin {plugin_name} not found'}, 
                status=404
            )
            
        # Get aggregates
        aggregates = self.collector.get_aggregates(plugin_name)
        
        # Get history (last 1 hour)
        history = self.collector.get_history(plugin_name)
        
        response = {
            'name': plugin_name,
            'version': current.version,
            'loaded_at': current.timestamp.isoformat(),
            'state': current.state,
            'pid': current.pid,
            'current': {
                'cpu_percent': current.cpu_percent,
                'memory_mb': current.memory_mb,
                'uptime_seconds': current.uptime,
                'event_count': current.event_count,
                'crash_count': current.crash_count,
            },
            'aggregates_1h': aggregates.to_dict() if aggregates else None,
            'history': [
                {
                    'timestamp': s.timestamp.isoformat(),
                    'cpu_percent': s.cpu_percent,
                    'memory_mb': s.memory_mb,
                    'event_count': s.event_count,
                }
                for s in history[-60:]  # Last 60 snapshots (5 minutes)
            ],
        }
        
        return web.json_response(response)
        
    async def handle_prometheus(self, request: web.Request) -> web.Response:
        """
        Prometheus /metrics endpoint
        
        Format:
        # HELP rosey_plugin_cpu_percent Plugin CPU usage
        # TYPE rosey_plugin_cpu_percent gauge
        rosey_plugin_cpu_percent{plugin="dice-roller"} 1.2
        """
        lines = []
        
        # Get all current metrics
        current_metrics = self.collector.get_all_current_metrics()
        system_metrics = self.collector.get_system_metrics()
        
        # Plugin metrics
        lines.append('# HELP rosey_plugin_cpu_percent Plugin CPU usage percent')
        lines.append('# TYPE rosey_plugin_cpu_percent gauge')
        for name, snapshot in current_metrics.items():
            lines.append(
                f'rosey_plugin_cpu_percent{{plugin="{name}"}} '
                f'{snapshot.cpu_percent}'
            )
            
        lines.append('')
        lines.append('# HELP rosey_plugin_memory_mb Plugin memory usage MB')
        lines.append('# TYPE rosey_plugin_memory_mb gauge')
        for name, snapshot in current_metrics.items():
            lines.append(
                f'rosey_plugin_memory_mb{{plugin="{name}"}} '
                f'{snapshot.memory_mb}'
            )
            
        lines.append('')
        lines.append('# HELP rosey_plugin_uptime_seconds Plugin uptime seconds')
        lines.append('# TYPE rosey_plugin_uptime_seconds gauge')
        for name, snapshot in current_metrics.items():
            lines.append(
                f'rosey_plugin_uptime_seconds{{plugin="{name}"}} '
                f'{snapshot.uptime}'
            )
            
        lines.append('')
        lines.append('# HELP rosey_plugin_events_total Plugin events processed')
        lines.append('# TYPE rosey_plugin_events_total counter')
        for name, snapshot in current_metrics.items():
            lines.append(
                f'rosey_plugin_events_total{{plugin="{name}"}} '
                f'{snapshot.event_count}'
            )
            
        lines.append('')
        lines.append('# HELP rosey_plugin_crashes_total Plugin crash count')
        lines.append('# TYPE rosey_plugin_crashes_total counter')
        for name, snapshot in current_metrics.items():
            lines.append(
                f'rosey_plugin_crashes_total{{plugin="{name}"}} '
                f'{snapshot.crash_count}'
            )
            
        # System metrics
        lines.append('')
        lines.append('# HELP rosey_bot_uptime_seconds Bot uptime seconds')
        lines.append('# TYPE rosey_bot_uptime_seconds gauge')
        lines.append(f'rosey_bot_uptime_seconds {system_metrics.bot_uptime}')
        
        lines.append('')
        lines.append('# HELP rosey_total_plugins Total plugins loaded')
        lines.append('# TYPE rosey_total_plugins gauge')
        lines.append(f'rosey_total_plugins {system_metrics.total_plugins}')
        
        lines.append('')
        lines.append('# HELP rosey_plugins_running Plugins currently running')
        lines.append('# TYPE rosey_plugins_running gauge')
        lines.append(f'rosey_plugins_running {system_metrics.plugins_running}')
        
        lines.append('')
        
        text = '\n'.join(lines)
        return web.Response(text=text, content_type='text/plain')
        
    async def handle_health(self, request: web.Request) -> web.Response:
        """Simple health check endpoint"""
        return web.json_response({'status': 'ok'})
        
    # ========== HTML Rendering ==========
    
    async def _render_dashboard(self) -> str:
        """Render HTML dashboard"""
        current_metrics = self.collector.get_all_current_metrics()
        system_metrics = self.collector.get_system_metrics()
        
        # Generate plugin cards
        plugin_cards = []
        for name, snapshot in sorted(current_metrics.items()):
            card_html = self._render_plugin_card(name, snapshot)
            plugin_cards.append(card_html)
            
        plugins_html = '\n'.join(plugin_cards)
        
        # System info
        system_html = self._render_system_info(system_metrics)
        
        # Full page
        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>🤖 Rosey Metrics Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 20px;
        }}
        .system-info {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .system-info h2 {{
            margin-top: 0;
            font-size: 18px;
        }}
        .system-stat {{
            display: inline-block;
            margin-right: 30px;
            margin-bottom: 10px;
        }}
        .plugins {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 15px;
        }}
        .plugin {{
            background: white;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .plugin.healthy {{
            border-left: 4px solid #28a745;
        }}
        .plugin.warning {{
            border-left: 4px solid #ffc107;
        }}
        .plugin.error {{
            border-left: 4px solid #dc3545;
        }}
        .plugin h2 {{
            margin: 0 0 10px 0;
            font-size: 18px;
            color: #333;
        }}
        .plugin .version {{
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }}
        .metric {{
            display: inline-block;
            margin-right: 15px;
            margin-bottom: 8px;
        }}
        .metric-label {{
            color: #666;
            font-size: 12px;
            display: block;
        }}
        .metric-value {{
            font-size: 18px;
            font-weight: bold;
            color: #333;
        }}
        .status {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .status.running {{
            background: #d4edda;
            color: #155724;
        }}
        .status.crashed {{
            background: #f8d7da;
            color: #721c24;
        }}
    </style>
</head>
<body>
    <h1>🤖 Rosey Metrics Dashboard</h1>
    <div class="subtitle">Auto-refresh every 5 seconds</div>
    
    {system_html}
    
    <div class="plugins">
        {plugins_html}
    </div>
</body>
</html>'''
        
        return html
        
    def _render_system_info(self, system: SystemMetrics) -> str:
        """Render system info section"""
        return f'''
<div class="system-info">
    <h2>System Overview</h2>
    <div class="system-stat">
        <span class="metric-label">Uptime</span>
        <span class="metric-value">{system.to_dict()['bot_uptime_human']}</span>
    </div>
    <div class="system-stat">
        <span class="metric-label">Plugins</span>
        <span class="metric-value">{system.plugins_running}/{system.total_plugins}</span>
    </div>
    <div class="system-stat">
        <span class="metric-label">Total Events</span>
        <span class="metric-value">{system.total_events:,}</span>
    </div>
    <div class="system-stat">
        <span class="metric-label">Total Memory</span>
        <span class="metric-value">{system.total_memory_mb:.1f} MB</span>
    </div>
</div>
'''
        
    def _render_plugin_card(self, name: str, snapshot: MetricSnapshot) -> str:
        """Render single plugin card"""
        # Determine status class
        if snapshot.state == 'RUNNING':
            if snapshot.cpu_percent > 50 or snapshot.memory_mb > 100:
                status_class = 'warning'
                status_badge = '<span class="status running">⚠️ RUNNING</span>'
            else:
                status_class = 'healthy'
                status_badge = '<span class="status running">✅ RUNNING</span>'
        else:
            status_class = 'error'
            status_badge = '<span class="status crashed">❌ CRASHED</span>'
            
        # Format uptime
        uptime_human = self._format_uptime(snapshot.uptime)
        
        return f'''
<div class="plugin {status_class}">
    <h2>{name} {status_badge}</h2>
    <div class="version">v{snapshot.version} | PID {snapshot.pid or "N/A"}</div>
    
    <div class="metric">
        <span class="metric-label">Uptime</span>
        <span class="metric-value">{uptime_human}</span>
    </div>
    
    <div class="metric">
        <span class="metric-label">CPU</span>
        <span class="metric-value">{snapshot.cpu_percent:.1f}%</span>
    </div>
    
    <div class="metric">
        <span class="metric-label">Memory</span>
        <span class="metric-value">{snapshot.memory_mb:.1f} MB</span>
    </div>
    
    <div class="metric">
        <span class="metric-label">Events</span>
        <span class="metric-value">{snapshot.event_count:,}</span>
    </div>
    
    <div class="metric">
        <span class="metric-label">Crashes</span>
        <span class="metric-value">{snapshot.crash_count}</span>
    </div>
</div>
'''
        
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
            
    def _format_plugin_summary(self, snapshot: MetricSnapshot) -> dict:
        """Format plugin snapshot for JSON API"""
        return {
            'name': snapshot.plugin_name,
            'version': snapshot.version,
            'pid': snapshot.pid,
            'state': snapshot.state,
            'uptime_seconds': snapshot.uptime,
            'cpu_percent': snapshot.cpu_percent,
            'memory_mb': snapshot.memory_mb,
            'event_count': snapshot.event_count,
            'crash_count': snapshot.crash_count,
        }
```

---

## Implementation Plan

### Phase 1: HTTP Server Setup (2h)

1. Add aiohttp dependency
2. Create `MetricsDashboard` class
3. Implement `start()` and `stop()` lifecycle
4. Implement `_setup_routes()`
5. Test server starts on port 8080

### Phase 2: JSON API Endpoints (2h)

1. Implement `/api/metrics` (all plugins)
2. Implement `/api/plugin/{name}` (single plugin)
3. Implement `/health` (simple check)
4. Test endpoints return valid JSON
5. Test 404 handling for unknown plugins

### Phase 3: HTML Dashboard (2h)

1. Implement `_render_dashboard()` template
2. Implement `_render_system_info()` section
3. Implement `_render_plugin_card()` component
4. Add CSS styling (responsive, clean)
5. Test dashboard renders correctly

### Phase 4: Prometheus Endpoint (1h)

1. Implement `/metrics` handler
2. Format metrics in Prometheus exposition format
3. Add all gauge/counter metrics
4. Test Prometheus can scrape endpoint

### Phase 5: Integration & Testing (1h)

1. Wire into `rosey.py` startup
2. Add config options (host, port)
3. Test dashboard with multiple plugins
4. Test dashboard during plugin reload

---

## Testing Strategy

### Unit Tests (2 new tests)

**Test 1: HTTP Endpoints**
```python
async def test_dashboard_endpoints():
    """All HTTP endpoints return valid responses"""
    # Arrange: Start dashboard
    manager = PluginManager(event_bus, plugin_dir)
    await manager.load_plugin('dice-roller')
    
    collector = MetricsCollector(manager)
    await collector.start()
    
    dashboard = MetricsDashboard(collector, port=8888)
    await dashboard.start()
    
    # Act & Assert: Test each endpoint
    async with aiohttp.ClientSession() as session:
        # GET /
        async with session.get('http://localhost:8888/') as resp:
            assert resp.status == 200
            assert 'text/html' in resp.content_type
            html = await resp.text()
            assert 'Rosey Metrics Dashboard' in html
            
        # GET /api/metrics
        async with session.get('http://localhost:8888/api/metrics') as resp:
            assert resp.status == 200
            data = await resp.json()
            assert 'plugins' in data
            assert 'system' in data
            assert len(data['plugins']) >= 1
            
        # GET /api/plugin/dice-roller
        async with session.get('http://localhost:8888/api/plugin/dice-roller') as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data['name'] == 'dice-roller'
            assert 'current' in data
            assert 'aggregates_1h' in data
            
        # GET /health
        async with session.get('http://localhost:8888/health') as resp:
            assert resp.status == 200
            data = await resp.json()
            assert data['status'] == 'ok'
            
    await dashboard.stop()
    await collector.stop()
```

**Test 2: Prometheus Format**
```python
async def test_prometheus_format():
    """Prometheus endpoint returns valid format"""
    # Arrange: Start dashboard with 2 plugins
    manager = PluginManager(event_bus, plugin_dir)
    await manager.load_plugin('dice-roller')
    await manager.load_plugin('8ball')
    
    collector = MetricsCollector(manager)
    await collector.start()
    await asyncio.sleep(1)  # Let collector poll once
    
    dashboard = MetricsDashboard(collector, port=8889)
    await dashboard.start()
    
    # Act: Fetch /metrics
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8889/metrics') as resp:
            assert resp.status == 200
            assert 'text/plain' in resp.content_type
            text = await resp.text()
            
    # Assert: Valid Prometheus format
    assert '# HELP rosey_plugin_cpu_percent' in text
    assert '# TYPE rosey_plugin_cpu_percent gauge' in text
    assert 'rosey_plugin_cpu_percent{plugin="dice-roller"}' in text
    assert 'rosey_plugin_cpu_percent{plugin="8ball"}' in text
    assert 'rosey_plugin_memory_mb{plugin="dice-roller"}' in text
    assert 'rosey_bot_uptime_seconds' in text
    
    await dashboard.stop()
    await collector.stop()
```

### Manual Testing

**Dashboard UI Test**:
```
1. Start bot: ./run_bot.sh
2. Open browser: http://localhost:8080
3. Verify:
   - System overview shows uptime, plugin count
   - Each plugin has a card (dice-roller, 8ball, etc.)
   - Plugin cards show: version, PID, uptime, CPU%, memory, events
   - Status badges: green=healthy, yellow=warning, red=error
   - Page auto-refreshes every 5 seconds
4. Generate load:
   - Send 100 !roll commands
   - Watch event count increment on dashboard
5. Crash a plugin:
   - Kill dice-roller subprocess
   - Watch card turn red
   - Watch crash count increment
```

---

## Quality Gates

**Must Pass Before Merge**:
- [ ] All 2 new tests passing
- [ ] Dashboard loads in browser
- [ ] All endpoints return valid data
- [ ] Prometheus endpoint validated (curl or Prometheus scraper)
- [ ] Dashboard auto-refresh works
- [ ] Response time <100ms (measured via curl)
- [ ] Code coverage >70% for new code

**Manual Validation**:
- [ ] Dashboard looks good in Chrome/Firefox
- [ ] Dashboard is mobile-responsive
- [ ] Colors/status indicators are clear
- [ ] No console errors in browser

---

## Integration

### Wire into rosey.py

```python
class Rosey:
    async def start(self):
        # ... existing startup ...
        
        # Start metrics collector
        self.metrics_collector = MetricsCollector(self.plugin_manager)
        await self.metrics_collector.start()
        
        # Start metrics dashboard (NEW)
        if self.config.dashboard.enabled:
            self.metrics_dashboard = MetricsDashboard(
                self.metrics_collector,
                host=self.config.dashboard.host,
                port=self.config.dashboard.port,
            )
            await self.metrics_dashboard.start()
            logger.info(
                f"✅ Dashboard: http://{self.config.dashboard.host}:"
                f"{self.config.dashboard.port}"
            )
```

### Config Schema

```json
{
  "dashboard": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8080
  }
}
```

---

## Dependencies

**New Package**:
```bash
pip install aiohttp
```

Add to `requirements.txt`:
```
aiohttp==3.9.1
```

---

## Follow-Up Work

**Sortie 4**: Add admin commands to trigger actions from CyTube chat  
**Sprint 24**: Grafana dashboard templates, historical charts (24h)  

---

**End of Sortie 3 Spec**
