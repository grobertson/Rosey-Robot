# Critical Dependency: Configure SSH Deployment

**Status**: Planning  
**Owner**: Agent (with user setup)  
**Estimated Effort**: 2-3 hours  
**Related Issue**: #17  
**Depends On**: Sorties 1-2 (servers + secrets configured)  
**Required For**: Sorties 4-5 (actual deployments)

## Overview

Replace placeholder deployment steps in CI/CD workflows with actual SSH-based deployment. Currently workflows just echo "would deploy" - we need them to actually copy files to servers and restart services.

**Critical because:** Without this, we can't deploy code to servers. All of Sprint 6 depends on working deployments.

## Current State

**Sprint 5 workflows use placeholders:**

`.github/workflows/test-deploy.yml`:

```yaml
- name: Deploy to test server
  run: |
    echo "Would deploy to test server"
    echo "Files ready for deployment in workspace"
```

`.github/workflows/prod-deploy.yml`:

```yaml
- name: Deploy to production
  run: |
    echo "Would deploy to production server"
    echo "Manual approval received"
```

**Problems:**

- No actual file transfer
- No service restart
- No deployment verification
- Can't tell if deployment succeeded

## Target State

**Real SSH-based deployment:**

- Use `rsync` to copy files to servers
- SSH to restart systemd services
- Verify deployment with health endpoint
- Report success/failure clearly

## Technical Design

### Deployment Strategy

Use GitHub's SSH action + rsync for safe, incremental deployments:

```
GitHub Runner
    ↓ (SSH)
    ↓ (authenticate with SSH_KEY_TEST/PROD)
    ↓
Server (test or prod)
    ↓ (rsync)
    Copy changed files to /opt/rosey-bot/
    ↓ (systemctl)
    Restart rosey-bot.service
    ↓ (curl)
    Verify health endpoint responds
```

**Why rsync?**

- Only copies changed files (fast)
- Preserves permissions
- Can exclude unnecessary files (.git, tests, etc.)
- Atomic operations (less likely to corrupt)

**Why not docker/ansible/etc?**

- Keeping it simple for Sprint 6
- Direct SSH deployment is straightforward
- Can evolve to containers later if needed

### Updated Test Deployment Workflow

File: `.github/workflows/test-deploy.yml`

```yaml
name: Test Deployment

on:
  push:
    branches:
      - main
    paths:
      - 'lib/**'
      - 'web/**'
      - 'common/**'
      - 'systemd/**'
      - 'monitoring/**'
      - 'config-test.json'
      - 'requirements.txt'

jobs:
  test:
    # ... existing test job ...
  
  deploy-test:
    name: Deploy to Test Server
    runs-on: ubuntu-latest
    needs: test  # Only deploy if tests pass
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_KEY_TEST }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keyscan -H ${{ secrets.TEST_SERVER_HOST }} >> ~/.ssh/known_hosts
      
      - name: Deploy code to test server
        run: |
          rsync -avz --delete \
            -e "ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no" \
            --exclude '.git' \
            --exclude '.github' \
            --exclude 'test/' \
            --exclude '*.pyc' \
            --exclude '__pycache__' \
            --exclude '.pytest_cache' \
            ./ ${{ secrets.TEST_SERVER_USER }}@${{ secrets.TEST_SERVER_HOST }}:/opt/rosey-bot/
      
      - name: Restart bot service
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.TEST_SERVER_USER }}@${{ secrets.TEST_SERVER_HOST }} << 'EOF'
            sudo systemctl restart rosey-bot
            sudo systemctl restart rosey-dashboard
          EOF
      
      - name: Verify deployment
        run: |
          # Wait for services to start
          sleep 10
          
          # Check health endpoint
          HEALTH_URL="http://${{ secrets.TEST_SERVER_HOST }}:8001/api/health"
          
          for i in {1..5}; do
            if curl -f -s "$HEALTH_URL" | grep -q "healthy"; then
              echo "✅ Test deployment successful!"
              exit 0
            fi
            echo "Waiting for health endpoint... ($i/5)"
            sleep 5
          done
          
          echo "❌ Health endpoint not responding"
          exit 1
      
      - name: Cleanup SSH key
        if: always()
        run: |
          rm -f ~/.ssh/deploy_key
```

### Updated Production Deployment Workflow

File: `.github/workflows/prod-deploy.yml`

```yaml
name: Production Deployment

on:
  workflow_dispatch:  # Manual trigger only
    inputs:
      version:
        description: 'Version/tag to deploy'
        required: true
        type: string

jobs:
  deploy-prod:
    name: Deploy to Production Server
    runs-on: ubuntu-latest
    environment: production  # Requires approval
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          ref: ${{ inputs.version }}
      
      - name: Run tests before production
        run: |
          python -m pytest tests/ -v
      
      - name: Setup SSH key
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_KEY_PROD }}" > ~/.ssh/deploy_key
          chmod 600 ~/.ssh/deploy_key
          ssh-keyscan -H ${{ secrets.PROD_SERVER_HOST }} >> ~/.ssh/known_hosts
      
      - name: Backup current production
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.PROD_SERVER_USER }}@${{ secrets.PROD_SERVER_HOST }} << 'EOF'
            BACKUP_DIR="/opt/rosey-bot-backup-$(date +%Y%m%d-%H%M%S)"
            sudo cp -r /opt/rosey-bot "$BACKUP_DIR"
            echo "Backup created at $BACKUP_DIR"
          EOF
      
      - name: Deploy code to production
        run: |
          rsync -avz --delete \
            -e "ssh -i ~/.ssh/deploy_key -o StrictHostKeyChecking=no" \
            --exclude '.git' \
            --exclude '.github' \
            --exclude 'test/' \
            --exclude '*.pyc' \
            --exclude '__pycache__' \
            --exclude '.pytest_cache' \
            ./ ${{ secrets.PROD_SERVER_USER }}@${{ secrets.PROD_SERVER_HOST }}:/opt/rosey-bot/
      
      - name: Restart bot service
        run: |
          ssh -i ~/.ssh/deploy_key ${{ secrets.PROD_SERVER_USER }}@${{ secrets.PROD_SERVER_HOST }} << 'EOF'
            sudo systemctl restart rosey-bot
            sudo systemctl restart rosey-dashboard
          EOF
      
      - name: Verify deployment
        run: |
          sleep 10
          
          HEALTH_URL="http://${{ secrets.PROD_SERVER_HOST }}:8000/api/health"
          
          for i in {1..5}; do
            if curl -f -s "$HEALTH_URL" | grep -q "healthy"; then
              echo "✅ Production deployment successful!"
              curl -s "$HEALTH_URL" | jq
              exit 0
            fi
            echo "Waiting for health endpoint... ($i/5)"
            sleep 5
          done
          
          echo "❌ Health endpoint not responding"
          echo "⚠️  Consider rolling back!"
          exit 1
      
      - name: Cleanup SSH key
        if: always()
        run: |
          rm -f ~/.ssh/deploy_key
```

## Server Setup (User Tasks)

You'll need to prepare servers for SSH deployment:

### 1. Create Deployment Directory

On both test and production servers:

```bash
# SSH to server
ssh rosey@YOUR_SERVER_IP

# Create deployment directory
sudo mkdir -p /opt/rosey-bot
sudo chown rosey:rosey /opt/rosey-bot
sudo chmod 755 /opt/rosey-bot

# Verify
ls -ld /opt/rosey-bot
# Should show: drwxr-xr-x 2 rosey rosey ...
```

### 2. Configure sudo for Service Management

GitHub Actions needs to restart services without password:

```bash
# Edit sudoers
sudo visudo

# Add this line (replace 'rosey' if using different user):
rosey ALL=(ALL) NOPASSWD: /bin/systemctl restart rosey-bot, /bin/systemctl restart rosey-dashboard, /bin/systemctl status rosey-bot, /bin/systemctl status rosey-dashboard

# Save and exit
```

**Security note:** This only allows restarting specific services, not full sudo access.

### 3. Test SSH Connection from Your Machine

Before GitHub Actions tries, verify SSH works:

```powershell
# From your Windows machine
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "echo 'SSH OK'"

# Should print: SSH OK
```

### 4. Test rsync

```powershell
# Create test file
echo "test" > test.txt

# Try rsync to server
rsync -avz -e "ssh -i ~/.ssh/rosey_bot_test_deploy" test.txt rosey@YOUR_TEST_IP:/tmp/

# SSH and verify
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "cat /tmp/test.txt"
# Should print: test
```

If these work, GitHub Actions will work too!

## Implementation Steps

1. **Update test deployment workflow**
   - Modify `.github/workflows/test-deploy.yml`
   - Replace echo placeholders with actual SSH/rsync
   - Add health endpoint verification
   - Add cleanup steps

2. **Update production deployment workflow**
   - Modify `.github/workflows/prod-deploy.yml`
   - Add backup step before deployment
   - Replace echo placeholders with SSH/rsync
   - Add health endpoint verification
   - Add rollback instructions

3. **Update README with deployment docs**
   - Document manual deployment process
   - Document rollback process
   - Document troubleshooting steps

4. **Test deployment locally**
   - Manually run rsync commands
   - Verify file transfer works
   - Verify service restart works

## Testing

### Test Deployment Workflow

```bash
# Trigger test deployment by pushing to main
git push origin main

# Watch GitHub Actions
# Go to: https://github.com/YOUR_USER/Rosey-Robot/actions

# Should see:
# ✅ Test Deployment
#   ✅ test job
#   ✅ deploy-test job
#     ✅ Deploy code to test server
#     ✅ Restart bot service
#     ✅ Verify deployment
```

### Test Production Deployment Workflow

```bash
# Trigger production deployment manually
# Go to: GitHub → Actions → Production Deployment → Run workflow
# Enter version: main (or tag)
# Click "Run workflow"

# Should see:
# ⏸  Waiting for approval
# (Click "Review deployments" → Approve)
# ✅ Production Deployment
#   ✅ Backup current production
#   ✅ Deploy code to production
#   ✅ Restart bot service
#   ✅ Verify deployment
```

## Validation Checklist

After implementation:

### Configuration Checks

- [ ] GitHub Secrets configured (from Sortie 2)
  - [ ] `SSH_KEY_TEST` (private key)
  - [ ] `SSH_KEY_PROD` (private key)
  - [ ] `TEST_SERVER_HOST` (IP or hostname)
  - [ ] `TEST_SERVER_USER` (usually "rosey")
  - [ ] `PROD_SERVER_HOST`
  - [ ] `PROD_SERVER_USER`

### Server Checks

- [ ] `/opt/rosey-bot/` directory exists on both servers
- [ ] Directory owned by deployment user (`rosey:rosey`)
- [ ] sudoers configured for service restart
- [ ] SSH access works from your machine

### Workflow Checks

- [ ] Test workflow updated with real SSH/rsync
- [ ] Production workflow updated with real SSH/rsync
- [ ] Both workflows include health endpoint verification
- [ ] Production workflow includes backup step
- [ ] Both workflows clean up SSH keys after use

### Deployment Checks

- [ ] Test deployment triggered and succeeded
- [ ] Files visible on test server: `ssh test-server "ls -la /opt/rosey-bot"`
- [ ] Services restarted: `ssh test-server "systemctl status rosey-bot"`
- [ ] Health endpoint responds: `curl http://TEST_IP:8001/api/health`
- [ ] Bot connected to CyTube: check channel

## Common Issues & Solutions

### Issue: "Permission denied (publickey)"

**Cause:** SSH key not configured correctly.

**Fix:**

```bash
# Verify secret contains PRIVATE key
gh secret list

# Test SSH manually
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_SERVER

# If fails, regenerate keys (Sortie 1)
```

### Issue: "Host key verification failed"

**Cause:** Server's host key not in known_hosts.

**Fix:**

```bash
# Add to workflow (already included above)
ssh-keyscan -H ${{ secrets.TEST_SERVER_HOST }} >> ~/.ssh/known_hosts
```

### Issue: "sudo: no tty present"

**Cause:** sudo requires password or not configured correctly.

**Fix:**

```bash
# Edit sudoers on server
sudo visudo

# Add NOPASSWD line (see Server Setup above)
```

### Issue: "rsync: command not found"

**Cause:** rsync not installed on server.

**Fix:**

```bash
# SSH to server
sudo apt-get update
sudo apt-get install -y rsync
```

### Issue: Deployment succeeds but bot not running

**Causes:**

- Service file incorrect
- Config file wrong
- Python dependencies missing

**Debug:**

```bash
# SSH to server
ssh rosey@YOUR_SERVER

# Check service status
sudo systemctl status rosey-bot

# Check logs
sudo journalctl -u rosey-bot -n 50

# Check files deployed
ls -la /opt/rosey-bot/

# Try running manually
cd /opt/rosey-bot
python3 -m lib
```

## Rollback Procedure

If production deployment fails:

### Automated Rollback (when backup exists)

```bash
# SSH to production server
ssh rosey@PROD_IP

# List backups
ls -la /opt/ | grep rosey-bot-backup

# Restore latest backup
LATEST_BACKUP=$(ls -t /opt/rosey-bot-backup-* | head -1)
sudo rm -rf /opt/rosey-bot
sudo mv $LATEST_BACKUP /opt/rosey-bot
sudo chown -R rosey:rosey /opt/rosey-bot

# Restart services
sudo systemctl restart rosey-bot
sudo systemctl restart rosey-dashboard

# Verify
curl http://PROD_IP:8000/api/health
```

### Manual Rollback (redeploy previous version)

```bash
# From your machine, trigger production deployment
# Use previous known-good tag/commit

# Go to: GitHub → Actions → Production Deployment → Run workflow
# Version: v1.2.3 (previous good version)
# Run workflow
```

## Security Considerations

**SSH Keys:**

- Private keys stored in GitHub Secrets (encrypted)
- Keys deleted from runner after each deployment
- Different keys for test and production
- Keys should be rotated every 90 days

**sudo Access:**

- Limited to specific systemctl commands only
- No full root access
- Monitored via system logs

**Network:**

- Firewall allows SSH only from GitHub's IP ranges (optional)
- Deploy over SSH (encrypted)
- Health endpoint on internal network (or firewall-protected)

## Success Criteria

This critical dependency is complete when:

1. Test deployment workflow uses real SSH/rsync
2. Production deployment workflow uses real SSH/rsync
3. Both workflows verify deployment with health endpoint
4. Test deployment triggered automatically on main push
5. Production deployment requires manual approval
6. Successful test deployment to test server
7. Documentation updated with deployment and rollback procedures

## Impact on Sprint 6

**Blocks these sorties:**

- Sortie 4: First test deployment (need working deployment)
- Sortie 5: First production deployment (same)
- All subsequent sorties (depend on deployed code)

**Timeline:** Must complete before Sortie 4.

## Time Estimate

- **Update workflows**: 1.5 hours
- **Server setup** (user): 30 minutes
- **Testing**: 1 hour
- **Documentation**: 30 minutes
- **Total**: ~3.5 hours

Ready to implement! 🚀
