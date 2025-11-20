# SPEC: Sortie 4 - Test Deploy Workflow

**Sprint:** 5 (ship-it)  
**Sortie:** 4 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 3 (Deployment Scripts)

---

## Objective

Create GitHub Actions workflow to automatically deploy to test channel when pull requests are opened or updated. This enables stakeholders to preview changes before production merge.

## Success Criteria

- ✅ `.github/workflows/test-deploy.yml` created
- ✅ Workflow triggers on PR events (opened, synchronize, reopened)
- ✅ Deployment only runs if lint and test workflows pass
- ✅ Bot deploys to test channel successfully
- ✅ Deployment status visible in GitHub Actions
- ✅ Workflow runs in < 8 minutes total

## Technical Specification

### Workflow Triggers

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [main]
```

**Events:**
- `opened`: When PR is first created
- `synchronize`: When new commits are pushed to PR
- `reopened`: When closed PR is reopened

### Workflow Dependencies

Test deployment should only run after quality gates pass:

```yaml
needs: [lint, test]
```

This ensures:
1. Code passes linting (ruff, mypy)
2. All tests pass (567 tests, 85%+ coverage)
3. Only then attempt deployment

### Deployment Environment

**Runner:** `ubuntu-latest`  
**Python:** 3.11  
**Secrets Required:**
- `CYTUBEBOT_TEST_PASSWORD`: Test channel bot password

### Workflow Jobs

#### Job 1: Lint (from Sortie 1)
- Run ruff linting
- Run mypy type checking
- Fast feedback (< 2 min)

#### Job 2: Test (from Sortie 1)
- Run full test suite
- Generate coverage report
- Enforce coverage minimum (< 3 min)

#### Job 3: Deploy to Test
- Wait for lint + test to pass
- Checkout code
- Setup Python environment
- Install dependencies
- Export secrets to environment
- Run deployment script
- Capture deployment output
- Report success/failure

### Deployment Steps

1. **Setup environment:**
   ```yaml
   - name: Set up Python 3.11
     uses: actions/setup-python@v4
     with:
       python-version: '3.11'
       cache: 'pip'
   ```

2. **Install dependencies:**
   ```yaml
   - name: Install dependencies
     run: |
       python -m pip install --upgrade pip
       pip install -r requirements.txt
   ```

3. **Configure secrets:**
   ```yaml
   - name: Configure test environment
     env:
       CYTUBEBOT_TEST_PASSWORD: ${{ secrets.CYTUBEBOT_TEST_PASSWORD }}
     run: |
       echo "CYTUBEBOT_TEST_PASSWORD=$CYTUBEBOT_TEST_PASSWORD" >> $GITHUB_ENV
   ```

4. **Run deployment:**
   ```yaml
   - name: Deploy to test channel
     run: |
       chmod +x scripts/deploy.sh
       ./scripts/deploy.sh test
   ```

5. **Handle failures:**
   ```yaml
   - name: Deployment failed
     if: failure()
     run: |
       echo "::error::Test deployment failed. Check logs for details."
       exit 1
   ```

## Implementation

### .github/workflows/test-deploy.yml

```yaml
name: Test Deployment

on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [main]

jobs:
  lint:
    name: Lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Lint with ruff
        run: ruff check .
      
      - name: Type check with mypy
        run: mypy lib/ common/ bots/ --ignore-missing-imports

  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run tests with coverage
        run: |
          pytest --cov --cov-report=term --cov-report=xml --cov-fail-under=66
      
      - name: Upload coverage report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: coverage-report
          path: coverage.xml

  deploy-test:
    name: Deploy to Test Channel
    needs: [lint, test]
    runs-on: ubuntu-latest
    environment:
      name: test
      url: https://cytu.be/r/test-rosey
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Configure test environment
        env:
          CYTUBEBOT_TEST_PASSWORD: ${{ secrets.CYTUBEBOT_TEST_PASSWORD }}
        run: |
          echo "CYTUBEBOT_TEST_PASSWORD=$CYTUBEBOT_TEST_PASSWORD" >> $GITHUB_ENV
      
      - name: Make deployment scripts executable
        run: chmod +x scripts/*.sh scripts/*.py
      
      - name: Deploy to test channel
        id: deploy
        run: |
          echo "Starting deployment to test channel..."
          ./scripts/deploy.sh test
          echo "deployment_time=$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> $GITHUB_OUTPUT
      
      - name: Deployment succeeded
        if: success()
        run: |
          echo "✅ Test deployment successful!"
          echo "Bot is now running on test channel: https://cytu.be/r/test-rosey"
      
      - name: Deployment failed
        if: failure()
        run: |
          echo "::error::❌ Test deployment failed. Check logs above for details."
          echo "The deployment script encountered an error."
          echo "Common issues:"
          echo "  - Health check failed (bot not responding)"
          echo "  - Configuration error"
          echo "  - Database initialization failed"
          exit 1
```

## Implementation Steps

### Step 1: Create Workflow File

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/test-deploy.yml` with the content above.

### Step 2: Configure GitHub Secrets

In GitHub repository settings:

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add secret:
   - Name: `CYTUBEBOT_TEST_PASSWORD`
   - Value: [actual test bot password]
4. Click **Add secret**

### Step 3: Configure GitHub Environment (Optional)

For enhanced security and environment-specific settings:

1. Go to **Settings** → **Environments**
2. Click **New environment**
3. Name: `test`
4. Configure environment (optional):
   - Add environment-specific secrets
   - Add protection rules (if desired)
   - Set environment URL: `https://cytu.be/r/test-rosey`

### Step 4: Test Workflow

1. Create a test branch:
   ```bash
   git checkout -b test-workflow
   ```

2. Make a small change (e.g., update README)
   ```bash
   echo "# Test change" >> README.md
   git add README.md
   git commit -m "test: verify test deployment workflow"
   ```

3. Push and create PR:
   ```bash
   git push -u origin test-workflow
   # Create PR via GitHub UI or gh CLI
   ```

4. Verify workflow:
   - Check Actions tab in GitHub
   - Verify lint job runs and passes
   - Verify test job runs and passes
   - Verify deploy-test job runs and passes
   - Check deployment output in logs

### Step 5: Verify Deployment

1. Check workflow logs for deployment output
2. Visit test channel: `https://cytu.be/r/test-rosey`
3. Verify bot is connected and responsive
4. Test a simple command

### Step 6: Handle Failures

If deployment fails:

1. **Check workflow logs:**
   - Navigate to Actions tab
   - Click on failed workflow run
   - Expand deploy-test job
   - Review error messages

2. **Common issues:**
   - **Secret not set:** Configure `CYTUBEBOT_TEST_PASSWORD` in GitHub
   - **Health check failed:** Check test channel permissions
   - **Script not executable:** Verify `chmod +x` step runs
   - **Configuration error:** Verify `config-test.json` valid

3. **Fix and retry:**
   - Fix the issue
   - Push new commit to PR
   - Workflow will automatically re-run

### Step 7: Commit Workflow

```bash
git add .github/workflows/test-deploy.yml
git commit -m "ci: add test deployment workflow

Created automated deployment workflow for test channel.

.github/workflows/test-deploy.yml:
- Trigger on PR opened/updated
- Depends on lint and test jobs passing
- Deploy to test channel using deploy.sh script
- Export CYTUBEBOT_TEST_PASSWORD secret
- Run health check after deployment
- Report success/failure with clear messages

Workflow structure:
- Job 1: Lint (ruff + mypy)
- Job 2: Test (pytest + coverage)
- Job 3: Deploy to test channel (if jobs 1-2 pass)

Environment:
- Ubuntu latest runner
- Python 3.11
- Test channel: https://cytu.be/r/test-rosey
- Secrets: CYTUBEBOT_TEST_PASSWORD

Features:
- Only deploys if quality gates pass
- Clear success/failure messages
- Deployment time tracking
- Environment URL for easy access

This enables automatic test deployments on every PR,
allowing stakeholders to preview changes before production.

SPEC: Sortie 4 - Test Deploy Workflow"
```

## Validation Checklist

- [ ] `.github/workflows/test-deploy.yml` created
- [ ] Workflow triggers on PR events
- [ ] Lint job included and passes
- [ ] Test job included and passes
- [ ] Deploy job depends on lint + test
- [ ] `CYTUBEBOT_TEST_PASSWORD` secret configured
- [ ] Deployment script runs successfully
- [ ] Health check passes after deployment
- [ ] Bot connects to test channel
- [ ] Workflow completes in < 8 minutes
- [ ] Failure messages are clear
- [ ] Deployment time is tracked

## Testing Strategy

### Test 1: Successful Deployment

1. Create PR with clean changes
2. Verify lint passes
3. Verify tests pass
4. Verify deployment succeeds
5. Check bot on test channel

**Expected:** All jobs green, bot connected

### Test 2: Lint Failure Blocks Deployment

1. Create PR with linting errors
2. Verify lint job fails
3. Verify deploy job doesn't run

**Expected:** Lint fails, deployment skipped

### Test 3: Test Failure Blocks Deployment

1. Create PR with failing test
2. Verify lint passes
3. Verify test job fails
4. Verify deploy job doesn't run

**Expected:** Test fails, deployment skipped

### Test 4: Deployment Failure

1. Create PR with invalid configuration
2. Verify lint and test pass
3. Verify deployment fails
4. Check error messages are clear

**Expected:** Deployment fails with helpful error

### Test 5: Subsequent PR Updates

1. Create PR
2. Wait for deployment
3. Push new commit to same PR
4. Verify workflow re-runs automatically

**Expected:** New deployment on update

## Performance Targets

| Job | Target Time | Max Time |
|-----|-------------|----------|
| Lint | < 2 minutes | 3 minutes |
| Test | < 3 minutes | 5 minutes |
| Deploy | < 3 minutes | 5 minutes |
| **Total** | **< 8 minutes** | **13 minutes** |

## Deployment Notes

### Local vs GitHub Actions

**Differences:**
- GitHub Actions: Fresh ubuntu environment each run
- Local: May have cached dependencies, running processes

**Implications:**
- Deployment script must handle fresh environment
- No assumptions about pre-existing state
- All dependencies must be installed

### Secrets Security

**Best Practices:**
- ✅ Store passwords in GitHub Secrets
- ✅ Never log secret values
- ✅ Use environment variables for secrets
- ❌ Don't commit secrets to repository
- ❌ Don't echo secrets in workflow output

### Concurrent Deployments

**Behavior:**
- GitHub Actions queues workflows automatically
- Multiple PRs will deploy sequentially, not parallel
- Each PR gets its own workflow run

**Future Enhancement:**
- Could add concurrency control to prevent simultaneous test deployments
- Not critical for MVP (test channel can handle multiple connections)

## Rollback Plan

If workflow causes issues:

1. **Disable workflow:**
   - Rename file: `test-deploy.yml.disabled`
   - Or delete the file temporarily

2. **Fix issues:**
   - Review workflow logs
   - Fix configuration/scripts
   - Test locally if possible

3. **Re-enable:**
   - Restore filename
   - Create test PR to verify
   - Monitor first few runs closely

## Success Metrics

- ✅ Workflow passes on first PR
- ✅ All jobs complete successfully
- ✅ Deployment time < 8 minutes
- ✅ Bot connects to test channel
- ✅ Clear error messages on failure
- ✅ Stakeholders can preview changes

## Troubleshooting

### "Secret not found" Error

**Problem:** `CYTUBEBOT_TEST_PASSWORD` not configured

**Solution:**
1. Go to Settings → Secrets and variables → Actions
2. Add `CYTUBEBOT_TEST_PASSWORD` secret
3. Re-run workflow

### Deployment Script Fails

**Problem:** `deploy.sh` exits with non-zero code

**Solution:**
1. Check workflow logs for error message
2. Review `scripts/deploy.sh` logic
3. Verify test configuration valid
4. Check health_check.py works

### Health Check Fails

**Problem:** Bot doesn't respond to health check

**Solution:**
1. Verify test channel exists and accessible
2. Check bot has correct permissions
3. Verify database can be created
4. Review bot logs if available

### Workflow Doesn't Trigger

**Problem:** No workflow runs on PR

**Solution:**
1. Verify workflow file in `.github/workflows/`
2. Check workflow triggers match PR type
3. Verify targeting `main` branch
4. Check workflow file syntax (YAML valid)

## Future Enhancements

### Phase 2 (Sortie 5):
- Add PR comment with deployment status
- Include test channel URL in comment
- Link to workflow logs

### Phase 3 (Sortie 6):
- Add verification step after deployment
- Test basic bot commands
- Report detailed health status

## Related Documentation

- **Sortie 1:** GitHub Actions Setup (lint, test workflows)
- **Sortie 2:** Configuration Management (config-test.json)
- **Sortie 3:** Deployment Scripts (deploy.sh, health_check.py)
- **GitHub Actions Docs:** https://docs.github.com/en/actions

## Next Sortie

**Sortie 5: PR Status Integration** - Add bot comments to PRs with deployment status, test channel URL, and workflow logs link.

---

**Implementation Time Estimate:** 2-3 hours  
**Risk Level:** Medium  
**Priority:** High (enables test channel preview)  
**Dependencies:** Sorties 1-3 complete
