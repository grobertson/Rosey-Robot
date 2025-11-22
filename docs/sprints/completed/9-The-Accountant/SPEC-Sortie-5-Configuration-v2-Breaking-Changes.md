# Technical Specification: Configuration v2 & Breaking Changes

**Sprint**: Sprint 9 "The Accountant"  
**Sortie**: 5 of 6  
**Status**: Ready for Implementation  
**Estimated Effort**: 4-5 hours  
**Dependencies**: Sortie 1-4 MUST be complete  
**Blocking**: Sortie 6 (Testing & Documentation)  

---

## Overview

**Purpose**: Implement Configuration v2 format that reflects distributed NATS-first architecture, and enforce breaking changes by removing `db` parameter from bot constructor. This is the **final breaking changes commit** that completes the architectural transformation.

**Scope**:
- New configuration format (`config.json` v2 schema)
- Remove `db` parameter from `Bot.__init__()`
- Make NATS client mandatory (not optional)
- Configuration migration script
- Update bot instantiation in `bot/rosey/rosey.py`

**Key Principle**: *"NATS is not optional."* — Sprint 9 PRD

**⚠️ WARNING**: This sortie contains BREAKING CHANGES. After this commit:
- Old configuration format will not work
- Bot requires NATS server running
- `db` parameter removed from bot constructor

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: New configuration format MUST be platform-agnostic and distributed-first  
**FR-002**: Bot constructor MUST require NATS client (no longer optional)  
**FR-003**: Bot constructor MUST NOT accept `db` parameter (hard boundary enforced)  
**FR-004**: Configuration migration script MUST convert old format to new  
**FR-005**: Bot initialization MUST start DatabaseService separately  
**FR-006**: NATS connection details MUST be in configuration  

### 1.2 Non-Functional Requirements

**NFR-001**: Configuration validation with clear error messages  
**NFR-002**: Migration script preserves all settings  
**NFR-003**: Backward compatibility explicitly NOT maintained (breaking changes)  

---

## 2. Configuration v2 Format

### 2.1 Old Format (v1 - Current)

**File**: `bot/rosey/config.json` (current)

```json
{
  "domain": "https://cytu.be",
  "channel": "YourChannelName",
  "user": ["YourUsername", "YourPassword"],
  "shell": "localhost:5555",
  "db": "bot_data.db",
  "llm": { ... }
}
```

**Problems**:
- Flat structure, platform-specific
- Database path in main config (not separate service)
- No NATS configuration
- Assumes single platform (CyTube)

### 2.2 New Format (v2 - Target)

**File**: `bot/rosey/config.json` (NEW)

```json
{
  "version": "2.0",
  
  "nats": {
    "url": "nats://localhost:4222",
    "connection_timeout": 5,
    "max_reconnect_attempts": -1,
    "reconnect_delay": 2
  },
  
  "database": {
    "path": "bot_data.db",
    "run_as_service": true
  },
  
  "platforms": [
    {
      "type": "cytube",
      "name": "primary",
      "enabled": true,
      "domain": "https://cytu.be",
      "channel": "YourChannelName",
      "user": ["YourUsername", "YourPassword"],
      "response_timeout": 1,
      "restart_delay": 5
    }
  ],
  
  "shell": {
    "enabled": true,
    "host": "localhost",
    "port": 5555
  },
  
  "logging": {
    "level": "WARNING",
    "chat_log_file": "chat.log",
    "media_log_file": "media.log"
  },
  
  "llm": {
    "enabled": false,
    "provider": "ollama",
    "system_prompt_file": "prompt.md",
    "max_context_messages": 10,
    "temperature": 0.7,
    "max_tokens": 500,
    "log_only": false,
    "openai": { ... },
    "ollama": { ... },
    "triggers": { ... }
  },
  
  "plugins": {
    "enabled": true,
    "directory": "plugins/",
    "auto_reload": false
  }
}
```

**Key Changes**:
1. **`version` field**: Explicit version for validation
2. **`nats` section**: NATS connection configuration (REQUIRED)
3. **`database` section**: Database as separate service
4. **`platforms` array**: Multi-platform support ready (currently one CyTube)
5. **`shell` object**: Structured shell configuration
6. **`logging` object**: Separate logging configuration
7. **`plugins` section**: Plugin system configuration (future-ready)

---

## 3. Bot Constructor Changes

### 3.1 Current Constructor (v1)

**File**: `lib/bot.py`

```python
def __init__(self, connection, channel_name, logger=None, db=None, nats_client=None):
    """Initialize bot.
    
    Args:
        connection: CyTube connection
        channel_name: Channel to join
        logger: Optional logger
        db: Optional database (DEPRECATED - use nats_client)
        nats_client: Optional NATS client (RECOMMENDED)
    """
    self.connection = connection
    self.channel_name = channel_name
    self.logger = logger or logging.getLogger(__name__)
    self.db = db  # ❌ REMOVE
    self.nats = nats_client
```

### 3.2 New Constructor (v2 - BREAKING)

**File**: `lib/bot.py`

```python
def __init__(self, connection, channel_name, nats_client, logger=None):
    """Initialize bot.
    
    Args:
        connection: CyTube connection
        channel_name: Channel to join
        nats_client: NATS client (REQUIRED - not optional)
        logger: Optional logger
        
    Note:
        The `db` parameter has been REMOVED. All database operations
        now go through NATS event bus. See Sprint 9 migration guide.
    """
    self.connection = connection
    self.channel_name = channel_name
    self.nats = nats_client  # REQUIRED, not optional
    self.logger = logger or logging.getLogger(__name__)
    
    # Validate NATS client
    if self.nats is None:
        raise ValueError(
            "NATS client is required. Bot cannot operate without NATS. "
            "See docs/sprints/upcoming/9-The-Accountant/MIGRATION.md"
        )
    
    # NO self.db - REMOVED
```

**Breaking Changes**:
- `db` parameter REMOVED
- `nats_client` parameter now REQUIRED (not optional)
- ValueError raised if NATS client is None
- Constructor signature incompatible with v1

---

## 4. Bot Initialization Changes

### 4.1 Current Initialization (v1)

**File**: `bot/rosey/rosey.py`

```python
# Load config
with open('config.json') as f:
    config = json.load(f)

# Create database
db = BotDatabase(config.get('db', 'bot_data.db'))

# Create bot
bot = Bot(connection, channel, logger=logger, db=db)
```

### 4.2 New Initialization (v2 - BREAKING)

**File**: `bot/rosey/rosey.py`

```python
import asyncio
from nats.aio.client import Client as NATS
from common.database_service import DatabaseService

async def main():
    # Load config v2
    with open('config.json') as f:
        config = json.load(f)
    
    # Validate config version
    if config.get('version') != '2.0':
        raise ValueError(
            f"Configuration version {config.get('version')} not supported. "
            "Run 'python scripts/migrate_config.py' to upgrade."
        )
    
    # Connect to NATS (REQUIRED)
    nats_config = config['nats']
    nats = NATS()
    await nats.connect(
        servers=[nats_config['url']],
        max_reconnect_attempts=nats_config.get('max_reconnect_attempts', -1),
        reconnect_time_wait=nats_config.get('reconnect_delay', 2)
    )
    logger.info(f"Connected to NATS: {nats_config['url']}")
    
    # Start database service (separate from bot)
    db_config = config['database']
    if db_config.get('run_as_service', True):
        db_service = DatabaseService(nats, db_config['path'])
        await db_service.start()
        logger.info("DatabaseService started")
    
    # Get platform config (currently only one)
    platform_config = config['platforms'][0]  # Primary platform
    
    # Create CyTube connection
    connection = CyTubeConnection(
        platform_config['domain'],
        platform_config['channel'],
        platform_config['user']
    )
    
    # Create bot (NATS required, no db parameter)
    bot = Bot(
        connection,
        platform_config['channel'],
        nats_client=nats,  # REQUIRED
        logger=logger
    )
    # NO db parameter - REMOVED
    
    # ... rest of initialization ...

if __name__ == '__main__':
    asyncio.run(main())
```

**Key Changes**:
1. Main function is now `async` (required for NATS)
2. NATS connection established first (mandatory)
3. DatabaseService started separately (process isolation ready)
4. Bot receives NATS client (no `db` parameter)
5. Configuration validation enforces v2 format

---

## 5. Configuration Migration Script

### 5.1 Migration Script

**File**: `scripts/migrate_config.py` (NEW)

```python
#!/usr/bin/env python3
"""Migrate configuration from v1 to v2 format.

Usage:
    python scripts/migrate_config.py bot/rosey/config.json
    python scripts/migrate_config.py --backup bot/rosey/config.json
"""
import argparse
import json
import shutil
from pathlib import Path


def migrate_config_v1_to_v2(old_config: dict) -> dict:
    """Convert v1 config to v2 format.
    
    Args:
        old_config: Configuration in v1 format
        
    Returns:
        Configuration in v2 format
    """
    # Extract old values with defaults
    domain = old_config.get('domain', 'https://cytu.be')
    channel = old_config.get('channel', 'YourChannelName')
    user = old_config.get('user', ['YourUsername', 'YourPassword'])
    response_timeout = old_config.get('response_timeout', 1)
    restart_delay = old_config.get('restart_delay', 5)
    log_level = old_config.get('log_level', 'WARNING')
    chat_log_file = old_config.get('chat_log_file', 'chat.log')
    media_log_file = old_config.get('media_log_file', 'media.log')
    shell = old_config.get('shell', 'localhost:5555')
    db_path = old_config.get('db', 'bot_data.db')
    llm = old_config.get('llm', {})
    
    # Parse shell (old format: "host:port")
    if ':' in shell:
        shell_host, shell_port = shell.split(':', 1)
        shell_port = int(shell_port)
    else:
        shell_host = 'localhost'
        shell_port = 5555
    
    # Build v2 config
    new_config = {
        "version": "2.0",
        
        "nats": {
            "url": "nats://localhost:4222",
            "connection_timeout": 5,
            "max_reconnect_attempts": -1,
            "reconnect_delay": 2
        },
        
        "database": {
            "path": db_path,
            "run_as_service": True
        },
        
        "platforms": [
            {
                "type": "cytube",
                "name": "primary",
                "enabled": True,
                "domain": domain,
                "channel": channel,
                "user": user,
                "response_timeout": response_timeout,
                "restart_delay": restart_delay
            }
        ],
        
        "shell": {
            "enabled": True,
            "host": shell_host,
            "port": shell_port
        },
        
        "logging": {
            "level": log_level,
            "chat_log_file": chat_log_file,
            "media_log_file": media_log_file
        },
        
        "llm": llm,
        
        "plugins": {
            "enabled": True,
            "directory": "plugins/",
            "auto_reload": False
        }
    }
    
    return new_config


def main():
    parser = argparse.ArgumentParser(description='Migrate config from v1 to v2')
    parser.add_argument('config_file', help='Path to config.json')
    parser.add_argument('--backup', action='store_true', help='Backup original file')
    parser.add_argument('--output', help='Output file (default: overwrite input)')
    args = parser.parse_args()
    
    config_path = Path(args.config_file)
    
    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return 1
    
    # Load old config
    print(f"Loading config: {config_path}")
    with open(config_path) as f:
        old_config = json.load(f)
    
    # Check if already v2
    if old_config.get('version') == '2.0':
        print("Config is already v2 format. Nothing to do.")
        return 0
    
    # Backup if requested
    if args.backup:
        backup_path = config_path.with_suffix('.json.bak')
        print(f"Backing up to: {backup_path}")
        shutil.copy2(config_path, backup_path)
    
    # Migrate
    print("Migrating config v1 → v2...")
    new_config = migrate_config_v1_to_v2(old_config)
    
    # Write output
    output_path = Path(args.output) if args.output else config_path
    print(f"Writing new config: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(new_config, f, indent=2)
    
    print("✅ Migration complete!")
    print("\nNext steps:")
    print("1. Review the new config file")
    print("2. Ensure NATS server is installed and running: nats-server")
    print("3. Update bot startup: python bot/rosey/rosey.py config.json")
    print("4. See docs/sprints/upcoming/9-The-Accountant/MIGRATION.md for details")
    
    return 0


if __name__ == '__main__':
    exit(main())
```

---

## 6. Implementation Plan

### Phase 1: Create Migration Script (1 hour)

1. Create `scripts/migrate_config.py`
2. Implement `migrate_config_v1_to_v2()` function
3. Add CLI argument parsing
4. Test migration with real config files

### Phase 2: Update Bot Constructor (30 minutes)

1. Remove `db` parameter from `Bot.__init__()`
2. Make `nats_client` required (not optional)
3. Add validation error if NATS is None
4. Update docstring with migration notice

### Phase 3: Update Bot Initialization (1.5 hours)

1. Convert `bot/rosey/rosey.py` main to async
2. Add NATS connection setup
3. Add DatabaseService startup
4. Update bot instantiation (remove `db`, require `nats`)
5. Add config version validation

### Phase 4: Update Config Distribution File (30 minutes)

1. Update `bot/rosey/config.json.dist` to v2 format
2. Add comments explaining each section
3. Update README.md with new config format

### Phase 5: Testing (1.5 hours)

1. Test migration script with various configs
2. Test bot startup with v2 config
3. Test error handling for missing NATS
4. Verify database service runs separately

---

## 7. Testing Strategy

### 7.1 Migration Script Tests

**Test Cases**:
1. Migrate minimal v1 config
2. Migrate full v1 config with all options
3. Handle missing optional fields
4. Detect and skip v2 configs
5. Backup functionality

**Manual Testing**:
```bash
# Test migration
python scripts/migrate_config.py bot/rosey/config.json.dist --backup

# Verify output
cat bot/rosey/config.json.dist
```

### 7.2 Bot Startup Tests

**Test Cases**:
1. Start bot with v2 config (should work)
2. Start bot with v1 config (should fail with clear message)
3. Start bot without NATS running (should fail gracefully)
4. Start bot with invalid config (should fail with validation error)

**Manual Testing**:
```bash
# Start NATS server
nats-server

# Start bot with new config
python bot/rosey/rosey.py config.json
```

---

## 8. Acceptance Criteria

**Definition of Done**:

- [ ] Configuration v2 format defined and documented
- [ ] Migration script implemented (`scripts/migrate_config.py`)
- [ ] Bot constructor updated (no `db` parameter, `nats` required)
- [ ] Bot initialization updated (async, NATS connection, DatabaseService)
- [ ] `config.json.dist` updated to v2 format
- [ ] Migration script tested with real configs
- [ ] Bot startup tested with v2 config
- [ ] Error messages clear and helpful
- [ ] Breaking changes documented in CHANGELOG.md
- [ ] Migration guide created (Sortie 6)

---

## 9. Breaking Changes Summary

**⚠️ BREAKING CHANGES** in this sortie:

### 9.1 Configuration Format
- **Old**: Flat structure, single platform
- **New**: Nested structure, multi-platform array
- **Migration**: Run `python scripts/migrate_config.py config.json`

### 9.2 Bot Constructor
- **Old**: `Bot(connection, channel, logger, db=None, nats_client=None)`
- **New**: `Bot(connection, channel, nats_client, logger=None)`
- **Changes**:
  - `db` parameter REMOVED
  - `nats_client` now REQUIRED (not optional)
  - Position changed (3rd parameter)

### 9.3 Bot Initialization
- **Old**: Synchronous, creates database, passes to bot
- **New**: Asynchronous, connects NATS, starts DatabaseService separately
- **Changes**:
  - Must use `asyncio.run(main())`
  - NATS connection required
  - DatabaseService runs separately

### 9.4 Dependencies
- **New Requirement**: NATS server must be running
- **Installation**: `nats-server` (or use Docker)
- **Configuration**: NATS URL in `config.nats.url`

---

## 10. Migration Path for Users

**Step-by-Step Migration**:

1. **Backup current config**:
   ```bash
   cp bot/rosey/config.json bot/rosey/config.json.v1.bak
   ```

2. **Install NATS server** (if not already):
   ```bash
   # macOS
   brew install nats-server
   
   # Linux
   curl -L https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.zip -o nats-server.zip
   unzip nats-server.zip
   sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/
   
   # Windows
   # Download from https://github.com/nats-io/nats-server/releases
   ```

3. **Start NATS server**:
   ```bash
   nats-server
   # Or run in background:
   nats-server -D
   ```

4. **Migrate configuration**:
   ```bash
   python scripts/migrate_config.py bot/rosey/config.json --backup
   ```

5. **Review new config**:
   ```bash
   cat bot/rosey/config.json
   # Verify settings, adjust if needed
   ```

6. **Update bot startup command** (now async):
   ```bash
   # Old: python bot/rosey/rosey.py config.json
   # New: Same command, but now async internally
   python bot/rosey/rosey.py config.json
   ```

7. **Verify bot starts**:
   - Check logs for "Connected to NATS"
   - Check logs for "DatabaseService started"
   - Bot should connect to channel normally

---

## 11. Rollback Plan

**If Migration Fails**:

1. Stop bot
2. Restore backup config:
   ```bash
   cp bot/rosey/config.json.v1.bak bot/rosey/config.json
   ```
3. Checkout previous commit (before Sortie 5):
   ```bash
   git checkout HEAD~1
   ```
4. Restart bot with old version

**Note**: After Sortie 5 is merged, backward compatibility is intentionally broken. Rollback requires reverting entire Sprint 9.

---

## 12. Dependencies

**Requires**:
- ✅ Sortie 1-4 (All previous sorties MUST be complete)
- ✅ NATS server installed and tested

**Blocks**:
- Sortie 6 (Testing & Documentation)

**This is the Final Breaking Changes Commit** - After this, Sprint 9 core work is complete.

---

## 13. Next Steps

**After Completion**:

1. Mark Sortie 5 complete
2. Begin Sortie 6: Testing & Documentation (final sortie)
3. Create MIGRATION.md guide for users
4. Update CHANGELOG.md with breaking changes
5. Test entire Sprint 9 end-to-end

---

**Sortie Status**: Ready for Implementation  
**Priority**: CRITICAL (Final Breaking Changes)  
**Estimated Effort**: 4-5 hours  
**Success Metric**: Configuration v2 enforced, NATS mandatory, bot runs with new architecture
