# Technical Specification: Commit 5 - Deployment Automation

**Commit Title:** Deployment Automation  
**Feature:** Systemd Service Configuration for Production Deployment  
**Status:** ✅ Implemented  
**Related PRD Section:** 5.1 Nano-Sprint Deliverables (Item 5), US-010  
**Dependencies:** SPEC-Commit-2-Ollama-Remote-Support.md  
**Target Release:** v2.1.0  

---

## 1. Overview

### 1.1 Purpose

Provide production-ready systemd service configuration for deploying Rosey with LLM integration, including support for remote Ollama servers via environment variables and proper service management for reliability and monitoring.

### 1.2 Scope

- Update systemd service file with LLM-related environment variables
- Add `OLLAMA_HOST` environment variable support
- Document deployment procedures
- Configure automatic restart on failure
- Set up proper logging to systemd journal
- Ensure service runs as non-root user

### 1.3 Non-Goals

- Docker/Kubernetes deployment (future enhancement)
- Multi-instance deployment (future enhancement)
- Blue/green deployments
- Automated provisioning/Ansible playbooks

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-001: Systemd Service File**
- Service file shall be named `cytube-bot.service`
- Service shall run bot with correct Python environment
- Service shall set working directory to bot directory
- Service shall pass configuration file path as argument

**FR-002: Environment Variables**
- Service shall support `OLLAMA_HOST` environment variable
- Service shall support `OPENAI_API_KEY` environment variable (optional)
- Environment variables shall override config file settings
- Service shall document all supported environment variables

**FR-003: Service Management**
- Service shall start automatically on boot (`enabled`)
- Service shall restart automatically on failure
- Service shall use `Restart=always` with delay
- Service shall depend on `network.target`

**FR-004: Logging**
- Service shall log to systemd journal
- Logs shall include service name and timestamp
- Logs shall be accessible via `journalctl`
- Standard output and error shall be captured

**FR-005: Security**
- Service shall run as non-root user
- Service shall use dedicated user account (e.g., `cytube`)
- Service shall have minimal permissions
- Service shall protect API keys in environment

### 2.2 Non-Functional Requirements

**NFR-001: Reliability**
- Service shall achieve >99.5% uptime
- Service shall recover from crashes automatically
- Service shall handle graceful shutdown (SIGTERM)

**NFR-002: Maintainability**
- Service file shall be well-documented
- Service shall follow systemd best practices
- Service shall be easy to enable/disable/restart

---

## 3. Design

### 3.1 Systemd Service Structure

**File:** `systemd/cytube-bot.service`

```ini
[Unit]
Description=CyTube Bot (Rosey) with LLM Integration
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=cytube
Group=cytube
WorkingDirectory=/opt/rosey-robot
ExecStart=/opt/rosey-robot/venv/bin/python -m lib bot/rosey/config.json

# Environment variables
Environment="PYTHONUNBUFFERED=1"
Environment="OLLAMA_HOST=http://localhost:11434"
# Environment="OPENAI_API_KEY=sk-..."

# Restart policy
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=60

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cytube-bot

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/rosey-robot

[Install]
WantedBy=multi-user.target
```

### 3.2 Environment Variable Support

**In Code (`lib/bot.py`):**

```python
async def _setup_llm(self):
    """Initialize LLM provider with environment variable support."""
    import os
    
    provider = self.llm_config.get('provider', '').lower()
    
    if provider == 'ollama':
        # Environment variable overrides config file
        ollama_host = os.getenv('OLLAMA_HOST') or \
                     self.llm_config.get('ollama_host', 'http://localhost:11434')
        
        self.llm_client = ollama.Client(host=ollama_host)
        self.logger.info('LLM enabled: provider=ollama, host=%s', ollama_host)
    
    elif provider == 'openai':
        # Environment variable overrides config file
        api_key = os.getenv('OPENAI_API_KEY') or \
                 self.llm_config.get('openai_api_key')
        
        if not api_key:
            self.logger.error('OpenAI API key not provided')
            return
        
        self.llm_client = openai.OpenAI(api_key=api_key)
        self.logger.info('LLM enabled: provider=openai')
```

### 3.3 Directory Structure

```
/opt/rosey-robot/          # Installation directory
├── lib/                   # Bot library
│   └── bot.py
├── common/                # Common modules
├── bot/rosey/             # Bot configuration
│   └── config.json
├── venv/                  # Python virtual environment
├── logs/                  # Log files (optional)
└── data/                  # Database files

/etc/systemd/system/       # Systemd services
├── cytube-bot.service
└── cytube-web.service     # Separate web dashboard service

/var/log/journal/          # Systemd journal (auto-managed)
```

---

## 4. Implementation

### 4.1 Modified Files

**`systemd/cytube-bot.service`**

**Before (if existed):**
```ini
[Unit]
Description=CyTube Bot

[Service]
ExecStart=/usr/bin/python3 /opt/rosey/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**After (Commit 5):**
```ini
[Unit]
Description=CyTube Bot (Rosey) with LLM Integration
After=network.target
Wants=network-online.target
Documentation=https://github.com/grobertson/Rosey-Robot

[Service]
Type=simple
User=cytube
Group=cytube
WorkingDirectory=/opt/rosey-robot

# Main process
ExecStart=/opt/rosey-robot/venv/bin/python -m lib bot/rosey/config.json

# Environment variables for LLM integration
Environment="PYTHONUNBUFFERED=1"
Environment="OLLAMA_HOST=http://localhost:11434"
# Environment="OPENAI_API_KEY=sk-..."
# To use remote Ollama, set: Environment="OLLAMA_HOST=http://192.168.1.100:11434"

# Restart policy
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=60

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=cytube-bot

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/rosey-robot
# ReadOnlyPaths=/etc/rosey-robot  # If using separate config directory

[Install]
WantedBy=multi-user.target
```

### 4.2 Documentation Updates

**`systemd/README.md`** (updated):

```markdown
# Systemd Deployment

## Installation

### 1. Create User

```bash
sudo useradd -r -s /bin/false cytube
sudo usermod -aG cytube $(whoami)  # Add yourself to group
```

### 2. Install Bot

```bash
# Clone repository
sudo mkdir -p /opt/rosey-robot
sudo chown cytube:cytube /opt/rosey-robot
cd /opt/rosey-robot
git clone https://github.com/grobertson/Rosey-Robot.git .

# Set up virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Bot

```bash
# Copy and edit configuration
cp bot/rosey/config.json.dist bot/rosey/config.json
nano bot/rosey/config.json

# Set permissions
chmod 600 bot/rosey/config.json
chown cytube:cytube bot/rosey/config.json
```

### 4. Install Service

```bash
# Copy service file
sudo cp systemd/cytube-bot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start service
sudo systemctl enable cytube-bot
sudo systemctl start cytube-bot

# Check status
sudo systemctl status cytube-bot
```

## Configuration

### Environment Variables

Edit `/etc/systemd/system/cytube-bot.service`:

```ini
[Service]
# For remote Ollama
Environment="OLLAMA_HOST=http://192.168.1.100:11434"

# For OpenAI (if not in config.json)
Environment="OPENAI_API_KEY=sk-proj-..."
```

After editing, reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart cytube-bot
```

### Using Environment File

Alternatively, use an environment file:

1. Create `/etc/rosey-robot/env`:
   ```bash
   OLLAMA_HOST=http://192.168.1.100:11434
   OPENAI_API_KEY=sk-proj-...
   ```

2. Update service file:
   ```ini
   [Service]
   EnvironmentFile=/etc/rosey-robot/env
   ```

3. Reload:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart cytube-bot
   ```

## Management

### Start/Stop/Restart

```bash
sudo systemctl start cytube-bot    # Start service
sudo systemctl stop cytube-bot     # Stop service
sudo systemctl restart cytube-bot  # Restart service
sudo systemctl status cytube-bot   # Check status
```

### Enable/Disable Auto-Start

```bash
sudo systemctl enable cytube-bot   # Start on boot
sudo systemctl disable cytube-bot  # Don't start on boot
```

### View Logs

```bash
# Recent logs
sudo journalctl -u cytube-bot -n 100

# Follow logs (live)
sudo journalctl -u cytube-bot -f

# Logs since boot
sudo journalctl -u cytube-bot -b

# Logs for specific date
sudo journalctl -u cytube-bot --since "2025-11-10 00:00:00"

# Logs with specific log level
sudo journalctl -u cytube-bot -p err  # Only errors
```

## Monitoring

### Check Service Health

```bash
# Status
systemctl is-active cytube-bot    # Returns: active/inactive
systemctl is-enabled cytube-bot   # Returns: enabled/disabled
systemctl is-failed cytube-bot    # Returns: failed/active

# Detailed status
sudo systemctl status cytube-bot

# Process info
ps aux | grep "python -m lib"
```

### Resource Usage

```bash
# CPU and memory
sudo systemctl status cytube-bot  # Shows memory/CPU in status

# Detailed resource usage
systemd-cgtop  # Press 'c' to sort by CPU, 'm' for memory

# Specific service
systemd-cgtop | grep cytube-bot
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs for errors
sudo journalctl -u cytube-bot -n 50

# Common issues:
# 1. Permission denied
sudo chown -R cytube:cytube /opt/rosey-robot

# 2. Python not found
ls -la /opt/rosey-robot/venv/bin/python

# 3. Config file missing
ls -la /opt/rosey-robot/bot/rosey/config.json
```

### Service Keeps Restarting

```bash
# Check restart count
sudo systemctl status cytube-bot | grep "Started"

# View crash logs
sudo journalctl -u cytube-bot | grep "Failed\|Error\|Exception"

# Disable auto-restart temporarily for debugging
sudo systemctl edit cytube-bot
# Add: [Service]
#      Restart=no
sudo systemctl daemon-reload
sudo systemctl restart cytube-bot
```

### LLM Not Working

```bash
# Check environment variables
sudo systemctl show cytube-bot | grep Environment

# Test Ollama connectivity
curl http://localhost:11434/api/tags
# or
curl $OLLAMA_HOST/api/tags

# Check bot logs for LLM errors
sudo journalctl -u cytube-bot | grep LLM
```

## Security

### Protect API Keys

```bash
# Use environment file with restricted permissions
sudo nano /etc/rosey-robot/env
sudo chmod 600 /etc/rosey-robot/env
sudo chown root:cytube /etc/rosey-robot/env
```

### Harden Service

Edit service file to add:
```ini
[Service]
# Prevent privilege escalation
NoNewPrivileges=true

# Isolate temporary files
PrivateTmp=true

# Read-only system directories
ProtectSystem=strict
ProtectHome=true

# Restrict network access (if needed)
# IPAddressDeny=any
# IPAddressAllow=localhost
```

## Upgrades

```bash
# 1. Stop service
sudo systemctl stop cytube-bot

# 2. Backup config
sudo cp /opt/rosey-robot/bot/rosey/config.json /opt/rosey-robot/config.json.backup

# 3. Pull updates
cd /opt/rosey-robot
sudo -u cytube git pull

# 4. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 5. Restart service
sudo systemctl start cytube-bot

# 6. Check status
sudo systemctl status cytube-bot
```
```

### 4.3 Code Changes

**`lib/bot.py`** (update `_setup_llm()`):

```python
import os

async def _setup_llm(self):
    """Initialize LLM provider with environment variable support."""
    provider = self.llm_config.get('provider', '').lower()
    
    if provider == 'openai':
        try:
            import openai
            # Environment variable overrides config
            api_key = os.getenv('OPENAI_API_KEY') or \
                     self.llm_config.get('openai_api_key')
            
            if not api_key:
                self.logger.error('OpenAI API key not provided')
                return
            
            self.llm_client = openai.OpenAI(api_key=api_key)
            self.logger.info('LLM enabled: provider=openai, model=%s', 
                           self.llm_config.get('model'))
        except ImportError:
            self.logger.error('openai library not installed: pip install openai')
            
    elif provider == 'ollama':
        try:
            import ollama
            # Environment variable overrides config
            ollama_host = os.getenv('OLLAMA_HOST') or \
                         self.llm_config.get('ollama_host', 'http://localhost:11434')
            
            self.llm_client = ollama.Client(host=ollama_host)
            
            # Test connection
            try:
                self.llm_client.list()
                self.logger.info('LLM enabled: provider=ollama, model=%s, host=%s', 
                               self.llm_config.get('model'), ollama_host)
            except Exception as conn_error:
                self.logger.error('Ollama server unavailable at %s: %s', 
                                ollama_host, conn_error)
                self.llm_client = None
                
        except ImportError:
            self.logger.error('ollama library not installed: pip install ollama')
            self.llm_client = None
    else:
        self.logger.error('Unknown LLM provider: %s', provider)
```

---

## 5. Testing

### 5.1 Installation Test

```bash
# Test service file syntax
systemd-analyze verify systemd/cytube-bot.service

# Expected output: (no errors)
```

### 5.2 Deployment Test

**Full Deployment Test:**

1. **Install on test VM:**
   ```bash
   # Set up fresh Ubuntu/Debian VM
   sudo apt update
   sudo apt install python3 python3-venv git
   
   # Follow installation steps
   # ...
   ```

2. **Verify service starts:**
   ```bash
   sudo systemctl start cytube-bot
   sudo systemctl status cytube-bot
   # Expected: "Active: active (running)"
   ```

3. **Verify logging:**
   ```bash
   sudo journalctl -u cytube-bot -n 20
   # Expected: Bot initialization logs, LLM setup, connection logs
   ```

4. **Verify auto-restart:**
   ```bash
   # Kill bot process
   sudo pkill -f "python -m lib"
   
   # Wait 10 seconds
   sleep 10
   
   # Check if restarted
   sudo systemctl status cytube-bot
   # Expected: "Active: active (running)" with recent restart timestamp
   ```

5. **Verify boot persistence:**
   ```bash
   sudo systemctl enable cytube-bot
   sudo reboot
   
   # After reboot
   sudo systemctl status cytube-bot
   # Expected: "Active: active (running)" and "enabled"
   ```

### 5.3 Environment Variable Test

```bash
# Edit service file
sudo nano /etc/systemd/system/cytube-bot.service

# Change:
Environment="OLLAMA_HOST=http://test-server:11434"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart cytube-bot

# Check logs
sudo journalctl -u cytube-bot -n 10 | grep "LLM enabled"

# Expected: "host=http://test-server:11434"
```

---

## 6. Acceptance Criteria

- [x] Systemd service file created/updated
- [x] Service includes `OLLAMA_HOST` environment variable
- [x] Service supports `OPENAI_API_KEY` environment variable
- [x] Service restarts automatically on failure
- [x] Service starts on boot when enabled
- [x] Service runs as non-root user (`cytube`)
- [x] Service logs to systemd journal
- [x] Service file includes documentation comments
- [x] README documents installation procedure
- [x] README documents configuration options
- [x] README documents management commands
- [x] README documents troubleshooting steps

---

## 7. Deployment

### 7.1 Production Deployment Checklist

- [ ] Create `cytube` user account
- [ ] Install bot to `/opt/rosey-robot`
- [ ] Set up Python virtual environment
- [ ] Install dependencies from `requirements.txt`
- [ ] Copy and configure `config.json`
- [ ] Set file permissions (`chmod 600 config.json`)
- [ ] Copy `cytube-bot.service` to `/etc/systemd/system/`
- [ ] Edit service file (set `OLLAMA_HOST` if remote)
- [ ] Run `systemctl daemon-reload`
- [ ] Run `systemctl enable cytube-bot`
- [ ] Run `systemctl start cytube-bot`
- [ ] Verify logs with `journalctl -u cytube-bot -f`
- [ ] Test auto-restart (kill process, wait, check status)
- [ ] Configure firewall (if needed)
- [ ] Set up monitoring/alerts

### 7.2 Post-Deployment Verification

```bash
# 1. Service is running
systemctl is-active cytube-bot  # Returns: active

# 2. Service is enabled
systemctl is-enabled cytube-bot  # Returns: enabled

# 3. Bot connected to CyTube
sudo journalctl -u cytube-bot | grep "Connected\|Logged in"

# 4. LLM initialized
sudo journalctl -u cytube-bot | grep "LLM enabled"

# 5. No errors
sudo journalctl -u cytube-bot -p err --since "1 hour ago"
# Expected: no output (or only transient errors)
```

---

## 8. Documentation Updates

### 8.1 README.md

Add systemd deployment section:
```markdown
## Production Deployment

For production use, deploy Rosey as a systemd service:

1. Install to `/opt/rosey-robot`
2. Create `cytube` user
3. Configure `bot/rosey/config.json`
4. Install systemd service
5. Enable and start service

See [systemd/README.md](systemd/README.md) for detailed instructions.
```

### 8.2 ARCHITECTURE.md

Add deployment section:
```markdown
## Deployment

Rosey supports multiple deployment methods:

- **Systemd** (recommended for production)
  - Automatic restart on failure
  - Boot persistence
  - Centralized logging via journalctl
  
- **Docker** (future)
  - Containerized deployment
  - Easy scaling
  
- **Manual** (development)
  - Run directly: `python -m lib bot/rosey/config.json`
```

---

## 9. Related Specifications

- **SPEC-Commit-2-Ollama-Remote-Support.md**: `OLLAMA_HOST` environment variable
- **SPEC-Commit-1-LLM-Foundation.md**: LLM configuration

---

## 10. Sign-Off

**Specification Author:** GitHub Copilot  
**Review Date:** 2025-11-10  
**Implementation Status:** ✅ Complete  
**Next Commit:** Commit 6 - Documentation & PR
