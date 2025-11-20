# Sortie 3: Create systemd Services

**Status**: Planning  
**Owner**: Agent (with user verification)  
**Estimated Effort**: 1-2 hours  
**Related Issue**: #21  
**Depends On**: Sorties 1-2 (servers provisioned, secrets configured)

## Overview

Create and configure systemd service files for all bot components so they run as system services with automatic restart, proper logging, and boot-time startup.

**Key Point**: I'll handle most of this! You'll just need to verify the services on the server after I create the files.

## Components Needing Services

We need systemd services for:

1. **cytube-bot** - The main bot (already exists, needs updating)
2. **cytube-web** - Status dashboard (already exists, needs updating)
3. **prometheus** - Metrics collection (new)
4. **alertmanager** - Alert handling (new)

## Current Service Files Review

### Existing: `systemd/cytube-bot.service`

Current issues to fix:
- Uses generic `botuser` user (should be `rosey`)
- Uses old path `/home/botuser/cytube-bot` (should be `/opt/rosey-bot`)
- Points to `bot/rosey/rosey.py` (doesn't exist in current structure)
- Should point to `python -m lib` (our actual entry point)

### Existing: `systemd/cytube-web.service`

Current issues to fix:
- Uses `botuser` user (should be `rosey`)
- Old path `/home/botuser/cytube-bot`
- Points to wrong file `web/status_server.py`
- Should use `web/dashboard.py` (from Sprint 5)

### Missing: Prometheus Service

Need to create for Prometheus monitoring.

### Missing: Alertmanager Service

Need to create for alert notifications.

## Implementation Plan

### Task 1: Update cytube-bot.service

**Changes needed:**

```ini
[Unit]
Description=Rosey CyTube Bot
Documentation=https://github.com/grobertson/Rosey-Robot
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rosey
Group=rosey
WorkingDirectory=/opt/rosey-bot

# Run bot using module entry point
Environment="PYTHONPATH=/opt/rosey-bot"
ExecStart=/usr/bin/python3 -m lib

# Configuration
Environment="BOT_CONFIG=/opt/rosey-bot/config-prod.json"

# Restart configuration
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=60

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rosey-bot

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Key changes:**
- User: `botuser` → `rosey`
- WorkingDirectory: `/home/botuser/cytube-bot` → `/opt/rosey-bot`
- ExecStart: Points to proper module entry
- Uses `config-prod.json` from deployment
- Logs to systemd journal
- Simpler, cleaner configuration

### Task 2: Update cytube-web.service

**Changes needed:**

```ini
[Unit]
Description=Rosey Bot Status Dashboard
Documentation=https://github.com/grobertson/Rosey-Robot
After=network.target rosey-bot.service

[Service]
Type=simple
User=rosey
Group=rosey
WorkingDirectory=/opt/rosey-bot/web

# Run dashboard server
Environment="PYTHONPATH=/opt/rosey-bot"
ExecStart=/usr/bin/python3 dashboard.py

# Restart configuration
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rosey-dashboard

# Security hardening
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Key changes:**
- User: `botuser` → `rosey`
- WorkingDirectory: `/opt/rosey-bot/web`
- ExecStart: `dashboard.py` (from Sprint 5)
- Depends on bot service (After directive)
- Logs to journal

### Task 3: Create prometheus.service

**New service file:**

```ini
[Unit]
Description=Prometheus Monitoring
Documentation=https://prometheus.io/docs/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rosey
Group=rosey
WorkingDirectory=/opt/rosey-bot/monitoring

# Prometheus binary and config
ExecStart=/usr/local/bin/prometheus \
  --config.file=/opt/rosey-bot/monitoring/prometheus.yml \
  --storage.tsdb.path=/opt/rosey-bot/monitoring/data \
  --web.console.templates=/usr/share/prometheus/consoles \
  --web.console.libraries=/usr/share/prometheus/console_libraries

# Restart configuration
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=prometheus

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Features:**
- Runs as `rosey` user
- Uses config from `/opt/rosey-bot/monitoring/`
- Data stored in `/opt/rosey-bot/monitoring/data/`
- Auto-restart on failure
- Journal logging

### Task 4: Create alertmanager.service

**New service file:**

```ini
[Unit]
Description=Prometheus Alertmanager
Documentation=https://prometheus.io/docs/alerting/alertmanager/
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=rosey
Group=rosey
WorkingDirectory=/opt/rosey-bot/monitoring

# Alertmanager binary and config
ExecStart=/usr/local/bin/alertmanager \
  --config.file=/opt/rosey-bot/monitoring/alertmanager.yml \
  --storage.path=/opt/rosey-bot/monitoring/alertmanager-data

# Restart configuration
Restart=always
RestartSec=10

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=alertmanager

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

**Features:**
- Runs as `rosey` user
- Uses config from `/opt/rosey-bot/monitoring/`
- Data stored in `/opt/rosey-bot/monitoring/alertmanager-data/`
- Auto-restart on failure
- Journal logging

## Service Installation (You'll do this on servers)

After I create the service files, you'll install them on each server:

### On Test Server (port 8001)

```bash
# SSH to test server
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP

# Service files will be deployed by GitHub Actions to /opt/rosey-bot/systemd/
# Copy to systemd directory
sudo cp /opt/rosey-bot/systemd/rosey-bot.service /etc/systemd/system/
sudo cp /opt/rosey-bot/systemd/rosey-dashboard.service /etc/systemd/system/
sudo cp /opt/rosey-bot/systemd/prometheus.service /etc/systemd/system/
sudo cp /opt/rosey-bot/systemd/alertmanager.service /etc/systemd/system/

# Reload systemd to recognize new services
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable rosey-bot
sudo systemctl enable rosey-dashboard
sudo systemctl enable prometheus
sudo systemctl enable alertmanager

# Start services
sudo systemctl start rosey-bot
sudo systemctl start rosey-dashboard
sudo systemctl start prometheus
sudo systemctl start alertmanager

# Check status
sudo systemctl status rosey-bot
sudo systemctl status rosey-dashboard
sudo systemctl status prometheus
sudo systemctl status alertmanager
```

### On Production Server (port 8000)

Same commands as test server. Services automatically use production config.

## Service Management Commands

Once installed, manage services with:

### Check Status

```bash
# Individual service
sudo systemctl status rosey-bot

# All Rosey services
sudo systemctl status 'rosey-*'

# All monitoring services
sudo systemctl status prometheus alertmanager
```

### View Logs

```bash
# Real-time logs
sudo journalctl -u rosey-bot -f

# Last 50 lines
sudo journalctl -u rosey-bot -n 50

# Logs since boot
sudo journalctl -u rosey-bot -b

# All Rosey services
sudo journalctl -u rosey-bot -u rosey-dashboard -f
```

### Start/Stop/Restart

```bash
# Start service
sudo systemctl start rosey-bot

# Stop service
sudo systemctl stop rosey-bot

# Restart service (for deployments)
sudo systemctl restart rosey-bot

# Reload config without full restart
sudo systemctl reload rosey-bot
```

### Enable/Disable Boot Startup

```bash
# Enable (start on boot)
sudo systemctl enable rosey-bot

# Disable (don't start on boot)
sudo systemctl disable rosey-bot

# Check if enabled
sudo systemctl is-enabled rosey-bot
```

## Service Dependencies

Services depend on each other:

```
rosey-bot.service
  ↓ (After)
rosey-dashboard.service (reads bot health endpoint)

prometheus.service (independent)
  ↓ (scrapes)
rosey-bot health endpoint
rosey-dashboard metrics

alertmanager.service (independent)
  ↑ (receives alerts from)
prometheus
```

**Start order:**
1. prometheus, alertmanager (can start anytime)
2. rosey-bot (core service)
3. rosey-dashboard (depends on bot being up)

**Stop order:** Reverse

## Validation Checklist

After service installation, verify:

### Service Status Checks

- [ ] `rosey-bot.service` exists in `/etc/systemd/system/`
- [ ] `rosey-dashboard.service` exists in `/etc/systemd/system/`
- [ ] `prometheus.service` exists in `/etc/systemd/system/`
- [ ] `alertmanager.service` exists in `/etc/systemd/system/`
- [ ] All services enabled: `systemctl is-enabled <service>` returns `enabled`
- [ ] All services running: `systemctl is-active <service>` returns `active`

### Functionality Checks

- [ ] Bot is running: `ps aux | grep "python3 -m lib"`
- [ ] Dashboard is running: `ps aux | grep dashboard.py`
- [ ] Prometheus is running: `ps aux | grep prometheus`
- [ ] Alertmanager is running: `ps aux | grep alertmanager`
- [ ] Bot logs appearing: `journalctl -u rosey-bot -n 10`
- [ ] Dashboard accessible: `curl http://localhost:8001/status` (test) or `8000` (prod)
- [ ] Prometheus accessible: `curl http://localhost:9090/-/healthy`
- [ ] Alertmanager accessible: `curl http://localhost:9093/-/healthy`

### Auto-Restart Checks

Test that services restart on failure:

```bash
# Test bot auto-restart
sudo systemctl stop rosey-bot
sleep 11  # Wait for RestartSec=10
sudo systemctl status rosey-bot  # Should be active again

# Test crash recovery (more aggressive)
sudo kill -9 $(pgrep -f "python3 -m lib")
sleep 11
sudo systemctl status rosey-bot  # Should have restarted
```

### Boot Startup Checks

Test services start on boot:

```bash
# Reboot server
sudo reboot

# Wait for server to come back up, then SSH and check:
sudo systemctl status rosey-bot
sudo systemctl status rosey-dashboard
sudo systemctl status prometheus
sudo systemctl status alertmanager
# All should be active
```

## Common Service Issues & Solutions

### Issue: "Failed to start service"

**Check:**

```bash
# View full error
sudo journalctl -u rosey-bot -n 50

# Check service file syntax
sudo systemd-analyze verify /etc/systemd/system/rosey-bot.service

# Check file permissions
ls -l /etc/systemd/system/rosey-bot.service
# Should be: -rw-r--r-- root root
```

**Fix:**

```bash
# Fix permissions
sudo chmod 644 /etc/systemd/system/rosey-bot.service

# Reload after fixing
sudo systemctl daemon-reload
sudo systemctl start rosey-bot
```

### Issue: "User 'rosey' not found"

**Check:**

```bash
# Verify user exists
id rosey
```

**Fix:**

```bash
# Create user if missing
sudo useradd -m -s /bin/bash rosey
sudo systemctl start rosey-bot
```

### Issue: "WorkingDirectory does not exist"

**Check:**

```bash
ls -ld /opt/rosey-bot
```

**Fix:**

```bash
sudo mkdir -p /opt/rosey-bot
sudo chown rosey:rosey /opt/rosey-bot
sudo systemctl start rosey-bot
```

### Issue: "Python module not found"

**Check:**

```bash
# Test Python import manually
cd /opt/rosey-bot
python3 -c "import lib; print('OK')"
```

**Fix:**

```bash
# Check deployment completed
ls -la /opt/rosey-bot/lib/

# Redeploy if files missing
# (We'll cover this in Sortie 4)
```

### Issue: "Permission denied" in logs

**Check:**

```bash
# Check file ownership
ls -la /opt/rosey-bot/

# Check log directory
sudo ls -la /var/log/journal/
```

**Fix:**

```bash
# Fix ownership
sudo chown -R rosey:rosey /opt/rosey-bot/

# Ensure journal logging enabled
sudo systemctl restart systemd-journald
```

## Service File Locations

After completion:

**In Repository:**

- `systemd/rosey-bot.service`
- `systemd/rosey-dashboard.service`
- `systemd/prometheus.service`
- `systemd/alertmanager.service`

**On Servers:**

- `/etc/systemd/system/rosey-bot.service`
- `/etc/systemd/system/rosey-dashboard.service`
- `/etc/systemd/system/prometheus.service`
- `/etc/systemd/system/alertmanager.service`

## What I'll Do (Agent Tasks)

1. ✅ Update `systemd/cytube-bot.service` → rename to `rosey-bot.service`
2. ✅ Update `systemd/cytube-web.service` → rename to `rosey-dashboard.service`
3. ✅ Create `systemd/prometheus.service`
4. ✅ Create `systemd/alertmanager.service`
5. ✅ Update systemd README with usage instructions
6. ✅ Test service file syntax locally
7. ✅ Commit service files to repository

## What You'll Do (User Tasks)

1. **After Sortie 4 (first deployment):**
   - SSH to test server
   - Copy service files to `/etc/systemd/system/`
   - Run `systemctl daemon-reload`
   - Enable and start services
   - Verify all services running

2. **After Sortie 5 (production deployment):**
   - Repeat for production server

3. **Ongoing:**
   - Use `systemctl restart` after deployments
   - Check logs with `journalctl` when debugging
   - Monitor service status

## Success Criteria

Sortie 3 is complete when:

- [ ] All 4 service files created/updated
- [ ] Services use correct user (`rosey`)
- [ ] Services use correct paths (`/opt/rosey-bot`)
- [ ] Services configured for auto-restart
- [ ] Services configured for boot startup
- [ ] Service files committed to repository
- [ ] Documentation updated

**Note:** Service *installation* happens in Sortie 4 (test) and Sortie 5 (prod), not in this sortie. This sortie just creates the files.

## Next Steps

After this sortie:

1. Verify **Sorties 2A, 2B, 2C** are complete (timeout, health endpoint, SSH deployment)
2. Those must be complete before Sortie 4 (first deployment)
3. In Sortie 4, we'll install and test these services on test server
4. In Sortie 5, we'll install on production server

## Time Estimate

- **Creating service files**: 1 hour
- **Testing syntax**: 15 minutes
- **Documentation**: 30 minutes
- **Total**: ~2 hours

## Questions?

Ask me:
- "What does X setting in the service file do?"
- "Why are we using systemd journal instead of log files?"
- "How do I debug service startup issues?"
- "Can I customize the service files for my setup?"

Ready to proceed! 🚀
