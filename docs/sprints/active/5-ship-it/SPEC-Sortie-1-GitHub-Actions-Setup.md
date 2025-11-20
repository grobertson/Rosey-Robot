# SPEC: Sortie 1 - GitHub Actions Setup

**Sprint:** 5 (ship-it)  
**Sortie:** 1 of 12  
**Status:** Ready for Implementation  
**Depends On:** Sprint 4 (Test Coverage)

---

## Objective

Set up GitHub Actions workflows for continuous integration, including linting and testing. This establishes the foundation for automated quality gates before deployment.

## Success Criteria

- ✅ `.github/workflows/` directory created
- ✅ `lint.yml` workflow runs ruff and mypy
- ✅ `test.yml` workflow runs pytest with coverage
- ✅ Python 3.11 configured with dependency caching
- ✅ Workflows trigger on pull requests and pushes
- ✅ All workflows pass on clean branch

## Technical Specification

### File Structure
```
.github/
  workflows/
    lint.yml        # Code quality checks
    test.yml        # Test suite execution
```

### Workflow: lint.yml

**Purpose:** Fast feedback on code quality (linting and type checking)

**Triggers:**
- `pull_request` (opened, synchronize, reopened)
- `push` to main branch

**Jobs:**
1. **Lint Job**
   - Checkout code
   - Setup Python 3.11
   - Install dependencies (requirements.txt)
   - Run `ruff check .`
   - Fail if linting errors found

2. **Type Check Job**
   - Checkout code
   - Setup Python 3.11
   - Install dependencies
   - Run `mypy lib/ common/ bots/`
   - Fail if type errors found

**Performance:** Target < 2 minutes total

### Workflow: test.yml

**Purpose:** Run full test suite with coverage reporting

**Triggers:**
- `pull_request` (opened, synchronize, reopened)
- `push` to main branch

**Jobs:**
1. **Test Job**
   - Checkout code
   - Setup Python 3.11
   - Cache pip dependencies
   - Install dependencies (requirements.txt)
   - Run `pytest --cov --cov-report=term --cov-report=xml`
   - Require 85% coverage minimum (66% floor)
   - Upload coverage report artifact
   - Fail if tests fail or coverage below minimum

**Performance:** Target < 3 minutes total

### Dependency Caching Strategy

```yaml
- name: Cache pip packages
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
    restore-keys: |
      ${{ runner.os }}-pip-
```

### Python Setup

```yaml
- name: Set up Python 3.11
  uses: actions/setup-python@v4
  with:
    python-version: '3.11'
    cache: 'pip'
```

## Implementation Steps

### Step 1: Create Workflow Directory
```bash
mkdir -p .github/workflows
```

### Step 2: Create lint.yml

```yaml
name: Lint

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches: [main]

jobs:
  lint:
    name: Lint with ruff
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Lint with ruff
        run: ruff check .

  typecheck:
    name: Type check with mypy
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Type check with mypy
        run: mypy lib/ common/ bots/ --ignore-missing-imports
```

### Step 3: Create test.yml

```yaml
name: Test

on:
  pull_request:
    types: [opened, synchronize, reopened]
  push:
    branches: [main]

jobs:
  test:
    name: Test with pytest
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run tests with coverage
        run: |
          pytest --cov --cov-report=term --cov-report=xml --cov-fail-under=66
      
      - name: Upload coverage report
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: coverage-report
          path: coverage.xml
```

### Step 4: Test Workflows Locally (Optional)

Use [act](https://github.com/nektos/act) to test workflows locally:
```bash
# Install act (if available)
act pull_request --workflows .github/workflows/lint.yml
act pull_request --workflows .github/workflows/test.yml
```

### Step 5: Commit and Push

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflows for lint and test

Added foundational CI workflows for continuous integration.

.github/workflows/lint.yml:
- Run ruff for code linting
- Run mypy for type checking
- Parallel jobs for fast feedback
- Trigger on PR and push to main

.github/workflows/test.yml:
- Run full pytest suite (567 tests)
- Generate coverage report (require 85%+)
- Upload coverage artifact
- Fail on coverage below 66% floor

Configuration:
- Python 3.11 on ubuntu-latest
- Pip dependency caching for performance
- Target < 5 minutes total CI time

This establishes quality gates for all future changes.

SPEC: Sortie 1 - GitHub Actions Setup"

git push -u origin nano-sprint/5-ship-it
```

### Step 6: Verify Workflows

1. Create a test PR (or push to branch)
2. Navigate to Actions tab in GitHub
3. Verify both workflows trigger
4. Verify both workflows pass
5. Check execution time (should be < 5 minutes combined)

## Validation Checklist

- [ ] `.github/workflows/lint.yml` exists
- [ ] `.github/workflows/test.yml` exists
- [ ] Both workflows have proper triggers
- [ ] Python 3.11 configured correctly
- [ ] Dependencies cached for performance
- [ ] Ruff lint job passes
- [ ] Mypy type check job passes
- [ ] Pytest test job passes
- [ ] Coverage report generated
- [ ] Coverage meets 66% minimum
- [ ] Total CI time < 5 minutes
- [ ] Workflows visible in GitHub Actions tab

## Dependencies

### Required Tools
- GitHub Actions (free tier)
- Python 3.11
- ruff (in requirements.txt)
- mypy (in requirements.txt)
- pytest, pytest-cov (in requirements.txt)

### Environment
- Ubuntu latest runner
- No secrets required for this sortie

## Testing Strategy

### Test the Lint Workflow
1. Introduce intentional lint error (e.g., unused import)
2. Push to branch
3. Verify lint workflow fails
4. Fix lint error
5. Verify lint workflow passes

### Test the Test Workflow
1. Introduce failing test
2. Push to branch
3. Verify test workflow fails
4. Fix test
5. Verify test workflow passes

### Test Coverage Gate
1. Comment out tests to reduce coverage
2. Push to branch
3. Verify test workflow fails due to coverage
4. Restore tests
5. Verify test workflow passes

## Performance Targets

| Workflow | Target Time | Max Time |
|----------|-------------|----------|
| lint.yml | < 2 minutes | 3 minutes |
| test.yml | < 3 minutes | 5 minutes |
| **Total** | **< 5 minutes** | **8 minutes** |

## Rollback Plan

If workflows fail unexpectedly:
1. Check workflow logs in GitHub Actions
2. Fix configuration errors
3. Test locally if possible (using act)
4. Push fix
5. If unfixable, revert sortie: `git revert HEAD`

## Success Metrics

- ✅ Lint workflow execution time: < 2 minutes
- ✅ Test workflow execution time: < 3 minutes
- ✅ All 567 tests pass
- ✅ Coverage > 85% (66% minimum enforced)
- ✅ Zero linting errors
- ✅ Zero type errors

## Notes

- GitHub Actions free tier: 2,000 minutes/month (sufficient)
- Workflows run in parallel by default
- Caching reduces execution time by ~30-50%
- Both workflows must pass for PR merge protection (configured later)

## Next Sortie

**Sortie 2: Configuration Management** - Create separate test/prod configurations with secrets management.

---

**Implementation Time Estimate:** 2-3 hours  
**Risk Level:** Low  
**Priority:** High (foundation for all CI/CD)
