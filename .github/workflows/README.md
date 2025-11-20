# GitHub Actions Workflows

**Status**: ⏸️ Temporarily Disabled  
**Reason**: Cost optimization  
**Date Disabled**: November 20, 2025

## Current State

All GitHub Actions workflows have been disabled to save on GitHub Actions minutes/costs. The workflows are preserved in place and can be re-enabled when needed.

## Disabled Workflows

| Workflow | File | Original Trigger | Can Manually Run? |
|----------|------|------------------|-------------------|
| CI | `ci.yml` | Push to main/nano-sprint branches, PRs | ✅ Yes |
| PR Status Check | `pr-status.yml` | PR opened/updated | ✅ Yes |
| Release Automation | `release.yml` | VERSION file changes on main | ✅ Yes |
| Deploy to Test | `test-deploy.yml` | Push to main | ✅ Yes |
| Deploy to Production | `prod-deploy.yml` | Manual only (unchanged) | ✅ Yes |

## How They Were Disabled

Each workflow's automatic triggers were commented out and replaced with `workflow_dispatch:` only. This means:

- ❌ Workflows won't run automatically on push/PR/etc.
- ✅ Workflows can still be triggered manually if needed
- ✅ All workflow code is preserved unchanged
- ✅ Easy to re-enable by uncommenting the trigger sections

## To Re-enable Workflows

When you're ready to use GitHub Actions again:

1. Open each workflow file (`.yml`)
2. Find the commented section at the top:
   ```yaml
   # DISABLED: GitHub Actions temporarily disabled for cost reasons
   # Uncomment the 'on:' section below to re-enable
   # on:
   #   push:
   #     branches:
   #       - main
   ```
3. Uncomment the original `on:` section
4. Remove or comment out the `workflow_dispatch:` only trigger
5. Commit and push

## Manual Workflow Execution (If Needed)

You can still manually run any workflow:

1. Go to: **Actions** tab in GitHub
2. Select the workflow from the left sidebar
3. Click **Run workflow** button
4. Fill in any required inputs
5. Click **Run workflow**

This is useful for:
- Testing workflow changes
- One-off deployments
- Creating releases manually
- Running CI checks before merging

## Alternative Deployment Methods

While GitHub Actions is disabled, use these methods:

### Manual Deployment to Test

```bash
# SSH to test server
ssh rosey@TEST_SERVER_IP

# Pull latest code
cd /opt/rosey-bot
git pull origin main

# Install dependencies (if changed)
pip install -r requirements.txt

# Restart services
sudo systemctl restart rosey-bot
sudo systemctl restart rosey-dashboard

# Verify
sudo systemctl status rosey-bot
curl http://localhost:8001/api/health
```

### Manual Deployment to Production

```bash
# SSH to production server
ssh rosey@PROD_SERVER_IP

# Create backup first
sudo cp -r /opt/rosey-bot /opt/rosey-bot-backup-$(date +%Y%m%d-%H%M%S)

# Pull specific version
cd /opt/rosey-bot
git fetch --all --tags
git checkout v0.2.0  # or whatever version

# Install dependencies
pip install -r requirements.txt

# Restart services
sudo systemctl restart rosey-bot
sudo systemctl restart rosey-dashboard

# Verify
sudo systemctl status rosey-bot
curl http://localhost:8000/api/health
```

### Automated Deploy Script (Alternative)

You can create a local deploy script that uses SSH/rsync (same as GitHub Actions would):

```bash
# See: scripts/deploy.sh (if exists)
# Or: DEPLOYMENT_SETUP.md for manual steps
```

## Cost Considerations

GitHub Actions pricing (as of 2025):
- **Free tier**: 2,000 minutes/month for private repos
- **Cost**: ~$0.008/minute after free tier
- **Typical usage**: CI + deployments = ~100-300 minutes/month

Re-enable when:
- Have budget for Actions minutes
- Switch to public repo (unlimited free minutes)
- Only use for critical deployments (manual trigger only)
- Use self-hosted runners (free compute)

## See Also

- [DEPLOYMENT_SETUP.md](../../DEPLOYMENT_SETUP.md) - Manual deployment guide
- [Sprint 6 Docs](../../docs/sprints/active/6-make-it-real/) - Deployment automation specs
- [GitHub Actions Pricing](https://docs.github.com/en/billing/managing-billing-for-github-actions/about-billing-for-github-actions)

---

**Note**: These workflows were fully implemented and tested. They can be re-enabled at any time without modification.
