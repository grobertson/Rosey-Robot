# NATS Configuration Guide

**Purpose**: Configure NATS messaging for Quicksilver event bus architecture  
**Audience**: Deployment engineers and bot administrators  
**Prerequisites**: Sprint 6a (Quicksilver) complete, NATS server installed  

---

## Overview

Sprint 6a (Quicksilver) introduced a NATS-based event bus architecture that requires:

1. **NATS Server**: Message broker running on each deployment server
2. **Bot Configuration**: NATS connection settings in environment configs
3. **Plugin Configuration**: NATS subjects for plugin communication

This guide covers NATS setup and configuration for all environments.

---

## NATS Server Installation

The NATS server should be installed during **Sprint 6 Sortie 1** (Server Provisioning). See `docs/6-make-it-real/SPEC-Sortie-1-Server-Provisioning.md` for detailed instructions.

### Quick Summary

```bash
# Install NATS server binary
wget https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.tar.gz
tar -xzf nats-server-v2.10.7-linux-amd64.tar.gz
sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/

# Create systemd service
sudo systemctl enable nats
sudo systemctl start nats

# Verify installation
nats-server --version
sudo systemctl status nats
curl http://localhost:8222/varz
```

---

## NATS Server Configuration

The NATS server configuration is stored in `/etc/nats/nats-server.conf`.

### Production Configuration

**File: `/etc/nats/nats-server.conf`** (production server)

```conf
# NATS Server Configuration - Production

server_name: rosey_nats_prod

# Listen on localhost only (bot and NATS on same server)
host: 127.0.0.1
port: 4222

# Monitoring endpoint
http_port: 8222

# Logging
log_file: "/var/log/nats/nats-server.log"
debug: false
trace: false
logtime: true

# Connection limits
max_connections: 200        # Higher for production
max_control_line: 4096
max_payload: 1048576        # 1MB max message size

# Timeouts
ping_interval: 2m
ping_max: 2

# JetStream (message persistence)
jetstream {
    store_dir: "/var/lib/nats"
    max_mem: 2G             # Higher memory for production
    max_file: 20G           # More storage for production
}

# Security (future enhancement - authentication)
# authorization {
#     users = [
#         {user: "rosey", password: "$2a$11$..."}  # Bcrypt hash
#     ]
# }
```

### Staging/Test Configuration

**File: `/etc/nats/nats-server.conf`** (staging/test server)

```conf
# NATS Server Configuration - Staging/Test

server_name: rosey_nats_test

# Listen on localhost only
host: 127.0.0.1
port: 4222

# Monitoring endpoint
http_port: 8222

# Logging (more verbose for testing)
log_file: "/var/log/nats/nats-server.log"
debug: true                 # Enable debug logging for testing
trace: false
logtime: true

# Connection limits (smaller for test)
max_connections: 50
max_control_line: 4096
max_payload: 1048576

# Timeouts
ping_interval: 1m           # Faster ping for testing
ping_max: 2

# JetStream (smaller limits for test)
jetstream {
    store_dir: "/var/lib/nats"
    max_mem: 512M           # Less memory for test
    max_file: 5G            # Less storage for test
}
```

### Development Configuration

For local development, you can run NATS in Docker:

```bash
# Run NATS in Docker
docker run -d --name nats-dev \
    -p 4222:4222 \
    -p 8222:8222 \
    nats:2.10.7-alpine

# Verify
curl http://localhost:8222/varz
```

Or use the same systemd service approach as production.

---

## Bot Configuration

The bot's NATS connection settings are in the environment config files.

### Development Environment

**File: `environments/development/config.yaml`**

```yaml
nats:
  # Connection URL for NATS server
  servers:
    - "nats://localhost:4222"
  
  # Connection options
  name: "rosey-bot-dev"
  reconnect_time_wait: 2          # Seconds between reconnect attempts
  max_reconnect_attempts: 60      # Try for 2 minutes before giving up
  ping_interval: 30               # Seconds between pings
  max_outstanding_pings: 2        # Disconnect after 2 missed pings
  
  # Credentials (future enhancement)
  # user: "rosey"
  # password: "secret"
  
  # Subject prefixes
  prefix: "rosey.dev"             # All subjects start with rosey.dev.*
```

### Staging Environment

**File: `environments/staging/config.yaml`**

```yaml
nats:
  servers:
    - "nats://localhost:4222"
  
  name: "rosey-bot-staging"
  reconnect_time_wait: 2
  max_reconnect_attempts: 60
  ping_interval: 30
  max_outstanding_pings: 2
  
  # Staging uses different prefix to isolate from dev
  prefix: "rosey.staging"
```

### Production Environment

**File: `environments/production/config.yaml`**

```yaml
nats:
  servers:
    - "nats://localhost:4222"
  
  name: "rosey-bot-prod"
  reconnect_time_wait: 5          # Longer waits for production
  max_reconnect_attempts: -1      # Retry forever
  ping_interval: 60               # Less frequent pings
  max_outstanding_pings: 3        # More tolerant of missed pings
  
  # Production prefix for complete isolation
  prefix: "rosey.prod"
```

### Environment Variables

For sensitive configuration (future enhancement), use environment variables:

```bash
# In environments/*/secrets.env
NATS_SERVER="nats://localhost:4222"
NATS_USER="rosey"
NATS_PASSWORD="supersecret"
NATS_TOKEN="secrettoken123"  # Alternative to user/password
```

---

## Subject Hierarchy

NATS uses a hierarchical subject structure for routing messages.

### Standard Subjects

All subjects start with the environment prefix (e.g., `rosey.prod.*`):

```
rosey.{env}.cytube.>           # CyTube events (join, chat, etc.)
rosey.{env}.commands.>         # User commands
rosey.{env}.plugin.>           # Plugin-specific subjects
rosey.{env}.system.>           # System events (startup, shutdown)
```

### CyTube Event Subjects

```
rosey.{env}.cytube.chat.message      # Chat messages
rosey.{env}.cytube.user.join         # User joins channel
rosey.{env}.cytube.user.leave        # User leaves channel
rosey.{env}.cytube.playlist.add      # Video added to playlist
rosey.{env}.cytube.playlist.remove   # Video removed
```

### Command Subjects

```
rosey.{env}.commands.quote           # !quote command
rosey.{env}.commands.trivia          # !trivia command
rosey.{env}.commands.roll            # !roll command
rosey.{env}.commands.*               # Catch-all for other commands
```

### Plugin Subjects

```
rosey.{env}.plugin.{name}.request    # Request to plugin
rosey.{env}.plugin.{name}.response   # Response from plugin
rosey.{env}.plugin.{name}.event      # Plugin event notification
```

---

## Plugin Configuration

Each plugin has its own YAML configuration that includes NATS subjects.

### Example: Quote Plugin

**File: `environments/production/plugins/quotes.yaml`**

```yaml
name: quotes
enabled: true
type: isolated    # Runs in separate process

# NATS subjects this plugin subscribes to
subscriptions:
  - "rosey.prod.commands.quote"
  - "rosey.prod.commands.addquote"
  - "rosey.prod.commands.delquote"

# NATS subjects this plugin publishes to
publishes:
  - "rosey.prod.cytube.chat.message"  # Send quote to chat

# Plugin-specific config
config:
  database: "/opt/rosey-bot/data/quotes.db"
  max_quote_length: 500
  cooldown: 5  # Seconds between quotes
```

### Example: Trivia Plugin

**File: `environments/production/plugins/trivia.yaml`**

```yaml
name: trivia
enabled: true
type: isolated

subscriptions:
  - "rosey.prod.commands.trivia"
  - "rosey.prod.commands.triviastop"
  - "rosey.prod.cytube.chat.message"  # Listen for answers

publishes:
  - "rosey.prod.cytube.chat.message"

config:
  questions_file: "/opt/rosey-bot/data/trivia.json"
  time_limit: 30
  points_correct: 10
  points_wrong: 0
```

---

## Health Monitoring

### NATS Server Health

Check NATS server health via monitoring endpoint:

```bash
# Get server info
curl http://localhost:8222/varz

# Get connection stats
curl http://localhost:8222/connz

# Get subscription stats
curl http://localhost:8222/subsz

# Get route stats (for clustering)
curl http://localhost:8222/routez
```

### Bot Health

The bot exposes NATS connection status via health endpoint:

```bash
# Production health endpoint
curl http://localhost:8000/api/health

# Example response
{
  "status": "connected",
  "connected": true,
  "channel": "mychannel",
  "uptime": 12345,
  "version": "2.0.0",
  "user_count": 42,
  "requests": 1000,
  "errors": 3,
  "nats": {
    "connected": true,
    "server": "nats://localhost:4222",
    "subjects": 15
  }
}
```

---

## Troubleshooting

### NATS Server Not Starting

**Symptom**: `systemctl status nats` shows failed status

**Check**:
```bash
# Check logs
sudo journalctl -u nats -n 50

# Common issues:
# - Port 4222 already in use
# - Invalid config syntax
# - Insufficient permissions on log/data directories

# Fix permissions
sudo chown -R nats:nats /var/log/nats /var/lib/nats

# Test config manually
sudo -u nats nats-server -c /etc/nats/nats-server.conf
```

### Bot Can't Connect to NATS

**Symptom**: Bot logs show "Failed to connect to NATS"

**Check**:
```bash
# Is NATS running?
sudo systemctl status nats

# Is it listening?
sudo netstat -tlnp | grep 4222

# Can you reach it?
curl http://localhost:8222/varz

# Check bot config
cat environments/production/config.yaml | grep -A 10 nats
```

### Plugin Not Receiving Messages

**Symptom**: Plugin doesn't respond to commands

**Check**:
```bash
# Check plugin is running
ps aux | grep plugin_name

# Check plugin logs
tail -f /opt/rosey-bot/logs/plugins/plugin_name.log

# Test NATS subscription (requires nats CLI)
nats sub "rosey.prod.commands.quote"

# Send test message
nats pub "rosey.prod.commands.quote" '{"user":"test","message":"!quote"}'
```

### High Message Latency

**Symptom**: Commands take >100ms to execute

**Check**:
```bash
# Check NATS server stats
curl http://localhost:8222/varz | jq '.cpu, .mem'

# Check system load
uptime
top

# Check message backlog
curl http://localhost:8222/subsz

# Increase NATS resources if needed (edit config)
sudo systemctl restart nats
```

---

## Performance Tuning

### NATS Server

**For high-traffic production:**

```conf
# In /etc/nats/nats-server.conf

# Increase connection limits
max_connections: 500

# Increase payload size if needed
max_payload: 2097152  # 2MB

# Tune JetStream
jetstream {
    store_dir: "/var/lib/nats"
    max_mem: 4G
    max_file: 50G
}
```

### Bot Configuration

**For low-latency responses:**

```yaml
nats:
  ping_interval: 15              # More frequent pings detect failures faster
  max_outstanding_pings: 1       # Disconnect sooner
  reconnect_time_wait: 1         # Reconnect faster
```

**For unreliable networks:**

```yaml
nats:
  ping_interval: 120             # Less frequent pings
  max_outstanding_pings: 5       # More tolerant
  reconnect_time_wait: 10        # Wait longer between reconnects
  max_reconnect_attempts: -1     # Never give up
```

---

## Security Considerations

### Current State (Sprint 6a)

- NATS listens only on localhost (127.0.0.1)
- No authentication required
- All plugins can publish to all subjects
- Suitable for single-server deployments

### Future Enhancements

1. **Authentication**: Add user/password to NATS config
2. **Authorization**: Restrict which clients can pub/sub to which subjects
3. **TLS**: Encrypt NATS traffic (for multi-server deployments)
4. **Clustering**: Run multiple NATS servers for high availability
5. **Leafnodes**: Connect multiple bot instances securely

---

## Migration Path

### From Pre-Quicksilver Bot

1. **Install NATS Server** (see Sortie 1 spec)
2. **Update Bot Config** (add `nats:` section)
3. **Test in Development** (ensure NATS connectivity)
4. **Deploy to Staging** (validate with real traffic)
5. **Deploy to Production** (monitor closely)

### Rollback Plan

If NATS issues occur:

1. **Stop bot**: `sudo systemctl stop cytube-bot`
2. **Revert config**: Remove `nats:` section
3. **Restart with legacy mode**: Bot runs without NATS
4. **Fix NATS issues**: Debug and repair
5. **Redeploy**: Try again when ready

---

## References

- [NATS Documentation](https://docs.nats.io/)
- [NATS Server Configuration](https://docs.nats.io/running-a-nats-service/configuration)
- [NATS Python Client](https://github.com/nats-io/nats.py)
- Sprint 6a PRD: `docs/6a-quicksilver/PRD.md`
- Sprint 6 Sortie 1: `docs/6-make-it-real/SPEC-Sortie-1-Server-Provisioning.md`

---

**Document Version**: 1.0  
**Last Updated**: November 18, 2025  
**Maintained By**: Rosey-Robot Team
