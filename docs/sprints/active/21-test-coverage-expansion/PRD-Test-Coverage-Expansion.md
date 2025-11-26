# Sprint 21: Test Coverage Expansion

**Status:** Planning  
**Start Date:** November 26, 2025  
**Target Completion:** TBD  
**Sprint Type:** Quality & Infrastructure  

---

## Executive Summary

Sprint 20 delivered a clean v1.0 architecture with 43 passing tests (100% pass rate), but only 46% code coverage. This sprint focuses on expanding test coverage to achieve 80%+ coverage across core infrastructure, ensuring v1.0 is production-ready with confidence.

### Current State
- **Test Suite:** 43 tests (6 integration, 37 unit)
- **Pass Rate:** 100% (43/43 passing)
- **Coverage:** 46% overall
- **Coverage by Module:**
  - `core/__init__.py`: 100% (9 statements)
  - `core/event_bus.py`: 50% (212 statements, 105 missed)
  - `core/cytube_connector.py`: 58% (218 statements, 91 missed)
  - `core/router.py`: 44% (200 statements, 111 missed)
  - `core/plugin_manager.py`: 47% (265 statements, 140 missed)
  - `core/plugin_isolation.py`: 34% (337 statements, 222 missed)
  - `core/plugin_permissions.py`: 47% (186 statements, 98 missed)
  - `core/subjects.py`: 43% (153 statements, 87 missed)

### Target State
- **Test Suite:** 120+ tests
- **Pass Rate:** 100% (maintained)
- **Coverage:** 80%+ overall
- **Focus Areas:** Error paths, edge cases, integration scenarios

---

## Problem Statement

### Current Coverage Gaps

**1. EventBus (50% → 80% target)**
- Missing: JetStream operations, error callbacks, reconnection logic
- Missing: Stream creation, subscription management, connection lifecycle
- Critical paths: Error handling, timeout scenarios, disconnection recovery

**2. CytubeConnector (58% → 80% target)**
- Missing: Event handler registration/unregistration
- Missing: All cytube event handlers (_on_queue, _on_playlist, etc.)
- Missing: Command routing to Cytube (_skip_video, _take_leader)
- Critical paths: Connection errors, WebSocket failures

**3. Router (44% → 80% target)**
- Missing: Route pattern matching (EXACT, PREFIX, SUFFIX, CONTAINS, REGEX)
- Missing: Route rule management (add/remove rules)
- Missing: Message routing logic (_route_by_rules, _route_to_fallbacks)
- Missing: Plugin response handling
- Critical paths: Command parsing, routing decisions, fallback behavior

**4. PluginManager (47% → 80% target)**
- Missing: Plugin dependency resolution
- Missing: Load order calculation (topological sort)
- Missing: Bulk operations (start_all, stop_all, restart_all)
- Missing: Callback notification system
- Critical paths: Dependency failures, circular dependencies, start failures

**5. PluginIsolation (34% → 70% target)**
- Missing: Process lifecycle management
- Missing: Resource monitoring and limits
- Missing: IPC (inter-process communication)
- Missing: Restart logic and backoff strategies
- High complexity: Multi-process plugin execution (may defer to Sprint 22)

**6. PluginPermissions (47% → 80% target)**
- Missing: Permission grant/deny/revoke operations
- Missing: Permission profile enforcement
- Missing: Audit log functionality
- Critical paths: Permission violations, denied operations

**7. Subjects (43% → 70% target)**
- Missing: Subject builder functions
- Missing: Pattern validation
- Missing: Wildcard matching helpers
- Lower priority: Utility functions, not critical paths

---

## Success Criteria

### Quantitative Metrics
- [ ] **Overall coverage:** 80%+ (from 46%)
- [ ] **EventBus coverage:** 80%+ (from 50%)
- [ ] **CytubeConnector coverage:** 80%+ (from 58%)
- [ ] **Router coverage:** 80%+ (from 44%)
- [ ] **PluginManager coverage:** 80%+ (from 47%)
- [ ] **PluginIsolation coverage:** 70%+ (from 34%)
- [ ] **PluginPermissions coverage:** 80%+ (from 47%)
- [ ] **Subjects coverage:** 70%+ (from 43%)
- [ ] **Test count:** 120+ tests (from 43)
- [ ] **Pass rate:** 100% maintained

### Qualitative Goals
- [ ] All critical error paths tested
- [ ] All public APIs have happy path tests
- [ ] At least one failure scenario per major operation
- [ ] Integration tests cover full command flows
- [ ] Mock-based tests don't require NATS/CyTube
- [ ] Tests run in <5 seconds
- [ ] CI pipeline validates all tests on every commit

---

## Scope

### In Scope

**Phase 1: EventBus & Core Communication (Priority: Critical)**
- JetStream publish/subscribe tests
- Connection lifecycle tests (connect, disconnect, reconnect)
- Error callback tests
- Request/reply timeout scenarios
- Subscription management tests

**Phase 2: Router & Command Dispatch (Priority: Critical)**
- Pattern matching tests (all 5 types)
- Route rule management tests
- Command routing tests (platform → plugin)
- Plugin response routing tests (plugin → platform)
- Fallback plugin tests
- Unknown command handling

**Phase 3: PluginManager Lifecycle (Priority: High)**
- Plugin loading with dependencies
- Start/stop with dependency checking
- Bulk operations (start_all, stop_all)
- Dependency resolution (load order calculation)
- Plugin state transitions
- Callback notifications

**Phase 4: CytubeConnector (Priority: High)**
- All event handler tests (_on_chat_message, _on_user_join, etc.)
- Handler registration/unregistration
- Event translation to EventBus
- Command execution tests (_send_chat_message, etc.)
- Error handling in event processing

**Phase 5: PluginPermissions (Priority: Medium)**
- Permission grant/deny/revoke operations
- Profile-based permission checks
- Permission violation handling
- Audit log tests
- Custom permission sets

**Phase 6: Subjects & Helpers (Priority: Low)**
- Subject builder function tests
- Pattern validation tests
- Wildcard matching tests

### Out of Scope (Defer to Sprint 22)
- PluginIsolation process management (complex, requires refactoring)
- Multi-process plugin execution tests
- Resource monitoring and limit enforcement
- IPC mechanism tests
- Plugin hot-reload without restart
- Performance benchmarking
- Stress testing (1000+ commands/sec)

---

## Technical Approach

### Testing Strategy

**1. Unit Test Philosophy**
- Mock external dependencies (NATS, WebSocket, filesystem)
- Test one component at a time in isolation
- Focus on public API contracts, not implementation details
- Use fixtures for common setup (already in conftest.py)

**2. Integration Test Philosophy**
- Test component interactions (EventBus ↔ Router ↔ PluginManager)
- Use real Event objects, minimal mocking
- Validate end-to-end flows (command in → response out)
- Keep integration tests fast (<1s each)

**3. Coverage Targets by Priority**
- **Critical paths:** 100% (error handling, main flows)
- **Public APIs:** 90% (all documented methods)
- **Private methods:** 60% (tested via public API usage)
- **Edge cases:** 80% (boundary conditions, invalid inputs)

### Test Organization

```
tests/
├── conftest.py                    # Global fixtures (existing)
├── unit/
│   ├── test_event_bus.py          # Expand from 12 → 30 tests
│   ├── test_router.py             # Expand from 7 → 25 tests
│   ├── test_plugin_manager.py     # Expand from 11 → 30 tests
│   ├── test_cytube_connector.py   # Expand from 14 → 25 tests
│   ├── test_plugin_permissions.py # NEW: 20 tests
│   └── test_subjects.py           # NEW: 15 tests
├── integration/
│   ├── test_chat_flow.py          # Expand from 7 → 15 tests
│   ├── test_plugin_lifecycle.py   # NEW: 10 tests
│   └── test_error_recovery.py     # NEW: 10 tests
└── fixtures/
    ├── mock_plugins.py            # NEW: Mock plugin implementations
    └── test_data.py               # NEW: Test data generators
```

**Test Count Projection:**
- EventBus: 12 → 30 tests (+18)
- Router: 7 → 25 tests (+18)
- PluginManager: 11 → 30 tests (+19)
- CytubeConnector: 14 → 25 tests (+11)
- PluginPermissions: 0 → 20 tests (+20)
- Subjects: 0 → 15 tests (+15)
- Integration: 7 → 35 tests (+28)
- **Total:** 43 → 180 tests (+137)

---

## Implementation Plan

### Sortie 1: EventBus Deep Testing (Target: 80% coverage)

**Scope:** Add 18 tests to cover missing EventBus functionality

**Tasks:**
1. JetStream operations (publish_js, create_stream)
2. Connection lifecycle (connect errors, disconnect cleanup)
3. Subscription management (unsubscribe, multiple subscriptions)
4. Error callbacks (_error_cb, _disconnected_cb, _reconnected_cb)
5. Request/reply timeouts
6. Edge cases (publish when disconnected, subscribe before connect)

**Deliverable:** 30 total EventBus tests, 80%+ coverage

**Estimated Time:** 4 hours

---

### Sortie 2: Router Command Dispatch (Target: 80% coverage)

**Scope:** Add 18 tests to cover routing logic

**Tasks:**
1. Pattern matching tests (EXACT, PREFIX, SUFFIX, CONTAINS, REGEX)
2. Route rule management (add_rule, remove_rule)
3. Command handler registration (add_command_handler, remove_command_handler)
4. Message routing (_route_by_rules, _route_to_plugin)
5. Fallback routing (_route_to_fallbacks)
6. Plugin response routing (_handle_plugin_response)
7. Edge cases (no matching route, invalid regex, stopped plugin)

**Deliverable:** 25 total Router tests, 80%+ coverage

**Estimated Time:** 5 hours

---

### Sortie 3: PluginManager Lifecycle (Target: 80% coverage)

**Scope:** Add 19 tests to cover plugin orchestration

**Tasks:**
1. Plugin loading with dependencies
2. Dependency resolution (get_load_order, check_dependencies)
3. Start/stop with dependency checks
4. Bulk operations (start_all, stop_all, restart_all)
5. Callback notifications (plugin_loaded, plugin_started, etc.)
6. Error scenarios (missing dependencies, start failures, circular deps)
7. Plugin info queries (get_plugin_info, get_statistics)

**Deliverable:** 30 total PluginManager tests, 80%+ coverage

**Estimated Time:** 6 hours

---

### Sortie 4: CytubeConnector Events (Target: 80% coverage)

**Scope:** Add 11 tests to cover Cytube event handling

**Tasks:**
1. Event handler registration (_register_cytube_handlers)
2. All cytube event handlers:
   - _on_playlist
   - _on_queue  
   - _on_user_count
3. Handler cleanup (_unregister_cytube_handlers)
4. Command execution (_skip_video, _take_leader)
5. Error handling in event processing
6. Statistics tracking

**Deliverable:** 25 total CytubeConnector tests, 80%+ coverage

**Estimated Time:** 4 hours

---

### Sortie 5: PluginPermissions (Target: 80% coverage)

**Scope:** Add 20 tests for new component

**Tasks:**
1. Permission grant/deny/revoke operations
2. Profile-based permission checks (RESTRICTED, STANDARD, ELEVATED, PRIVILEGED)
3. Permission validation (can_execute, check_permission)
4. Custom permission sets
5. Audit log functionality
6. Error scenarios (permission violations, invalid permissions)

**Deliverable:** 20 new PluginPermissions tests, 80%+ coverage

**Estimated Time:** 5 hours

---

### Sortie 6: Integration & Edge Cases (Target: 35 integration tests)

**Scope:** Add 28 integration tests

**Tasks:**
1. Expand chat_flow tests (+8 tests)
   - Error recovery flows
   - Multiple plugins handling same command
   - Plugin unavailable scenarios
2. Plugin lifecycle integration (+10 tests)
   - Load → Start → Command → Response → Stop flow
   - Dependency chain startup
   - Graceful degradation when plugin crashes
3. Error recovery integration (+10 tests)
   - NATS disconnection during command
   - Plugin crash during command processing
   - Timeout scenarios
   - Invalid event data handling

**Deliverable:** 35 total integration tests, real-world scenarios covered

**Estimated Time:** 6 hours

---

### Sortie 7: Subjects & Utilities (Target: 70% coverage)

**Scope:** Add 15 tests for helper functions

**Tasks:**
1. Subject builder tests (build_platform_subject, build_plugin_subject, etc.)
2. Pattern validation tests
3. Wildcard matching tests
4. Edge cases (empty strings, special characters)

**Deliverable:** 15 new Subjects tests, 70%+ coverage

**Estimated Time:** 2 hours

---

## Timeline

**Total Estimated Time:** 32 hours (4 days @ 8 hours/day)

| Sortie | Component | Tests Added | Coverage Target | Time | Dependencies |
|--------|-----------|-------------|-----------------|------|--------------|
| 1 | EventBus | +18 | 80% | 4h | None |
| 2 | Router | +18 | 80% | 5h | Sortie 1 (EventBus) |
| 3 | PluginManager | +19 | 80% | 6h | Sortie 1 |
| 4 | CytubeConnector | +11 | 80% | 4h | Sortie 1 |
| 5 | PluginPermissions | +20 | 80% | 5h | None |
| 6 | Integration | +28 | N/A | 6h | Sortie 1-5 |
| 7 | Subjects | +15 | 70% | 2h | None |

**Parallelization Opportunities:**
- Sortie 1 and Sortie 5 can run in parallel (no dependencies)
- Sortie 4 and Sortie 5 can run in parallel
- Sortie 7 can run anytime (independent)

**Critical Path:** Sortie 1 → Sortie 2 → Sortie 6 (15 hours)

---

## Risks & Mitigations

### Risk 1: Complex Mocking Requirements
**Likelihood:** High  
**Impact:** Medium  
**Description:** Some components (EventBus, CytubeConnector) require complex mocking of external systems (NATS, WebSocket)

**Mitigation:**
- Reuse existing mock fixtures from conftest.py
- Create dedicated mock helpers for NATS messages
- Use pytest-mock for spy/stub patterns where appropriate
- Document mock patterns in test docstrings

### Risk 2: Slow Test Execution
**Likelihood:** Medium  
**Impact:** High  
**Description:** 180 tests could exceed 5-second target, slowing development

**Mitigation:**
- Use pytest-xdist for parallel test execution
- Minimize setup/teardown in fixtures (use module/session scope where safe)
- Mock external I/O (no real NATS connections)
- Profile slow tests and optimize
- Set pytest timeout markers (--timeout=2 per test)

### Risk 3: Brittle Tests Due to Implementation Details
**Likelihood:** Medium  
**Impact:** High  
**Description:** Tests that check private methods break during refactoring

**Mitigation:**
- Test only public APIs in unit tests
- Use integration tests for internal interactions
- Mock at component boundaries, not internal methods
- Follow "test behavior, not implementation" principle
- Review tests during code reviews for brittleness

### Risk 4: Insufficient Coverage of Error Paths
**Likelihood:** Medium  
**Impact:** High  
**Description:** Focusing on happy paths, missing error scenarios

**Mitigation:**
- Each public method requires 1 success + 1 failure test minimum
- Use pytest.raises for exception testing
- Dedicated error handling tests per sortie
- Code review checklist includes "error paths tested?"
- Track error path coverage separately in reports

### Risk 5: Test Maintenance Burden
**Likelihood:** Medium  
**Impact:** Medium  
**Description:** 180 tests may become maintenance burden if poorly structured

**Mitigation:**
- Strong fixture reuse (conftest.py patterns)
- Parametrized tests for similar scenarios
- Clear test naming (test_<method>_<scenario>_<expected>)
- Organize tests in logical modules
- Document complex test setups
- Regular test refactoring sprints

---

## Dependencies

### Technical Dependencies
- pytest 7.4.4+ (already installed)
- pytest-asyncio 0.23.8+ (already installed)
- pytest-cov 7.0.0+ (already installed)
- coverage 7.12.0+ (already installed, fixed in Sprint 20)
- pytest-mock (may need to install)
- pytest-timeout (may need to install)
- pytest-xdist (may need to install for parallelization)

### Code Dependencies
- All Sortie 2-4 tests depend on EventBus tests (Sortie 1) being complete
- Integration tests (Sortie 6) depend on all unit tests (Sortie 1-5)
- No external service dependencies (NATS, CyTube mocked)

---

## Acceptance Criteria

### Sprint Complete When:
1. **Coverage targets met:**
   - [ ] Overall: 80%+ (from 46%)
   - [ ] EventBus: 80%+
   - [ ] Router: 80%+
   - [ ] PluginManager: 80%+
   - [ ] CytubeConnector: 80%+
   - [ ] PluginPermissions: 80%+
   - [ ] Subjects: 70%+

2. **Test suite quality:**
   - [ ] 120+ tests total (from 43)
   - [ ] 100% pass rate maintained
   - [ ] All tests run in <5 seconds
   - [ ] No test flakiness (0 intermittent failures)
   - [ ] CI pipeline green

3. **Documentation complete:**
   - [ ] All new test modules have docstrings
   - [ ] Complex mocks documented in conftest.py
   - [ ] Coverage gaps identified for Sprint 22
   - [ ] Test execution guide in docs/TESTING.md

4. **Code quality:**
   - [ ] All tests follow naming conventions
   - [ ] No duplicate test logic (use fixtures/parametrize)
   - [ ] No TODOs or skipped tests (@pytest.skip removed)
   - [ ] No commented-out test code

---

## Open Questions

1. **PluginIsolation Testing Strategy:**
   - Q: Should we test process-based isolation now or defer to Sprint 22?
   - A: Defer to Sprint 22. Current 34% coverage is acceptable for process management. Focus on API contracts now.

2. **Integration Test Scope:**
   - Q: How deep should integration tests go? Full plugin execution?
   - A: No real plugin execution. Mock plugin responses. Test component wiring only.

3. **Performance Testing:**
   - Q: Should we include performance benchmarks in this sprint?
   - A: No. Sprint 21 is functional correctness. Sprint 22 can add performance tests.

4. **Mocking Philosophy:**
   - Q: Mock at component boundaries or use real objects where possible?
   - A: Mock external systems (NATS, WebSocket). Use real internal objects (Event, PluginMetadata).

5. **Test Data Management:**
   - Q: Should we create test data fixtures or generate inline?
   - A: Create fixtures/test_data.py for complex test data. Inline for simple cases.

---

## Success Metrics

### Quantitative Metrics (Must-Have)
- Overall coverage: 80%+ ✓
- Test count: 120+ ✓
- Pass rate: 100% ✓
- Test execution time: <5 seconds ✓
- Zero skipped/xfailed tests ✓

### Qualitative Metrics (Nice-to-Have)
- Test readability score: 8/10+ (peer review)
- Test maintainability: No duplicate logic
- Error path coverage: 80%+ of error handlers tested
- CI reliability: 0 flaky tests over 10 runs

---

## Future Enhancements (Sprint 22+)

### Deferred from Sprint 21
- PluginIsolation deep testing (process management, IPC, resource limits)
- Performance benchmarks (throughput, latency, memory)
- Stress testing (sustained load, concurrent commands)
- Chaos testing (random failures, network partitions)

### Potential Sprint 22 Goals
- 90%+ overall coverage
- Property-based testing (Hypothesis library)
- Mutation testing (validating test quality)
- Contract testing (NATS subject contracts)
- Load testing framework

---

## References

### Related Documents
- [Sprint 20 PRD: v1.0 Release Ready](./20-v1-release-ready/PRD-Release-Ready-v1.md)
- [Sprint 20 Sortie 3 Spec: Test Migration](./20-v1-release-ready/SPEC-Sortie-3-Test-Migration.md)
- [v1.0 Architecture Documentation](../../ARCHITECTURE.md)
- [NATS Contracts Reference](../../NATS-CONTRACTS.md)

### External Resources
- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Guide](https://pytest-asyncio.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)

---

## Appendix: Current Coverage Report

```
Name                         Stmts   Miss  Cover   Missing
------------------------------------------------------
core/__init__.py                 9      0   100%
core/cytube_connector.py       218     91    58%
core/event_bus.py              212    105    50%
core/plugin_isolation.py       337    222    34%
core/plugin_manager.py         265    140    47%
core/plugin_permissions.py     186     98    47%
core/router.py                 200    111    44%
core/subjects.py               153     87    43%
------------------------------------------------------
TOTAL                         1580    854    46%
```

**Generated:** November 26, 2025  
**Last Updated:** November 26, 2025  
**Status:** Draft for Review
