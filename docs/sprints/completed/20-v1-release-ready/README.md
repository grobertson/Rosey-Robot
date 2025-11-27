# Sprint 20: v1.0 Release Ready - Execution Plan

**Status:** Active  
**Timeline:** 3 weeks (November 26 - December 17, 2025)  
**Approach:** Clean slate rebuild (no production deployments exist)  

---

## Overview

Complete clean slate rebuild of Rosey Bot with plugin-first architecture. Replace 1680 lines of architectural confusion with 100-line orchestrator. Migrate from lib/-based architecture to pure NATS communication.

**Key Metrics**:
- 1680 lines → 100 lines (core bot)
- 2000 tests → 600 focused tests
- 66% coverage → 78% coverage
- lib/ architecture → NATS-first architecture

---

## Sprint Documents

### Planning
- **[PRD-Release-Ready-v1.md](PRD-Release-Ready-v1.md)** - Complete product requirements

### Execution (Sorties)
1. **[SPEC-Sortie-1-Archive-Safety.md](SPEC-Sortie-1-Archive-Safety.md)** - Archive & Safety (Day 1)
2. **[SPEC-Sortie-2-Build-v1-Branch.md](SPEC-Sortie-2-Build-v1-Branch.md)** - Build v1 Branch (Week 1)
3. **[SPEC-Sortie-3-Test-Migration.md](SPEC-Sortie-3-Test-Migration.md)** - Test Migration (Week 2)
4. **[SPEC-Sortie-4-Documentation.md](SPEC-Sortie-4-Documentation.md)** - Documentation (Week 2-3)
5. **[SPEC-Sortie-5-Main-Branch-Transition.md](SPEC-Sortie-5-Main-Branch-Transition.md)** - Main Branch Transition (Week 3)

---

## Timeline

### Week 1: Build v1 Branch
**Sortie 1 (Day 1)**: Archive & Safety
- Create archive branches (archive/pre-v1-main, archive/pre-v1-sprint-19)
- Create safety tags (v0.9-main-final, v0.9-sprint-19-final)
- Document archives in README and CHANGELOG

**Sortie 2 (Days 2-5)**: Build v1 Branch
- Create orphan branch (clean slate)
- Copy working code (plugins/, common/, core/)
- Write 100-line orchestrator (rosey.py)
- Consolidate core infrastructure
- Manual smoke test (bot runs, plugins load, CyTube connects)

**Deliverables**:
- ✅ Archives created (safety net)
- ✅ v1 branch with working bot
- ✅ 100-line orchestrator replacing 1680 lines
- ✅ Bot runs and loads plugins successfully

### Week 2: Test & Documentation
**Sortie 3 (Days 6-10)**: Test Migration
- Migrate 201 plugin tests from Sprint 19
- Write 300 NATS interface tests (chat, commands, plugins, CyTube)
- Write 100 core unit tests (event_bus, plugin_manager, router, cytube_connector)
- Setup CI/CD pipeline (GitHub Actions)
- Coverage reporting (78%+ achieved)

**Sortie 4 (Days 11-13)**: Documentation
- Update core docs (README, QUICKSTART, ARCHITECTURE)
- Write migration guide (MIGRATION-V1.md)
- Write developer docs (PLUGIN-DEVELOPMENT, NATS-CONTRACTS)
- Update existing docs (remove all lib/ references)
- Verify all code examples work

**Deliverables**:
- ✅ 600+ tests passing (78% coverage)
- ✅ CI/CD pipeline green
- ✅ Complete documentation
- ✅ Zero lib/ references in docs

### Week 3: Main Branch Transition
**Sortie 5 (Days 14-15)**: Main Branch Transition
- Replace main with v1.0 (force push OR PR + squash)
- Create v1.0.0 release tag
- Publish GitHub Release with notes
- Archive and delete working branches
- Final verification (CI, release, archives)

**Deliverables**:
- ✅ main branch is v1.0
- ✅ v1.0.0 release published
- ✅ CI passing on main
- ✅ Branch cleanup complete

---

## Progress Tracking

### Sortie Completion

| Sortie | Name | Duration | Status | Completion Date |
|--------|------|----------|--------|-----------------|
| 1 | Archive & Safety | 1 day | 📋 Ready | - |
| 2 | Build v1 Branch | 5 days | 📋 Ready | - |
| 3 | Test Migration | 5 days | 📋 Ready | - |
| 4 | Documentation | 3 days | 📋 Ready | - |
| 5 | Main Branch Transition | 1 day | 📋 Ready | - |

**Legend**: 📋 Ready | 🔄 In Progress | ✅ Complete | ⏸️ Blocked

### Key Milestones

- [ ] **Day 1**: Archives created (safety net)
- [ ] **Day 5**: v1 branch running (bot works)
- [ ] **Day 10**: Tests passing (CI green)
- [ ] **Day 13**: Docs complete (ready to ship)
- [ ] **Day 15**: v1.0.0 released (main branch is v1.0)

---

## Architecture Comparison

### Before (v0.9 - Sprint 19)
```
lib/                          (74 files, 1241 lines in bot.py)
├── bot.py                    ← Core bot class
├── plugin/                   ← Plugin infrastructure
├── storage/                  ← Storage abstractions
├── connection/               ← Connection adapters
└── ...

bot/rosey/
└── rosey.py                  (439 lines, wrapper around lib.Bot)

plugins/                      (60+ files)

tests/                        (2000 tests, 1800 broken)
```

**Problems**:
- Two bot implementations (lib/bot.py + bot/rosey/rosey.py)
- Architectural confusion (which to use?)
- 1800 tests testing wrong architecture (lib/ internals)
- Test suite broken (`ModuleNotFoundError: No module named 'lib.playlist'`)

### After (v1.0)
```
rosey.py                      (100 lines, pure orchestration)

core/                         (NATS infrastructure)
├── event_bus.py
├── plugin_manager.py
├── router.py
└── cytube_connector.py

plugins/                      (60+ files, unchanged)

common/                       (database, config)

tests/                        (600 tests, all passing)
├── integration/              (300 NATS interface tests)
├── unit/                     (100 core component tests)
└── plugins/                  (201 plugin tests)
```

**Benefits**:
- Single bot implementation (rosey.py)
- Clear architecture (orchestration vs plugins)
- 600 focused tests (test NATS interfaces)
- Zero lib/ confusion

---

## Key Decisions

### Decision 1: Clean Slate vs Incremental Refactor
**Choice**: Clean slate (Option C from CRISIS-ANALYSIS.md)  
**Rationale**: No production deployments = complete architectural freedom. Clean slate is 3 weeks vs 3+ months incremental surgery.  
**Trade-off**: Lose lib/ implementation history (but preserved in archives).

### Decision 2: Orphan Branch vs New Repo
**Choice**: Orphan branch in same repo  
**Rationale**: Preserves GitHub issues, stars, external links. Clean git history while maintaining continuity.  
**Trade-off**: Force push to main eventually (but safe with archives).

### Decision 3: Force Push vs PR to Main
**Choice**: Either acceptable (documented both approaches)  
**Rationale**: Force push cleaner slate, PR preserves history link. Both achieve same result.  
**Default**: Force push (matches clean slate philosophy).

### Decision 4: Test Count Target
**Choice**: 600 focused tests vs 2000 scattered tests  
**Rationale**: Test architecture (NATS interfaces) not implementation (lib/ internals). Quality over quantity.  
**Trade-off**: Fewer tests but better tests (78% coverage vs 66%).

---

## Success Criteria (Sprint Level)

### Must Have (v1.0 Release)
- [x] PRD complete and approved
- [ ] All 5 sorties complete
- [ ] v1.0.0 released on GitHub
- [ ] main branch is v1.0 code
- [ ] CI/CD green and stable
- [ ] 600+ tests passing (75%+ coverage)
- [ ] Complete documentation (zero lib/ references)
- [ ] Archives created (v0.9 preserved)

### Should Have
- [ ] 100-line orchestrator (≤150 acceptable)
- [ ] 78%+ test coverage (75% minimum)
- [ ] All plugin tests migrated (201+)
- [ ] All code examples tested
- [ ] Migration guide comprehensive

### Nice to Have (Defer to v1.1)
- Performance benchmarks
- Docker deployment guide
- Video tutorials
- API reference documentation

---

## Risks & Mitigations

### High Priority Risks

**Risk 1: Timeline Slip** (Medium Likelihood, Medium Impact)
- **Mitigation**: Focus on core functionality, defer nice-to-haves, daily progress tracking
- **Contingency**: Extend Week 3 if needed

**Risk 2: Tests Don't Migrate Cleanly** (Medium Likelihood, Medium Impact)
- **Mitigation**: Plugin tests already test NATS (correct architecture), systematic import fixes
- **Contingency**: Can reduce interface test count (300 → 200)

**Risk 3: Documentation Takes Too Long** (Medium Likelihood, Low Impact)
- **Mitigation**: Prioritize core docs, defer deep-dives to v1.1
- **Contingency**: Ship with core docs, iterate on developer docs

### Low Priority Risks

**Risk 4: CI Fails After Main Transition** (Low Likelihood, Medium Impact)
- **Mitigation**: CI already passing on v1, identical code
- **Contingency**: Rollback plan documented in Sortie 5

**Risk 5: Archives Lost** (Low Likelihood, High Impact)
- **Mitigation**: Multiple archives (branches + tags), remote backups
- **Contingency**: Git history immutable on GitHub

---

## Communication Plan

### Internal (Team)
- **Before Start**: Review PRD and all sorties
- **Daily**: Progress updates (which sortie, blockers)
- **After Each Sortie**: Verify deliverables complete
- **After Sprint**: Retrospective (lessons learned)

### External (Future)
- **v1.0 Release**: GitHub Release notes, README badge
- **Post-Release**: Consider announcement (optional)
- **Ongoing**: Update docs with learnings

---

## Resources

### Documentation
- [PRD-Release-Ready-v1.md](PRD-Release-Ready-v1.md) - Full product requirements
- [CRISIS-ANALYSIS.md](../../CRISIS-ANALYSIS.md) - Original architectural analysis
- [AGENTS.md](../../../../AGENTS.md) - Agent workflow guide

### Archives (Post-Sortie 1)
- `archive/pre-v1-main` - Main branch before v1.0
- `archive/pre-v1-sprint-19` - Sprint 19 final state
- `v0.9-main-final` tag
- `v0.9-sprint-19-final` tag

### Sprint 19 (Previous)
- [Sprint 19 Docs](../../completed/19-core-migration/) - Core Migrations (completed)
- Playlist plugin migration
- LLM plugin migration
- Test suite broken (starting point)

---

## Next Actions

### Immediate (Start Sprint)
1. Read PRD-Release-Ready-v1.md thoroughly
2. Review all 5 sortie specs
3. Confirm force push vs PR preference
4. Schedule 3-week sprint timeline
5. **Start Sortie 1** (Archive & Safety)

### Post-Sprint (v1.1 Planning)
1. Retrospective on Sprint 20
2. Collect feedback on v1.0
3. Plan v1.1 features
4. Deploy to production
5. Monitor and iterate

---

**Sprint Status**: 📋 Ready to Start  
**Created**: November 26, 2025  
**Target Completion**: December 17, 2025  
**Approach**: Clean Slate / No Production Deployments  

**Ready to begin!** 🚀
