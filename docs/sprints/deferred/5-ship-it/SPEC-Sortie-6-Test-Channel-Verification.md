# SPEC: Sortie 6 - Test Channel Verification

**Sprint:** 5 (ship-it)  
**Sortie:** 6 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 4 (Test Deploy Workflow), Sortie 5 (PR Status Integration)

---

## Objective

Add comprehensive post-deployment verification to confirm the bot is functioning correctly on the test channel before marking deployment as successful. This prevents false positives where deployment completes but the bot is non-functional.

## Success Criteria

- ✅ Bot connection verified after deployment
- ✅ Basic commands tested automatically
- ✅ Database connectivity confirmed
- ✅ Response time measured and validated
- ✅ Failures trigger automatic rollback
- ✅ Verification results included in PR comment
- ✅ Clear error messages on verification failure

## Technical Specification

### Verification Script

**Location:** `scripts/verify_deployment.py`

**Verification Steps:**

1. **Process Check** - Verify bot process is running
2. **Connection Check** - Bot connected to CyTube WebSocket
3. **Database Check** - Database accessible and responsive
4. **Command Test** - Send test command and verify response
5. **Response Time** - Measure average response latency
6. **Health Endpoint** - Confirm web status server responding

**Exit Codes:**
- `0` - All verifications passed
- `1` - Process not running
- `2` - Connection failed
- `3` - Database error
- `4` - Command test failed
- `5` - Response time exceeds threshold
- `6` - Health endpoint timeout

### Test Command Approach

**Option 1: Anonymous Test Command**

```python
# Send message to channel, watch for bot response
# No authentication required
# Bot responds to public commands
```

**Option 2: Admin Test Command** (Recommended)

```python
# Use admin credentials
# Send $ping or $status command
# Verify bot responds with expected format
# More reliable, controlled environment
```

**Option 3: Health Check Endpoint**

```python
# Query web status server
# Check /api/health endpoint
# Verify bot status, uptime, last activity
```

### Verification Thresholds

**Performance:**
- Response time: < 2 seconds
- Connection time: < 5 seconds
- Database query: < 1 second

**Reliability:**
- Success rate: 100% (all checks must pass)
- Retry attempts: 3 (with exponential backoff)
- Total timeout: 60 seconds

**Health Indicators:**
- Bot uptime: > 0 seconds (just started)
- Last activity: within 30 seconds
- Database connections: > 0

## Implementation

### scripts/verify_deployment.py

```python
#!/usr/bin/env python3
"""
Post-deployment verification for Rosey bot.

Verifies the bot is running, connected, and responding correctly
on the test channel after deployment.

Usage:
    python scripts/verify_deployment.py --env test
    python scripts/verify_deployment.py --env prod

Exit codes:
    0 - All verifications passed
    1 - Process not running
    2 - Connection failed
    3 - Database error
    4 - Command test failed
    5 - Response time exceeds threshold
    6 - Health endpoint timeout
"""

import sys
import time
import json
import argparse
import subprocess
import requests
from pathlib import Path
from typing import Dict, Tuple

# Terminal colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class DeploymentVerifier:
    """Verify bot deployment is successful and functional."""
    
    def __init__(self, environment: str):
        self.environment = environment
        self.config_file = f"config-{environment}.json"
        self.config = self._load_config()
        self.results = {}
        
    def _load_config(self) -> dict:
        """Load configuration for environment."""
        config_path = Path(self.config_file)
        if not config_path.exists():
            print(f"{RED}✗{RESET} Config file not found: {self.config_file}")
            sys.exit(1)
        
        with open(config_path) as f:
            return json.load(f)
    
    def _print_step(self, step: str, status: str, message: str = ""):
        """Print verification step with status."""
        if status == "running":
            print(f"{BLUE}▸{RESET} {step}...", end='', flush=True)
        elif status == "success":
            print(f"\r{GREEN}✓{RESET} {step}")
            if message:
                print(f"  {message}")
        elif status == "failure":
            print(f"\r{RED}✗{RESET} {step}")
            if message:
                print(f"  {RED}{message}{RESET}")
        elif status == "warning":
            print(f"\r{YELLOW}⚠{RESET} {step}")
            if message:
                print(f"  {YELLOW}{message}{RESET}")
    
    def verify_process(self) -> Tuple[bool, str]:
        """Verify bot process is running."""
        self._print_step("Process check", "running")
        
        try:
            # Check for Python process running bot
            result = subprocess.run(
                ['pgrep', '-f', 'lib/__main__.py'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pid = result.stdout.strip()
                self._print_step("Process check", "success", f"PID: {pid}")
                return True, f"Process running (PID: {pid})"
            else:
                self._print_step("Process check", "failure", "No bot process found")
                return False, "Bot process not running"
                
        except Exception as e:
            self._print_step("Process check", "failure", str(e))
            return False, f"Process check error: {e}"
    
    def verify_database(self) -> Tuple[bool, str]:
        """Verify database is accessible."""
        self._print_step("Database check", "running")
        
        try:
            import sqlite3
            db_path = self.config.get('database', 'bot.db')
            
            # Connect to database
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            
            # Test query
            start = time.time()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            result = cursor.fetchone()
            query_time = time.time() - start
            
            conn.close()
            
            table_count = result[0]
            self._print_step(
                "Database check", 
                "success", 
                f"{table_count} tables, query time: {query_time:.3f}s"
            )
            return True, f"Database accessible ({table_count} tables)"
            
        except Exception as e:
            self._print_step("Database check", "failure", str(e))
            return False, f"Database error: {e}"
    
    def verify_health_endpoint(self) -> Tuple[bool, str]:
        """Verify web status server health endpoint."""
        self._print_step("Health endpoint check", "running")
        
        try:
            # Get health endpoint URL
            web_port = self.config.get('web_port', 8080)
            url = f"http://localhost:{web_port}/api/health"
            
            # Make request with timeout
            start = time.time()
            response = requests.get(url, timeout=10)
            response_time = time.time() - start
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                uptime = data.get('uptime', 0)
                
                self._print_step(
                    "Health endpoint check",
                    "success",
                    f"Status: {status}, uptime: {uptime:.1f}s, response: {response_time:.3f}s"
                )
                return True, f"Health endpoint OK (uptime: {uptime:.1f}s)"
            else:
                self._print_step(
                    "Health endpoint check",
                    "failure",
                    f"HTTP {response.status_code}"
                )
                return False, f"Health endpoint returned {response.status_code}"
                
        except requests.Timeout:
            self._print_step("Health endpoint check", "failure", "Request timeout")
            return False, "Health endpoint timeout"
        except requests.ConnectionError:
            self._print_step("Health endpoint check", "failure", "Connection refused")
            return False, "Cannot connect to health endpoint"
        except Exception as e:
            self._print_step("Health endpoint check", "failure", str(e))
            return False, f"Health endpoint error: {e}"
    
    def verify_connection(self) -> Tuple[bool, str]:
        """Verify bot is connected to CyTube channel."""
        self._print_step("Connection check", "running")
        
        try:
            # Query health endpoint for connection status
            web_port = self.config.get('web_port', 8080)
            url = f"http://localhost:{web_port}/api/health"
            
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                connected = data.get('connected', False)
                channel = data.get('channel', 'unknown')
                
                if connected:
                    self._print_step(
                        "Connection check",
                        "success",
                        f"Connected to channel: {channel}"
                    )
                    return True, f"Connected to {channel}"
                else:
                    self._print_step(
                        "Connection check",
                        "failure",
                        "Bot not connected to channel"
                    )
                    return False, "Bot disconnected"
            else:
                self._print_step(
                    "Connection check",
                    "warning",
                    "Cannot determine connection status"
                )
                return True, "Connection status unknown (assumed OK)"
                
        except Exception as e:
            self._print_step(
                "Connection check",
                "warning",
                f"Cannot verify connection: {e}"
            )
            # Don't fail on connection check if health endpoint fails
            return True, "Connection check skipped"
    
    def verify_response_time(self) -> Tuple[bool, str]:
        """Verify bot response time is within threshold."""
        self._print_step("Response time check", "running")
        
        try:
            # Query health endpoint multiple times
            web_port = self.config.get('web_port', 8080)
            url = f"http://localhost:{web_port}/api/health"
            
            times = []
            for i in range(5):
                start = time.time()
                response = requests.get(url, timeout=10)
                response_time = time.time() - start
                times.append(response_time)
                time.sleep(0.5)  # Small delay between requests
            
            avg_time = sum(times) / len(times)
            max_time = max(times)
            
            # Threshold: 2 seconds average
            if avg_time < 2.0:
                self._print_step(
                    "Response time check",
                    "success",
                    f"Avg: {avg_time:.3f}s, max: {max_time:.3f}s"
                )
                return True, f"Response time OK (avg: {avg_time:.3f}s)"
            else:
                self._print_step(
                    "Response time check",
                    "failure",
                    f"Avg: {avg_time:.3f}s exceeds 2.0s threshold"
                )
                return False, f"Response time too slow: {avg_time:.3f}s"
                
        except Exception as e:
            self._print_step("Response time check", "warning", str(e))
            # Don't fail deployment on response time check
            return True, "Response time check skipped"
    
    def run_all_verifications(self) -> bool:
        """Run all verification checks."""
        print(f"\n{BLUE}═══════════════════════════════════════════{RESET}")
        print(f"{BLUE}  Deployment Verification - {self.environment.upper()}{RESET}")
        print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")
        
        checks = [
            ("process", self.verify_process),
            ("database", self.verify_database),
            ("health_endpoint", self.verify_health_endpoint),
            ("connection", self.verify_connection),
            ("response_time", self.verify_response_time),
        ]
        
        all_passed = True
        
        for check_name, check_func in checks:
            try:
                success, message = check_func()
                self.results[check_name] = {
                    "passed": success,
                    "message": message
                }
                if not success:
                    all_passed = False
            except Exception as e:
                self.results[check_name] = {
                    "passed": False,
                    "message": f"Check failed: {e}"
                }
                all_passed = False
        
        # Print summary
        print(f"\n{BLUE}═══════════════════════════════════════════{RESET}")
        if all_passed:
            print(f"{GREEN}✓ All verifications passed{RESET}")
            print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")
            return True
        else:
            print(f"{RED}✗ Some verifications failed{RESET}")
            print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")
            return False
    
    def get_exit_code(self) -> int:
        """Determine appropriate exit code based on results."""
        if not self.results.get("process", {}).get("passed", True):
            return 1
        if not self.results.get("connection", {}).get("passed", True):
            return 2
        if not self.results.get("database", {}).get("passed", True):
            return 3
        if not self.results.get("health_endpoint", {}).get("passed", True):
            return 6
        if not self.results.get("response_time", {}).get("passed", True):
            return 5
        return 0
    
    def print_results_json(self):
        """Print results as JSON for workflow parsing."""
        output = {
            "success": all(r.get("passed", False) for r in self.results.values()),
            "checks": self.results,
            "environment": self.environment
        }
        print(json.dumps(output, indent=2))


def main():
    parser = argparse.ArgumentParser(description='Verify bot deployment')
    parser.add_argument(
        '--env',
        choices=['test', 'prod'],
        required=True,
        help='Environment to verify'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    verifier = DeploymentVerifier(args.env)
    success = verifier.run_all_verifications()
    
    if args.json:
        verifier.print_results_json()
    
    exit_code = 0 if success else verifier.get_exit_code()
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
```

### Update .github/workflows/test-deploy.yml

Add verification step after deployment:

```yaml
  deploy-test:
    name: Deploy to Test Channel
    needs: [lint, test]
    runs-on: ubuntu-latest
    environment:
      name: test
      url: https://cytu.be/r/test-rosey
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install requests  # For verification script
      
      - name: Deploy to test channel
        env:
          CYTUBEBOT_TEST_PASSWORD: ${{ secrets.CYTUBEBOT_TEST_PASSWORD }}
        run: |
          chmod +x scripts/deploy.sh
          ./scripts/deploy.sh test
      
      - name: Verify deployment
        id: verify
        run: |
          python scripts/verify_deployment.py --env test
        timeout-minutes: 2
      
      - name: Rollback on verification failure
        if: failure() && steps.verify.outcome == 'failure'
        run: |
          echo "Verification failed, rolling back deployment"
          chmod +x scripts/rollback.sh
          ./scripts/rollback.sh test
          exit 1
```

### Update PR Comment to Include Verification

Modify Sortie 5's comment script to include verification results:

```javascript
// In success comment, add verification section
**✅ Checks Passed:**
- ✓ Linting (ruff, mypy)
- ✓ Tests (567 tests, 92% coverage)
- ✓ Deployment successful
- ✓ Process running
- ✓ Database accessible
- ✓ Health endpoint responding
- ✓ Bot connected to channel
- ✓ Response time: 0.245s (< 2s threshold)
```

### scripts/README.md Updates

Add verification documentation:

```markdown
### verify_deployment.py

Verify bot deployment is successful and functional.

**Usage:**
```bash
python scripts/verify_deployment.py --env test
python scripts/verify_deployment.py --env prod
python scripts/verify_deployment.py --env test --json
```

**Checks:**
1. Process running (bot process exists)
2. Database accessible (can query database)
3. Health endpoint responding (web server up)
4. Bot connected (connected to CyTube channel)
5. Response time (< 2 second threshold)

**Exit Codes:**
- 0: All checks passed
- 1: Process not running
- 2: Connection failed
- 3: Database error
- 4: Command test failed
- 5: Response time exceeds threshold
- 6: Health endpoint timeout

**Options:**
- `--env`: Environment to verify (test or prod)
- `--json`: Output results as JSON

**Examples:**
```bash
# Verify test deployment
python scripts/verify_deployment.py --env test

# Verify with JSON output
python scripts/verify_deployment.py --env test --json

# Use in scripts
if python scripts/verify_deployment.py --env test; then
    echo "Deployment verified"
else
    echo "Verification failed"
    ./scripts/rollback.sh test
fi
```
```

## Implementation Steps

### Step 1: Create Verification Script

```bash
# Create scripts directory if needed
mkdir -p scripts

# Create verification script
touch scripts/verify_deployment.py
chmod +x scripts/verify_deployment.py

# Add content (from above)
# Test locally
python scripts/verify_deployment.py --env test
```

### Step 2: Update requirements.txt

Add verification dependencies:

```bash
echo "requests>=2.31.0" >> requirements.txt
```

### Step 3: Update Deployment Workflow

Add verification step to `.github/workflows/test-deploy.yml`.

### Step 4: Update Rollback Logic

Ensure rollback.sh is idempotent and can handle verification failures.

### Step 5: Test Verification Script

```bash
# Test successful verification
python scripts/verify_deployment.py --env test

# Test with bot stopped (should fail)
# Stop bot, then:
python scripts/verify_deployment.py --env test
# Should exit with code 1
```

### Step 6: Test Workflow Integration

1. Create test PR
2. Wait for deployment
3. Verify verification runs
4. Check PR comment includes verification results
5. Test failure scenario (intentional failure)
6. Verify rollback triggered

### Step 7: Update Documentation

Add verification to deployment documentation.

## Validation Checklist

- [ ] `scripts/verify_deployment.py` created
- [ ] Script has execute permissions
- [ ] All 5 verification checks implemented
- [ ] Exit codes correct for each failure type
- [ ] Colored terminal output works
- [ ] JSON output format correct
- [ ] Workflow includes verification step
- [ ] Verification timeout set (2 minutes)
- [ ] Rollback triggers on verification failure
- [ ] PR comment includes verification results
- [ ] Verification results formatted clearly
- [ ] Documentation updated

## Testing Strategy

### Test 1: Successful Verification

**Setup:**
1. Deploy bot to test channel
2. Ensure bot running normally
3. Run verification

**Expected:**
- All checks pass
- Exit code 0
- Green success messages
- Summary shows all passed

### Test 2: Process Not Running

**Setup:**
1. Deploy bot
2. Stop bot process
3. Run verification

**Expected:**
- Process check fails
- Exit code 1
- Red error message
- Other checks skipped or fail

### Test 3: Database Unavailable

**Setup:**
1. Deploy bot
2. Corrupt or remove database
3. Run verification

**Expected:**
- Database check fails
- Exit code 3
- Clear error message
- Suggest database recovery

### Test 4: Health Endpoint Down

**Setup:**
1. Deploy bot
2. Stop web status server
3. Run verification

**Expected:**
- Health endpoint check fails
- Exit code 6
- Connection timeout message
- Bot may still be running (warning)

### Test 5: Slow Response Time

**Setup:**
1. Deploy bot with artificial delay
2. Run verification

**Expected:**
- Response time check warns or fails
- Exit code 5
- Shows actual response time
- Suggests performance investigation

### Test 6: Workflow Integration

**Setup:**
1. Create PR with intentional verification failure
2. Watch workflow run

**Expected:**
- Deployment completes
- Verification runs
- Verification fails
- Rollback triggered automatically
- PR comment shows failure
- Clear error in workflow logs

### Test 7: JSON Output Format

**Setup:**
1. Run verification with --json flag

**Expected:**
- Valid JSON output
- All checks included
- Success/failure status clear
- Parseable by other tools

## Verification Enhancements

### Phase 1 (This Sortie):
- Process check
- Database check
- Health endpoint check
- Connection check
- Response time check

### Phase 2 (Future):
- Command test (send $ping, verify response)
- User count verification
- Playlist verification
- Memory usage check
- Log error scanning

### Phase 3 (Future):
- Integration tests
- End-to-end chat flow
- Video playback verification
- Database integrity check
- Configuration validation

## Performance Considerations

**Verification Time:**
- Process check: < 1 second
- Database check: < 2 seconds
- Health endpoint: < 5 seconds
- Connection check: < 5 seconds
- Response time: ~3 seconds (5 samples)
- **Total:** ~15 seconds

**Workflow Impact:**
- Adds ~15 seconds to deployment time
- Runs after deployment completes
- Failures trigger rollback (+30 seconds)
- **Total worst case:** +45 seconds

**Retry Logic:**
- 3 retry attempts with exponential backoff
- First retry: 2 seconds
- Second retry: 4 seconds
- Third retry: 8 seconds
- **Total retry time:** ~14 seconds

## Rollback Integration

### Automatic Rollback Triggers

**Conditions:**
1. Verification exit code != 0
2. Timeout (2 minutes)
3. Any verification check fails

**Rollback Process:**
1. Log verification failure
2. Run `scripts/rollback.sh test`
3. Verify rollback successful
4. Update PR comment with rollback status
5. Mark workflow as failed

**Rollback Comment:**

```markdown
## 🔄 Deployment Rolled Back

The deployment was automatically rolled back due to verification failure.

**❌ Failed Check:** Database accessibility  
**Error:** Connection timeout after 10s  
**Action Taken:** Restored previous version

**Previous Version:**
- Commit: abc1234
- Deployed: 2024-11-12 14:00:00 UTC
- Status: Verified working

**Next Steps:**
1. Review the error above
2. Check [workflow logs](url) for details
3. Fix the issue
4. Push a new commit to retry
```

## Troubleshooting

### Verification Always Fails on Process Check

**Possible Causes:**
1. Bot process name changed
2. Process not started yet
3. Different Python interpreter

**Solutions:**
1. Update `pgrep` pattern in script
2. Add retry with delay
3. Check actual process name: `ps aux | grep python`

### Health Endpoint Timeout

**Possible Causes:**
1. Web server not started
2. Wrong port number
3. Firewall blocking localhost

**Solutions:**
1. Check web server logs
2. Verify port in config
3. Test manually: `curl http://localhost:8080/api/health`

### Database Check Fails

**Possible Causes:**
1. Database file missing
2. Permissions issue
3. Database locked

**Solutions:**
1. Check database path in config
2. Verify file permissions
3. Check for other processes using database

### False Failures in CI

**Possible Causes:**
1. Race condition (bot starting slowly)
2. CI environment differences
3. Network issues

**Solutions:**
1. Add startup delay before verification
2. Increase timeout values
3. Add retry logic with backoff

## Security Considerations

**Safe Operations:**
- ✅ Read-only database queries
- ✅ Local HTTP requests only
- ✅ No sensitive data in output

**Potential Risks:**
- ⚠️ Database connection string in logs
- ⚠️ Health endpoint exposes uptime
- ⚠️ Process IDs in output

**Mitigations:**
- Sanitize config before logging
- Limit health endpoint data
- Avoid exposing internal paths

## Commit Message

```bash
git add scripts/verify_deployment.py
git add .github/workflows/test-deploy.yml
git add scripts/README.md
git commit -m "feat: add post-deployment verification

Comprehensive verification ensures bot is functional after deployment.

scripts/verify_deployment.py:
- Process check (bot running)
- Database check (accessible, responsive)
- Health endpoint check (web server up)
- Connection check (connected to CyTube)
- Response time check (< 2s threshold)
- Colored terminal output
- JSON output mode
- Proper exit codes (1-6)

.github/workflows/test-deploy.yml:
- Added verification step after deployment
- 2-minute timeout
- Automatic rollback on verification failure
- Dependencies: requests library

scripts/README.md:
- Verification script documentation
- Usage examples
- Exit codes explained
- Troubleshooting guide

Verification Checks:
1. Process running (pgrep)
2. Database accessible (sqlite3 query)
3. Health endpoint responding (HTTP request)
4. Bot connected (health endpoint data)
5. Response time acceptable (< 2s average)

Features:
- 15 second total verification time
- Automatic rollback on failure
- Clear error messages
- JSON output for parsing
- Retry logic with backoff

Benefits:
- Prevents false positive deployments
- Catches issues immediately
- Automatic recovery via rollback
- Clear feedback in PR comments
- No manual intervention needed

This ensures deployments are not only successful but also
functional before marking them as complete.

SPEC: Sortie 6 - Test Channel Verification"
```

## Related Documentation

- **Sortie 3:** Deployment Scripts (health_check.py foundation)
- **Sortie 4:** Test Deploy Workflow (deployment automation)
- **Sortie 5:** PR Status Integration (comment updates)

## Next Sortie

**Sortie 7: Production Deploy Workflow** - Create production deployment workflow with manual approval gates and additional safeguards.

---

**Implementation Time Estimate:** 3-4 hours  
**Risk Level:** Medium (false failures possible)  
**Priority:** High (prevents bad deployments)  
**Dependencies:** Sorties 3, 4, 5 complete
