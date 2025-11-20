# Sortie 10: Validate Production Traffic

**Status**: Planning  
**Owner**: User (monitoring), Agent (analysis)  
**Estimated Effort**: 24 hours (mostly passive monitoring)  
**Related Issue**: #28  
**Depends On**: Sorties 4-5 (production deployment)

## Overview

Monitor production bot for 24 hours to validate stability, performance, and reliability under real traffic. This is our "burn-in" period before declaring Sprint 6 complete.

**Goal:** Confidence that bot can handle production workload reliably.

## Monitoring Plan

### What to Monitor

**Health Metrics:**

- Connection status (should stay connected)
- Error rate (should be < 0.1 errors/min)
- Restart count (should be 0 unplanned restarts)
- Memory usage (should be stable, no leaks)
- CPU usage (should be low < 20%)

**Performance Metrics:**

- Request handling time
- Message processing latency
- User count fluctuations
- Health endpoint response time

**Reliability Metrics:**

- Uptime percentage (target: > 99.9%)
- Alert count (should be 0 or only expected alerts)
- Deployment success rate
- Backup creation success

## Monitoring Schedule

### Hour 0-1: Initial Deployment

**Tasks:**

- Deploy to production (if not already done)
- Verify health endpoint responds
- Confirm bot joined channel
- Check initial metrics in Prometheus

**Checkpoints:**

```bash
# Initial health check
curl http://PROD_IP:8000/api/health | jq

# Expected:
{
  "status": "healthy",
  "connected": true,
  "channel": "#production-channel",
  "uptime_seconds": 30,
  "version": "v1.0.0",
  "user_count": 42,
  "requests_handled": 0,
  "error_count": 0
}
```

### Hour 1-4: Active Monitoring

**Tasks:**

- Check health every 15 minutes
- Watch for alerts
- Monitor channel activity
- Check logs for warnings

**Automated check script:**

```bash
#!/bin/bash
# check-production.sh

PROD_HOST="YOUR_PROD_IP"

echo "=== Production Health Check ==="
echo "Time: $(date)"

# Health endpoint
echo "Health endpoint:"
curl -s http://$PROD_HOST:8000/api/health | jq -r '"Status: \(.status), Connected: \(.connected), Errors: \(.error_count)"'

# Service status
echo "Service status:"
ssh rosey@$PROD_HOST "sudo systemctl is-active rosey-bot"

# Recent errors
echo "Recent errors:"
ssh rosey@$PROD_HOST "sudo journalctl -u rosey-bot --since '15 minutes ago' | grep -i error | wc -l"

echo ""
```

**Run every 15 minutes:**

```bash
# On your machine
while true; do
    ./check-production.sh
    sleep 900  # 15 minutes
done
```

### Hour 4-12: Periodic Checks

**Reduce to hourly checks:**

- Bot still connected
- Error count stable
- No unexpected alerts
- Memory usage stable

**Hourly check:**

```bash
# Quick status
curl -s http://PROD_IP:8000/api/health | jq '.status, .error_count, .uptime_seconds'
```

### Hour 12-24: Passive Monitoring

**Monitor via:**

- Dashboard: `http://PROD_IP:5000`
- Prometheus: `http://PROD_IP:9090`
- Email alerts (should receive none if healthy)

**Check once every 4 hours.**

## Validation Metrics

### Target Metrics (24 hours)

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Uptime | 100% | > 99.9% | < 99% |
| Error Rate | 0 | < 0.1/min | > 1/min |
| Unplanned Restarts | 0 | 0 | > 0 |
| Alert Count | 0 | < 3 | > 5 |
| Avg Response Time | < 50ms | < 100ms | > 200ms |
| Memory Growth | 0 MB/hr | < 10 MB/hr | > 50 MB/hr |

### Data Collection

**Prometheus queries for 24-hour period:**

```promql
# Uptime percentage
(count_over_time(bot_connected{env="production"}[24h]) - 
 count_over_time((bot_connected{env="production"} == 0)[24h])) / 
 count_over_time(bot_connected{env="production"}[24h]) * 100

# Average error rate
rate(bot_errors_total{env="production"}[24h])

# Total errors
increase(bot_errors_total{env="production"}[24h])

# Restart count
count(changes(bot_uptime_seconds{env="production"}[24h]))

# Memory usage trend (if available)
rate(process_resident_memory_bytes{env="production"}[24h])
```

## Traffic Patterns to Observe

### Peak Hours

**Expected:** More users during evenings (18:00-23:00)

**Monitor:**

- User count: `bot_users`
- Request rate: `rate(bot_requests_total[5m])`
- Response time (if tracked)

**Verify:** Bot handles increased load without errors

### Off-Peak Hours

**Expected:** Fewer users overnight (02:00-07:00)

**Monitor:**

- Bot stays connected (doesn't timeout from inactivity)
- No errors from empty channel
- Resource usage drops proportionally

### Channel Events

**Observe bot behavior during:**

- Channel topic changes
- Admin actions (kicks, bans)
- Media additions/changes
- User joins/leaves

## Issue Detection

### Red Flags

**Immediate action required:**

- Bot disconnected for > 1 minute
- Error rate > 1/minute sustained
- Memory usage growing continuously
- Health endpoint not responding
- Multiple alerts firing

**Action:**

1. Check logs: `ssh prod "sudo journalctl -u rosey-bot -n 100"`
2. Check metrics: Prometheus dashboard
3. Assess severity
4. Execute rollback if needed (Sortie 9)

### Yellow Flags

**Monitor closely:**

- Occasional disconnections (< 5% of time)
- Low error rate (< 0.1/minute)
- Single non-critical alert
- Slow response times

**Action:**

1. Document issue
2. Continue monitoring
3. Create ticket for investigation
4. Plan fix for next sprint

### Performance Issues

**Symptoms:**

- Slow health endpoint (> 200ms)
- High CPU usage (> 50%)
- High memory usage (> 500MB)
- Increasing response times

**Action:**

1. Check for resource leaks
2. Review recent changes
3. Consider optimization
4. Scale up server if needed

## Daily Report Template

Create daily report during validation:

```markdown
# Production Validation Report - Day 1

## Date: YYYY-MM-DD
## Validator: Your Name

### Overall Status: ✅ HEALTHY / ⚠️ ISSUES / ❌ CRITICAL

### Metrics Summary

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Uptime | 99.98% | > 99.9% | ✅ |
| Error Count | 2 | < 0.1/min | ✅ |
| Restarts | 0 | 0 | ✅ |
| Alerts | 0 | < 3 | ✅ |
| Peak Users | 87 | - | ℹ️ |

### Notable Events

- **12:30** - Brief network hiccup, bot reconnected in 5s
- **18:00** - Peak hour, 87 users, no performance degradation
- **23:45** - Daily backup successful

### Issues Encountered

1. **None** / [Describe issues]

### Action Items

1. None / [List actions needed]

### Observations

- Bot performed well under peak load
- No unexpected behavior
- Resource usage stable
- Alert system working (tested manually)

### Recommendation

✅ Continue to Day 2 validation
⚠️ Address issues before proceeding
❌ Rollback and investigate
```

## Checkpoints

### 6-Hour Checkpoint

**Criteria:**

- [ ] Bot connected 100% of time
- [ ] Zero errors
- [ ] No alerts
- [ ] Memory stable
- [ ] Logs clean

**Decision:** Continue monitoring or investigate issues

### 12-Hour Checkpoint

**Criteria:**

- [ ] Uptime > 99.9%
- [ ] Error count < 10 total
- [ ] No critical alerts
- [ ] Performance acceptable
- [ ] One peak period observed

**Decision:** Continue to 24 hours or rollback

### 24-Hour Checkpoint (Final)

**Criteria:**

- [ ] Uptime > 99.9%
- [ ] Error rate acceptable
- [ ] Zero unplanned restarts
- [ ] Passed peak hours
- [ ] Passed off-peak hours
- [ ] All monitoring systems operational
- [ ] Team confident in stability

**Decision:** 

- ✅ **PASS:** Declare Sprint 6 success, move to Sortie 11
- ⚠️ **PARTIAL:** Fix issues, extend monitoring
- ❌ **FAIL:** Rollback, investigate, retry

## User Feedback

**If bot has interactive features:**

- Monitor channel for user complaints
- Ask trusted users for feedback
- Check for unusual behavior reports

**Questions to ask:**

- Is bot responsive?
- Any errors or strange behavior?
- Performance acceptable?
- Any features not working?

## Validation Checklist

Production validation complete when:

- [ ] 24 hours of monitoring complete
- [ ] Uptime target met (> 99.9%)
- [ ] Error rate acceptable
- [ ] No unplanned restarts
- [ ] Peak hours handled successfully
- [ ] Off-peak hours stable
- [ ] All alerts functional (tested)
- [ ] Performance metrics acceptable
- [ ] Memory usage stable (no leaks)
- [ ] User feedback positive (if applicable)
- [ ] Daily reports created
- [ ] Issues documented
- [ ] Team confident in production deployment

## Common Issues

### Issue: Bot Disconnecting Overnight

**Symptoms:** Bot offline during low-traffic hours

**Causes:**

- Network timeout settings
- Idle connection dropped
- Server maintenance

**Fix:**

- Adjust keepalive settings
- Implement connection heartbeat
- Document as known limitation

### Issue: Memory Growing Over Time

**Symptoms:** Slow memory leak

**Fix:**

- Restart bot daily (temporary)
- Investigate memory leak
- Add memory monitoring alert

### Issue: Slower During Peak Hours

**Symptoms:** Response time increases with user count

**Fix:**

- Optimize code
- Add caching
- Scale server resources

## Success Criteria

Sortie 10 complete when:

1. 24 hours of production monitoring complete
2. All validation metrics met
3. No critical issues encountered
4. Performance acceptable under load
5. Team confident in stability
6. Documentation updated with findings
7. Ready for Sprint 6 wrap-up (Sortie 11)

## Time Estimate

- **Active monitoring (first 4 hours)**: 4 hours
- **Periodic checks (hours 4-24)**: 2 hours spread over 20 hours
- **Analysis and reporting**: 1 hour
- **Total elapsed**: 24 hours
- **Total hands-on**: ~7 hours

Production validated! 📈✅
