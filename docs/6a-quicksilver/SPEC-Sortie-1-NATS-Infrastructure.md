# Sortie 1: NATS Infrastructure Setup

**Sprint:** 6a-quicksilver  
**Complexity:** ⭐☆☆☆☆ (Setup & Configuration)  
**Estimated Time:** 2-3 hours  
**Priority:** CRITICAL (blocks all other sorties)  
**Dependencies:** None

---

## Objective

Install and configure NATS server with JetStream enabled, verify basic functionality, and establish monitoring.

---

## Deliverables

1. ✅ NATS server installed and running
2. ✅ Configuration file with JetStream enabled
3. ✅ Monitoring dashboard accessible
4. ✅ Basic pub/sub test successful
5. ✅ Documentation for server setup

---

## Technical Tasks

### Task 1.1: Download & Install NATS Server

**Steps:**
```powershell
# Download NATS server
# https://github.com/nats-io/nats-server/releases/latest
# Windows: nats-server-v2.10.x-windows-amd64.zip

# Create directory structure
mkdir infrastructure\nats
cd infrastructure\nats

# Extract binary
# nats-server.exe should be in this directory

# Verify installation
.\nats-server.exe --version
```

**Expected Output:**
```
nats-server: v2.10.7
```

---

### Task 1.2: Create Server Configuration

**File:** `infrastructure/nats/nats-server.conf`

```conf
# NATS Server Configuration for Rosey Robot
# Production-grade configuration with JetStream persistence

# Server Identity
server_name: rosey-nats

# Network Configuration
port: 4222                      # Client connections
http_port: 8222                # HTTP monitoring endpoint

# WebSocket (for potential browser clients)
websocket {
    port: 8223
    no_tls: true               # Enable TLS in production
}

# JetStream Configuration
jetstream {
    store_dir: "./data/jetstream"
    
    # Memory limits
    max_memory: 1G             # Max RAM for stream storage
    max_file: 10G              # Max disk for stream storage
    
    # Domain (for clustering in future)
    # domain: rosey
}

# Logging
debug: false                   # Disable in production
trace: false                   # Disable in production
logtime: true
log_file: "../../logs/nats.log"
log_size_limit: 10MB          # Rotate at 10MB
max_traced_msg_len: 1024

# Connection Limits
max_connections: 100
max_payload: 8MB              # Large payloads for MediaCMS data
max_pending: 64MB
write_deadline: 5s

# Performance Tuning
max_control_line: 4096
max_subscriptions: 0          # Unlimited

# Authorization (Development)
authorization {
    # Simple token for development
    # Production: Use JWT-based auth
    token: $NATS_TOKEN
    timeout: 2
}

# Monitoring & Observability
http: 8222
system_account: SYS

# Ping interval
ping_interval: 2m
ping_max: 3

# Slow Consumer Protection
max_slow_consumers: 10
max_subs_per_conn: 0          # Unlimited

# TLS Configuration (for production)
# tls {
#     cert_file: "./certs/server-cert.pem"
#     key_file:  "./certs/server-key.pem"
#     ca_file:   "./certs/ca.pem"
#     verify: true
# }
```

**Environment Variables:**

Create `.env.nats` (add to .gitignore):
```bash
NATS_TOKEN=your_secure_token_here_dev_only
```

---

### Task 1.3: Create Start/Stop Scripts

**File:** `infrastructure/nats/start-nats.bat` (Windows)

```batch
@echo off
echo Starting NATS Server for Rosey...

REM Load environment variables
if exist .env.nats (
    for /f "tokens=*" %%a in (.env.nats) do set %%a
)

REM Create data directory if not exists
if not exist "data\jetstream" mkdir data\jetstream

REM Start NATS server
nats-server.exe -c nats-server.conf

pause
```

**File:** `infrastructure/nats/start-nats.sh` (Linux/Mac)

```bash
#!/bin/bash
echo "Starting NATS Server for Rosey..."

# Load environment variables
if [ -f .env.nats ]; then
    export $(cat .env.nats | xargs)
fi

# Create data directory
mkdir -p data/jetstream

# Start NATS server
./nats-server -c nats-server.conf
```

**File:** `infrastructure/nats/stop-nats.bat`

```batch
@echo off
echo Stopping NATS Server...
taskkill /IM nats-server.exe /F
pause
```

---

### Task 1.4: Test Basic Functionality

**Test Script:** `infrastructure/nats/test-connection.py`

```python
"""
Basic NATS connectivity test
Run this to verify NATS server is working
"""
import asyncio
import nats

async def test_nats():
    """Test NATS pub/sub"""
    
    print("Connecting to NATS...")
    nc = await nats.connect("nats://localhost:4222")
    print("✓ Connected to NATS")
    
    # Test subscription
    messages_received = []
    
    async def message_handler(msg):
        data = msg.data.decode()
        print(f"✓ Received: {data}")
        messages_received.append(data)
    
    await nc.subscribe("test.hello", cb=message_handler)
    print("✓ Subscribed to test.hello")
    
    # Test publish
    await nc.publish("test.hello", b"Hello, NATS!")
    print("✓ Published message")
    
    # Wait for message
    await asyncio.sleep(1)
    
    # Verify
    assert len(messages_received) == 1
    assert messages_received[0] == "Hello, NATS!"
    print("✓ Message received correctly")
    
    # Test request/reply
    async def reply_handler(msg):
        await nc.publish(msg.reply, b"Pong!")
    
    await nc.subscribe("test.ping", cb=reply_handler)
    
    response = await nc.request("test.ping", b"Ping!", timeout=2)
    assert response.data == b"Pong!"
    print("✓ Request/Reply works")
    
    # Cleanup
    await nc.close()
    print("✓ Connection closed")
    
    print("\n✅ All tests passed! NATS is ready.")

if __name__ == "__main__":
    asyncio.run(test_nats())
```

**Run Test:**
```powershell
# Install nats-py first
pip install nats-py

# Start NATS server in one terminal
cd infrastructure\nats
.\start-nats.bat

# Run test in another terminal
python test-connection.py
```

---

### Task 1.5: Verify Monitoring Dashboard

**Access Dashboard:**
```
http://localhost:8222
```

**Key Endpoints:**

- `/varz` - General server stats
- `/connz` - Connection information
- `/subsz` - Subscription information
- `/jsz` - JetStream information
- `/healthz` - Health check

**Test Commands:**
```powershell
# Check server status
curl http://localhost:8222/varz

# Check JetStream status
curl http://localhost:8222/jsz

# Health check
curl http://localhost:8222/healthz
```

**Expected Response (healthz):**
```json
{
  "status": "ok"
}
```

---

### Task 1.6: Create Monitoring Script

**File:** `infrastructure/nats/monitor.py`

```python
"""
NATS monitoring script
Displays real-time server stats
"""
import asyncio
import aiohttp
import json
from datetime import datetime

async def monitor_nats():
    """Monitor NATS server stats"""
    
    url = "http://localhost:8222/varz"
    
    print("NATS Server Monitor")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(url) as response:
                    data = await response.json()
                    
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}]")
                    print(f"Connections: {data.get('connections', 0)}")
                    print(f"Messages In:  {data.get('in_msgs', 0):,}")
                    print(f"Messages Out: {data.get('out_msgs', 0):,}")
                    print(f"Bytes In:     {data.get('in_bytes', 0):,}")
                    print(f"Bytes Out:    {data.get('out_bytes', 0):,}")
                    print(f"Slow Consumers: {data.get('slow_consumers', 0)}")
                    print(f"Memory: {data.get('mem', 0) / 1024 / 1024:.2f} MB")
                    
            except Exception as e:
                print(f"Error: {e}")
            
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(monitor_nats())
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")
```

---

## Testing Checklist

- [ ] NATS server starts without errors
- [ ] Configuration file loaded successfully
- [ ] JetStream storage directory created
- [ ] Monitoring dashboard accessible on :8222
- [ ] `/varz` endpoint returns valid JSON
- [ ] `/healthz` returns `{"status": "ok"}`
- [ ] Basic pub/sub test passes
- [ ] Request/reply pattern works
- [ ] Server logs to file correctly
- [ ] Token authentication works

---

## Documentation

### Setup Guide

Create `infrastructure/nats/README.md`:

```markdown
# NATS Server Setup for Rosey

## Quick Start

1. Download NATS server from https://github.com/nats-io/nats-server/releases
2. Extract to `infrastructure/nats/`
3. Create `.env.nats` with token
4. Run `start-nats.bat` (Windows) or `start-nats.sh` (Linux/Mac)
5. Verify: http://localhost:8222

## Configuration

Edit `nats-server.conf` for:
- Port changes
- Memory limits
- Logging levels
- Authentication

## Monitoring

- Dashboard: http://localhost:8222
- Stats: http://localhost:8222/varz
- JetStream: http://localhost:8222/jsz
- Health: http://localhost:8222/healthz

## Troubleshooting

### Server won't start
- Check if port 4222 is already in use
- Verify NATS_TOKEN environment variable
- Check logs in `../../logs/nats.log`

### Cannot connect
- Verify server is running: `curl http://localhost:8222/healthz`
- Check firewall settings
- Verify token matches in client

## Production Deployment

1. Enable TLS (uncomment in config)
2. Use JWT-based auth (not simple token)
3. Set up monitoring alerts
4. Configure clustering for HA
5. Set up automated backups of JetStream data
```

---

## Success Criteria

✅ NATS server running on :4222  
✅ HTTP monitoring on :8222  
✅ JetStream enabled and storing data  
✅ Basic pub/sub verified  
✅ Request/reply verified  
✅ Monitoring dashboard accessible  
✅ Documentation complete  

---

## Time Breakdown

- Download & install: 15 minutes
- Configuration file: 30 minutes
- Start/stop scripts: 15 minutes
- Testing: 45 minutes
- Monitoring setup: 30 minutes
- Documentation: 30 minutes

**Total: 2.5 hours**

---

## Next Steps

After completing this sortie:
- ✅ NATS infrastructure ready
- → Proceed to Sortie 2: Event Bus Core Library
- → Begin implementing Python NATS client wrapper
