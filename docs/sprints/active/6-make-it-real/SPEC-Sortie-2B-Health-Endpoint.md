# Critical Dependency: Implement /api/health Endpoint

**Status**: Planning  
**Owner**: Agent  
**Estimated Effort**: 3-4 hours  
**Related Issue**: #16  
**Depends On**: None (can start immediately)  
**Required For**: Sorties 4-5 (deployments), Sortie 6 (monitoring)

## Overview

Implement a `/api/health` HTTP endpoint that provides real-time bot status information. This is **critical** for:

- Deployment validation (is the bot actually running?)
- Prometheus scraping (metrics collection)
- Load balancer health checks (future)
- Debugging (quick status snapshot)

Without this, we have no way to programmatically check if deployments succeeded.

## Current State

**No health endpoint exists.**

- `web/status_server.py` exists but isn't integrated with the bot
- Sprint 5 dashboard (`web/dashboard.py`) provides HTML but no JSON API
- No way to check bot status without SSH + logs
- Monitoring can't scrape metrics

## Target State

RESTful JSON endpoint at `/api/health` returning:

```json
{
  "status": "healthy",
  "connected": true,
  "channel": "#programming",
  "uptime_seconds": 3600,
  "version": "nano-sprint-6",
  "user_count": 42,
  "requests_handled": 1523,
  "error_count": 3
}
```

**Ports:**

- Test server: `http://TEST_IP:8001/api/health`
- Production server: `http://PROD_IP:8000/api/health`

## Technical Design

### Architecture

```
lib/bot.py (CyTubeBot)
    ↓
    Creates & starts
    ↓
lib/health_server.py (HealthServer)
    ↓
    Flask app on separate thread
    ↓
    Reads bot.get_health_status()
    ↓
    Returns JSON at /api/health
```

**Key decisions:**

- **Separate thread**: Health server runs independently from bot's asyncio loop
- **Flask**: Lightweight HTTP server (already have it)
- **Polling**: Health server periodically reads bot state
- **Non-blocking**: Health checks don't interfere with bot operations

### Component: `lib/health_server.py` (NEW)

Create new module for health HTTP server:

```python
"""
HTTP health check server for bot monitoring.

Runs a lightweight Flask server on a separate thread to provide
real-time health status without blocking the bot's async operations.
"""

import threading
import time
from flask import Flask, jsonify
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.bot import CyTubeBot


class HealthServer:
    """HTTP server for health checks and metrics."""
    
    def __init__(self, bot: 'CyTubeBot', port: int = 8000):
        """
        Initialize health server.
        
        Args:
            bot: Bot instance to monitor
            port: HTTP port (8000 prod, 8001 test)
        """
        self.bot = bot
        self.port = port
        self.app = Flask(__name__)
        self.thread = None
        self.start_time = time.time()
        
        # Configure routes
        self._setup_routes()
    
    def _setup_routes(self):
        """Configure Flask routes."""
        
        @self.app.route('/api/health', methods=['GET'])
        def health():
            """Return bot health status."""
            return jsonify(self._get_health_data())
        
        @self.app.route('/api/metrics', methods=['GET'])
        def metrics():
            """Return Prometheus-compatible metrics."""
            return self._get_prometheus_metrics(), 200, {
                'Content-Type': 'text/plain; charset=utf-8'
            }
    
    def _get_health_data(self) -> dict:
        """
        Collect current health status from bot.
        
        Returns:
            Health status dictionary
        """
        uptime = time.time() - self.start_time
        
        # Get bot state (safely, with defaults)
        try:
            connected = self.bot.is_connected()
            channel = self.bot.channel_name if hasattr(self.bot, 'channel_name') else 'unknown'
            user_count = len(self.bot.users) if hasattr(self.bot, 'users') else 0
            requests = self.bot.request_count if hasattr(self.bot, 'request_count') else 0
            errors = self.bot.error_count if hasattr(self.bot, 'error_count') else 0
        except Exception:
            # Bot not fully initialized yet
            connected = False
            channel = 'initializing'
            user_count = 0
            requests = 0
            errors = 0
        
        # Determine overall status
        if not connected:
            status = 'unhealthy'
        elif errors > 100:  # Too many errors
            status = 'degraded'
        else:
            status = 'healthy'
        
        return {
            'status': status,
            'connected': connected,
            'channel': channel,
            'uptime_seconds': int(uptime),
            'version': self._get_version(),
            'user_count': user_count,
            'requests_handled': requests,
            'error_count': errors,
        }
    
    def _get_version(self) -> str:
        """Get bot version from git or fallback."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                timeout=1
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return 'unknown'
    
    def _get_prometheus_metrics(self) -> str:
        """
        Format metrics in Prometheus format.
        
        Returns:
            Prometheus metrics text
        """
        health = self._get_health_data()
        
        metrics = [
            '# HELP bot_connected Bot connection status (1=connected, 0=disconnected)',
            '# TYPE bot_connected gauge',
            f'bot_connected {1 if health["connected"] else 0}',
            '',
            '# HELP bot_uptime_seconds Bot uptime in seconds',
            '# TYPE bot_uptime_seconds counter',
            f'bot_uptime_seconds {health["uptime_seconds"]}',
            '',
            '# HELP bot_users Current user count in channel',
            '# TYPE bot_users gauge',
            f'bot_users {health["user_count"]}',
            '',
            '# HELP bot_requests_total Total requests handled',
            '# TYPE bot_requests_total counter',
            f'bot_requests_total {health["requests_handled"]}',
            '',
            '# HELP bot_errors_total Total errors encountered',
            '# TYPE bot_errors_total counter',
            f'bot_errors_total {health["error_count"]}',
            '',
        ]
        
        return '\n'.join(metrics)
    
    def start(self):
        """Start health server in background thread."""
        if self.thread and self.thread.is_alive():
            return  # Already running
        
        self.thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name='HealthServer'
        )
        self.thread.start()
        print(f"Health server started on port {self.port}")
    
    def _run_server(self):
        """Run Flask server (called in thread)."""
        self.app.run(
            host='0.0.0.0',
            port=self.port,
            debug=False,
            use_reloader=False
        )
    
    def stop(self):
        """Stop health server."""
        # Flask doesn't have clean shutdown in thread
        # Server will stop when bot exits (daemon thread)
        pass
```

### Integration in `lib/bot.py`

Modify bot to create and start health server:

```python
# At top of file
from lib.health_server import HealthServer

class CyTubeBot:
    def __init__(self, config_file: str):
        # ... existing init code ...
        
        # Add tracking attributes
        self.request_count = 0
        self.error_count = 0
        
        # Start health server
        health_port = config.get('health_port', 8000)
        self.health_server = HealthServer(self, port=health_port)
        self.health_server.start()
    
    async def connect(self):
        """Connect to CyTube server."""
        try:
            # ... existing connect code ...
            self.request_count += 1
        except Exception as e:
            self.error_count += 1
            raise
    
    def is_connected(self) -> bool:
        """Check if bot is connected to CyTube."""
        return (
            hasattr(self, 'socket') and
            self.socket is not None and
            self.socket.connected
        )
```

### Configuration Updates

Add health port to config files:

**config-test.json:**

```json
{
  "server": "cytu.be",
  "channel": "test-channel",
  "health_port": 8001
}
```

**config-prod.json:**

```json
{
  "server": "cytu.be",
  "channel": "programming",
  "health_port": 8000
}
```

### Dependencies

Add to `requirements.txt`:

```
Flask>=3.0.0
```

(May already be installed from Sprint 5 dashboard work.)

## Implementation Steps

1. **Create `lib/health_server.py`**
   - Implement `HealthServer` class
   - Flask routes: `/api/health`, `/api/metrics`
   - Thread management
   - Safe bot state access

2. **Update `lib/bot.py`**
   - Import `HealthServer`
   - Add `request_count`, `error_count` tracking
   - Create health server in `__init__`
   - Start server on bot startup
   - Implement `is_connected()` method

3. **Update configuration files**
   - Add `health_port: 8001` to `config-test.json`
   - Add `health_port: 8000` to `config-prod.json`

4. **Update `requirements.txt`**
   - Ensure Flask is listed (version >=3.0.0)

5. **Add tests**
   - Test health endpoint returns JSON
   - Test metrics endpoint returns Prometheus format
   - Test graceful degradation when bot not connected

6. **Update documentation**
   - Document health endpoint in README
   - Add monitoring guide

## Testing

### Manual Testing

```bash
# Start bot locally
python -m lib

# In another terminal, check health
curl http://localhost:8000/api/health | jq

# Expected output:
{
  "status": "healthy",
  "connected": true,
  "channel": "#programming",
  "uptime_seconds": 45,
  "version": "abc123f",
  "user_count": 3,
  "requests_handled": 12,
  "error_count": 0
}

# Check metrics
curl http://localhost:8000/api/metrics

# Expected output:
# HELP bot_connected Bot connection status
# TYPE bot_connected gauge
bot_connected 1
# ... more metrics
```

### Automated Testing

```python
# tests/test_health_endpoint.py
import pytest
import requests
import time
from lib.bot import CyTubeBot

def test_health_endpoint_returns_json():
    """Test that health endpoint returns valid JSON."""
    # Start bot (will start health server)
    bot = CyTubeBot('config-test.json')
    time.sleep(1)  # Let server start
    
    # Check endpoint
    response = requests.get('http://localhost:8001/api/health')
    assert response.status_code == 200
    
    data = response.json()
    assert 'status' in data
    assert 'connected' in data
    assert 'uptime_seconds' in data

def test_health_endpoint_reports_disconnected():
    """Test that health correctly reports disconnected state."""
    bot = CyTubeBot('config-test.json')
    # Don't connect
    time.sleep(1)
    
    response = requests.get('http://localhost:8001/api/health')
    data = response.json()
    
    assert data['connected'] == False
    assert data['status'] in ['unhealthy', 'initializing']

def test_metrics_endpoint_prometheus_format():
    """Test that metrics endpoint returns Prometheus format."""
    bot = CyTubeBot('config-test.json')
    time.sleep(1)
    
    response = requests.get('http://localhost:8001/api/metrics')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/plain; charset=utf-8'
    
    text = response.text
    assert 'bot_connected' in text
    assert 'bot_uptime_seconds' in text
```

## Validation Checklist

After implementation:

- [ ] `lib/health_server.py` created with `HealthServer` class
- [ ] `/api/health` endpoint returns JSON with 8 fields
- [ ] `/api/metrics` endpoint returns Prometheus format
- [ ] Health server starts on bot initialization
- [ ] Health server runs in separate thread (doesn't block bot)
- [ ] Config files updated with `health_port`
- [ ] `requirements.txt` includes Flask
- [ ] Manual test: `curl http://localhost:8000/api/health` works
- [ ] Manual test: `curl http://localhost:8000/api/metrics` works
- [ ] Automated tests pass
- [ ] Documentation updated

## Success Criteria

This critical dependency is complete when:

1. Health endpoint implemented and tested locally
2. Endpoint returns accurate bot status
3. Metrics endpoint works for Prometheus
4. Server runs without blocking bot operations
5. Configuration supports both test and prod ports
6. All tests pass
7. Code committed to branch

## Impact on Sprint 6

**Blocks these sorties:**

- Sortie 4: First test deployment (need to validate deployment worked)
- Sortie 5: First prod deployment (same)
- Sortie 6: Deploy monitoring (Prometheus needs to scrape this)

**Timeline:** Must complete before Sortie 4.

## Time Estimate

- **Create `health_server.py`**: 2 hours
- **Integrate with bot**: 1 hour
- **Testing**: 1 hour
- **Documentation**: 30 minutes
- **Total**: ~4.5 hours

Ready to implement! 🚀
