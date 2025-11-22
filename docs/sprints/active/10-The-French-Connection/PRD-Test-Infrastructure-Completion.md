# Product Requirements Document: Test Infrastructure Completion

**Project:** Rosey-Robot  
**Sprint:** 10 - The French Connection  
**Feature:** Complete Test Infrastructure for Sprint 9 Architecture  
**Version:** 1.0  
**Date:** November 21, 2025  
**Status:** Planning  

---

## Executive Summary

Sprint 10 focuses on completing the test infrastructure deferred during Sprint 9's NATS architecture implementation. By implementing `BotDatabase.connect()`, refactoring test fixtures, and re-enabling 31 xfail tests, we will achieve comprehensive test coverage of the event-driven architecture. This sprint prioritizes quality assurance and validation of the Sprint 9 foundation before building additional features.

### Key Deliverables

- Async `BotDatabase` implementation with `connect()` and `close()` methods
- Updated test fixtures for NATS architecture
- Re-implementation of stats command via NATS request/reply
- PM command logging via NATS events
- 31 xfail tests converted to passing tests
- Performance benchmarks validated against requirements
- Test pass rate: 95%+ (from current 94.9%)

---

## Problem Statement

### Current Situation

Sprint 9 successfully transformed Rosey to an event-driven architecture using NATS, but 31 tests were marked as `xfail` to maintain development momentum:

- **Test Pass Rate**: 94.9% (1,167 passing, 31 xfailed, 16 skipped)
- **Coverage**: 66.8% (meets minimum but below 85% target)
- **Blocked Features**: Stats command, PM logging, performance validation
- **Technical Debt**: Test fixtures still use direct database access patterns

### Business Impact

**Risk**: Without comprehensive test coverage, we cannot confidently:
- Deploy production releases
- Add new features (unstable foundation)
- Validate performance requirements
- Ensure fault tolerance guarantees

**Opportunity**: Completing test infrastructure enables:
- High-confidence deployments
- Rapid feature development (Sprint 11+)
- Performance optimization based on real benchmarks
- Demonstration of architecture resilience

---

## Goals and Success Metrics

### Primary Goals

1. **Test Completion**: Convert 31 xfail tests to passing
2. **Database Integration**: Implement async BotDatabase for testing
3. **Stats Command**: Re-enable stats via NATS request/reply
4. **Performance Validation**: Run and analyze all 10 benchmarks

### Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Test Pass Rate | 94.9% | ≥95% | pytest results |
| xfail Tests | 31 | 0 | pytest --tb=short |
| Code Coverage | 66.8% | ≥75% | pytest-cov |
| Performance Benchmarks | 0/10 run | 10/10 pass | benchmark suite |
| Stats Command | Disabled | Functional | Manual testing |
| PM Logging | Direct | Via NATS | Integration test |

### Non-Goals (Sprint 10)

- ❌ New features or user-facing functionality
- ❌ Multi-platform support (future sprint)
- ❌ Plugin system enhancements
- ❌ Production deployment (Sprint 11)
- ❌ Performance optimization (validate first)

---

## User Stories

### Story 1: Test Engineer - Database Testing
**As a** test engineer  
**I want** temporary test databases with full async support  
**So that** I can write reliable integration tests for NATS architecture  

**Acceptance Criteria:**
- [ ] `BotDatabase.connect()` method implemented
- [ ] `BotDatabase.close()` method implemented
- [ ] `temp_database` fixture works in all tests
- [ ] Tests can create/destroy databases independently
- [ ] No test pollution between test runs

---

### Story 2: Developer - Stats Command Access
**As a** CyTube moderator  
**I want** to use the `!stats` command  
**So that** I can see channel and user statistics  

**Acceptance Criteria:**
- [ ] `!stats` command returns channel statistics
- [ ] `!user <name>` command returns user statistics
- [ ] Response time <1 second
- [ ] Stats retrieved via NATS request/reply
- [ ] Error messages if DatabaseService is unavailable

---

### Story 3: DevOps Engineer - Performance Validation
**As a** DevOps engineer  
**I want** performance benchmarks to validate NATS overhead  
**So that** I can ensure production readiness  

**Acceptance Criteria:**
- [ ] All 10 performance benchmarks run successfully
- [ ] NATS latency <5ms average (meets requirement)
- [ ] CPU overhead <5% vs direct writes (meets requirement)
- [ ] Memory overhead <10% (meets requirement)
- [ ] Throughput >100 events/sec (meets requirement)
- [ ] Results documented in benchmark report

---

### Story 4: QA Engineer - Service Resilience
**As a** QA engineer  
**I want** resilience tests to verify fault tolerance  
**So that** I can validate the system handles failures gracefully  

**Acceptance Criteria:**
- [ ] Bot continues when DatabaseService is down
- [ ] DatabaseService recovers after restart
- [ ] Events processed after recovery
- [ ] Recovery rate >75% (fire-and-forget semantics)
- [ ] Tests run reliably without flakiness

---

### Story 5: Developer - PM Command Logging
**As a** bot administrator  
**I want** PM commands logged to the database  
**So that** I can audit moderator actions  

**Acceptance Criteria:**
- [ ] PM commands publish to NATS
- [ ] DatabaseService logs PM commands
- [ ] Audit log includes username, command, timestamp
- [ ] No functional change for moderators
- [ ] Integration tests verify end-to-end flow

---

## Technical Architecture

### Component: BotDatabase (Async Implementation)

```python
# common/database.py

from typing import Optional
import aiosqlite
from lib.storage import StorageAdapter

class BotDatabase(StorageAdapter):
    """Async SQLite database for bot data storage."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
        self._is_connected = False
    
    async def connect(self) -> None:
        """Initialize database connection and run migrations."""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._run_migrations()
        self._is_connected = True
    
    async def close(self) -> None:
        """Close database connection gracefully."""
        if self.conn:
            await self.conn.commit()
            await self.conn.close()
            self._is_connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected
```

**Key Design Decisions:**
- Use `aiosqlite` for async SQLite operations
- Breaking change: Remove sync `_connect()` and `_create_tables()` methods
- v0.5.0 alpha: Breaking changes acceptable for better architecture
- Explicit connection lifecycle: `await db.connect()` required
- Graceful shutdown with transaction commit

---

### Component: Stats Command (NATS Request/Reply)

```python
# common/shell.py

async def cmd_stats(bot, args):
    """Get channel statistics via NATS request/reply."""
    try:
        # Request stats from DatabaseService
        response = await bot.nats.request(
            'rosey.database.query.channel_stats',
            b'{}',
            timeout=1.0
        )
        
        stats = json.loads(response.data)
        
        return format_stats_output(stats)
    
    except asyncio.TimeoutError:
        return "Stats unavailable (DatabaseService timeout)"
    except Exception as e:
        return f"Stats error: {str(e)}"
```

**Request/Reply Pattern:**
- Subject: `rosey.database.query.channel_stats`
- Timeout: 1 second
- Response: JSON with stats data
- Fallback: Clear error message if unavailable

---

### Component: PM Command Logging (NATS Events)

```python
# common/shell.py

async def handle_pm_command(bot, username, message):
    """Process PM command and log via NATS."""
    # Execute command (existing logic)
    result = await execute_command(bot, message)
    
    # Publish audit log event
    await bot.nats.publish(
        'rosey.events.pm_command',
        json.dumps({
            'timestamp': time.time(),
            'username': username,
            'command': message,
            'result': 'success' if result else 'error'
        }).encode()
    )
    
    return result
```

**Event Structure:**
- Subject: `rosey.events.pm_command`
- Payload: JSON with timestamp, username, command, result
- DatabaseService subscribes and logs asynchronously

---

### Test Fixtures Update

```python
# tests/conftest.py

@pytest.fixture
async def temp_database():
    """Create temporary database with async support."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db = BotDatabase(db_path)
    await db.connect()  # Now implemented!
    
    yield db
    
    await db.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
async def nats_test_client():
    """Real NATS client for integration tests."""
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    yield nc
    await nc.close()


@pytest.fixture
async def database_service(nats_test_client, temp_database):
    """DatabaseService for integration testing."""
    service = DatabaseService(nats_test_client, temp_database)
    await service.start()
    
    yield service
    
    await service.stop()
```

---

## Dependencies

### Internal Dependencies

- **Sprint 9 (Complete)**: NATS event bus architecture
- **DatabaseService**: Must be runnable independently
- **NATS Server**: Required for integration/performance tests

### External Dependencies

| Dependency | Version | Purpose | Installation |
|------------|---------|---------|--------------|
| `aiosqlite` | ≥0.19.0 | Async SQLite | `pip install aiosqlite` |
| `pytest-asyncio` | ≥0.21.0 | Async test support | Already installed |
| `nats-py` | ≥2.7.0 | NATS client | Already installed |
| `psutil` | ≥5.9.0 | Performance benchmarks | Already installed |

### CI/CD Dependencies

- NATS container (already configured in `.github/workflows/ci.yml`)
- Python 3.11+
- pytest with coverage plugin

---

## Security and Privacy

### Security Considerations

1. **Database Security**: Test databases use same security as production
2. **Credential Isolation**: Test fixtures don't use production credentials
3. **NATS Auth**: Tests use unauthenticated NATS (localhost only)
4. **Audit Logging**: PM commands logged for security compliance

### Privacy Considerations

- **Test Data**: Use synthetic data in all tests
- **Cleanup**: All test databases deleted after test runs
- **Logs**: Test logs don't contain real user data
- **CI**: No sensitive data in CI logs

---

## Performance Requirements

### Test Execution Performance

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| Full Test Suite | ~1m17s | <2m | With NATS container |
| Integration Tests | ~20s | <30s | Sprint 9 tests |
| Performance Tests | N/A | <5m | All 10 benchmarks |
| Unit Tests | ~10s | <15s | Fast feedback |

### NATS Performance Requirements

| Metric | Requirement | Validation |
|--------|-------------|------------|
| Latency (avg) | <5ms | Benchmark suite |
| Latency (P95) | <10ms | Benchmark suite |
| CPU Overhead | <5% | CPU benchmark |
| Memory Overhead | <10% | Memory benchmark |
| Throughput | >100 events/sec | Throughput benchmark |
| Stability | No leaks (1hr) | Memory stability test |

---

## Rollout Plan

### Phase 1: Database Foundation (Sortie 1)
**Duration**: 1 day  
**Scope**: Implement `BotDatabase.connect()` and `close()`

**Deliverables:**
- [ ] `BotDatabase.connect()` method
- [ ] `BotDatabase.close()` method
- [ ] Async migration runner
- [ ] Updated `temp_database` fixture
- [ ] 12 Sprint 9 integration tests passing

**Success Criteria:**
- All database tests pass
- No test pollution
- Clean connection lifecycle

---

### Phase 2: Stats Command Implementation (Sortie 2)
**Duration**: 1 day  
**Scope**: Re-implement stats via NATS request/reply

**Deliverables:**
- [ ] `cmd_stats()` using NATS request/reply
- [ ] `cmd_user()` using NATS request/reply
- [ ] DatabaseService query handlers
- [ ] 3 stats tests passing
- [ ] User documentation update

**Success Criteria:**
- Stats command functional
- Response time <1s
- Clear error messages

---

### Phase 3: PM Logging & Resilience (Sortie 3)
**Duration**: 1 day  
**Scope**: PM logging via NATS, service resilience tests

**Deliverables:**
- [ ] PM command NATS events
- [ ] DatabaseService PM logging handler
- [ ] 7 PM command tests passing
- [ ] 2 resilience tests passing
- [ ] 1 normalization test fixed

**Success Criteria:**
- PM commands logged asynchronously
- Resilience tests run reliably
- No test flakiness

---

### Phase 4: Performance Validation (Sortie 4)
**Duration**: 1 day  
**Scope**: Run benchmarks, generate report, validate requirements

**Deliverables:**
- [ ] All 10 performance benchmarks running
- [ ] Benchmark results report
- [ ] Performance vs requirements analysis
- [ ] Optimization recommendations (if needed)
- [ ] Documentation updates

**Success Criteria:**
- All benchmarks pass
- Results meet requirements
- Report committed to repo

---

## Testing Strategy

### Test Categories

| Category | Count | Priority | Dependencies |
|----------|-------|----------|--------------|
| Database Tests | 12 | P0 | BotDatabase.connect() |
| Stats Tests | 3 | P1 | Request/reply |
| PM Command Tests | 7 | P1 | NATS events |
| Resilience Tests | 2 | P1 | Fixtures |
| Normalization Test | 1 | P2 | NATS fixture |
| Database Integration | 3 | P1 | Fixtures |
| Performance Tests | 10 | P0 | BotDatabase.connect() |

### Test Execution Plan

```bash
# Phase 1: Database foundation
pytest tests/integration/test_sprint9_integration.py::TestUserJoinedFlow -v

# Phase 2: Stats command
pytest tests/integration/test_shell_integration.py -k stats -v

# Phase 3: PM logging
pytest tests/integration/test_pm_commands.py -v

# Phase 4: Performance
pytest tests/performance/test_nats_overhead.py -v -s
```

---

## Documentation Updates

### Required Documentation

1. **README.md**: Update stats command documentation
2. **TESTING.md**: Document async test patterns
3. **ARCHITECTURE.md**: Add request/reply pattern documentation
4. **Performance README**: Include benchmark results
5. **CHANGELOG.md**: Document breaking changes in v0.5.0

### New Documentation

- [ ] `tests/performance/BENCHMARK_RESULTS.md` - Sprint 10 results
- [ ] `docs/guides/TESTING_ASYNC.md` - Async testing patterns
- [ ] `docs/PERFORMANCE_ANALYSIS.md` - Sprint 9 performance analysis

---

## Risks and Mitigations

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Performance requirements not met | Medium | High | Run benchmarks early, optimize if needed |
| Test flakiness with NATS | Low | Medium | Use fixtures with proper cleanup |
| Breaking changes in v0.5.0 | Low | Medium | Alpha version - breaking changes expected |
| CI timeout with performance tests | Low | Medium | Run benchmarks on demand, not in CI |

### Project Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep (new features) | High | Medium | Strict focus on test completion only |
| Time overrun (4 days → 6 days) | Medium | Low | Each sortie is independently valuable |
| Dependency on NATS server | Low | Low | Already working in CI (Sprint 9) |

---

## Open Questions

### Technical Questions

1. **Q**: Should performance benchmarks run in CI or manually?
   **A**: Manually initially. Add to CI after validating stability.

2. **Q**: What if performance requirements aren't met?
   **A**: Document findings, create optimization sprint if needed (Sprint 11).

3. **Q**: How do we handle breaking changes in v0.5.0 alpha?
   **A**: Clean async-only implementation. No backward compatibility needed.

### Product Questions

1. **Q**: Should stats command be cached or real-time?
   **A**: Real-time via NATS. Caching is future optimization.

2. **Q**: What if DatabaseService is unavailable during stats query?
   **A**: Clear error message with 1-second timeout.

3. **Q**: Should PM logging be synchronous or async?
   **A**: Async (fire-and-forget). Moderator action isn't blocked by logging.

---

## Success Criteria Summary

### Must Have (Sprint 10 Complete)

- ✅ `BotDatabase.connect()` implemented
- ✅ All 31 xfail tests passing
- ✅ Stats command functional via NATS
- ✅ PM logging via NATS events
- ✅ Performance benchmarks running
- ✅ Test pass rate ≥95%

### Should Have (High Value)

- ✅ Coverage ≥75%
- ✅ Performance meets all requirements
- ✅ Benchmark results documented
- ✅ No test flakiness

### Nice to Have (If Time Permits)

- ⚪ Performance optimization
- ⚪ Advanced resilience testing
- ⚪ Benchmark visualization
- ⚪ Additional async test helpers

---

## Appendix A: Test Issue References

- [Issue #45](https://github.com/grobertson/Rosey-Robot/issues/45) - Stats Command Disabled (3 tests)
- [Issue #46](https://github.com/grobertson/Rosey-Robot/issues/46) - PM Command Logging (7 tests)
- [Issue #47](https://github.com/grobertson/Rosey-Robot/issues/47) - Event Normalization Test (1 test)
- [Issue #48](https://github.com/grobertson/Rosey-Robot/issues/48) - Database Stats Integration (3 tests)
- [Issue #49](https://github.com/grobertson/Rosey-Robot/issues/49) - Service Resilience Tests (2 tests)
- [Issue #50](https://github.com/grobertson/Rosey-Robot/issues/50) - BotDatabase.connect() (12 tests)
- [Issue #51](https://github.com/grobertson/Rosey-Robot/issues/51) - Performance Tests (10 tests)

---

## Appendix B: Current Test Status

```
Test Summary (Sprint 9):
========================
Total Tests: 1,231
✅ Passed: 1,167 (94.9%)
⚠️  xfail: 31 (2.5%)
⏭️  Skipped: 16 (1.3%)
❌ Failed: 0 (0%)

Coverage: 66.8%

CI Status: ✅ All jobs passing
- Test: 1m17s
- Lint: 26s  
- Build: 17s
```

---

## Appendix C: Related Sprints

**Sprint 11: SQLAlchemy Migration ("The Conversation")**

Following Sprint 10's test infrastructure completion, Sprint 11 will migrate the database layer to SQLAlchemy ORM with Alembic migrations. This provides:
- **Database portability**: SQLite → PostgreSQL → MySQL
- **Type safety**: ORM models with full type hints
- **Schema versioning**: Alembic migrations for controlled evolution
- **Production ready**: PostgreSQL support for high-availability deployments

See: `docs/sprints/upcoming/11-The-Conversation/PRD-SQLAlchemy-Migration.md`

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**Author**: Rosey-Robot Development Team  
**Status**: Ready for Implementation
