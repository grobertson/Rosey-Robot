# Sortie 5: First Production Deployment

**Status**: Planning  
**Owner**: Both (User executes with approval, Agent supports)  
**Estimated Effort**: 1-2 hours  
**Related Issue**: #23  
**Depends On**: Sortie 4 (successful test deployment + 24hr stability)

## Overview

Deploy to production! This is the big one - deploying our bot to the real production channel where actual users are.

**Critical difference from test:** Production requires manual approval and has real consequences. We go slow and careful.

## Prerequisites

### Test Environment Validation

**Before deploying to production, test must be:**

- [ ] Stable for 24+ hours (no crashes, reconnects)
- [ ] Health endpoint reliable
- [ ] systemd services working correctly
- [ ] Auto-restart functional
- [ ] Logs clean (no repeated errors)
- [ ] All features working as expected

**If test is unstable:** Fix issues before production deployment!

### Production Server Readiness

- [ ] Production server provisioned (Sortie 1)
- [ ] SSH key installed on production server
- [ ] User `rosey` created with proper permissions
- [ ] `/opt/rosey-bot/` directory exists
- [ ] Firewall configured (ports 22, 8000, 9090, 9093)
- [ ] sudoers configured for service management

### GitHub Configuration

- [ ] GitHub Secrets configured (Sortie 2):
  - `SSH_KEY_PROD`
  - `PROD_SERVER_HOST`
  - `PROD_SERVER_USER`
- [ ] Production environment configured in GitHub (requires approval)

## Pre-Deployment Steps

### Step 1: Verify Test Stability

```bash
# SSH to test server
ssh rosey@TEST_IP

# Check uptime
sudo journalctl -u rosey-bot | head -1  # First log entry
sudo journalctl -u rosey-bot | tail -1  # Latest log entry

# Count errors in last 24 hours
sudo journalctl -u rosey-bot --since "24 hours ago" | grep -i error | wc -l
# Should be 0 or very few

# Check health endpoint
curl http://localhost:8001/api/health | jq '.status'
# Should be: "healthy"

# Exit test server
exit
```

**Proceed only if test is stable.**

### Step 2: Manual Production Server Setup

Do initial setup on production server (one-time):

```bash
# SSH to production server
ssh -i ~/.ssh/rosey_bot_prod_deploy rosey@YOUR_PROD_IP

# Install dependencies (same as test)
sudo apt-get update
sudo apt-get install -y python3-pip git rsync

# Verify directory exists
ls -ld /opt/rosey-bot
# Should show: drwxr-xr-x ... rosey rosey

# Create log directory
sudo mkdir -p /var/log/rosey-bot
sudo chown rosey:rosey /var/log/rosey-bot

# Exit production server
exit
```

### Step 3: Create GitHub Environment

Configure production environment for approval requirement:

1. Go to GitHub: `Settings` → `Environments`
2. Click "New environment"
3. Name: `production`
4. Under "Deployment protection rules":
   - ✅ Check "Required reviewers"
   - Add yourself as reviewer
5. Click "Save protection rules"

This ensures **no deployment happens without your explicit approval.**

### Step 4: Create Production Deployment Tag

Tag the code we want to deploy:

```bash
# On your local machine
cd d:\Devel\Rosey-Robot

# Ensure main is up to date
git checkout main
git pull origin main

# Create deployment tag
git tag -a v1.0.0-prod-1 -m "First production deployment"

# Push tag
git push origin v1.0.0-prod-1
```

## Deployment Process

### Step 5: Trigger Production Deployment

Unlike test (automatic), production requires manual trigger:

1. Go to: https://github.com/YOUR_USER/Rosey-Robot/actions
2. Click "Production Deployment" workflow
3. Click "Run workflow"
4. In the form:
   - Branch: `main`
   - Version/tag: `v1.0.0-prod-1`
5. Click "Run workflow"

**Workflow starts** but **waits for approval.**

### Step 6: Review and Approve Deployment

1. In GitHub Actions, you'll see: `⏸ Waiting for approval`
2. Click "Review deployments"
3. **Review the changes:**
   - What code is being deployed?
   - Are tests passing?
   - Is test environment stable?
   - Is this the right time? (low traffic period?)
4. If everything looks good:
   - Check "production"
   - Click "Approve and deploy"

**Deployment proceeds immediately after approval.**

### Step 7: Monitor Deployment

Watch the workflow carefully:

```
Production Deployment
├── Run tests
│   └── ✅ Tests pass
│
├── Waiting for approval
│   └── ✅ Approved by YOU
│
└── Deploy to production
    ├── Checkout code (tag v1.0.0-prod-1)
    ├── Setup SSH key
    ├── Backup current production
    ├── Deploy code (rsync)
    ├── Restart services
    ├── Verify deployment
    └── ✅ Deployment successful
```

**Watch for:**

- ✅ Backup created successfully
- ✅ rsync completes without errors
- ✅ Services restart cleanly
- ✅ Health endpoint responds "healthy"

### Step 8: Install Production Services

After first deployment, install systemd services (one-time):

```bash
# SSH to production server
ssh -i ~/.ssh/rosey_bot_prod_deploy rosey@YOUR_PROD_IP

# Copy service files
sudo cp /opt/rosey-bot/systemd/rosey-bot.service /etc/systemd/system/
sudo cp /opt/rosey-bot/systemd/rosey-dashboard.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable rosey-bot
sudo systemctl enable rosey-dashboard

# Start services
sudo systemctl start rosey-bot
sudo systemctl start rosey-dashboard

# Check status
sudo systemctl status rosey-bot
sudo systemctl status rosey-dashboard
```

## Verification

### Comprehensive Production Checks

#### 1. Service Status

```bash
# On production server
sudo systemctl status rosey-bot
sudo systemctl status rosey-dashboard

# Both should be "active (running)"
```

#### 2. Health Endpoint

```bash
# From your local machine
curl http://YOUR_PROD_IP:8000/api/health | jq

# Expected:
{
  "status": "healthy",
  "connected": true,
  "channel": "#your-production-channel",
  "uptime_seconds": 30,
  "version": "v1.0.0-prod-1",
  "user_count": 42,
  "requests_handled": 10,
  "error_count": 0
}
```

#### 3. Bot in Production Channel

1. Open production CyTube channel in browser
2. Look for bot in user list
3. Bot should be connected
4. Try a test command (if applicable)

#### 4. Logs

```bash
# On production server
sudo journalctl -u rosey-bot -n 50

# Should see:
# ✅ "Connected to CyTube"
# ✅ "Joined channel #production-channel"
# ✅ "Bot ready"
# ❌ NO errors
# ❌ NO reconnection loops
```

#### 5. Monitor for 1 Hour

Stay connected and watch for issues:

```bash
# Watch logs live
sudo journalctl -u rosey-bot -f

# In another terminal, watch health
watch -n 5 'curl -s http://localhost:8000/api/health | jq'

# Monitor for:
# - Stable connection
# - No errors
# - No unexpected restarts
# - Consistent user_count
```

## Post-Deployment

### Monitoring

For the first 24 hours, check frequently:

**Every 15 minutes (first hour):**
- Health endpoint status
- Bot presence in channel
- Error count

**Every hour (first 24 hours):**
- Service status
- Log for errors
- User complaints/feedback

**Daily (first week):**
- Overall stability
- Error trends
- Performance metrics

### Announce Deployment

Let channel users know (if appropriate):

```
[Rosey] 🤖 Hi everyone! I've just been upgraded to a new version. 
If you notice any issues, please let @your-username know!
```

### Document Deployment

Create deployment record:

```bash
# On your machine
cd d:\Devel\Rosey-Robot

# Create deployment log
echo "Production Deployment $(date)" >> docs/6-make-it-real/DEPLOYMENT-LOG.md
echo "Version: v1.0.0-prod-1" >> docs/6-make-it-real/DEPLOYMENT-LOG.md
echo "Status: Successful" >> docs/6-make-it-real/DEPLOYMENT-LOG.md
echo "Notes: First production deployment" >> docs/6-make-it-real/DEPLOYMENT-LOG.md
echo "" >> docs/6-make-it-real/DEPLOYMENT-LOG.md

git add docs/6-make-it-real/DEPLOYMENT-LOG.md
git commit -m "docs: Record first production deployment"
git push
```

## Rollback Procedure

If deployment fails or causes issues:

### Quick Rollback (Restore from Backup)

```bash
# SSH to production
ssh rosey@PROD_IP

# Stop services
sudo systemctl stop rosey-bot
sudo systemctl stop rosey-dashboard

# List backups
ls -la /opt/ | grep rosey-bot-backup

# Restore latest backup
LATEST_BACKUP=$(ls -t /opt/rosey-bot-backup-* | head -1)
echo "Restoring from: $LATEST_BACKUP"

sudo rm -rf /opt/rosey-bot
sudo mv $LATEST_BACKUP /opt/rosey-bot
sudo chown -R rosey:rosey /opt/rosey-bot

# Restart services
sudo systemctl start rosey-bot
sudo systemctl start rosey-dashboard

# Verify
curl http://localhost:8000/api/health | jq
```

### Redeploy Previous Version

```bash
# From GitHub Actions
# Go to: Production Deployment → Run workflow
# Version: <previous-tag> (e.g., v1.0.0-prod-0)
# Approve deployment
```

### Emergency Manual Rollback

```bash
# If automation fails, manual rollback:
ssh rosey@PROD_IP

# Stop bot
sudo systemctl stop rosey-bot

# Manually restore working code
# (User's responsibility to have backup)

# Restart
sudo systemctl start rosey-bot
```

## Common Issues

### Issue: Deployment Approved But Fails

**Symptoms:** Workflow shows failure after approval

**Debug:**

1. Check workflow logs for error
2. SSH to server and check service status
3. Verify backup exists
4. Attempt rollback

**Common causes:**

- Network issues during deployment
- SSH key expired
- Disk space full
- Permissions changed

### Issue: Bot Connects But Behaves Incorrectly

**Symptoms:** Bot online but not responding or acting strangely

**Debug:**

```bash
# Check logs
sudo journalctl -u rosey-bot -n 100

# Check config
cat /opt/rosey-bot/config-prod.json

# Compare to test config
diff config-prod.json config-test.json
```

**Fix:** Verify config-prod.json has correct channel, credentials, etc.

### Issue: Performance Problems

**Symptoms:** Bot slow to respond or high CPU/memory

**Debug:**

```bash
# Check resource usage
top -u rosey

# Check bot process
ps aux | grep python3

# Check health metrics
curl http://localhost:8000/api/health | jq
```

**Fix:** May need to optimize code or increase server resources.

## Validation Checklist

Production deployment complete when:

- [ ] Deployment workflow succeeded
- [ ] Backup created before deployment
- [ ] Code deployed to `/opt/rosey-bot/`
- [ ] systemd services installed and running
- [ ] Health endpoint responding: `http://PROD_IP:8000/api/health`
- [ ] Health status: `"healthy"`
- [ ] Bot connected to production channel
- [ ] Bot visible to channel users
- [ ] Bot responding to commands (if applicable)
- [ ] Logs show clean operation
- [ ] No errors in first hour
- [ ] Stable for 24 hours
- [ ] Deployment documented

## Success Criteria

Sortie 5 is complete when:

1. Production deployment successful
2. Bot stable in production channel
3. Health monitoring functional
4. Users can interact with bot (if applicable)
5. No critical errors
6. Rollback plan tested
7. Team confident in deployment process
8. Ready for Sortie 6 (monitoring stack)

## Celebration Checklist 🎉

When production deployment succeeds:

- [ ] Bot is LIVE in production! 🚀🎉
- [ ] Real users can interact with it! 👥
- [ ] Full CI/CD pipeline operational! ⚙️
- [ ] Automatic deployments working! 🤖
- [ ] Sprint 5 infrastructure paying off! 💰

**This is HUGE!** From local development to production deployment - that's the full journey!

## Time Estimate

- **Pre-deployment setup**: 30 minutes
- **Create environment/tag**: 15 minutes
- **Trigger and approve**: 10 minutes
- **Monitor deployment**: 15 minutes
- **Install services**: 15 minutes
- **Verification**: 30 minutes
- **Initial monitoring**: 1 hour
- **Total**: 2.5-3 hours

**Plus:** 24 hours of monitoring before considering stable.

Ready for production! 🚢
