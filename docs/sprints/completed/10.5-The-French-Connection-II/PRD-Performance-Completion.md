# Product Requirements Document: Performance Completion

**Sprint**: Sprint 10.5 "The French Connection II"  
**Status**: Ready for Implementation  
**Estimated Effort**: 6 hours (half-day sprint)  
**Dependencies**: Sprint 10 Complete  
**Priority**: P1 (Complete unfinished Sprint 10 work)  

---

## Executive Summary

Sprint 10 established NATS performance infrastructure and validated excellent latency (0.090ms). However, 6/10 benchmarks remain incomplete due to missing BotDatabase methods and one xfail marker blocks validation. Sprint 10.5 completes this work with minimal API additions and CI integration.

**Goals**:
1. Add missing BotDatabase methods to unblock 6 benchmarks
2. Remove final xfail marker to validate stats query handlers
3. Integrate benchmarks into CI for regression tracking
4. Investigate CPU overhead (5.80% vs 5% target)

**Non-Goals**:
- Major architectural changes (Sprint 10 architecture is solid)
- New features (pure completion work)
- Performance optimization beyond investigation

---

## Problem Statement

### Current State

**Sprint 10 Results**:
- ✅ 4/10 benchmarks passing (infrastructure works!)
- ❌ 6/10 benchmarks blocked on missing API methods
- ⚠️ 1 xfail marker remains (stats query validation)
- ⚠️ CPU overhead 5.80% (slightly over 5% P1 target)

**Blocked Benchmarks**:
1. `test_sustained_throughput` - needs `get_recent_messages()`
2. `test_burst_throughput` - needs `get_recent_messages()`
3. `test_direct_database_cpu` - needs `log_chat()`
4. `test_database_service_restart` - needs fixture fix
5. `test_request_reply_latency` - NoRespondersError (may need stats handler check)

**Impact**: Can't validate full NATS performance profile without these tests.

---

## User Stories

### US-1: Database API Completeness
**As a** performance test engineer  
**I want** complete BotDatabase API methods  
**So that** I can benchmark all database operations  

**Acceptance Criteria**:
- `get_recent_messages(limit=100)` returns last N chat messages
- `log_chat(username, message)` saves chat message to database
- Both methods follow existing async patterns
- Tests validate methods work correctly

---

### US-2: Stats Query Validation
**As a** integration test maintainer  
**I want** xfail marker removed from stats query test  
**So that** I can validate Sortie 2 stats handlers work  

**Acceptance Criteria**:
- `test_query_user_stats_via_nats` xfail removed
- Test passes (stats handlers implemented in Sortie 2)
- If test fails, document root cause for Sprint 11

---

### US-3: CI Performance Tracking
**As a** DevOps engineer  
**I want** benchmarks running in CI  
**So that** performance regressions are caught automatically  

**Acceptance Criteria**:
- Benchmarks run on PR + weekly schedule
- Results saved as artifacts (JSON + markdown)
- Performance trends tracked over time
- Failures don't block PR merge (informational)

---

### US-4: CPU Overhead Analysis
**As a** performance engineer  
**I want** understanding of 5.80% CPU overhead  
**So that** I can determine if optimization is needed  

**Acceptance Criteria**:
- Profile NATS operations vs direct writes
- Identify top 3 CPU hotspots
- Document findings in performance report
- Recommend optimization strategy (if needed)

---

## Technical Requirements

### TR-1: BotDatabase.get_recent_messages()

**Signature**:
```python
async def get_recent_messages(self, limit: int = 100, offset: int = 0) -> list[dict]:
    """Get recent chat messages from database.
    
    Args:
        limit: Maximum messages to return (default 100)
        offset: Number of messages to skip (default 0)
    
    Returns:
        List of message dicts with keys: id, timestamp, username, message
    """
```

**Query**:
```sql
SELECT id, timestamp, username, message
FROM recent_chat
ORDER BY timestamp DESC
LIMIT ? OFFSET ?
```

---

### TR-2: BotDatabase.log_chat()

**Signature**:
```python
async def log_chat(self, username: str, message: str, timestamp: int = None) -> None:
    """Log chat message to database.
    
    Args:
        username: Username who sent message
        message: Message text
        timestamp: Unix timestamp (default: current time)
    """
```

**Implementation**:
```sql
INSERT INTO recent_chat (timestamp, username, message)
VALUES (?, ?, ?)
```

---

### TR-3: CI Benchmark Workflow

**File**: `.github/workflows/benchmarks.yml`

**Triggers**:
- Pull request (on changes to `common/`, `lib/`, `tests/performance/`)
- Weekly schedule (Sunday 3am UTC)
- Manual dispatch

**Jobs**:
1. Run benchmarks with pytest-json-report
2. Generate markdown report
3. Upload artifacts (JSON + markdown)
4. Comment on PR with summary (if PR trigger)

**Success Criteria**: Informational only (don't block merge)

---

### TR-4: CPU Overhead Investigation

**Tools**:
- Python cProfile for hotspot identification
- line_profiler for line-by-line analysis
- Memory profiler for allocation patterns

**Deliverables**:
- Performance report markdown (CPU_OVERHEAD_ANALYSIS.md)
- Top 3 hotspots identified
- Optimization recommendations (if applicable)

---

## Success Metrics

### Before Sprint 10.5:
- Benchmarks passing: 4/10 (40%)
- xfail markers: 1 (stats query test)
- CI performance tracking: None
- CPU overhead understanding: Unknown

### After Sprint 10.5:
- Benchmarks passing: 10/10 (100%) ✅
- xfail markers: 0 ✅
- CI performance tracking: Automated ✅
- CPU overhead understanding: Documented ✅

---

## Risks and Mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| CPU overhead requires refactor | Medium | Investigation only, defer optimization to Sprint 11 |
| Stats query test still fails | Low | Document root cause, fix in Sprint 11 |
| CI benchmarks timeout | Low | Set 10-minute timeout, skip if infrastructure unavailable |
| New methods break existing code | Low | Follow existing patterns, comprehensive tests |

---

## Rollout Plan

**Phase 1**: Add Missing Methods (1 hour)
- Implement `get_recent_messages()` in database.py
- Implement `log_chat()` in database.py
- Write unit tests

**Phase 2**: Remove xfail (15 minutes)
- Remove marker from test_query_user_stats_via_nats
- Run test, verify pass
- If fail: document and restore xfail

**Phase 3**: CI Integration (1 hour)
- Create benchmarks.yml workflow
- Test with manual dispatch
- Validate artifacts upload

**Phase 4**: CPU Investigation (3 hours)
- Profile NATS operations
- Identify hotspots
- Write analysis document

---

## Related Documents

- Sprint 10 Retrospective: Performance baseline (0.090ms NATS latency)
- Sprint 10 PRD: Test Infrastructure Completion
- Sprint 10 Sortie 4 SPEC: Performance Benchmarks Infrastructure

---

**Document Version**: 1.0  
**Created**: November 22, 2025  
**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Status**: Ready for Implementation ✅
