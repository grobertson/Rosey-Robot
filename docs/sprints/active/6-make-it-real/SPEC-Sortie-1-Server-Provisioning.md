# Sortie 1: Provision and Configure Servers

**Status**: Planning  
**Owner**: User (with agent assistance)  
**Estimated Effort**: 2-4 hours  
**Related Issue**: #19  

## Overview

Provision and configure two servers (test and production) ready for bot deployment. This is the foundation for all subsequent sorties.

**Key Point**: This sortie is mostly YOUR work! I'll provide clear instructions for what you need to do, then we'll validate together.

## What You Need to Decide

### 1. Server Provider Choice

Pick one that you're comfortable with (or already have):

**Option A: DigitalOcean Droplets** (Recommended - simple, cheap)
- Cost: ~$6-12/month per server
- Easy web UI
- Good docs
- 1GB RAM is enough for our bot

**Option B: AWS EC2**
- Free tier available (t2.micro)
- More complex but powerful
- Good if you already use AWS

**Option C: Linode, Vultr, Hetzner**
- Similar to DigitalOcean
- Good pricing
- Pick what you know

**Option D: Local VMs** (Development only)
- Free but not real "production"
- Good for testing deployment process
- VirtualBox or VMware

**Option E: Your own servers**
- If you have physical servers or existing VMs
- Need SSH access and sudo

### 2. Operating System

**Recommended: Ubuntu 22.04 LTS** (what I'll document)
- Long-term support
- Widely used
- Excellent Python support

**Also works: Debian 11+, Ubuntu 20.04+**
- Instructions will be 95% the same

**Will need adjustments: CentOS, RHEL, other distros**
- Let me know and I'll adjust commands

## Step-by-Step Setup Instructions

### PHASE 1: Provision Servers

#### Step 1.1: Create Test Server

**If using DigitalOcean:**

1. Log into DigitalOcean console
2. Click "Create" → "Droplets"
3. Configure:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic ($6/month - 1GB RAM, 1 vCPU is plenty)
   - **Datacenter**: Pick closest to you
   - **Authentication**: SSH Key (we'll generate below)
   - **Hostname**: `rosey-bot-test`
4. Click "Create Droplet"
5. Note the IP address (e.g., `192.0.2.1`)

**If using AWS EC2:**

1. Log into AWS Console → EC2
2. Click "Launch Instance"
3. Configure:
   - **Name**: `rosey-bot-test`
   - **AMI**: Ubuntu Server 22.04 LTS
   - **Instance type**: t2.micro (free tier)
   - **Key pair**: Create new (we'll generate below)
   - **Security group**: Allow SSH (port 22) from your IP
4. Launch instance
5. Note the public IP address

**If using local VM:**

1. Install VirtualBox
2. Create new VM:
   - Name: `rosey-bot-test`
   - Type: Linux, Ubuntu 64-bit
   - RAM: 2GB
   - Disk: 20GB
3. Install Ubuntu 22.04
4. Configure port forwarding:
   - Host port 2222 → Guest port 22 (SSH)
   - Host port 8001 → Guest port 8001 (health endpoint)

#### Step 1.2: Create Production Server

**Repeat Step 1.1 but:**
- Hostname: `rosey-bot-prod`
- Consider slightly larger size for production ($12/month - 2GB RAM)
- Note the IP address (different from test!)

**IMPORTANT**: Keep test and prod servers SEPARATE. We want to test deployments safely before touching production.

### PHASE 2: Generate SSH Keys

You'll need SSH keys to access servers and for GitHub Actions to deploy.

#### Step 2.1: Generate Deployment Key Pair

**On your local machine** (Windows PowerShell):

```powershell
# Create .ssh directory if it doesn't exist
mkdir ~\.ssh -ErrorAction SilentlyContinue

# Generate key for TEST server (no passphrase for automation)
ssh-keygen -t ed25519 -C "rosey-bot-test-deploy" -f ~\.ssh\rosey_bot_test_deploy -N '""'

# Generate key for PRODUCTION server (no passphrase for automation)
ssh-keygen -t ed25519 -C "rosey-bot-prod-deploy" -f ~\.ssh\rosey_bot_prod_deploy -N '""'
```

This creates 4 files:
- `~\.ssh\rosey_bot_test_deploy` (private key for test)
- `~\.ssh\rosey_bot_test_deploy.pub` (public key for test)
- `~\.ssh\rosey_bot_prod_deploy` (private key for prod)
- `~\.ssh\rosey_bot_prod_deploy.pub` (public key for prod)

**SECURITY NOTE**: The private keys stay on your machine AND in GitHub Secrets. Never commit them to git!

#### Step 2.2: Generate Your Personal Access Key (Optional)

For your own access (not deployment):

```powershell
# Only if you don't already have an SSH key
ssh-keygen -t ed25519 -C "your_email@example.com"
```

### PHASE 3: Configure Servers

Now we'll set up each server. Do this for BOTH test and prod servers.

#### Step 3.1: First Connection

**Connect to test server:**

```powershell
# Replace with your server IP
ssh root@192.0.2.1
```

If this is your first time, you'll see:
```
The authenticity of host '192.0.2.1' can't be established.
ED25519 key fingerprint is SHA256:...
Are you sure you want to continue connecting (yes/no)?
```

Type `yes` and press Enter.

#### Step 3.2: Update System

```bash
# Update package lists
apt update

# Upgrade installed packages
apt upgrade -y

# Install essential packages
apt install -y python3 python3-pip python3-venv git curl wget systemd
```

#### Step 3.3: Create Deployment User

**Don't run the bot as root!** Create a dedicated user:

```bash
# Create user 'rosey' (no password needed)
useradd -m -s /bin/bash rosey

# Give sudo access (for service management)
usermod -aG sudo rosey

# Allow sudo without password (needed for deployment automation)
echo "rosey ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/rosey
```

#### Step 3.4: Set Up SSH Keys for Deployment User

```bash
# Switch to rosey user
su - rosey

# Create .ssh directory
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# Create authorized_keys file
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Now **on your local machine**, copy the public key:

```powershell
# Display test server public key
Get-Content ~\.ssh\rosey_bot_test_deploy.pub
```

Copy the output (starts with `ssh-ed25519 AAAA...`).

Back **on the test server**:

```bash
# Paste the public key into authorized_keys
nano ~/.ssh/authorized_keys
# Paste the key, save (Ctrl+X, Y, Enter)
```

**Repeat for production server** using `rosey_bot_prod_deploy.pub`!

#### Step 3.5: Test SSH Connection

**On your local machine**, test the new key:

```powershell
# Test test server (use your test server IP)
ssh -i ~\.ssh\rosey_bot_test_deploy rosey@192.0.2.1

# Test prod server (use your prod server IP)
ssh -i ~\.ssh\rosey_bot_prod_deploy rosey@your.prod.ip
```

If you can connect as `rosey` without a password, SUCCESS! ✅

#### Step 3.6: Create Deployment Directory

**On each server (as rosey user)**:

```bash
# Create deployment directory
sudo mkdir -p /opt/rosey-bot
sudo chown rosey:rosey /opt/rosey-bot
cd /opt/rosey-bot

# Create directory structure
mkdir -p {web,monitoring,scripts,logs}
```

#### Step 3.7: Install and Configure NATS Server

**CRITICAL**: Sprint 6a (Quicksilver) introduced a NATS-based event bus architecture. NATS server must be installed and running before the bot can function.

**On each server (test and production)**:

##### Install NATS Server

```bash
# Download and install NATS server (latest stable)
wget https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.tar.gz

# Extract
tar -xzf nats-server-v2.10.7-linux-amd64.tar.gz

# Move binary to system path
sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/

# Verify installation
nats-server --version
# Expected: nats-server: v2.10.7

# Clean up
rm -rf nats-server-v2.10.7-linux-amd64*
```

##### Create NATS Configuration

```bash
# Create NATS config directory
sudo mkdir -p /etc/nats

# Create NATS server configuration
sudo tee /etc/nats/nats-server.conf <<'EOF'
# NATS Server Configuration for Rosey Bot

# Server identification
server_name: rosey_nats

# Listen on localhost only (bot and NATS on same server)
host: 127.0.0.1
port: 4222

# Monitoring endpoint (for health checks)
http_port: 8222

# Logging
log_file: "/var/log/nats/nats-server.log"
debug: false
trace: false
logtime: true

# Limits
max_connections: 100
max_control_line: 4096
max_payload: 1048576    # 1MB

# Timeouts
ping_interval: 2m
ping_max: 2

# JetStream (persistence) - optional for now
jetstream {
    store_dir: "/var/lib/nats"
    max_mem: 1G
    max_file: 10G
}
EOF
```

##### Create NATS System Service

```bash
# Create NATS user
sudo useradd -r -s /bin/false nats

# Create directories
sudo mkdir -p /var/log/nats /var/lib/nats
sudo chown -R nats:nats /var/log/nats /var/lib/nats

# Create systemd service
sudo tee /etc/systemd/system/nats.service <<'EOF'
[Unit]
Description=NATS Server
Documentation=https://docs.nats.io
After=network.target

[Service]
Type=simple
User=nats
Group=nats
ExecStart=/usr/local/bin/nats-server -c /etc/nats/nats-server.conf
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nats-server

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/nats /var/lib/nats

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
sudo systemctl daemon-reload

# Enable NATS to start on boot
sudo systemctl enable nats

# Start NATS server
sudo systemctl start nats

# Check status
sudo systemctl status nats
```

##### Verify NATS Installation

```bash
# Check NATS is running
curl http://localhost:8222/varz

# Expected: JSON response with server info

# Check logs
sudo tail -f /var/log/nats/nats-server.log
# Expected: "Server is ready" message

# Test NATS connectivity (if nats CLI is installed)
# Optional: install NATS CLI for testing
curl -L https://github.com/nats-io/natscli/releases/download/v0.1.1/nats-0.1.1-linux-amd64.tar.gz -o nats-cli.tar.gz
tar -xzf nats-cli.tar.gz
sudo mv nats-0.1.1-linux-amd64/nats /usr/local/bin/
rm -rf nats-*

# Test pub/sub
nats pub test "Hello NATS"
# Expected: Published message
```

#### Step 3.8: Configure Firewall

**On each server**:

```bash
# Install ufw (Ubuntu firewall)
sudo apt install -y ufw

# Allow SSH (IMPORTANT - don't lock yourself out!)
sudo ufw allow 22/tcp

# Allow health endpoint ports
sudo ufw allow 8000/tcp  # Production health endpoint
sudo ufw allow 8001/tcp  # Test health endpoint

# NATS server listens on localhost only (127.0.0.1:4222)
# No external firewall rule needed - bot and NATS on same server

# Allow Prometheus (if accessing remotely)
sudo ufw allow 9090/tcp

# Allow Alertmanager (if accessing remotely)
sudo ufw allow 9093/tcp

# Enable firewall
sudo ufw --force enable

# Check status
sudo ufw status
```

**Expected output:**
```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
8000/tcp                   ALLOW       Anywhere
8001/tcp                   ALLOW       Anywhere
9090/tcp                   ALLOW       Anywhere
9093/tcp                   ALLOW       Anywhere
```

### PHASE 4: Document Server Details

Create a local file (NOT IN GIT!) with your server details:

**File: `~/rosey-servers.txt`** (or wherever you keep secrets)

```
# Rosey Bot Servers

## Test Server
IP: 192.0.2.1
User: rosey
SSH Key: ~\.ssh\rosey_bot_test_deploy
Deployment Dir: /opt/rosey-bot
Health Endpoint: http://192.0.2.1:8001/api/health

## Production Server  
IP: 198.51.100.1
User: rosey
SSH Key: ~\.ssh\rosey_bot_prod_deploy
Deployment Dir: /opt/rosey-bot
Health Endpoint: http://198.51.100.1:8000/api/health

## CyTube Bot Credentials
Test Channel: [your test channel]
Test Username: [your test bot username]
Test Password: [your test bot password]

Prod Channel: [your prod channel]
Prod Username: [your prod bot username]
Prod Password: [your prod bot password]
```

## Validation Checklist

Complete this checklist for BOTH servers before proceeding:

### Test Server Validation

- [ ] Server provisioned and accessible
- [ ] Ubuntu 22.04 (or compatible) installed
- [ ] Python 3.9+ installed (`python3 --version`)
- [ ] Git installed (`git --version`)
- [ ] User `rosey` created with sudo access
- [ ] SSH key authentication works (passwordless)
- [ ] Directory `/opt/rosey-bot` exists and owned by `rosey`
- [ ] NATS server installed (`nats-server --version`)
- [ ] NATS service running (`systemctl status nats`)
- [ ] NATS monitoring accessible (`curl http://localhost:8222/varz`)
- [ ] Firewall configured (ports 22, 8001, 9090, 9093 open)
- [ ] Can connect: `ssh -i ~\.ssh\rosey_bot_test_deploy rosey@TEST_IP`
- [ ] Server IP address documented

### Production Server Validation

- [ ] Server provisioned and accessible
- [ ] Ubuntu 22.04 (or compatible) installed
- [ ] Python 3.9+ installed (`python3 --version`)
- [ ] Git installed (`git --version`)
- [ ] User `rosey` created with sudo access
- [ ] SSH key authentication works (passwordless)
- [ ] Directory `/opt/rosey-bot` exists and owned by `rosey`
- [ ] NATS server installed (`nats-server --version`)
- [ ] NATS service running (`systemctl status nats`)
- [ ] NATS monitoring accessible (`curl http://localhost:8222/varz`)
- [ ] Firewall configured (ports 22, 8000, 9090, 9093 open)
- [ ] Can connect: `ssh -i ~\.ssh\rosey_bot_prod_deploy rosey@PROD_IP`
- [ ] Server IP address documented
- [ ] DIFFERENT IP from test server ✅

### Local Machine Validation

- [ ] SSH keys generated (`~\.ssh\rosey_bot_test_deploy*`)
- [ ] Can SSH to test server as `rosey` without password
- [ ] Can SSH to prod server as `rosey` without password
- [ ] Server details documented (IPs, users, keys)
- [ ] Bot credentials ready (CyTube username/password)

## What I Need From You

Once you've completed the above, give me:

1. **Test server IP address**: `192.0.2.1` (example)
2. **Production server IP address**: `198.51.100.1` (example)
3. **Confirmation**: "Both servers are set up and I can SSH as rosey"

**DO NOT** share your private SSH keys! We'll put those in GitHub Secrets in Sortie 2.

## Common Issues & Solutions

### Issue: "Permission denied (publickey)"

**Solution:**
```powershell
# Check SSH key permissions
icacls ~\.ssh\rosey_bot_test_deploy

# Should show: You:(R,W) and SYSTEM:(F)
# If not, fix with:
icacls ~\.ssh\rosey_bot_test_deploy /inheritance:r /grant:r "$($env:USERNAME):(R,W)"
```

### Issue: "ssh: connect to host port 22: Connection refused"

**Solution:**
- Check server is running
- Check firewall allows port 22
- Try SSH to root first, then troubleshoot

### Issue: "sudo: a password is required"

**Solution:**
```bash
# On server, check sudoers file exists
sudo cat /etc/sudoers.d/rosey

# Should show: rosey ALL=(ALL) NOPASSWD: ALL
```

### Issue: Can't remember which key is which

**Solution:**
```powershell
# Show public key fingerprint
ssh-keygen -lf ~\.ssh\rosey_bot_test_deploy.pub

# List all keys
Get-ChildItem ~\.ssh\rosey_bot_*
```

## Cost Estimate

**DigitalOcean:**
- Test: $6/month (1GB Droplet)
- Prod: $12/month (2GB Droplet)
- **Total: ~$18/month**

**AWS Free Tier:**
- First year: $0 (t2.micro free)
- After: ~$8-16/month

**Stop anytime**: Both can be deleted when not needed!

## Next Steps

After validation:
1. Tell me your server IPs
2. Move to **Sortie 2: Configure GitHub Secrets** (I'll guide you through GitHub UI)
3. Then I'll handle systemd services (Sortie 3)

## Time Estimate

- **First time**: 2-4 hours (learning + setup)
- **If you've done this before**: 30-60 minutes
- **With existing servers**: 15-30 minutes

Don't rush! Getting this foundation right makes everything else easier.

## Questions?

Ask me:
- "What command do I run on the server?"
- "How do I check if X is working?"
- "My provider is Y, what settings should I use?"
- "I'm stuck at step Z, help!"

I'm here to help you through every step! 🤖
