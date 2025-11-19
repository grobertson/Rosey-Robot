# Sprint 6a: Quicksilver - NATS Event Bus Foundation

**Sprint Name:** Quicksilver (like the bike messenger from the movie - fast, connects everything)  
**Priority:** ⚡ CRITICAL - Architectural Foundation  
**Estimated Effort:** 18-22 hours across 8 sorties  
**Dependencies:** None (blocks Sprint 9 implementation)  
**Status:** Planning

---

## Executive Summary

Migrate Rosey from monolithic internal event system to NATS-based message broker architecture. This enables:
- **Plugin isolation** (security boundary for untrusted code)
- **Multi-platform support** (Cytube, Discord, Slack, Twitch)
- **Microservices architecture** (Web UI, API, MediaCMS as separate services)
- **Horizontal scaling** (multiple instances, load balancing)
- **Event persistence** (JetStream for guaranteed delivery)

This sprint lays the architectural foundation for all future multi-platform and integration work.

---

## Problem Statement

### Current Architecture Limitations

**1. Security Risk:**
- Plugins run in same process as bot core
- No isolation between trusted core and untrusted plugins
- Plugin bugs can crash entire bot
- No resource limits on plugin code

**2. Multi-Platform Blocker:**
- Events tightly coupled to Cytube implementation
- No generic event model for other platforms
- Platform-specific features (media, voice, threads) not abstracted
- Adding Discord/Slack requires core refactoring

**3. Integration Constraints:**
- MediaCMS integration must run in bot process
- Web UI coupled to bot lifecycle
- API endpoints mixed with bot logic
- Cannot scale components independently

**4. Operational Limitations:**
- Single point of failure (one process)
- Cannot update plugins without bot restart
- No message persistence (events lost on crash)
- Limited observability into event flow

### Why Now?

**Critical Timing:**
- Sprint 9 plugins not yet implemented (no code to migrate)
- Current codebase still small enough to refactor cleanly
- Every feature built on current architecture = technical debt
- Multi-platform support is roadmap requirement

**Strategic Value:**
- Enables Discord connector (roadmap item)
- Enables Slack connector (future)
- Enables MediaCMS "TV marathon" feature (dream feature)
- Enables mobile/GUI chat applications
- Positions Rosey as multi-platform framework, not just Cytube bot

---

## Goals & Success Criteria

### Primary Goals

1. **Replace Internal Events with NATS**
   - All bot events flow through NATS message broker
   - JetStream enabled for persistence
   - Zero functional regression (transparent to users)

2. **Plugin Isolation Foundation**
   - Plugins run in separate processes
   - Communicate ONLY via NATS
   - Permission system for subject access
   - Resource limits (CPU, memory)

3. **Platform Abstraction Layer**
   - Generic event model (platform-agnostic)
   - Platform connectors as separate services
   - Cytube-specific features in Cytube connector
   - Ready for Discord/Slack connectors

### Success Criteria

✅ NATS server running and monitored  
✅ Event bus library with pub/sub + request/reply  
✅ Cytube events translated to NATS subjects  
✅ Plugin sandbox runner operational  
✅ Test plugin runs isolated with NATS communication  
✅ No functional changes to bot behavior  
✅ Foundation ready for Sprint 9 plugin implementation  

### Non-Goals (Out of Scope)

❌ Implement Sprint 9 plugins (separate sprint)  
❌ Discord/Slack connectors (future sprints)  
❌ MediaCMS integration (future sprint)  
❌ Web UI separation (future sprint)  
❌ Horizontal scaling/clustering (future sprint)  

---

## Technical Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                     NATS Message Broker                     │
│              (Core + JetStream for Persistence)             │
└────────────┬──────────┬──────────┬──────────┬───────────────┘
             │          │          │          │
    ┌────────▼───┐  ┌──▼─────┐ ┌──▼─────┐ ┌──▼──────────┐
    │  Platform  │  │Platform│ │Platform│ │   Plugin    │
    │ Connectors │  │Connect.│ │Connect.│ │   Sandbox   │
    └────────────┘  └────────┘ └────────┘ └─────────────┘
    │ Cytube     │  │Discord │ │ Slack  │ │ Trivia      │
    │ • Chat     │  │ • Text │ │ • Text │ │ Weather     │
    │ • Media    │  │ • Voice│ │ • Thrd │ │ Quotes      │
    │ • Playlist │  │ • React│ │ • React│ │ (isolated)  │
    └─────┬──────┘  └───┬────┘ └───┬────┘ └──────┬──────┘
          │             │          │             │
    ┌─────▼─────────────▼──────────▼─────────────▼──────┐
    │               Core Event Router                    │
    │    • Normalizes platform events                    │
    │    • Routes to appropriate handlers                │
    │    • Enforces security policies                    │
    │    • Command processing & dispatch                 │
    └────────┬──────────┬──────────┬──────────────┬──────┘
             │          │          │              │
       ┌─────▼────┐ ┌──▼──────┐ ┌─▼─────────┐ ┌──▼──────┐
       │   Web    │ │  API    │ │ MediaCMS  │ │   AI    │
       │   UI     │ │ Service │ │ Connector │ │ Service │
       │ (future) │ │ (future)│ │ (future)  │ │ (exists)│
       └──────────┘ └─────────┘ └───────────┘ └─────────┘
```

### NATS Subject Hierarchy

```
rosey.
├── platform.                    # Platform-specific events
│   ├── cytube.
│   │   ├── chat                # Chat messages
│   │   ├── media               # Media changes
│   │   ├── playlist            # Playlist updates
│   │   └── user                # User join/leave
│   ├── discord.
│   │   ├── message             # Discord messages
│   │   ├── reaction            # Reactions
│   │   └── voice               # Voice events
│   └── slack.
│       ├── message             # Slack messages
│       └── thread              # Thread activity
│
├── events.                      # Normalized events
│   ├── message                 # Generic message
│   ├── user.join               # User joined
│   ├── user.leave              # User left
│   └── media.change            # Media changed
│
├── commands.
│   ├── {plugin}.execute        # Execute command
│   └── {plugin}.result         # Command result
│
├── plugins.
│   ├── trivia.>                # Trivia plugin events
│   ├── weather.>               # Weather plugin events
│   ├── quotes.>                # Quotes plugin events
│   └── inspector.>             # Inspector plugin events
│
├── mediacms.                    # MediaCMS integration
│   ├── marathon.create         # Create TV marathon
│   ├── marathon.ready          # Marathon ready
│   └── search                  # Search content
│
├── api.
│   ├── request.>               # API requests
│   └── response.{id}           # API responses
│
├── security.
│   ├── violation               # Security violations
│   └── plugin.restricted       # Plugin access denied
│
└── monitoring.
    ├── health                  # Health checks
    └── metrics                 # Metrics collection
```

### Event Flow Example

**User sends "!trivia start" in Cytube:**

```
1. Cytube WebSocket → CytubeConnector
   ↓
2. CytubeConnector publishes:
   - rosey.platform.cytube.chat (raw Cytube event)
   - rosey.events.message (normalized event)
   ↓
3. Core Event Router subscribes to rosey.events.message
   - Parses command: "trivia start"
   - Publishes: rosey.commands.trivia.execute
   ↓
4. Trivia Plugin (isolated process) subscribed to:
   - rosey.commands.trivia.execute
   - Starts game, publishes: rosey.plugins.trivia.game_started
   ↓
5. Core Router gets game_started event
   - Publishes: rosey.platform.cytube.chat (response)
   ↓
6. CytubeConnector sends response back to Cytube
```

### Plugin Isolation Model

**Security Boundaries:**

```python
# Plugin can ONLY:
✅ Subscribe to:
   - rosey.events.message (read messages)
   - rosey.commands.{plugin_name}.> (own commands)

✅ Publish to:
   - rosey.plugins.{plugin_name}.> (own events)
   - rosey.commands.{plugin_name}.result (command results)

❌ Cannot:
   - Access filesystem (except designated plugin data dir)
   - Access network (except NATS connection)
   - Import dangerous modules (os, subprocess, etc.)
   - Exceed resource limits (256MB RAM, 0.5 CPU)
   - Subscribe to security.> subjects
   - Publish to platform.> subjects
```

### Technology Stack

**NATS Server:**
- **Version:** 2.10+ (latest stable)
- **Binary:** 12MB standalone executable
- **Memory:** ~5MB base + JetStream storage
- **Features:** Core pub/sub + JetStream persistence

**Python Client:**
- **Library:** `nats-py` (official Python client)
- **Version:** 2.7+
- **Async:** Full asyncio support
- **Features:** Pub/sub, request/reply, JetStream

**Configuration:**
- YAML-based NATS server config
- Environment variables for secrets
- Monitoring dashboard on :8222

---

## Implementation Plan

### Sortie Breakdown (8 Sorties, 18-22 hours)

**Sortie 1: NATS Infrastructure** (2-3 hours)
- Install NATS server binary
- Create server configuration
- Set up monitoring dashboard
- Test basic pub/sub

**Sortie 2: Event Bus Core Library** (3-4 hours)
- Implement EventBus class
- Pub/sub methods
- Request/reply pattern
- JetStream integration
- Error handling & reconnection

**Sortie 3: Subject Design & Event Model** (2 hours)
- Define subject hierarchy
- Create Subjects constants
- Implement Event dataclass
- Serialization/deserialization

**Sortie 4: Cytube Connector Extraction** (3-4 hours)
- Extract Cytube logic to connector service
- Translate Cytube events → NATS
- Translate NATS → Cytube actions
- Event normalization layer

**Sortie 5: Core Router Integration** (2-3 hours)
- Update bot initialization for NATS
- Subscribe to normalized events
- Command processing via NATS
- Response publishing

**Sortie 6: Plugin Sandbox Foundation** (3-4 hours)
- Implement sandbox runner process
- PluginInterface with permissions
- Subject access control
- Resource limits (basic)

**Sortie 7: Plugin Manager** (2 hours)
- Plugin lifecycle management
- Start/stop plugins as subprocesses
- Monitor plugin health
- Auto-restart on failure

**Sortie 8: Testing & Validation** (2-3 hours)
- Unit tests for EventBus
- Integration tests (Cytube → NATS → Plugin)
- Load testing (1000 msg/sec)
- Failure scenarios (NATS down, plugin crash)
- Performance profiling

### Milestones

**M1: NATS Running** (After Sortie 1)
- NATS server operational
- Monitoring dashboard accessible
- Basic pub/sub confirmed

**M2: Event Bus Ready** (After Sortie 3)
- EventBus library complete
- Subject hierarchy defined
- Event model implemented

**M3: Cytube Migrated** (After Sortie 5)
- Cytube events flow through NATS
- Bot responds to commands via NATS
- No functional regression

**M4: Plugins Isolated** (After Sortie 7)
- Test plugin runs in sandbox
- Permission system enforced
- Plugin manager operational

**M5: Sprint Complete** (After Sortie 8)
- All tests passing
- Documentation complete
- Ready for Sprint 9 implementation

---

## Risk Assessment

### Technical Risks

**Risk 1: NATS Learning Curve**
- **Probability:** Medium
- **Impact:** Low
- **Mitigation:** NATS is well-documented, Python client is mature
- **Contingency:** Redis pub/sub as fallback (less features)

**Risk 2: Performance Overhead**
- **Probability:** Low
- **Impact:** Medium
- **Mitigation:** NATS is extremely fast (millions msg/sec)
- **Testing:** Load test with 1000 msg/sec (10x expected load)

**Risk 3: Plugin Sandbox Escape**
- **Probability:** Low
- **Impact:** High
- **Mitigation:** Process isolation + subject permissions + resource limits
- **Future:** Container-based isolation (Docker) for maximum security

**Risk 4: Event Ordering Issues**
- **Probability:** Medium
- **Impact:** Medium
- **Mitigation:** JetStream guarantees order within subject
- **Testing:** Validate command processing order

**Risk 5: Migration Bugs**
- **Probability:** Medium
- **Impact:** High
- **Mitigation:** Comprehensive test suite, gradual rollout
- **Rollback:** Keep old event system until NATS proven stable

### Operational Risks

**Risk 1: NATS Server Downtime**
- **Probability:** Low
- **Impact:** High (bot stops working)
- **Mitigation:** NATS auto-reconnect, bot graceful degradation
- **Future:** NATS clustering for HA

**Risk 2: Message Backlog**
- **Probability:** Low
- **Impact:** Medium
- **Mitigation:** JetStream retention limits, monitoring
- **Monitoring:** Track queue depth, alert on buildup

---

## Testing Strategy

### Unit Tests

```python
# test_event_bus.py
- test_connect()
- test_publish()
- test_subscribe()
- test_request_reply()
- test_jetstream_persistence()
- test_reconnection()
- test_error_handling()

# test_subjects.py
- test_subject_patterns()
- test_wildcard_matching()

# test_plugin_sandbox.py
- test_plugin_initialization()
- test_permission_enforcement()
- test_allowed_subscriptions()
- test_denied_publications()
- test_resource_limits()
```

### Integration Tests

```python
# test_cytube_integration.py
- test_chat_message_flow()
- test_media_change_flow()
- test_command_execution()
- test_plugin_response()

# test_end_to_end.py
- test_full_command_cycle()
  (Cytube → Connector → Router → Plugin → Response)
```

### Performance Tests

```python
# test_performance.py
- test_message_throughput()  # Target: 1000 msg/sec
- test_latency()             # Target: <10ms p99
- test_memory_usage()        # Target: <100MB increase
- test_concurrent_plugins()  # 5 plugins simultaneously
```

### Failure Scenario Tests

```python
# test_failures.py
- test_nats_disconnect()
- test_nats_reconnect()
- test_plugin_crash()
- test_plugin_timeout()
- test_message_loss_recovery()
```

---

## Documentation Requirements

### User-Facing Docs

1. **NATS-MIGRATION.md**
   - Migration guide for existing code
   - Pattern changes (old → new)
   - Plugin migration guide

2. **PLUGIN-DEVELOPMENT.md**
   - How to write sandboxed plugins
   - Available interfaces
   - Permission system
   - Resource limits

### Developer Docs

1. **ARCHITECTURE.md** (update)
   - Add NATS architecture section
   - Event flow diagrams
   - Subject hierarchy

2. **NATS-SETUP.md**
   - NATS server installation
   - Configuration options
   - Monitoring dashboard

3. **EVENT-BUS-API.md**
   - EventBus class reference
   - Code examples
   - Best practices

---

## Future Enhancements (Post-Sprint)

### Sprint 11+: Build on Foundation

1. **Discord Connector** (Sprint 11)
   - Discord.py integration
   - Event normalization
   - Voice channel support

2. **MediaCMS Integration** (Sprint 12)
   - API connector
   - TV marathon generator (AI-powered)
   - Playlist synchronization

3. **Web UI Service** (Sprint 13)
   - Separate web service
   - Real-time updates via NATS
   - Mobile-friendly interface

4. **Plugin Marketplace** (Future)
   - Community plugin repository
   - Plugin signing & verification
   - One-click installation

5. **Horizontal Scaling** (Future)
   - Multiple bot instances
   - Load balancing via queue groups
   - Shared state in Redis

---

## Resource Requirements

### Infrastructure

- **NATS Server:** 12MB binary, 5-50MB RAM (depends on JetStream usage)
- **Additional Python Packages:** `nats-py` (~2MB)
- **Development Time:** 18-22 hours

### Monitoring

- NATS dashboard: `http://localhost:8222`
- Prometheus metrics: `/varz`, `/connz`, `/subsz`
- Custom metrics: Plugin health, message throughput, latency

---

## Rollout Plan

### Development Phase (This Sprint)

1. Implement on feature branch
2. All tests passing
3. Code review
4. Merge to main

### Staging Phase (Next Sprint Start)

1. Deploy to staging environment
2. Run for 48 hours
3. Monitor for issues
4. Performance validation

### Production Phase (When Stable)

1. Deploy to production
2. Monitor closely (24 hours)
3. Rollback plan ready
4. Gradual plugin migration

---

## Success Metrics

**Technical Metrics:**
- ✅ 100% test coverage on EventBus
- ✅ <10ms p99 latency on message handling
- ✅ 1000+ msg/sec throughput
- ✅ Zero memory leaks in 24hr test
- ✅ Plugin sandbox 100% permission enforcement

**Operational Metrics:**
- ✅ Zero functional regressions
- ✅ Bot uptime unchanged
- ✅ Command response time unchanged
- ✅ Error rate unchanged

**Architectural Metrics:**
- ✅ Plugins fully isolated
- ✅ Platform abstraction complete
- ✅ Event normalization working
- ✅ Ready for Discord connector (Sprint 11)

---

## Conclusion

Sprint 6a (Quicksilver) establishes the architectural foundation for Rosey's evolution from Cytube-specific bot to multi-platform framework. By migrating to NATS now:

- **Security:** Plugins run isolated, cannot compromise core
- **Scalability:** Components scale independently
- **Flexibility:** Add platforms/features without core changes
- **Reliability:** Message persistence, automatic reconnection
- **Performance:** Minimal overhead (<10ms latency)

This sprint unblocks all future multi-platform and integration work, positioning Rosey for long-term success.

**Let's go fast and connect everything! 🚴‍♂️💨**
