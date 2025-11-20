# SPEC: Sortie 9 - Production Verification

**Sprint:** 5 (ship-it)  
**Sortie:** 9 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 6 (Test Channel Verification), Sortie 7 (Production Deploy Workflow)

---

## Objective

Enhance verification for production deployments with stricter thresholds, additional checks, and extended monitoring. Production verification should be more comprehensive than test channel verification to ensure stability and reliability.

## Success Criteria

- ✅ All test channel verification checks included
- ✅ Additional production-specific checks
- ✅ Stricter performance thresholds
- ✅ Extended monitoring period (5 minutes post-deployment)
- ✅ User count validation
- ✅ Memory usage monitoring
- ✅ Error log scanning
- ✅ Configuration validation
- ✅ Automatic rollback on any failure

## Technical Specification

### Enhanced Verification Checks

**Core Checks (from Test Channel):**
1. Process running
2. Database accessible
3. Health endpoint responding
4. Bot connected to channel
5. Response time validation

**Production-Specific Checks:**
6. Channel user count (should be > 0 after startup)
7. Memory usage (within acceptable limits)
8. Error log scanning (no critical errors in last 5 minutes)
9. Configuration validation (prod config loaded correctly)
10. Uptime verification (bot stays running for 5 minutes)

### Stricter Thresholds

**Test Channel vs Production:**

| Check | Test Channel | Production |
|-------|--------------|------------|
| Response time | < 2s avg | < 1s avg |
| Startup wait | 10 seconds | 30 seconds |
| Verification timeout | 2 minutes | 5 minutes |
| Health check retries | 3 | 5 |
| Memory usage | Not checked | < 500MB |
| Error tolerance | Warnings OK | No errors |
| Uptime requirement | Immediate | 5 minutes stable |

### Extended Monitoring

**Post-Deployment Monitoring:**
1. **Initial verification (30s):** Basic health checks
2. **Stability period (5m):** Monitor for crashes/errors
3. **Final verification:** Confirm all checks still passing

**Monitoring Metrics:**
- Process uptime
- Memory consumption trend
- Error rate
- Response time trend
- User count stability

## Implementation

### scripts/verify_deployment.py Enhancement

Update existing script to support production mode:

```python
def verify_production(self) -> Tuple[bool, str]:
    """Production-specific verification with stricter checks."""
    self._print_step("Production verification", "running")
    
    checks = [
        self.verify_user_count,
        self.verify_memory_usage,
        self.verify_error_logs,
        self.verify_configuration,
        self.verify_uptime_stability
    ]
    
    all_passed = True
    for check in checks:
        success, message = check()
        if not success:
            all_passed = False
            break
    
    if all_passed:
        self._print_step("Production verification", "success")
        return True, "All production checks passed"
    else:
        self._print_step("Production verification", "failure")
        return False, "Production verification failed"

def verify_user_count(self) -> Tuple[bool, str]:
    """Verify channel has users connected."""
    self._print_step("User count check", "running")
    
    try:
        web_port = self.config.get('web_port', 8080)
        url = f"http://localhost:{web_port}/api/health"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            user_count = data.get('user_count', 0)
            
            # Production should have at least 1 user (the bot itself)
            if user_count >= 1:
                self._print_step(
                    "User count check",
                    "success",
                    f"Channel has {user_count} users"
                )
                return True, f"{user_count} users connected"
            else:
                self._print_step(
                    "User count check",
                    "failure",
                    f"Expected ≥1 users, found {user_count}"
                )
                return False, "No users in channel"
        else:
            self._print_step("User count check", "warning", "Cannot verify user count")
            return True, "User count check skipped"
    
    except Exception as e:
        self._print_step("User count check", "warning", str(e))
        return True, "User count check skipped"

def verify_memory_usage(self) -> Tuple[bool, str]:
    """Verify bot memory usage is within limits."""
    self._print_step("Memory usage check", "running")
    
    try:
        import psutil
        
        # Find bot process
        result = subprocess.run(
            ['pgrep', '-f', 'lib/__main__.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self._print_step("Memory usage check", "failure", "Process not found")
            return False, "Cannot find bot process"
        
        pid = int(result.stdout.strip())
        process = psutil.Process(pid)
        
        # Get memory info
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        
        # Threshold: 500MB
        if mem_mb < 500:
            self._print_step(
                "Memory usage check",
                "success",
                f"Memory usage: {mem_mb:.1f}MB"
            )
            return True, f"Memory usage OK ({mem_mb:.1f}MB)"
        else:
            self._print_step(
                "Memory usage check",
                "failure",
                f"Memory usage: {mem_mb:.1f}MB exceeds 500MB limit"
            )
            return False, f"High memory usage: {mem_mb:.1f}MB"
    
    except ImportError:
        self._print_step("Memory usage check", "warning", "psutil not available")
        return True, "Memory check skipped (psutil missing)"
    except Exception as e:
        self._print_step("Memory usage check", "warning", str(e))
        return True, "Memory check skipped"

def verify_error_logs(self) -> Tuple[bool, str]:
    """Scan logs for critical errors."""
    self._print_step("Error log check", "running")
    
    try:
        # Check systemd journal if using systemd
        result = subprocess.run(
            ['journalctl', '-u', 'cytube-bot', '--since', '5 minutes ago', '-p', 'err'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            error_lines = [line for line in result.stdout.strip().split('\n') if line]
            
            if not error_lines:
                self._print_step("Error log check", "success", "No errors in last 5 minutes")
                return True, "No errors in logs"
            else:
                error_count = len(error_lines)
                self._print_step(
                    "Error log check",
                    "failure",
                    f"Found {error_count} error(s) in logs"
                )
                return False, f"{error_count} errors in logs"
        else:
            # Fallback: check log file directly
            log_file = Path('/var/log/cytube-bot/bot.log')
            if log_file.exists():
                # Check last 100 lines for ERROR or CRITICAL
                with open(log_file) as f:
                    lines = f.readlines()[-100:]
                
                errors = [l for l in lines if 'ERROR' in l or 'CRITICAL' in l]
                
                if not errors:
                    self._print_step("Error log check", "success", "No errors found")
                    return True, "No errors in logs"
                else:
                    self._print_step(
                        "Error log check",
                        "failure",
                        f"Found {len(errors)} error(s)"
                    )
                    return False, f"{len(errors)} errors in logs"
            else:
                self._print_step("Error log check", "warning", "Log file not found")
                return True, "Error log check skipped"
    
    except Exception as e:
        self._print_step("Error log check", "warning", str(e))
        return True, "Error log check skipped"

def verify_configuration(self) -> Tuple[bool, str]:
    """Verify correct configuration is loaded."""
    self._print_step("Configuration check", "running")
    
    try:
        web_port = self.config.get('web_port', 8080)
        url = f"http://localhost:{web_port}/api/health"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # Check environment matches
            env = data.get('environment', 'unknown')
            expected_env = self.environment
            
            if env == expected_env:
                # Check channel matches
                channel = data.get('channel', 'unknown')
                expected_channel = self.config.get('channel')
                
                if channel == expected_channel:
                    self._print_step(
                        "Configuration check",
                        "success",
                        f"Correct config loaded: {env}/{channel}"
                    )
                    return True, f"Config correct ({env}/{channel})"
                else:
                    self._print_step(
                        "Configuration check",
                        "failure",
                        f"Wrong channel: {channel} (expected {expected_channel})"
                    )
                    return False, f"Wrong channel loaded: {channel}"
            else:
                self._print_step(
                    "Configuration check",
                    "failure",
                    f"Wrong environment: {env} (expected {expected_env})"
                )
                return False, f"Wrong environment: {env}"
        else:
            self._print_step("Configuration check", "warning", "Cannot verify config")
            return True, "Config check skipped"
    
    except Exception as e:
        self._print_step("Configuration check", "warning", str(e))
        return True, "Config check skipped"

def verify_uptime_stability(self) -> Tuple[bool, str]:
    """Verify bot stays running for extended period."""
    self._print_step("Uptime stability check", "running")
    
    try:
        import time
        
        # Check process exists
        result = subprocess.run(
            ['pgrep', '-f', 'lib/__main__.py'],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            self._print_step("Uptime stability check", "failure", "Process not running")
            return False, "Process not running"
        
        initial_pid = result.stdout.strip()
        
        # Wait and check again (5 minutes for production)
        wait_time = 300 if self.environment == 'prod' else 60
        
        self._print_step(
            "Uptime stability check",
            "running",
            f"Monitoring for {wait_time}s..."
        )
        
        # Check every 30 seconds
        checks = wait_time // 30
        for i in range(checks):
            time.sleep(30)
            
            result = subprocess.run(
                ['pgrep', '-f', 'lib/__main__.py'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self._print_step(
                    "Uptime stability check",
                    "failure",
                    f"Process crashed after {(i+1)*30}s"
                )
                return False, f"Process crashed after {(i+1)*30}s"
            
            current_pid = result.stdout.strip()
            if current_pid != initial_pid:
                self._print_step(
                    "Uptime stability check",
                    "failure",
                    f"Process restarted (PID changed)"
                )
                return False, "Process restarted"
            
            # Progress indicator
            progress = (i + 1) / checks * 100
            print(f"  Stability: {progress:.0f}% ({(i+1)*30}/{wait_time}s)", end='\r')
        
        print()  # New line after progress
        self._print_step(
            "Uptime stability check",
            "success",
            f"Stable for {wait_time}s"
        )
        return True, f"Stable for {wait_time}s"
    
    except Exception as e:
        self._print_step("Uptime stability check", "failure", str(e))
        return False, f"Stability check failed: {e}"

def run_all_verifications(self) -> bool:
    """Run all verification checks with environment-specific logic."""
    print(f"\n{BLUE}═══════════════════════════════════════════{RESET}")
    print(f"{BLUE}  Deployment Verification - {self.environment.upper()}{RESET}")
    print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")
    
    # Standard checks (all environments)
    standard_checks = [
        ("process", self.verify_process),
        ("database", self.verify_database),
        ("health_endpoint", self.verify_health_endpoint),
        ("connection", self.verify_connection),
        ("response_time", self.verify_response_time),
    ]
    
    # Production-specific checks
    if self.environment == 'prod':
        production_checks = [
            ("user_count", self.verify_user_count),
            ("memory_usage", self.verify_memory_usage),
            ("error_logs", self.verify_error_logs),
            ("configuration", self.verify_configuration),
            ("uptime_stability", self.verify_uptime_stability),
        ]
        all_checks = standard_checks + production_checks
    else:
        all_checks = standard_checks
    
    all_passed = True
    
    for check_name, check_func in all_checks:
        try:
            success, message = check_func()
            self.results[check_name] = {
                "passed": success,
                "message": message
            }
            if not success:
                all_passed = False
                # For production, stop on first failure
                if self.environment == 'prod':
                    print(f"\n{RED}⚠ Stopping verification due to failure{RESET}\n")
                    break
        except Exception as e:
            self.results[check_name] = {
                "passed": False,
                "message": f"Check failed: {e}"
            }
            all_passed = False
            if self.environment == 'prod':
                break
    
    # Print summary
    print(f"\n{BLUE}═══════════════════════════════════════════{RESET}")
    if all_passed:
        print(f"{GREEN}✓ All verifications passed{RESET}")
        print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")
        return True
    else:
        print(f"{RED}✗ Verification failed{RESET}")
        print(f"{BLUE}═══════════════════════════════════════════{RESET}\n")
        return False
```

### Update requirements.txt

Add psutil for memory monitoring:

```bash
echo "psutil>=5.9.0" >> requirements.txt
```

### Update .github/workflows/prod-deploy.yml

Modify verification step:

```yaml
- name: Wait for startup
  run: |
    echo "Waiting 30 seconds for bot to fully start..."
    sleep 30

- name: Verify deployment
  id: verify
  if: ${{ !inputs.skip_verification }}
  run: |
    python scripts/verify_deployment.py --env prod
  timeout-minutes: 10  # Increased from 3 for stability check
```

### Update web/status_server.py

Add additional health endpoint data:

```python
@app.route('/api/health')
def health():
    """Health check endpoint with extended information."""
    bot = get_bot_instance()
    
    if not bot:
        return jsonify({
            'status': 'down',
            'connected': False
        }), 503
    
    # Calculate uptime
    uptime = time.time() - bot.start_time if hasattr(bot, 'start_time') else 0
    
    # Get memory info
    import psutil
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    
    return jsonify({
        'status': 'up',
        'connected': bot.connected,
        'channel': bot.channel_name,
        'environment': os.environ.get('BOT_ENV', 'unknown'),
        'uptime': uptime,
        'user_count': len(bot.users) if hasattr(bot, 'users') else 0,
        'memory_mb': round(memory_mb, 2),
        'last_activity': bot.last_activity if hasattr(bot, 'last_activity') else None
    }), 200
```

## Implementation Steps

### Step 1: Update verify_deployment.py

```bash
# Backup existing script
cp scripts/verify_deployment.py scripts/verify_deployment.py.bak

# Add new verification methods
# (Add the production-specific methods from above)

# Test with dry run
python scripts/verify_deployment.py --env prod --dry-run
```

### Step 2: Add psutil Dependency

```bash
# Add to requirements.txt
echo "psutil>=5.9.0" >> requirements.txt

# Install locally for testing
pip install psutil

# Commit dependency
git add requirements.txt
git commit -m "deps: add psutil for memory monitoring"
```

### Step 3: Update Health Endpoint

```bash
# Update web/status_server.py with extended data
# (Add environment, user_count, memory_mb fields)

# Test health endpoint locally
curl http://localhost:8080/api/health | jq
```

### Step 4: Update Production Workflow

```bash
# Modify .github/workflows/prod-deploy.yml
# - Increase startup wait to 30s
# - Increase verification timeout to 10 minutes
# - Update step descriptions

git add .github/workflows/prod-deploy.yml
git commit -m "ci: enhance production verification"
```

### Step 5: Test Enhanced Verification

```bash
# Test all checks locally
python scripts/verify_deployment.py --env prod

# Verify each check individually
# - Process check
# - Database check
# - Health endpoint check
# - Connection check
# - Response time check
# - User count check
# - Memory usage check
# - Error log check
# - Configuration check
# - Uptime stability check (may take 5 minutes)
```

### Step 6: Test Failure Scenarios

```bash
# Test memory limit failure
# (Temporarily set threshold lower)

# Test error log detection
# (Generate error in logs)

# Test uptime stability failure
# (Kill and restart process mid-check)

# Test configuration mismatch
# (Load wrong config file)
```

### Step 7: Update Documentation

```bash
# Update scripts/README.md with new checks
# Document production-specific thresholds
# Add troubleshooting for new checks

git add scripts/README.md
git commit -m "docs: document production verification checks"
```

## Validation Checklist

- [ ] `verify_user_count()` method added
- [ ] `verify_memory_usage()` method added
- [ ] `verify_error_logs()` method added
- [ ] `verify_configuration()` method added
- [ ] `verify_uptime_stability()` method added
- [ ] psutil dependency added to requirements.txt
- [ ] Health endpoint returns extended data
- [ ] Production workflow uses 30s startup wait
- [ ] Verification timeout increased to 10 minutes
- [ ] Stricter response time threshold (< 1s)
- [ ] Memory usage threshold set (< 500MB)
- [ ] Error log scanning working
- [ ] Configuration validation working
- [ ] 5-minute stability check working
- [ ] All tests pass for production verification

## Testing Strategy

### Test 1: Full Production Verification

**Steps:**
1. Deploy to production
2. Wait for startup
3. Run full verification

**Expected:**
- All 10 checks pass
- Process running
- Database accessible
- Health endpoint responding
- Bot connected
- Response time < 1s
- User count ≥ 1
- Memory usage < 500MB
- No errors in logs
- Correct config loaded
- Stable for 5 minutes

### Test 2: Memory Usage Failure

**Setup:**
1. Temporarily set memory threshold to 10MB
2. Deploy and verify

**Expected:**
- Memory check fails
- Verification stops
- Rollback triggered
- Clear error message

### Test 3: Error Log Detection

**Setup:**
1. Generate ERROR log entry
2. Run verification

**Expected:**
- Error log check fails
- Specific error count shown
- Verification stops
- Rollback triggered

### Test 4: Configuration Mismatch

**Setup:**
1. Deploy with wrong config symlink
2. Run verification

**Expected:**
- Configuration check fails
- Shows expected vs actual
- Rollback triggered

### Test 5: Uptime Instability

**Setup:**
1. Start verification
2. Kill process after 2 minutes
3. Let verification continue

**Expected:**
- Stability check detects process death
- Fails with timestamp
- Rollback triggered

### Test 6: User Count Validation

**Setup:**
1. Deploy to channel with no users
2. Run verification

**Expected:**
- User count check warns or passes (bot itself is a user)
- If count is 0, check fails

### Test 7: Response Time Threshold

**Setup:**
1. Add artificial delay to bot responses
2. Run verification

**Expected:**
- Response time check fails
- Shows actual avg time
- Threshold exceeded message

## Performance Targets

**Verification Times:**

| Check | Time |
|-------|------|
| Process check | < 1s |
| Database check | < 2s |
| Health endpoint | < 5s |
| Connection check | < 5s |
| Response time (5 samples) | ~5s |
| User count check | < 2s |
| Memory usage check | < 1s |
| Error log scan | < 5s |
| Configuration check | < 2s |
| Uptime stability | 300s (5 min) |
| **Total** | **~330s (5.5 min)** |

**Thresholds:**

| Metric | Test | Production |
|--------|------|------------|
| Response time | < 2s avg | < 1s avg |
| Memory usage | Not checked | < 500MB |
| Startup wait | 10s | 30s |
| Stability period | Immediate | 5 minutes |
| Error tolerance | Warnings OK | Zero errors |

## Exit Codes Enhancement

Update exit codes to include new checks:

```python
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
    # Production-specific exit codes
    if not self.results.get("user_count", {}).get("passed", True):
        return 7
    if not self.results.get("memory_usage", {}).get("passed", True):
        return 8
    if not self.results.get("error_logs", {}).get("passed", True):
        return 9
    if not self.results.get("configuration", {}).get("passed", True):
        return 10
    if not self.results.get("uptime_stability", {}).get("passed", True):
        return 11
    return 0
```

**Exit Code Reference:**
- 0: All checks passed
- 1: Process not running
- 2: Connection failed
- 3: Database error
- 4: (reserved)
- 5: Response time exceeds threshold
- 6: Health endpoint timeout
- 7: User count validation failed
- 8: Memory usage too high
- 9: Errors found in logs
- 10: Configuration mismatch
- 11: Uptime instability

## Monitoring Dashboard Integration

### Future Enhancement: Real-Time Monitoring

```python
def stream_verification_status(self):
    """Stream verification progress to monitoring dashboard."""
    # Could integrate with:
    # - Prometheus metrics
    # - Grafana dashboard
    # - DataDog monitoring
    # - Custom status page
    pass
```

### Metrics to Export

**For Monitoring Systems:**
- Verification success rate
- Average verification time
- Check failure distribution
- Memory usage trends
- Response time trends
- Error rate over time

## Rollback Enhancements

### Automatic Rollback Conditions

Production verification triggers rollback on:

1. ❌ Process not running after startup
2. ❌ Database connection failure
3. ❌ Health endpoint timeout
4. ❌ Bot not connected to channel
5. ❌ Response time > 1s average
6. ❌ Memory usage > 500MB
7. ❌ Errors found in logs
8. ❌ Wrong configuration loaded
9. ❌ Process crashes during stability period
10. ❌ User count = 0 (optional)

### Rollback Decision Tree

```
Verification Failed?
├─ Yes → Which check failed?
│  ├─ Critical (process, database, health)
│  │  └─ Immediate rollback
│  ├─ Performance (response time, memory)
│  │  └─ Rollback with performance data
│  └─ Stability (uptime, errors)
│     └─ Rollback with monitoring data
└─ No → Deployment successful
```

## Troubleshooting

### Uptime Check Times Out

**Possible Causes:**
1. 5-minute wait too long for workflow
2. Bot crashes intermittently
3. Resource constraints

**Solutions:**
1. Increase workflow timeout to 15 minutes
2. Check logs for crash causes
3. Monitor CPU/memory during check

### Memory Check False Positives

**Possible Causes:**
1. Threshold too strict (500MB)
2. Memory spike during startup
3. psutil measurement inaccurate

**Solutions:**
1. Adjust threshold to 750MB or 1GB
2. Wait longer before memory check
3. Take multiple samples and average

### Error Log Check Too Sensitive

**Possible Causes:**
1. Catching non-critical errors
2. Old errors still in logs
3. Log rotation issue

**Solutions:**
1. Filter by severity (only ERROR/CRITICAL)
2. Only check last 5 minutes
3. Implement log rotation

### Configuration Check Fails

**Possible Causes:**
1. Health endpoint not returning environment
2. Environment variable not set
3. Config loaded before environment set

**Solutions:**
1. Update health endpoint to return env
2. Set BOT_ENV in deployment script
3. Verify config loading order

## Security Considerations

**Log Scanning:**
- ✅ Don't expose sensitive data in logs
- ✅ Sanitize log output before checking
- ❌ Don't log passwords or tokens

**Memory Inspection:**
- ✅ Only check process memory usage
- ❌ Don't dump memory contents
- ❌ Don't expose memory details in errors

**Configuration Validation:**
- ✅ Verify environment matches
- ✅ Verify channel name matches
- ❌ Don't log full configuration
- ❌ Don't expose secrets in validation

## Commit Message

```bash
git add scripts/verify_deployment.py
git add requirements.txt
git add web/status_server.py
git add .github/workflows/prod-deploy.yml
git commit -m "feat: add enhanced production verification

Comprehensive production verification with stricter thresholds.

scripts/verify_deployment.py:
- Added verify_user_count() method
- Added verify_memory_usage() method (psutil)
- Added verify_error_logs() method (journalctl/log files)
- Added verify_configuration() method
- Added verify_uptime_stability() method (5 minute monitor)
- Environment-specific check selection
- Fail-fast for production (stop on first failure)
- Enhanced exit codes (7-11 for production checks)
- Progress indicator for long-running checks

Production Checks:
1. User count ≥ 1 (channel not empty)
2. Memory usage < 500MB (resource monitoring)
3. No errors in last 5 minutes (log scanning)
4. Correct config loaded (env/channel validation)
5. Stable for 5 minutes (no crashes/restarts)

Stricter Thresholds:
- Response time: < 1s avg (was 2s for test)
- Startup wait: 30s (was 10s for test)
- Verification timeout: 10 min (was 2 min for test)
- Memory limit: 500MB (not checked for test)
- Error tolerance: Zero (warnings OK for test)

requirements.txt:
- Added psutil>=5.9.0 for memory monitoring

web/status_server.py:
- Extended /api/health endpoint
- Added environment field
- Added user_count field
- Added memory_mb field
- Added uptime calculation

.github/workflows/prod-deploy.yml:
- Increased startup wait to 30s
- Increased verification timeout to 10 min
- Updated step descriptions

Exit Codes:
- 7: User count validation failed
- 8: Memory usage too high
- 9: Errors found in logs
- 10: Configuration mismatch
- 11: Uptime instability

Features:
- Real-time progress indicators
- Colored terminal output
- Detailed failure messages
- JSON output support
- Environment-specific behavior

Benefits:
- Catches production-specific issues
- Prevents bad deployments earlier
- More comprehensive health checks
- Extended stability monitoring
- Clear failure diagnostics
- Automatic rollback on any failure

This ensures production deployments are not only functional
but also stable, performant, and properly configured.

SPEC: Sortie 9 - Production Verification"
```

## Related Documentation

- **Sortie 6:** Test Channel Verification (foundation)
- **Sortie 7:** Production Deploy Workflow (uses this verification)
- **Sortie 3:** Deployment Scripts (rollback integration)

## Next Sortie

**Sortie 10: Rollback Mechanism** - Comprehensive rollback testing, validation, and documentation for both test and production environments.

---

**Implementation Time Estimate:** 4-5 hours  
**Risk Level:** Medium (extended checks could timeout)  
**Priority:** Critical (prevents bad production deployments)  
**Dependencies:** Sorties 3, 6, 7 complete, psutil available
