# Sprint 6: Make It Real - Product Requirements Document

## Overview

**Sprint Name**: Make It Real  
**Sprint Goal**: Deploy infrastructure to actual servers and validate in real production environments  
**Status**: Planning  
**Created**: 2025-11-12  

## Context

Sprint 5 "Ship It!" delivered a complete CI/CD pipeline with all infrastructure components:
- Deployment workflows (test and production)
- Monitoring stack (Prometheus + Alertmanager)
- Status dashboard
- Verification scripts
- systemd services
- Documentation

However, all of this infrastructure is theoretical or stubbed:
- Workflows have echo commands instead of actual SSH deployments
- No actual servers provisioned
- GitHub Secrets not configured
- Health endpoint not implemented
- No real-world validation

**Sprint 6 takes this infrastructure and makes it real** by deploying to actual servers, configuring real secrets, implementing missing dependencies, and validating everything works in production.

## Problem Statement

The CI/CD pipeline built in Sprint 5 is complete but untested in real environments:

1. **Stubbed Deployments**: Workflows simulate deployment with echo commands
2. **Missing Health Endpoint**: Verification scripts, monitoring, and dashboard all expect `/api/health` but it doesn't exist
3. **No Server Configuration**: No actual servers provisioned or configured
4. **Unconfigured Secrets**: GitHub Secrets needed for SSH deployment not set up
5. **Untested in Production**: No validation that infrastructure works with real traffic
6. **Missing Operational Experience**: No real-world deployment experience to refine procedures

## Success Criteria

Sprint 6 is successful when:

1. ✅ Bot deployed and running on actual test server
2. ✅ Bot deployed and running on actual production server
3. ✅ Health endpoint implemented and returning valid data
4. ✅ Monitoring stack collecting real metrics
5. ✅ Dashboard displaying real bot status
6. ✅ Alerts firing and delivering to notification channels
7. ✅ Rollback procedure tested and validated
8. ✅ Bot handling production traffic successfully
9. ✅ Documentation updated with real-world findings
10. ✅ Operational confidence in deployment pipeline

## Dependencies & Blockers

### Prerequisites
- Sprint 5 complete (all infrastructure code exists)
- Sprint 6a (Quicksilver) complete (NATS event bus architecture)
- PR #12 merged (or Sprint 6 branches from Sprint 5)

### External Dependencies
- **Servers**: Need access to test and production servers (VM, cloud, or physical)
- **Domain/Networking**: Server connectivity and firewall configuration
- **CyTube Access**: Production bot credentials and channel access
- **NATS Server**: Message broker for event bus architecture (Sprint 6a requirement)

### Technical Debt from Sprint 5
Must be resolved during Sprint 6:
- **Health endpoint** (#16) - Required by monitoring, verification, dashboard
- **SSH deployment** (#17) - Required for automated deployments
- **WebSocket timeout** (#14) - Critical bug blocking bot functionality
- **Database checks** (#18) - Optional, document for future

### New Requirements from Sprint 6a (Quicksilver)
The Quicksilver nano-sprint introduced a NATS-based event bus architecture that requires:
- **NATS Server Installation**: Must be installed and running on all deployment servers
- **NATS Configuration**: Connection strings and credentials in environment configs
- **Firewall Rules**: NATS ports (4222 client, 8222 monitoring) must be accessible
- **Service Management**: NATS must start before bot and restart on failure

## Sprint 6 Sorties

### Phase 1: Foundation (Sorties 1-2)
Setup infrastructure needed for first deployment.

#### Sortie 1: Provision and Configure Servers (#19)
**Goal**: Get actual servers ready for deployment  
**Tasks**:
- Provision test server (VM/cloud instance)
- Provision production server
- Configure base system (Python, git, systemd)
- Create deployment user
- Set up SSH keys
- Configure firewall rules
- Document server specifications

**Acceptance**:
- Both servers accessible via SSH
- Python 3.9+ installed
- Deployment user configured
- Directory structure created
- Firewall allows health check ports

#### Sortie 2: Configure GitHub Secrets (#20)
**Goal**: Enable automated deployments  
**Tasks**:
- Generate dedicated SSH keys for deployment
- Add public keys to servers
- Configure GitHub Secrets:
  - `SSH_KEY_TEST`, `SSH_KEY_PROD`
  - `TEST_SERVER_HOST`, `TEST_SERVER_USER`
  - `PROD_SERVER_HOST`, `PROD_SERVER_USER`
- Test SSH authentication
- Document secret management procedures

**Acceptance**:
- All secrets configured in GitHub
- SSH authentication works with keys
- Secrets match workflow requirements
- Security best practices followed

### Phase 2: Critical Dependencies (Sorties 2A-2C)
Execute in parallel with Sorties 1-2 to unblock first deployment.

#### Sortie 2A: Fix WebSocket Timeout (#14)
**Goal**: Fix critical bug preventing bot connection  
**Priority**: CRITICAL - Bot fails 100% without this fix  
**Tasks**:
- Update `config-test.json`: timeout 0.1 → 3.0
- Update `config-prod.json`: timeout 0.1 → 3.0
- Update documentation with rationale
- Test connection with new timeout

**Acceptance**:
- Bot connects successfully
- Connection stable over time
- Configuration documented
- No regression in performance

#### Sortie 2B: Implement Health Endpoint (#16)
**Goal**: Implement `/api/health` endpoint required by all monitoring  
**Priority**: CRITICAL - Blocks verification, monitoring, dashboard  
**Tasks**:
- Implement Flask endpoint on separate thread
- Return JSON with 8 fields:
  - `status` (connected/disconnected)
  - `connected` (boolean)
  - `channel` (string)
  - `uptime` (seconds)
  - `version` (from VERSION file)
  - `user_count` (int)
  - `requests` (counter)
  - `errors` (counter)
- Configure ports (8000 prod, 8001 test)
- Integrate with bot state
- Test endpoint locally

**Acceptance**:
- Endpoint accessible on configured port
- Returns valid JSON
- All 8 fields present and accurate
- Endpoint works when bot connected/disconnected
- No performance impact on bot

#### Sortie 2C: Configure SSH Deployment (#17)
**Goal**: Replace stubbed echo commands with actual SSH deployment  
**Priority**: CRITICAL - Required for automated deployments  
**Tasks**:
- Update `test-deploy.yml` with real SSH commands
- Update `prod-deploy.yml` with real SSH commands
- Use rsync or scp for file transfer
- Implement service restart commands
- Test SSH commands manually
- Document SSH deployment process

**Acceptance**:
- Workflows use actual SSH commands
- File transfer works reliably
- Service restarts work
- Deployments complete successfully
- SSH operations properly secured

### Phase 3: First Deployments (Sorties 3-5)

#### Sortie 3: Create systemd Services (#21)
**Goal**: Manage bot and services as system services  
**Tasks**:
- Review/update `systemd/cytube-bot.service`
- Review/update `systemd/cytube-web.service`
- Create `systemd/prometheus.service`
- Create `systemd/alertmanager.service`
- Update paths to match deployment structure
- Document service management

**Acceptance**:
- All 4 service files created/updated
- Services use correct paths and users
- Services configured for auto-restart
- Services start on boot
- Service management documented

#### Sortie 4: First Test Deployment (#22)
**Goal**: Execute first end-to-end deployment to test server  
**Tasks**:
- Verify pre-deployment checklist
- Trigger test-deploy workflow
- Monitor deployment execution
- Run verification scripts
- Verify all services running
- Verify bot connects to test channel
- Check dashboard and monitoring
- Document deployment experience

**Acceptance**:
- Deployment completes successfully
- All 4 services running
- Verification script passes (100%)
- Bot connected to CyTube test channel
- Dashboard accessible and accurate
- Health endpoint returns valid data
- Prometheus collecting metrics
- No critical errors in logs

#### Sortie 5: First Production Deployment (#23)
**Goal**: Execute first production deployment with approval  
**Tasks**:
- Verify test deployment stable
- Review production workflow
- Trigger production workflow (merge to main)
- Review and approve deployment
- Monitor deployment execution
- Run production verification scripts
- Verify bot handles production traffic
- Document production experience

**Acceptance**:
- Approval gate reviewed and approved
- Deployment completes successfully
- All services running in production
- Production verification passes
- Bot connected to production channel
- Dashboard accessible
- Monitoring operational
- Deployment documented in CHANGELOG

### Phase 4: Monitoring & Operations (Sorties 6-8)

#### Sortie 6: Deploy Monitoring Stack (#24)
**Goal**: Get Prometheus and Alertmanager operational  
**Tasks**:
- Install Prometheus on production server
- Deploy Prometheus configuration
- Deploy alert rules
- Install Alertmanager
- Deploy Alertmanager configuration
- Configure notification endpoints
- Verify Prometheus scraping health endpoint
- Verify alerts evaluating
- Test alert delivery

**Acceptance**:
- Prometheus running and scraping bot
- Alert rules loaded and evaluating
- Alertmanager receiving alerts
- At least one notification channel working
- Prometheus UI accessible
- Metrics being collected

#### Sortie 7: Deploy Dashboard (#25)
**Goal**: Get status dashboard operational  
**Tasks**:
- Deploy dashboard to production
- Configure dashboard service
- Verify dashboard shows bot status
- Verify links to Prometheus/Alertmanager work
- Configure dashboard access
- Document dashboard features
- Add dashboard screenshots

**Acceptance**:
- Dashboard service running
- Dashboard accessible via browser
- Shows correct bot status
- Displays accurate metrics
- Links to monitoring work
- Dashboard documented with screenshots

#### Sortie 8: Test Alert Notifications (#26)
**Goal**: Validate alerts reach notification endpoints  
**Tasks**:
- Test webhook notifications
- Test email notifications
- Test Slack notifications (if configured)
- Verify alert grouping
- Verify resolution notifications
- Test multiple alert scenarios
- Document notification procedures

**Acceptance**:
- Webhook notifications working
- Email notifications working
- Alert grouping verified
- Resolution notifications verified
- Notification format clear and actionable
- Alert response procedures documented

### Phase 5: Production Validation (Sorties 9-11)

#### Sortie 9: Test Rollback Procedure (#27)
**Goal**: Validate rollback works in production  
**Tasks**:
- Document current production state
- Execute rollback test
- Time rollback duration
- Verify services after rollback
- Redeploy to latest
- Update rollback procedures
- Document rollback decision criteria

**Acceptance**:
- Rollback executed successfully
- Services functioning after rollback
- Rollback duration < 5 minutes
- Forward deployment successful
- Rollback procedures updated
- No data loss during rollback

#### Sortie 10: Validate Production Traffic (#28)
**Goal**: Verify bot handles real production traffic  
**Tasks**:
- Monitor bot for 24+ hours
- Verify command processing
- Verify event handling
- Monitor performance metrics
- Check for memory leaks
- Monitor error rates
- Test under high activity
- Document production behavior

**Acceptance**:
- Bot stable for 24+ hours
- All commands working
- Events processed correctly
- Performance within targets
- No critical errors
- No memory leaks
- Production behavior documented

#### Sortie 11: Update Documentation (#29)
**Goal**: Capture real-world deployment learnings  
**Tasks**:
- Update deployment documentation
- Update monitoring documentation
- Create operations runbook
- Create troubleshooting guide
- Add deployment checklists
- Document lessons learned
- Add actual timings and findings

**Acceptance**:
- Deployment docs updated
- Monitoring docs reflect actual config
- Runbook created with common issues
- Troubleshooting guide complete
- Real examples and screenshots added
- Lessons learned documented

## Technical Architecture

### Deployment Flow
```
GitHub Actions Workflow
         ↓
   SSH to Server
         ↓
   rsync/scp files
         ↓
   systemctl restart services
         ↓
   Run verification scripts
         ↓
   Report status
```

### Production Architecture
```
Bot Process (systemd)
   ↓ (metrics via health endpoint)
Prometheus (systemd)
   ↓ (alert rules)
Alertmanager (systemd)
   ↓ (notifications)
Webhook/Email/Slack

Dashboard (systemd)
   ↓ (reads health endpoint)
Web Browser
```

### Health Endpoint
```python
# GET /api/health
{
  "status": "connected",
  "connected": true,
  "channel": "RoseyRoom",
  "uptime": 86400,
  "version": "1.0.0",
  "user_count": 42,
  "requests": 1234,
  "errors": 5
}
```

## Risk Analysis

### High Risk
1. **Server Access Issues**
   - Risk: Can't access servers via SSH
   - Mitigation: Test SSH access before deployment, have backup access methods

2. **Health Endpoint Performance**
   - Risk: Endpoint impacts bot performance
   - Mitigation: Run on separate thread, implement async properly

3. **Production Bot Credentials**
   - Risk: Invalid credentials block production deployment
   - Mitigation: Test credentials in test environment first

### Medium Risk
1. **SSH Deployment Complexity**
   - Risk: SSH commands fail in CI environment
   - Mitigation: Test SSH commands manually first, add proper error handling

2. **Network Configuration**
   - Risk: Firewall blocks monitoring or health endpoints
   - Mitigation: Document and test all required ports

3. **Service Dependencies**
   - Risk: Services fail to start due to missing dependencies
   - Mitigation: Document all dependencies, test service startup

### Low Risk
1. **Documentation Gaps**
   - Risk: Missing real-world details in docs
   - Mitigation: Update docs throughout sprint, not just at end

2. **Alert Tuning**
   - Risk: Too many or too few alerts
   - Mitigation: Start conservative, tune based on experience

## Validation Plan

### Per-Sortie Validation
Each sortie has acceptance criteria that must be met before proceeding.

### End-of-Sprint Validation
1. **Functionality Check**
   - Bot running in production
   - All services operational
   - Monitoring collecting metrics
   - Alerts configured and tested

2. **Reliability Check**
   - Bot stable for 24+ hours
   - No critical errors
   - Automated deployments working
   - Rollback tested and documented

3. **Operational Readiness**
   - Documentation updated
   - Runbook created
   - Team trained on operations
   - Confidence in production deployment

## Success Metrics

### Deployment Metrics
- **Test deployment**: First attempt succeeds
- **Production deployment**: Completed with approval
- **Deployment duration**: < 10 minutes end-to-end
- **Verification pass rate**: 100% of checks pass

### Reliability Metrics
- **Uptime**: > 99% during validation period
- **Error rate**: < 1% of operations
- **Connection stability**: > 23 hours continuous
- **Rollback time**: < 5 minutes

### Operational Metrics
- **Documentation completeness**: All procedures documented
- **Runbook coverage**: Common issues have solutions
- **Team confidence**: High confidence in deployment process
- **Monitoring coverage**: All critical metrics tracked

## Out of Scope

The following are explicitly NOT part of Sprint 6:

1. **Testing Infrastructure** (Sprint 7)
   - Unit tests
   - Integration tests
   - Load testing
   - Coverage analysis

2. **Additional Features**
   - New bot commands
   - New bot functionality
   - Additional monitoring beyond what exists

3. **Performance Optimization**
   - Code optimization
   - Database optimization
   - Beyond proving it works

4. **Security Hardening**
   - Beyond basic SSH key security
   - Detailed security audit
   - Penetration testing

5. **Scaling**
   - Multiple bot instances
   - Load balancing
   - High availability setup

## Timeline Estimate

Based on Sprint 5 experience (3:1 planning ratio):

### Optimistic (Best Case)
- **Planning**: 1 day
- **Implementation**: 3-4 days
- **Total**: ~5 days

### Realistic (Expected)
- **Planning**: 2 days
- **Implementation**: 6-8 days
- **Total**: 8-10 days

### Pessimistic (If Issues)
- **Planning**: 3 days
- **Implementation**: 12-15 days
- **Total**: 15-18 days

**Key Variables**:
- Server provisioning speed
- Network/access issues
- Health endpoint complexity
- Production validation duration

## Next Steps

### Before Starting Sprint 6
1. Review and approve this PRD
2. Ensure Sprint 5 PR (#12) is merged
3. Create Sprint 6 branch from main
4. Verify server access available
5. Verify bot credentials for production

### To Begin Sprint 6
1. Start with Sortie 1 (server provisioning)
2. Execute Sortie 2 (GitHub Secrets configuration)
3. Parallelize Sorties 2A, 2B, 2C (critical dependencies) - can start after Sortie 2
4. Execute Sortie 3 (systemd services)
5. Proceed through remaining sorties sequentially
6. Update documentation continuously

### Dependencies to Resolve
- [ ] Production server access confirmed
- [ ] Production bot credentials obtained
- [ ] GitHub Secrets access confirmed
- [ ] Network/firewall requirements documented

## Appendix

### Related GitHub Issues
- #14: WebSocket timeout bug
- #15: Refactor lib/bot.py (future, not Sprint 6)
- #16: Implement health endpoint
- #17: Configure SSH deployment
- #18: Database health checks (document for future)
- #19-29: Sprint 6 sorties (11 issues)

### Related Documentation
- Sprint 5 Retrospective: `docs/5-ship-it/RETROSPECTIVE.md`
- Sprint 5 Summary: `docs/5-ship-it/SPRINT-5-SUMMARY.md`
- Deployment Guide: `docs/5-ship-it/DEPLOYMENT.md`
- Monitoring Guide: `docs/5-ship-it/MONITORING.md`

### Reference Architecture
Sprint 6 implements the architecture designed in Sprint 5:
- Deployment workflows (test and production)
- Monitoring stack (Prometheus + Alertmanager)
- Status dashboard
- Verification scripts
- systemd service management

### Key Learnings from Sprint 5
1. **Detailed specs eliminate guesswork** - Continue this in Sprint 6
2. **Sortie chunking is perfect** - 11 sorties for Sprint 6
3. **3:1 planning ratio** - Expect 6-10 days implementation
4. **Documentation is implementation** - Update docs continuously
5. **Real-world validation is essential** - Core goal of Sprint 6

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-12  
**Status**: Ready for Review
