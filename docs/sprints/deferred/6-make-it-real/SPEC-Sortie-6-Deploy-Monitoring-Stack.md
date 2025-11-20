# Sortie 6: Deploy Monitoring Stack

**Status**: Planning  
**Owner**: User (installation), Agent (configuration files)  
**Estimated Effort**: 2-3 hours  
**Related Issue**: #24  
**Depends On**: Sorties 4-5 (servers deployed and stable)

## Overview

Deploy Prometheus and Alertmanager to collect metrics and send alerts. This gives us visibility into bot health and automatic notifications when something goes wrong.

**What we're building:**

```
Bot Health Endpoint (:8000/8001)
    ↓ (scrapes every 15s)
Prometheus (:9090)
    ↓ (evaluates rules)
Alertmanager (:9093)
    ↓ (sends notifications)
Your Email/Slack/Webhook
```

## Prerequisites

- [ ] Test and production servers stable (Sorties 4-5)
- [ ] Health endpoint operational (`/api/health`, `/api/metrics`)
- [ ] Ports 9090, 9093 open in firewall
- [ ] systemd services created (Sortie 3)

## Components

### Prometheus

**Purpose:** Time-series database that collects metrics

- Scrapes `/api/metrics` endpoint every 15 seconds
- Stores metrics history
- Evaluates alerting rules
- Provides query interface (PromQL)
- Web UI at port 9090

### Alertmanager

**Purpose:** Handles alerts from Prometheus

- Receives alerts from Prometheus
- Deduplicates and groups alerts
- Routes to appropriate destinations
- Manages silences
- Web UI at port 9093

## Installation

### Step 1: Install Prometheus (Both Servers)

```bash
# SSH to server (test or prod)
ssh rosey@SERVER_IP

# Download Prometheus
cd /tmp
wget https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz

# Extract
tar xvfz prometheus-2.48.0.linux-amd64.tar.gz
cd prometheus-2.48.0.linux-amd64

# Install binaries
sudo cp prometheus /usr/local/bin/
sudo cp promtool /usr/local/bin/

# Verify
prometheus --version
# Should show: prometheus, version 2.48.0

# Create data directory
sudo mkdir -p /opt/rosey-bot/monitoring/data
sudo chown -R rosey:rosey /opt/rosey-bot/monitoring

# Cleanup
cd ~
rm -rf /tmp/prometheus-*
```

### Step 2: Install Alertmanager (Both Servers)

```bash
# Download Alertmanager
cd /tmp
wget https://github.com/prometheus/alertmanager/releases/download/v0.26.0/alertmanager-0.26.0.linux-amd64.tar.gz

# Extract
tar xvfz alertmanager-0.26.0.linux-amd64.tar.gz
cd alertmanager-0.26.0.linux-amd64

# Install binary
sudo cp alertmanager /usr/local/bin/

# Verify
alertmanager --version
# Should show: alertmanager, version 0.26.0

# Create data directory
sudo mkdir -p /opt/rosey-bot/monitoring/alertmanager-data
sudo chown -R rosey:rosey /opt/rosey-bot/monitoring

# Cleanup
cd ~
rm -rf /tmp/alertmanager-*
```

## Configuration Files (Agent Creates)

### prometheus.yml

File: `monitoring/prometheus.yml`

```yaml
# Prometheus configuration for Rosey Bot

global:
  scrape_interval: 15s  # Scrape every 15 seconds
  evaluation_interval: 15s  # Evaluate rules every 15 seconds
  external_labels:
    cluster: 'rosey-bot'

# Alertmanager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - localhost:9093

# Load alerting rules
rule_files:
  - 'alert_rules.yml'

# Scrape configurations
scrape_configs:
  # Bot health endpoint
  - job_name: 'rosey-bot'
    static_configs:
      - targets: ['localhost:8000']  # Prod: 8000, Test: 8001
        labels:
          env: 'production'  # or 'test'
    metrics_path: '/api/metrics'
```

**Test vs Production:** Only difference is port and label:

- Test: `localhost:8001`, `env: 'test'`
- Production: `localhost:8000`, `env: 'production'`

### alert_rules.yml

File: `monitoring/alert_rules.yml`

```yaml
# Alerting rules for Rosey Bot

groups:
  - name: rosey_bot_alerts
    interval: 15s
    rules:
      # Bot is down
      - alert: BotDown
        expr: bot_connected == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Rosey bot is disconnected"
          description: "Bot has been disconnected for more than 1 minute. Channel: {{ $labels.instance }}"
      
      # Bot is restarting frequently
      - alert: BotRestarting
        expr: rate(bot_uptime_seconds[5m]) < 0
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Rosey bot is restarting"
          description: "Bot uptime is decreasing, indicating restarts. Check logs."
      
      # High error rate
      - alert: HighErrorRate
        expr: rate(bot_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in Rosey bot"
          description: "Bot is experiencing {{ $value }} errors per second."
      
      # Very high error rate
      - alert: CriticalErrorRate
        expr: rate(bot_errors_total[5m]) > 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Critical error rate in Rosey bot"
          description: "Bot is experiencing {{ $value }} errors per second. Immediate attention required."
      
      # No users in channel (unusual)
      - alert: ChannelEmpty
        expr: bot_users == 0
        for: 10m
        labels:
          severity: info
        annotations:
          summary: "Rosey bot channel is empty"
          description: "No users detected in channel for 10 minutes. Is this expected?"
```

### alertmanager.yml

File: `monitoring/alertmanager.yml`

```yaml
# Alertmanager configuration for Rosey Bot

global:
  # Default notification settings
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'your-email@gmail.com'
  smtp_auth_username: 'your-email@gmail.com'
  smtp_auth_password: 'your-app-password'
  smtp_require_tls: true

# Route configuration
route:
  # Default receiver for all alerts
  receiver: 'email-default'
  
  # Group alerts by these labels
  group_by: ['alertname', 'cluster', 'env']
  
  # Wait time before sending first notification
  group_wait: 10s
  
  # Wait time before sending about new alerts in existing group
  group_interval: 10s
  
  # Wait time before resending notification for firing alert
  repeat_interval: 3h
  
  # Route specific alerts differently
  routes:
    # Critical alerts go to multiple channels
    - match:
        severity: critical
      receiver: 'email-critical'
      continue: true
    
    # Info alerts only during business hours
    - match:
        severity: info
      receiver: 'email-info'

# Receivers (notification destinations)
receivers:
  # Default email
  - name: 'email-default'
    email_configs:
      - to: 'your-email@gmail.com'
        headers:
          Subject: '[Rosey Bot] {{ .GroupLabels.alertname }}'
  
  # Critical alerts (could add Slack, PagerDuty, etc.)
  - name: 'email-critical'
    email_configs:
      - to: 'your-email@gmail.com'
        headers:
          Subject: '🚨 [CRITICAL] Rosey Bot: {{ .GroupLabels.alertname }}'
  
  # Info alerts
  - name: 'email-info'
    email_configs:
      - to: 'your-email@gmail.com'
        headers:
          Subject: 'ℹ️ [INFO] Rosey Bot: {{ .GroupLabels.alertname }}'

# Inhibition rules (suppress alerts based on other alerts)
inhibit_rules:
  # If bot is down, suppress other alerts
  - source_match:
      alertname: 'BotDown'
    target_match_re:
      alertname: '.*'
    equal: ['cluster', 'env']
```

**Email configuration notes:**

- Replace `your-email@gmail.com` with your email
- Use Gmail app password (not regular password)
- Can add Slack, Discord, webhooks later

## Deployment Steps

### Step 3: Deploy Configuration Files

```bash
# On your local machine, after agent creates configs
cd d:\Devel\Rosey-Robot

# Commit monitoring configs
git add monitoring/
git commit -m "feat: Add Prometheus and Alertmanager configuration"
git push origin main

# SSH to test server
ssh rosey@TEST_IP

# Pull latest code
cd /opt/rosey-bot
git pull origin main

# Verify configs
ls -la monitoring/
# Should see: prometheus.yml, alert_rules.yml, alertmanager.yml
```

### Step 4: Install systemd Services

```bash
# On server (test or prod)

# Copy service files (created in Sortie 3)
sudo cp /opt/rosey-bot/systemd/prometheus.service /etc/systemd/system/
sudo cp /opt/rosey-bot/systemd/alertmanager.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable prometheus
sudo systemctl enable alertmanager

# Start services
sudo systemctl start prometheus
sudo systemctl start alertmanager

# Check status
sudo systemctl status prometheus
sudo systemctl status alertmanager
```

**Expected output:**

```
● prometheus.service - Prometheus Monitoring
   Loaded: loaded (/etc/systemd/system/prometheus.service; enabled)
   Active: active (running) since ...
   ...

● alertmanager.service - Prometheus Alertmanager
   Loaded: loaded (/etc/systemd/system/alertmanager.service; enabled)
   Active: active (running) since ...
   ...
```

### Step 5: Update Firewall

```bash
# Allow Prometheus web UI
sudo ufw allow 9090/tcp

# Allow Alertmanager web UI
sudo ufw allow 9093/tcp

# Reload firewall
sudo ufw reload

# Verify
sudo ufw status | grep 909
```

## Verification

### Check Prometheus

```bash
# From your local machine
curl http://SERVER_IP:9090/-/healthy
# Should return: Prometheus is Healthy.

# Open in browser:
# http://SERVER_IP:9090
```

**In Prometheus UI:**

1. Go to Status → Targets
2. Should see: `rosey-bot (1/1 up)`
3. Go to Graph
4. Query: `bot_connected`
5. Execute
6. Should see: `bot_connected{env="test", instance="localhost:8001", job="rosey-bot"} 1`

### Check Alertmanager

```bash
# From your local machine
curl http://SERVER_IP:9093/-/healthy
# Should return: OK

# Open in browser:
# http://SERVER_IP:9093
```

**In Alertmanager UI:**

1. Should see "No alerts" (if bot is healthy)
2. Check Status page
3. Should show Prometheus as alert source

### Test Alert Notification

Trigger a test alert:

```bash
# SSH to server
ssh rosey@SERVER_IP

# Stop bot to trigger alert
sudo systemctl stop rosey-bot

# Wait 1-2 minutes
# Check Prometheus: http://SERVER_IP:9090/alerts
# Should see: BotDown alert firing

# Check Alertmanager: http://SERVER_IP:9093
# Should see: BotDown alert

# Check your email
# Should receive: [Rosey Bot] BotDown alert

# Restart bot
sudo systemctl start rosey-bot

# Wait 1-2 minutes
# Alert should resolve
# Should receive: [Rosey Bot] BotDown resolved email
```

## Monitoring Queries (PromQL)

Useful queries in Prometheus:

```promql
# Bot connection status
bot_connected

# Bot uptime in hours
bot_uptime_seconds / 3600

# Error rate (errors per second)
rate(bot_errors_total[5m])

# Request rate (requests per second)
rate(bot_requests_total[5m])

# User count
bot_users

# 95th percentile of users over last hour
quantile_over_time(0.95, bot_users[1h])
```

## Dashboards (Future Enhancement)

For Sortie 7, we'll create web dashboards. For now, use Prometheus UI.

## Validation Checklist

Monitoring stack complete when:

- [ ] Prometheus installed on both servers
- [ ] Alertmanager installed on both servers
- [ ] Configuration files deployed
- [ ] systemd services running
- [ ] Prometheus scraping bot metrics
- [ ] Prometheus UI accessible (port 9090)
- [ ] Alertmanager UI accessible (port 9093)
- [ ] Test alert triggered and received
- [ ] Alert resolved notification received
- [ ] Firewall configured
- [ ] Services enabled for boot startup

## Common Issues

### Issue: Prometheus Not Scraping

**Symptoms:** Targets show "DOWN" in Prometheus

**Debug:**

```bash
# Check Prometheus logs
sudo journalctl -u prometheus -n 50

# Verify bot health endpoint
curl http://localhost:8000/api/metrics
```

**Fix:** Check bot is running and health endpoint accessible.

### Issue: No Email Alerts

**Symptoms:** Alerts firing but no emails received

**Debug:**

```bash
# Check Alertmanager logs
sudo journalctl -u alertmanager -n 50

# Test email config
amtool config routes test --config.file=/opt/rosey-bot/monitoring/alertmanager.yml
```

**Fix:** Verify SMTP settings, app password correct.

### Issue: Too Many Alerts

**Symptoms:** Alert spam, constant notifications

**Fix:** Adjust alert rules:

- Increase `for:` duration
- Adjust thresholds
- Add inhibition rules

## Security

**Prometheus and Alertmanager UIs are UNPROTECTED by default:**

- Only accessible from your IP (if firewall configured)
- Or use SSH tunnel for access:
  ```bash
  ssh -L 9090:localhost:9090 rosey@SERVER_IP
  # Then access: http://localhost:9090
  ```

**For production, consider:**

- Nginx reverse proxy with authentication
- VPN access only
- Cloud-based monitoring (Grafana Cloud, Datadog)

## Success Criteria

Sortie 6 complete when:

1. Monitoring stack deployed on both servers
2. Metrics being collected
3. Alerts configured and tested
4. Email notifications working
5. Dashboards accessible
6. Documentation updated
7. Team trained on using tools

## Time Estimate

- **Install binaries**: 30 minutes per server (1 hour total)
- **Deploy configs**: 30 minutes
- **Install services**: 20 minutes per server (40 minutes total)
- **Verification**: 30 minutes
- **Testing**: 30 minutes
- **Total**: ~3 hours

Ready to deploy monitoring! 📊
