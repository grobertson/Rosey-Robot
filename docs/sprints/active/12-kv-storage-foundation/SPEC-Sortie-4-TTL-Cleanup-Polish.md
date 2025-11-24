# SPEC: Sortie 4 - TTL Cleanup & Polish

**Sprint**: 12 (KV Storage Foundation)  
**Sortie**: 4 of 4  
**Estimated Effort**: ~4 hours  
**Branch**: `feature/sprint-12-sortie-4-cleanup-polish`  
**Dependencies**: Sorties 1-3 (complete KV implementation)

---

## 1. Overview

Implement background TTL cleanup task and finalize the KV storage feature with documentation, performance validation, and production readiness checks.

**What This Sortie Achieves**:

- Background cleanup task (runs every 5 minutes)
- Performance benchmarks and validation
- Comprehensive feature documentation
- Production deployment checklist
- Final integration testing

---

## 2. Scope and Non-Goals

### In Scope

✅ Background cleanup task in DatabaseService  
✅ Configurable cleanup interval  
✅ Performance benchmarks (10k keys)  
✅ Feature documentation (user + developer)  
✅ Production deployment checklist  
✅ Final integration tests  
✅ Monitoring/logging enhancements

### Out of Scope

❌ DatabaseClient wrapper (future sprint)  
❌ Advanced monitoring dashboards (future)  
❌ KV storage quotas per plugin (future)  
❌ Backup/restore for KV data (future)

---

## 3. Requirements

### Functional Requirements

**FR-1**: Background cleanup task must:
- Run every 5 minutes (configurable)
- Call `kv_cleanup_expired()`
- Log number of keys deleted
- Handle errors gracefully (log and continue)
- Not block other DatabaseService operations

**FR-2**: Performance benchmarks must validate:
- kv_set: <10ms for 1000 operations
- kv_get: <5ms for 1000 operations
- kv_list: <50ms for 1000 keys
- kv_cleanup_expired: <1s for 10,000 keys

**FR-3**: Documentation must include:
- User guide: How plugins use KV storage
- Developer guide: Implementation details
- API reference: All methods and NATS subjects
- Performance characteristics
- Best practices and gotchas

**FR-4**: Production checklist must cover:
- Database migration applied
- Indexes verified
- NATS subjects registered
- Cleanup task running
- Monitoring in place

### Non-Functional Requirements

**NFR-1 Reliability**: Cleanup failures don't crash DatabaseService  
**NFR-2 Performance**: Cleanup completes <1s for typical workloads  
**NFR-3 Observability**: All operations logged at appropriate levels

---

## 4. Technical Design

### 4.1 Background Cleanup Task

**File**: `common/database_service.py`

```python
import asyncio
from datetime import datetime

class DatabaseService:
    """Database service with NATS handlers and background tasks."""
    
    def __init__(self, db, nats_url, cleanup_interval_seconds=300):
        """
        Initialize DatabaseService.
        
        Args:
            db: BotDatabase instance
            nats_url: NATS server URL
            cleanup_interval_seconds: Cleanup interval (default 300 = 5 minutes)
        """
        self.db = db
        self.nats_url = nats_url
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.nc = None
        self.logger = logging.getLogger(__name__)
        self._cleanup_task = None
        self._shutdown = False
    
    async def start(self):
        """Start DatabaseService and background tasks."""
        self.logger.info("Starting DatabaseService...")
        
        # Connect to NATS
        self.nc = NATS()
        await self.nc.connect(self.nats_url)
        
        # Register handlers
        # ... existing row operation handlers ...
        
        # KV storage handlers
        await self.nc.subscribe("rosey.db.kv.set", cb=self._handle_kv_set)
        await self.nc.subscribe("rosey.db.kv.get", cb=self._handle_kv_get)
        await self.nc.subscribe("rosey.db.kv.delete", cb=self._handle_kv_delete)
        await self.nc.subscribe("rosey.db.kv.list", cb=self._handle_kv_list)
        
        # Start background cleanup task
        self._shutdown = False
        self._cleanup_task = asyncio.create_task(self._kv_cleanup_loop())
        
        self.logger.info(
            f"DatabaseService started (cleanup interval: {self.cleanup_interval_seconds}s)"
        )
    
    async def stop(self):
        """Stop DatabaseService and background tasks."""
        self.logger.info("Stopping DatabaseService...")
        
        # Signal shutdown
        self._shutdown = True
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Disconnect NATS
        if self.nc:
            await self.nc.close()
        
        self.logger.info("DatabaseService stopped")
    
    async def _kv_cleanup_loop(self):
        """
        Background task to clean up expired KV entries.
        
        Runs every cleanup_interval_seconds and deletes expired entries.
        Errors are logged but don't stop the loop.
        """
        self.logger.info("Starting KV cleanup background task")
        
        while not self._shutdown:
            try:
                # Wait for next cleanup interval
                await asyncio.sleep(self.cleanup_interval_seconds)
                
                if self._shutdown:
                    break
                
                # Run cleanup
                start_time = datetime.utcnow()
                deleted_count = await self.db.kv_cleanup_expired()
                elapsed_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                if deleted_count > 0:
                    self.logger.info(
                        f"KV cleanup: deleted {deleted_count} expired keys "
                        f"in {elapsed_ms:.1f}ms"
                    )
                else:
                    self.logger.debug(
                        f"KV cleanup: no expired keys found ({elapsed_ms:.1f}ms)"
                    )
                
            except asyncio.CancelledError:
                # Task cancelled during shutdown
                break
            except Exception as e:
                # Log error but continue cleanup loop
                self.logger.error(
                    f"Error in KV cleanup task: {e}",
                    exc_info=True
                )
                # Brief backoff on error
                await asyncio.sleep(60)
        
        self.logger.info("KV cleanup background task stopped")
```

### 4.2 Configuration

Add to `config.json`:

```json
{
  "database": {
    "url": "postgresql://...",
    "kv_cleanup_interval_seconds": 300
  }
}
```

### 4.3 Performance Benchmarks

**File**: `tests/performance/test_kv_performance.py`

```python
import pytest
import time
from common.database import BotDatabase

class TestKVPerformance:
    """Performance benchmarks for KV storage."""
    
    @pytest.fixture
    async def db(self):
        """Create test database."""
        db = BotDatabase("sqlite:///:memory:")
        await db.create_tables()
        yield db
        await db.close()
    
    async def test_kv_set_1000_ops(self, db):
        """Benchmark: 1000 set operations."""
        start = time.time()
        
        for i in range(1000):
            await db.kv_set("bench", f"key{i}", {"index": i})
        
        elapsed = time.time() - start
        avg_ms = (elapsed / 1000) * 1000
        
        print(f"\nkv_set: {elapsed:.2f}s for 1000 ops ({avg_ms:.2f}ms avg)")
        assert elapsed < 10.0  # <10s total = <10ms avg
    
    async def test_kv_get_1000_ops(self, db):
        """Benchmark: 1000 get operations."""
        # Setup data
        for i in range(1000):
            await db.kv_set("bench", f"key{i}", {"index": i})
        
        # Benchmark gets
        start = time.time()
        
        for i in range(1000):
            result = await db.kv_get("bench", f"key{i}")
            assert result['exists'] == True
        
        elapsed = time.time() - start
        avg_ms = (elapsed / 1000) * 1000
        
        print(f"\nkv_get: {elapsed:.2f}s for 1000 ops ({avg_ms:.2f}ms avg)")
        assert elapsed < 5.0  # <5s total = <5ms avg
    
    async def test_kv_list_1000_keys(self, db):
        """Benchmark: List 1000 keys."""
        # Setup data
        for i in range(1000):
            await db.kv_set("bench", f"key{i:04d}", i)
        
        # Benchmark list
        start = time.time()
        result = await db.kv_list("bench", limit=1000)
        elapsed = time.time() - start
        
        assert result['count'] == 1000
        print(f"\nkv_list (1000 keys): {elapsed*1000:.1f}ms")
        assert elapsed < 0.050  # <50ms
    
    async def test_kv_cleanup_10k_expired(self, db):
        """Benchmark: Cleanup 10k expired keys."""
        from datetime import datetime, timedelta
        from common.models import PluginKVStorage
        
        # Setup 10k expired keys
        past = datetime.utcnow() - timedelta(hours=1)
        async with db.session_factory() as session:
            for i in range(10000):
                entry = PluginKVStorage(
                    plugin_name="bench",
                    key=f"key{i}",
                    value_json='"data"',
                    expires_at=past
                )
                session.add(entry)
            await session.commit()
        
        # Benchmark cleanup
        start = time.time()
        deleted = await db.kv_cleanup_expired()
        elapsed = time.time() - start
        
        assert deleted == 10000
        print(f"\nkv_cleanup_expired (10k keys): {elapsed*1000:.0f}ms")
        assert elapsed < 1.0  # <1 second
    
    async def test_kv_concurrent_access(self, db):
        """Test concurrent set operations."""
        async def worker(worker_id):
            for i in range(100):
                await db.kv_set("bench", f"worker{worker_id}_key{i}", i)
        
        # Run 10 workers concurrently
        start = time.time()
        workers = [worker(i) for i in range(10)]
        await asyncio.gather(*workers)
        elapsed = time.time() - start
        
        # Verify all keys written
        result = await db.kv_list("bench", limit=2000)
        assert result['count'] == 1000  # 10 workers * 100 keys
        
        print(f"\nConcurrent access (10 workers, 100 ops each): {elapsed:.2f}s")
        assert elapsed < 15.0
```

---

## 5. Implementation Steps

### Step 1: Add Cleanup Task

1. Update `DatabaseService.__init__()` with `cleanup_interval_seconds` parameter
2. Add `_cleanup_task` and `_shutdown` instance variables
3. Implement `_kv_cleanup_loop()` method
4. Update `start()` to launch cleanup task
5. Update `stop()` to cancel cleanup task gracefully

### Step 2: Add Configuration

1. Update `config.json.dist` with KV cleanup settings
2. Update config loading in `common/config.py`
3. Pass cleanup interval to DatabaseService constructor

### Step 3: Create Performance Tests

1. Create `tests/performance/test_kv_performance.py`
2. Implement 5 benchmark tests
3. Run and validate performance targets met

### Step 4: Write Documentation

Create three documentation files:

**File 1**: `docs/guides/KV_STORAGE_USER_GUIDE.md`
- Overview of KV storage feature
- How plugins use it (via NATS)
- Code examples
- TTL usage patterns
- Best practices

**File 2**: `docs/guides/KV_STORAGE_DEV_GUIDE.md`
- Architecture overview
- Implementation details
- Database schema
- NATS subject patterns
- Performance characteristics
- Troubleshooting

**File 3**: `docs/API_REFERENCE.md` (update)
- Add KV storage section
- Document all NATS subjects
- Request/response schemas
- Error codes

### Step 5: Create Deployment Checklist

**File**: `docs/sprints/12-kv-storage-foundation/DEPLOYMENT_CHECKLIST.md`

```markdown
# Sprint 12 Deployment Checklist

## Pre-Deployment

- [ ] All 4 sorties merged to main
- [ ] Full test suite passes (unit + integration)
- [ ] Performance benchmarks validated
- [ ] Documentation reviewed and complete

## Database Migration

- [ ] Backup production database
- [ ] Run migration: `alembic upgrade head`
- [ ] Verify table created: `\d plugin_kv_storage`
- [ ] Verify indexes: `\di plugin_kv_storage*`
- [ ] Test rollback on staging: `alembic downgrade -1`

## Service Deployment

- [ ] Update config.json with KV cleanup interval
- [ ] Deploy DatabaseService with new code
- [ ] Verify NATS subscriptions: `nats sub 'rosey.db.kv.>'`
- [ ] Test manual request: `nats req rosey.db.kv.set '{...}'`
- [ ] Verify cleanup task started (check logs)

## Monitoring

- [ ] Check DatabaseService logs for cleanup messages
- [ ] Monitor NATS message counts for kv.* subjects
- [ ] Set up alerts for handler errors
- [ ] Monitor database size growth

## Testing

- [ ] Run integration test suite against production
- [ ] Create test key via NATS: `nats req rosey.db.kv.set '{...}'`
- [ ] Retrieve test key: `nats req rosey.db.kv.get '{...}'`
- [ ] List test keys: `nats req rosey.db.kv.list '{...}'`
- [ ] Delete test key: `nats req rosey.db.kv.delete '{...}'`

## Rollback Plan (if needed)

- [ ] Revert DatabaseService deployment
- [ ] Run migration downgrade: `alembic downgrade -1`
- [ ] Verify table dropped
- [ ] Restore from backup if data corruption
```

---

## 6. Testing Strategy

### 6.1 Cleanup Task Tests

**File**: `tests/unit/test_database_service_cleanup.py`

```python
import pytest
import asyncio
from datetime import datetime, timedelta
from common.database_service import DatabaseService
from common.database import BotDatabase
from common.models import PluginKVStorage

class TestDatabaseServiceCleanup:
    """Test background cleanup task."""
    
    @pytest.fixture
    async def db(self):
        """Create test database."""
        db = BotDatabase("sqlite:///:memory:")
        await db.create_tables()
        yield db
        await db.close()
    
    async def test_cleanup_task_starts(self, db):
        """Test cleanup task starts with service."""
        service = DatabaseService(
            db,
            "nats://localhost:4222",
            cleanup_interval_seconds=60
        )
        
        # Don't actually connect to NATS for this test
        service.nc = None
        service._cleanup_task = asyncio.create_task(service._kv_cleanup_loop())
        
        # Task should be running
        assert service._cleanup_task is not None
        assert not service._cleanup_task.done()
        
        # Cleanup
        service._shutdown = True
        service._cleanup_task.cancel()
        try:
            await service._cleanup_task
        except asyncio.CancelledError:
            pass
    
    async def test_cleanup_removes_expired(self, db):
        """Test cleanup removes expired keys."""
        # Setup expired keys
        past = datetime.utcnow() - timedelta(hours=1)
        async with db.session_factory() as session:
            for i in range(10):
                entry = PluginKVStorage(
                    plugin_name="test",
                    key=f"expired{i}",
                    value_json='"data"',
                    expires_at=past
                )
                session.add(entry)
            await session.commit()
        
        # Verify keys exist
        result = await db.kv_list("test", limit=100)
        initial_count = result['count']
        
        # Run cleanup manually
        deleted = await db.kv_cleanup_expired()
        assert deleted == 10
        
        # Verify keys removed
        result = await db.kv_list("test", limit=100)
        assert result['count'] == 0
    
    async def test_cleanup_preserves_valid_keys(self, db):
        """Test cleanup preserves non-expired keys."""
        # Setup mix of expired and valid keys
        past = datetime.utcnow() - timedelta(hours=1)
        future = datetime.utcnow() + timedelta(hours=1)
        
        async with db.session_factory() as session:
            # Expired
            for i in range(5):
                session.add(PluginKVStorage(
                    plugin_name="test",
                    key=f"expired{i}",
                    value_json='"data"',
                    expires_at=past
                ))
            
            # Valid with TTL
            for i in range(5):
                session.add(PluginKVStorage(
                    plugin_name="test",
                    key=f"valid{i}",
                    value_json='"data"',
                    expires_at=future
                ))
            
            # Permanent (no TTL)
            for i in range(5):
                session.add(PluginKVStorage(
                    plugin_name="test",
                    key=f"permanent{i}",
                    value_json='"data"',
                    expires_at=None
                ))
            
            await session.commit()
        
        # Run cleanup
        deleted = await db.kv_cleanup_expired()
        assert deleted == 5
        
        # Verify valid keys remain
        result = await db.kv_list("test", limit=100)
        assert result['count'] == 10  # 5 valid + 5 permanent
    
    async def test_cleanup_handles_errors(self, db):
        """Test cleanup continues after errors."""
        service = DatabaseService(
            db,
            "nats://localhost:4222",
            cleanup_interval_seconds=1  # Fast for testing
        )
        
        # Mock cleanup to raise error once
        original_cleanup = db.kv_cleanup_expired
        call_count = 0
        
        async def mock_cleanup():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Simulated error")
            return await original_cleanup()
        
        db.kv_cleanup_expired = mock_cleanup
        
        # Start cleanup task
        service._shutdown = False
        service._cleanup_task = asyncio.create_task(service._kv_cleanup_loop())
        
        # Wait for multiple cleanup cycles
        await asyncio.sleep(3)
        
        # Task should still be running after error
        assert not service._cleanup_task.done()
        assert call_count >= 2  # At least 2 cleanup attempts
        
        # Cleanup
        service._shutdown = True
        service._cleanup_task.cancel()
        try:
            await service._cleanup_task
        except asyncio.CancelledError:
            pass
```

### 6.2 Performance Validation

Run performance tests:
```bash
pytest tests/performance/test_kv_performance.py -v -s
```

Expected output:
```
kv_set: 2.35s for 1000 ops (2.35ms avg)
kv_get: 1.87s for 1000 ops (1.87ms avg)
kv_list (1000 keys): 23.4ms
kv_cleanup_expired (10k keys): 456ms
Concurrent access (10 workers, 100 ops each): 3.21s
```

### 6.3 Integration Testing

Full end-to-end test with all components:
```python
async def test_full_kv_workflow():
    """Test complete KV workflow with cleanup."""
    # Start DatabaseService with short cleanup interval
    db = BotDatabase("sqlite:///:memory:")
    await db.create_tables()
    
    service = DatabaseService(db, "nats://localhost:4222", cleanup_interval_seconds=5)
    await service.start()
    
    # Create NATS client
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    
    try:
        # Set key with short TTL
        await nc.request(
            "rosey.db.kv.set",
            json.dumps({
                "plugin_name": "test",
                "key": "temp",
                "value": "data",
                "ttl_seconds": 3
            }).encode()
        )
        
        # Verify exists
        resp = await nc.request("rosey.db.kv.get", ...)
        result = json.loads(resp.data.decode())
        assert result['data']['exists'] == True
        
        # Wait for cleanup cycle
        await asyncio.sleep(8)
        
        # Verify removed by cleanup
        resp = await nc.request("rosey.db.kv.get", ...)
        result = json.loads(resp.data.decode())
        assert result['data']['exists'] == False
        
    finally:
        await nc.close()
        await service.stop()
        await db.close()
```

---

## 7. Acceptance Criteria

- [x] **AC-1**: Cleanup task implemented
  - Given DatabaseService started
  - When checking background tasks
  - Then _cleanup_task is running

- [x] **AC-2**: Cleanup runs on schedule
  - Given 5-minute interval configured
  - When monitoring logs
  - Then cleanup runs every 5 minutes

- [x] **AC-3**: Cleanup removes expired keys
  - Given database with expired keys
  - When cleanup runs
  - Then expired keys deleted, valid keys preserved

- [x] **AC-4**: Cleanup errors handled gracefully
  - Given cleanup encounters error
  - When exception raised
  - Then error logged, task continues

- [x] **AC-5**: Performance benchmarks pass
  - Given performance test suite
  - When running benchmarks
  - Then all targets met (kv_set <10ms, cleanup <1s, etc.)

- [x] **AC-6**: Documentation complete
  - Given docs folder
  - When reviewing documentation
  - Then user guide, dev guide, and API ref exist

- [x] **AC-7**: Deployment checklist created
  - Given sprint folder
  - When checking for DEPLOYMENT_CHECKLIST.md
  - Then file exists with complete steps

- [x] **AC-8**: Integration tests pass
  - Given full test suite
  - When running all tests
  - Then 100% pass rate

---

## 8. Rollout Plan

### Pre-deployment

1. Complete all prior sorties (1-3)
2. Run full test suite
3. Validate performance benchmarks
4. Review all documentation

### Deployment Steps

1. Create feature branch: `git checkout -b feature/sprint-12-sortie-4-cleanup-polish`
2. Implement cleanup task in DatabaseService
3. Add configuration for cleanup interval
4. Create performance tests and validate
5. Write user and developer documentation
6. Create deployment checklist
7. Run full integration tests
8. Commit changes with message:
   ```
   Sprint 12 Sortie 4: TTL Cleanup & Polish
   
   - Add background cleanup task (runs every 5 minutes)
   - Create performance benchmarks (all targets met)
   - Write comprehensive documentation (user + dev guides)
   - Add deployment checklist
   - Final integration tests pass
   
   Implements: SPEC-Sortie-4-TTL-Cleanup-Polish.md
   Related: PRD-KV-Storage-Foundation.md
   Completes: Sprint 12 (KV Storage Foundation)
   ```
9. Push branch and create PR
10. Code review
11. Merge to main
12. Deploy following DEPLOYMENT_CHECKLIST.md

### Post-deployment

- Monitor cleanup task logs
- Verify cleanup runs on schedule
- Check performance metrics
- Gather user feedback

### Rollback Procedure

If issues arise:
```bash
# Revert code
git revert <commit-hash>

# Optional: Remove table if needed
alembic downgrade -1
```

---

## 9. Dependencies & Risks

### Dependencies

- **Sorties 1-3**: Complete KV implementation
- **asyncio**: Background task management
- **Logging**: For cleanup task monitoring

### External Dependencies

None

### Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Cleanup task crashes service | Low | High | Comprehensive error handling, task isolation |
| Cleanup too slow for large datasets | Low | Medium | Index on expires_at ensures <1s for 10k keys |
| Interval too frequent/infrequent | Medium | Low | Make configurable, default to 5 minutes |
| Documentation becomes stale | Medium | Low | Include in PR review checklist |

---

## 10. Documentation

### 10.1 User Guide

**File**: `docs/guides/KV_STORAGE_USER_GUIDE.md`

- Overview: What is KV storage?
- Quick start: Simple set/get example
- TTL usage: Expiring keys automatically
- Prefix queries: Organizing keys
- Best practices: Key naming, value sizes, error handling
- Examples: Common patterns (config, cache, session data)

### 10.2 Developer Guide

**File**: `docs/guides/KV_STORAGE_DEV_GUIDE.md`

- Architecture: Three-layer design (model, BotDatabase, DatabaseService)
- Database schema: Table structure, indexes
- NATS integration: Subject patterns, request/response
- Performance: Latency characteristics, optimization tips
- Cleanup: How TTL cleanup works
- Troubleshooting: Common issues and solutions

### 10.3 API Reference

Update `docs/API_REFERENCE.md`:

- KV Storage section
- All NATS subjects documented
- Request/response schemas
- Error codes reference
- Code examples

---

## 11. Related Specifications

**Previous**: 
- [SPEC-Sortie-1-KV-Schema-Model.md](SPEC-Sortie-1-KV-Schema-Model.md)
- [SPEC-Sortie-2-BotDatabase-KV-Methods.md](SPEC-Sortie-2-BotDatabase-KV-Methods.md)
- [SPEC-Sortie-3-DatabaseService-NATS-Handlers.md](SPEC-Sortie-3-DatabaseService-NATS-Handlers.md)

**Next**: Sprint 13 - Row Operations Foundation

**Parent PRD**: [PRD-KV-Storage-Foundation.md](PRD-KV-Storage-Foundation.md)

---

**Document Version**: 1.0  
**Last Updated**: November 24, 2025  
**Status**: Ready for Implementation  
**Sprint Status**: ✅ All 4 Sorties Specified
