# Deferred Sprints

This directory contains sprint documentation for work that has been **deferred** (postponed) due to various constraints.

## What "Deferred" Means

Deferred sprints are:

- **Planned**: Fully documented with PRDs and technical specifications
- **Valid**: Still valuable and aligned with project goals
- **Postponed**: Not currently being worked on due to constraints
- **Recoverable**: Can be resumed when circumstances change

## Current Deferred Sprints

### Sprint 5: ship-it (Production Deployment)

**Status**: ⏸️ Deferred - Using manual deployment instead

**Reason**: GitHub Actions deployment automation deferred due to cost constraints. The project uses manual SSH deployment instead.

**Contents**:
- Full CI/CD pipeline documentation
- GitHub Actions workflow specifications
- Test and production deployment workflows
- Configuration management and monitoring integration

**What Was Implemented**:
- ✅ GitHub Actions workflows created (`.github/workflows/`)
- ✅ Deployment scripts implemented (`scripts/deploy.sh`, `scripts/rollback.sh`)
- ✅ Systemd service configurations (`systemd/`)
- ✅ Comprehensive deployment guide (`DEPLOYMENT_SETUP.md`)
- ⏸️ **Workflows disabled** to save GitHub Actions minutes costs

**Resume Conditions**: 
- GitHub Actions budget becomes available
- Project requires automated CI/CD for team collaboration
- Deployment frequency justifies automation costs

### Sprint 6: make-it-real (Advanced Deployment)

**Status**: ⏸️ Deferred - Cost constraints

**Reason**: Advanced deployment features (dedicated servers, monitoring stack, multi-environment orchestration) deferred due to infrastructure and operational costs.

**Contents**:
- Server provisioning and configuration
- Multi-environment deployment (test, staging, production)
- Monitoring stack deployment (Prometheus, Grafana, Alertmanager)
- Health checks and automated rollback procedures
- Production validation and traffic monitoring

**What Was Considered**:
- Dedicated test/production servers
- Full monitoring and alerting infrastructure
- Automated rollback mechanisms
- Dashboard for deployment status
- Production traffic validation

**Current Alternative**:
- Manual deployment to production server
- Basic health endpoint monitoring
- Manual verification procedures
- SSH-based deployment scripts

**Resume Conditions**:
- Project grows to require dedicated infrastructure
- Budget allocated for hosting and monitoring services
- Team size increases requiring robust deployment processes
- Production traffic justifies investment in monitoring

## Relationship to Active Work

### Completed Work Relevant to Deferred Sprints

- **Sprint 6a (quicksilver)**: NATS Event Bus - Completed successfully, provides foundation for distributed deployment
- **Manual Deployment**: Working deployment process documented in `DEPLOYMENT_SETUP.md`
- **Health Endpoints**: Basic health monitoring implemented in status server

### Active Sprints (7-9)

Active work continues with:
- **Sprint 7 (the-divide)**: API Separation - Planned
- **Sprint 8 (inception)**: Multi-level Architecture - Planned
- **Sprint 9 (funny-games)**: Interactive Features - Planned

These sprints focus on feature development and architecture improvements that work with the current manual deployment approach.

## How to Resume a Deferred Sprint

If circumstances change and a deferred sprint should be resumed:

1. **Move Directory**: 
   ```powershell
   Move-Item 'docs\sprints\deferred\{sprint-name}' 'docs\sprints\active\'
   ```

2. **Update Documentation**:
   - Update `docs/README.md` sprint listings
   - Update `docs/SPRINT_NAMING.md` status table
   - Update `AGENTS.md` example sprints section

3. **Review Specifications**:
   - Re-read PRD to confirm goals still align
   - Review technical specs for any changes needed
   - Update dependencies or architecture changes

4. **Create Branch**:
   ```bash
   git checkout -b nano-sprint/{sprint-name}
   ```

5. **Begin Implementation**:
   - Follow the sortie specifications in sequence
   - Update acceptance criteria as work progresses
   - Commit changes with references to spec files

## Cost Analysis

### Sprint 5 Costs (GitHub Actions)

GitHub Actions pricing (as of 2025):
- **Free tier**: 2,000 minutes/month for public repos
- **Private repos**: $0.008 per minute (Linux runners)

Estimated monthly costs:
- **CI on every push**: ~500 minutes/month = $4/month
- **Test deployments**: ~200 minutes/month = $1.60/month
- **Production deployments**: ~100 minutes/month = $0.80/month
- **Total**: ~$6.40/month or ~$77/year

**Decision**: Manual deployment preferred for single-developer project.

### Sprint 6 Costs (Infrastructure)

Estimated infrastructure costs:
- **Test Server**: $5-10/month (VPS, 1GB RAM)
- **Production Server**: $10-20/month (VPS, 2GB RAM)
- **Monitoring Services**: $0-15/month (self-hosted or SaaS)
- **Total**: ~$15-45/month or ~$180-540/year

**Decision**: Single production server with manual deployment sufficient for current scale.

## Documentation

Both deferred sprints contain complete planning documentation:

### Sprint 5 (ship-it)
- `PRD-CI-CD-Pipeline.md` - Product requirements
- `SPEC-Sortie-*.md` - 12 technical specifications
- `RETROSPECTIVE.md` - Sprint retrospective
- `SPRINT-5-SUMMARY.md` - Summary of work

### Sprint 6 (make-it-real)
- `PRD-Make-It-Real.md` - Product requirements
- `SPEC-Sortie-*.md` - 11+ technical specifications
- `PLANNING-COMPLETE.md` - Planning completion notes

## See Also

- [Active Sprints](../active/) - Current and planned work
- [Completed Sprints](../completed/) - Finished work
- [Sprint Naming Convention](../../SPRINT_NAMING.md) - Sprint organization
- [Agent Workflow](../../../AGENTS.md) - Development process
- [Deployment Setup](../../../DEPLOYMENT_SETUP.md) - Current manual deployment guide

---

**Status**: Both sprints fully planned, implementations deferred  
**Last Updated**: January 2025  
**Decision Made By**: Cost-benefit analysis for solo development project
