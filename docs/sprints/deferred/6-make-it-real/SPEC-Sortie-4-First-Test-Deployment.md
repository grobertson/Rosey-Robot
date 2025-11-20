# Sortie 4: First Test Deployment

**Status**: Planning  
**Owner**: Both (User executes, Agent supports)  
**Estimated Effort**: 1-2 hours  
**Related Issue**: #22  
**Depends On**: 
- Sortie 1 (Test server provisioned)
- Sortie 2 (GitHub Secrets configured)
- Sortie 2A (WebSocket timeout fixed)
- Sortie 2B (Health endpoint implemented)
- Sortie 2C (SSH deployment configured)
- Sortie 3 (systemd services created)

## Overview

Execute the first real deployment to the test server! This is where we validate that everything we've built actually works in a real server environment.

**This is exciting!** 🎉 We've done all the planning - now we make it real.

## Pre-Flight Checklist

Before starting, verify these are complete:

### Code Readiness
- [ ] Health endpoint implemented (`/api/health`)
- [ ] SSH deployment workflows updated
- [ ] Timeout configuration fixed (`3.0` seconds)
- [ ] systemd service files created
- [ ] All changes committed to `main` branch
- [ ] All tests passing in CI

### Server Readiness
- [ ] Test server provisioned (Sortie 1)
- [ ] SSH key installed on test server
- [ ] User `rosey` created with proper permissions
- [ ] `/opt/rosey-bot/` directory exists
- [ ] Firewall configured (ports 22, 8001, 9090, 9093)
- [ ] sudoers configured for service management

### GitHub Readiness
- [ ] GitHub Secrets configured (Sortie 2):
  - `SSH_KEY_TEST`
  - `TEST_SERVER_HOST`
  - `TEST_SERVER_USER`
- [ ] Test deployment workflow exists (`.github/workflows/test-deploy.yml`)

## Deployment Process

### Step 1: Manual Pre-Deployment

Before letting GitHub Actions deploy, do initial manual setup:

```bash
# SSH to test server
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP

# Verify Python installed
python3 --version
# Should be Python 3.9 or higher

# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip git rsync

# Verify directory exists and is owned by rosey
ls -ld /opt/rosey-bot
# Should show: drwxr-xr-x ... rosey rosey ... /opt/rosey-bot

# Create log directory
sudo mkdir -p /var/log/rosey-bot
sudo chown rosey:rosey /var/log/rosey-bot

# Exit SSH
exit
```

### Step 2: Trigger First Deployment

The deployment will be triggered automatically when you push to `main`:

```bash
# On your local machine
cd d:\Devel\Rosey-Robot

# Ensure you're on the sprint branch with all changes
git status

# Merge sprint branch to main
git checkout main
git pull origin main
git merge nano-sprint/6-make-it-real
git push origin main
```

**This triggers:** `.github/workflows/test-deploy.yml`

### Step 3: Monitor Deployment

Watch GitHub Actions:

1. Go to: https://github.com/YOUR_USER/Rosey-Robot/actions
2. Find "Test Deployment" workflow
3. Click to see details

**Expected workflow steps:**

```
Test Deployment
├── Run tests
│   ├── Setup Python
│   ├── Install dependencies
│   ├── Run pytest
│   └── ✅ Tests pass
│
└── Deploy to test server
    ├── Checkout code
    ├── Setup SSH key
    ├── Deploy code (rsync)
    ├── Restart services
    ├── Verify deployment
    └── ✅ Deployment successful
```

**What to watch for:**

- ✅ **Tests pass:** All unit tests green
- ✅ **SSH connection:** No "Permission denied" errors
- ✅ **rsync completes:** Files transferred successfully
- ✅ **Services restart:** systemctl commands succeed
- ✅ **Health check:** `/api/health` responds with "healthy"

### Step 4: Install systemd Services

After first deployment, install the service files (one-time setup):

```bash
# SSH to test server
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP

# Service files were deployed to /opt/rosey-bot/systemd/
# Copy to systemd directory
sudo cp /opt/rosey-bot/systemd/rosey-bot.service /etc/systemd/system/
sudo cp /opt/rosey-bot/systemd/rosey-dashboard.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (start on boot)
sudo systemctl enable rosey-bot
sudo systemctl enable rosey-dashboard

# Start services
sudo systemctl start rosey-bot
sudo systemctl start rosey-dashboard

# Check status
sudo systemctl status rosey-bot
sudo systemctl status rosey-dashboard
```

**Expected output:**

```
● rosey-bot.service - Rosey CyTube Bot
   Loaded: loaded (/etc/systemd/system/rosey-bot.service; enabled)
   Active: active (running) since ...
   Main PID: 1234 (python3)
   ...

● rosey-dashboard.service - Rosey Bot Status Dashboard
   Loaded: loaded (/etc/systemd/system/rosey-dashboard.service; enabled)
   Active: active (running) since ...
   Main PID: 1235 (python3)
   ...
```

### Step 5: Verify Deployment

Run comprehensive checks:

#### Check Services Running

```bash
# On test server
sudo systemctl status rosey-bot
sudo systemctl status rosey-dashboard

# Both should show "active (running)"
```

#### Check Health Endpoint

```bash
# From your local machine
curl http://YOUR_TEST_IP:8001/api/health | jq

# Expected output:
{
  "status": "healthy",
  "connected": true,
  "channel": "#your-test-channel",
  "uptime_seconds": 45,
  "version": "abc123f",
  "user_count": 1,
  "requests_handled": 5,
  "error_count": 0
}
```

#### Check Bot in Channel

1. Open browser to your CyTube test channel
2. Look for bot in user list
3. Bot should be connected and idle

#### Check Logs

```bash
# On test server
sudo journalctl -u rosey-bot -n 50

# Should see:
# - "Connected to CyTube"
# - "Joined channel ..."
# - "Bot ready"
# - NO "Connection timeout" errors
# - NO repeated reconnection cycles
```

## Validation Checklist

Complete deployment when:

### Deployment Process
- [ ] GitHub Actions workflow completed successfully
- [ ] No errors in workflow logs
- [ ] rsync transferred all files
- [ ] Services restarted without errors

### Service Status
- [ ] `rosey-bot.service` installed and enabled
- [ ] `rosey-dashboard.service` installed and enabled
- [ ] Both services show "active (running)"
- [ ] Services configured to start on boot
- [ ] No errors in `systemctl status`

### Health & Connectivity
- [ ] Health endpoint responds: `http://TEST_IP:8001/api/health`
- [ ] Health status: `"status": "healthy"`
- [ ] Health connected: `"connected": true"`
- [ ] Bot appears in CyTube channel user list
- [ ] Bot responds to test command (if implemented)

### Logs & Monitoring
- [ ] Bot logs show successful connection
- [ ] No "timeout" errors in logs
- [ ] No repeated reconnection cycles
- [ ] Dashboard accessible (if implemented)
- [ ] Logs being written to journal

### Auto-Restart
- [ ] Test service restart: `sudo systemctl restart rosey-bot` → bot reconnects
- [ ] Test crash recovery: kill bot process → service auto-restarts
- [ ] Verify restart logs in journal

## Common Issues & Solutions

### Issue: GitHub Actions SSH Fails

**Symptoms:** "Permission denied (publickey)" in workflow

**Debug:**

```bash
# Verify secret is set
gh secret list

# Test SSH manually from your machine
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "echo OK"
```

**Fix:** Re-run Sortie 2 (GitHub Secrets configuration)

### Issue: rsync Permission Denied

**Symptoms:** "Permission denied" during file copy

**Debug:**

```bash
# Check directory ownership
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "ls -ld /opt/rosey-bot"
```

**Fix:**

```bash
# Fix ownership
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "sudo chown -R rosey:rosey /opt/rosey-bot"
```

### Issue: Service Fails to Start

**Symptoms:** `systemctl start rosey-bot` fails or service shows "failed"

**Debug:**

```bash
# Check service status
sudo systemctl status rosey-bot

# Check logs
sudo journalctl -u rosey-bot -n 50

# Verify service file syntax
sudo systemd-analyze verify /etc/systemd/system/rosey-bot.service
```

**Common causes:**

1. **Python module not found**
   ```bash
   # Install dependencies
   cd /opt/rosey-bot
   pip3 install -r requirements.txt
   ```

2. **Config file missing**
   ```bash
   # Verify config exists
   ls -la /opt/rosey-bot/config-test.json
   ```

3. **Permissions wrong**
   ```bash
   # Fix ownership
   sudo chown -R rosey:rosey /opt/rosey-bot
   ```

### Issue: Health Endpoint Not Responding

**Symptoms:** `curl http://TEST_IP:8001/api/health` times out or refuses connection

**Debug:**

```bash
# Check if port is open
ssh rosey@TEST_IP "sudo netstat -tlnp | grep 8001"

# Check firewall
ssh rosey@TEST_IP "sudo ufw status"

# Check if process is listening
ssh rosey@TEST_IP "ps aux | grep python3"
```

**Fix:**

1. **Firewall blocking port:**
   ```bash
   sudo ufw allow 8001/tcp
   sudo ufw reload
   ```

2. **Health server not starting:**
   ```bash
   # Check logs for health server startup
   sudo journalctl -u rosey-bot | grep -i health
   ```

3. **Wrong port in config:**
   ```bash
   # Verify config-test.json has "health_port": 8001
   cat /opt/rosey-bot/config-test.json | grep health_port
   ```

### Issue: Bot Connects But Immediately Disconnects

**Symptoms:** Bot joins channel, then leaves, repeatedly

**Debug:**

```bash
# Watch logs live
sudo journalctl -u rosey-bot -f
```

**Fix:**

1. **Timeout still too low:**
   ```bash
   # Verify timeout is 3.0 (not 0.1)
   cat /opt/rosey-bot/config-test.json | grep timeout
   ```

2. **Network issues:**
   ```bash
   # Test connectivity to CyTube
   curl -I https://cytu.be
   ```

3. **Config error:**
   ```bash
   # Validate JSON
   python3 -c "import json; print(json.load(open('/opt/rosey-bot/config-test.json')))"
   ```

## Rollback Procedure

If deployment fails catastrophically:

```bash
# SSH to test server
ssh rosey@TEST_IP

# Stop services
sudo systemctl stop rosey-bot
sudo systemctl stop rosey-dashboard

# Remove deployment
sudo rm -rf /opt/rosey-bot/*

# Report issue to agent for fix
# Then retry deployment
```

## Success Criteria

Sortie 4 is complete when:

- [ ] GitHub Actions deployment workflow succeeds
- [ ] Code deployed to test server (`/opt/rosey-bot/`)
- [ ] systemd services installed and running
- [ ] Health endpoint responding correctly
- [ ] Bot connected to CyTube test channel
- [ ] Bot stable for 15 minutes (no crashes/reconnects)
- [ ] Logs show healthy operation
- [ ] Auto-restart working (service survives kill)
- [ ] Ready for Sortie 5 (production deployment)

## Next Steps

After successful test deployment:

1. **Monitor for 24 hours** - Verify stability
2. **Test features** - Run through bot commands
3. **Check logs daily** - Look for issues
4. **Plan Sortie 5** - Production deployment (if test is stable)

## Celebration Checklist 🎉

When deployment succeeds:

- [ ] Bot is running on a real server! 🚀
- [ ] Health endpoint working! 💚
- [ ] CI/CD pipeline operational! ⚙️
- [ ] One step closer to production! 🏁

**This is a huge milestone!** We went from "it works on my machine" to "it works on a real server." That's real progress!

## Time Estimate

- **Manual pre-deployment**: 30 minutes
- **Trigger deployment**: 5 minutes
- **Monitor workflow**: 10 minutes
- **Install services**: 15 minutes
- **Verification**: 30 minutes
- **Debugging** (if needed): 30-60 minutes
- **Total**: 2-3 hours

Ready to deploy! 🚀
