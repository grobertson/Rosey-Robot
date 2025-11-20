# SPEC: Sortie 3 - Deployment Scripts

**Sprint:** 5 (ship-it)  
**Sortie:** 3 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 2 (Configuration Management)

---

## Objective

Create deployment automation scripts for deploying, rolling back, and health checking the bot across test and production environments.

## Success Criteria

- ✅ `scripts/deploy.sh` created and functional
- ✅ `scripts/rollback.sh` created and functional
- ✅ `scripts/health_check.py` created and functional
- ✅ All scripts executable (`chmod +x`)
- ✅ Scripts work for both test and production
- ✅ Documentation complete

## Technical Specification

### File Structure

```
scripts/
  deploy.sh          # Main deployment script
  rollback.sh        # Rollback to previous version
  health_check.py    # Verify bot health
  README.md          # Scripts documentation
```

### deploy.sh

**Purpose:** Deploy bot to test or production environment

**Usage:** `./scripts/deploy.sh [test|prod]`

**Steps:**
1. Validate environment parameter
2. Load configuration
3. Create backup of current deployment
4. Stop existing bot process
5. Copy new bot files to deployment location
6. Switch config symlink
7. Start bot with new config
8. Wait for startup
9. Run health check
10. Report success or failure

**Exit Codes:**
- `0`: Deployment successful
- `1`: Invalid arguments
- `2`: Backup failed
- `3`: Bot stop failed
- `4`: Deployment failed
- `5`: Health check failed

### rollback.sh

**Purpose:** Rollback to previous deployment version

**Usage:** `./scripts/rollback.sh [test|prod]`

**Steps:**
1. Validate environment parameter
2. Check backup exists
3. Stop current bot
4. Restore files from backup
5. Restart bot
6. Run health check
7. Report success or failure

**Exit Codes:**
- `0`: Rollback successful
- `1`: Invalid arguments
- `2`: No backup found
- `3`: Bot stop failed
- `4`: Restore failed
- `5`: Health check failed

### health_check.py

**Purpose:** Verify bot is healthy and operational

**Usage:** `python scripts/health_check.py [test|prod]`

**Checks:**
1. Bot process running
2. Database accessible
3. Network connection active (optional)
4. Recent activity in database

**Exit Codes:**
- `0`: Bot healthy
- `1`: Bot not running
- `2`: Database inaccessible
- `3`: No recent activity
- `4`: Configuration error

## Implementation

### scripts/deploy.sh

```bash
#!/bin/bash
# Deployment script for Rosey CyTube bot
# Usage: ./scripts/deploy.sh [test|prod]

set -e  # Exit on error
set -u  # Exit on undefined variable

ENVIRONMENT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/.deploy-backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
if [[ "$ENVIRONMENT" != "test" && "$ENVIRONMENT" != "prod" ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [test|prod]"
    exit 1
fi

log_info "Starting deployment to $ENVIRONMENT environment..."

# Configuration
BOT_DIR="$PROJECT_ROOT/bots/rosey"
CONFIG_FILE="$BOT_DIR/config-${ENVIRONMENT}.json"
ACTIVE_CONFIG="$BOT_DIR/config.json"
PID_FILE="$PROJECT_ROOT/data/${ENVIRONMENT}-rosey.pid"

# Validate configuration exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Configuration not found: $CONFIG_FILE"
    exit 4
fi

# Create backup directory
log_info "Creating backup..."
mkdir -p "$BACKUP_DIR"
BACKUP_PATH="$BACKUP_DIR/${ENVIRONMENT}_${TIMESTAMP}"
mkdir -p "$BACKUP_PATH"

# Backup current deployment if exists
if [[ -L "$ACTIVE_CONFIG" ]] || [[ -f "$ACTIVE_CONFIG" ]]; then
    cp -r "$BOT_DIR"/* "$BACKUP_PATH/" 2>/dev/null || true
    log_info "Backup created: $BACKUP_PATH"
fi

# Stop existing bot if running
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log_info "Stopping existing bot (PID: $PID)..."
        kill "$PID" || {
            log_error "Failed to stop bot"
            exit 3
        }
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# Switch configuration symlink
log_info "Switching to $ENVIRONMENT configuration..."
rm -f "$ACTIVE_CONFIG"
ln -s "config-${ENVIRONMENT}.json" "$ACTIVE_CONFIG"

# Start bot
log_info "Starting bot..."
cd "$PROJECT_ROOT"

# Use systemd if available, otherwise direct start
if command -v systemctl &> /dev/null; then
    SERVICE_NAME="cytube-bot-${ENVIRONMENT}"
    if systemctl list-unit-files | grep -q "${SERVICE_NAME}.service"; then
        log_info "Starting via systemd: $SERVICE_NAME"
        sudo systemctl start "$SERVICE_NAME" || {
            log_error "Failed to start systemd service"
            exit 4
        }
    else
        log_warn "Systemd service not found, starting directly..."
        nohup python -m bots.rosey.bot > "logs/${ENVIRONMENT}-bot.log" 2>&1 &
        echo $! > "$PID_FILE"
    fi
else
    log_info "Starting bot directly..."
    nohup python -m bots.rosey.bot > "logs/${ENVIRONMENT}-bot.log" 2>&1 &
    echo $! > "$PID_FILE"
fi

# Wait for bot to start
log_info "Waiting for bot to start..."
sleep 5

# Health check
log_info "Running health check..."
python "$SCRIPT_DIR/health_check.py" "$ENVIRONMENT" || {
    log_error "Health check failed!"
    log_warn "Attempting rollback..."
    "$SCRIPT_DIR/rollback.sh" "$ENVIRONMENT"
    exit 5
}

log_info "Deployment successful! ✓"
log_info "Bot running in $ENVIRONMENT environment"

# Keep only last 5 backups
log_info "Cleaning old backups..."
cd "$BACKUP_DIR"
ls -t | grep "^${ENVIRONMENT}_" | tail -n +6 | xargs -r rm -rf

exit 0
```

### scripts/rollback.sh

```bash
#!/bin/bash
# Rollback script for Rosey CyTube bot
# Usage: ./scripts/rollback.sh [test|prod]

set -e
set -u

ENVIRONMENT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/.deploy-backup"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Validate environment
if [[ "$ENVIRONMENT" != "test" && "$ENVIRONMENT" != "prod" ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    echo "Usage: $0 [test|prod]"
    exit 1
fi

log_info "Starting rollback for $ENVIRONMENT environment..."

# Find most recent backup
LATEST_BACKUP=$(ls -t "$BACKUP_DIR" | grep "^${ENVIRONMENT}_" | head -n 1)

if [[ -z "$LATEST_BACKUP" ]]; then
    log_error "No backup found for $ENVIRONMENT"
    exit 2
fi

BACKUP_PATH="$BACKUP_DIR/$LATEST_BACKUP"
log_info "Rolling back to: $BACKUP_PATH"

# Configuration
BOT_DIR="$PROJECT_ROOT/bots/rosey"
PID_FILE="$PROJECT_ROOT/data/${ENVIRONMENT}-rosey.pid"

# Stop current bot
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        log_info "Stopping current bot (PID: $PID)..."
        kill "$PID" || {
            log_error "Failed to stop bot"
            exit 3
        }
        sleep 2
    fi
    rm -f "$PID_FILE"
fi

# Restore from backup
log_info "Restoring files from backup..."
rm -rf "$BOT_DIR"/*
cp -r "$BACKUP_PATH"/* "$BOT_DIR/" || {
    log_error "Failed to restore backup"
    exit 4
}

# Restart bot
log_info "Restarting bot..."
cd "$PROJECT_ROOT"

if command -v systemctl &> /dev/null; then
    SERVICE_NAME="cytube-bot-${ENVIRONMENT}"
    if systemctl list-unit-files | grep -q "${SERVICE_NAME}.service"; then
        sudo systemctl start "$SERVICE_NAME" || {
            log_error "Failed to start systemd service"
            exit 4
        }
    else
        nohup python -m bots.rosey.bot > "logs/${ENVIRONMENT}-bot.log" 2>&1 &
        echo $! > "$PID_FILE"
    fi
else
    nohup python -m bots.rosey.bot > "logs/${ENVIRONMENT}-bot.log" 2>&1 &
    echo $! > "$PID_FILE"
fi

sleep 5

# Health check
log_info "Running health check..."
python "$SCRIPT_DIR/health_check.py" "$ENVIRONMENT" || {
    log_error "Health check failed after rollback!"
    exit 5
}

log_info "Rollback successful! ✓"
exit 0
```

### scripts/health_check.py

```python
#!/usr/bin/env python3
"""
Health check script for Rosey CyTube bot.
Usage: python health_check.py [test|prod]
"""
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta

def health_check(environment: str) -> int:
    """
    Check if bot is healthy.
    
    Returns:
        0 if healthy, non-zero otherwise
    """
    project_root = Path(__file__).parent.parent
    
    # Check 1: Process running
    print(f"[1/3] Checking if {environment} bot process is running...")
    pid_file = project_root / "data" / f"{environment}-rosey.pid"
    
    if not pid_file.exists():
        print("❌ PID file not found - bot may not be running")
        return 1
    
    try:
        pid = int(pid_file.read_text().strip())
        # Check if process exists (works on Unix-like systems)
        import os
        os.kill(pid, 0)  # Signal 0 just checks existence
        print(f"✓ Bot process running (PID: {pid})")
    except (ProcessLookupError, ValueError, OSError):
        print("❌ Bot process not running")
        return 1
    
    # Check 2: Database accessible
    print(f"[2/3] Checking database accessibility...")
    db_path = project_root / "data" / f"{environment if environment == 'test' else ''}-rosey.db"
    if environment == "prod":
        db_path = project_root / "data" / "rosey.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return 2
    
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]
        conn.close()
        print(f"✓ Database accessible ({table_count} tables)")
    except Exception as e:
        print(f"❌ Database error: {e}")
        return 2
    
    # Check 3: Recent activity (optional but recommended)
    print(f"[3/3] Checking recent activity...")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if there's been activity in the last 5 minutes
        # This is optional - bot might be running but idle
        cursor.execute("""
            SELECT last_seen FROM user_stats 
            ORDER BY last_seen DESC LIMIT 1
        """)
        result = cursor.fetchone()
        conn.close()
        
        if result:
            last_activity = datetime.fromisoformat(result[0])
            age = datetime.now() - last_activity
            if age < timedelta(hours=24):
                print(f"✓ Recent activity detected ({age.total_seconds():.0f}s ago)")
            else:
                print(f"⚠ No recent activity (last: {age.days} days ago)")
                # This is a warning, not a failure
        else:
            print("⚠ No activity records (fresh bot?)")
    except Exception as e:
        print(f"⚠ Could not check activity: {e}")
        # This is non-critical, don't fail
    
    print("\n✅ Health check passed!")
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ["test", "prod"]:
        print("Usage: python health_check.py [test|prod]")
        sys.exit(1)
    
    environment = sys.argv[1]
    print(f"Running health check for {environment} environment...\n")
    
    exit_code = health_check(environment)
    sys.exit(exit_code)
```

### scripts/README.md

```markdown
# Deployment Scripts

Automation scripts for deploying and managing the Rosey CyTube bot.

## Scripts

### deploy.sh

Deploy bot to test or production environment.

**Usage:**
```bash
./scripts/deploy.sh test   # Deploy to test channel
./scripts/deploy.sh prod   # Deploy to production channel
```

**What it does:**
1. Creates backup of current deployment
2. Stops existing bot process
3. Switches configuration to target environment
4. Starts bot with new configuration
5. Runs health check to verify deployment
6. Auto-rollback if health check fails

**Exit codes:**
- 0: Success
- 1: Invalid arguments
- 2: Backup failed
- 3: Failed to stop bot
- 4: Deployment failed
- 5: Health check failed

### rollback.sh

Rollback to previous deployment version.

**Usage:**
```bash
./scripts/rollback.sh test   # Rollback test deployment
./scripts/rollback.sh prod   # Rollback production deployment
```

**What it does:**
1. Finds most recent backup
2. Stops current bot
3. Restores files from backup
4. Restarts bot
5. Runs health check

**Exit codes:**
- 0: Success
- 1: Invalid arguments
- 2: No backup found
- 3: Failed to stop bot
- 4: Restore failed
- 5: Health check failed after rollback

### health_check.py

Verify bot is running and healthy.

**Usage:**
```bash
python scripts/health_check.py test   # Check test bot
python scripts/health_check.py prod   # Check production bot
```

**Checks:**
1. Bot process is running
2. Database is accessible
3. Recent activity detected (warning only)

**Exit codes:**
- 0: Healthy
- 1: Process not running
- 2: Database inaccessible
- 3: No recent activity (unused currently)

## Examples

**Deploy to test:**
```bash
./scripts/deploy.sh test
```

**Deploy to production:**
```bash
./scripts/deploy.sh prod
```

**Rollback production:**
```bash
./scripts/rollback.sh prod
```

**Manual health check:**
```bash
python scripts/health_check.py prod
```

## Requirements

- Bash shell (Linux/Mac)
- Python 3.11+
- Write permissions to project directory
- Environment variables configured (if using passwords)

## Troubleshooting

**Error: "Permission denied"**
- Make scripts executable: `chmod +x scripts/*.sh`

**Error: "Configuration not found"**
- Ensure config templates exist in `bots/rosey/`
- Check environment name is correct (test or prod)

**Health check fails**
- Check bot logs: `tail -f logs/*-bot.log`
- Verify database exists
- Check process is running: `ps aux | grep rosey`

## Backup Management

Backups are stored in `.deploy-backup/` directory:
- Named: `[env]_[timestamp]/`
- Kept: Last 5 backups per environment
- Older backups auto-deleted on new deployment

## Integration with CI/CD

These scripts are called by GitHub Actions workflows:
- `test-deploy.yml` → `./scripts/deploy.sh test`
- `prod-deploy.yml` → `./scripts/deploy.sh prod`

See `.github/workflows/` for workflow configuration.
```

## Validation Checklist

- [ ] `scripts/deploy.sh` created and executable
- [ ] `scripts/rollback.sh` created and executable
- [ ] `scripts/health_check.py` created and executable
- [ ] `scripts/README.md` created
- [ ] Scripts work for test environment
- [ ] Scripts work for prod environment
- [ ] Backup/restore functions correctly
- [ ] Health checks pass
- [ ] Error handling works

## Testing Strategy

1. **Test deployment script:**
   ```bash
   ./scripts/deploy.sh test
   # Verify bot starts and health check passes
   ```

2. **Test rollback script:**
   ```bash
   ./scripts/rollback.sh test
   # Verify restoration and health check passes
   ```

3. **Test health check:**
   ```bash
   python scripts/health_check.py test
   # Should return 0 if bot healthy
   ```

4. **Test failure scenarios:**
   - Deploy with invalid config (should fail)
   - Rollback with no backup (should fail gracefully)
   - Health check with stopped bot (should fail)

## Commit Message

```bash
git add scripts/
git commit -m "feat: add deployment automation scripts

Created deployment, rollback, and health check scripts for
automating bot deployments to test and production environments.

scripts/deploy.sh:
- Deploy to test or production environment
- Auto-backup current deployment
- Stop existing bot
- Switch configuration
- Start bot
- Run health check
- Auto-rollback on failure
- Keep last 5 backups

scripts/rollback.sh:
- Rollback to previous deployment
- Restore from backup
- Restart bot
- Verify with health check

scripts/health_check.py:
- Check process running
- Verify database accessible
- Check recent activity
- Exit codes for automation

scripts/README.md:
- Complete documentation
- Usage examples
- Troubleshooting guide
- Integration notes

Features:
- Colored output for clarity
- Comprehensive error handling
- Exit codes for automation
- Backup management (keep last 5)
- Systemd integration support
- Works for both test and prod

This enables automated deployments via GitHub Actions.

SPEC: Sortie 3 - Deployment Scripts"
```

## Next Sortie

**Sortie 4: Test Deploy Workflow** - Create GitHub Actions workflow for automated test channel deployment on PRs.

---

**Implementation Time Estimate:** 4-5 hours  
**Risk Level:** Medium  
**Priority:** High (core deployment automation)
