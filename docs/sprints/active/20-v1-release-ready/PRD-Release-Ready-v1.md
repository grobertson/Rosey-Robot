# PRD: Rosey v1.0 Release-Ready Rebuild

**Sprint:** 20 - Release Ready v1.0  
**Status:** Active  
**Created:** November 26, 2025  
**Target Completion:** December 17, 2025 (3 weeks)  

---

## Executive Summary

**Problem**: Sprint 19 broke the test suite (`ModuleNotFoundError: No module named 'lib.playlist'`), exposing deep architectural confusion between `lib/bot.py` (1241 lines) and `bot/rosey/core/` (8 files). We have 1800 tests testing the wrong architecture and zero production deployments.

**Solution**: Clean slate rebuild preserving only working code. Replace 1680 lines of confused bot implementations with a 100-line orchestrator. Keep 201 working plugin tests, add 300 NATS interface tests. Total: 500 focused tests vs 2000 scattered ones.

**Opportunity**: No production deployments = complete architectural freedom. Can implement correct design without migration paths, backward compatibility, or user disruption.

**Timeline**: 3 weeks to production-ready v1.0 vs 3+ months of incremental surgery.

---

## Background

### Current State (Sprint 19)

**What Works** ✅:
- `plugins/` - 60+ files, 201/209 tests passing (96%), correct NATS architecture
- `common/` - database_service.py, config.py, models.py (solid foundation)
- `bot/rosey/core/` - event_bus, plugin_manager, router, cytube_connector (NATS infrastructure)
- 19 sprints of valuable lessons learned

**What's Broken** ❌:
- Test suite: `ModuleNotFoundError: No module named 'lib.playlist'`
- Architectural confusion: lib/bot.py (1241 lines) vs bot/rosey/core/ (8 files)
- 1800 tests test lib/ internals instead of NATS interfaces
- lib/playlist.py removed in Sprint 19, breaks tests/conftest.py
- lib/llm/ removed in Sprint 19, breaks test imports

**Critical Insight**: Sprint 19 successfully migrated functionality to plugins but didn't update the test infrastructure or remove legacy bot implementations.

### Why Clean Slate Now

**Constraint Analysis**:
- ❌ No production deployments
- ❌ No active users to migrate
- ❌ No backward compatibility requirements
- ❌ No data migration needed
- ✅ Complete architectural freedom

**Cost-Benefit**:
| Approach | Timeline | Result | Technical Debt |
|----------|----------|--------|----------------|
| Fix broken tests | 1 week | Tests pass | Still have 1680-line bot confusion |
| Incremental refactor | 8-12 weeks | Gradual improvement | Half-migrated state, endless decisions |
| **Clean slate (v1.0)** | **3 weeks** | **100-line orchestrator, correct architecture** | **Zero legacy debt** |

**Validation**: Plugins prove the NATS architecture works. We just need to delete confused parts and write 100 lines of glue.

---

## Goals & Success Metrics

### Primary Goals

1. **Architectural Clarity**: Single bot implementation, no lib/bot.py confusion
2. **Test Quality**: 500 focused NATS interface tests (not 2000 scattered tests)
3. **Code Simplicity**: 100-line orchestrator replaces 1680 lines of wrappers
4. **Production Ready**: Deployable v1.0 in 3 weeks

### Success Metrics

**Code Metrics**:
- Core bot implementation: ≤150 lines (currently 1680)
- Test count: 500-800 total (currently 2000, 1800 broken)
- Test coverage: 80%+ on plugin interfaces
- Plugin tests: Preserve all 201 working tests

**Quality Metrics**:
- Zero architectural confusion (single bot implementation)
- All tests test correct architecture (NATS interfaces)
- CI/CD green on v1 branch before main merge
- Documentation complete and accurate

**Timeline Metrics**:
- Week 1: v1 branch built and running
- Week 2: Tests migrated, CI green
- Week 3: Documentation complete, merged to main

---

## Architecture

### v1.0 Structure

```
rosey-v1/
├── rosey.py              # 100-line orchestrator (was 1680)
├── core/                 # NATS infrastructure (from bot/rosey/core/)
│   ├── __init__.py
│   ├── event_bus.py
│   ├── plugin_manager.py  # Merged with lib/plugin/ patterns
│   ├── router.py
│   └── cytube_connector.py
├── plugins/              # Copy verbatim (60+ files, working)
│   ├── playlist/
│   ├── llm/
│   ├── trivia/
│   ├── quote-db/
│   └── ... (all plugins)
├── common/               # Copy verbatim (database service)
│   ├── __init__.py
│   ├── config.py
│   ├── database_service.py
│   ├── database.py
│   └── models.py
├── tests/
│   ├── integration/      # 300 NATS interface tests (NEW)
│   ├── plugins/          # 201 tests (PRESERVED from current)
│   └── unit/             # ~100 core unit tests (NEW)
├── docs/                 # Updated documentation
├── .github/              # CI/CD workflows
├── requirements.txt      # Dependencies
└── config.json           # Configuration
```

**What's Gone**:
- ❌ `lib/` directory (entire 74-file directory)
- ❌ `bot/rosey/rosey.py` (439-line wrapper)
- ❌ 1800 lib/ tests (wrong architecture)
- ❌ Migration scripts (already obsolete)
- ❌ Test artifacts (.db, .log files)
- ❌ Stale documentation

### Core Orchestrator (rosey.py)

```python
"""
Rosey Bot v1.0 - NATS-First Plugin Architecture
100 lines replacing 1680 lines of confused wrappers
"""
import asyncio
import nats
from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.router import CommandRouter
from core.cytube_connector import CyTubeConnector
from common.config import load_config

async def main():
    """Main entry point - pure orchestration"""
    config = load_config()
    
    # Connect to NATS
    nc = await nats.connect(config['nats']['url'])
    
    # Initialize core components (all NATS-based)
    event_bus = EventBus(nc)
    plugin_mgr = PluginManager(nc)
    router = CommandRouter(nc)
    cytube = CyTubeConnector(nc, config['cytube'])
    
    # Load plugins (they handle their own logic via NATS)
    await plugin_mgr.load_plugins_from('./plugins')
    
    # Connect to CyTube (publishes events to NATS)
    await cytube.connect()
    
    # That's it. Everything else is plugins.
    print("Rosey v1.0 running - plugin-first architecture")
    await asyncio.Event().wait()

if __name__ == '__main__':
    asyncio.run(main())
```

**Design Principles**:
1. **Orchestration only** - no business logic in core
2. **NATS-first** - all communication via event bus
3. **Plugin autonomy** - plugins own their features
4. **Zero lib/ dependency** - clean slate architecture

### Test Strategy

**Interface Tests** (300 new tests):
```python
# Test NATS interfaces, not internals
async def test_chat_message_broadcast():
    """Verify chat messages are broadcast on NATS"""
    nc = await nats.connect(TEST_NATS_URL)
    
    # Subscribe to chat.message subject
    messages = []
    async def handler(msg):
        messages.append(json.loads(msg.data))
    await nc.subscribe('chat.message', cb=handler)
    
    # Simulate CyTube chat event
    await nc.publish('cytube.chat', json.dumps({
        'username': 'test_user',
        'msg': 'hello'
    }).encode())
    
    await asyncio.sleep(0.1)
    assert len(messages) == 1
    assert messages[0]['msg'] == 'hello'

async def test_plugin_responds_to_command():
    """Verify plugins respond to commands via NATS"""
    nc = await nats.connect(TEST_NATS_URL)
    
    # Request command processing
    response = await nc.request(
        'command.process',
        json.dumps({'msg': '!help'}).encode(),
        timeout=1.0
    )
    
    data = json.loads(response.data)
    assert data['success']
    assert 'Available commands' in data['response']
```

**Test Migration Plan**:
1. Copy all 201 working plugin tests (they already test NATS)
2. Write 300 NATS interface tests (replaces 1800 lib/ tests)
3. Add ~100 unit tests for core components
4. Total: 500-800 focused tests vs 2000 scattered

**Coverage Targets**:
- Plugin interfaces: 80%+ (verify NATS contracts)
- Core components: 70%+ (unit tests for event_bus, router, etc.)
- Integration: Full happy path coverage
- Overall: 75%+ (down from forced 85%, but tests are correct)

---

## Implementation Plan

### Phase 1: Archive & Safety (Day 1)

**Objective**: Preserve current state before any changes

**Tasks**:
1. Archive current main branch
2. Create safety tags
3. Document archive locations

**Commands**:
```powershell
# Archive current state
git checkout main
git pull origin main

# Create archive branch (preserves full history)
git branch archive/pre-v1-sprint-19
git push origin archive/pre-v1-sprint-19

# Create safety tag
git tag v0.9-sprint-19-final
git push origin v0.9-sprint-19-final

# Document in README
# Add notice: "v1.0 clean slate rebuild - see archive/pre-v1-sprint-19 for history"
```

**Deliverables**:
- ✅ archive/pre-v1-sprint-19 branch on GitHub
- ✅ v0.9-sprint-19-final tag
- ✅ README.md updated with archive notice

### Phase 2: Build v1 Branch (Week 1)

**Objective**: Create clean v1 structure with working code only

**Day 1-2: Core Structure**
```powershell
# Create orphan branch (clean slate, no history)
git checkout --orphan v1
git rm -rf .

# Copy essential configs
cp ../Rosey-Robot-backup/.gitignore ./
cp ../Rosey-Robot-backup/requirements.txt ./
cp ../Rosey-Robot-backup/LICENSE ./
cp ../Rosey-Robot-backup/pytest.ini ./
cp ../Rosey-Robot-backup/config.json ./

# Copy working code only
cp -r ../Rosey-Robot-backup/plugins ./
cp -r ../Rosey-Robot-backup/common ./
cp -r ../Rosey-Robot-backup/bot/rosey/core ./core

# Initial commit
git add -A
git commit -m "Rosey v1.0 - Initial structure

Copy working code from Sprint 19:
- plugins/ (60+ files, 96% tests passing)
- common/ (database service, config, models)
- core/ (NATS infrastructure from bot/rosey/core/)

Architectural foundation:
- Plugin-first design
- Pure NATS communication
- Zero lib/ dependency"

git push origin v1
```

**Day 3-4: Core Orchestrator**
- Write new `rosey.py` (100-line orchestrator)
- Merge `lib/plugin/` patterns into `core/plugin_manager.py`
- Update `core/__init__.py` with clean exports
- Write basic smoke tests

**Day 5: Verification**
- Run bot manually to verify startup
- Test plugin loading
- Test CyTube connection
- Verify NATS communication

**Deliverables**:
- ✅ v1 branch on GitHub
- ✅ 100-line rosey.py orchestrator
- ✅ Consolidated core/ directory
- ✅ Bot runs and connects to CyTube
- ✅ Plugins load successfully

### Phase 3: Test Migration (Week 2)

**Objective**: 500 focused tests all passing

**Day 1-2: Plugin Tests**
```powershell
# Copy working plugin tests
cp -r ../Rosey-Robot-backup/tests/plugins ./tests/

# Run to verify (should mostly pass)
pytest tests/plugins -v

# Fix any broken imports (lib. -> core. or common.)
# Update fixtures as needed
```

**Day 3-4: Interface Tests**
- Write 300 NATS interface tests
  - 100 chat message tests
  - 100 command routing tests
  - 50 plugin communication tests
  - 50 CyTube integration tests
- Place in `tests/integration/`

**Day 5: Core Unit Tests**
- Write ~100 unit tests for core components
  - event_bus.py tests
  - plugin_manager.py tests
  - router.py tests
  - cytube_connector.py tests

**Weekend: CI/CD Setup**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov --cov-report=term
```

**Deliverables**:
- ✅ 201 plugin tests passing
- ✅ 300 interface tests passing
- ✅ 100 core unit tests passing
- ✅ Total 500-800 tests all green
- ✅ CI/CD pipeline green
- ✅ 75%+ test coverage

### Phase 4: Documentation (Week 2-3)

**Objective**: Complete, accurate documentation for v1.0

**Day 1: Core Documentation**
- Update `README.md` for v1.0 architecture
- Write `QUICKSTART.md` (5-minute setup guide)
- Update `ARCHITECTURE.md` (new structure)

**Day 2: Migration Guide**
- Write `MIGRATION-V1.md` (v0.9 → v1.0 guide)
- Document what changed and why
- Provide plugin development guide for v1.0

**Day 3: Developer Documentation**
- Update `docs/TESTING.md` for new test strategy
- Update `docs/SETUP.md` for v1.0 setup
- Document NATS interface contracts

**Day 4: User Documentation**
- Write deployment guide for v1.0
- Update plugin README files
- Write troubleshooting guide

**Deliverables**:
- ✅ README.md updated
- ✅ QUICKSTART.md created
- ✅ ARCHITECTURE.md updated
- ✅ MIGRATION-V1.md created
- ✅ All docs accurate for v1.0

### Phase 5: Main Branch Transition (Week 3)

**Objective**: Replace main with v1.0

**Option A: Force Push (Cleanest)**
```powershell
# Final review
git checkout v1
git pull origin v1

# Run full test suite
pytest tests/ -v --cov

# Force push to main
git push origin v1:main --force

# Tag release
git tag v1.0.0
git push origin v1.0.0

# Update default branch description
gh repo edit --description "Rosey Bot v1.0 - Plugin-first CyTube bot"
```

**Option B: PR + Squash (Preserves Link)**
```powershell
# Create PR
gh pr create \
  --base main \
  --head v1 \
  --title "Rosey v1.0 - Release-Ready Clean Slate" \
  --body "$(cat docs/sprints/active/20-v1-release-ready/PR-BODY.md)"

# After review, squash merge
gh pr merge --squash --delete-branch
```

**Post-Merge**:
```powershell
# Archive nano-sprint/19-core-migration
git branch archive/nano-sprint-19
git push origin archive/nano-sprint-19
git push origin :nano-sprint/19-core-migration  # Delete remote

# Clean local branches
git branch -D nano-sprint/19-core-migration
git branch -D v1
```

**Deliverables**:
- ✅ main branch is v1.0
- ✅ v1.0.0 tag created
- ✅ Old branches archived
- ✅ CI/CD green on main
- ✅ Release notes published

---

## Risks & Mitigations

### Risk 1: Plugin Compatibility

**Risk**: Plugins depend on removed lib/ code  
**Likelihood**: Low (plugins already tested, zero lib/ imports)  
**Impact**: Medium (would need plugin updates)  

**Mitigation**:
- Verified plugins have zero `from lib.` imports
- 201/209 plugin tests passing (96%)
- Test all plugins in v1 branch before main merge

### Risk 2: Lost Functionality

**Risk**: Some feature only exists in lib/ and wasn't migrated to plugins  
**Likelihood**: Low (Sprint 19 completed migrations)  
**Impact**: High (lost feature)  

**Mitigation**:
- Review Sprint 19 PRD/specs (documents what was migrated)
- Compare bot capabilities before/after
- Manual testing of all bot commands

### Risk 3: Timeline Slip

**Risk**: 3 weeks not enough for full rebuild  
**Likelihood**: Medium (ambitious timeline)  
**Impact**: Medium (delays v1.0 release)  

**Mitigation**:
- Focus on core functionality first
- Advanced features can be v1.1+
- Daily progress tracking with hard deadlines

### Risk 4: Test Coverage Gaps

**Risk**: 500 tests miss critical edge cases  
**Likelihood**: Medium (fewer tests than before)  
**Impact**: Medium (bugs in production)  

**Mitigation**:
- Focus tests on NATS interfaces (architectural boundaries)
- Keep all 201 working plugin tests (coverage already good)
- Add tests reactively as bugs found
- 75% coverage target (realistic, focused)

---

## Success Criteria

### Week 1 Checkpoint
- [ ] v1 branch exists and bot runs
- [ ] Plugins load successfully
- [ ] CyTube connection works
- [ ] NATS communication verified
- [ ] Core orchestrator ≤150 lines

### Week 2 Checkpoint
- [ ] 500+ tests passing
- [ ] CI/CD green
- [ ] 75%+ test coverage
- [ ] Zero test imports from lib/
- [ ] All tests test NATS interfaces

### Week 3 Checkpoint (Release Ready)
- [ ] Documentation complete and accurate
- [ ] MIGRATION-V1.md written
- [ ] main branch is v1.0
- [ ] v1.0.0 tag created
- [ ] Release notes published
- [ ] Archive branches created

### Quality Gates
- [ ] Zero architectural confusion (single bot implementation)
- [ ] Zero lib/ imports in production code
- [ ] Zero lib/ imports in tests
- [ ] All plugin tests passing
- [ ] CI/CD green for 3 consecutive days

---

## Out of Scope

### Not in v1.0
- Advanced deployment (Docker, systemd) - defer to v1.1
- Performance optimization - focus on correctness first
- Additional plugins - v1.0 preserves existing only
- Monitoring/observability - basic logging sufficient
- Multi-channel support - single CyTube instance only

### Explicitly Removed
- lib/ directory and all contents
- bot/rosey/rosey.py wrapper
- 1800 lib/ tests
- Migration scripts (obsolete)
- Test artifacts (.db, .log files)
- Stale documentation

---

## Appendix

### Current vs v1.0 Comparison

| Metric | Current (Sprint 19) | v1.0 Target |
|--------|---------------------|-------------|
| Core bot lines | 1680 (bot.py + rosey.py) | ≤150 (rosey.py only) |
| Bot implementations | 2 (lib/ + bot/rosey/) | 1 (rosey.py) |
| Test count | 2000 (1800 broken) | 500-800 (all passing) |
| Test architecture | lib/ internals | NATS interfaces |
| Plugin tests | 201 passing | 201+ passing |
| Directory structure | lib/, bot/rosey/, plugins/ | core/, plugins/, common/ |
| lib/ imports | 100+ in tests | 0 everywhere |

### Key Decisions

**Decision 1**: Clean slate vs incremental refactor  
**Rationale**: No production deployments removes migration constraint. Clean slate is faster (3 weeks vs 3 months) and cleaner (zero debt).

**Decision 2**: Orphan branch vs new repo  
**Rationale**: Keep same repo preserves GitHub issues, stars, external links. Orphan branch gives clean git history while maintaining continuity.

**Decision 3**: 500 tests vs 2000 tests  
**Rationale**: Focus on testing architecture (NATS interfaces) vs implementation (lib/ internals). Quality over quantity.

**Decision 4**: Force push vs PR to main  
**Rationale**: Either works. Force push cleaner, PR preserves link. Choose based on preference.

---

**Document Version**: 1.0  
**Created**: November 26, 2025  
**Sprint**: 20 - Release Ready v1.0  
**Status**: Active  
**Next**: Create execution sorties (SPEC-Sortie-1 through SPEC-Sortie-5)
