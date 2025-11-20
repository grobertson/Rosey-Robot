# SPEC: Sortie 10 - Rollback Mechanism

**Sprint:** 5 (ship-it)  
**Sortie:** 10 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 3 (Deployment Scripts), Sorties 6 & 9 (Verification)

---

## Objective

Enhance and thoroughly test the rollback mechanism for both test and production environments. Ensure rollbacks are reliable, fast, and can be triggered automatically or manually with clear success/failure feedback.

## Success Criteria

- ✅ Automatic rollback on verification failure
- ✅ Manual rollback command available
- ✅ Rollback completes in < 60 seconds
- ✅ Previous version verified after rollback
- ✅ Rollback history tracked
- ✅ Emergency rollback mode (skip verification)
- ✅ Clear feedback on rollback status
- ✅ Documentation for rollback procedures

## Technical Specification

### Rollback Script Enhancement

Enhance existing `scripts/rollback.sh` with:

**Features to Add:**
1. Rollback verification after restore
2. Multiple backup selection (not just latest)
3. Dry-run mode for testing
4. Rollback history logging
5. Emergency mode (force rollback)
6. Status reporting
7. Pre-rollback validation

### Rollback Triggers

**Automatic Triggers:**
1. Deployment verification failure (test/prod)
2. Health check timeout
3. Critical error in logs
4. Process crash during stability check
5. Configuration validation failure

**Manual Triggers:**
1. CLI command: `./scripts/rollback.sh <env>`
2. GitHub Actions workflow dispatch
3. Emergency rollback button (future: dashboard)

### Rollback Types

**Standard Rollback:**
- Restore previous backup
- Restart bot
- Verify restoration
- Report success/failure

**Emergency Rollback:**
- Skip verification checks
- Force restore previous version
- Restart immediately
- Minimal validation

**Targeted Rollback:**
- Select specific backup by timestamp
- Restore to known-good version
- Useful for skipping bad deployments

## Implementation

### Enhanced scripts/rollback.sh

```bash
#!/bin/bash
# Enhanced rollback script with verification and history tracking

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_ROOT/backups"
LOG_FILE="$PROJECT_ROOT/logs/rollback.log"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Print colored message
print_msg() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Usage information
usage() {
    cat << EOF
Usage: $0 <environment> [options]

Arguments:
    environment     Environment to rollback (test or prod)

Options:
    --dry-run       Preview rollback without making changes
    --emergency     Skip verification (emergency rollback)
    --backup        Specific backup to restore (timestamp format)
    --list          List available backups
    --verify-only   Only verify rollback capability
    -h, --help      Show this help message

Examples:
    $0 prod                                    # Rollback production to latest backup
    $0 test --dry-run                          # Preview test rollback
    $0 prod --emergency                        # Emergency production rollback
    $0 prod --backup backup_20241112_153045   # Rollback to specific backup
    $0 test --list                             # List available test backups

EOF
    exit 1
}

# Parse arguments
ENVIRONMENT=""
DRY_RUN=false
EMERGENCY=false
SPECIFIC_BACKUP=""
LIST_BACKUPS=false
VERIFY_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        test|prod)
            ENVIRONMENT=$1
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --emergency)
            EMERGENCY=true
            shift
            ;;
        --backup)
            SPECIFIC_BACKUP=$2
            shift 2
            ;;
        --list)
            LIST_BACKUPS=true
            shift
            ;;
        --verify-only)
            VERIFY_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate environment
if [[ -z "$ENVIRONMENT" ]] && [[ "$LIST_BACKUPS" == false ]]; then
    echo "Error: Environment required"
    usage
fi

# List backups and exit
if [[ "$LIST_BACKUPS" == true ]]; then
    print_msg "$BLUE" "═══════════════════════════════════════════"
    print_msg "$BLUE" "  Available Backups - ${ENVIRONMENT^^}"
    print_msg "$BLUE" "═══════════════════════════════════════════"
    echo ""
    
    ENV_BACKUP_DIR="$BACKUP_DIR/$ENVIRONMENT"
    
    if [[ ! -d "$ENV_BACKUP_DIR" ]] || [[ -z "$(ls -A "$ENV_BACKUP_DIR" 2>/dev/null)" ]]; then
        print_msg "$YELLOW" "No backups found for $ENVIRONMENT"
        exit 0
    fi
    
    # List backups with details
    for backup in "$ENV_BACKUP_DIR"/backup_*; do
        if [[ -d "$backup" ]]; then
            backup_name=$(basename "$backup")
            backup_date=$(echo "$backup_name" | sed 's/backup_//' | sed 's/_/ /' | sed 's/_/:/' | sed 's/_/:/')
            
            # Get backup size
            size=$(du -sh "$backup" 2>/dev/null | cut -f1)
            
            # Check if current deployment
            if [[ -L "$PROJECT_ROOT/current" ]] && [[ "$(readlink "$PROJECT_ROOT/current")" == "$backup" ]]; then
                print_msg "$GREEN" "● $backup_name (CURRENT) - $backup_date - $size"
            else
                print_msg "$NC" "  $backup_name - $backup_date - $size"
            fi
        fi
    done
    
    echo ""
    exit 0
fi

# Verify-only mode
if [[ "$VERIFY_ONLY" == true ]]; then
    print_msg "$BLUE" "Verifying rollback capability for $ENVIRONMENT..."
    
    ENV_BACKUP_DIR="$BACKUP_DIR/$ENVIRONMENT"
    
    if [[ ! -d "$ENV_BACKUP_DIR" ]]; then
        print_msg "$RED" "✗ No backup directory for $ENVIRONMENT"
        exit 1
    fi
    
    backup_count=$(find "$ENV_BACKUP_DIR" -maxdepth 1 -type d -name "backup_*" | wc -l)
    
    if [[ $backup_count -eq 0 ]]; then
        print_msg "$RED" "✗ No backups available for $ENVIRONMENT"
        exit 1
    fi
    
    print_msg "$GREEN" "✓ Rollback capability verified"
    print_msg "$GREEN" "  Available backups: $backup_count"
    exit 0
fi

print_msg "$BLUE" "═══════════════════════════════════════════"
print_msg "$BLUE" "  Rollback - ${ENVIRONMENT^^}"
print_msg "$BLUE" "═══════════════════════════════════════════"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    print_msg "$YELLOW" "DRY RUN MODE - No changes will be made"
    echo ""
fi

if [[ "$EMERGENCY" == true ]]; then
    print_msg "$YELLOW" "EMERGENCY MODE - Verification will be skipped"
    echo ""
fi

log "INFO" "Rollback started for $ENVIRONMENT (dry_run=$DRY_RUN, emergency=$EMERGENCY)"

# Step 1: Find backup to restore
print_msg "$BLUE" "▸ Finding backup to restore..."

ENV_BACKUP_DIR="$BACKUP_DIR/$ENVIRONMENT"

if [[ ! -d "$ENV_BACKUP_DIR" ]]; then
    print_msg "$RED" "✗ No backup directory found for $ENVIRONMENT"
    log "ERROR" "Backup directory not found: $ENV_BACKUP_DIR"
    exit 1
fi

if [[ -n "$SPECIFIC_BACKUP" ]]; then
    BACKUP_PATH="$ENV_BACKUP_DIR/$SPECIFIC_BACKUP"
    if [[ ! -d "$BACKUP_PATH" ]]; then
        print_msg "$RED" "✗ Specified backup not found: $SPECIFIC_BACKUP"
        log "ERROR" "Backup not found: $BACKUP_PATH"
        exit 1
    fi
    print_msg "$GREEN" "✓ Using specified backup: $SPECIFIC_BACKUP"
else
    # Find most recent backup (excluding current if it's a symlink)
    CURRENT_DEPLOYMENT=$(readlink "$PROJECT_ROOT/current" 2>/dev/null || echo "")
    
    BACKUP_PATH=$(find "$ENV_BACKUP_DIR" -maxdepth 1 -type d -name "backup_*" ! -path "$CURRENT_DEPLOYMENT" | sort -r | head -n 1)
    
    if [[ -z "$BACKUP_PATH" ]]; then
        print_msg "$RED" "✗ No backup available for rollback"
        log "ERROR" "No backup found in $ENV_BACKUP_DIR"
        exit 1
    fi
    
    BACKUP_NAME=$(basename "$BACKUP_PATH")
    print_msg "$GREEN" "✓ Found backup: $BACKUP_NAME"
fi

log "INFO" "Selected backup: $BACKUP_PATH"

# Step 2: Stop current bot
print_msg "$BLUE" "▸ Stopping current bot..."

if [[ "$DRY_RUN" == false ]]; then
    if systemctl is-active --quiet cytube-bot; then
        systemctl stop cytube-bot
        sleep 2
        print_msg "$GREEN" "✓ Bot stopped"
        log "INFO" "Bot stopped"
    else
        print_msg "$YELLOW" "⚠ Bot was not running"
        log "WARN" "Bot was not running"
    fi
else
    print_msg "$YELLOW" "  Would stop bot (dry run)"
fi

# Step 3: Update current symlink
print_msg "$BLUE" "▸ Switching to backup version..."

if [[ "$DRY_RUN" == false ]]; then
    # Remove old symlink
    rm -f "$PROJECT_ROOT/current"
    
    # Create new symlink
    ln -s "$BACKUP_PATH" "$PROJECT_ROOT/current"
    
    print_msg "$GREEN" "✓ Switched to backup version"
    log "INFO" "Symlink updated to $BACKUP_PATH"
else
    print_msg "$YELLOW" "  Would update symlink to $BACKUP_PATH (dry run)"
fi

# Step 4: Update config symlink
print_msg "$BLUE" "▸ Updating configuration..."

if [[ "$DRY_RUN" == false ]]; then
    CONFIG_FILE="config-${ENVIRONMENT}.json"
    
    if [[ -f "$PROJECT_ROOT/$CONFIG_FILE" ]]; then
        rm -f "$PROJECT_ROOT/current/config.json"
        ln -s "$PROJECT_ROOT/$CONFIG_FILE" "$PROJECT_ROOT/current/config.json"
        print_msg "$GREEN" "✓ Configuration updated"
        log "INFO" "Config linked to $CONFIG_FILE"
    else
        print_msg "$YELLOW" "⚠ Config file not found: $CONFIG_FILE"
        log "WARN" "Config file not found: $CONFIG_FILE"
    fi
else
    print_msg "$YELLOW" "  Would update config symlink (dry run)"
fi

# Step 5: Start bot
print_msg "$BLUE" "▸ Starting bot..."

if [[ "$DRY_RUN" == false ]]; then
    systemctl start cytube-bot
    sleep 3
    
    if systemctl is-active --quiet cytube-bot; then
        print_msg "$GREEN" "✓ Bot started"
        log "INFO" "Bot started successfully"
    else
        print_msg "$RED" "✗ Bot failed to start"
        log "ERROR" "Bot failed to start after rollback"
        exit 1
    fi
else
    print_msg "$YELLOW" "  Would start bot (dry run)"
fi

# Step 6: Verify rollback (unless emergency mode or dry run)
if [[ "$EMERGENCY" == false ]] && [[ "$DRY_RUN" == false ]]; then
    print_msg "$BLUE" "▸ Verifying rollback..."
    
    # Wait for startup
    sleep 5
    
    # Run verification
    if python3 "$SCRIPT_DIR/verify_deployment.py" --env "$ENVIRONMENT"; then
        print_msg "$GREEN" "✓ Rollback verified successfully"
        log "INFO" "Rollback verified successfully"
    else
        print_msg "$RED" "✗ Rollback verification failed"
        log "ERROR" "Rollback verification failed"
        
        # Log rollback failure but don't fail the rollback itself
        print_msg "$YELLOW" "⚠ Rollback completed but verification failed"
        print_msg "$YELLOW" "  Manual investigation required"
        exit 2
    fi
elif [[ "$EMERGENCY" == true ]]; then
    print_msg "$YELLOW" "⚠ Skipping verification (emergency mode)"
    log "WARN" "Verification skipped (emergency mode)"
fi

# Success
if [[ "$DRY_RUN" == false ]]; then
    print_msg "$BLUE" "═══════════════════════════════════════════"
    print_msg "$GREEN" "✓ Rollback completed successfully"
    print_msg "$BLUE" "═══════════════════════════════════════════"
    echo ""
    
    log "INFO" "Rollback completed successfully"
    
    # Print rollback info
    print_msg "$BLUE" "Rollback Details:"
    print_msg "$NC" "  Environment: $ENVIRONMENT"
    print_msg "$NC" "  Backup: $(basename "$BACKUP_PATH")"
    print_msg "$NC" "  Time: $(date)"
    echo ""
else
    print_msg "$BLUE" "═══════════════════════════════════════════"
    print_msg "$GREEN" "✓ Dry run completed"
    print_msg "$BLUE" "═══════════════════════════════════════════"
    echo ""
fi

exit 0
```

### .github/workflows/manual-rollback.yml

Create manual rollback workflow:

```yaml
name: Manual Rollback

on:
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to rollback'
        required: true
        type: choice
        options:
          - test
          - prod
      backup:
        description: 'Specific backup to restore (leave empty for latest)'
        required: false
        type: string
      emergency:
        description: 'Emergency rollback (skip verification)'
        required: false
        type: boolean
        default: false
      reason:
        description: 'Reason for rollback'
        required: true
        type: string

permissions:
  contents: read
  deployments: write

jobs:
  rollback:
    name: Rollback ${{ inputs.environment }}
    runs-on: ubuntu-latest
    environment:
      name: ${{ inputs.environment }}
      url: ${{ inputs.environment == 'prod' && 'https://cytu.be/r/rosey' || 'https://cytu.be/r/test-rosey' }}
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Log rollback reason
        run: |
          echo "Rollback initiated by: ${{ github.actor }}"
          echo "Environment: ${{ inputs.environment }}"
          echo "Reason: ${{ inputs.reason }}"
          echo "Emergency: ${{ inputs.emergency }}"
          echo "Specific backup: ${{ inputs.backup || 'latest' }}"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: List available backups
        run: |
          chmod +x scripts/rollback.sh
          ./scripts/rollback.sh ${{ inputs.environment }} --list
      
      - name: Verify rollback capability
        run: |
          ./scripts/rollback.sh ${{ inputs.environment }} --verify-only
      
      - name: Execute rollback
        run: |
          chmod +x scripts/rollback.sh
          
          ROLLBACK_CMD="./scripts/rollback.sh ${{ inputs.environment }}"
          
          if [[ "${{ inputs.emergency }}" == "true" ]]; then
            ROLLBACK_CMD="$ROLLBACK_CMD --emergency"
          fi
          
          if [[ -n "${{ inputs.backup }}" ]]; then
            ROLLBACK_CMD="$ROLLBACK_CMD --backup ${{ inputs.backup }}"
          fi
          
          eval $ROLLBACK_CMD
      
      - name: Send notification
        if: always()
        uses: actions/github-script@v7
        env:
          WEBHOOK_URL: ${{ secrets.DEPLOY_NOTIFICATION_WEBHOOK }}
        with:
          script: |
            const webhook = process.env.WEBHOOK_URL;
            if (!webhook) {
              console.log('No webhook configured, skipping notification');
              return;
            }
            
            const success = '${{ job.status }}' === 'success';
            const emoji = success ? '🔄' : '❌';
            const status = success ? 'Successful' : 'Failed';
            
            const payload = {
              text: `${emoji} Rollback ${status}`,
              blocks: [
                {
                  type: "section",
                  text: {
                    type: "mrkdwn",
                    text: `*Rollback ${status}*\n\n` +
                          `• Environment: ${{ inputs.environment }}\n` +
                          `• Initiated by: ${{ github.actor }}\n` +
                          `• Reason: ${{ inputs.reason }}\n` +
                          `• Emergency: ${{ inputs.emergency }}\n` +
                          `• Time: ${new Date().toISOString()}`
                  }
                }
              ]
            };
            
            await fetch(webhook, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
            });
```

### Rollback History Tracking

Add `scripts/rollback_history.py`:

```python
#!/usr/bin/env python3
"""
Track rollback history for auditing and analysis.

Usage:
    python scripts/rollback_history.py --log <env> <backup> <reason>
    python scripts/rollback_history.py --list [--env <env>]
    python scripts/rollback_history.py --stats
"""

import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict

HISTORY_FILE = Path(__file__).parent.parent / 'logs' / 'rollback_history.json'

def load_history() -> List[Dict]:
    """Load rollback history from JSON file."""
    if not HISTORY_FILE.exists():
        return []
    
    with open(HISTORY_FILE) as f:
        return json.load(f)

def save_history(history: List[Dict]):
    """Save rollback history to JSON file."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def log_rollback(env: str, backup: str, reason: str, success: bool = True):
    """Log a rollback event."""
    history = load_history()
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'environment': env,
        'backup': backup,
        'reason': reason,
        'success': success,
        'initiated_by': 'manual'  # Could be 'automatic', 'workflow', etc.
    }
    
    history.append(entry)
    save_history(history)
    
    print(f"Logged rollback: {env} -> {backup}")

def list_rollbacks(env: str = None, limit: int = 20):
    """List recent rollbacks."""
    history = load_history()
    
    if env:
        history = [h for h in history if h['environment'] == env]
    
    # Show most recent first
    history = sorted(history, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    if not history:
        print("No rollback history found")
        return
    
    print(f"\nRecent Rollbacks (last {len(history)}):\n")
    print(f"{'Timestamp':<20} {'Env':<6} {'Backup':<25} {'Status':<10} {'Reason'}")
    print("─" * 100)
    
    for entry in history:
        timestamp = entry['timestamp'][:19].replace('T', ' ')
        env = entry['environment']
        backup = entry['backup'][:25]
        status = '✓ Success' if entry['success'] else '✗ Failed'
        reason = entry['reason'][:40]
        
        print(f"{timestamp} {env:<6} {backup:<25} {status:<10} {reason}")

def show_stats():
    """Show rollback statistics."""
    history = load_history()
    
    if not history:
        print("No rollback history found")
        return
    
    total = len(history)
    successful = sum(1 for h in history if h['success'])
    failed = total - successful
    
    # By environment
    envs = {}
    for entry in history:
        env = entry['environment']
        envs[env] = envs.get(env, 0) + 1
    
    print("\nRollback Statistics:\n")
    print(f"Total rollbacks: {total}")
    print(f"Successful: {successful} ({successful/total*100:.1f}%)")
    print(f"Failed: {failed} ({failed/total*100:.1f}%)")
    print()
    print("By environment:")
    for env, count in envs.items():
        print(f"  {env}: {count}")
    print()

def main():
    parser = argparse.ArgumentParser(description='Track rollback history')
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Log command
    log_parser = subparsers.add_parser('log', help='Log a rollback')
    log_parser.add_argument('env', choices=['test', 'prod'])
    log_parser.add_argument('backup', help='Backup name')
    log_parser.add_argument('reason', help='Reason for rollback')
    log_parser.add_argument('--failed', action='store_true', help='Mark as failed')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List rollbacks')
    list_parser.add_argument('--env', choices=['test', 'prod'], help='Filter by environment')
    list_parser.add_argument('--limit', type=int, default=20, help='Number of entries')
    
    # Stats command
    subparsers.add_parser('stats', help='Show rollback statistics')
    
    args = parser.parse_args()
    
    if args.command == 'log':
        log_rollback(args.env, args.backup, args.reason, success=not args.failed)
    elif args.command == 'list':
        list_rollbacks(env=args.env, limit=args.limit)
    elif args.command == 'stats':
        show_stats()
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
```

## Implementation Steps

### Step 1: Enhance Rollback Script

```bash
# Backup existing script
cp scripts/rollback.sh scripts/rollback.sh.backup

# Replace with enhanced version
# (Use code from above)

# Test dry run
./scripts/rollback.sh test --dry-run

# Test list backups
./scripts/rollback.sh test --list

# Test verify-only
./scripts/rollback.sh test --verify-only
```

### Step 2: Create Rollback History Tracker

```bash
# Create history tracker
touch scripts/rollback_history.py
chmod +x scripts/rollback_history.py

# Test history commands
python scripts/rollback_history.py stats
python scripts/rollback_history.py list
```

### Step 3: Create Manual Rollback Workflow

```bash
# Create workflow file
touch .github/workflows/manual-rollback.yml

# Add content (from above)

# Commit workflow
git add .github/workflows/manual-rollback.yml
git commit -m "ci: add manual rollback workflow"
```

### Step 4: Update Rollback Script Integration

```bash
# Update deploy.sh to log rollbacks
# Update verification scripts to trigger rollback
# Add rollback history logging

# Test integration
./scripts/deploy.sh test
# (Trigger verification failure)
# (Observe automatic rollback)
```

### Step 5: Test All Rollback Scenarios

```bash
# Scenario 1: Standard rollback
./scripts/rollback.sh test

# Scenario 2: Emergency rollback
./scripts/rollback.sh prod --emergency

# Scenario 3: Specific backup
./scripts/rollback.sh test --backup backup_20241112_153045

# Scenario 4: Dry run
./scripts/rollback.sh prod --dry-run
```

### Step 6: Document Rollback Procedures

```bash
# Create docs/ROLLBACK.md with procedures
# Update scripts/README.md with rollback documentation
# Add troubleshooting guide

git add docs/ROLLBACK.md scripts/README.md
git commit -m "docs: add rollback procedures"
```

## Validation Checklist

- [ ] Enhanced rollback.sh with all features
- [ ] Dry-run mode working
- [ ] Emergency mode working
- [ ] Specific backup selection working
- [ ] List backups command working
- [ ] Verify-only mode working
- [ ] Rollback history tracking implemented
- [ ] Manual rollback workflow created
- [ ] Automatic rollback tested
- [ ] Rollback verification working
- [ ] Rollback logging working
- [ ] Documentation complete
- [ ] All test scenarios passing

## Testing Strategy

### Test 1: Automatic Rollback on Verification Failure

**Steps:**
1. Deploy to test channel
2. Break verification (kill bot process)
3. Watch verification fail
4. Observe automatic rollback

**Expected:**
- Verification detects failure
- Rollback triggered automatically
- Previous version restored
- Bot restarted
- Verification passes after rollback

### Test 2: Manual Rollback via CLI

**Steps:**
1. Run `./scripts/rollback.sh test`
2. Observe rollback process
3. Check bot status

**Expected:**
- Finds latest backup
- Stops bot
- Switches to backup
- Restarts bot
- Runs verification
- Reports success

### Test 3: Emergency Rollback

**Steps:**
1. Run `./scripts/rollback.sh prod --emergency`
2. Observe fast rollback

**Expected:**
- Skips verification
- Fast restoration
- Bot restarted
- Warning about skipped verification
- Completes in < 30 seconds

### Test 4: Specific Backup Rollback

**Steps:**
1. List backups: `./scripts/rollback.sh test --list`
2. Select specific backup
3. Rollback: `./scripts/rollback.sh test --backup backup_20241112_120000`

**Expected:**
- Lists all available backups
- Restores specified backup
- Not latest backup
- Successful restoration

### Test 5: Dry Run Rollback

**Steps:**
1. Run `./scripts/rollback.sh prod --dry-run`
2. Review output

**Expected:**
- Shows what would happen
- No actual changes made
- Bot keeps running
- Clear dry-run indicators

### Test 6: Workflow-Based Rollback

**Steps:**
1. Go to Actions > Manual Rollback
2. Select environment: test
3. Enter reason
4. Run workflow

**Expected:**
- Workflow runs successfully
- Lists backups
- Verifies capability
- Executes rollback
- Sends notification
- Logs event

### Test 7: Rollback History

**Steps:**
1. Perform several rollbacks
2. Run `python scripts/rollback_history.py list`
3. Run `python scripts/rollback_history.py stats`

**Expected:**
- All rollbacks logged
- Timestamps accurate
- Success/failure tracked
- Statistics correct
- Queryable by environment

## Performance Targets

**Rollback Speed:**

| Operation | Target | Maximum |
|-----------|--------|---------|
| Find backup | < 1s | 3s |
| Stop bot | < 5s | 10s |
| Switch version | < 1s | 3s |
| Start bot | < 10s | 30s |
| Verification | < 20s | 60s |
| **Total (standard)** | **< 40s** | **60s** |
| **Total (emergency)** | **< 20s** | **30s** |

**Rollback Success Rate:**
- Target: > 99%
- Acceptable: > 95%
- Critical: Alert if < 90%

## Rollback Decision Matrix

### When to Rollback

**Automatic Rollback:**
- ✅ Verification failure (any check)
- ✅ Process crash during deployment
- ✅ Database connection failure
- ✅ Critical errors in logs
- ✅ Configuration validation failure

**Manual Rollback Recommended:**
- ⚠️ Performance degradation after deployment
- ⚠️ User reports of issues
- ⚠️ Memory leaks detected
- ⚠️ Unexpected behavior
- ⚠️ Security vulnerability discovered

**Emergency Rollback:**
- 🚨 Service completely down
- 🚨 Data corruption risk
- 🚨 Security incident
- 🚨 Critical bug affecting all users
- 🚨 Production outage

### When NOT to Rollback

**Proceed with Fix:**
- ✗ Minor cosmetic issues
- ✗ Non-critical warnings
- ✗ Feature not working but no errors
- ✗ Performance slightly slower
- ✗ Single user report

## Rollback Communication

### Notification Template

```markdown
## 🔄 Rollback Executed

**Environment:** Production  
**Time:** 2024-11-12 15:45:00 UTC  
**Initiated by:** @admin  
**Reason:** Verification failure - database timeout

**Previous Version:**
- Commit: abc1234
- Deployed: 2024-11-12 14:00:00 UTC
- Status: ✅ Verified working

**Rollback Details:**
- Backup: backup_20241112_140000
- Duration: 35 seconds
- Verification: ✅ Passed

**Next Steps:**
1. Investigate root cause
2. Fix issue in development
3. Test thoroughly
4. Redeploy when ready

**Status:** Service restored and operational
```

## Troubleshooting

### Rollback Fails to Start Bot

**Possible Causes:**
1. Backup corrupted
2. Configuration issue
3. Dependency missing
4. Permissions problem

**Solutions:**
1. Try older backup
2. Verify config file
3. Check requirements.txt
4. Fix file permissions: `chmod -R 755`

### Verification Fails After Rollback

**Possible Causes:**
1. Underlying system issue
2. Database corrupted
3. Network problem
4. Backup was also broken

**Solutions:**
1. Check system resources
2. Restore database backup
3. Check network connectivity
4. Try earlier backup

### No Backups Available

**Possible Causes:**
1. First deployment
2. Backup directory deleted
3. Backup retention policy
4. Disk space issue

**Solutions:**
1. Can't rollback first deployment
2. Restore from external backup
3. Adjust retention settings
4. Free disk space

### Emergency Rollback Needed But Workflow Requires Approval

**Solution:**
Use CLI command directly on server:

```bash
ssh production-server
cd /opt/rosey-bot
sudo ./scripts/rollback.sh prod --emergency
```

## Security Considerations

**Rollback Authorization:**
- ✅ Production rollbacks require admin access
- ✅ Audit trail maintained
- ✅ Reason required for manual rollbacks
- ✅ Notifications sent on rollback

**Backup Security:**
- ✅ Backups stored with restricted permissions
- ✅ No secrets in backup names
- ✅ Backup integrity verifiable
- ❌ Don't expose backup contents publicly

**Logging:**
- ✅ Log all rollback events
- ✅ Track who initiated rollback
- ✅ Include reason and outcome
- ❌ Don't log sensitive configuration

## Future Enhancements

### Phase 1 (Current Sortie):
- Enhanced rollback script
- Rollback history tracking
- Manual rollback workflow
- Comprehensive testing

### Phase 2 (Future):
- Rollback preview (show diff)
- Automated rollback tests
- Canary rollback (gradual)
- Rollback scheduling

### Phase 3 (Future):
- AI-assisted rollback decisions
- Predictive rollback suggestions
- Multi-service rollback coordination
- Cross-region rollback

## Commit Message

```bash
git add scripts/rollback.sh
git add scripts/rollback_history.py
git add .github/workflows/manual-rollback.yml
git add docs/ROLLBACK.md
git commit -m "feat: enhance rollback mechanism with comprehensive features

Production-ready rollback system with verification and history tracking.

scripts/rollback.sh (enhanced):
- Added dry-run mode for safe testing
- Added emergency mode (skip verification)
- Added specific backup selection
- Added backup listing (--list)
- Added rollback capability verification
- Enhanced logging to rollback.log
- Improved error handling
- Colored output for clarity
- Usage documentation
- Rollback verification after restore

Rollback Features:
- Standard rollback (with verification)
- Emergency rollback (fast, skip verification)
- Targeted rollback (specific backup)
- Dry-run mode (preview only)
- Backup listing
- Capability verification

scripts/rollback_history.py:
- Track all rollback events
- JSON-based history storage
- List recent rollbacks
- Filter by environment
- Show statistics
- Audit trail for compliance

.github/workflows/manual-rollback.yml:
- Manual rollback workflow dispatch
- Environment selection (test/prod)
- Emergency mode option
- Specific backup selection
- Reason required (audit trail)
- Lists available backups
- Verifies rollback capability
- Executes rollback
- Sends notifications

Rollback Types:
1. Automatic - triggered by verification failure
2. Manual CLI - ./scripts/rollback.sh <env>
3. Manual workflow - GitHub Actions UI
4. Emergency - skip verification for speed

Performance:
- Standard rollback: < 60s
- Emergency rollback: < 30s
- Find backup: < 1s
- Verification: < 20s

Exit Codes:
- 0: Success
- 1: Backup not found
- 2: Rollback completed but verification failed

Features:
- Comprehensive help text
- Multiple rollback modes
- History tracking
- Statistics reporting
- Audit trail
- Notification integration

Benefits:
- Fast recovery from bad deployments
- Multiple rollback strategies
- Clear audit trail
- Easy to use (CLI and UI)
- Safe with dry-run mode
- Emergency mode for critical issues

This provides reliable, fast rollback capability for all
deployment scenarios.

SPEC: Sortie 10 - Rollback Mechanism"
```

## Related Documentation

- **Sortie 3:** Deployment Scripts (original rollback.sh)
- **Sortie 6:** Test Channel Verification (verification integration)
- **Sortie 7:** Production Deploy Workflow (automatic rollback)
- **Sortie 9:** Production Verification (rollback triggers)

## Next Sortie

**Sortie 11: Deployment Dashboard** - Web-based dashboard for monitoring deployments, viewing history, and triggering rollbacks.

---

**Implementation Time Estimate:** 4-5 hours  
**Risk Level:** Low (improves reliability)  
**Priority:** High (critical for production safety)  
**Dependencies:** Sorties 3, 6, 7, 9 complete
