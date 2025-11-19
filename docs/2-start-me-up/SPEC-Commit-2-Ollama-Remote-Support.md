# Technical Specification: Commit 2 - Ollama Remote Support

**Commit Title:** Ollama Remote Support  
**Feature:** Remote Ollama Server Connectivity  
**Status:** ✅ Implemented  
**Related PRD Section:** 5.1 Nano-Sprint Deliverables (Item 2), US-003  
**Dependencies:** SPEC-Commit-1-LLM-Foundation.md  
**Target Release:** v0.3.0  

---

## 1. Overview

### 1.1 Purpose

Enable Rosey to connect to Ollama servers running on remote machines, allowing operators to separate the bot instance from the GPU-equipped LLM server. This is critical for production deployments where the bot runs on a lightweight server while the LLM runs on dedicated GPU hardware.

### 1.2 Scope

- Add `ollama_host` configuration parameter
- Modify `_setup_llm()` to initialize Ollama client with custom host
- Validate remote connection during bot startup
- Handle network errors gracefully
- Support both HTTP and HTTPS protocols

### 1.3 Non-Goals

- Load balancing across multiple Ollama servers (future enhancement)
- Authentication/authorization for Ollama server (rely on network security)
- Automatic server discovery (must be explicitly configured)
- SSL certificate management (assume valid certs or HTTP)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-001: Remote Host Configuration**
- Configuration shall accept `ollama_host` field (string)
- Field shall support HTTP URLs (e.g., "http://192.168.1.100:11434")
- Field shall support HTTPS URLs (e.g., "https://ollama.example.com:11434")
- Field shall support hostnames and IP addresses
- Field shall default to "http://localhost:11434" if not specified

**FR-002: Client Initialization**
- `_setup_llm()` shall pass `ollama_host` to Ollama client constructor
- Client shall use configured host for all API requests
- Client shall validate host format (valid URL)
- Client shall log configured host on initialization

**FR-003: Connection Validation**
- Bot shall test connection during `_setup_llm()`
- Bot shall call `ollama.Client.list()` to verify server reachability
- Bot shall log success or failure of connection test
- Bot shall continue startup even if Ollama unavailable (graceful degradation)

**FR-004: Error Handling**
- Bot shall catch network errors (timeout, connection refused, DNS failure)
- Bot shall catch HTTP errors (404, 500, 502, 503)
- Bot shall log detailed error messages
- Bot shall set `self.llm_client = None` on failure
- Bot shall continue operating without LLM functionality

**FR-005: Runtime Request Handling**
- All LLM requests shall use configured remote host
- Network errors during requests shall be caught and logged
- Failed requests shall not crash the bot
- Users shall not receive error messages in chat (silent failure)

### 2.2 Non-Functional Requirements

**NFR-001: Performance**
- Remote requests shall complete within timeout period (30s default)
- Network latency shall be acceptable (<5s for typical requests)
- Bot shall not block on slow remote server

**NFR-002: Reliability**
- Bot shall handle transient network failures
- Bot shall retry failed requests (future enhancement)
- Bot shall function normally with local Ollama (backward compatibility)

**NFR-003: Security**
- Bot shall support HTTPS for encrypted communication
- Bot shall not log sensitive data (API keys, full request bodies)
- Bot should use firewalls/VPNs for production (documented, not enforced)

---

## 3. Design

### 3.1 Architecture

```
Bot.__init__()
    ↓
_setup_llm()
    ↓
    ├─ provider == "ollama"?
    │       ↓
    │   Read ollama_host from config
    │       ↓
    │   ollama.Client(host=ollama_host)
    │       ↓
    │   Test connection with .list()
    │       ↓
    │   ├─ Success: self.llm_client = client
    │   └─ Failure: self.llm_client = None, log error
    ↓
Bot runs with remote Ollama
```

### 3.2 Configuration Schema

**Updated `llm` section:**
```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "ollama_host": "http://192.168.1.100:11434",
    "system_prompt": "...",
    "llm_triggers": ["rosey"],
    "llm_cooldown": 10,
    "max_history_messages": 10
  }
}
```

**Field Details:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ollama_host` | string | No | `"http://localhost:11434"` | Remote Ollama server URL |

**Valid Examples:**
- `"http://localhost:11434"` (default, local server)
- `"http://192.168.1.100:11434"` (LAN IP address)
- `"http://ollama-gpu-server:11434"` (hostname)
- `"https://ollama.example.com:11434"` (HTTPS with domain)
- `"http://10.0.0.5:8080"` (custom port)

**Invalid Examples:**
- `"192.168.1.100:11434"` (missing protocol)
- `"ollama-server"` (missing port and protocol)
- `"ftp://192.168.1.100:11434"` (unsupported protocol)

### 3.3 Network Communication

**Request Flow:**
```
Bot (192.168.1.10)
    ↓ HTTP/HTTPS
    ├─ POST /api/chat
    │  Body: {"model": "llama3.2:3b", "messages": [...]}
    ↓
Ollama Server (192.168.1.100:11434)
    ↓ (processes request on GPU)
    ↓
    ├─ Response: {"message": {"content": "..."}}
    ↓
Bot receives and posts to channel
```

**Network Requirements:**
- Firewall rules: Allow TCP traffic from bot IP to Ollama server on port 11434
- Latency: <100ms recommended for good UX
- Bandwidth: ~10KB per request (varies by context size)

---

## 4. Implementation

### 4.1 Modified Files

**`lib/bot.py`**

#### 4.1.1 Modify `_setup_llm()` Method

```python
async def _setup_llm(self):
    """Initialize LLM provider based on configuration."""
    provider = self.llm_config.get('provider', '').lower()
    
    if provider == 'openai':
        # ... existing OpenAI code ...
        pass
        
    elif provider == 'ollama':
        try:
            import ollama
            
            # Get remote host from config (default to localhost)
            ollama_host = self.llm_config.get('ollama_host', 'http://localhost:11434')
            
            # Initialize client with custom host
            self.llm_client = ollama.Client(host=ollama_host)
            
            # Test connection
            try:
                self.llm_client.list()  # Will raise if server unavailable
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

#### 4.1.2 Update `_handle_llm_chat()` Error Handling

```python
async def _handle_llm_chat(self, username: str, message: str):
    """Generate and send LLM response."""
    # ... existing code ...
    
    try:
        # ... existing code ...
        
        if provider == 'ollama':
            response = self.llm_client.chat(
                model=model,
                messages=messages
            )
            reply = response['message']['content'].strip()
        
        # ... existing code ...
        
    except ConnectionError as e:
        self.logger.error('LLM connection error: %s', e)
        # Don't send error to chat, fail silently
    except TimeoutError as e:
        self.logger.error('LLM timeout: %s', e)
    except Exception as e:
        self.logger.error('LLM error: %s', e, exc_info=True)
```

### 4.2 Configuration Files

**`bot/rosey/config.json.dist`**

Update with `ollama_host` field:
```json
{
  "llm": {
    "enabled": false,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "ollama_host": "http://localhost:11434",
    "openai_api_key": "",
    "system_prompt": "You are Rosey, a helpful assistant in a CyTube chat.",
    "llm_triggers": ["rosey", "@rosey"],
    "llm_cooldown": 10,
    "max_history_messages": 10
  }
}
```

### 4.3 Environment Variables (Optional)

**Support via systemd (future commit):**
```bash
# /etc/systemd/system/cytube-bot.service
[Service]
Environment="OLLAMA_HOST=http://192.168.1.100:11434"
```

**Code to read environment variable:**
```python
import os

ollama_host = os.getenv('OLLAMA_HOST') or \
              self.llm_config.get('ollama_host', 'http://localhost:11434')
```

---

## 5. Testing

### 5.1 Unit Tests

**Test Default Host:**
```python
def test_ollama_default_host():
    config = {"provider": "ollama", "model": "llama3.2"}
    bot = Bot(llm_config=config)
    # Verify client initialized with localhost
    assert bot.llm_client.host == "http://localhost:11434"
```

**Test Custom Host:**
```python
def test_ollama_custom_host():
    config = {
        "provider": "ollama",
        "model": "llama3.2",
        "ollama_host": "http://192.168.1.100:11434"
    }
    bot = Bot(llm_config=config)
    assert bot.llm_client.host == "http://192.168.1.100:11434"
```

**Test Invalid Host:**
```python
def test_ollama_invalid_host():
    config = {
        "provider": "ollama",
        "model": "llama3.2",
        "ollama_host": "not-a-valid-url"
    }
    bot = Bot(llm_config=config)
    # Should log error, client should be None
    assert bot.llm_client is None
```

### 5.2 Integration Tests

**Test Remote Server Connection:**
```bash
# Set up remote Ollama server on 192.168.1.100
ssh user@192.168.1.100
ollama serve

# On bot machine
cat > test-config.json <<EOF
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "ollama_host": "http://192.168.1.100:11434"
  }
}
EOF

# Run bot
python -m lib test-config.json

# Verify in logs:
# "LLM enabled: provider=ollama, model=llama3.2:3b, host=http://192.168.1.100:11434"
```

**Test Network Failure:**
```bash
# Configure unreachable host
"ollama_host": "http://192.168.1.200:11434"

# Start bot
# Verify log: "Ollama server unavailable at http://192.168.1.200:11434: ..."
# Verify bot continues running
```

**Test HTTPS Connection:**
```bash
# Set up Ollama with TLS (nginx reverse proxy)
"ollama_host": "https://ollama.example.com:443"

# Run bot, verify HTTPS used
```

### 5.3 Manual Test Checklist

- [ ] Bot starts with `ollama_host` pointing to local server (localhost)
- [ ] Bot starts with `ollama_host` pointing to remote server (LAN IP)
- [ ] Bot logs successful connection to remote server
- [ ] Bot sends message to channel, receives LLM response from remote server
- [ ] Bot handles remote server being down gracefully (no crash)
- [ ] Bot handles network timeout gracefully
- [ ] Bot handles DNS resolution failure gracefully
- [ ] Bot works with HTTPS Ollama server

---

## 6. Acceptance Criteria

- [x] Configuration accepts `ollama_host` field
- [x] `_setup_llm()` passes `ollama_host` to Ollama client
- [x] Bot tests connection during startup with `.list()` call
- [x] Bot logs configured host on successful initialization
- [x] Bot logs error if remote server unreachable
- [x] Bot sets `llm_client = None` on connection failure
- [x] Bot continues startup despite Ollama unavailability
- [x] Bot handles network errors during LLM requests
- [x] Bot supports HTTP and HTTPS protocols
- [x] Bot supports IP addresses and hostnames
- [x] Default value is "http://localhost:11434" for backward compatibility

---

## 7. Deployment

### 7.1 Deployment Steps

**For Local Ollama (no changes):**
1. Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
2. Pull model: `ollama pull llama3.2:3b`
3. Start server: `ollama serve` (or use systemd)
4. Configure bot with default `ollama_host` (or omit)

**For Remote Ollama:**
1. **On GPU server (192.168.1.100):**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Pull model
   ollama pull llama3.2:3b
   
   # Start server (listen on all interfaces)
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   
   # OR use systemd
   sudo nano /etc/systemd/system/ollama.service
   # Set: Environment="OLLAMA_HOST=0.0.0.0:11434"
   sudo systemctl enable --now ollama
   
   # Configure firewall
   sudo ufw allow 11434/tcp
   ```

2. **On bot server (192.168.1.10):**
   ```bash
   # Update config.json
   nano bot/rosey/config.json
   # Set: "ollama_host": "http://192.168.1.100:11434"
   
   # Test connection
   curl http://192.168.1.100:11434/api/tags
   
   # Start bot
   python -m lib bot/rosey/config.json
   ```

3. **Verify:**
   ```bash
   # Check bot logs
   journalctl -u cytube-bot -f | grep "LLM enabled"
   # Should see: "host=http://192.168.1.100:11434"
   ```

### 7.2 Network Configuration

**Firewall Rules (on Ollama server):**
```bash
# iptables
sudo iptables -A INPUT -p tcp --dport 11434 -s 192.168.1.10 -j ACCEPT

# ufw
sudo ufw allow from 192.168.1.10 to any port 11434

# firewalld
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="192.168.1.10" port protocol="tcp" port="11434" accept'
sudo firewall-cmd --reload
```

**SSH Tunnel (alternative for secure access):**
```bash
# On bot server
ssh -L 11434:localhost:11434 user@192.168.1.100 -N -f

# Configure bot to use localhost (tunnel forwards to remote)
"ollama_host": "http://localhost:11434"
```

### 7.3 Rollback Plan

If remote Ollama causes issues:
1. Change `ollama_host` to `"http://localhost:11434"`
2. Install Ollama locally: `curl -fsSL https://ollama.ai/install.sh | sh`
3. Pull model locally: `ollama pull llama3.2:3b`
4. Start local server: `ollama serve`
5. Restart bot

---

## 8. Monitoring and Troubleshooting

### 8.1 Health Checks

**Check Ollama Server:**
```bash
# From bot server
curl http://192.168.1.100:11434/api/tags

# Should return JSON with model list
# {"models":[{"name":"llama3.2:3b",...}]}
```

**Check Network Connectivity:**
```bash
# Ping server
ping 192.168.1.100

# Check port
nc -zv 192.168.1.100 11434
# or
telnet 192.168.1.100 11434
```

**Check Bot Logs:**
```bash
# Look for successful connection
journalctl -u cytube-bot | grep "LLM enabled"

# Look for connection errors
journalctl -u cytube-bot | grep "Ollama server unavailable"

# Look for runtime errors
journalctl -u cytube-bot | grep "LLM connection error"
```

### 8.2 Common Issues

**Issue: "Ollama server unavailable"**
- **Cause**: Server not running or unreachable
- **Solution**: 
  1. Check Ollama service: `systemctl status ollama`
  2. Check firewall rules
  3. Test with curl: `curl http://192.168.1.100:11434/api/tags`

**Issue: "Connection timeout"**
- **Cause**: Network latency or slow server
- **Solution**:
  1. Check network latency: `ping -c 10 192.168.1.100`
  2. Increase timeout in code (future enhancement)
  3. Use faster model (e.g., llama3.2:3b instead of 70b)

**Issue: "DNS resolution failed"**
- **Cause**: Hostname not resolvable
- **Solution**:
  1. Use IP address instead: `"ollama_host": "http://192.168.1.100:11434"`
  2. Or add to /etc/hosts: `192.168.1.100 ollama-server`

**Issue: Bot works locally but not remotely**
- **Cause**: Ollama listening on localhost only
- **Solution**: Set `OLLAMA_HOST=0.0.0.0:11434` on Ollama server

### 8.3 Performance Monitoring

**Metrics to Track:**
- Network latency to Ollama server (ping time)
- LLM request duration (should be <5s for remote)
- Network errors per hour
- Ollama server CPU/GPU usage

**Sample Monitoring Script:**
```bash
#!/bin/bash
# monitor-ollama.sh

while true; do
  # Check if Ollama is reachable
  if curl -sf http://192.168.1.100:11434/api/tags > /dev/null; then
    echo "$(date): Ollama OK"
  else
    echo "$(date): Ollama DOWN" | tee -a /var/log/ollama-monitor.log
    # Send alert (email, Slack, etc.)
  fi
  sleep 60
done
```

---

## 9. Documentation Updates

### 9.1 README.md

Add section on remote Ollama setup:
```markdown
### Remote Ollama Setup

To run Ollama on a separate GPU server:

1. **On GPU server:**
   ```bash
   # Install and start Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   
   # Configure firewall
   sudo ufw allow from <bot-ip> to any port 11434
   ```

2. **In bot config.json:**
   ```json
   "llm": {
     "provider": "ollama",
     "ollama_host": "http://<gpu-server-ip>:11434"
   }
   ```

3. **Test connection:**
   ```bash
   curl http://<gpu-server-ip>:11434/api/tags
   ```
```

### 9.2 ARCHITECTURE.md

Update network diagram to show remote Ollama:
```
Bot Server (192.168.1.10)
    ↓ HTTP
    └─> Ollama Server (192.168.1.100:11434)
            ↓ GPU inference
            └─> Response
```

---

## 10. Security Considerations

### 10.1 Network Security

**Recommended Practices:**
- Use HTTPS for production (set up reverse proxy with TLS)
- Restrict Ollama server to internal network only
- Use firewall rules to allow only bot IP
- Consider VPN for cross-datacenter deployments
- Avoid exposing Ollama port to public internet

**Example Nginx Reverse Proxy with TLS:**
```nginx
server {
    listen 443 ssl;
    server_name ollama.example.com;
    
    ssl_certificate /etc/letsencrypt/live/ollama.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ollama.example.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:11434;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Bot config with HTTPS:**
```json
"ollama_host": "https://ollama.example.com"
```

### 10.2 Authentication

**Current State:** No authentication (rely on network security)

**Future Enhancement:** 
- API key authentication (if Ollama adds support)
- mTLS (mutual TLS) for client authentication
- VPN-only access

---

## 11. Related Specifications

- **SPEC-Commit-1-LLM-Foundation.md**: Prerequisite (defines `_setup_llm()`)
- **SPEC-Commit-5-Deployment-Automation.md**: Uses `OLLAMA_HOST` env var

---

## 12. Sign-Off

**Specification Author:** GitHub Copilot  
**Review Date:** 2025-11-10  
**Implementation Status:** ✅ Complete  
**Next Commit:** Commit 3 - Trigger System Refinement
