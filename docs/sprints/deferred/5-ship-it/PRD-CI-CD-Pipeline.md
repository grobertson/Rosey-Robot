# PRD: Sprint 5 - Ship It (CI/CD Pipeline)

**Status:** Draft  
**Sprint:** 5 (ship-it)  
**Created:** 2024-11-11  
**Owner:** Development Team  

---

## Problem Statement

Currently, deployments to test and production channels require manual intervention, creating friction and anxiety for stakeholders. There's no automated validation before deployment, no visibility into what's being deployed, and no clear rollback strategy. The deployment process is error-prone and lacks the confidence needed to "move quick and beg forgiveness."

**Current Pain Points:**
- Manual deployment steps (error-prone)
- No automated testing before deployment
- Stakeholder anxiety about what's live
- No visibility into deployment status
- Difficult to verify changes before production
- No rollback capability
- Configuration management is manual

**Impact:**
- Slows down development velocity
- Creates deployment anxiety
- Risk of downtime from manual errors
- Stakeholder concerns about change control
- Cannot confidently deploy frequently

---

## Goals

### Primary Objectives
1. **Automated CI/CD Pipeline** - GitHub Actions workflow for build, test, deploy
2. **Dual Deployment Targets** - Separate test and production channel deployments
3. **Stakeholder Visibility** - Test channel for validation before production
4. **Configuration Management** - Separate configs for test vs production
5. **Safety & Rollback** - Automated rollback on failure, manual rollback option

### Success Metrics
- ✅ Pull requests auto-deploy to test channel
- ✅ Merges to main auto-deploy to production channel
- ✅ All 600+ tests pass before any deployment
- ✅ Zero manual deployment steps
- ✅ Configuration separated and secure
- ✅ Deployment status visible in GitHub
- ✅ Rollback completes in < 2 minutes

### Non-Goals (Out of Scope)
- Multi-region deployments
- Blue-green deployment strategy
- Kubernetes/container orchestration
- Database migration automation (future sprint)
- Performance testing in pipeline
- Integration with external monitoring (future sprint)

---

## User Stories

### Stakeholder Stories
1. **As a stakeholder**, I want to see changes deployed to test channel automatically so I can review them before production
2. **As a stakeholder**, I want deployment status visible in GitHub so I know what's live
3. **As a stakeholder**, I want confidence that all tests pass before deployment so changes are validated

### Developer Stories
1. **As a developer**, I want my PR to auto-deploy to test channel so I can validate end-to-end behavior
2. **As a developer**, I want production deployment automated so I don't have manual steps
3. **As a developer**, I want clear deployment logs so I can debug failures
4. **As a developer**, I want rollback capability so I can quickly fix production issues
5. **As a developer**, I want configuration separated so test/prod don't interfere

---

## Technical Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     GitHub Repository                        │
│                                                              │
│  ┌────────────┐         ┌────────────┐                     │
│  │ Pull Request│         │   Merge    │                     │
│  │   Created   │         │  to Main   │                     │
│  └──────┬──────┘         └──────┬─────┘                     │
│         │                       │                            │
│         ▼                       ▼                            │
│  ┌──────────────────────────────────────┐                  │
│  │      GitHub Actions Workflow          │                  │
│  │                                        │                  │
│  │  1. Checkout Code                     │                  │
│  │  2. Setup Python 3.11                 │                  │
│  │  3. Install Dependencies              │                  │
│  │  4. Run Linters (ruff, mypy)          │                  │
│  │  5. Run Tests (pytest, 600+ tests)    │                  │
│  │  6. Coverage Report (85%+ required)   │                  │
│  │  7. Build Artifacts                   │                  │
│  │  8. Deploy                            │                  │
│  └───────────┬──────────────────┬────────┘                  │
│              │                  │                            │
└──────────────┼──────────────────┼────────────────────────────┘
               │                  │
               ▼                  ▼
      ┌────────────────┐  ┌────────────────┐
      │  Test Channel  │  │ Prod Channel   │
      │   CyTube       │  │    CyTube      │
      │  (PR Deploy)   │  │ (Merge Deploy) │
      └────────────────┘  └────────────────┘
```

### Workflow Details

#### PR Workflow (Test Deployment)
```yaml
Trigger: Pull Request opened/updated
Steps:
  1. Checkout PR branch
  2. Setup Python 3.11
  3. Install dependencies (requirements.txt)
  4. Lint: ruff check .
  5. Type check: mypy lib/ common/ bots/
  6. Test: pytest --cov --cov-report=term
  7. Coverage gate: Require 85%+ (66% minimum)
  8. Deploy to test channel:
     - Copy bot/rosey/ to deployment location
     - Use config-test.json (test channel credentials)
     - Restart bot service (systemd or direct)
     - Health check: Wait for connection
  9. Post deployment status to PR
  
Success: Comment on PR with deployment URL
Failure: Comment on PR with logs, block merge
```

#### Merge Workflow (Production Deployment)
```yaml
Trigger: Push to main branch (after merge)
Steps:
  1. Checkout main branch
  2. Setup Python 3.11
  3. Install dependencies
  4. Lint: ruff check .
  5. Type check: mypy lib/ common/ bots/
  6. Test: pytest --cov --cov-report=term
  7. Coverage gate: Require 85%+
  8. Create release tag (v*.*.*)
  9. Deploy to production channel:
     - Copy bot/rosey/ to deployment location
     - Use config-prod.json (prod channel credentials)
     - Restart bot service (systemd)
     - Health check: Wait for connection
     - Smoke test: Verify basic commands
  10. Post deployment status
  
Success: Create GitHub release, notify team
Failure: Auto-rollback, alert team
```

### Configuration Strategy

**Separate Configuration Files:**
- `bot/rosey/config-test.json` - Test channel configuration
- `bot/rosey/config-prod.json` - Production channel configuration
- `bot/rosey/config.json` - Symlink to active config (deployment switches)

**Secrets Management:**
- GitHub Secrets store sensitive values
- Environment variables in workflow
- No credentials in repository
- Secrets: CYTUBEBOT_TEST_PASSWORD, CYTUBEBOT_PROD_PASSWORD, DEPLOY_SSH_KEY

**Configuration Differences:**
```json
{
  "channel": "test-rosey" or "rosey",
  "bot_name": "RoseyTest" or "Rosey",
  "server": "cytu.be",
  "log_level": "DEBUG" (test) or "INFO" (prod),
  "db_path": "data/test.db" or "data/rosey.db"
}
```

### Deployment Scripts

**`scripts/deploy.sh`** - Main deployment script
```bash
#!/bin/bash
# Usage: ./scripts/deploy.sh [test|prod]

ENVIRONMENT=$1
CONFIG_FILE="bot/rosey/config-${ENVIRONMENT}.json"

# Validate environment
# Stop existing bot process
# Copy new bot files
# Switch config symlink
# Start bot with new config
# Wait for health check
# Verify connection
```

**`scripts/rollback.sh`** - Rollback to previous version
```bash
#!/bin/bash
# Usage: ./scripts/rollback.sh [test|prod]

ENVIRONMENT=$1
BACKUP_DIR=".deploy-backup"

# Stop current bot
# Restore previous version from backup
# Restart bot
# Verify connection
```

**`scripts/health_check.py`** - Verify bot health
```python
# Check bot connection to CyTube
# Verify database access
# Test basic command response
# Exit 0 if healthy, 1 if not
```

### GitHub Actions Workflow Files

**`.github/workflows/test-deploy.yml`**
- Trigger: pull_request (opened, synchronize)
- Deploy to test channel
- Post status to PR

**`.github/workflows/prod-deploy.yml`**
- Trigger: push to main
- Deploy to production channel
- Create release tag
- Auto-rollback on failure

**`.github/workflows/lint.yml`**
- Trigger: pull_request, push
- Run ruff + mypy
- Fast feedback on code quality

**`.github/workflows/test.yml`**
- Trigger: pull_request, push
- Run full test suite
- Generate coverage report

---

## Implementation Plan

### Phase 1: Foundation (Commits 1-3)
**Goal:** Setup CI infrastructure and linting

**Commit 1: GitHub Actions Setup**
- Create `.github/workflows/` directory
- Add `lint.yml` workflow (ruff + mypy)
- Add `test.yml` workflow (pytest + coverage)
- Configure Python 3.11, caching
- Test workflows on PR

**Commit 2: Configuration Management**
- Create `bot/rosey/config-test.json`
- Create `bot/rosey/config-prod.json`
- Update `.gitignore` (exclude config.json, include templates)
- Document configuration differences
- Add secrets documentation

**Commit 3: Deployment Scripts**
- Create `scripts/deploy.sh`
- Create `scripts/rollback.sh`
- Create `scripts/health_check.py`
- Make scripts executable
- Test locally

### Phase 2: Test Channel Deployment (Commits 4-6)
**Goal:** Automate test channel deployment from PRs

**Commit 4: Test Deploy Workflow**
- Create `.github/workflows/test-deploy.yml`
- Configure PR trigger
- Add deployment steps
- Add GitHub secrets (test channel)
- Test on sample PR

**Commit 5: PR Status Integration**
- Add PR comment with deployment status
- Include test channel URL
- Link to workflow logs
- Add deployment timestamp
- Test status posting

**Commit 6: Test Channel Verification**
- Add health check after deployment
- Verify bot connection
- Test basic command
- Fail deployment if unhealthy
- Test failure scenarios

### Phase 3: Production Deployment (Commits 7-9)
**Goal:** Automate production deployment from main branch

**Commit 7: Production Deploy Workflow**
- Create `.github/workflows/prod-deploy.yml`
- Configure push to main trigger
- Add deployment steps
- Add GitHub secrets (prod channel)
- Test on merge

**Commit 8: Release Automation**
- Auto-create git tags (semantic versioning)
- Generate release notes from commits
- Create GitHub release
- Attach build artifacts
- Test release creation

**Commit 9: Production Verification**
- Add smoke tests after deployment
- Verify critical functionality
- Alert on failure
- Test alerting

### Phase 4: Safety & Observability (Commits 10-12)
**Goal:** Add rollback capability and monitoring

**Commit 10: Rollback Mechanism**
- Backup before deployment
- Implement rollback script
- Auto-rollback on deployment failure
- Manual rollback workflow
- Test rollback scenarios

**Commit 11: Deployment Dashboard**
- Add workflow status badges to README
- Document deployment process
- Create troubleshooting guide
- Add deployment history view
- Test documentation

**Commit 12: Monitoring Integration**
- Log deployment events to database
- Track deployment history
- Add deployment metrics
- Expose status via web UI
- Test monitoring

---

## Testing Strategy

### Pre-Deployment Testing
- All 600+ tests must pass
- 85%+ code coverage required
- Linting must pass (ruff)
- Type checking must pass (mypy)
- No high-severity security issues

### Deployment Testing
- Health check after deployment
- Connection verification
- Basic command test
- Database access test
- Configuration validation

### Rollback Testing
- Test rollback on failure
- Verify rollback completes
- Test manual rollback
- Verify bot recovery

### Integration Testing
- Test PR → test deployment
- Test merge → prod deployment
- Test failure scenarios
- Test concurrent deployments (should queue)

---

## Rollout Plan

### Week 1: Foundation & Test Deployment
- Day 1-2: Setup GitHub Actions workflows (lint, test)
- Day 3-4: Create configuration management
- Day 5: Build deployment scripts
- Day 6-7: Implement test channel deployment

### Week 2: Production & Safety
- Day 1-2: Implement production deployment
- Day 3: Add release automation
- Day 4-5: Build rollback mechanism
- Day 6: Create deployment dashboard
- Day 7: Add monitoring integration

### Week 3: Validation & Documentation
- Day 1-2: End-to-end testing
- Day 3: Failure scenario testing
- Day 4-5: Documentation and runbooks
- Day 6: Team training
- Day 7: Launch and monitor

---

## Dependencies

### External Services
- GitHub Actions (free tier sufficient)
- CyTube test channel (existing)
- CyTube production channel (existing)
- SSH access to deployment server (or local deployment)

### Required Tools
- Python 3.11
- pytest, ruff, mypy (already in requirements.txt)
- systemd (for service management)
- Git (for tagging and releases)

### Configuration Secrets
- `CYTUBEBOT_TEST_PASSWORD` - Test channel bot password
- `CYTUBEBOT_PROD_PASSWORD` - Production channel bot password
- `DEPLOY_SSH_KEY` - SSH key for deployment (if remote)
- `GITHUB_TOKEN` - For posting PR comments (auto-provided)

---

## Risks & Mitigations

### Risk 1: Deployment Failure Breaks Production
**Impact:** High  
**Probability:** Medium  
**Mitigation:** 
- Comprehensive pre-deployment testing (600+ tests)
- Health checks after deployment
- Auto-rollback on failure
- Manual rollback script available
- Test channel validation before production

### Risk 2: Configuration Leak
**Impact:** Critical  
**Probability:** Low  
**Mitigation:**
- Use GitHub Secrets for sensitive values
- Never commit credentials to repository
- Validate .gitignore coverage
- Regular security audits

### Risk 3: Concurrent Deployments Conflict
**Impact:** Medium  
**Probability:** Low  
**Mitigation:**
- GitHub Actions queues workflows automatically
- Add deployment lock mechanism
- Test concurrent scenarios

### Risk 4: Test Channel Interferes with Prod
**Impact:** Low  
**Probability:** Low  
**Mitigation:**
- Completely separate configurations
- Different database files
- Different bot names
- Different channels

### Risk 5: Deployment Too Slow
**Impact:** Low  
**Probability:** Medium  
**Mitigation:**
- Cache Python dependencies
- Parallel test execution
- Optimize health checks
- Target < 5 minute total pipeline time

---

## Success Criteria

### Must Have (MVP)
- ✅ PR creates → auto-deploy to test channel
- ✅ Merge to main → auto-deploy to production
- ✅ All tests pass before deployment
- ✅ Configuration separated (test vs prod)
- ✅ Deployment status visible in GitHub
- ✅ Basic rollback capability

### Should Have
- ✅ Health checks after deployment
- ✅ PR comments with deployment status
- ✅ Automated release creation
- ✅ Deployment badges in README
- ✅ Troubleshooting documentation

### Nice to Have
- 🎯 Smoke tests in production
- 🎯 Deployment metrics dashboard
- 🎯 Slack/Discord notifications
- 🎯 Deployment history tracking
- 🎯 Performance benchmarks in pipeline

---

## Documentation Requirements

### User Documentation
1. **DEPLOYMENT.md** - Complete deployment guide
   - How the pipeline works
   - PR workflow (test deployment)
   - Merge workflow (production deployment)
   - How to trigger manual deployment
   - How to rollback

2. **CONFIGURATION.md** - Configuration management
   - Test vs production configuration
   - How to add secrets
   - Configuration validation
   - Troubleshooting config issues

3. **README.md Updates** - Add deployment section
   - Workflow status badges
   - Quick deployment instructions
   - Link to detailed documentation

### Developer Documentation
1. **TROUBLESHOOTING.md** - Deployment issues
   - Common deployment failures
   - How to read workflow logs
   - How to debug failed deployments
   - Emergency procedures

2. **RUNBOOK.md** - Operations guide
   - Manual deployment steps
   - Rollback procedures
   - Health check interpretation
   - Incident response

---

## Metrics & Monitoring

### Deployment Metrics
- Deployment frequency (target: daily)
- Deployment success rate (target: >95%)
- Time to deploy (target: <5 minutes)
- Rollback frequency (target: <5%)
- Tests passed (target: 100%)

### Quality Metrics
- Code coverage (target: >85%)
- Lint issues (target: 0)
- Type errors (target: 0)
- Failed tests (target: 0)

### Operational Metrics
- Bot uptime (target: >99%)
- Deployment impact on uptime
- Time to rollback (target: <2 minutes)
- Mean time to recovery

---

## Open Questions

1. **Deployment Location:** Local machine vs remote server?
   - Assumption: Local machine for now, systemd services
   - Can migrate to remote server later

2. **Notification Strategy:** How to alert on deployment events?
   - Assumption: GitHub PR comments sufficient for MVP
   - Can add Slack/Discord later

3. **Database Migrations:** How to handle schema changes?
   - Assumption: Out of scope for Sprint 5
   - Will address in future sprint

4. **Multi-Bot Deployment:** Deploy multiple bots simultaneously?
   - Assumption: Focus on rosey bot only
   - Other bots (log, markov, echo) can reuse pipeline

5. **Deployment Approval:** Require manual approval for production?
   - Assumption: Auto-deploy on merge (trust the tests)
   - Can add approval gate later if needed

---

## Appendix

### Related Documents
- Sprint 4: Test Coverage (600+ tests prerequisite)
- systemd/README.md (existing service management)
- WEB_STATUS_SUMMARY.md (status server)

### References
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Python Application Deployment Best Practices](https://12factor.net/)
- [Semantic Versioning](https://semver.org/)

### Sprint Timeline
- **Start Date:** TBD (after Sprint 4 implementation)
- **End Date:** TBD (2-3 weeks estimated)
- **Milestone:** Automated CI/CD pipeline operational

---

**Document Version:** 1.0  
**Last Updated:** 2024-11-11  
**Next Review:** After Sprint 4 completion
