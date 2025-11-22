# Deployment Guide

## Overview

This guide covers deploying Rosey-Robot in various environments, from local development to production. As of Sprint 9 (The Accountant), Rosey uses an event-driven architecture with NATS, requiring deployment of multiple services.

## Architecture

### v1.x (Monolithic - Legacy)
```
Single Process:
  Bot + Database (embedded)
```

### v2.x (Event-Driven - Current)
```
Multiple Processes:
  1. NATS Server (event bus)
  2. Bot (publishes events)
  3. DatabaseService (subscribes to events)
```

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.10+
- NATS Server 2.9+
- Git

### 1. Install NATS Server

#### macOS
```bash
brew install nats-server
```

#### Linux (Ubuntu/Debian)
```bash
# Download latest release
curl -L https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.tar.gz -o nats-server.tar.gz
tar -xzf nats-server.tar.gz
sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/
```

#### Windows
Download from: https://github.com/nats-io/nats-server/releases

Or use Chocolatey:
```powershell
choco install nats-server
```

### 2. Clone Repository

```bash
git clone https://github.com/grobertson/Rosey-Robot.git
cd Rosey-Robot
```

### 3. Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 4. Configure Bot

```bash
# Copy example config
cp bot/rosey/config.json.dist bot/rosey/config.json

# Edit configuration
nano bot/rosey/config.json
```

**Required changes**:
- Update `platforms[0].channel` to your CyTube channel
- Optionally set `platforms[0].user` and `platforms[0].password` for auth
- Verify `nats.url` is `nats://localhost:4222`

### 5. Migrate Configuration (if upgrading from v1.x)

```bash
python -m common.config bot/rosey/config.json
```

This automatically converts v1.x config to v2.x format.

### 6. Start Services

**Terminal 1 - NATS Server:**
```bash
nats-server
```

**Terminal 2 - Database Service:**
```bash
python -m lib.database_service bot/rosey/config.json
```

**Terminal 3 - Bot:**
```bash
python bot/rosey/rosey.py bot/rosey/config.json
```

### 7. Verify Deployment

Check logs for:
- ✅ NATS Server: `Server is ready`
- ✅ DatabaseService: `DatabaseService started`
- ✅ Bot: `Connected to channel`

---

## Production Deployment

### Systemd (Linux)

Production deployments should use systemd for service management.

#### 1. Install NATS as Service

Create `/etc/systemd/system/nats.service`:
```ini
[Unit]
Description=NATS Server
After=network.target

[Service]
Type=simple
User=rosey
Group=rosey
ExecStart=/usr/local/bin/nats-server -c /etc/nats/nats.conf
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Create `/etc/nats/nats.conf`:
```text
# NATS Server Configuration
port: 4222
http_port: 8222

# Logging
logtime: true
log_file: "/var/log/nats/nats.log"

# Limits
max_payload: 1048576
max_connections: 100
max_control_line: 4096

# JetStream (optional - for persistence)
jetstream {
  store_dir: "/var/lib/nats"
  max_memory_store: 1GB
  max_file_store: 10GB
}
```

#### 2. Install DatabaseService

Create `/etc/systemd/system/rosey-database.service`:
```ini
[Unit]
Description=Rosey Database Service
After=nats.service
Requires=nats.service

[Service]
Type=simple
User=rosey
Group=rosey
WorkingDirectory=/opt/rosey
ExecStart=/opt/rosey/.venv/bin/python -m lib.database_service /opt/rosey/bot/rosey/config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

#### 3. Install Bot Service

Create `/etc/systemd/system/rosey-bot.service`:
```ini
[Unit]
Description=Rosey CyTube Bot
After=nats.service rosey-database.service
Requires=nats.service

[Service]
Type=simple
User=rosey
Group=rosey
WorkingDirectory=/opt/rosey
ExecStart=/opt/rosey/.venv/bin/python bot/rosey/rosey.py bot/rosey/config.json
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

#### 4. Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable nats
sudo systemctl enable rosey-database
sudo systemctl enable rosey-bot

# Start services
sudo systemctl start nats
sudo systemctl start rosey-database
sudo systemctl start rosey-bot

# Check status
sudo systemctl status nats
sudo systemctl status rosey-database
sudo systemctl status rosey-bot
```

#### 5. Monitor Logs

```bash
# Follow all Rosey logs
sudo journalctl -fu rosey-bot -fu rosey-database

# Follow NATS logs
sudo journalctl -fu nats

# View recent logs
sudo journalctl -u rosey-bot -n 100 --no-pager
```

#### 6. Service Management

```bash
# Restart services
sudo systemctl restart rosey-bot
sudo systemctl restart rosey-database

# Stop services
sudo systemctl stop rosey-bot
sudo systemctl stop rosey-database

# View service dependencies
systemctl list-dependencies rosey-bot
```

---

## Docker Deployment

### Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  nats:
    image: nats:2.10-alpine
    container_name: rosey-nats
    command: 
      - "-js"
      - "-m"
      - "8222"
    ports:
      - "4222:4222"  # Client connections
      - "8222:8222"  # HTTP monitoring
    volumes:
      - nats-data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:8222/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  database:
    build: .
    container_name: rosey-database
    command: python -m lib.database_service /app/bot/rosey/config.json
    depends_on:
      nats:
        condition: service_healthy
    volumes:
      - ./bot/rosey/config.json:/app/bot/rosey/config.json:ro
      - database-data:/app/data
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3

  bot:
    build: .
    container_name: rosey-bot
    command: python bot/rosey/rosey.py bot/rosey/config.json
    depends_on:
      nats:
        condition: service_healthy
      database:
        condition: service_started
    volumes:
      - ./bot/rosey/config.json:/app/bot/rosey/config.json:ro
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped

volumes:
  nats-data:
  database-data:
```

Create `Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Default command (overridden by docker-compose)
CMD ["python", "bot/rosey/rosey.py", "bot/rosey/config.json"]
```

Update `config.json` for Docker:
```json
{
  "version": 2,
  "platforms": [{
    "name": "cytube",
    "server": "https://cytu.be",
    "channel": "your_channel"
  }],
  "nats": {
    "url": "nats://nats:4222"
  },
  "database": {
    "path": "/app/data/rosey.db"
  },
  "logging": {
    "level": "INFO",
    "file": "/app/data/rosey.log"
  }
}
```

**Start Stack:**
```bash
docker-compose up -d
```

**View Logs:**
```bash
docker-compose logs -f bot
docker-compose logs -f database
docker-compose logs -f nats
```

**Stop Stack:**
```bash
docker-compose down
```

---

## Kubernetes Deployment

### Namespace

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: rosey
```

### NATS StatefulSet

```yaml
# nats-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: nats
  namespace: rosey
spec:
  serviceName: nats
  replicas: 1
  selector:
    matchLabels:
      app: nats
  template:
    metadata:
      labels:
        app: nats
    spec:
      containers:
      - name: nats
        image: nats:2.10-alpine
        args:
          - "-js"
          - "-m"
          - "8222"
        ports:
        - containerPort: 4222
          name: client
        - containerPort: 8222
          name: monitoring
        volumeMounts:
        - name: nats-data
          mountPath: /data
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8222
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8222
          initialDelaySeconds: 5
          periodSeconds: 5
  volumeClaimTemplates:
  - metadata:
      name: nats-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: nats
  namespace: rosey
spec:
  selector:
    app: nats
  ports:
  - port: 4222
    name: client
  - port: 8222
    name: monitoring
  clusterIP: None
```

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rosey-config
  namespace: rosey
data:
  config.json: |
    {
      "version": 2,
      "platforms": [{
        "name": "cytube",
        "server": "https://cytu.be",
        "channel": "your_channel"
      }],
      "nats": {
        "url": "nats://nats:4222"
      },
      "database": {
        "path": "/data/rosey.db"
      }
    }
```

### Database Deployment

```yaml
# database-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rosey-database
  namespace: rosey
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rosey-database
  template:
    metadata:
      labels:
        app: rosey-database
    spec:
      containers:
      - name: database
        image: rosey-bot:latest
        command: ["python", "-m", "lib.database_service", "/config/config.json"]
        volumeMounts:
        - name: config
          mountPath: /config
        - name: data
          mountPath: /data
        env:
        - name: PYTHONUNBUFFERED
          value: "1"
      volumes:
      - name: config
        configMap:
          name: rosey-config
      - name: data
        persistentVolumeClaim:
          claimName: rosey-data
```

### Bot Deployment

```yaml
# bot-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rosey-bot
  namespace: rosey
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rosey-bot
  template:
    metadata:
      labels:
        app: rosey-bot
    spec:
      containers:
      - name: bot
        image: rosey-bot:latest
        command: ["python", "bot/rosey/rosey.py", "/config/config.json"]
        volumeMounts:
        - name: config
          mountPath: /config
        env:
        - name: PYTHONUNBUFFERED
          value: "1"
      volumes:
      - name: config
        configMap:
          name: rosey-config
```

**Deploy:**
```bash
kubectl apply -f namespace.yaml
kubectl apply -f nats-statefulset.yaml
kubectl apply -f configmap.yaml
kubectl apply -f database-deployment.yaml
kubectl apply -f bot-deployment.yaml
```

---

## Monitoring

### NATS Monitoring

NATS provides HTTP monitoring endpoint on port 8222:

```bash
# Server info
curl http://localhost:8222/varz

# Connection stats
curl http://localhost:8222/connz

# Subscription stats
curl http://localhost:8222/subsz

# Route info (clustering)
curl http://localhost:8222/routez
```

### Prometheus Metrics

Enable Prometheus exporter in NATS config:
```text
# /etc/nats/nats.conf
http_port: 8222
```

Add to `prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'nats'
    static_configs:
      - targets: ['localhost:8222']
```

### Application Logs

**Structured Logging** (recommended for production):

Update `config.json`:
```json
{
  "logging": {
    "level": "INFO",
    "format": "json",
    "file": "/var/log/rosey/rosey.log"
  }
}
```

**Log Aggregation**:
- Use `journalctl` for systemd
- Use ELK stack (Elasticsearch, Logstash, Kibana)
- Use Loki + Grafana for Kubernetes

---

## Backup and Recovery

### Database Backups

```bash
# Create backup
cp /opt/rosey/data/rosey.db /backups/rosey-$(date +%Y%m%d).db

# Automated daily backup
cat > /etc/cron.daily/rosey-backup <<'EOF'
#!/bin/bash
cp /opt/rosey/data/rosey.db /backups/rosey-$(date +%Y%m%d).db
find /backups -name "rosey-*.db" -mtime +30 -delete
EOF
chmod +x /etc/cron.daily/rosey-backup
```

### Configuration Backups

```bash
# Backup config
cp /opt/rosey/bot/rosey/config.json /backups/config-$(date +%Y%m%d).json
```

### NATS JetStream Backups

If using JetStream persistence:
```bash
# Backup JetStream data
tar -czf /backups/nats-$(date +%Y%m%d).tar.gz /var/lib/nats/
```

### Recovery

1. Stop services
2. Restore database: `cp /backups/rosey-YYYYMMDD.db /opt/rosey/data/rosey.db`
3. Restore config: `cp /backups/config-YYYYMMDD.json /opt/rosey/bot/rosey/config.json`
4. Start services

---

## Scaling

### Horizontal Scaling

**Multiple Bots → One Database:**
```bash
# Start multiple bot instances with different channels
python bot/rosey/rosey.py config-channel1.json &
python bot/rosey/rosey.py config-channel2.json &
python bot/rosey/rosey.py config-channel3.json &

# One DatabaseService handles all
python -m lib.database_service config.json
```

**NATS Clustering** (for high availability):
```text
# /etc/nats/nats-1.conf
cluster {
  name: rosey-cluster
  listen: 0.0.0.0:6222
  routes: [
    nats://nats-2:6222
    nats://nats-3:6222
  ]
}
```

### Load Balancing

Not applicable - CyTube uses WebSocket connections (1 bot = 1 connection).

For multiple channels, run multiple bot instances.

---

## Security

### NATS Authentication

Enable auth in `/etc/nats/nats.conf`:
```text
authorization {
  users = [
    {user: rosey, password: "secret123"}
  ]
}
```

Update bot config:
```json
{
  "nats": {
    "url": "nats://rosey:secret123@localhost:4222"
  }
}
```

### TLS/SSL

**NATS with TLS:**
```text
# /etc/nats/nats.conf
tls {
  cert_file: "/etc/nats/certs/server.pem"
  key_file: "/etc/nats/certs/server-key.pem"
  ca_file: "/etc/nats/certs/ca.pem"
  verify: true
}
```

**Update config:**
```json
{
  "nats": {
    "url": "tls://localhost:4222"
  }
}
```

### Firewall Rules

```bash
# Allow NATS client connections
sudo ufw allow 4222/tcp comment "NATS client"

# Allow NATS monitoring (localhost only)
sudo ufw allow from 127.0.0.1 to any port 8222

# Deny all other inbound
sudo ufw default deny incoming
sudo ufw enable
```

---

## Troubleshooting

### Bot Won't Connect

1. Check NATS is running: `systemctl status nats`
2. Check NATS connectivity: `telnet localhost 4222`
3. Check bot logs: `journalctl -u rosey-bot -n 50`
4. Verify config: `cat bot/rosey/config.json | grep nats`

### DatabaseService Not Receiving Events

1. Check service is running: `systemctl status rosey-database`
2. Check NATS subscriptions: `curl http://localhost:8222/subsz`
3. Check for errors: `journalctl -u rosey-database -n 50`
4. Test NATS manually: `nats pub rosey.test "hello"`

### High Latency

1. Check NATS performance: `curl http://localhost:8222/varz`
2. Check database size: `ls -lh /opt/rosey/data/rosey.db`
3. Monitor system resources: `htop`
4. Enable verbose logging: Set `"log_level": "DEBUG"` in config

### Memory Leaks

1. Monitor memory: `ps aux | grep python`
2. Check NATS memory: `curl http://localhost:8222/varz | grep mem`
3. Restart services if needed
4. Review logs for warnings

---

## Migration Guide

See [`MIGRATION.md`](docs/sprints/active/9-The-Accountant/MIGRATION.md) for complete v1.x → v2.x migration guide.

---

## Performance Tuning

### NATS Configuration

```text
# /etc/nats/nats.conf
# Increase limits for high-throughput
max_payload: 2097152        # 2MB
max_connections: 1000
max_subscriptions: 10000
max_pending: 67108864       # 64MB

# Enable JetStream for persistence
jetstream {
  store_dir: "/var/lib/nats"
  max_memory_store: 2GB
  max_file_store: 20GB
}
```

### Python Optimization

```bash
# Use uvloop for better async performance
pip install uvloop

# Enable in bot code
import uvloop
uvloop.install()
```

### Database Optimization

```python
# In DatabaseService, use connection pooling
# Enable WAL mode for better concurrency
await db.execute("PRAGMA journal_mode=WAL")
await db.execute("PRAGMA synchronous=NORMAL")
```

---

## Support

- Documentation: [`README.md`](README.md), [`ARCHITECTURE.md`](ARCHITECTURE.md)
- Issues: https://github.com/grobertson/Rosey-Robot/issues
- NATS Docs: https://docs.nats.io
