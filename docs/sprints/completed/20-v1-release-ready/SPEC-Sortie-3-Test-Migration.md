# SPEC: Sortie 3 - Test Migration

**Sprint:** 20 - Release Ready v1.0  
**Sortie:** 3 of 5  
**Status:** Ready  
**Estimated Duration:** 5 days (Week 2)  
**Created:** November 26, 2025  

---

## Objective

Migrate test suite from testing lib/ internals to testing NATS interfaces. Preserve 201 working plugin tests, write 300 new NATS interface tests, and establish CI/CD pipeline. Total: 500-800 focused tests replacing 2000 scattered tests.

---

## Context

**Starting Point** (Post-Sortie 2):
- v1 branch exists with working bot
- rosey.py orchestrator runs successfully
- Plugins load and respond via NATS
- Zero tests on v1 branch yet

**Test Architecture Change**:
```
Sprint 19 (broken):
├── 201 plugin tests (WORKING - test NATS interfaces)
└── 1800 lib/ tests (BROKEN - test wrong architecture)

v1.0 (target):
├── 201 plugin tests (MIGRATED - already correct)
├── 300 interface tests (NEW - test NATS contracts)
└── 100 core unit tests (NEW - test core components)
Total: 500-800 focused tests
```

**Key Principle**: Test architectural boundaries (NATS subjects/messages), not implementation details.

---

## Success Criteria

### Deliverables
- [ ] 201 plugin tests migrated and passing
- [ ] 300 NATS interface tests written and passing
- [ ] 100 core unit tests written and passing
- [ ] Total: 500-800 tests all green
- [ ] Test coverage: 75%+ overall, 80%+ plugin interfaces
- [ ] CI/CD pipeline established and green
- [ ] pytest configuration complete

### Quality Gates
- Zero imports from `lib/` in any test
- All tests test NATS interfaces or core components
- Plugin tests pass at same 96%+ rate
- Interface tests cover all critical NATS subjects
- CI passes 3 consecutive times
- Coverage reports generated automatically

---

## Scope

### In Scope
- Copy 201 working plugin tests from Sprint 19
- Fix any broken imports (lib. → core. or common.)
- Write 300 NATS interface tests (chat, commands, events)
- Write 100 core unit tests (event_bus, plugin_manager, etc.)
- Setup pytest configuration
- Establish GitHub Actions CI/CD
- Coverage reporting (pytest-cov)

### Out of Scope
- Testing implementation details (that's overspecification)
- 100% code coverage (target: 75%+, focus on interfaces)
- Performance testing (defer to v1.1+)
- Load testing (defer to v1.1+)
- Integration with external services (mock in tests)

---

## Requirements

### Functional Requirements

**FR1: Plugin Tests Migration**
- Copy `tests/plugins/` directory from Sprint 19
- Fix imports: `from lib.` → `from core.` or `from common.`
- Update fixtures as needed
- Verify 201+ tests pass
- Maintain 96%+ pass rate

**FR2: NATS Interface Tests**
Write 300 tests covering:
- Chat message flow (100 tests)
  - Chat message broadcast
  - Username handling
  - Message filtering
  - Error handling
- Command routing (100 tests)
  - Command detection
  - Command parsing
  - Command dispatch
  - Response handling
- Plugin communication (50 tests)
  - Plugin registration
  - Plugin events
  - Plugin queries
  - Plugin errors
- CyTube integration (50 tests)
  - Connection events
  - User events
  - Media events
  - Error events

**FR3: Core Unit Tests**
Write 100 tests covering:
- EventBus (25 tests)
  - Subject registration
  - Message publishing
  - Message subscription
  - Error handling
- PluginManager (25 tests)
  - Plugin discovery
  - Plugin loading
  - Plugin unloading
  - Error isolation
- CommandRouter (25 tests)
  - Route registration
  - Route matching
  - Route dispatch
  - Error handling
- CyTubeConnector (25 tests)
  - Connection lifecycle
  - Message parsing
  - Event publishing
  - Reconnection logic

**FR4: CI/CD Pipeline**
- GitHub Actions workflow
- Run on push and PR
- Python 3.12
- pytest with coverage
- Fail if coverage <75%
- Badge in README.md

### Non-Functional Requirements

**NFR1: Test Speed**
- Full test suite runs in <5 minutes
- Interface tests use mocks (no real NATS)
- Plugin tests isolated (no shared state)

**NFR2: Test Clarity**
- Each test tests ONE thing
- Clear test names describe what's tested
- Fixtures reusable across tests
- Minimal test code duplication

**NFR3: Maintainability**
- Tests organized by component
- Fixtures in conftest.py
- Test utilities in tests/utils.py
- Documentation for test patterns

---

## Design

### Test Directory Structure

```
tests/
├── conftest.py              # Shared fixtures (NATS mock, bot fixture, etc.)
├── utils.py                 # Test utilities (helpers, assertions)
├── integration/             # NATS interface tests (300 tests)
│   ├── test_chat_flow.py    # Chat message tests (100)
│   ├── test_commands.py     # Command routing tests (100)
│   ├── test_plugins.py      # Plugin communication tests (50)
│   └── test_cytube.py       # CyTube integration tests (50)
├── unit/                    # Core component tests (100 tests)
│   ├── test_event_bus.py    # EventBus tests (25)
│   ├── test_plugin_manager.py  # PluginManager tests (25)
│   ├── test_router.py       # CommandRouter tests (25)
│   └── test_cytube_connector.py  # CyTubeConnector tests (25)
└── plugins/                 # Plugin tests (201+ tests, from Sprint 19)
    ├── test_playlist.py
    ├── test_llm.py
    ├── test_trivia.py
    └── ... (all plugin tests)
```

### NATS Interface Test Pattern

**Template** (test NATS message contracts):
```python
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
import nats

from core.event_bus import EventBus


@pytest.fixture
async def mock_nats():
    """Mock NATS connection for testing."""
    nc = AsyncMock(spec=nats.NATS)
    nc.subscribe = AsyncMock()
    nc.publish = AsyncMock()
    nc.request = AsyncMock()
    return nc


@pytest.mark.asyncio
async def test_chat_message_broadcast(mock_nats):
    """Chat messages are broadcast on chat.message subject."""
    # Setup
    event_bus = EventBus(mock_nats)
    
    # Capture published messages
    published = []
    async def capture_publish(subject, data):
        published.append((subject, json.loads(data)))
    mock_nats.publish.side_effect = capture_publish
    
    # Act: Simulate CyTube chat event
    await event_bus.publish('cytube.chat', {
        'username': 'test_user',
        'msg': 'hello world',
        'time': 1234567890
    })
    
    # Assert: Message broadcast on chat.message
    assert len(published) == 1
    subject, data = published[0]
    assert subject == 'chat.message'
    assert data['username'] == 'test_user'
    assert data['msg'] == 'hello world'


@pytest.mark.asyncio
async def test_command_dispatch(mock_nats):
    """Commands are dispatched to command.{name} subjects."""
    from core.router import CommandRouter
    
    # Setup
    event_bus = EventBus(mock_nats)
    router = CommandRouter(mock_nats, event_bus)
    
    # Track command dispatch
    dispatched = []
    async def capture_request(subject, data, timeout):
        dispatched.append((subject, json.loads(data)))
        return MagicMock(data=json.dumps({'response': 'ok'}).encode())
    mock_nats.request.side_effect = capture_request
    
    # Act: Send command via NATS
    await event_bus.publish('chat.message', {
        'username': 'test_user',
        'msg': '!help',
    })
    
    await asyncio.sleep(0.1)  # Let router process
    
    # Assert: Command dispatched
    assert len(dispatched) == 1
    subject, data = dispatched[0]
    assert subject == 'command.help'
    assert data['username'] == 'test_user'
```

**Pattern Benefits**:
- Tests NATS contract (subjects, message format)
- Mocks NATS (fast, no server needed)
- Tests architectural boundaries (not internals)
- Catches breaking changes to message formats

### Core Unit Test Pattern

**Template** (test component logic):
```python
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from core.plugin_manager import PluginManager


@pytest.fixture
def mock_event_bus():
    """Mock EventBus for testing."""
    bus = AsyncMock()
    bus.subscribe = AsyncMock()
    bus.publish = AsyncMock()
    return bus


@pytest.mark.asyncio
async def test_plugin_discovery(mock_event_bus, tmp_path):
    """PluginManager discovers plugins in directory."""
    # Setup: Create fake plugin directory
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    
    # Create fake plugin
    plugin_dir = plugins_dir / "test_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text("""
from core.plugin import Plugin

class TestPlugin(Plugin):
    name = "test_plugin"
    
    async def load(self):
        pass
""")
    
    # Act
    nc = AsyncMock()
    manager = PluginManager(nc, mock_event_bus)
    await manager.load_all(plugins_dir)
    
    # Assert
    assert manager.count() == 1
    assert "test_plugin" in manager.list()


@pytest.mark.asyncio
async def test_plugin_load_error_isolated(mock_event_bus, tmp_path):
    """Plugin load errors don't crash PluginManager."""
    # Setup: Plugin that raises error on load
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    
    bad_plugin = plugins_dir / "bad_plugin"
    bad_plugin.mkdir()
    (bad_plugin / "__init__.py").write_text("""
class BadPlugin:
    async def load(self):
        raise RuntimeError("Plugin load failed!")
""")
    
    # Act
    nc = AsyncMock()
    manager = PluginManager(nc, mock_event_bus)
    
    # Should not raise
    await manager.load_all(plugins_dir)
    
    # Assert: Manager still functional
    assert manager.count() == 0  # Bad plugin not loaded
```

### CI/CD Workflow

**`.github/workflows/test.yml`**:
```yaml
name: Tests

on:
  push:
    branches: [v1, main]
  pull_request:
    branches: [v1, main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
      
      - name: Set up Python 3.12
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run tests with coverage
        run: |
          pytest tests/ \
            --cov=core \
            --cov=plugins \
            --cov=common \
            --cov=rosey \
            --cov-report=term \
            --cov-report=xml \
            --cov-fail-under=75
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
```

---

## Implementation Steps

### Day 1-2: Plugin Tests Migration (8 hours)

**Step 1.1: Copy Plugin Tests**
```powershell
# From Sprint 19 backup
cd ../Rosey-Robot-backup
git checkout nano-sprint/19-core-migration

# Copy plugin tests
cd ../Rosey-Robot  # v1 branch
mkdir tests
cp -r ../Rosey-Robot-backup/tests/plugins ./tests/plugins

# Verify
ls tests/plugins
# Should show: test_playlist.py, test_llm.py, test_trivia.py, etc.
```

**Step 1.2: Fix Imports**
```python
# In tests/plugins/*.py
# Find and replace:
# OLD: from lib.bot import Bot
# NEW: (remove - don't need Bot)

# OLD: from lib.playlist import Playlist
# NEW: (plugin tests don't import lib - they test NATS interfaces)

# OLD: from lib import X
# NEW: from core import X  (if needed)
#      or from common import X
```

**Step 1.3: Update Fixtures**
```python
# Create tests/conftest.py
"""Shared test fixtures for v1.0."""
import pytest
from unittest.mock import AsyncMock
import nats

@pytest.fixture
async def mock_nats():
    """Mock NATS connection."""
    nc = AsyncMock(spec=nats.NATS)
    nc.subscribe = AsyncMock()
    nc.publish = AsyncMock()
    nc.request = AsyncMock()
    return nc

@pytest.fixture
async def mock_event_bus(mock_nats):
    """Mock EventBus."""
    from core.event_bus import EventBus
    return EventBus(mock_nats)

# Add more shared fixtures as needed
```

**Step 1.4: Run Plugin Tests**
```powershell
pytest tests/plugins -v

# Expected: 201+ tests pass (96%+ rate)
# Fix any failures (likely import issues)
```

**Step 1.5: Commit Plugin Tests**
```powershell
git add tests/plugins tests/conftest.py
git commit -m "Migrate plugin tests from Sprint 19

Copy 201 working plugin tests:
- All plugins covered
- NATS interface tests (correct architecture)
- Fix imports: lib.* → core.* or common.*
- Update fixtures for v1.0

Test results: 201/209 passing (96% rate maintained)

Relates-to: Sprint 20 Sortie 3 (Test Migration)"

git push origin v1
```

### Day 2-3: NATS Interface Tests (10 hours)

**Step 2.1: Chat Flow Tests (100 tests)**
```python
# tests/integration/test_chat_flow.py
"""Test chat message flow via NATS."""

@pytest.mark.asyncio
async def test_chat_message_broadcast(mock_nats):
    """Chat messages broadcast on chat.message."""
    # ... (see design section)

@pytest.mark.asyncio
async def test_chat_message_username_extracted(mock_nats):
    """Chat messages extract username correctly."""
    # ...

@pytest.mark.asyncio
async def test_chat_message_filtered_for_bots(mock_nats):
    """Bot messages filtered (don't process own messages)."""
    # ...

# ... 97 more chat flow tests
```

**Step 2.2: Command Routing Tests (100 tests)**
```python
# tests/integration/test_commands.py
"""Test command routing via NATS."""

@pytest.mark.asyncio
async def test_command_detection(mock_nats):
    """Commands detected by ! prefix."""
    # ...

@pytest.mark.asyncio
async def test_command_parsing(mock_nats):
    """Command name and args parsed correctly."""
    # ...

@pytest.mark.asyncio
async def test_command_dispatch(mock_nats):
    """Commands dispatched to command.{name} subject."""
    # ...

# ... 97 more command tests
```

**Step 2.3: Plugin Communication Tests (50 tests)**
```python
# tests/integration/test_plugins.py
"""Test plugin communication via NATS."""

@pytest.mark.asyncio
async def test_plugin_registration(mock_nats):
    """Plugins register on plugin.register subject."""
    # ...

@pytest.mark.asyncio
async def test_plugin_event_handling(mock_nats):
    """Plugins receive events via subscriptions."""
    # ...

# ... 48 more plugin communication tests
```

**Step 2.4: CyTube Integration Tests (50 tests)**
```python
# tests/integration/test_cytube.py
"""Test CyTube integration via NATS."""

@pytest.mark.asyncio
async def test_cytube_connection_event(mock_nats):
    """CyTube connection publishes cytube.connected event."""
    # ...

@pytest.mark.asyncio
async def test_cytube_chat_event(mock_nats):
    """CyTube chat events published to cytube.chat."""
    # ...

# ... 48 more CyTube integration tests
```

**Step 2.5: Commit Interface Tests**
```powershell
git add tests/integration/
git commit -m "Add 300 NATS interface tests

Test architectural boundaries:
- Chat message flow (100 tests)
- Command routing (100 tests)
- Plugin communication (50 tests)
- CyTube integration (50 tests)

All tests use mocked NATS (fast, isolated)
All tests verify message contracts (subjects, formats)

Test coverage: 80%+ on plugin interfaces

Relates-to: Sprint 20 Sortie 3 (Test Migration)"

git push origin v1
```

### Day 4: Core Unit Tests (6 hours)

**Step 3.1: EventBus Tests (25 tests)**
```python
# tests/unit/test_event_bus.py
"""Test EventBus component."""

@pytest.mark.asyncio
async def test_event_bus_publish(mock_nats):
    """EventBus publishes messages to NATS."""
    # ...

# ... 24 more EventBus tests
```

**Step 3.2: PluginManager Tests (25 tests)**
```python
# tests/unit/test_plugin_manager.py
"""Test PluginManager component."""

@pytest.mark.asyncio
async def test_plugin_discovery(mock_event_bus, tmp_path):
    """PluginManager discovers plugins in directory."""
    # ... (see design section)

# ... 24 more PluginManager tests
```

**Step 3.3: CommandRouter Tests (25 tests)**
```python
# tests/unit/test_router.py
"""Test CommandRouter component."""

@pytest.mark.asyncio
async def test_router_route_registration(mock_nats, mock_event_bus):
    """CommandRouter registers routes."""
    # ...

# ... 24 more CommandRouter tests
```

**Step 3.4: CyTubeConnector Tests (25 tests)**
```python
# tests/unit/test_cytube_connector.py
"""Test CyTubeConnector component."""

@pytest.mark.asyncio
async def test_connector_connection(mock_nats, mock_event_bus):
    """CyTubeConnector establishes connection."""
    # ...

# ... 24 more CyTubeConnector tests
```

**Step 3.5: Commit Core Tests**
```powershell
git add tests/unit/
git commit -m "Add 100 core component unit tests

Test core infrastructure:
- EventBus (25 tests)
- PluginManager (25 tests)
- CommandRouter (25 tests)
- CyTubeConnector (25 tests)

Focus on component logic and error handling

Test coverage: 70%+ on core components

Relates-to: Sprint 20 Sortie 3 (Test Migration)"

git push origin v1
```

### Day 5: CI/CD & Coverage (6 hours)

**Step 4.1: Update pytest.ini**
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = 
    -v
    --strict-markers
    --tb=short
    --cov=core
    --cov=plugins
    --cov=common
    --cov=rosey
    --cov-report=term-missing
    --cov-report=html
    --cov-fail-under=75
markers =
    asyncio: mark test as async
    integration: mark test as integration test
    unit: mark test as unit test
    slow: mark test as slow running
```

**Step 4.2: Create CI Workflow**
```yaml
# .github/workflows/test.yml
# (see design section above)
```

**Step 4.3: Run Full Test Suite**
```powershell
pytest tests/ -v --cov

# Expected output:
# tests/plugins/test_*.py .............. (201 passed)
# tests/integration/test_*.py ........... (300 passed)
# tests/unit/test_*.py .................. (100 passed)
# 
# ----------- coverage: ----------- 
# core/event_bus.py              95%
# core/plugin_manager.py         82%
# core/router.py                 88%
# core/cytube_connector.py       79%
# plugins/*/plugin.py            85%
# common/*.py                    78%
# rosey.py                       60%
# TOTAL                          78%
```

**Step 4.4: Generate Coverage Reports**
```powershell
# HTML coverage report
pytest tests/ --cov --cov-report=html
start htmlcov/index.html  # View in browser

# Terminal coverage report
pytest tests/ --cov --cov-report=term-missing
```

**Step 4.5: Commit CI/CD**
```powershell
git add pytest.ini .github/workflows/test.yml
git commit -m "Establish CI/CD pipeline with coverage

GitHub Actions workflow:
- Run on push and PR
- Python 3.12
- Full test suite with coverage
- Fail if coverage <75%

Test results:
- 601 tests passing (201 plugin + 300 interface + 100 core)
- 78% overall coverage
- 80%+ coverage on plugin interfaces
- CI green ✓

Ready for production deployment

Relates-to: Sprint 20 Sortie 3 (Test Migration)"

git push origin v1
```

**Step 4.6: Verify CI Passes**
```powershell
# Check GitHub Actions
gh run list --branch v1

# Should show: ✓ Tests passing
```

---

## Testing Strategy

### Test Pyramid

```
        /\
       /  \  100 Core Unit Tests (test components)
      /____\
     /      \
    / 300    \ NATS Interface Tests (test contracts)
   /__________\
  /            \
 /   201 Plugin \ Plugin Tests (test features)
/________________\
```

**Philosophy**:
- More integration tests than typical (interface tests)
- Test architectural boundaries (NATS subjects)
- Plugin tests already exist and work
- Core tests ensure components function

### Coverage Strategy

**Targets**:
- Plugin interfaces: 80%+ (critical contracts)
- Core components: 70%+ (unit tests)
- Common utilities: 75%+ (database, config)
- Overall: 75%+ (realistic, focused)

**Not Targeted**:
- rosey.py orchestrator: 60% okay (thin orchestration)
- Error handling edge cases: Not required for v1.0
- External service mocks: Tested in integration tests

### Test Execution

**Local Development**:
```powershell
# Run all tests
pytest tests/

# Run specific test file
pytest tests/integration/test_chat_flow.py -v

# Run with coverage
pytest tests/ --cov

# Run only fast tests (exclude slow)
pytest tests/ -m "not slow"
```

**CI/CD**:
- Runs on every push to v1 or main
- Runs on every PR
- Fails if tests fail
- Fails if coverage <75%

---

## Acceptance Criteria

### Deliverables
- [ ] 201+ plugin tests migrated and passing (96%+ rate)
- [ ] 300 NATS interface tests written and passing
- [ ] 100 core unit tests written and passing
- [ ] Total: 500-800 tests all green
- [ ] CI/CD workflow created and green
- [ ] Coverage reports generated (78%+ achieved)
- [ ] pytest.ini configured
- [ ] tests/conftest.py with shared fixtures
- [ ] Zero `from lib.` imports in any test

### Quality Gates
- [ ] Full test suite runs in <5 minutes
- [ ] All tests test NATS interfaces or core components
- [ ] CI passes 3 consecutive times
- [ ] Coverage badge in README.md
- [ ] Test documentation in tests/README.md

---

## Dependencies

### Prerequisites
- Sortie 2 complete (v1 branch with working bot)
- Python 3.12+ environment
- pytest, pytest-cov, pytest-asyncio installed

### External Dependencies
- pytest (testing framework)
- pytest-cov (coverage reporting)
- pytest-asyncio (async test support)
- unittest.mock (mocking framework)
- GitHub Actions (CI/CD)

### Blocks
- Sortie 4 (Documentation) - needs tests green

---

## Risks & Mitigations

### Risk 1: Plugin Tests Don't Migrate Cleanly
**Likelihood**: Medium  
**Impact**: Medium (need to fix imports)  

**Mitigation**:
- Plugin tests already test NATS interfaces (correct architecture)
- Most imports should work (plugins/ and common/ unchanged)
- Systematic find/replace for lib.* imports
- Can fix broken tests incrementally

### Risk 2: 300 Interface Tests Takes Too Long
**Likelihood**: Medium  
**Impact**: Low (can reduce scope)  

**Mitigation**:
- Target is realistic (300 tests, 5 days)
- ~60 tests/day = ~1 test/10 minutes
- Can reduce to 200 tests if needed
- Most tests follow same pattern (copy/modify)

### Risk 3: Coverage Target Too Aggressive
**Likelihood**: Low  
**Impact**: Low (can adjust target)  

**Mitigation**:
- 75% is reasonable target (not 85%+)
- Focus on interface coverage (80%+) is achievable
- Can defer edge case tests to v1.1+
- Current Sprint 19 coverage is 66% (we're improving)

---

## Notes

### Why 500-800 Tests?
- 201 plugin tests already exist (proven working)
- 300 interface tests cover NATS contracts (critical)
- 100 core tests ensure components work (unit tests)
- Total is focused, not exhaustive
- Quality over quantity (test right things)

### Why 75% Coverage?
- Sprint 19 had 66% with 2000 tests
- 75% with 600 tests is better coverage
- Focus on interfaces (80%+) more important than overall
- Realistic for 5-day timeline
- Can improve incrementally in v1.1+

### Test Speed
- Mocked NATS = fast tests (no server needed)
- No external services = isolated tests
- Parallel execution = faster CI
- Target: <5 minutes full suite

---

## Completion Checklist

### Day 1-2: Plugin Tests
- [ ] Plugin tests copied from Sprint 19
- [ ] Imports fixed (lib.* → core.* or common.*)
- [ ] Fixtures updated for v1.0
- [ ] tests/conftest.py created
- [ ] 201+ tests passing (96%+ rate)
- [ ] Committed and pushed

### Day 2-3: Interface Tests
- [ ] Chat flow tests (100 tests)
- [ ] Command routing tests (100 tests)
- [ ] Plugin communication tests (50 tests)
- [ ] CyTube integration tests (50 tests)
- [ ] All 300 tests passing
- [ ] Committed and pushed

### Day 4: Core Tests
- [ ] EventBus tests (25 tests)
- [ ] PluginManager tests (25 tests)
- [ ] CommandRouter tests (25 tests)
- [ ] CyTubeConnector tests (25 tests)
- [ ] All 100 tests passing
- [ ] Committed and pushed

### Day 5: CI/CD
- [ ] pytest.ini updated
- [ ] CI workflow created
- [ ] Full test suite passing locally
- [ ] Coverage reports generated
- [ ] CI passing on GitHub
- [ ] Coverage badge added to README
- [ ] Committed and pushed

---

**Estimated Time**: 5 days (Week 2)  
**Actual Time**: _[To be filled after completion]_  
**Completed By**: _[To be filled]_  
**Completion Date**: _[To be filled]_  

---

**Next Sortie**: [SPEC-Sortie-4-Documentation.md](SPEC-Sortie-4-Documentation.md)
