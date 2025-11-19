# Roadmap: Sprints 7-9

**Planning Date:** November 12, 2025  
**Theme:** Refactoring, Extensibility, and Plugin Architecture

## Overview

After completing Sprint 6 "Make It Real" (production deployment), the next three sprints focus on architectural improvements and extensibility through a plugin system.

## Sprint 7: "The Divide" (2011)

**Focus:** Refactor monolithic `lib/bot.py` into focused modules

**Core Objective:** Split the 1000+ line `lib/bot.py` into three separate, maintainable modules with clear separation of concerns.

**Modules to Create:**
1. **`lib/bot.py`** - Core bot logic
   - Command handling and registration
   - Message processing
   - Feature coordination
   - High-level bot behavior

2. **`lib/database.py`** - Database operations
   - Markov chain storage and retrieval
   - Message logging
   - Statistics tracking
   - Database connection management
   - Schema migrations

3. **`lib/connection.py`** - Connection management
   - WebSocket connection handling
   - CyTube protocol implementation
   - Reconnection logic
   - Connection health monitoring

**Key Constraints:**
- Preserve existing API where possible (minimize breaking changes)
- Update imports in dependent files (`bots/markov/bot.py`, etc.)
- Update tests for new module structure
- Update documentation

**Related Issues:** #15 (already created)

---

## Sprint 8: "Inception" (2010)

**Focus:** Build robust plugin architecture

**Core Objective:** Create a comprehensive plugin system with dynamic loading, registration, lifecycle management, and configuration.

**Plugin System Requirements:**
- Plugin discovery and loading mechanism
- Plugin registration and lifecycle hooks (init, start, stop, cleanup)
- Plugin configuration per instance
- Event system for plugin communication
- Error isolation (plugin failures don't crash bot)
- Hot reload capability (optional)
- Plugin metadata and versioning
- Documentation for plugin developers

**Architecture Considerations:**
- Clear plugin interface/base class
- Dependency injection for bot services
- Sandboxing/resource limits (if needed)
- Plugin repository structure

**Deliverables:**
- Plugin framework code
- Plugin developer documentation
- Example skeleton plugin
- Plugin testing utilities

---

## Sprint 9: "Funny Games" (2007)

**Focus:** Battle-test plugin system with experimental plugins

**Core Objective:** Create 3-5 functional plugins using the new plugin interface to validate the architecture and identify issues before migrating existing code.

**Experimental Plugins to Build:**
- Simple utility plugin (e.g., dice roller, 8-ball, coin flip)
- Moderate complexity plugin (e.g., quote database, trivia game)
- Integration plugin (e.g., external API consumer)
- Stateful plugin (e.g., persistent counter, scoreboard)
- Complex plugin (stress test the system)

**Success Criteria:**
- All test plugins install and run successfully
- Plugin isolation verified (one plugin failure doesn't affect others)
- Performance acceptable with multiple plugins loaded
- Developer experience is smooth
- Documentation is sufficient for plugin creation
- Edge cases and limitations identified

**Outcome:**
- Validated plugin architecture
- Documented best practices and gotchas
- List of improvements needed before migration
- Confidence that existing bot functionality can be migrated to plugins

**Note:** Intentionally NOT migrating existing bots (markov, echo, log) to plugins yet. Sprint 9 validates the system with new code first.

---

## Future Considerations (Sprint 10+)

After Sprint 9 validates the plugin architecture:
- **Sprint 10:** Migrate existing bot-specific code to plugins (markov chain bot, etc.)
- **Sprint 11+:** TBD based on Sprint 9 learnings and priorities

---

## Testing Strategy

- **Sprint 7:** Extensive testing of refactored modules (600+ existing tests need updates)
- **Sprint 8:** Plugin framework unit tests, integration tests for plugin loading
- **Sprint 9:** Plugin-specific tests, system tests with multiple plugins

## Documentation Updates

Each sprint requires:
- Updated architecture documentation
- API documentation for new modules/interfaces
- Developer guides (especially Sprint 8 plugin development)
- Updated deployment documentation if needed
