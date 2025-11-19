# PRD: Comprehensive Test Coverage

**Sprint:** nano-sprint/4-test-assured  
**Status:** Planning  
**Priority:** High (Technical Debt Reduction)

---

## Problem Statement

Rosey has grown significantly with new features (LLM integration, database tracking, shell commands, and planned REST API), but test coverage has been minimal to maintain development velocity. We now need comprehensive test coverage before technical debt accumulates and makes testing more difficult.

**Current State:**
- Minimal existing tests (legacy shell test script only)
- No pytest infrastructure
- No coverage reporting
- New features (LLM, database) untested
- Risk of regressions when making changes

**Desired State:**
- pytest-based test suite with >85% coverage (minimum 66%)
- Unit tests for all core components
- Integration tests for critical workflows
- Coverage reporting integrated into development workflow
- Confidence to refactor and extend codebase

---

## Goals & Success Metrics

### Primary Goals
1. **Establish pytest infrastructure** with proper configuration
2. **Achieve 85%+ test coverage** across the codebase (66% minimum acceptable)
3. **Unit test all core components** (lib/, common/, bot logic)
4. **Integration tests** for key workflows (database, bot lifecycle)
5. **CI-ready** tests that can run in automated pipelines

### Success Metrics

- ✅ pytest runs successfully with 0 warnings
- ✅ Coverage report shows >85% overall (stretch: 90%)
- ✅ All critical paths covered (bot startup, message handling, database ops)
- ✅ Clear documentation on running and writing tests

---

## Test Coverage Priority

### 1. Core Library (lib/) - **HIGHEST PRIORITY**
- `lib/bot.py` - Bot class, connection handling, event system
- `lib/channel.py` - Channel state, user management
- `lib/user.py` - User class and rank handling
- `lib/util.py` - MessageParser and utility functions
- `lib/socket_io.py` - SocketIO communication
- `lib/media_link.py` - Media URL parsing and validation
- `lib/playlist.py` - Playlist management

**Why First:** Core library is the foundation; bugs here affect everything.

### 2. Database (common/database.py) - **HIGH PRIORITY**
- Database class initialization
- User tracking (log_user_action, get_or_create_user)
- Statistics queries
- Media logging
- Connection handling and error cases

**Why Second:** Data integrity is critical; database bugs can corrupt data.

### 3. Shell Commands (common/shell.py) - **MEDIUM PRIORITY**
- Command parsing and routing
- PM command handling and rank validation
- Individual commands (help, info, status, say, playlist, users)
- Error handling
- Long message splitting

**Why Third:** Shell is stable but heavily used; good to have coverage.

### 4. REST API (web/*) - **MEDIUM PRIORITY**
- FastAPI endpoints (once Sprint 3 implemented)
- Authentication middleware
- Bot interface
- Error handling
- Status server

**Why Fourth:** New code, easier to test while fresh in memory.

### 5. LLM Integration (lib/llm/) - **LOWER PRIORITY**
- LLMClient basic functionality
- Provider initialization
- Trigger system
- Error handling for API failures

**Why Last:** Already has manual test scripts; less critical to core bot operation.

---

## Technical Approach

### Test Framework Stack
- **pytest** - Main test runner
- **pytest-cov** - Coverage reporting
- **pytest-asyncio** - Async test support
- **pytest-mock** - Enhanced mocking capabilities
- **pytest-timeout** - Prevent hanging tests

### Test Organization
```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests (isolated components)
│   ├── __init__.py
│   ├── test_bot.py
│   ├── test_channel.py
│   ├── test_user.py
│   ├── test_util.py
│   ├── test_media_link.py
│   ├── test_playlist.py
│   ├── test_database.py
│   └── test_shell.py
├── integration/             # Integration tests (multiple components)
│   ├── __init__.py
│   ├── test_bot_lifecycle.py
│   ├── test_database_integration.py
│   └── test_shell_integration.py
└── fixtures/                # Test data files
    ├── sample_config.json
    └── test_playlist.txt
```

### Configuration Files
- `pytest.ini` - pytest configuration
- `.coveragerc` - Coverage configuration
- `conftest.py` - Shared fixtures and test utilities

### Mock Strategy
- **External services** - Mock websocket connections, HTTP requests, LLM APIs
- **Database** - Use in-memory SQLite for fast tests
- **Time-dependent code** - Mock time.time(), datetime
- **File I/O** - Use temporary directories and pytest's tmp_path fixture

---

## Test Categories

### Unit Tests

**Focus:** Single function/class in isolation  
**Characteristics:**

- No external dependencies
- Mock all I/O and network
- Test edge cases and error conditions

**Example Coverage:**

- `MessageParser.parse()` with various input formats
- `User` rank comparison operators
- `MediaLink.from_url()` with valid/invalid URLs
- Shell command parsing logic

### Integration Tests

**Focus:** Multiple components working together  
**Characteristics:**

- May use real database (in-memory)
- Test realistic workflows
- Verify component interactions

**Example Coverage:**

- Bot connects, receives events, logs to database
- Shell command executes and modifies bot state
- Database transaction rollback on error
- User rank changes propagate through system

---

## Coverage Targets by Module

| Module | Target Coverage | Minimum Acceptable | Priority |
|--------|----------------|-------------------|----------|
| lib/bot.py | 90% | 75% | 1 |
| lib/channel.py | 90% | 75% | 1 |
| lib/user.py | 95% | 80% | 1 |
| lib/util.py | 95% | 85% | 1 |
| common/database.py | 90% | 70% | 2 |
| common/shell.py | 85% | 65% | 3 |
| lib/socket_io.py | 80% | 60% | 1 |
| lib/media_link.py | 95% | 85% | 1 |
| lib/playlist.py | 90% | 70% | 1 |
| lib/llm/* | 75% | 50% | 5 |
| web/* | 80% | 60% | 4 |

**Overall Target:** 85% minimum, 90% stretch goal

---

## Implementation Plan

### Phase 1: Infrastructure Setup
1. Create `tests/` directory structure
2. Add pytest dependencies to requirements.txt
3. Configure pytest.ini and .coveragerc
4. Create conftest.py with base fixtures
5. Set up coverage reporting

**Deliverable:** `pytest` and `pytest-cov` commands work

### Phase 2: Core Library Unit Tests
6. Test lib/user.py (simplest, good starting point)
7. Test lib/util.py (MessageParser)
8. Test lib/media_link.py
9. Test lib/playlist.py
10. Test lib/channel.py
11. Test lib/bot.py (most complex)

**Deliverable:** >85% coverage of lib/

### Phase 3: Database Tests
12. Create in-memory database fixtures
13. Test database.py CRUD operations
14. Test transaction handling
15. Test edge cases (duplicate users, etc.)

**Deliverable:** >70% coverage of common/database.py

### Phase 4: Shell Command Tests
16. Test command parsing
17. Test individual commands with mocked bot
18. Test PM command rank validation
19. Test error handling

**Deliverable:** >65% coverage of common/shell.py

### Phase 5: Integration Tests
20. Bot lifecycle (connect, disconnect, reconnect)
21. Database integration (bot events → database)
22. Shell integration (commands modify bot state)
23. Error recovery scenarios

**Deliverable:** Integration test suite passes

### Phase 6: Documentation & CI
24. Write TESTING.md guide
25. Update README with test instructions
26. Create GitHub Actions workflow (optional)
27. Add coverage badge (optional)

**Deliverable:** Clear testing documentation

---

## Technical Challenges

### Challenge 1: Async Code Testing
**Problem:** Bot is heavily async/await based  
**Solution:** Use pytest-asyncio, mark tests with `@pytest.mark.asyncio`

### Challenge 2: WebSocket Mocking
**Problem:** Bot connects to CyTube via websockets  
**Solution:** Mock websocket at transport level, use pytest-mock

### Challenge 3: Database State
**Problem:** Tests interfere with each other via shared DB  
**Solution:** Use in-memory SQLite, rollback transactions after each test

### Challenge 4: Time-Dependent Code
**Problem:** Uptime calculations, timestamps  
**Solution:** Mock time.time() and datetime.now(), use freezegun

### Challenge 5: External Dependencies
**Problem:** LLM API calls, HTTP requests  
**Solution:** Mock at httpx/aiohttp level, use responses library

---

## Non-Goals (Out of Scope)

- ❌ End-to-end tests with real CyTube server
- ❌ Performance/load testing (not a focus unless tests exceed 3-5 minutes)
- ❌ UI/visual regression tests
- ❌ Security/penetration testing
- ❌ Testing legacy code in _old/ directory
- ❌ 100% test coverage (diminishing returns)
- ❌ CI/CD integration (planned for future sprint)

---

## Dependencies & Requirements

### Python Packages (add to requirements.txt)
```
# Testing dependencies
pytest>=8.2.2
pytest-asyncio>=0.23.0
pytest-cov>=5.0.0
pytest-mock>=3.14.0
pytest-timeout>=2.3.0
freezegun>=1.5.0  # For mocking time
httpx>=0.27.0     # For testing HTTP in async code
```

### Development Environment
- Python 3.9+ (async features)
- No external services required for tests
- Can run on any platform (Windows/Linux/macOS)

---

## Documentation Deliverables

1. **TESTING.md** - Comprehensive testing guide
   - How to run tests
   - How to write new tests
   - Fixture documentation
   - Best practices

2. **README.md updates** - Add testing section
   - Quick start: `pytest`
   - Coverage: `pytest --cov`
   - Single file: `pytest tests/unit/test_user.py`

3. **Inline Documentation** - Docstrings for fixtures and utilities

---

## Success Criteria Checklist

- [ ] pytest infrastructure set up and working
- [ ] Coverage reporting configured and running
- [ ] lib/ modules at >85% coverage
- [ ] common/database.py at >70% coverage
- [ ] common/shell.py at >65% coverage
- [ ] Integration tests for critical workflows
- [ ] All tests pass consistently
- [ ] TESTING.md documentation complete
- [ ] README.md updated with test instructions
- [ ] Zero pytest warnings or errors

---

## Timeline Estimate

**Total Effort:** ~40-50 commits over multiple sessions

- Phase 1 (Infrastructure): 5 commits
- Phase 2 (Core Library): 15-20 commits
- Phase 3 (Database): 5-7 commits
- Phase 4 (Shell): 5-7 commits
- Phase 5 (Integration): 5-7 commits
- Phase 6 (Documentation): 3-5 commits

**Note:** This is a larger sprint than previous ones due to the breadth of coverage needed. Can be broken into sub-sprints if needed.

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Tests take too long to run | High | Focus on unit tests, minimize I/O |
| Brittle tests break on refactoring | Medium | Test behavior not implementation |
| Coverage metric becomes goal | Medium | Focus on meaningful tests, not just coverage |
| Mocking complexity slows development | Medium | Create reusable fixtures in conftest.py |
| Async test debugging is hard | Low | Use pytest -v for verbose output |

---

## Future Enhancements (Post-Sprint)

- Mutation testing (pytest-mutpy) to verify test quality
- Property-based testing (hypothesis) for edge cases
- GitHub Actions CI/CD integration
- Coverage reporting in PRs
- Benchmark tests for performance regression
- Contract tests for REST API (once implemented)

---

## Questions for Stakeholder

1. ✅ Pytest vs unittest? → **pytest**
2. ✅ Target coverage? → **85% target, 66% minimum**
3. ✅ Priority order? → **Core, Database, Shell, API, LLM**
4. ✅ Should we test legacy code in _old/? → **NO**
5. ✅ Do we need CI/CD integration in this sprint? → **Not this sprint, but soon!**
6. ✅ Any specific bugs or edge cases to prioritize? → **None currently**
7. ✅ Test performance concerns? → **Not a priority; only focus if suite exceeds 3-5 minutes**

---

**Next Steps:** Create detailed SPEC documents for each phase/commit.
