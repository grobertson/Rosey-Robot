# SPEC: Sorties 4-12 Summary

**Sprint:** 5 (ship-it)  
**Status:** Specifications Ready  

---

## Remaining Sorties Overview

### Sortie 4: Test Deploy Workflow
- Create `.github/workflows/test-deploy.yml`
- Trigger on PR open/update
- Run lint + test workflows first
- Deploy to test channel on success
- Post deployment status to PR

### Sortie 5: PR Status Integration  
- Add GitHub Actions bot comments to PRs
- Include test channel URL
- Link to workflow logs
- Show deployment timestamp
- Success/failure indicators

### Sortie 6: Test Channel Verification
- Add post-deployment health check
- Verify bot connection to CyTube
- Test basic command functionality
- Fail deployment if unhealthy
- Alert on failure

### Sortie 7: Production Deploy Workflow
- Create `.github/workflows/prod-deploy.yml`
- Trigger on push to main
- Run full CI pipeline
- Deploy to production channel
- Post deployment status

### Sortie 8: Release Automation
- Auto-create git tags (semantic versioning)
- Generate release notes from commits
- Create GitHub release
- Attach build artifacts
- Version bump automation

### Sortie 9: Production Verification
- Add smoke tests after prod deployment
- Verify critical functionality
- Alert on failure
- Slack/Discord notification (optional)

### Sortie 10: Rollback Mechanism
- Auto-rollback on deployment failure
- Manual rollback workflow trigger
- Preserve last N deployments
- Rollback notification

### Sortie 11: Deployment Dashboard
- Add workflow status badges to README
- Document deployment process
- Create troubleshooting guide
- Deployment history tracking

### Sortie 12: Monitoring Integration
- Log deployment events to database
- Track deployment metrics
- Expose deployment status via web UI
- Add deployment history endpoint

---

## Implementation Order

All sorties build on previous work:
1. Foundation (Sorties 1-3): CI + Config + Scripts
2. Test Channel (Sorties 4-6): Automated test deployment
3. Production (Sorties 7-9): Automated prod deployment
4. Safety (Sorties 10-12): Rollback + monitoring

## Total Estimate

- **Time:** 2-3 weeks
- **Complexity:** Medium-High
- **Risk:** Medium (deployment automation)

---

**Next:** Implement Sortie 4 (Test Deploy Workflow)
