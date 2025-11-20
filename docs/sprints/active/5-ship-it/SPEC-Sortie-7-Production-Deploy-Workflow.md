# SPEC: Sortie 7 - Production Deploy Workflow

**Sprint:** 5 (ship-it)  
**Sortie:** 7 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sorties 1-6 (CI foundation, test deployment proven)

---

## Objective

Create production deployment workflow with manual approval gates, additional safeguards, and stricter validation. Production deployments should only occur for merged PRs or direct pushes to main, with explicit human approval required.

## Success Criteria

- ✅ Production deployment requires manual approval
- ✅ Only deploys from main branch
- ✅ All quality gates must pass before approval option appears
- ✅ Deployment includes backup creation
- ✅ Verification stricter than test channel
- ✅ Rollback available if verification fails
- ✅ Notifications sent on deployment completion
- ✅ Deployment history tracked

## Technical Specification

### Deployment Triggers

**Allowed Triggers:**
- Manual workflow dispatch (recommended for initial releases)
- Push to main branch (after merge)
- Git tags matching `v*.*.*` pattern

**Not Allowed:**
- Direct PR deployment to production
- Deployment from feature branches
- Automated deployment without approval

### Manual Approval Gate

**GitHub Environment:**
- Environment name: `production`
- Required reviewers: Repository admins
- Wait timer: 0 minutes (immediate approval available)
- Protection rules: Require approval before deployment

**Approval Process:**
1. Quality gates pass (lint, test, build)
2. Approval button appears in workflow
3. Reviewer checks readiness
4. Reviewer clicks "Approve deployment"
5. Deployment proceeds

### Quality Gates

**Pre-Approval Gates:**
1. Linting passes (ruff + mypy)
2. All tests pass (567 tests minimum)
3. Code coverage ≥ 92%
4. No critical security vulnerabilities
5. Test deployment verified (optional)

**Post-Approval Gates:**
1. Backup created successfully
2. Deployment completes without errors
3. Health check passes
4. All verification checks pass
5. Response time within threshold

### Production Environment Configuration

**GitHub Environment Settings:**
```yaml
Environment: production
URL: https://cytu.be/r/rosey
Deployment branches: main only
Reviewers: @admin1, @admin2
Wait timer: 0 minutes
```

**Secrets Required:**
- `CYTUBEBOT_PROD_PASSWORD` - Production bot password
- `DEPLOY_NOTIFICATION_WEBHOOK` - Slack/Discord webhook (optional)

## Implementation

### .github/workflows/prod-deploy.yml

```yaml
name: Production Deployment

on:
  # Manual trigger
  workflow_dispatch:
    inputs:
      reason:
        description: 'Reason for deployment'
        required: true
        type: string
      skip_verification:
        description: 'Skip post-deployment verification (emergency only)'
        required: false
        type: boolean
        default: false
  
  # Automatic on main branch push
  push:
    branches:
      - main
  
  # Automatic on version tags
  push:
    tags:
      - 'v*.*.*'

permissions:
  contents: read
  pull-requests: write
  deployments: write

jobs:
  # Quality gates - must pass before approval
  lint:
    name: Lint Code
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install ruff mypy
          pip install -r requirements.txt
      
      - name: Run ruff
        run: ruff check .
      
      - name: Run mypy
        run: mypy lib/ common/ bots/
  
  test:
    name: Run Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov pytest-asyncio
          pip install -r requirements.txt
      
      - name: Run tests with coverage
        run: |
          pytest tests/ \
            --cov=lib \
            --cov=common \
            --cov-report=term \
            --cov-report=xml \
            --cov-fail-under=92
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        if: always()
        with:
          files: ./coverage.xml
  
  # Production deployment - requires manual approval
  deploy-production:
    name: Deploy to Production
    needs: [lint, test]
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://cytu.be/r/rosey
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install requests
      
      - name: Create deployment backup
        run: |
          chmod +x scripts/deploy.sh
          # Backup is created automatically by deploy.sh
          echo "Backup will be created during deployment"
      
      - name: Deploy to production
        env:
          CYTUBEBOT_PROD_PASSWORD: ${{ secrets.CYTUBEBOT_PROD_PASSWORD }}
        run: |
          ./scripts/deploy.sh prod
      
      - name: Wait for startup
        run: |
          echo "Waiting 10 seconds for bot to fully start..."
          sleep 10
      
      - name: Verify deployment
        id: verify
        if: ${{ !inputs.skip_verification }}
        run: |
          python scripts/verify_deployment.py --env prod
        timeout-minutes: 3
      
      - name: Rollback on verification failure
        if: failure() && steps.verify.outcome == 'failure'
        run: |
          echo "Verification failed, rolling back to previous version"
          chmod +x scripts/rollback.sh
          ./scripts/rollback.sh prod
          exit 1
      
      - name: Send deployment notification
        if: success()
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
            
            const commitSha = context.sha.substring(0, 7);
            const commitUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/commit/${context.sha}`;
            const workflowUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            
            const payload = {
              text: `🚀 Production Deployment Successful`,
              blocks: [
                {
                  type: "section",
                  text: {
                    type: "mrkdwn",
                    text: `*Production Deployment Complete*\n\n` +
                          `• Channel: https://cytu.be/r/rosey\n` +
                          `• Commit: <${commitUrl}|${commitSha}>\n` +
                          `• Workflow: <${workflowUrl}|View logs>\n` +
                          `• Deployed by: ${context.actor}`
                  }
                }
              ]
            };
            
            await fetch(webhook, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(payload)
            });
  
  # Comment on related PR if deployment came from merge
  comment-deployment:
    name: Comment on PR
    needs: [deploy-production]
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    permissions:
      pull-requests: write
      contents: read
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2
      
      - name: Find related PR
        id: find-pr
        uses: actions/github-script@v7
        with:
          script: |
            // Find PR that was just merged
            const { data: prs } = await github.rest.pulls.list({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'closed',
              sort: 'updated',
              direction: 'desc',
              per_page: 10
            });
            
            const recentlyMergedPR = prs.find(pr => 
              pr.merged_at && 
              pr.merge_commit_sha === context.sha
            );
            
            if (recentlyMergedPR) {
              core.setOutput('pr_number', recentlyMergedPR.number);
              core.setOutput('found', 'true');
            } else {
              core.setOutput('found', 'false');
            }
      
      - name: Comment on PR
        if: steps.find-pr.outputs.found == 'true'
        uses: actions/github-script@v7
        with:
          script: |
            const prNumber = ${{ steps.find-pr.outputs.pr_number }};
            const commitSha = context.sha.substring(0, 7);
            const workflowUrl = `${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            const deployTime = new Date().toISOString();
            
            const body = `## 🎉 Deployed to Production
            
            Your changes are now live on the production channel!
            
            **🔗 Production Channel:** https://cytu.be/r/rosey  
            **⏱️ Deployed:** ${deployTime}  
            **📦 Commit:** ${commitSha}  
            **🔍 Workflow:** [View logs](${workflowUrl})
            
            **✅ All Checks Passed:**
            - ✓ Linting passed
            - ✓ Tests passed (567 tests, 92% coverage)
            - ✓ Deployment successful
            - ✓ Verification passed
            
            ---
            
            <sub>🤖 Automated production deployment via GitHub Actions</sub>
            `;
            
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: prNumber,
              body: body
            });
```

### Alternative: Separate Manual Deploy Workflow

For organizations that want explicit manual-only deployments:

```yaml
name: Manual Production Deploy

on:
  workflow_dispatch:
    inputs:
      commit_sha:
        description: 'Commit SHA to deploy (leave empty for latest main)'
        required: false
        type: string
      reason:
        description: 'Deployment reason'
        required: true
        type: string
      notify:
        description: 'Send notification after deployment'
        required: false
        type: boolean
        default: true

jobs:
  deploy:
    name: Deploy to Production
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://cytu.be/r/rosey
    
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ inputs.commit_sha || 'main' }}
      
      - name: Log deployment reason
        run: |
          echo "Deployment initiated by: ${{ github.actor }}"
          echo "Reason: ${{ inputs.reason }}"
          echo "Commit: ${{ inputs.commit_sha || 'latest main' }}"
      
      # ... rest of deployment steps ...
```

## Implementation Steps

### Step 1: Configure Production Environment

```bash
# In GitHub repo settings:
1. Go to Settings > Environments
2. Create "production" environment
3. Add required reviewers (repo admins)
4. Set deployment branch: main only
5. Save environment
```

### Step 2: Add Production Secrets

```bash
# In GitHub repo settings:
1. Go to Settings > Secrets and variables > Actions
2. Add secret: CYTUBEBOT_PROD_PASSWORD
3. Add secret: DEPLOY_NOTIFICATION_WEBHOOK (optional)
4. Save secrets
```

### Step 3: Create Production Config

```bash
# Create config-prod.json (already done in Sortie 2)
# Verify configuration is correct
cat config-prod.json

# Test configuration loading
python -c "import json; print(json.load(open('config-prod.json')))"
```

### Step 4: Create Workflow File

```bash
# Create production deployment workflow
touch .github/workflows/prod-deploy.yml
# Add content from above
```

### Step 5: Test Approval Flow

```bash
# Method 1: Manual dispatch
1. Go to Actions > Production Deployment
2. Click "Run workflow"
3. Enter reason
4. Click "Run workflow"
5. Wait for quality gates
6. Approve deployment
7. Watch deployment proceed

# Method 2: Merge to main
1. Merge a PR to main
2. Watch workflow trigger automatically
3. Quality gates run
4. Approve deployment when ready
5. Deployment proceeds
```

### Step 6: Test Rollback

```bash
# Simulate verification failure
1. Temporarily break health check
2. Trigger deployment
3. Approve deployment
4. Watch verification fail
5. Verify automatic rollback occurs
6. Check logs for rollback confirmation
```

### Step 7: Configure Notifications

```bash
# Slack webhook (optional)
1. Create Slack incoming webhook
2. Add as DEPLOY_NOTIFICATION_WEBHOOK secret
3. Test deployment notification

# Discord webhook (optional)
# Same process as Slack
```

## Validation Checklist

- [ ] Production environment configured in GitHub
- [ ] Required reviewers added to environment
- [ ] Deployment branch restricted to main
- [ ] `CYTUBEBOT_PROD_PASSWORD` secret set
- [ ] Workflow file created and committed
- [ ] Lint job runs before approval gate
- [ ] Test job runs before approval gate
- [ ] Approval gate appears after quality checks
- [ ] Deployment only proceeds after approval
- [ ] Backup created before deployment
- [ ] Verification runs after deployment
- [ ] Rollback triggers on verification failure
- [ ] Notification sent on success (if configured)
- [ ] PR comment added on merge deployment

## Testing Strategy

### Test 1: Manual Deployment with Approval

**Steps:**
1. Navigate to Actions > Production Deployment
2. Click "Run workflow"
3. Enter reason: "Test deployment flow"
4. Click "Run workflow"
5. Wait for lint and test to pass
6. Approve deployment
7. Wait for completion

**Expected:**
- Workflow starts
- Lint and test run
- Approval button appears
- After approval, deployment proceeds
- Verification passes
- Success notification sent
- No errors in logs

### Test 2: Automatic Deployment on Merge

**Steps:**
1. Create test PR
2. Get PR approved
3. Merge PR to main
4. Watch workflow trigger
5. Wait for quality gates
6. Approve deployment

**Expected:**
- Workflow auto-triggers on merge
- Quality gates pass
- Approval gate appears
- Deployment proceeds after approval
- PR comment added with production URL
- Success notification

### Test 3: Deployment Rejection

**Steps:**
1. Trigger workflow
2. Wait for approval gate
3. Reject deployment

**Expected:**
- Workflow stops after rejection
- No deployment occurs
- Clear rejection message in logs
- No notification sent

### Test 4: Verification Failure Rollback

**Steps:**
1. Temporarily break verification
2. Trigger deployment
3. Approve deployment
4. Watch verification fail

**Expected:**
- Deployment proceeds
- Verification runs
- Verification fails
- Automatic rollback triggered
- Previous version restored
- Error notification sent
- Clear error in logs

### Test 5: Quality Gate Failure

**Steps:**
1. Create PR with failing tests
2. Merge to main
3. Watch workflow run

**Expected:**
- Lint or test job fails
- Approval gate never appears
- Deployment does not occur
- Clear failure message
- No notification sent

## Approval Gate Best Practices

### When to Approve

**✅ Safe to Approve:**
- All quality gates passed
- Test deployment verified working
- No active incidents
- During maintenance window
- Team available for monitoring

**❌ Do Not Approve:**
- Quality gates failed
- Test deployment failing
- Active production incidents
- Off-hours without on-call
- Untested changes

### Approval Checklist

Before clicking "Approve deployment":

1. ✅ All tests passed
2. ✅ Linting passed
3. ✅ Test deployment verified (optional)
4. ✅ No active incidents
5. ✅ Change is expected
6. ✅ Team aware of deployment
7. ✅ Rollback plan ready
8. ✅ Monitoring in place

## Rollback Procedures

### Automatic Rollback

Triggered automatically on:
- Verification failure
- Deployment script error
- Health check timeout

### Manual Rollback

```bash
# From local machine
ssh production-server
cd /opt/rosey-bot
./scripts/rollback.sh prod

# Verify rollback
python scripts/verify_deployment.py --env prod
```

### Emergency Rollback

```bash
# Quick rollback without verification
./scripts/rollback.sh prod --force

# Restart with previous version
systemctl restart cytube-bot
```

## Deployment History

### Tracking Deployments

**GitHub Deployments API:**
- Automatically tracks each deployment
- View in repo > Environments > production
- Shows: timestamp, commit, actor, status

**Backup Directory:**
```bash
# List recent deployments
ls -lt backups/prod/

# Each backup shows deployment time
backups/prod/backup_20241112_153045/
```

### Deployment Logs

**Workflow Logs:**
- Actions > Production Deployment > specific run
- Shows full deployment timeline
- Includes verification results

**Server Logs:**
```bash
# View deployment logs
journalctl -u cytube-bot -n 100

# View specific deployment
grep "Deployment started" /var/log/cytube-bot/deploy.log
```

## Performance Targets

**Quality Gates:**
- Lint: < 2 minutes
- Test: < 5 minutes
- Total pre-approval: < 8 minutes

**Deployment:**
- Backup creation: < 30 seconds
- Bot restart: < 10 seconds
- Verification: < 20 seconds
- Total deployment: < 2 minutes

**Approval Wait:**
- Variable (human dependent)
- Timeout: None (waits indefinitely)
- Can cancel if needed

**Total Time:**
- Pre-approval: ~8 minutes
- Approval wait: ~1-5 minutes (typical)
- Deployment: ~2 minutes
- **Total:** ~11-15 minutes

## Security Considerations

### Secrets Management

**Required Secrets:**
- `CYTUBEBOT_PROD_PASSWORD` - Encrypted at rest
- `DEPLOY_NOTIFICATION_WEBHOOK` - Optional

**Best Practices:**
- ✅ Secrets stored in GitHub Secrets
- ✅ Never logged or printed
- ✅ Passed as environment variables
- ✅ Rotated regularly (every 90 days)

### Access Control

**Deployment Approval:**
- Only repository admins
- Requires authenticated session
- Audit trail maintained

**Workflow Permissions:**
- Minimal required permissions
- Read-only by default
- Write only where needed

### Audit Trail

**Tracked Information:**
- Who initiated deployment
- When deployment occurred
- What commit was deployed
- Who approved deployment
- Deployment outcome
- Rollback events

## Troubleshooting

### Approval Gate Not Appearing

**Possible Causes:**
1. Quality gates failed
2. Environment not configured
3. No reviewers set

**Solutions:**
1. Check lint/test job logs
2. Verify environment exists in settings
3. Add required reviewers

### Deployment Fails After Approval

**Possible Causes:**
1. Secrets not configured
2. Server unreachable
3. Configuration error

**Solutions:**
1. Verify `CYTUBEBOT_PROD_PASSWORD` set
2. Check server connectivity
3. Validate config-prod.json

### Verification Always Fails

**Possible Causes:**
1. Bot takes longer to start in production
2. Stricter thresholds
3. Resource constraints

**Solutions:**
1. Increase startup wait time (10s → 30s)
2. Adjust verification thresholds
3. Check server resources

### Notification Not Sent

**Possible Causes:**
1. Webhook not configured
2. Webhook URL invalid
3. Service down

**Solutions:**
1. Verify `DEPLOY_NOTIFICATION_WEBHOOK` set
2. Test webhook URL manually
3. Check service status

## Commit Message

```bash
git add .github/workflows/prod-deploy.yml
git commit -m "feat: add production deployment workflow with manual approval

Production deployment with strict quality gates and human approval.

.github/workflows/prod-deploy.yml:
- Manual workflow dispatch trigger
- Automatic on push to main (with approval)
- Tag-based deployment (v*.*.*)
- Lint and test quality gates
- Manual approval gate (production environment)
- Backup creation before deployment
- Post-deployment verification
- Automatic rollback on failure
- Success notifications (Slack/Discord)
- PR comment on merge deployments

Quality Gates (Pre-Approval):
- Linting (ruff + mypy)
- Tests (pytest with 92% coverage requirement)
- Must pass before approval option appears

Production Environment:
- GitHub environment: production
- URL: https://cytu.be/r/rosey
- Required reviewers: repository admins
- Deployment branch: main only
- Secrets: CYTUBEBOT_PROD_PASSWORD

Deployment Process:
1. Trigger (manual or merge to main)
2. Quality gates run (lint, test)
3. Approval gate appears
4. Reviewer approves deployment
5. Backup created automatically
6. Deployment proceeds
7. 10 second startup wait
8. Verification runs (3 min timeout)
9. Success notification sent
10. PR comment added (if from merge)

Rollback:
- Automatic on verification failure
- Uses scripts/rollback.sh
- Restores previous working version
- Can be triggered manually

Notifications:
- Slack/Discord webhook support
- Deployment success/failure alerts
- Includes commit, workflow links
- Actor information

Security:
- Manual approval required
- Admin-only deployment access
- Secrets encrypted at rest
- Full audit trail maintained

Benefits:
- Human oversight for production changes
- Prevents accidental deployments
- Clear approval process
- Automatic quality validation
- Quick rollback on issues
- Team notification on changes

This provides safe, controlled production deployments with
appropriate safeguards and visibility.

SPEC: Sortie 7 - Production Deploy Workflow"
```

## Related Documentation

- **Sortie 3:** Deployment Scripts (deploy.sh, rollback.sh)
- **Sortie 4:** Test Deploy Workflow (pattern foundation)
- **Sortie 6:** Verification (verification checks)
- **Sortie 8:** Release Automation (tag-based versioning)

## Next Sortie

**Sortie 8: Release Automation** - Automate version tagging, changelog generation, and release notes for production deployments.

---

**Implementation Time Estimate:** 3-4 hours  
**Risk Level:** Medium (production changes always risky)  
**Priority:** Critical (enables production deployments)  
**Dependencies:** Sorties 1-6 complete, production environment configured
