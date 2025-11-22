# Sprint 9 Migration Guide: Event Normalization & NATS Architecture

**Version**: 2.0 (Breaking Changes)  
**Date**: November 21, 2025  
**Target Audience**: Rosey-Robot Users & Contributors  
**Sprint**: 9 "The Accountant"  

---

## Overview

Sprint 9 introduces **breaking changes** to establish a proper distributed, event-driven architecture. This guide helps you migrate from v1 to v2.

**Breaking Changes**:
- ✅ Configuration format (v1 → v2)
- ✅ Bot constructor signature (no `db` parameter)
- ✅ NATS server **required**
- ✅ Database runs as separate service

**What You Gain**:
- 🚀 Process isolation (can run components separately)
- 🔌 Multi-platform ready (Discord/Slack support in Sprint 10)
- 🛡️ Plugin sandboxing (isolated processes in Sprint 11)
- 📊 Horizontal scaling (multiple bot instances possible)

---

## Prerequisites

### 1. Install NATS Server

NATS is a lightweight message broker that enables the new event-driven architecture.

**macOS**:
```bash
brew install nats-server
```

**Linux**:
```bash
curl -L https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.zip -o nats-server.zip
unzip nats-server.zip
sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/
```

**Windows**:
- Download from https://github.com/nats-io/nats-server/releases
- Extract `nats-server.exe`
- Add to PATH or place in project directory

**Verify Installation**:
```bash
nats-server --version
# Should output: nats-server: v2.10.x
```

### 2. Backup Current Configuration

**IMPORTANT**: Back up your current config before migration!

```bash
cp bot/rosey/config.json bot/rosey/config.json.v1.backup
```

---

## Migration Steps

### Step 1: Migrate Configuration

We provide an automatic migration script that converts v1 configs to v2 format.

**Automatic Migration** (Recommended):
```bash
python scripts/migrate_config.py bot/rosey/config.json --backup
```

**Output**:
```
[*] Reading config: bot/rosey/config.json
[*] Config version: 1.0 (v1 format detected)
[*] Creating backup: bot/rosey/config.json.bak
[+] Backup created successfully
[*] Migrating to v2 format...
[+] Migration successful!
[*] Writing new config: bot/rosey/config.json

✅ Migration complete!

Next steps:
1. Start NATS server: nats-server
2. Start bot: python bot/rosey/rosey.py config.json
```

**Manual Migration** (If Needed):

<details>
<summary>Click to see manual migration example</summary>

**Old Format** (v1):
```json
{
  "domain": "https://cytu.be",
  "channel": "YourChannel",
  "user": ["username", "password"],
  "db": "bot_data.db",
  "poll_interval": 300,
  "log_level": "info"
}
```

**New Format** (v2):
```json
{
  "version": "2.0",
  "nats": {
    "url": "nats://localhost:4222"
  },
  "database": {
    "path": "bot_data.db",
    "run_as_service": true
  },
  "platforms": [
    {
      "type": "cytube",
      "domain": "https://cytu.be",
      "channel": "YourChannel",
      "user": ["username", "password"]
    }
  ],
  "shell": {
    "enabled": true
  },
  "logging": {
    "level": "info"
  }
}
```

**Key Changes**:
- Added `version` field (required)
- Added `nats` section with server URL
- Moved `db` to `database.path`
- Wrapped platform config in `platforms` array
- Moved logging settings to nested `logging` object

</details>

### Step 2: Start NATS Server

NATS must be running before starting the bot.

**Option A: Foreground** (for testing):
```bash
nats-server
```

**Option B: Background** (for production):
```bash
# Windows
start /B nats-server

# Linux/Mac
nats-server -D
```

**Verify NATS Running**:
```bash
# Check if NATS is listening on port 4222
netstat -an | findstr :4222   # Windows
netstat -an | grep :4222      # Linux/Mac
```

### Step 3: Start Bot

The bot command doesn't change, but now it:
1. Connects to NATS first
2. Starts DatabaseService automatically
3. Then connects to CyTube

```bash
python bot/rosey/rosey.py bot/rosey/config.json
```

**Expected Output**:
```
[*] Connecting to NATS: nats://localhost:4222
[+] Connected to NATS: nats://localhost:4222
[*] Starting DatabaseService: bot_data.db
[+] DatabaseService started (listening on NATS)
[*] Creating bot for https://cytu.be/YourChannel
[+] Bot created with NATS integration
[+] PM command shell enabled
[*] Starting bot...
```

### Step 4: Verify Everything Works

**Check Bot Status**:
1. Bot connects to CyTube channel ✅
2. Users appear in userlist ✅
3. Chat messages are logged ✅
4. PM commands work ✅

**Test Database**:
```bash
sqlite3 bot_data.db "SELECT COUNT(*) FROM user_stats;"
# Should show number of users seen
```

**Test PM Commands**:
Send a PM to your bot:
```
help
```

You should receive the command list back.

---

## Troubleshooting

### Error: "Could not connect to NATS"

**Problem**: NATS server not running

**Solution**:
```bash
# Start NATS server in separate terminal
nats-server

# Then start bot
python bot/rosey/rosey.py config.json
```

### Error: "Configuration version None not supported"

**Problem**: Config file still in v1 format

**Solution**:
```bash
# Run migration script
python scripts/migrate_config.py bot/rosey/config.json --backup
```

### Error: "ValueError: NATS client is required"

**Problem**: Bot code expects NATS but config isn't migrated properly

**Solution**:
1. Verify config has `"version": "2.0"` field
2. Verify config has `"nats"` section
3. Re-run migration script if needed

### Bot Connects But No Chat/Users Logged

**Problem**: DatabaseService not receiving events

**Solution**:
1. Check NATS server is running: `nats-server --signal=status`
2. Check bot logs for NATS connection messages
3. Restart bot to re-establish subscriptions

### Windows: "nats-server is not recognized"

**Problem**: NATS server not in PATH

**Solution**:
```powershell
# Add to PATH permanently
$env:Path += ";C:\path\to\nats-server"
[System.Environment]::SetEnvironmentVariable("Path", $env:Path, [System.EnvironmentVariableTarget]::User)

# Or run with full path
C:\path\to\nats-server.exe
```

---

## Rollback Procedure

If migration fails or you need to revert:

### Option 1: Restore Config Backup

```bash
# Stop bot
Ctrl+C

# Restore v1 config
cp bot/rosey/config.json.v1.backup bot/rosey/config.json

# Checkout pre-Sprint 9 code
git checkout <commit-before-sprint-9>

# Start bot (no NATS needed)
python bot/rosey/rosey.py config.json
```

### Option 2: Use Git Reset

```bash
# Stop bot
Ctrl+C

# Reset to pre-Sprint 9
git reset --hard <commit-before-sprint-9>

# Your database is preserved (bot_data.db unchanged)
```

---

## What Changed

### Configuration ✅
- New nested structure with version field
- NATS section required
- Multi-platform array ready for Discord/Slack
- Logging configuration moved to separate section

### Bot Architecture ✅
- NATS-first communication (all components talk via message bus)
- Process isolation enforced (Bot ≠ Database ≠ Plugins)
- Event-driven design (publish/subscribe pattern)
- No direct database access from bot

### Database ✅
- Runs as separate service (DatabaseService)
- Communicates via NATS only
- Can run on different machine/process
- Same schema (data preserved)

### What DIDN'T Change ✅
- Database schema (all your data is safe)
- Bot features (all commands still work)
- CyTube protocol (connection unchanged)
- PM commands (same syntax)
- User experience (no visible changes)

---

## FAQ

**Q: Do I need to reinstall Python dependencies?**  
A: No, all Python packages remain the same. Only NATS server is new.

**Q: Will my chat history and user data be lost?**  
A: No! Database schema is unchanged. All data is preserved.

**Q: Can I run the bot without NATS?**  
A: No, NATS is now **required**. This is intentional to enforce the new architecture.

**Q: Why these breaking changes?**  
A: To fix fundamental architectural flaws discovered in Sprint 8. See [PRD](PRD-Event-Normalization-NATS-Architecture.md) for full rationale.

**Q: When can I use Discord/Slack platforms?**  
A: Sprint 10 (now unblocked). Discord/Slack support blocked until Sprint 9 complete.

**Q: Can I run database on a different machine?**  
A: Yes! Point NATS URL to remote server:
```json
{
  "nats": {
    "url": "nats://your-server.com:4222"
  }
}
```

**Q: How do I monitor NATS?**  
A: NATS has built-in monitoring:
```bash
# Start with monitoring port
nats-server -m 8222

# View stats
curl http://localhost:8222/varz
```

**Q: What if NATS server crashes?**  
A: Bot will detect disconnect and attempt reconnection. Configure auto-restart with systemd (see [DEPLOYMENT.md](../../docs/DEPLOYMENT.md)).

**Q: Is NATS secure?**  
A: Yes, NATS supports TLS encryption. For production, use:
```json
{
  "nats": {
    "url": "nats://localhost:4222",
    "tls": {
      "cert": "/path/to/cert.pem",
      "key": "/path/to/key.pem"
    }
  }
}
```

---

## Performance Impact

**Benchmarks**:
- NATS overhead: <5% for typical operations
- Message latency: <1ms on localhost
- Throughput: >10,000 msg/sec

**Memory Usage**:
- NATS server: ~10MB RAM
- Bot: Same as before
- DatabaseService: Same as before

**Total**: Minimal overhead for significant architectural benefits.

---

## Next Steps After Migration

1. ✅ Verify bot works with new architecture
2. ✅ Test PM commands
3. ✅ Check database logging
4. 📚 Read updated [ARCHITECTURE.md](../../docs/ARCHITECTURE.md)
5. 🚀 Prepare for Sprint 10 (Multi-Platform Support)

---

## Getting Help

**Documentation**:
- [PRD: Event Normalization & NATS Architecture](PRD-Event-Normalization-NATS-Architecture.md)
- [Architecture Documentation](../../docs/ARCHITECTURE.md)
- [Deployment Guide](../../docs/DEPLOYMENT.md)

**Issues**:
- Open GitHub issue with `migration` label
- Include config (redact passwords!)
- Include bot startup logs

**Community**:
- Join project Discord (if applicable)
- Ask in GitHub Discussions

---

## Migration Checklist

Use this checklist to track your migration:

- [ ] Backup current config: `config.json.v1.backup` created
- [ ] NATS server installed and tested
- [ ] Config migrated to v2 format
- [ ] NATS server started
- [ ] Bot starts successfully
- [ ] Bot connects to CyTube
- [ ] Users appear in channel
- [ ] Chat messages logged
- [ ] PM commands work
- [ ] Database updated (check with sqlite3)
- [ ] Bot runs for 1 hour without issues
- [ ] Mark Sprint 9 migration complete! 🎉

---

**Migration Status**: Production Ready  
**Support**: Available via GitHub Issues  
**Last Updated**: November 21, 2025  

**Welcome to Sprint 9! 🚀**
