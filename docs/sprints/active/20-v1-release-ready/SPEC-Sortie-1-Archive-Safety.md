# SPEC: Sortie 1 - Archive & Safety

**Sprint:** 20 - Release Ready v1.0  
**Sortie:** 1 of 5  
**Status:** Ready  
**Estimated Duration:** 1 day  
**Created:** November 26, 2025  

---

## Objective

Create comprehensive safety net before v1.0 rebuild by archiving current codebase state, preserving full history, and documenting archive locations. Enable zero-risk experimentation with ability to restore any previous state.

---

## Context

**Current State**:
- Branch: `nano-sprint/19-core-migration` (Sprint 19 complete)
- Test suite: BROKEN (`ModuleNotFoundError: No module named 'lib.playlist'`)
- Main branch: May not reflect Sprint 19 changes yet
- Zero production deployments (no rollback concerns)

**Why Archive First**:
- Sprint 19 represents 19 sprints of work and lessons learned
- Test suite broken but code has value (plugins, infrastructure)
- v1.0 will be clean slate - need reference to old structure
- Archive preserves full git history for future reference

**Key Insight**: With no production deployments, we can be bold with v1.0 rebuild, but should still preserve history for learning and potential reference.

---

## Success Criteria

### Deliverables
- [ ] Archive branch created: `archive/pre-v1-sprint-19`
- [ ] Safety tag created: `v0.9-sprint-19-final`
- [ ] Both pushed to GitHub (remote backup)
- [ ] README.md updated with archive notice
- [ ] Archive documented in CHANGELOG.md
- [ ] Verification: Can checkout archive and see Sprint 19 state

### Quality Gates
- Archive branch contains all Sprint 19 commits
- Tag points to exact current HEAD
- Remote branches/tags visible on GitHub
- Documentation clearly explains archive purpose

---

## Scope

### In Scope
- Archive current `main` branch state
- Archive current `nano-sprint/19-core-migration` branch
- Create descriptive safety tags
- Document archive locations and purpose
- Update README.md with migration notice
- Verify remote backups exist

### Out of Scope
- Cleaning up old branches (defer to Sortie 5)
- Deleting any code (only archiving)
- Starting v1 work (that's Sortie 2)
- Documentation beyond archive notices

---

## Requirements

### Functional Requirements

**FR1: Archive Main Branch**
- Create archive branch from current `main`
- Name: `archive/pre-v1-main`
- Preserve full git history
- Push to remote immediately

**FR2: Archive Sprint 19 Branch**
- Create archive branch from `nano-sprint/19-core-migration`
- Name: `archive/pre-v1-sprint-19`
- Preserve full git history
- Push to remote immediately

**FR3: Create Safety Tags**
- Tag main: `v0.9-main-final`
- Tag Sprint 19: `v0.9-sprint-19-final`
- Use annotated tags with descriptions
- Push all tags to remote

**FR4: Document Archives**
- Update README.md with prominent notice
- Add CHANGELOG.md entry for v0.9 archive
- List all archive branches and tags
- Explain purpose and how to access

### Non-Functional Requirements

**NFR1: Safety**
- All archives pushed to remote before any destructive operations
- Verification step confirms archives are accessible
- Documentation prevents accidental archive deletion

**NFR2: Clarity**
- Archive naming clearly indicates purpose (`pre-v1`)
- Documentation explains what was archived and why
- Future developers can understand archive structure

---

## Design

### Archive Strategy

**Branch Archives** (preserve full history):
```
archive/pre-v1-main              ← Full main branch history
archive/pre-v1-sprint-19         ← Full Sprint 19 branch history
```

**Tag Archives** (point-in-time snapshots):
```
v0.9-main-final                  ← Main branch HEAD before v1.0
v0.9-sprint-19-final             ← Sprint 19 HEAD before v1.0
```

**Why Both**:
- Branches: Can checkout and continue work if needed
- Tags: Permanent markers, can't be accidentally moved
- Together: Complete safety net

### Naming Convention

**Pattern**: `archive/pre-v1-{source-branch}`
- `pre-v1` indicates these are pre-v1.0 snapshots
- `{source-branch}` identifies what was archived
- `archive/` prefix groups all archives together

**Version Tags**: `v0.9-{branch}-final`
- `v0.9` indicates pre-v1.0 state
- `{branch}` identifies source
- `-final` indicates last state before v1.0

### Documentation Updates

**README.md Update**:
```markdown
# Rosey Robot

> **⚠️ MIGRATION NOTICE**: This project underwent a clean slate rebuild for v1.0.
> The previous architecture (through Sprint 19) is preserved in:
> - Branch: `archive/pre-v1-sprint-19`
> - Tag: `v0.9-sprint-19-final`
> 
> See [MIGRATION-V1.md](docs/MIGRATION-V1.md) for details on architectural changes.

[rest of README...]
```

**CHANGELOG.md Entry**:
```markdown
## [0.9.0] - 2025-11-26 - Pre-v1.0 Archive

### Archive Notice
Complete codebase archived before v1.0 clean slate rebuild.

**Archive Locations**:
- Main branch: `archive/pre-v1-main` (tag: `v0.9-main-final`)
- Sprint 19: `archive/pre-v1-sprint-19` (tag: `v0.9-sprint-19-final`)

**What Was Preserved**:
- All 19 sprints of development history
- lib/ directory architecture (74 files)
- bot/rosey/ wrapper implementation (439 lines)
- 2000 tests (1800 testing lib/ internals)
- All documentation through Sprint 19

**Why Archived**:
v1.0 represents a clean slate rebuild focusing on plugin-first architecture.
No production deployments existed, enabling architectural freedom.

**Access Archives**:
```bash
# View Sprint 19 final state
git checkout archive/pre-v1-sprint-19

# Or use tag
git checkout v0.9-sprint-19-final
```

### Verification Steps

**Step 1**: Verify local archives created
```powershell
git branch | Select-String "archive/pre-v1"
# Should show: archive/pre-v1-main, archive/pre-v1-sprint-19

git tag | Select-String "v0.9"
# Should show: v0.9-main-final, v0.9-sprint-19-final
```

**Step 2**: Verify remote backups
```powershell
git ls-remote --heads origin | Select-String "archive/pre-v1"
git ls-remote --tags origin | Select-String "v0.9"
```

**Step 3**: Verify checkout works
```powershell
git checkout archive/pre-v1-sprint-19
# Should see Sprint 19 files (lib/, bot/rosey/, tests/)
git log --oneline -5
# Should show Sprint 19 commits
```

---

## Implementation Steps

### Step 1: Archive Main Branch (15 min)

```powershell
# Ensure main is up to date
git checkout main
git pull origin main

# Create archive branch
git branch archive/pre-v1-main
git push origin archive/pre-v1-main

# Create annotated tag
git tag -a v0.9-main-final -m "Main branch final state before v1.0 clean slate rebuild

Preserved for reference:
- Project state through November 2025
- All commits and history on main branch
- Pre-Sprint 19 architecture

Access: git checkout v0.9-main-final
Archive branch: archive/pre-v1-main"

git push origin v0.9-main-final
```

### Step 2: Archive Sprint 19 Branch (15 min)

```powershell
# Switch to Sprint 19 branch
git checkout nano-sprint/19-core-migration
git pull origin nano-sprint/19-core-migration

# Create archive branch
git branch archive/pre-v1-sprint-19
git push origin archive/pre-v1-sprint-19

# Create annotated tag
git tag -a v0.9-sprint-19-final -m "Sprint 19 (Core Migrations) final state before v1.0

Preserved for reference:
- Playlist plugin migration (complete)
- LLM plugin migration (complete)
- lib/playlist.py and lib/llm/ removed
- 201/209 plugin tests passing (96%)
- Test suite broken (ModuleNotFoundError)

Access: git checkout v0.9-sprint-19-final
Archive branch: archive/pre-v1-sprint-19"

git push origin v0.9-sprint-19-final
```

### Step 3: Update Documentation (20 min)

**Update README.md**:
```powershell
# Add migration notice at top of README.md (after title)
# See "Documentation Updates" section above for content
```

**Update CHANGELOG.md**:
```powershell
# Add v0.9.0 entry at top
# See "Documentation Updates" section above for content
```

**Commit documentation**:
```powershell
git checkout nano-sprint/19-core-migration

# Stage changes
git add README.md CHANGELOG.md

# Commit
git commit -m "Document v0.9 archives before v1.0 rebuild

- Add migration notice to README.md
- Document archive locations in CHANGELOG.md
- Explain v1.0 clean slate approach

Relates-to: Sprint 20 Sortie 1 (Archive & Safety)"

git push origin nano-sprint/19-core-migration
```

### Step 4: Verification (10 min)

**Verify remote archives**:
```powershell
# Check GitHub for archive branches
gh repo view --web
# Navigate to branches, should see archive/pre-v1-*

# Check tags
gh release list
# Should show v0.9 tags (or use tags view)
```

**Verify checkout**:
```powershell
# Test Sprint 19 archive
git checkout archive/pre-v1-sprint-19
ls -la
# Should see: lib/, bot/, plugins/, tests/, etc.

git log --oneline -10
# Should show Sprint 19 commits

# Return to working branch
git checkout nano-sprint/19-core-migration
```

**Document verification**:
```powershell
# Check README.md shows migration notice
cat README.md | Select-Object -First 20

# Check CHANGELOG.md shows v0.9 entry
cat CHANGELOG.md | Select-Object -First 50
```

---

## Testing Strategy

### Manual Verification Tests

**Test 1: Archive Branch Exists**
```powershell
# Should pass
git show-ref --verify refs/heads/archive/pre-v1-main
git show-ref --verify refs/heads/archive/pre-v1-sprint-19
```

**Test 2: Tags Exist**
```powershell
# Should pass
git show-ref --verify refs/tags/v0.9-main-final
git show-ref --verify refs/tags/v0.9-sprint-19-final
```

**Test 3: Remote Backups**
```powershell
# Should return commit SHAs
git ls-remote origin archive/pre-v1-main
git ls-remote origin archive/pre-v1-sprint-19
git ls-remote origin refs/tags/v0.9-main-final
git ls-remote origin refs/tags/v0.9-sprint-19-final
```

**Test 4: Checkout Works**
```powershell
git checkout archive/pre-v1-sprint-19
if (Test-Path lib/bot.py) {
    Write-Host "✓ Archive contains lib/bot.py" -ForegroundColor Green
} else {
    Write-Host "✗ Archive missing lib/bot.py" -ForegroundColor Red
}
```

### Acceptance Criteria

- [ ] Both archive branches exist locally and remotely
- [ ] Both tags exist locally and remotely
- [ ] Can checkout archive branches and see Sprint 19 files
- [ ] README.md contains migration notice
- [ ] CHANGELOG.md contains v0.9 archive entry
- [ ] All git operations completed without errors
- [ ] No code deleted (only archived)

---

## Dependencies

### Prerequisites
- Current branch: `nano-sprint/19-core-migration` or `main`
- Git status clean (all changes committed)
- Access to push to `grobertson/Rosey-Robot`

### Blocks
None - this is first sortie, no dependencies

### Blocked By
None

---

## Risks & Mitigations

### Risk 1: Accidental Archive Deletion
**Likelihood**: Low  
**Impact**: High (lose reference to Sprint 19 work)  

**Mitigation**:
- Both branch and tag archives (redundancy)
- Remote backups on GitHub (can restore)
- Clear `archive/` prefix prevents accidental deletion
- Documentation warns against deleting archives

### Risk 2: Archive Becomes Outdated Reference
**Likelihood**: Medium  
**Impact**: Low (archives are snapshots, not maintained)  

**Mitigation**:
- Clear naming indicates "pre-v1" timeframe
- Documentation explains archive is point-in-time
- v1.0 docs reference archives only for comparison

---

## Notes

### Archive Maintenance
- **Do NOT** update archive branches after creation (they're snapshots)
- **Do NOT** delete archive branches without team discussion
- **Keep archives** even after v1.0 ships (reference for learning)

### Future Cleanup
In Sortie 5 (Main Branch Transition), we'll:
- Archive and delete `nano-sprint/19-core-migration` working branch
- Keep `archive/pre-v1-*` branches permanently
- Clean up any other stale working branches

### GitHub UI
Archives will appear in:
- Branches dropdown (with `archive/` prefix)
- Tags/Releases view (v0.9-* tags)
- Network graph (full history preserved)

---

## Completion Checklist

- [ ] Checked out `main` branch
- [ ] Created `archive/pre-v1-main` branch
- [ ] Pushed `archive/pre-v1-main` to remote
- [ ] Created `v0.9-main-final` tag
- [ ] Pushed tag to remote
- [ ] Checked out `nano-sprint/19-core-migration` branch
- [ ] Created `archive/pre-v1-sprint-19` branch
- [ ] Pushed `archive/pre-v1-sprint-19` to remote
- [ ] Created `v0.9-sprint-19-final` tag
- [ ] Pushed tag to remote
- [ ] Updated README.md with migration notice
- [ ] Updated CHANGELOG.md with v0.9 entry
- [ ] Committed documentation updates
- [ ] Pushed documentation to remote
- [ ] Verified all archives exist remotely
- [ ] Verified can checkout archives
- [ ] Verified documentation renders correctly

---

**Estimated Time**: 1 hour  
**Actual Time**: _[To be filled after completion]_  
**Completed By**: _[To be filled]_  
**Completion Date**: _[To be filled]_  

---

**Next Sortie**: [SPEC-Sortie-2-Build-v1-Branch.md](SPEC-Sortie-2-Build-v1-Branch.md)
