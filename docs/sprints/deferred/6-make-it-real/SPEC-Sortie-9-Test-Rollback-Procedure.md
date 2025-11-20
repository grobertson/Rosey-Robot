# Sortie 9: Test Rollback Procedure

**Status**: Planning  
**Owner**: User (execution), Agent (support)  
**Estimated Effort**: 1-2 hours  
**Related Issue**: #27  
**Depends On**: Sorties 4-5 (deployments working)

## Overview

Test the rollback procedure before we need it in an emergency. Practice recovering from a bad deployment so we're confident we can fix production issues quickly.

**Why test rollback?**

- Verify backup procedure works
- Practice under controlled conditions
- Identify gaps in process
- Build team confidence
- Reduce MTTR (Mean Time To Recovery)

## Rollback Scenarios

### Scenario 1: Bad Code Deployment

**Simulated problem:** New code has bug that prevents bot from starting

**Test on:** Test server first, then production (if needed)

**Steps:**

#### 1. Create "Bad" Deployment

```bash
# On your local machine
cd d:\Devel\Rosey-Robot

# Create test branch with intentional bug
git checkout -b test/broken-deployment

# Break something critical
# Edit lib/bot.py - add syntax error
echo "this will cause error" >> lib/bot.py

# Commit bad code
git add lib/bot.py
git commit -m "test: Intentional breakage for rollback test"

# Push to trigger deployment
git push origin test/broken-deployment

# Merge to main (DON'T do this in real life!)
git checkout main
git merge test/broken-deployment
git push origin main
```

**Expected result:** Test deployment fails, bot won't start

#### 2. Detect Failure

```bash
# Watch deployment
# GitHub Actions should show: ❌ Deployment failed

# Or check health endpoint
curl http://TEST_IP:8001/api/health
# Should timeout or show unhealthy

# Check service status
ssh rosey@TEST_IP "sudo systemctl status rosey-bot"
# Should show: failed
```

#### 3. Execute Rollback

**Method A: Restore from Backup** (Fastest)

```bash
# SSH to test server
ssh rosey@TEST_IP

# List backups
ls -la /opt/ | grep rosey-bot-backup

# Find backup from before bad deployment
# Format: rosey-bot-backup-YYYYMMDD-HHMMSS
BACKUP="/opt/rosey-bot-backup-20240115-143000"  # Example

# Stop service
sudo systemctl stop rosey-bot

# Move bad deployment aside
sudo mv /opt/rosey-bot /opt/rosey-bot-failed-$(date +%Y%m%d-%H%M%S)

# Restore backup
sudo cp -r $BACKUP /opt/rosey-bot
sudo chown -R rosey:rosey /opt/rosey-bot

# Start service
sudo systemctl start rosey-bot

# Verify
curl http://localhost:8001/api/health | jq
```

**Expected time:** 2-3 minutes

**Method B: Redeploy Previous Version** (via GitHub Actions)

```bash
# Find previous good commit
git log --oneline -10

# Example: commit abc123f was working
# Trigger deployment of that commit

# Go to: GitHub Actions → Test Deployment → Run workflow
# Branch: main
# Commit: abc123f

# Or revert the bad commit
git checkout main
git revert HEAD
git push origin main
```

**Expected time:** 5-10 minutes (includes deployment)

**Method C: Manual Git Rollback** (On server)

```bash
# SSH to test server
ssh rosey@TEST_IP

cd /opt/rosey-bot

# Check current commit
git log --oneline -5

# Reset to previous commit
git reset --hard HEAD~1  # Go back one commit

# Restart service
sudo systemctl restart rosey-bot

# Verify
curl http://localhost:8001/api/health | jq
```

**Expected time:** 1-2 minutes

#### 4. Verify Rollback Success

```bash
# Health endpoint should respond
curl http://TEST_IP:8001/api/health | jq '.status'
# Expected: "healthy"

# Bot should be in channel
# Check CyTube channel user list

# Logs should show successful startup
ssh rosey@TEST_IP "sudo journalctl -u rosey-bot -n 50"
# Expected: "Connected to CyTube", no errors

# Dashboard should show online
# Open: http://TEST_IP:5000
```

#### 5. Clean Up Test

```bash
# Remove bad code from repository
git checkout main
git reset --hard HEAD~1  # Remove bad commit
git push origin main --force

# Delete test branch
git branch -D test/broken-deployment
git push origin --delete test/broken-deployment
```

### Scenario 2: Database Corruption

**Simulated problem:** Bot database file corrupted

**Steps:**

#### 1. Simulate Corruption

```bash
# SSH to test server
ssh rosey@TEST_IP

# Corrupt database (if bot uses one)
echo "garbage data" >> /opt/rosey-bot/data/bot.db

# Restart bot
sudo systemctl restart rosey-bot

# Bot should fail to start
sudo systemctl status rosey-bot
# Expected: failed
```

#### 2. Rollback Database

```bash
# Restore database from backup
# (Assuming backups include data directory)
BACKUP="/opt/rosey-bot-backup-20240115-143000"

# Stop bot
sudo systemctl stop rosey-bot

# Restore database
sudo cp $BACKUP/data/bot.db /opt/rosey-bot/data/bot.db
sudo chown rosey:rosey /opt/rosey-bot/data/bot.db

# Start bot
sudo systemctl start rosey-bot

# Verify
curl http://localhost:8001/api/health | jq
```

### Scenario 3: Configuration Error

**Simulated problem:** Bad config pushed to production

**Steps:**

#### 1. Simulate Bad Config

```bash
# Edit config-test.json with invalid JSON
ssh rosey@TEST_IP
echo "invalid json {" >> /opt/rosey-bot/config-test.json

# Restart bot
sudo systemctl restart rosey-bot

# Should fail
sudo systemctl status rosey-bot
```

#### 2. Rollback Config

```bash
# Restore from backup
BACKUP="/opt/rosey-bot-backup-20240115-143000"
sudo cp $BACKUP/config-test.json /opt/rosey-bot/config-test.json

# Or manually fix
sudo nano /opt/rosey-bot/config-test.json
# Remove bad line, save

# Restart
sudo systemctl restart rosey-bot

# Verify
curl http://localhost:8001/api/health | jq
```

## Rollback Time Goals

**Target Recovery Times:**

- **Method A (Backup restore):** < 3 minutes
- **Method B (Redeploy):** < 10 minutes
- **Method C (Git rollback):** < 2 minutes

**Measure actual times during test:**

```bash
# Start timer
START=$(date +%s)

# Execute rollback
# ... rollback commands ...

# End timer
END=$(date +%s)
DURATION=$((END - START))
echo "Rollback took: $DURATION seconds"
```

## Rollback Validation Checklist

After each rollback test:

- [ ] Bot service running: `systemctl status rosey-bot`
- [ ] Health endpoint healthy: `curl .../api/health`
- [ ] Bot connected to CyTube channel
- [ ] No errors in logs: `journalctl -u rosey-bot -n 50`
- [ ] Dashboard shows online status
- [ ] Bot responding to commands (if applicable)
- [ ] Prometheus metrics being collected
- [ ] Time to recovery < target

## Rollback Runbook

Document procedure for quick reference:

```markdown
# EMERGENCY ROLLBACK PROCEDURE

## Quick Assessment

1. Verify deployment failed:
   - Health endpoint: `curl http://SERVER:PORT/api/health`
   - Service status: `ssh server "sudo systemctl status rosey-bot"`
   
2. Check recent changes:
   - GitHub: Last merged PR
   - Server logs: `journalctl -u rosey-bot -n 100`

## Option 1: Restore from Backup (FASTEST - 2-3 min)

ssh rosey@SERVER
sudo systemctl stop rosey-bot
sudo mv /opt/rosey-bot /opt/rosey-bot-failed-$(date +%Y%m%d)
sudo cp -r /opt/rosey-bot-backup-LATEST /opt/rosey-bot
sudo chown -R rosey:rosey /opt/rosey-bot
sudo systemctl start rosey-bot
curl http://localhost:8001/api/health | jq

## Option 2: Git Revert (SAFE - 5-10 min)

git log --oneline -10
git revert <bad-commit>
git push origin main
# Wait for CI/CD deployment

## Option 3: Manual Git Rollback (FAST - 1-2 min)

ssh rosey@SERVER
cd /opt/rosey-bot
git reset --hard <good-commit>
sudo systemctl restart rosey-bot
curl http://localhost:8001/api/health | jq

## Verify Recovery

✅ Health endpoint: healthy
✅ Bot in channel
✅ No errors in logs
✅ Metrics collecting

## Post-Rollback

1. Alert team
2. Create incident report
3. Schedule postmortem
4. Fix underlying issue
```

Save as: `docs/ROLLBACK-RUNBOOK.md`

## Production Rollback Test (Optional)

**⚠️ WARNING:** Only do this during maintenance window with user notification.

**Steps:**

1. Announce maintenance: "Testing deployment procedures, 5-minute downtime expected"
2. Create backup: `sudo cp -r /opt/rosey-bot /opt/rosey-bot-backup-test`
3. Execute rollback test (using backup method)
4. Verify recovery
5. Announce completion: "Testing complete, bot operational"

**Alternative:** Practice on test server only, consider production rollback procedure documented and ready.

## Validation Checklist

Sortie 9 complete when:

- [ ] Rollback tested on test server
- [ ] All three rollback methods tested
- [ ] Recovery times measured and acceptable
- [ ] Rollback runbook created
- [ ] Team trained on procedure
- [ ] Backups verified (can actually restore from them)
- [ ] Confidence in emergency recovery process
- [ ] Production rollback procedure documented

## Lessons Learned

Document insights from testing:

```markdown
## Rollback Test Results

### What Worked Well:
- Backup restore was fastest (2m 15s)
- systemctl commands easy to remember
- Health endpoint great for verification

### What Needs Improvement:
- Backup names hard to identify (add timestamp to filename)
- No automated backup cleanup (old backups pile up)
- Git rollback confusing (need better tagging)

### Action Items:
1. Improve backup naming: include version tag
2. Add backup cleanup script (keep last 10)
3. Tag all production deployments
4. Add rollback button to dashboard
```

## Common Issues

### Issue: Backup Directory Not Found

**Cause:** Backup not created during deployment

**Fix:** Verify prod workflow includes backup step:

```yaml
- name: Backup current production
  run: |
    ssh ... "sudo cp -r /opt/rosey-bot /opt/rosey-bot-backup-$(date +%Y%m%d-%H%M%S)"
```

### Issue: Permissions Wrong After Restore

**Cause:** Backup owned by root, not rosey

**Fix:**

```bash
sudo chown -R rosey:rosey /opt/rosey-bot
```

### Issue: Rollback Successful But Issues Persist

**Cause:** State not in code/config (cached data, external systems)

**Fix:**

- Clear cache/temp files
- Restart dependent services
- Check external dependencies

## Success Criteria

Sortie 9 complete when:

1. Rollback procedure tested and verified
2. Recovery time < 3 minutes (backup method)
3. All team members know how to rollback
4. Runbook created and accessible
5. Confidence to deploy to production
6. Emergency process documented

## Time Estimate

- **Setup**: 15 minutes
- **Test Scenario 1**: 30 minutes
- **Test Scenario 2**: 20 minutes
- **Test Scenario 3**: 15 minutes
- **Document runbook**: 20 minutes
- **Team training**: 20 minutes
- **Total**: ~2 hours

Rollback tested and ready! 🔄✅
