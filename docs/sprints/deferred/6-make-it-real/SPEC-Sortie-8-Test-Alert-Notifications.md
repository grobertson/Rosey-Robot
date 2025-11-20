# Sortie 8: Test Alert Notifications

**Status**: Planning  
**Owner**: User (testing), Agent (support)  
**Estimated Effort**: 1-2 hours  
**Related Issue**: #26  
**Depends On**: Sortie 6 (Alertmanager configured)

## Overview

Systematically test all alert notification channels to ensure we'll know when something goes wrong. Better to find configuration issues now than during a real incident.

## Test Plan

### Alerts to Test

From `monitoring/alert_rules.yml`:

1. **BotDown** - Critical: Bot disconnected
2. **BotRestarting** - Warning: Frequent restarts
3. **HighErrorRate** - Warning: Elevated errors
4. **CriticalErrorRate** - Critical: Severe error rate
5. **ChannelEmpty** - Info: No users in channel

### Notification Channels to Test

- **Email** (configured in Sortie 6)
- **Slack** (optional, if configured)
- **Webhook** (optional, if configured)

## Test Procedures

### Test 1: BotDown Alert

**Trigger:** Stop the bot

```bash
# SSH to test server
ssh rosey@TEST_IP

# Stop bot
sudo systemctl stop rosey-bot

# Wait 60 seconds (alert fires after 1 minute)
sleep 60
```

**Verify:**

1. **Prometheus Alerts** (`http://TEST_IP:9090/alerts`)
   - Should show: BotDown alert FIRING
   - Status: Red
   
2. **Alertmanager** (`http://TEST_IP:9093`)
   - Should show: BotDown alert
   - Severity: critical
   
3. **Email**
   - Check inbox
   - Subject: `🚨 [CRITICAL] Rosey Bot: BotDown`
   - Body: "Bot has been disconnected for more than 1 minute"
   - Received within 1-2 minutes

**Resolve:**

```bash
# Restart bot
sudo systemctl start rosey-bot

# Wait 60 seconds for alert to clear
sleep 60
```

**Verify Resolution:**

1. **Prometheus**: Alert should be GREEN (resolved)
2. **Alertmanager**: Alert should disappear
3. **Email**: Receive resolution notification

**✅ Pass criteria:**

- Alert fired correctly
- Email received within 2 minutes
- Alert resolved when bot restarted
- Resolution email received

### Test 2: HighErrorRate Alert

**Trigger:** Cause errors in bot

Option A - Disconnect network temporarily:

```bash
# Temporarily break connection
sudo iptables -A OUTPUT -d cytu.be -j DROP

# Wait 5 minutes for errors to accumulate
sleep 300

# Restore connection
sudo iptables -D OUTPUT -d cytu.be -j DROP
```

Option B - Use test endpoint (if implemented):

```bash
# Call error-generating endpoint
curl -X POST http://localhost:8001/api/test/generate-errors?count=50
```

**Verify:**

- Prometheus shows HighErrorRate FIRING
- Email received: `[WARNING] Rosey Bot: HighErrorRate`
- Alert clears after error rate drops

### Test 3: ChannelEmpty Alert

**Trigger:** Ensure channel has no users

**Scenario:** Wait for natural empty channel period, or:

```bash
# Temporarily configure bot to join empty test channel
# Edit config-test.json: "channel": "#empty-test-channel"
sudo systemctl restart rosey-bot

# Wait 10 minutes (alert fires after 10 min)
sleep 600
```

**Verify:**

- Prometheus shows ChannelEmpty FIRING
- Email received: `ℹ️ [INFO] Rosey Bot: ChannelEmpty`
- Different severity styling than critical alerts

**Restore:**

```bash
# Restore original channel
# Edit config-test.json back to original channel
sudo systemctl restart rosey-bot
```

### Test 4: Alert Grouping

**Purpose:** Verify multiple alerts group together

**Trigger:** Stop bot AND cause errors

```bash
# Stop bot
sudo systemctl stop rosey-bot

# This will trigger BotDown
# Plus potentially other alerts
```

**Verify:**

- Alertmanager groups related alerts together
- Single email with multiple alerts (not one per alert)
- Grouped by: alertname, cluster, env

### Test 5: Alert Inhibition

**Purpose:** Verify BotDown suppresses other alerts

**Trigger:** Stop bot (triggers BotDown)

**Expected behavior:**

- BotDown alert fires → Email received
- Other alerts (errors, etc.) are inhibited
- Only receive BotDown email, not alert spam

**Verify:**

```bash
# Check Alertmanager UI
# Go to http://TEST_IP:9093/#/alerts

# Should see:
# - BotDown: ACTIVE
# - Other alerts: INHIBITED (suppressed)
```

### Test 6: Alert Silencing

**Purpose:** Test manual alert silencing

**Scenario:** Testing or maintenance - don't want alerts

**Create silence:**

1. Go to Alertmanager UI: `http://TEST_IP:9093/#/silences`
2. Click "New Silence"
3. Fill form:
   - Matchers: `alertname=BotDown`
   - Duration: 1 hour
   - Creator: your-email
   - Comment: "Testing - ignore BotDown alerts"
4. Click "Create"

**Test:**

```bash
# Stop bot (would normally alert)
sudo systemctl stop rosey-bot

# Wait 2 minutes
sleep 120
```

**Verify:**

- No email received (alert silenced)
- Prometheus still shows alert FIRING
- Alertmanager shows alert but marked SILENCED

**Clean up:**

1. Go to Alertmanager silences
2. Expire silence (click "Expire" button)
3. Restart bot: `sudo systemctl start rosey-bot`

## Notification Channels Setup (Optional)

### Slack Integration

If you want Slack notifications:

**Step 1: Create Slack Webhook**

1. Go to: https://api.slack.com/messaging/webhooks
2. Create new webhook for your workspace
3. Copy webhook URL

**Step 2: Update alertmanager.yml**

```yaml
receivers:
  - name: 'slack-critical'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/YOUR/WEBHOOK/URL'
        channel: '#alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

routes:
  - match:
      severity: critical
    receiver: 'slack-critical'
    continue: true  # Also send to email
```

**Step 3: Restart Alertmanager**

```bash
sudo systemctl restart alertmanager
```

**Step 4: Test**

Stop bot, verify Slack message received.

### Webhook Integration

For custom integrations (Discord, PagerDuty, etc.):

```yaml
receivers:
  - name: 'webhook-critical'
    webhook_configs:
      - url: 'https://your-webhook-endpoint.com/alert'
        send_resolved: true
```

## Validation Checklist

Complete when:

- [ ] BotDown alert tested (firing and resolving)
- [ ] Email notifications received for all severities
- [ ] Alert grouping verified (multiple alerts → one email)
- [ ] Alert inhibition working (BotDown suppresses others)
- [ ] Alert silencing tested (can manually suppress)
- [ ] Resolution notifications received
- [ ] Slack/webhook tested (if configured)
- [ ] All alerts documented with trigger conditions
- [ ] Team knows how to create silences

## Test Results Documentation

Create test log:

```markdown
# Alert Testing Results

## Date: YYYY-MM-DD
## Server: Test / Production
## Tester: Your Name

### Test 1: BotDown Alert
- ✅ Alert fired after 1 minute
- ✅ Email received: 1m 45s
- ✅ Correct subject and body
- ✅ Resolution email received

### Test 2: HighErrorRate
- ✅ Alert fired after 5 minutes
- ✅ Warning severity correct
- ✅ Alert cleared after resolution

... (continue for all tests)

### Issues Found:
1. None / [describe issues]

### Recommendations:
1. Alert thresholds appropriate
2. Notification timing acceptable
```

## Common Issues

### Issue: No Email Received

**Debug:**

```bash
# Check Alertmanager logs
sudo journalctl -u alertmanager -n 50 | grep -i email

# Common causes:
# 1. SMTP settings wrong
# 2. App password incorrect
# 3. Gmail blocking "less secure apps"
# 4. Firewall blocking SMTP port (587)
```

**Fix:**

```bash
# Test SMTP manually
curl smtp://smtp.gmail.com:587 --mail-from 'you@gmail.com' --mail-rcpt 'you@gmail.com' --user 'you@gmail.com:app-password' -T /tmp/test.txt

# If fails, check:
# - Gmail → Security → App passwords
# - Ensure 2FA enabled
# - Create new app password
```

### Issue: Too Many Emails

**Symptoms:** Email spam, duplicate alerts

**Fix:** Adjust `alertmanager.yml`:

```yaml
route:
  group_wait: 30s        # Wait longer before first alert
  group_interval: 5m     # Group alerts over 5 minutes
  repeat_interval: 12h   # Don't repeat for 12 hours
```

### Issue: Alerts Not Grouping

**Symptoms:** Separate email for each alert

**Fix:** Check `group_by` labels:

```yaml
route:
  group_by: ['alertname', 'cluster', 'env', 'severity']
```

## Success Criteria

Sortie 8 complete when:

1. All alerts tested on test server
2. Email notifications working reliably
3. Alert lifecycle verified (firing → resolving)
4. Grouping and inhibition working
5. Silencing procedure documented
6. Test results documented
7. Team confident in alerting system
8. Optional channels tested (Slack, webhook)
9. Ready to apply to production

## Next Steps

After successful test:

1. Apply same alerts to production (Sortie 6 already did this)
2. Monitor production alerts for false positives
3. Tune thresholds based on real usage
4. Add more alerts as needed

## Time Estimate

- **Setup and preparation**: 15 minutes
- **Test each alert**: 15 minutes × 5 = 1.25 hours
- **Test optional channels**: 30 minutes
- **Documentation**: 15 minutes
- **Total**: ~2 hours

Alerts tested and working! 🔔✅
