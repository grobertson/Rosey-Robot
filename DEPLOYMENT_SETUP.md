# Deployment Setup Guide

**Status**: Ready for test environment setup  
**Date**: November 19, 2025  
**Sprint**: 6-make-it-real, Sortie 2C

## Overview

This guide walks through setting up SSH-based deployment from GitHub Actions to your test and production servers.

## Prerequisites

- ✅ Test server provisioned with Ubuntu
- ✅ NATS server running on test server
- ✅ `rosey` user account created on test server
- ✅ SSH key pair generated for deployment

## GitHub Secrets Configuration

You need to configure these secrets in your GitHub repository:

**Go to**: Repository → Settings → Secrets and variables → Actions → New repository secret

### Test Environment Secrets

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `SSH_KEY_TEST` | Private key content | Full content of `~/.ssh/rosey_bot_test_deploy` |
| `TEST_SERVER_HOST` | Server IP or hostname | e.g., `192.168.1.100` or `test.example.com` |
| `TEST_SERVER_USER` | `rosey` | Username for SSH connection |

### Production Environment Secrets (for later)

| Secret Name | Value | Description |
|-------------|-------|-------------|
| `SSH_KEY_PROD` | Private key content | Full content of production deploy key |
| `PROD_SERVER_HOST` | Server IP or hostname | Production server address |
| `PROD_SERVER_USER` | `rosey` | Username for SSH connection |

### How to Add SSH_KEY_TEST Secret

```powershell
# On your Windows machine, read the private key
Get-Content ~/.ssh/rosey_bot_test_deploy | clip

# Then:
# 1. Go to GitHub → Repository → Settings → Secrets → New secret
# 2. Name: SSH_KEY_TEST
# 3. Value: Paste from clipboard (Ctrl+V)
# 4. Click "Add secret"
```

**Important**: Make sure to paste the ENTIRE key including:
```
-----BEGIN OPENSSH PRIVATE KEY-----
[key content]
-----END OPENSSH PRIVATE KEY-----
```

## Server Setup (Test Environment)

SSH to your test server and run these commands:

### 1. Create Deployment Directory

```bash
# Create the deployment directory
sudo mkdir -p /opt/rosey-bot
sudo chown rosey:rosey /opt/rosey-bot
sudo chmod 755 /opt/rosey-bot

# Verify
ls -ld /opt/rosey-bot
# Should show: drwxr-xr-x 2 rosey rosey ... /opt/rosey-bot
```

### 2. Install rsync

```bash
# Install rsync (if not already installed)
sudo apt-get update
sudo apt-get install -y rsync

# Verify
rsync --version
```

### 3. Configure sudo for Service Management

GitHub Actions needs to restart services without a password prompt:

```bash
# Edit sudoers file
sudo visudo

# Add this line at the end (one line, no wrapping):
rosey ALL=(ALL) NOPASSWD: /bin/systemctl restart rosey-bot, /bin/systemctl restart rosey-dashboard, /bin/systemctl status rosey-bot, /bin/systemctl status rosey-dashboard

# Save and exit (Ctrl+O, Enter, Ctrl+X in nano)
```

**Explanation**: This allows the `rosey` user to restart ONLY these specific services without sudo password. It's secure because it doesn't grant full root access.

### 4. Test sudo Configuration

```bash
# Test that you can restart services without password
sudo systemctl status rosey-bot

# Should show status WITHOUT asking for password
# If it asks for password, check the sudoers entry
```

## Verification Steps

### Test SSH Connection from Your Machine

Before GitHub Actions tries, verify SSH works from your local machine:

```powershell
# Test basic SSH connection
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "echo 'SSH connection OK'"

# Should print: SSH connection OK
```

### Test rsync

```powershell
# Create a test file
"test deployment" | Out-File -Encoding UTF8 test_deploy.txt

# Try rsync to server
rsync -avz -e "ssh -i ~/.ssh/rosey_bot_test_deploy" test_deploy.txt rosey@YOUR_TEST_IP:/tmp/

# Verify it arrived
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP "cat /tmp/test_deploy.txt"

# Should print: test deployment

# Cleanup
Remove-Item test_deploy.txt
```

### Test Service Restart

```bash
# SSH to server
ssh -i ~/.ssh/rosey_bot_test_deploy rosey@YOUR_TEST_IP

# Try restarting services (should work without password)
sudo systemctl restart rosey-bot
sudo systemctl status rosey-bot

# If this works without password prompt, GitHub Actions will work too!
```

## Health Endpoint Setup

The workflows expect a health endpoint at `http://YOUR_SERVER:8001/api/health` that returns JSON with "healthy" in it.

### Quick Health Endpoint (for testing)

If you don't have the full dashboard yet, create a simple health endpoint:

```bash
# SSH to server
ssh rosey@YOUR_TEST_IP

# Create a simple health endpoint script
cat > /opt/rosey-bot/health_endpoint.py << 'EOF'
#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health = {"status": "healthy", "service": "rosey-bot"}
            self.wfile.write(json.dumps(health).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8001), HealthHandler)
    print('Health endpoint running on port 8001')
    server.serve_forever()
EOF

chmod +x /opt/rosey-bot/health_endpoint.py

# Test it
python3 /opt/rosey-bot/health_endpoint.py &

# In another terminal, test it
curl http://localhost:8001/api/health
# Should return: {"status": "healthy", "service": "rosey-bot"}

# Kill the test
pkill -f health_endpoint.py
```

### Create systemd Service for Health Endpoint

```bash
# Create service file
sudo tee /etc/systemd/system/rosey-health.service > /dev/null << 'EOF'
[Unit]
Description=Rosey Bot Health Endpoint
After=network.target

[Service]
Type=simple
User=rosey
WorkingDirectory=/opt/rosey-bot
ExecStart=/usr/bin/python3 /opt/rosey-bot/health_endpoint.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable rosey-health
sudo systemctl start rosey-health

# Verify
sudo systemctl status rosey-health
curl http://localhost:8001/api/health
```

## Testing the Deployment Workflow

Once everything is configured:

### 1. Verify GitHub Secrets

```bash
# From your local machine, check secrets are set
gh secret list

# Should show:
# SSH_KEY_TEST         Updated 2024-XX-XX
# TEST_SERVER_HOST     Updated 2024-XX-XX
# TEST_SERVER_USER     Updated 2024-XX-XX
```

### 2. Trigger Test Deployment

```bash
# Make a small change to trigger deployment
git checkout main
echo "# Test deployment" >> README.md
git add README.md
git commit -m "test: trigger deployment workflow"
git push origin main

# Watch the deployment
gh run watch
```

### 3. Monitor on GitHub

Go to: `https://github.com/YOUR_USERNAME/Rosey-Robot/actions`

You should see:
- ✅ Quality Gates job (lint, test)
- ✅ Deploy job
  - ✅ Setup SSH key
  - ✅ Deploy code to test server
  - ✅ Restart bot service
  - ✅ Verify deployment
  - ✅ Cleanup SSH key

### 4. Verify on Server

```bash
# SSH to server
ssh rosey@YOUR_TEST_IP

# Check files were deployed
ls -la /opt/rosey-bot/

# Check services restarted
sudo systemctl status rosey-bot
sudo journalctl -u rosey-bot -n 20

# Check health endpoint
curl http://localhost:8001/api/health
```

## Troubleshooting

### Issue: "Permission denied (publickey)"

**Cause**: SSH key not configured correctly in GitHub Secrets.

**Fix**:
1. Verify the secret contains the FULL private key (including header/footer)
2. Regenerate the key if needed
3. Make sure public key is in `~/.ssh/authorized_keys` on server

### Issue: "Host key verification failed"

**Cause**: Server's host key not in known_hosts.

**Fix**: The workflow includes `ssh-keyscan` which should handle this automatically. If it still fails, try running locally:

```powershell
ssh-keyscan -H YOUR_TEST_IP >> ~/.ssh/known_hosts
```

### Issue: "sudo: no tty present and no askpass program specified"

**Cause**: sudo requires password, but GitHub Actions can't provide one.

**Fix**: Check the sudoers configuration (see step 3 above). The line must include `NOPASSWD:`.

### Issue: rsync fails with "command not found"

**Fix**:
```bash
ssh rosey@YOUR_TEST_IP
sudo apt-get update
sudo apt-get install -y rsync
```

### Issue: Health endpoint returns 404

**Fix**: Make sure the health endpoint service is running:
```bash
sudo systemctl status rosey-health
sudo systemctl restart rosey-health
```

### Issue: Deployment succeeds but bot not running

**Debug steps**:
```bash
# SSH to server
ssh rosey@YOUR_TEST_IP

# Check service status
sudo systemctl status rosey-bot

# Check recent logs
sudo journalctl -u rosey-bot -n 50 --no-pager

# Try running manually to see errors
cd /opt/rosey-bot
python3 -m bot.rosey.rosey bot/rosey/config.json
```

## Rollback Procedure

If a deployment fails or causes issues:

### Automated Rollback (Production only)

Production deployments create automatic backups. To rollback:

```bash
# SSH to server
ssh rosey@YOUR_SERVER

# List backups
ls -lrt /opt/rosey-bot-backup-*

# Restore the most recent backup
LATEST_BACKUP=$(ls -t /opt/rosey-bot-backup-* | head -1)
sudo rm -rf /opt/rosey-bot
sudo mv $LATEST_BACKUP /opt/rosey-bot
sudo chown -R rosey:rosey /opt/rosey-bot

# Restart services
sudo systemctl restart rosey-bot
sudo systemctl restart rosey-dashboard

# Verify
curl http://localhost:8000/api/health
```

### Manual Rollback

Redeploy a previous known-good version:

```bash
# From your machine
git tag  # List available versions

# Go to GitHub Actions → Deploy to Production
# Click "Run workflow"
# Enter the previous version tag (e.g., v0.1.0)
# Click "Run workflow"
```

## Next Steps

Once test deployment is working:

1. ✅ Test deployment workflow runs successfully
2. ✅ Files deployed to `/opt/rosey-bot/`
3. ✅ Services restart automatically
4. ✅ Health endpoint confirms deployment
5. ⏭ Set up production environment (repeat these steps for prod server)
6. ⏭ Configure production GitHub secrets
7. ⏭ Test production deployment workflow

## Security Notes

- Private SSH keys stored in GitHub Secrets (encrypted at rest)
- Keys deleted from runner after each deployment (never persisted)
- sudo access limited to specific systemctl commands only
- Different keys for test and production (isolation)
- Rotate keys every 90 days (add to calendar)

## Reference

- Spec: `docs/sprints/active/6-make-it-real/SPEC-Sortie-2C-SSH-Deployment.md`
- Test workflow: `.github/workflows/test-deploy.yml`
- Production workflow: `.github/workflows/prod-deploy.yml`
- Health endpoint spec: `docs/sprints/active/6-make-it-real/SPEC-Sortie-2B-Health-Endpoint.md`

---

**Ready to deploy!** 🚀

Once you've completed the server setup and configured GitHub secrets, commit and push to main to trigger the first real deployment.
