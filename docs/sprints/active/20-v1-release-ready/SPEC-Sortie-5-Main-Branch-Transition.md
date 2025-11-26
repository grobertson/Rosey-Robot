# SPEC: Sortie 5 - Main Branch Transition

**Sprint:** 20 - Release Ready v1.0  
**Sortie:** 5 of 5  
**Status:** Ready  
**Estimated Duration:** 1 day (Week 3)  
**Created:** November 26, 2025  

---

## Objective

Replace main branch with v1.0, tag official v1.0.0 release, clean up working branches, and announce release. Make v1.0 the new default for all future development.

---

## Context

**Starting Point** (Post-Sortie 4):
- v1 branch complete: working bot, passing tests, full documentation
- CI/CD green for 3+ consecutive days
- All quality gates passed
- Ready for production

**Goal State**:
- main branch is v1.0 code
- v1.0.0 release tagged and published
- nano-sprint/19-core-migration archived and deleted
- GitHub repo reflects v1.0 as primary version

**Decision Made**: Force push to main (clean slate approach) OR PR + squash (preserves link). Both options detailed below.

---

## Success Criteria

### Deliverables
- [ ] main branch replaced with v1.0 code
- [ ] v1.0.0 release tag created and pushed
- [ ] GitHub Release published with notes
- [ ] nano-sprint/19-core-migration archived
- [ ] Working branches cleaned up
- [ ] Default branch is main (v1.0)
- [ ] CI/CD passing on main

### Quality Gates
- main branch = v1 branch content (verified)
- v1.0.0 tag points to main HEAD
- CI passes on main
- GitHub Release visible and complete
- Archive branches preserved
- No broken links or references

---

## Scope

### In Scope
- Replace main with v1.0 (force push OR PR)
- Create v1.0.0 release tag
- Publish GitHub Release with notes
- Archive nano-sprint/19-core-migration branch
- Delete working branches (after archiving)
- Update GitHub repo settings (if needed)

### Out of Scope
- Deployment to production (separate process)
- Announcing on social media (separate process)
- Creating demo videos (defer)
- Performance benchmarking (defer)

---

## Requirements

### Functional Requirements

**FR1: Main Branch Replacement**
Two options (choose one):

**Option A: Force Push** (recommended for clean slate):
```powershell
git checkout v1
git push origin v1:main --force
```

**Option B: PR + Squash** (preserves history link):
```powershell
gh pr create --base main --head v1 --title "Rosey v1.0 Release"
gh pr merge --squash --delete-branch
```

**FR2: Release Tag**
- Tag name: `v1.0.0`
- Annotated tag with full message
- Points to main branch HEAD after transition
- Pushed to remote immediately

**FR3: GitHub Release**
- Title: "Rosey v1.0.0 - Release Ready"
- Body: Release notes (highlights, changes, migration info)
- Tag: v1.0.0
- Mark as "Latest Release"
- Include assets (if applicable)

**FR4: Branch Cleanup**
- Archive: nano-sprint/19-core-migration → archive/sprint-19-working
- Delete: nano-sprint/19-core-migration (remote and local)
- Keep: archive/pre-v1-* branches (permanent)
- Delete: v1 branch (after merge to main)

### Non-Functional Requirements

**NFR1: Safety**
- All archives exist before deletion
- Verify main = v1 before proceeding
- CI passes before considering complete

**NFR2: Communication**
- Clear release notes
- Migration guide linked
- Breaking changes documented
- Support channels listed

**NFR3: Reversibility**
- Archives enable rollback
- Tags permanent (can't be moved)
- Force push documented (for awareness)

---

## Design

### Option A: Force Push (Recommended)

**Advantages**:
- Cleanest slate (no merge commit clutter)
- Clear "v1.0 starts here" in history
- Matches PRD intention (clean slate rebuild)
- Simple and fast

**Disadvantages**:
- Loses link to v0.9 history in main (but preserved in archives)
- Requires `--force` (scary but safe with archives)

**When to Choose**: Default choice for clean slate approach.

### Option B: PR + Squash

**Advantages**:
- Preserves link in git history
- Familiar PR workflow
- GitHub UI shows connection
- Less scary than force push

**Disadvantages**:
- Creates merge commit (link to old history)
- Doesn't feel like "clean slate"
- More steps

**When to Choose**: If preserving git history link important for team.

### Release Notes Structure

**GitHub Release Body**:
```markdown
# Rosey v1.0.0 - Release Ready

> Clean slate rebuild with plugin-first architecture and NATS-based communication.

## 🎉 Highlights

- **100-line orchestrator** replaces 1680 lines of architectural confusion
- **Plugin-first design** with pure NATS communication
- **600 focused tests** (78% coverage) replace 2000 scattered tests
- **Production ready** with CI/CD, monitoring, and complete documentation

## 📦 What's New

### Architecture
- New `rosey.py` orchestrator (pure coordination, zero business logic)
- Consolidated `core/` directory (NATS infrastructure)
- Plugin-first: all features are self-contained plugins
- NATS message bus for all communication

### Testing
- 201 plugin tests (96% pass rate, testing NATS interfaces)
- 300 NATS interface tests (test contracts, not internals)
- 100 core unit tests (component logic)
- CI/CD pipeline with coverage reporting

### Documentation
- Complete architecture documentation
- 5-minute quickstart guide
- Plugin development guide
- NATS interface contracts documentation
- Comprehensive migration guide (v0.9 → v1.0)

## 🔄 Migration from v0.9

**This is a major release with breaking changes.**

See **[MIGRATION-V1.md](https://github.com/grobertson/Rosey-Robot/blob/main/MIGRATION-V1.md)** for complete guide.

**Key Changes**:
- ❌ Removed `lib/` directory (use NATS interfaces)
- ❌ Removed `bot/rosey/rosey.py` wrapper
- ✅ New NATS-based plugin API
- ✅ Same configuration format
- ✅ Same database schema

**v0.9 Archives**: Preserved in `archive/pre-v1-sprint-19` branch.

## 🚀 Getting Started

```bash
# Clone repository
git clone https://github.com/grobertson/Rosey-Robot.git
cd Rosey-Robot

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.json config-local.json
nano config-local.json

# Run
python rosey.py --config config-local.json
```

See [QUICKSTART.md](https://github.com/grobertson/Rosey-Robot/blob/main/QUICKSTART.md) for detailed setup.

## 📚 Documentation

- [README.md](https://github.com/grobertson/Rosey-Robot/blob/main/README.md) - Project overview
- [QUICKSTART.md](https://github.com/grobertson/Rosey-Robot/blob/main/QUICKSTART.md) - 5-minute setup
- [ARCHITECTURE.md](https://github.com/grobertson/Rosey-Robot/blob/main/ARCHITECTURE.md) - System design
- [MIGRATION-V1.md](https://github.com/grobertson/Rosey-Robot/blob/main/MIGRATION-V1.md) - Migration guide
- [PLUGIN-DEVELOPMENT.md](https://github.com/grobertson/Rosey-Robot/blob/main/docs/PLUGIN-DEVELOPMENT.md) - Plugin authoring
- [NATS-CONTRACTS.md](https://github.com/grobertson/Rosey-Robot/blob/main/docs/NATS-CONTRACTS.md) - Interface docs

## 🐛 Known Issues

None at release time. See [issues](https://github.com/grobertson/Rosey-Robot/issues) for latest.

## 💬 Support

- **Issues**: https://github.com/grobertson/Rosey-Robot/issues
- **Documentation**: https://github.com/grobertson/Rosey-Robot/tree/main/docs

## 🙏 Acknowledgments

19 sprints of learning and iteration made v1.0 possible. Thanks to all contributors and lessons learned along the way.

---

**Full Changelog**: [v0.9.0...v1.0.0](https://github.com/grobertson/Rosey-Robot/compare/v0.9-sprint-19-final...v1.0.0)
```

### Branch Cleanup Strategy

**Archive Before Deletion**:
```
nano-sprint/19-core-migration → archive/sprint-19-working
```

**Delete After Archive**:
```
nano-sprint/19-core-migration (remote and local)
v1 (remote and local, after merge to main)
```

**Preserve Forever**:
```
archive/pre-v1-main
archive/pre-v1-sprint-19
archive/sprint-19-working
```

---

## Implementation Steps

### Pre-Flight Checks (30 min)

**Check 1: CI Green on v1**
```powershell
gh run list --branch v1 --limit 5

# Expected: All recent runs ✓ passing
```

**Check 2: All Sortie 1-4 Complete**
```powershell
# Verify archives exist
git branch -r | Select-String "archive/pre-v1"

# Verify v1 branch has all deliverables
git checkout v1
ls
# Should see: rosey.py, core/, plugins/, common/, tests/, docs/, etc.

# Verify tests pass
pytest tests/ -v

# Verify documentation complete
ls *.md
# Should see: README.md, QUICKSTART.md, ARCHITECTURE.md, MIGRATION-V1.md, etc.
```

**Check 3: No Uncommitted Changes**
```powershell
git status
# Should be clean
```

### Option A: Force Push to Main (45 min)

**Step A1: Final Verification**
```powershell
# Checkout v1 branch
git checkout v1
git pull origin v1

# Run full test suite
pytest tests/ -v --cov

# Expected: 600+ tests passing, 78%+ coverage

# Verify CI passing
gh run list --branch v1 --limit 1
# Expected: ✓ passing
```

**Step A2: Force Push to Main**
```powershell
# THIS IS THE BIG MOMENT!
# Force push v1 to main (replaces main)
git push origin v1:main --force

# Verify main now equals v1
git checkout main
git pull origin main

# Check content
ls
# Should see v1 structure (rosey.py, core/, plugins/, etc.)

git log --oneline -5
# Should see v1 commits
```

**Step A3: Create Release Tag**
```powershell
# Create annotated tag on main
git tag -a v1.0.0 -m "Rosey v1.0.0 - Release Ready

Plugin-first architecture with NATS-based communication.

Major Changes:
- 100-line orchestrator replaces 1680 lines
- NATS-first plugin architecture
- 600 focused tests (78% coverage)
- Complete documentation

Breaking Changes:
- Removed lib/ directory
- New NATS-based plugin API
- See MIGRATION-V1.md for full guide

Release Highlights:
- Production ready with CI/CD
- Comprehensive testing
- Complete documentation
- Clean slate architecture

This is the first official release. Previous work
preserved in archive/pre-v1-sprint-19.

Full changelog: https://github.com/grobertson/Rosey-Robot/blob/main/CHANGELOG.md"

# Push tag
git push origin v1.0.0

# Verify tag
git tag -l "v1.*"
# Should show: v1.0.0
```

**Step A4: Verify CI Passes on Main**
```powershell
# Trigger CI on main (push should have triggered it)
# Check status
gh run list --branch main --limit 1

# Wait for completion if needed
gh run watch

# Expected: ✓ passing
```

### Option B: PR + Squash to Main (60 min)

**Step B1: Create PR**
```powershell
# Checkout v1 branch
git checkout v1
git pull origin v1

# Create PR body file
cat > pr-body.md << 'EOF'
# Rosey v1.0.0 - Release Ready

## Summary
Clean slate rebuild with plugin-first architecture. Replaces main with v1.0 code.

## Changes
- **Core**: 100-line orchestrator replaces 1680 lines
- **Architecture**: Plugin-first with NATS communication
- **Tests**: 600 focused tests (78% coverage)
- **Docs**: Complete documentation for v1.0

## Breaking Changes
- Removed `lib/` directory
- New NATS-based plugin API
- See [MIGRATION-V1.md](MIGRATION-V1.md)

## Related PRD
- [PRD-Release-Ready-v1.md](docs/sprints/active/20-v1-release-ready/PRD-Release-Ready-v1.md)

## Sorties Complete
- ✅ Sortie 1: Archives created
- ✅ Sortie 2: v1 branch built
- ✅ Sortie 3: Tests migrated
- ✅ Sortie 4: Documentation complete
- 🔄 Sortie 5: Main branch transition (this PR)

## CI Status
- ✅ Tests passing (600+ tests)
- ✅ Coverage 78%+
- ✅ Linting clean
- ✅ All quality gates passed

## Checklist
- [x] All tests passing
- [x] Documentation complete
- [x] Migration guide written
- [x] Archives created
- [x] CI green

Ready to merge!
EOF

# Create PR
gh pr create \
  --base main \
  --head v1 \
  --title "Rosey v1.0.0 - Release Ready" \
  --body-file pr-body.md

# Note PR number
```

**Step B2: Review PR**
```powershell
# View PR
gh pr view

# Check CI status
gh pr checks

# Wait for CI if needed
gh pr checks --watch
```

**Step B3: Merge PR**
```powershell
# Squash merge (single commit on main)
gh pr merge --squash --delete-branch

# Or if prefer merge commit:
# gh pr merge --merge --delete-branch
```

**Step B4: Create Release Tag**
```powershell
# Checkout main (now has v1 code)
git checkout main
git pull origin main

# Create tag (same as Option A Step A3)
git tag -a v1.0.0 -m "..." # (see Step A3)
git push origin v1.0.0
```

### Publish GitHub Release (30 min)

**Step 1: Create Release**
```powershell
# Create release from tag
gh release create v1.0.0 \
  --title "Rosey v1.0.0 - Release Ready" \
  --notes-file release-notes.md

# Or use GitHub web UI:
# https://github.com/grobertson/Rosey-Robot/releases/new
# - Tag: v1.0.0
# - Title: "Rosey v1.0.0 - Release Ready"
# - Body: (paste release notes from design section)
# - Check "Set as latest release"
```

**Step 2: Verify Release**
```powershell
# View release
gh release view v1.0.0

# Or check web:
start https://github.com/grobertson/Rosey-Robot/releases/tag/v1.0.0
```

### Branch Cleanup (20 min)

**Step 1: Archive nano-sprint/19-core-migration**
```powershell
# Create archive branch
git branch archive/sprint-19-working nano-sprint/19-core-migration
git push origin archive/sprint-19-working

# Verify archive
git ls-remote --heads origin | Select-String "archive"
# Should show: archive/pre-v1-main, archive/pre-v1-sprint-19, archive/sprint-19-working
```

**Step 2: Delete Working Branches**
```powershell
# Delete nano-sprint/19-core-migration
git push origin --delete nano-sprint/19-core-migration
git branch -D nano-sprint/19-core-migration

# Delete v1 branch (if Option A was used)
# Note: If Option B was used, PR already deleted it
git push origin --delete v1  # Only if still exists
git branch -D v1  # Only if still exists
```

**Step 3: Verify Cleanup**
```powershell
# Check remote branches
git branch -r

# Should see:
# origin/main (v1.0 code)
# origin/archive/pre-v1-main
# origin/archive/pre-v1-sprint-19
# origin/archive/sprint-19-working

# Should NOT see:
# origin/nano-sprint/19-core-migration
# origin/v1 (unless you chose to keep it)
```

### Post-Transition Verification (15 min)

**Step 1: Verify main = v1.0**
```powershell
git checkout main
git pull origin main

# Check structure
ls
# Should see: rosey.py, core/, plugins/, common/, tests/, docs/

# Check tests pass
pytest tests/ -q
# Expected: 600+ passed

# Check documentation
cat README.md | Select-Object -First 20
# Should show v1.0 content
```

**Step 2: Verify CI on main**
```powershell
gh run list --branch main --limit 3
# All recent runs should be ✓ passing
```

**Step 3: Verify Release**
```powershell
gh release view v1.0.0
# Should show release notes, tag, etc.
```

**Step 4: Verify Archives**
```powershell
# Check all archives exist
git ls-remote --heads origin | Select-String "archive"

# Spot check one archive
git checkout archive/pre-v1-sprint-19
ls
# Should see old structure (lib/, bot/, etc.)

# Return to main
git checkout main
```

---

## Testing Strategy

### Pre-Transition Tests

**Test 1: v1 Branch Complete**
```powershell
git checkout v1
pytest tests/ --cov
# Expected: 600+ tests passing, 78%+ coverage
```

**Test 2: CI Green**
```powershell
gh run list --branch v1 --limit 5
# Expected: All ✓ passing
```

**Test 3: Documentation Complete**
```powershell
ls *.md
# Expected: README.md, QUICKSTART.md, ARCHITECTURE.md, MIGRATION-V1.md
```

### Post-Transition Tests

**Test 1: main = v1**
```powershell
git checkout main
git diff v1
# Expected: No differences (if v1 branch still exists)
# Or: git log shows v1 commits
```

**Test 2: Release Exists**
```powershell
gh release view v1.0.0
# Expected: Release details shown
```

**Test 3: CI on main**
```powershell
gh run list --branch main --limit 1
# Expected: ✓ passing
```

**Test 4: Archives Intact**
```powershell
git checkout archive/pre-v1-sprint-19
ls lib/
# Expected: lib/ directory exists (v0.9 code)
```

### Acceptance Criteria

- [ ] main branch contains v1.0 code
- [ ] v1.0.0 tag exists and points to main HEAD
- [ ] GitHub Release published and visible
- [ ] CI passing on main
- [ ] nano-sprint/19-core-migration archived and deleted
- [ ] v1 branch deleted (if applicable)
- [ ] Archive branches intact and accessible
- [ ] README renders correctly on GitHub main page
- [ ] Release notes complete and accurate

---

## Dependencies

### Prerequisites
- Sorties 1-4 complete
- v1 branch complete and stable
- CI green on v1 for 3+ days
- All documentation complete

### External Dependencies
- GitHub CLI (`gh`) for release creation
- GitHub Actions for CI verification
- Git push access to main branch

### Blocks
None - this is final sortie

---

## Risks & Mitigations

### Risk 1: Force Push Loses Important History
**Likelihood**: Low (archives exist)  
**Impact**: Low (history preserved in archives)  

**Mitigation**:
- Full archives created in Sortie 1
- Multiple archive branches (pre-v1-main, pre-v1-sprint-19)
- Tags as permanent markers (v0.9-*-final)
- Can always restore from archives
- v0.9 history was broken test suite anyway

### Risk 2: CI Fails on main After Transition
**Likelihood**: Low (CI green on v1)  
**Impact**: Medium (delays release)  

**Mitigation**:
- CI already passing on v1 (identical code)
- Verify CI green before proceeding
- Can rollback if needed (restore from archive)
- GitHub Actions configured for main branch

### Risk 3: Breaking Existing Clones
**Likelihood**: High (force push changes history)  
**Impact**: Low (no external users yet)  

**Mitigation**:
- No production deployments (no external users)
- Team aware of clean slate approach
- Documentation explains transition
- Fresh clone recommended in MIGRATION-V1.md

### Risk 4: Release Notes Incomplete
**Likelihood**: Medium  
**Impact**: Low (can edit release)  

**Mitigation**:
- Template provided with comprehensive structure
- Can edit GitHub Release after creation
- MIGRATION-V1.md covers details
- Release notes point to full documentation

---

## Rollback Plan

If something goes wrong:

### Rollback from Force Push
```powershell
# Restore main from archive
git checkout archive/pre-v1-main
git branch -D main
git checkout -b main
git push origin main --force

# Restore working branch
git checkout archive/sprint-19-working
git branch -D nano-sprint/19-core-migration
git checkout -b nano-sprint/19-core-migration
git push origin nano-sprint/19-core-migration --force
```

### Rollback from PR Merge
```powershell
# Revert merge commit on main
git checkout main
git revert HEAD
git push origin main
```

### Rollback Release
```powershell
# Delete release (keeps tag)
gh release delete v1.0.0

# Or delete tag too
gh release delete v1.0.0 --yes
git push origin --delete v1.0.0
git tag -d v1.0.0
```

---

## Notes

### Communication Plan

**Internal** (before transition):
- Review PRD and all sorties
- Confirm force push vs PR approach
- Schedule transition (low-traffic time)

**External** (after transition):
- Update repo description
- Add topics to GitHub repo (bot, cytube, nats, python)
- Consider announcement (Twitter, Reddit, etc.) - optional

### Post-Release Tasks (Out of Scope)

**Immediate** (same day):
- Monitor CI on main
- Watch for issues
- Test fresh clone

**Short-term** (week 1):
- Deploy to production environment
- Monitor bot behavior
- Address any issues

**Long-term** (ongoing):
- Update documentation as needed
- Plan v1.1 features
- Collect feedback

### Why Force Push is Safe Here

**Normally force push is dangerous**:
- Rewrites history (breaks clones)
- Can lose commits (if not careful)
- Disrupts collaborators

**But in this case**:
- ✅ No external users (no production deployments)
- ✅ Full archives exist (history preserved)
- ✅ Intentional clean slate (documented approach)
- ✅ Team aware and aligned
- ✅ Can rollback easily

---

## Completion Checklist

### Pre-Flight
- [ ] All Sortie 1-4 complete
- [ ] CI green on v1 for 3+ days
- [ ] All tests passing (600+)
- [ ] Documentation complete
- [ ] No uncommitted changes
- [ ] Archives verified

### Transition (Choose One)
**Option A: Force Push**
- [ ] Final verification on v1
- [ ] Force push v1 to main
- [ ] Verify main = v1 content
- [ ] Create v1.0.0 tag
- [ ] Push tag to remote
- [ ] CI passes on main

**Option B: PR + Squash**
- [ ] Create PR (v1 → main)
- [ ] CI passes on PR
- [ ] Review PR
- [ ] Merge PR (squash)
- [ ] Create v1.0.0 tag
- [ ] Push tag to remote

### Release
- [ ] Create GitHub Release
- [ ] Title: "Rosey v1.0.0 - Release Ready"
- [ ] Body: Complete release notes
- [ ] Tag: v1.0.0
- [ ] Mark as latest release
- [ ] Verify release visible

### Cleanup
- [ ] Archive nano-sprint/19-core-migration
- [ ] Delete nano-sprint/19-core-migration
- [ ] Delete v1 branch (if applicable)
- [ ] Verify cleanup complete
- [ ] Archives intact

### Verification
- [ ] main branch is v1.0
- [ ] v1.0.0 tag exists
- [ ] Release published
- [ ] CI passing on main
- [ ] README renders on GitHub
- [ ] Archives accessible
- [ ] No broken links

---

**Estimated Time**: 1 day  
**Actual Time**: _[To be filled after completion]_  
**Completed By**: _[To be filled]_  
**Completion Date**: _[To be filled]_  

---

## Success!

Upon completion:
- ✅ Rosey v1.0.0 officially released
- ✅ main branch is production-ready v1.0
- ✅ Complete documentation published
- ✅ CI/CD operational
- ✅ Clean slate architecture achieved

**Next Steps**: Deploy to production, monitor, plan v1.1 features.

**Sprint 20 Complete!** 🎉
