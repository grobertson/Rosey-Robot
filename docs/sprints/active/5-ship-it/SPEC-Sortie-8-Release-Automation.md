# SPEC: Sortie 8 - Release Automation

**Sprint:** 5 (ship-it)  
**Sortie:** 8 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sortie 7 (Production Deploy Workflow)

---

## Objective

Automate version tagging, changelog generation, and GitHub release creation for production deployments. This provides clear version history, automated release notes, and simplified rollback targeting.

## Success Criteria

- ✅ Semantic versioning (MAJOR.MINOR.PATCH) automated
- ✅ Changelog generated from commit messages
- ✅ GitHub releases created automatically
- ✅ Release notes include PR links and contributors
- ✅ Tags trigger production deployment workflow
- ✅ Version bump workflow easy to use
- ✅ Release artifacts attached (optional)

## Technical Specification

### Versioning Strategy

**Semantic Versioning:** `vMAJOR.MINOR.PATCH`

**Version Bump Rules:**
- **MAJOR (v0.2.0):** Breaking changes, major refactors
- **MINOR (v0.1.0):** New features, non-breaking changes
- **PATCH (v0.0.1):** Bug fixes, minor improvements

**Version Storage:**
- Git tags: `v1.2.3`
- `VERSION` file in repository root
- Python package: `lib/__version__.py`

### Changelog Format

**Conventional Commits:** Used to categorize changes

```
feat: add new feature (MINOR bump)
fix: fix bug (PATCH bump)
docs: update documentation (PATCH bump)
refactor: code refactoring (MINOR bump)
test: add tests (PATCH bump)
chore: update dependencies (PATCH bump)
BREAKING CHANGE: breaking change (MAJOR bump)
```

**Changelog Structure:**

```markdown
# Changelog

## [1.2.0] - 2024-11-12

### Features
- Add CI/CD pipeline (#45)
- Add deployment verification (#46)

### Bug Fixes
- Fix database connection timeout (#44)
- Fix health check race condition (#47)

### Documentation
- Update deployment guide (#48)

### Contributors
- @developer1
- @developer2
```

### Release Automation Workflow

**Trigger:** Manual workflow dispatch

**Process:**
1. Determine version bump type (major/minor/patch)
2. Calculate next version number
3. Generate changelog from commits
4. Update VERSION file
5. Commit version bump
6. Create and push git tag
7. Create GitHub release with notes
8. Trigger production deployment

## Implementation

### scripts/bump_version.py

```python
#!/usr/bin/env python3
"""
Automated version bumping and changelog generation.

Analyzes commit messages since last tag and determines
appropriate version bump using semantic versioning.

Usage:
    python scripts/bump_version.py --bump major
    python scripts/bump_version.py --bump minor
    python scripts/bump_version.py --bump patch
    python scripts/bump_version.py --auto
"""

import os
import re
import sys
import subprocess
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

class VersionBumper:
    """Handle version bumping and changelog generation."""
    
    def __init__(self):
        self.repo_root = Path(__file__).parent.parent
        self.version_file = self.repo_root / "VERSION"
        self.changelog_file = self.repo_root / "CHANGELOG.md"
        
    def get_current_version(self) -> str:
        """Get current version from VERSION file."""
        if self.version_file.exists():
            return self.version_file.read_text().strip()
        return "0.0.0"
    
    def parse_version(self, version: str) -> Tuple[int, int, int]:
        """Parse version string into components."""
        # Remove 'v' prefix if present
        version = version.lstrip('v')
        parts = version.split('.')
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {version}")
        return tuple(map(int, parts))
    
    def bump_version(self, current: str, bump_type: str) -> str:
        """Calculate next version based on bump type."""
        major, minor, patch = self.parse_version(current)
        
        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        elif bump_type == 'patch':
            patch += 1
        else:
            raise ValueError(f"Invalid bump type: {bump_type}")
        
        return f"{major}.{minor}.{patch}"
    
    def get_last_tag(self) -> str:
        """Get the most recent git tag."""
        try:
            result = subprocess.run(
                ['git', 'describe', '--tags', '--abbrev=0'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            # No tags yet
            return None
    
    def get_commits_since_tag(self, tag: str = None) -> List[Dict]:
        """Get commits since last tag."""
        if tag:
            cmd = ['git', 'log', f'{tag}..HEAD', '--pretty=format:%H|%s|%an|%ae']
        else:
            cmd = ['git', 'log', '--pretty=format:%H|%s|%an|%ae']
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        commits = []
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            sha, subject, author_name, author_email = line.split('|', 3)
            commits.append({
                'sha': sha[:7],
                'subject': subject,
                'author_name': author_name,
                'author_email': author_email,
                'type': self.parse_commit_type(subject)
            })
        
        return commits
    
    def parse_commit_type(self, subject: str) -> str:
        """Parse commit type from conventional commit format."""
        # Match: "type: description" or "type(scope): description"
        match = re.match(r'^(\w+)(?:\([^)]+\))?: ', subject)
        if match:
            commit_type = match.group(1).lower()
            # Normalize types
            if commit_type in ['feat', 'feature']:
                return 'feature'
            elif commit_type == 'fix':
                return 'fix'
            elif commit_type == 'docs':
                return 'docs'
            elif commit_type in ['refactor', 'perf']:
                return 'refactor'
            elif commit_type == 'test':
                return 'test'
            elif commit_type in ['chore', 'build', 'ci']:
                return 'chore'
        return 'other'
    
    def auto_determine_bump_type(self, commits: List[Dict]) -> str:
        """Automatically determine version bump type from commits."""
        has_breaking = any('BREAKING CHANGE' in c['subject'] or 
                          '!' in c['subject'].split(':')[0] 
                          for c in commits)
        
        if has_breaking:
            return 'major'
        
        has_features = any(c['type'] == 'feature' for c in commits)
        
        if has_features:
            return 'minor'
        
        return 'patch'
    
    def generate_changelog_section(self, commits: List[Dict], version: str) -> str:
        """Generate changelog section for this release."""
        date = datetime.now().strftime('%Y-%m-%d')
        
        # Group commits by type
        features = [c for c in commits if c['type'] == 'feature']
        fixes = [c for c in commits if c['type'] == 'fix']
        docs = [c for c in commits if c['type'] == 'docs']
        refactors = [c for c in commits if c['type'] == 'refactor']
        tests = [c for c in commits if c['type'] == 'test']
        chores = [c for c in commits if c['type'] == 'chore']
        others = [c for c in commits if c['type'] == 'other']
        
        # Get unique contributors
        contributors = sorted(set(c['author_name'] for c in commits))
        
        # Build changelog section
        lines = [
            f"## [{version}] - {date}",
            ""
        ]
        
        if features:
            lines.append("### ✨ Features")
            for commit in features:
                # Extract PR number if present
                pr_match = re.search(r'#(\d+)', commit['subject'])
                pr_link = f" (#{pr_match.group(1)})" if pr_match else ""
                
                # Clean up subject
                subject = re.sub(r'^feat(?:\([^)]+\))?: ', '', commit['subject'])
                subject = re.sub(r' \(#\d+\)$', '', subject)
                
                lines.append(f"- {subject}{pr_link} ({commit['sha']})")
            lines.append("")
        
        if fixes:
            lines.append("### 🐛 Bug Fixes")
            for commit in fixes:
                pr_match = re.search(r'#(\d+)', commit['subject'])
                pr_link = f" (#{pr_match.group(1)})" if pr_match else ""
                subject = re.sub(r'^fix(?:\([^)]+\))?: ', '', commit['subject'])
                subject = re.sub(r' \(#\d+\)$', '', subject)
                lines.append(f"- {subject}{pr_link} ({commit['sha']})")
            lines.append("")
        
        if refactors:
            lines.append("### ♻️ Refactoring")
            for commit in refactors:
                pr_match = re.search(r'#(\d+)', commit['subject'])
                pr_link = f" (#{pr_match.group(1)})" if pr_match else ""
                subject = re.sub(r'^(?:refactor|perf)(?:\([^)]+\))?: ', '', commit['subject'])
                subject = re.sub(r' \(#\d+\)$', '', subject)
                lines.append(f"- {subject}{pr_link} ({commit['sha']})")
            lines.append("")
        
        if docs:
            lines.append("### 📚 Documentation")
            for commit in docs:
                subject = re.sub(r'^docs(?:\([^)]+\))?: ', '', commit['subject'])
                lines.append(f"- {subject} ({commit['sha']})")
            lines.append("")
        
        if tests:
            lines.append("### 🧪 Tests")
            for commit in tests:
                subject = re.sub(r'^test(?:\([^)]+\))?: ', '', commit['subject'])
                lines.append(f"- {subject} ({commit['sha']})")
            lines.append("")
        
        if chores:
            lines.append("### 🔧 Chores")
            for commit in chores:
                subject = re.sub(r'^(?:chore|build|ci)(?:\([^)]+\))?: ', '', commit['subject'])
                lines.append(f"- {subject} ({commit['sha']})")
            lines.append("")
        
        if contributors:
            lines.append("### 👥 Contributors")
            for contributor in contributors:
                lines.append(f"- @{contributor}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def update_changelog(self, new_section: str):
        """Prepend new section to CHANGELOG.md."""
        if self.changelog_file.exists():
            existing = self.changelog_file.read_text()
        else:
            existing = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
        
        # Find where to insert (after header)
        header_end = existing.find('\n\n') + 2
        updated = existing[:header_end] + new_section + '\n' + existing[header_end:]
        
        self.changelog_file.write_text(updated)
    
    def update_version_file(self, version: str):
        """Update VERSION file."""
        self.version_file.write_text(f"{version}\n")
    
    def update_python_version(self, version: str):
        """Update Python package version."""
        version_py = self.repo_root / 'lib' / '__version__.py'
        content = f'__version__ = "{version}"\n'
        version_py.write_text(content)
    
    def commit_version_bump(self, version: str):
        """Commit version bump changes."""
        subprocess.run(['git', 'add', str(self.version_file)], check=True)
        subprocess.run(['git', 'add', str(self.changelog_file)], check=True)
        subprocess.run(['git', 'add', 'lib/__version__.py'], check=True)
        
        subprocess.run([
            'git', 'commit', '-m',
            f"chore: bump version to {version}\n\n[skip ci]"
        ], check=True)
    
    def create_tag(self, version: str):
        """Create and push git tag."""
        tag = f"v{version}"
        
        # Create annotated tag
        subprocess.run([
            'git', 'tag', '-a', tag,
            '-m', f"Release {tag}"
        ], check=True)
        
        return tag
    
    def push_changes(self, tag: str):
        """Push commits and tags."""
        subprocess.run(['git', 'push'], check=True)
        subprocess.run(['git', 'push', 'origin', tag], check=True)
    
    def run(self, bump_type: str = None, auto: bool = False, dry_run: bool = False):
        """Execute version bump workflow."""
        print("🔍 Analyzing repository...")
        
        # Get current version
        current_version = self.get_current_version()
        print(f"Current version: {current_version}")
        
        # Get commits since last tag
        last_tag = self.get_last_tag()
        if last_tag:
            print(f"Last tag: {last_tag}")
            commits = self.get_commits_since_tag(last_tag)
        else:
            print("No previous tags found")
            commits = self.get_commits_since_tag()
        
        print(f"Commits since last release: {len(commits)}")
        
        if not commits:
            print("⚠️  No new commits since last release")
            return
        
        # Determine bump type
        if auto:
            bump_type = self.auto_determine_bump_type(commits)
            print(f"Auto-determined bump type: {bump_type}")
        elif not bump_type:
            print("❌ Error: Must specify --bump or --auto")
            sys.exit(1)
        
        # Calculate new version
        new_version = self.bump_version(current_version, bump_type)
        print(f"\n📦 New version: {new_version}")
        
        # Generate changelog section
        changelog_section = self.generate_changelog_section(commits, new_version)
        
        print("\n📝 Changelog preview:")
        print("─" * 60)
        print(changelog_section)
        print("─" * 60)
        
        if dry_run:
            print("\n✅ Dry run complete (no changes made)")
            return
        
        # Confirm
        response = input("\nProceed with version bump? [y/N]: ")
        if response.lower() != 'y':
            print("❌ Aborted")
            return
        
        # Update files
        print("\n📝 Updating version files...")
        self.update_version_file(new_version)
        self.update_python_version(new_version)
        self.update_changelog(changelog_section)
        
        # Commit changes
        print("💾 Committing changes...")
        self.commit_version_bump(new_version)
        
        # Create tag
        print("🏷️  Creating tag...")
        tag = self.create_tag(new_version)
        
        # Push
        print("📤 Pushing changes and tag...")
        self.push_changes(tag)
        
        print(f"\n✅ Version bumped to {new_version}")
        print(f"🏷️  Tag created: {tag}")
        print(f"🚀 Production deployment will trigger automatically")


def main():
    parser = argparse.ArgumentParser(description='Bump version and generate changelog')
    parser.add_argument(
        '--bump',
        choices=['major', 'minor', 'patch'],
        help='Version bump type'
    )
    parser.add_argument(
        '--auto',
        action='store_true',
        help='Auto-determine bump type from commits'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without modifying anything'
    )
    
    args = parser.parse_args()
    
    if not args.bump and not args.auto:
        parser.error("Must specify either --bump or --auto")
    
    bumper = VersionBumper()
    bumper.run(bump_type=args.bump, auto=args.auto, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
```

### .github/workflows/release.yml

```yaml
name: Create Release

on:
  workflow_dispatch:
    inputs:
      bump_type:
        description: 'Version bump type'
        required: true
        type: choice
        options:
          - patch
          - minor
          - major
          - auto
      dry_run:
        description: 'Dry run (preview only)'
        required: false
        type: boolean
        default: false

permissions:
  contents: write
  pull-requests: read

jobs:
  release:
    name: Create Release
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Need full history for changelog
          token: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Configure Git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Bump version
        id: bump
        run: |
          chmod +x scripts/bump_version.py
          
          if [ "${{ inputs.dry_run }}" = "true" ]; then
            python scripts/bump_version.py --${{ inputs.bump_type }} --dry-run
          else
            python scripts/bump_version.py --${{ inputs.bump_type }}
          fi
          
          # Get new version
          NEW_VERSION=$(cat VERSION)
          echo "version=$NEW_VERSION" >> $GITHUB_OUTPUT
      
      - name: Extract changelog section
        id: changelog
        if: ${{ !inputs.dry_run }}
        run: |
          # Extract the first release section from CHANGELOG.md
          awk '/^## \[/{p++} p==1' CHANGELOG.md | head -n -1 > /tmp/release-notes.md
          
          # Set output
          echo "notes<<EOF" >> $GITHUB_OUTPUT
          cat /tmp/release-notes.md >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
      
      - name: Create GitHub Release
        if: ${{ !inputs.dry_run }}
        uses: actions/github-script@v7
        env:
          VERSION: ${{ steps.bump.outputs.version }}
        with:
          script: |
            const fs = require('fs');
            const version = process.env.VERSION;
            const releaseNotes = fs.readFileSync('/tmp/release-notes.md', 'utf8');
            
            const { data: release } = await github.rest.repos.createRelease({
              owner: context.repo.owner,
              repo: context.repo.repo,
              tag_name: `v${version}`,
              name: `Release v${version}`,
              body: releaseNotes,
              draft: false,
              prerelease: false
            });
            
            console.log(`Release created: ${release.html_url}`);
      
      - name: Trigger production deployment
        if: ${{ !inputs.dry_run }}
        run: |
          echo "✅ Release created successfully"
          echo "🚀 Production deployment will trigger automatically from tag"
```

### Create VERSION and __version__.py files

```bash
# VERSION file
echo "0.1.0" > VERSION

# lib/__version__.py
cat > lib/__version__.py << 'EOF'
__version__ = "0.1.0"
EOF

# Initial CHANGELOG.md
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

EOF
```

## Implementation Steps

### Step 1: Create Version Files

```bash
# Create VERSION file
echo "0.1.0" > VERSION

# Create Python version file
mkdir -p lib
echo '__version__ = "0.1.0"' > lib/__version__.py

# Create initial changelog
cat > CHANGELOG.md << 'EOF'
# Changelog

All notable changes to this project will be documented in this file.

EOF

# Commit initial version files
git add VERSION lib/__version__.py CHANGELOG.md
git commit -m "chore: add version tracking files"
```

### Step 2: Create Version Bump Script

```bash
# Create script
touch scripts/bump_version.py
chmod +x scripts/bump_version.py

# Add content (from above)

# Test dry run
python scripts/bump_version.py --auto --dry-run
```

### Step 3: Create Release Workflow

```bash
# Create workflow file
touch .github/workflows/release.yml

# Add content (from above)

# Commit workflow
git add .github/workflows/release.yml scripts/bump_version.py
git commit -m "feat: add release automation workflow"
```

### Step 4: Update Production Workflow

Modify `.github/workflows/prod-deploy.yml` to trigger on tags:

```yaml
on:
  push:
    tags:
      - 'v*.*.*'
```

### Step 5: Test Release Process

```bash
# Method 1: Local test
python scripts/bump_version.py --bump patch --dry-run

# Method 2: Workflow test
1. Go to Actions > Create Release
2. Select bump type: patch
3. Enable dry run
4. Run workflow
5. Review output
```

### Step 6: Create First Release

```bash
# Via workflow (recommended)
1. Go to Actions > Create Release
2. Select bump type (patch/minor/major)
3. Disable dry run
4. Run workflow
5. Review created release

# Via local script
python scripts/bump_version.py --auto
# Follow prompts
```

## Validation Checklist

- [ ] VERSION file created in repo root
- [ ] `lib/__version__.py` created
- [ ] CHANGELOG.md initialized
- [ ] `bump_version.py` script created and executable
- [ ] Release workflow created
- [ ] Production workflow triggers on tags
- [ ] Script parses conventional commits
- [ ] Changelog groups commits by type
- [ ] Contributors list generated
- [ ] GitHub release created with notes
- [ ] Tag pushed to repository
- [ ] Production deployment triggers from tag

## Testing Strategy

### Test 1: Dry Run

**Steps:**
1. Run `python scripts/bump_version.py --auto --dry-run`
2. Review output

**Expected:**
- Current version displayed
- Commits analyzed
- Bump type determined
- New version calculated
- Changelog preview shown
- No files modified
- No commits created

### Test 2: Patch Release

**Steps:**
1. Make a bug fix commit
2. Run `python scripts/bump_version.py --bump patch`
3. Review and confirm

**Expected:**
- Version bumps from 0.1.0 to 0.1.1
- CHANGELOG.md updated with fix
- VERSION file updated
- `__version__.py` updated
- Commit created
- Tag created and pushed
- GitHub release created

### Test 3: Minor Release

**Steps:**
1. Make a feature commit
2. Run `python scripts/bump_version.py --bump minor`

**Expected:**
- Version bumps from 0.1.1 to 0.2.0
- Feature listed in changelog
- All files updated
- Production deployment triggers

### Test 4: Auto-Detect

**Steps:**
1. Make multiple commits (feat, fix, docs)
2. Run `python scripts/bump_version.py --auto`

**Expected:**
- Detects feature commits
- Chooses minor bump
- Groups commits by type
- Changelog well-formatted

### Test 5: Workflow Release

**Steps:**
1. Go to Actions > Create Release
2. Choose bump type
3. Run workflow

**Expected:**
- Workflow runs successfully
- Version bumped
- Changelog updated
- GitHub release created
- Production deployment triggered

## Changelog Format Examples

### Feature Release

```markdown
## [0.2.0] - 2024-11-12

### ✨ Features
- Add CI/CD pipeline (#45) (abc1234)
- Add deployment automation (#46) (def5678)

### 🐛 Bug Fixes
- Fix database timeout (#44) (ghi9012)

### 👥 Contributors
- @developer1
- @developer2
```

### Bug Fix Release

```markdown
## [1.0.1] - 2024-11-12

### 🐛 Bug Fixes
- Fix memory leak in connection handler (abc1234)
- Fix race condition in shutdown (def5678)

### 👥 Contributors
- @developer1
```

### Major Release

```markdown
## [0.2.0] - 2024-11-12

### ⚠️ BREAKING CHANGES
- Database schema updated - migration required
- Configuration format changed

### ✨ Features
- Complete rewrite of core engine (#50)
- Add plugin system (#51)

### 👥 Contributors
- @developer1
- @developer2
- @developer3
```

## Commit Message Conventions

### Supported Types

```bash
feat: new feature (MINOR)
fix: bug fix (PATCH)
docs: documentation (PATCH)
refactor: code refactoring (MINOR)
perf: performance improvement (MINOR)
test: add tests (PATCH)
chore: maintenance (PATCH)
build: build system (PATCH)
ci: CI configuration (PATCH)
```

### Examples

```bash
# Feature (minor bump)
feat: add deployment verification
feat(bot): add command cooldown system

# Fix (patch bump)
fix: resolve connection timeout
fix(db): prevent race condition in queries

# Breaking change (major bump)
feat!: redesign configuration format
feat: redesign API
BREAKING CHANGE: API endpoints changed

# Multiple scopes
fix(bot,db): resolve connection issues
```

## Version Rollback

### Rollback to Previous Version

```bash
# Find previous version
git tag -l | tail -5

# Rollback to specific version
git checkout v1.0.0

# Deploy previous version
./scripts/deploy.sh prod

# Or create new tag from old commit
git tag -a v1.0.2 <old-commit-sha>
git push origin v1.0.2
```

## Integration with Production Deployment

### Tag-Based Deployment

When a tag is pushed:

1. `.github/workflows/prod-deploy.yml` triggered
2. Quality gates run
3. Approval gate appears
4. After approval, deployment proceeds
5. GitHub release provides changelog

### Manual Deployment Selection

In production workflow, can specify tag:

```yaml
workflow_dispatch:
  inputs:
    version:
      description: 'Version tag to deploy (e.g., v1.2.3)'
      required: false
```

## Troubleshooting

### Changelog Empty or Incomplete

**Possible Causes:**
1. Commits don't follow conventional format
2. No commits since last tag
3. Parsing regex incorrect

**Solutions:**
1. Use conventional commit messages
2. Check `git log` since last tag
3. Update commit type regex

### Version Bump Failed

**Possible Causes:**
1. No VERSION file
2. Invalid version format
3. Git conflicts

**Solutions:**
1. Create VERSION file
2. Verify current version format
3. Resolve conflicts and retry

### Tag Already Exists

**Possible Causes:**
1. Tag already created
2. Version not incremented

**Solutions:**
1. Delete tag: `git tag -d v1.2.3`
2. Push deletion: `git push origin :refs/tags/v1.2.3`
3. Create new tag

### GitHub Release Not Created

**Possible Causes:**
1. Missing permissions
2. Tag not pushed
3. API error

**Solutions:**
1. Verify `contents: write` permission
2. Check tag exists: `git ls-remote --tags`
3. Check workflow logs for errors

## Commit Message

```bash
git add scripts/bump_version.py
git add .github/workflows/release.yml
git add VERSION lib/__version__.py CHANGELOG.md
git commit -m "feat: add automated release management

Automated version bumping, changelog generation, and releases.

scripts/bump_version.py:
- Analyze commits since last tag
- Auto-determine version bump type
- Generate formatted changelog
- Update VERSION and __version__.py files
- Create git tag with release notes
- Push changes and tags

.github/workflows/release.yml:
- Manual workflow dispatch
- Bump type selection (major/minor/patch/auto)
- Dry run mode for testing
- Automatic changelog extraction
- GitHub release creation
- Triggers production deployment

Version Management:
- Semantic versioning (MAJOR.MINOR.PATCH)
- Conventional commit parsing
- Automatic bump type detection
- VERSION file in repo root
- Python package version sync

Changelog Generation:
- Groups commits by type
- Extracts PR numbers
- Lists contributors
- Formatted with emojis
- Follows Keep a Changelog format

Commit Type Categories:
- ✨ Features (feat:)
- 🐛 Bug Fixes (fix:)
- ♻️ Refactoring (refactor:, perf:)
- 📚 Documentation (docs:)
- 🧪 Tests (test:)
- 🔧 Chores (chore:, build:, ci:)

Version Bump Rules:
- MAJOR: Breaking changes
- MINOR: New features
- PATCH: Bug fixes

Features:
- Dry run mode for preview
- Interactive confirmation
- Colored terminal output
- Conventional commit parsing
- PR linking in changelog
- Contributor attribution
- Tag-based deployment trigger

Benefits:
- Consistent versioning
- Automated changelog
- Clear release history
- Easy rollback targeting
- Professional release notes
- Reduced manual work

This provides professional release management with automated
changelog generation and version tracking.

SPEC: Sortie 8 - Release Automation"
```

## Related Documentation

- **Sortie 7:** Production Deploy Workflow (triggered by tags)
- **GitHub Releases:** Release creation and management
- **Conventional Commits:** Commit message format
- **Semantic Versioning:** Version numbering standard

## Next Sortie

**Sortie 9: Production Verification** - Enhanced verification for production deployments with stricter thresholds and additional checks.

---

**Implementation Time Estimate:** 4-5 hours  
**Risk Level:** Low (no production impact, well-tested process)  
**Priority:** High (enables professional release management)  
**Dependencies:** Sortie 7 complete
