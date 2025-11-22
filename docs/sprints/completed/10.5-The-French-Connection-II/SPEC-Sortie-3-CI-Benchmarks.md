# Technical Specification: CI Benchmark Integration

**Sprint**: Sprint 10.5 "The French Connection II"  
**Sortie**: 3 of 4  
**Estimated Effort**: 1 hour  
**Dependencies**: Sprint 10 Sortie 4 (benchmark infrastructure)  

---

## Overview

Integrate performance benchmarks into GitHub Actions CI to track performance over time and catch regressions. Benchmarks run on PR + weekly schedule, with results saved as artifacts.

---

## Implementation

### 1. Create Benchmark Workflow

**File**: `.github/workflows/benchmarks.yml` (NEW)

```yaml
name: Performance Benchmarks

on:
  pull_request:
    paths:
      - 'common/**'
      - 'lib/**'
      - 'tests/performance/**'
      - '.github/workflows/benchmarks.yml'
  schedule:
    # Run weekly on Sunday at 3am UTC
    - cron: '0 3 * * 0'
  workflow_dispatch:
    # Allow manual trigger

permissions:
  contents: read
  pull-requests: write  # For PR comments

jobs:
  benchmark:
    name: Run Performance Benchmarks
    runs-on: ubuntu-latest
    timeout-minutes: 10
    
    services:
      nats:
        image: nats:2.10-alpine
        ports:
          - 4222:4222
        options: >-
          --health-cmd "wget --no-verbose --tries=1 --spider http://localhost:8222/healthz || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run benchmarks
        run: |
          pytest tests/performance/test_nats_overhead.py \
            --json-report \
            --json-report-file=benchmark_results.json \
            --json-report-indent=2 \
            -v
        env:
          NATS_URL: nats://localhost:4222
        continue-on-error: true  # Don't fail workflow if benchmarks fail
      
      - name: Generate report
        if: always()
        run: |
          python tests/performance/generate_report.py benchmark_results.json
      
      - name: Upload benchmark results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: benchmark-results-${{ github.sha }}
          path: |
            benchmark_results.json
            tests/performance/BENCHMARK_RESULTS.md
          retention-days: 90
      
      - name: Comment PR with results
        if: github.event_name == 'pull_request' && always()
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const reportPath = 'tests/performance/BENCHMARK_RESULTS.md';
            
            if (!fs.existsSync(reportPath)) {
              console.log('No benchmark report found');
              return;
            }
            
            const report = fs.readFileSync(reportPath, 'utf8');
            
            // Truncate if too long (GitHub comment limit)
            const maxLength = 65000;
            const summary = report.length > maxLength 
              ? report.substring(0, maxLength) + '\n\n... (truncated)'
              : report;
            
            // Find existing comment
            const comments = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });
            
            const botComment = comments.data.find(c => 
              c.user.login === 'github-actions[bot]' && 
              c.body.includes('## Performance Benchmark Results')
            );
            
            const commentBody = `## Performance Benchmark Results\n\n${summary}\n\n---\n*Benchmark run: ${context.sha}*`;
            
            if (botComment) {
              // Update existing comment
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: botComment.id,
                body: commentBody,
              });
            } else {
              // Create new comment
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body: commentBody,
              });
            }
```

---

### 2. Update Benchmark Report Generator

**File**: `tests/performance/generate_report.py`  
**Line**: ~350 (end of `generate_markdown_report()`)

Add CI-specific formatting:

```python
def generate_markdown_report(results: dict, output_path: str) -> None:
    """Generate markdown report from benchmark results."""
    # ... existing code ...
    
    # Add CI summary at end
    if os.getenv('GITHUB_ACTIONS') == 'true':
        report_lines.append('\n---\n')
        report_lines.append('## CI Information\n\n')
        report_lines.append(f"- **Run ID**: {os.getenv('GITHUB_RUN_ID', 'N/A')}\n")
        report_lines.append(f"- **Commit**: {os.getenv('GITHUB_SHA', 'N/A')[:7]}\n")
        report_lines.append(f"- **Branch**: {os.getenv('GITHUB_REF_NAME', 'N/A')}\n")
        report_lines.append(f"- **Triggered by**: {os.getenv('GITHUB_EVENT_NAME', 'N/A')}\n")
    
    # Write report
    with open(output_path, 'w') as f:
        f.writelines(report_lines)
```

---

## Testing

### 1. Test Workflow Locally (with act)

```bash
# Install act (GitHub Actions local runner)
# https://github.com/nektos/act

# Run benchmark workflow
act workflow_dispatch -W .github/workflows/benchmarks.yml
```

---

### 2. Test on GitHub (Manual Dispatch)

1. Push workflow file to branch
2. Go to GitHub Actions tab
3. Select "Performance Benchmarks" workflow
4. Click "Run workflow" → select branch → "Run workflow"
5. Verify:
   - Workflow completes (may have failing benchmarks - OK)
   - Artifacts uploaded (benchmark_results.json + BENCHMARK_RESULTS.md)
   - Results viewable in GitHub UI

---

### 3. Test PR Comment

1. Create PR with benchmark changes
2. Verify workflow runs automatically
3. Check PR for comment with benchmark results
4. Update PR, verify comment updates (not duplicates)

---

## Acceptance Criteria

- [ ] `.github/workflows/benchmarks.yml` created
- [ ] Workflow runs on PR (when performance code changes)
- [ ] Workflow runs weekly (Sunday 3am UTC)
- [ ] Workflow can be manually triggered
- [ ] NATS service starts correctly in CI
- [ ] Benchmarks run (even if some fail)
- [ ] Artifacts uploaded (JSON + markdown)
- [ ] PR comment posted with results
- [ ] Workflow doesn't block PR merge (informational only)
- [ ] 90-day artifact retention configured

---

## Success Metrics

**Before Sortie 3**:
- Benchmark visibility: Manual runs only
- Regression detection: None
- Historical tracking: None

**After Sortie 3**:
- Benchmark visibility: Automatic on every PR
- Regression detection: Weekly baseline checks
- Historical tracking: 90 days of artifacts

---

**Estimated Time**: 1 hour  
**Files Changed**: 2 (benchmarks.yml, generate_report.py)  
**Lines Added**: ~130
