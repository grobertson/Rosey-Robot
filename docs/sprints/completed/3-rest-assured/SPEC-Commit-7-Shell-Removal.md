# SPEC: Shell Removal and Final Cleanup

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 7 - Shell Removal  
**Dependencies:** All previous commits  
**Estimated Effort:** Small

---

## Objective

Remove the legacy REPL shell interface now that REST API provides all functionality. Clean up related code, documentation, and deployment configuration.

---

## Changes Required

### 1. Remove Shell Files

Delete the following files:

- `common/shell.py`
- `test_shell.py`

```bash
git rm common/shell.py
git rm test_shell.py
```

### 2. Update README

**File:** `README.md` (update)

Remove the "Using the REPL Shell" section entirely. It should be between "Bot Capabilities" and "LLM Integration" sections.

Find and remove this section:

```markdown
## Using the REPL Shell

[entire section about shell usage]
```

### 3. Update CHANGELOG

**File:** `CHANGELOG.md` (update)

Add entry for this sprint:

```markdown
## [Unreleased]

### Added
- REST API with FastAPI for programmatic bot control
- API key authentication system with PM-based key management
- Chat and system announcement endpoints
- Comprehensive playlist management (single add, bulk add, remove, clear)
- Command-line tool (rosey-cli) for easy API access
- OpenAPI/Swagger documentation at `/docs`
- Postman collection and cURL examples
- API audit logging for security

### Changed
- Bot control moved from shell interface to REST API

### Removed
- REPL shell interface (replaced by REST API)
- Shell telnet access (security improvement)

### Security
- API key authentication with bcrypt hashing
- Per-user API keys tied to moderator accounts
- Request audit logging
- No more telnet-accessible Python REPL
```

### 4. Update Deployment Documentation

**File:** `systemd/README.md` (update)

Remove any shell-related deployment instructions.

Add section for API server deployment:

```markdown
## API Server Deployment

The REST API server should run alongside the bot.

### Install API Service

```bash
# Copy service file
sudo cp systemd/rosey-api.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable API service
sudo systemctl enable rosey-api

# Start API service
sudo systemctl start rosey-api

# Check status
sudo systemctl status rosey-api
```

### Start Both Services

```bash
# Start bot
sudo systemctl start cytube-bot

# Start API
sudo systemctl start rosey-api

# Check both are running
sudo systemctl status cytube-bot rosey-api
```

### Logs

```bash
# Bot logs
sudo journalctl -u cytube-bot -f

# API logs
sudo journalctl -u rosey-api -f

# Both together
sudo journalctl -u cytube-bot -u rosey-api -f
```

### Firewall Configuration

If accessing API from other machines on local network:

```bash
# Allow API port (8080)
sudo ufw allow 8080/tcp

# Or restrict to specific subnet
sudo ufw allow from 192.168.1.0/24 to any port 8080
```

⚠️ **Security Note:** The API is designed for local network access. For internet-facing deployments, use HTTPS with a reverse proxy (nginx, Caddy, etc.).
```

### 5. Update QUICKSTART

**File:** `QUICKSTART.md` (update)

Remove shell-related setup instructions.

Add API setup to the quick start:

```markdown
## 6. Get API Access (Optional)

For programmatic bot control:

1. **Request API Key via PM:**
   - Join your CyTube channel
   - Send PM to bot: `!apikey`
   - Save the key shown (you'll only see it once)

2. **Test API:**
   ```bash
   curl -H "X-API-Key: your-key" http://localhost:8080/api/v1/status
   ```

3. **Use CLI Tool:**
   ```bash
   pip install httpx
   export ROSEY_API_KEY="your-key"
   python tools/rosey_cli.py status
   ```

See [docs/API_EXAMPLES.md](docs/API_EXAMPLES.md) for more.
```

### 6. Update PM_GUIDE

**File:** `PM_GUIDE.md` (update)

Add API key management commands to the PM commands documentation:

```markdown
### API Key Management

Request API access for programmatic bot control:

- `!apikey` - Request your API key (moderators only)
- `!apikey-info` - View API key status (created, last used)
- `!apikey-regenerate` - Generate new API key (revokes old one)
- `!apikey-revoke` - Disable API access

**Example:**
```
You: !apikey
Bot: ✅ Your API key: abc123def456ghi789jkl012mno345pqr
     
     ⚠️ IMPORTANT: Save this key securely!
     This is the ONLY time you'll see the full key.
     
     Usage:
       curl -H 'X-API-Key: {key}' http://localhost:8080/api/v1/status
     
     API Documentation: http://localhost:8080/docs
```

**Security:**
- Keys are hashed and never stored in plaintext
- Only shown once when generated
- Can be regenerated if lost or compromised
- Revoke immediately if compromised

See [docs/API_EXAMPLES.md](docs/API_EXAMPLES.md) for API usage.
```

### 7. Update Architecture Documentation

**File:** `ARCHITECTURE.md` (update if exists, otherwise skip)

Update any diagrams or descriptions that reference the shell interface.

Replace with API server architecture:

```markdown
## REST API Architecture

```
┌─────────────────────────────────────────┐
│         API Clients                     │
│  (CLI, Postman, curl, scripts)          │
└────────────┬────────────────────────────┘
             │ HTTP/REST
             │ (API Key Auth)
┌────────────▼────────────┐
│   FastAPI Server        │
│   (web/api_server.py)   │
│                         │
│ - Authentication        │
│ - Request Logging       │
│ - OpenAPI Docs          │
└───────┬─────────┬───────┘
        │         │
        │         │ (bot_interface)
        │         │
┌───────▼────┐   ┌▼──────────────┐
│ Database   │   │  Bot Process  │
│ (API Keys) │   │  (CyTube)     │
└────────────┘   └───────────────┘
```

**API Server:**
- Runs independently of bot
- Handles HTTP requests with API key auth
- Communicates with bot via shared interface
- Logs all requests to database
- Serves OpenAPI documentation

**Security:**
- API keys hashed with bcrypt
- Per-user authentication
- Request audit logging
- Rate limiting (future)
- Local network access by default
```
```

### 8. Remove Shell Dependencies

**File:** `requirements.txt` (update)

Check if any dependencies were shell-specific and remove if unused:

- Review for any telnet/shell-related packages
- Keep all API-related packages (fastapi, uvicorn, httpx, bcrypt)

### 9. Update .gitignore

**File:** `.gitignore` (update)

Add CLI configuration file:

```
# API keys
.rosey-api-key
```

---

## Testing Checklist

### Verify Shell Removed

1. **Files Deleted:**
   ```bash
   ls common/shell.py  # Should not exist
   ls test_shell.py    # Should not exist
   ```

2. **No Shell Imports:**
   ```bash
   grep -r "import.*shell" --include="*.py" .
   grep -r "from.*shell" --include="*.py" .
   # Should find no references to removed shell module
   ```

3. **Bot Starts Without Shell:**
   ```bash
   python bot/rosey/rosey.py
   # Should start normally without shell errors
   ```

### Verify Documentation Updated

1. **README:**
   - No mention of REPL shell
   - REST API section present
   - Links to API docs work

2. **CHANGELOG:**
   - Contains sprint changes
   - Notes shell removal

3. **QUICKSTART:**
   - No shell setup instructions
   - API setup instructions present

4. **PM_GUIDE:**
   - API key commands documented

### Verify API Works

1. **API Server Starts:**
   ```bash
   python -m web.api_server
   # Should start without errors
   ```

2. **All Endpoints Work:**
   - Test each endpoint via curl or Postman
   - Verify authentication required
   - Check OpenAPI docs at /docs

3. **CLI Tool Works:**
   ```bash
   rosey-cli status
   rosey-cli send "Test"
   # Should work with no shell code
   ```

### Verify Deployment

1. **Systemd Services:**
   ```bash
   sudo systemctl status cytube-bot
   sudo systemctl status rosey-api
   # Both should show active/running
   ```

2. **Logs Clean:**
   ```bash
   sudo journalctl -u cytube-bot -n 50
   sudo journalctl -u rosey-api -n 50
   # No errors about missing shell
   ```

---

## Success Criteria

- ✅ Shell files removed from repository
- ✅ No import errors related to shell
- ✅ Bot starts and runs without shell code
- ✅ README updated, no shell references
- ✅ CHANGELOG documents changes
- ✅ QUICKSTART has API instructions instead of shell
- ✅ PM_GUIDE documents API key commands
- ✅ Architecture docs updated (if applicable)
- ✅ All tests pass
- ✅ API server works independently
- ✅ CLI tool provides all shell functionality

---

## Migration Guide for Users

Create a migration guide for existing users:

**File:** `docs/3-rest-assured/MIGRATION.md` (new)

```markdown
# Migration Guide: Shell to REST API

The REPL shell interface has been replaced with a REST API.

## What Changed?

**Removed:**
- REPL shell (common/shell.py)
- Telnet access
- Interactive Python environment

**Added:**
- REST API with authentication
- Command-line tool (rosey-cli)
- OpenAPI documentation
- Postman collection

## How to Migrate

### Before (Shell):
```python
# Connect via telnet
telnet localhost 5555

# Execute commands
>>> await bot.send_message("Hello")
>>> await bot.add_media("https://youtube.com/...")
```

### After (REST API):
```bash
# Get API key via PM
# In CyTube PM: !apikey

# Use curl
curl -X POST http://localhost:8080/api/v1/chat/send \
  -H "X-API-Key: your-key" \
  -d '{"message": "Hello"}'

# Or use CLI tool
rosey-cli send "Hello"
rosey-cli playlist add "https://youtube.com/..."
```

## Benefits

1. **Security:** No telnet-accessible Python REPL
2. **Authentication:** Per-user API keys
3. **Audit Trail:** All requests logged
4. **Documentation:** Auto-generated OpenAPI docs
5. **Tooling:** Use any HTTP client (curl, Postman, Python, etc.)
6. **Scripting:** Easier to automate with standard REST

## Getting Started

1. **Request API Key:**
   - PM bot: `!apikey`
   - Save key securely

2. **Install CLI Tool:**
   ```bash
   pip install httpx
   export ROSEY_API_KEY="your-key"
   ```

3. **Try Commands:**
   ```bash
   rosey-cli status
   rosey-cli send "Hello from API!"
   rosey-cli playlist list
   ```

4. **Explore Documentation:**
   - Interactive: http://localhost:8080/docs
   - Examples: docs/API_EXAMPLES.md
   - Postman: docs/3-rest-assured/Rosey-API.postman_collection.json

## Questions?

- Check [docs/API_EXAMPLES.md](../API_EXAMPLES.md)
- Review OpenAPI docs at /docs
- Ask in the channel or via PM
```

---

## Rollback Plan

If critical issues discovered after shell removal:

1. **Restore shell files from git:**
   ```bash
   git checkout HEAD~1 common/shell.py test_shell.py
   ```

2. **Restore documentation:**
   ```bash
   git checkout HEAD~1 README.md QUICKSTART.md
   ```

3. **Keep API running** (it's independent and beneficial)

4. **Address issues** then re-attempt removal

---

## Post-Deployment

After successful deployment:

1. **Monitor logs** for any shell-related errors
2. **Gather user feedback** on API/CLI tool
3. **Update wiki/docs** with API examples
4. **Consider additional API features** based on usage

---

## Future Cleanup

After this commit is stable:

- Remove any shell-related TODO comments in code
- Archive old shell documentation to docs/archive/
- Update any external documentation (wiki, etc.)
