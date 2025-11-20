# Critical Dependency: Fix WebSocket Timeout Configuration

**Status**: Planning  
**Owner**: Agent  
**Estimated Effort**: 30 minutes  
**Related Issue**: #14  
**Priority**: CRITICAL (causing connection failures)  
**Depends On**: None (can fix immediately)

## Overview

Fix critically incorrect WebSocket timeout value in configuration files. Current 0.1 second timeout is causing frequent disconnections and connection failures.

**Why critical:** Bot can't stay connected with 0.1s timeout. This is breaking production operations right now.

## Current Problem

**config-test.json and config-prod.json:**

```json
{
  "socket_io_config": {
    "reconnection": true,
    "reconnectionDelay": 1000,
    "timeout": 0.1
  }
}
```

**Problem:** `timeout: 0.1` means 0.1 seconds (100ms)

**Impact:**

- WebSocket connection times out almost immediately
- Any network latency > 100ms causes disconnection
- Bot constantly reconnecting
- Missed messages
- Unreliable operation
- Production channel sees bot joining/leaving repeatedly

**Real-world latency:**

- Local network: ~10-50ms (works)
- Internet: ~50-200ms (fails often with 100ms timeout)
- Poor connection: 200-500ms+ (always fails)

## Root Cause

Incorrect timeout value:

- **Should be:** 3.0 seconds (3000ms) - reasonable for internet connections
- **Currently:** 0.1 seconds (100ms) - too aggressive

This was likely a typo or misunderstanding of units. Most Socket.IO implementations use milliseconds, but our library appears to use seconds.

## Target State

**Corrected configuration:**

```json
{
  "socket_io_config": {
    "reconnection": true,
    "reconnectionDelay": 1000,
    "timeout": 3.0
  }
}
```

**Benefits:**

- Reliable connections over internet
- Tolerates normal network latency
- Fewer reconnection cycles
- More stable bot operation
- Better user experience in channel

## Technical Details

### Timeout Explained

The `timeout` parameter controls how long the WebSocket waits for:

- Initial connection handshake
- Pong responses to ping messages
- Response to connection upgrade requests

**Too short (0.1s):**

- Fails on any network delay
- Constant reconnections
- Looks like network issues even when network is fine

**Too long (30s+):**

- Slow to detect real disconnections
- Bot appears connected when actually dead
- Delays reconnection when needed

**Just right (3s):**

- Tolerates normal latency
- Detects real problems quickly
- Balance of reliability and responsiveness

### Configuration Locations

Need to update:

1. **config-test.json** - Test server configuration
2. **config-prod.json** - Production server configuration

Both files have the same issue.

## Implementation

### Simple Fix

Update two files:

**File 1: config-test.json**

Change:

```json
"timeout": 0.1
```

To:

```json
"timeout": 3.0
```

**File 2: config-prod.json**

Same change:

```json
"timeout": 0.1
```

To:

```json
"timeout": 3.0
```

That's it! No code changes needed.

## Testing

### Verify Fix Locally

```bash
# Start bot with fixed config
python -m lib

# Should connect and stay connected
# Watch for these log messages:
# ✅ "Connected to CyTube"
# ✅ No repeated "Reconnecting..." messages
# ✅ No "Connection timeout" errors
```

### Test Network Resilience

```bash
# Simulate poor network (Linux/Mac)
sudo tc qdisc add dev eth0 root netem delay 200ms

# Or on Windows (requires admin PowerShell)
# Add 200ms latency to network adapter

# Bot should still connect and stay connected
# With 0.1s timeout: would fail
# With 3.0s timeout: works fine
```

### Monitor Connection Stability

```bash
# Watch logs for 5 minutes
python -m lib | tee bot.log

# Count reconnections
grep -c "Reconnecting" bot.log

# Should be: 0 (or very few if real network issues)
# Before fix: many (dozens per minute)
```

## Before/After Comparison

### Before Fix (timeout: 0.1)

```
[12:34:01] Connecting to CyTube...
[12:34:01] Connection timeout
[12:34:02] Reconnecting...
[12:34:02] Connected to CyTube
[12:34:03] Connection timeout
[12:34:04] Reconnecting...
[12:34:04] Connected to CyTube
[12:34:05] Connection timeout
...
```

**Reliability:** ~10% (constant failures)

### After Fix (timeout: 3.0)

```
[12:34:01] Connecting to CyTube...
[12:34:02] Connected to CyTube
[12:34:02] Joined channel #programming
[12:34:02] Bot ready
...
(stays connected)
```

**Reliability:** ~99% (only disconnects on real issues)

## Validation Checklist

After fix:

- [ ] `config-test.json` updated: `timeout: 3.0`
- [ ] `config-prod.json` updated: `timeout: 3.0`
- [ ] Local test: bot connects successfully
- [ ] Local test: bot stays connected for 5+ minutes
- [ ] No "Connection timeout" errors in logs
- [ ] No repeated reconnection cycles
- [ ] Changes committed to repository

## Impact Analysis

### Before Deployment

- [ ] **Test server:** Update config-test.json, push to main
- [ ] **GitHub Actions:** Deploys to test server automatically
- [ ] **Verify:** Test bot connects reliably

### After Deployment

**Expected improvements:**

- Stable connections on both test and production
- Fewer reconnection messages in logs
- More reliable message handling
- Better channel presence (no join/leave spam)
- Reduced server load from constant reconnections

### Monitoring

Watch these metrics after deployment:

```bash
# On test/prod server
sudo journalctl -u rosey-bot -f | grep -E "timeout|Reconnect|Connected"

# Should see:
# - One "Connected" message at startup
# - No "timeout" messages
# - No "Reconnecting" messages (except during actual network issues)
```

## Why This is Critical

This bug is **blocking production operations:**

1. **User Experience:** Bot appears unstable, joins/leaves constantly
2. **Reliability:** Can't process commands reliably
3. **Monitoring:** False alerts from constant disconnections
4. **Data Loss:** Missed messages during reconnection cycles
5. **Server Load:** Excessive reconnection attempts

**Must fix before production deployment.**

## Time Estimate

- **Make changes:** 5 minutes (edit 2 config files)
- **Test locally:** 10 minutes (verify connection stable)
- **Commit and push:** 5 minutes
- **Verify on test server:** 10 minutes
- **Total:** ~30 minutes

## Success Criteria

This critical bug fix is complete when:

1. Both config files updated with `timeout: 3.0`
2. Local testing shows stable connections
3. No timeout errors in logs during 5-minute test
4. Changes committed and pushed
5. Test server deployment successful
6. Test bot connects and stays connected
7. Production deployment successful
8. Production bot stable for 24 hours

## Next Steps

1. **Fix immediately** (this sortie)
2. **Test locally** (verify improvement)
3. **Push to main** (triggers test deployment)
4. **Monitor test server** (watch for stability)
5. **Deploy to production** (Sortie 5)

This is a quick win that dramatically improves bot stability! 🚀

## Additional Notes

### Why Was This Set to 0.1?

Possible reasons:

1. **Typo:** Meant to type `1.0` or `10.0`
2. **Unit confusion:** Thought it was milliseconds (100ms), not seconds
3. **Copy-paste error:** From example with different units
4. **Testing artifact:** Set low for testing, forgot to change back

### Preventing Similar Issues

After fixing:

- [ ] Add comment in config files explaining timeout units
- [ ] Add validation in bot code (warn if timeout < 1.0)
- [ ] Document reasonable timeout ranges in README
- [ ] Add to testing checklist: "Verify connection stable for 5 minutes"

### Future Improvements (Later)

- Make timeout configurable via environment variable
- Add connection health monitoring to dashboard
- Alert if reconnection rate > threshold
- Auto-adjust timeout based on measured latency

**But for now:** Just fix the config! 🔧
