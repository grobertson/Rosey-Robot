# Technical Specification: Testing & Documentation

**Sprint**: Sprint 9 "The Accountant"  
**Sortie**: 6 of 6 (FINAL)  
**Status**: Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Dependencies**: Sortie 1-5 MUST be complete  
**Blocking**: None (Sprint 9 completion)  

---

## Overview

**Purpose**: Update test suite to work with new NATS architecture, create comprehensive migration documentation, update deployment guides, and validate entire Sprint 9 implementation. This is the **final validation sortie** that ensures Sprint 9 is production-ready.

**Scope**:
- Update existing test suite (146 tests from Sprint 8)
- Create new tests for NATS functionality
- Write migration guide for users
- Update architecture documentation
- Update deployment documentation
- End-to-end integration testing
- Performance benchmarking

**Key Principle**: *"The Accountant verifies everything is correct before signing off."*

**Non-Goals**:
- New features (architecture work only)
- Multi-platform testing (Sprint 10)
- Plugin sandboxing (Sprint 11)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: All existing tests MUST pass with new architecture  
**FR-002**: New tests MUST cover NATS functionality  
**FR-003**: Migration guide MUST be complete and tested  
**FR-004**: Deployment guide MUST include NATS setup  
**FR-005**: End-to-end integration test MUST validate entire flow  
**FR-006**: Performance benchmarks MUST show <5% overhead  

### 1.2 Non-Functional Requirements

**NFR-001**: Test coverage ≥85% (maintain Sprint 8 level)  
**NFR-002**: Documentation clear and actionable  
**NFR-003**: Migration guide tested with real configs  

---

## 2. Test Suite Updates

### 2.1 Fixture Updates

**File**: `tests/conftest.py`

**Current Fixtures** (Sprint 8):
```python
@pytest.fixture
def bot_db():
    """In-memory database for testing."""
    return BotDatabase(':memory:')

@pytest.fixture
def bot(bot_db):
    """Bot instance with test database."""
    connection = Mock()
    return Bot(connection, 'test_channel', db=bot_db)
```

**New Fixtures** (Sprint 9):
```python
import pytest
from unittest.mock import Mock, AsyncMock
from nats.aio.client import Client as NATS

@pytest.fixture
async def nats_client():
    """Mock NATS client for testing."""
    client = Mock(spec=NATS)
    client.publish = AsyncMock()
    client.request = AsyncMock()
    client.subscribe = AsyncMock()
    return client

@pytest.fixture
def bot_db():
    """In-memory database for testing (still used by DatabaseService)."""
    return BotDatabase(':memory:')

@pytest.fixture
async def bot(nats_client):
    """Bot instance with NATS client (NEW - no db parameter)."""
    connection = Mock()
    return Bot(connection, 'test_channel', nats_client=nats_client)

@pytest.fixture
async def bot_with_db_service(nats_client, bot_db):
    """Bot with full DatabaseService for integration tests."""
    from common.database_service import DatabaseService
    
    db_service = DatabaseService(nats_client, ':memory:')
    await db_service.start()
    
    connection = Mock()
    bot = Bot(connection, 'test_channel', nats_client=nats_client)
    
    yield bot, db_service
    
    await db_service.stop()
```

### 2.2 Test Updates by Category

#### Category 1: Bot Handler Tests

**File**: `tests/unit/test_bot.py`

**Update Pattern**:
```python
# OLD (Sprint 8)
def test_user_join(bot, bot_db):
    """Test user join handler."""
    bot._on_user_join(None, {'user': 'alice'})
    assert 'alice' in bot.channel.userlist
    # Verify DB called
    assert bot_db.user_joined.called

# NEW (Sprint 9)
@pytest.mark.asyncio
async def test_user_join(bot, nats_client):
    """Test user join handler."""
    await bot._on_user_join(None, {
        'user': 'alice',
        'user_data': {'username': 'alice', 'rank': 0}
    })
    assert 'alice' in bot.channel.userlist
    # Verify NATS publish called
    nats_client.publish.assert_called_once_with(
        'rosey.db.user.joined',
        ANY  # JSON payload
    )
```

**Tests to Update**:
- `test_user_join` → verify NATS publish
- `test_user_leave` → verify NATS publish
- `test_chat_message` → verify NATS publish
- `test_user_count` → verify NATS publish
- `test_pending_messages` → verify NATS request/reply

**Estimated**: 30 tests to update, ~2 hours

#### Category 2: Event Normalization Tests

**File**: `tests/unit/test_event_normalization.py` (NEW)

**Test Coverage**:
```python
import pytest
from lib.connection.cytube import CyTubeConnection

class TestEventNormalization:
    """Test event normalization layer (Sortie 1)."""
    
    def test_user_list_has_user_objects(self):
        """Verify user_list contains objects, not strings."""
        conn = CyTubeConnection(...)
        raw_data = [
            {'name': 'alice', 'rank': 2, 'afk': False},
            {'name': 'bob', 'rank': 0, 'afk': True}
        ]
        
        normalized = conn._normalize_user_list(raw_data)
        
        # Verify users is array of objects
        assert 'users' in normalized
        assert len(normalized['users']) == 2
        
        for user in normalized['users']:
            assert isinstance(user, dict)
            assert 'username' in user
            assert 'rank' in user
            assert 'is_moderator' in user
    
    def test_user_join_has_user_data(self):
        """Verify user_join includes user_data field."""
        # ... test user_data field present ...
    
    def test_pm_has_recipient(self):
        """Verify PM events include recipient field."""
        # ... test recipient field present ...
```

**Estimated**: 10 new tests, ~1 hour

#### Category 3: DatabaseService Tests

**File**: `tests/unit/test_database_service.py` (NEW)

**Test Coverage**:
```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from common.database_service import DatabaseService

@pytest.fixture
async def db_service(nats_client):
    """DatabaseService with mock NATS and database."""
    with patch('common.database_service.BotDatabase') as MockDB:
        service = DatabaseService(nats_client, ':memory:')
        service.db = MockDB()
        yield service

@pytest.mark.asyncio
async def test_start_subscribes(db_service, nats_client):
    """Verify start() subscribes to all subjects."""
    await db_service.start()
    assert nats_client.subscribe.call_count == 9

@pytest.mark.asyncio
async def test_handle_user_joined(db_service):
    """Verify user_joined handler."""
    msg = Mock()
    msg.data = json.dumps({'username': 'alice'}).encode()
    
    await db_service._handle_user_joined(msg)
    
    db_service.db.user_joined.assert_called_once_with('alice')

# ... more handler tests ...
```

**Estimated**: 15 new tests, ~1.5 hours

#### Category 4: Integration Tests

**File**: `tests/integration/test_sprint9_integration.py` (NEW)

**End-to-End Test**:
```python
import pytest
import asyncio
from nats.aio.client import Client as NATS
from common.database_service import DatabaseService
from lib.bot import Bot

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_event_flow():
    """Test full event flow: Bot → NATS → DatabaseService → Database.
    
    This test validates the entire Sprint 9 architecture:
    1. Bot publishes event to NATS
    2. DatabaseService receives event
    3. Database is updated
    4. Bot queries database via NATS
    5. DatabaseService responds
    
    Requires: NATS server running on localhost:4222
    """
    # Connect to real NATS server
    nats = NATS()
    await nats.connect("nats://localhost:4222")
    
    # Start database service
    db_service = DatabaseService(nats, ':memory:')
    await db_service.start()
    
    # Create bot
    connection = Mock()
    bot = Bot(connection, 'test_channel', nats_client=nats)
    
    # Trigger user join event
    await bot._on_user_join(None, {
        'user': 'alice',
        'user_data': {'username': 'alice', 'rank': 2}
    })
    
    # Wait for NATS propagation
    await asyncio.sleep(0.1)
    
    # Verify database updated
    assert 'alice' in [u['username'] for u in db_service.db.get_all_users()]
    
    # Query via NATS
    response = await nats.request(
        'rosey.db.stats.recent_chat.get',
        json.dumps({'limit': 10}).encode(),
        timeout=2.0
    )
    
    # Verify response
    messages = json.loads(response.data.decode())
    assert isinstance(messages, list)
    
    # Cleanup
    await db_service.stop()
    await nats.close()
```

**Estimated**: 3 integration tests, ~1 hour

### 2.3 Test Execution

**Commands**:
```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests (requires NATS)
pytest tests/integration/ -v -m integration

# Run with coverage
pytest tests/ --cov=lib --cov=common --cov-report=html

# Target: ≥85% coverage (maintain Sprint 8 level)
```

---

## 3. Documentation Updates

### 3.1 Migration Guide

**File**: `docs/sprints/upcoming/9-The-Accountant/MIGRATION.md` (NEW)

**Contents**:
```markdown
# Sprint 9 Migration Guide: Event Normalization & NATS Architecture

**Version**: 2.0 (Breaking Changes)  
**Date**: November 2025  
**Target Audience**: Rosey-Robot Users & Contributors  

---

## Overview

Sprint 9 introduces breaking changes to establish a proper distributed, event-driven architecture. This guide helps you migrate from v1 to v2.

**Breaking Changes**:
- Configuration format (v1 → v2)
- Bot constructor signature (no `db` parameter)
- NATS server required
- Database runs as separate service

---

## Prerequisites

### 1. Install NATS Server

**macOS**:
```bash
brew install nats-server
```

**Linux**:
```bash
curl -L https://github.com/nats-io/nats-server/releases/download/v2.10.7/nats-server-v2.10.7-linux-amd64.zip -o nats-server.zip
unzip nats-server.zip
sudo mv nats-server-v2.10.7-linux-amd64/nats-server /usr/local/bin/
```

**Windows**:
- Download from https://github.com/nats-io/nats-server/releases
- Extract and add to PATH

**Verify Installation**:
```bash
nats-server --version
```

### 2. Backup Current Configuration

```bash
cp bot/rosey/config.json bot/rosey/config.json.v1.bak
```

---

## Migration Steps

### Step 1: Migrate Configuration

**Automatic Migration**:
```bash
python scripts/migrate_config.py bot/rosey/config.json --backup
```

**Manual Migration** (if needed):

**Old Format** (v1):
```json
{
  "domain": "https://cytu.be",
  "channel": "YourChannel",
  "user": ["username", "password"],
  "db": "bot_data.db",
  ...
}
```

**New Format** (v2):
```json
{
  "version": "2.0",
  "nats": {
    "url": "nats://localhost:4222"
  },
  "database": {
    "path": "bot_data.db",
    "run_as_service": true
  },
  "platforms": [
    {
      "type": "cytube",
      "domain": "https://cytu.be",
      "channel": "YourChannel",
      "user": ["username", "password"]
    }
  ]
}
```

### Step 2: Start NATS Server

```bash
# Start in foreground (for testing)
nats-server

# Or start in background
nats-server -D

# Verify running
nats-server --signal=status
```

### Step 3: Start Bot

```bash
# Same command as before
python bot/rosey/rosey.py config.json

# Bot now:
# 1. Connects to NATS
# 2. Starts DatabaseService
# 3. Runs normally
```

### Step 4: Verify

**Check Logs**:
- ✅ "Connected to NATS: nats://localhost:4222"
- ✅ "DatabaseService started"
- ✅ "Connected to CyTube channel"

**Test Bot**:
- Join channel → user_list received
- Send message → logged to database
- Check database: `sqlite3 bot_data.db "SELECT * FROM user_stats;"`

---

## Troubleshooting

### NATS Not Running

**Error**:
```
Error: Could not connect to NATS
```

**Solution**:
```bash
# Start NATS server
nats-server
```

### Configuration Version Error

**Error**:
```
ValueError: Configuration version 1.0 not supported
```

**Solution**:
```bash
python scripts/migrate_config.py config.json
```

### Missing NATS Client

**Error**:
```
ValueError: NATS client is required
```

**Solution**: Upgrade to Sprint 9 code, configuration alone isn't enough.

---

## Rollback

**If migration fails**:

1. Stop bot
2. Restore backup:
   ```bash
   cp bot/rosey/config.json.v1.bak bot/rosey/config.json
   ```
3. Checkout pre-Sprint 9 commit:
   ```bash
   git checkout <commit-before-sprint-9>
   ```

---

## What Changed

### Configuration
- ✅ New nested structure
- ✅ NATS section required
- ✅ Multi-platform ready

### Bot Architecture
- ✅ NATS-first communication
- ✅ Process isolation ready
- ✅ Event-driven design

### Database
- ✅ Runs as separate service
- ✅ Communicates via NATS
- ✅ Can run on different machine

### What DIDN'T Change
- ✅ Database schema (data preserved)
- ✅ Bot features (all commands work)
- ✅ CyTube protocol (connection unchanged)

---

## FAQ

**Q: Do I need to reinstall dependencies?**  
A: No, only NATS server is new.

**Q: Will my data be lost?**  
A: No, database schema unchanged. Data preserved.

**Q: Can I run without NATS?**  
A: No, NATS is now required. This is intentional.

**Q: Why the breaking changes?**  
A: To fix fundamental architectural flaws. See PRD for rationale.

**Q: When can I use Discord/Slack?**  
A: Sprint 10 (blocked until Sprint 9 complete).

---

**Need Help?** See docs/sprints/upcoming/9-The-Accountant/PRD-Event-Normalization-NATS-Architecture.md
```

### 3.2 Architecture Documentation Update

**File**: `docs/ARCHITECTURE.md`

**Add Section**:
```markdown
## Event-Driven Architecture (Sprint 9)

**Architecture**: NATS-first, event-driven, distributed

### Layer Isolation

```text
┌──────────────────────────────────────┐
│         NATS Event Bus               │
│  (Central Communication Layer)       │
└──────────────────────────────────────┘
    ↑         ↑         ↑         ↑
    │         │         │         │
┌───┴───┐ ┌───┴───┐ ┌───┴───┐ ┌───┴───┐
│  Bot  │ │  DB   │ │Plugin │ │Plugin │
│ Layer │ │Service│ │   A   │ │   B   │
└───────┘ └───────┘ └───────┘ └───────┘
```

**Hard Boundaries**:
- Bot CANNOT access database directly
- Plugins CANNOT access bot or database
- ALL communication via NATS

**Event Flow**:
1. Platform connection normalizes event
2. Bot processes and publishes to NATS
3. DatabaseService subscribes and updates
4. Plugins subscribe and react

**Benefits**:
- Process isolation (separate machines possible)
- Horizontal scaling (multiple bot instances)
- Plugin sandboxing (isolated processes)
- Platform-agnostic (add Discord/Slack easily)
```

### 3.3 Deployment Documentation

**File**: `docs/DEPLOYMENT.md` (update)

**Add Section**:
```markdown
## NATS Deployment

### Local Development

```bash
# Install NATS
brew install nats-server  # macOS
# or download from https://nats.io/download/

# Start NATS
nats-server

# Start DatabaseService
python -m common.database_service &

# Start Bot
python bot/rosey/rosey.py config.json
```

### Production (Docker Compose)

```yaml
version: '3.8'
services:
  nats:
    image: nats:latest
    ports:
      - "4222:4222"
      - "8222:8222"  # HTTP monitoring
    command: "-m 8222"
  
  database:
    build: .
    command: python -m common.database_service
    depends_on:
      - nats
    environment:
      NATS_URL: nats://nats:4222
    volumes:
      - ./data:/app/data
  
  bot:
    build: .
    command: python bot/rosey/rosey.py config.json
    depends_on:
      - nats
      - database
    environment:
      NATS_URL: nats://nats:4222
```

### Production (Systemd)

**File**: `/etc/systemd/system/rosey-nats.service`
```ini
[Unit]
Description=NATS Server for Rosey Bot
After=network.target

[Service]
Type=simple
User=rosey
ExecStart=/usr/local/bin/nats-server
Restart=always

[Install]
WantedBy=multi-user.target
```

**File**: `/etc/systemd/system/rosey-database.service`
```ini
[Unit]
Description=Rosey Database Service
After=network.target rosey-nats.service
Requires=rosey-nats.service

[Service]
Type=simple
User=rosey
WorkingDirectory=/opt/rosey-robot
ExecStart=/opt/rosey-robot/.venv/bin/python -m common.database_service
Restart=always

[Install]
WantedBy=multi-user.target
```

**File**: `/etc/systemd/system/rosey-bot.service` (update)
```ini
[Unit]
Description=Rosey CyTube Bot
After=network.target rosey-nats.service rosey-database.service
Requires=rosey-nats.service rosey-database.service

[Service]
Type=simple
User=rosey
WorkingDirectory=/opt/rosey-robot/bot/rosey
ExecStart=/opt/rosey-robot/.venv/bin/python rosey.py config.json
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and Start**:
```bash
sudo systemctl enable rosey-nats rosey-database rosey-bot
sudo systemctl start rosey-nats rosey-database rosey-bot
sudo systemctl status rosey-*
```
```

---

## 4. Performance Benchmarking

### 4.1 Benchmark Tests

**File**: `tests/performance/test_nats_overhead.py` (NEW)

```python
import pytest
import asyncio
import time
from unittest.mock import Mock
from nats.aio.client import Client as NATS
from common.database import BotDatabase
from common.database_service import DatabaseService

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_direct_db_call_baseline():
    """Baseline: direct database call performance."""
    db = BotDatabase(':memory:')
    
    start = time.time()
    for i in range(1000):
        db.user_joined(f'user_{i}')
    elapsed = time.time() - start
    
    print(f"\nDirect DB: {elapsed:.3f}s for 1000 calls ({elapsed*1000:.2f}ms avg)")
    return elapsed

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_nats_publish_overhead():
    """NATS publish overhead vs direct calls."""
    nats = NATS()
    await nats.connect("nats://localhost:4222")
    
    db_service = DatabaseService(nats, ':memory:')
    await db_service.start()
    
    start = time.time()
    for i in range(1000):
        await nats.publish('rosey.db.user.joined', json.dumps({
            'username': f'user_{i}',
            'timestamp': int(time.time())
        }).encode())
    
    # Wait for all messages processed
    await asyncio.sleep(0.5)
    
    elapsed = time.time() - start
    
    await db_service.stop()
    await nats.close()
    
    print(f"\nNATS Pub/Sub: {elapsed:.3f}s for 1000 calls ({elapsed*1000:.2f}ms avg)")
    return elapsed

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_nats_request_reply_overhead():
    """NATS request/reply overhead."""
    nats = NATS()
    await nats.connect("nats://localhost:4222")
    
    db_service = DatabaseService(nats, ':memory:')
    await db_service.start()
    
    start = time.time()
    for i in range(100):  # Fewer iterations (slower)
        response = await nats.request(
            'rosey.db.messages.outbound.get',
            json.dumps({'username': f'user_{i}', 'limit': 10}).encode(),
            timeout=2.0
        )
    elapsed = time.time() - start
    
    await db_service.stop()
    await nats.close()
    
    print(f"\nNATS Request/Reply: {elapsed:.3f}s for 100 calls ({elapsed*10:.2f}ms avg)")
    return elapsed
```

**Run Benchmarks**:
```bash
pytest tests/performance/ -v -m benchmark
```

**Target**: NATS overhead <5%

---

## 5. Implementation Plan

### Phase 1: Test Fixture Updates (1 hour)

1. Update `tests/conftest.py` with NATS fixtures
2. Add `nats_client` mock fixture
3. Add `bot_with_db_service` integration fixture
4. Test fixture changes with simple test

### Phase 2: Unit Test Updates (2.5 hours)

1. Update bot handler tests (30 tests) - 1.5 hours
2. Create event normalization tests - 1 hour

### Phase 3: DatabaseService Tests (1.5 hours)

1. Create `test_database_service.py`
2. Test all handlers
3. Test subscription setup/teardown

### Phase 4: Integration Tests (1.5 hours)

1. Create `test_sprint9_integration.py`
2. End-to-end event flow test
3. Multi-component test

### Phase 5: Documentation (2 hours)

1. Write MIGRATION.md - 1 hour
2. Update ARCHITECTURE.md - 30 min
3. Update DEPLOYMENT.md - 30 min

### Phase 6: Benchmarking (1 hour)

1. Create performance tests
2. Run benchmarks
3. Document results

### Phase 7: Final Validation (1 hour)

1. Run full test suite
2. Manual end-to-end testing
3. Review all documentation
4. Mark Sprint 9 complete

---

## 6. Acceptance Criteria

**Definition of Done**:

- [ ] All 146 existing tests pass (updated for NATS)
- [ ] 10+ new event normalization tests
- [ ] 15+ new DatabaseService tests
- [ ] 3+ integration tests
- [ ] Test coverage ≥85%
- [ ] MIGRATION.md complete and tested
- [ ] ARCHITECTURE.md updated
- [ ] DEPLOYMENT.md updated
- [ ] Performance benchmarks run (<5% overhead)
- [ ] Manual end-to-end test passed
- [ ] CHANGELOG.md updated with Sprint 9 summary
- [ ] Sprint 9 PRD acceptance criteria all checked
- [ ] NORMALIZATION_TODO.md all items marked complete

---

## 7. Sprint 9 Final Checklist

**All Sorties Complete**:
- [x] Sortie 1: Event Normalization Foundation
- [x] Sortie 2: Bot Handler Migration
- [x] Sortie 3: Database Service Layer
- [x] Sortie 4: Bot NATS Migration
- [x] Sortie 5: Configuration v2 & Breaking Changes
- [ ] Sortie 6: Testing & Documentation (THIS SORTIE)

**PRD Goals Achieved**:
- [ ] PG-001: Complete Event Normalization
- [ ] PG-002: Eliminate ALL Direct Calls
- [ ] PG-003: Enforce Process Isolation
- [ ] PG-004: Remove `db` Parameter
- [ ] PG-005: Plugin NATS-Only API
- [ ] PG-006: New Configuration Format
- [ ] PG-007: Maintain Test Coverage

**Success Metrics**:
- [ ] Event Structure Compliance: 100%
- [ ] Direct Database Calls: 0
- [ ] Bot Layer Isolation: ✅ Enforced
- [ ] NATS Message Throughput: >1000 msg/sec
- [ ] Process Isolation: ✅ Mandatory
- [ ] Test Coverage: ≥85%
- [ ] Configuration Migration: 100%
- [ ] Plugin API Compliance: 100%
- [ ] Performance Overhead: <5%

---

## 8. Sprint 9 Completion

**After This Sortie**:

1. Create Sprint 9 retrospective
2. Tag release: `v0.9.0`
3. Update README.md with v2 architecture
4. Announce breaking changes to users
5. Begin planning Sprint 10 (Multi-Platform Support)

**Sprint 9 Achievement**:
- ✅ NATS-first architecture established
- ✅ Event normalization complete
- ✅ Process isolation enabled
- ✅ Platform-agnostic foundation ready
- ✅ Multi-platform support unblocked (Sprint 10)
- ✅ Plugin sandboxing unblocked (Sprint 11)
- ✅ Horizontal scaling unblocked (Sprint 12)

**Movie Tagline**: *"The Accountant: Thorough, precise, and kicks ass."*

---

## 9. Dependencies

**Requires**:
- ✅ Sortie 1-5 (All previous sorties complete)

**Blocks**:
- Nothing (Sprint 9 complete after this)

**Unblocks**:
- Sprint 10: Multi-Platform Support
- Sprint 11: Plugin Sandboxing
- Sprint 12: Horizontal Scaling

---

## 10. Next Steps

**After Completion**:

1. Mark Sortie 6 complete
2. Mark Sprint 9 complete
3. Create Sprint 9 retrospective (A+ expected)
4. Plan Sprint 10 execution
5. Celebrate architectural transformation! 🎉

---

**Sortie Status**: Ready for Implementation  
**Priority**: CRITICAL (Sprint Completion)  
**Estimated Effort**: 6-8 hours  
**Success Metric**: All tests pass, documentation complete, Sprint 9 production-ready
