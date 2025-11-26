# SPEC: Sortie 4 - Documentation

**Sprint:** 20 - Release Ready v1.0  
**Sortie:** 4 of 5  
**Status:** Ready  
**Estimated Duration:** 3 days (Week 2-3)  
**Created:** November 26, 2025  

---

## Objective

Create complete, accurate documentation for v1.0 architecture. Update all existing docs, write migration guide from v0.9, document NATS interface contracts, and provide clear getting-started guide. Make v1.0 accessible to new developers and existing contributors.

---

## Context

**Starting Point** (Post-Sortie 3):
- v1 branch complete with working bot
- 500-800 tests passing
- CI/CD green
- Zero documentation for v1.0 architecture

**Documentation Needs**:
- Architecture changed dramatically (lib/ → NATS-first)
- New developers need quick start guide
- Existing contributors need migration guide
- NATS interface contracts need documentation
- All old docs reference lib/ (outdated)

**Key Principle**: Documentation is part of the product. Complete, accurate docs enable adoption.

---

## Success Criteria

### Deliverables
- [ ] README.md updated for v1.0
- [ ] QUICKSTART.md created (5-minute setup)
- [ ] ARCHITECTURE.md updated for v1.0 structure
- [ ] MIGRATION-V1.md created (v0.9 → v1.0 guide)
- [ ] NATS-CONTRACTS.md created (interface documentation)
- [ ] PLUGIN-DEVELOPMENT.md created (plugin authoring guide)
- [ ] All existing docs updated (no lib/ references)
- [ ] Deployment guide updated

### Quality Gates
- Zero references to `lib/` in documentation
- All code examples work (tested)
- Screenshots current (v1.0 UI)
- Links all work (no 404s)
- Spelling/grammar clean (proofread)

---

## Scope

### In Scope
- Core documentation (README, QUICKSTART, ARCHITECTURE)
- Migration documentation (MIGRATION-V1.md)
- Developer documentation (PLUGIN-DEVELOPMENT.md, NATS-CONTRACTS.md)
- Update existing docs (SETUP.md, TESTING.md, etc.)
- Deployment guide updates
- Code examples and snippets

### Out of Scope
- API reference documentation (defer to v1.1+)
- Advanced deployment scenarios (Docker, Kubernetes - defer)
- Performance tuning guide (defer to v1.1+)
- Troubleshooting deep-dives (defer)
- Video tutorials (defer)

---

## Requirements

### Functional Requirements

**FR1: Core Documentation**
- **README.md**: Project overview, features, quick links
- **QUICKSTART.md**: 5-minute setup guide (clone → run)
- **ARCHITECTURE.md**: v1.0 architecture (diagrams, components)

**FR2: Migration Documentation**
- **MIGRATION-V1.md**: Comprehensive v0.9 → v1.0 guide
  - What changed and why
  - How to access v0.9 archives
  - Plugin migration guide (if customized plugins)
  - Configuration changes
  - Breaking changes list

**FR3: Developer Documentation**
- **PLUGIN-DEVELOPMENT.md**: How to write plugins for v1.0
  - Plugin structure
  - NATS communication patterns
  - Testing plugins
  - Example plugin walkthrough
- **NATS-CONTRACTS.md**: NATS subject/message documentation
  - All subjects documented
  - Message formats
  - Example publish/subscribe code

**FR4: Existing Docs Update**
- **docs/SETUP.md**: Development environment setup
- **docs/TESTING.md**: Testing strategy and commands
- **docs/guides/\*.md**: Update all guides (remove lib/ references)

**FR5: Deployment Documentation**
- **DEPLOYMENT.md**: Production deployment guide
  - Requirements (NATS, Python, etc.)
  - Configuration
  - systemd service (if applicable)
  - Monitoring basics

### Non-Functional Requirements

**NFR1: Accessibility**
- Clear language (avoid jargon)
- Code examples for all concepts
- Diagrams for architecture
- Table of contents for long docs

**NFR2: Accuracy**
- All code examples tested
- All commands verified
- All links work
- Screenshots current

**NFR3: Maintainability**
- Consistent formatting (Markdown)
- Versioned (indicate v1.0)
- Modular (separate concerns)
- Easy to update

---

## Design

### Documentation Structure

```
.
├── README.md                    # Project overview (UPDATED)
├── QUICKSTART.md                # 5-minute start (NEW)
├── ARCHITECTURE.md              # v1.0 architecture (NEW, replaces old)
├── MIGRATION-V1.md              # v0.9 → v1.0 guide (NEW)
├── DEPLOYMENT.md                # Deployment guide (UPDATED)
├── CHANGELOG.md                 # Version history (UPDATED with v1.0)
├── docs/
│   ├── SETUP.md                 # Dev setup (UPDATED)
│   ├── TESTING.md               # Testing guide (UPDATED)
│   ├── NATS-CONTRACTS.md        # NATS interfaces (NEW)
│   ├── PLUGIN-DEVELOPMENT.md    # Plugin authoring (NEW)
│   ├── guides/
│   │   ├── AGENT_WORKFLOW_DETAILED.md  # Update examples
│   │   ├── AGENT_PROMPTING_GUIDE.md    # Update examples
│   │   └── ... (update all guides)
│   └── sprints/
│       └── active/20-v1-release-ready/  # This sprint's docs
```

### README.md Structure

**Template**:
```markdown
# Rosey Robot v1.0

> Plugin-first CyTube bot with NATS-based architecture

[![Tests](https://github.com/grobertson/Rosey-Robot/actions/workflows/test.yml/badge.svg)](https://github.com/grobertson/Rosey-Robot/actions/workflows/test.yml)
[![Coverage](https://codecov.io/gh/grobertson/Rosey-Robot/branch/v1/graph/badge.svg)](https://codecov.io/gh/grobertson/Rosey-Robot)

## What is Rosey?

Rosey is a modular bot for CyTube channels with a plugin-first architecture. All features are plugins that communicate via NATS message bus.

**Key Features**:
- 🔌 **Plugin-First**: All features are self-contained plugins
- 📨 **NATS-Based**: Pure message-passing architecture
- 🧪 **Well-Tested**: 600+ tests, 78%+ coverage
- 🚀 **Production-Ready**: CI/CD, monitoring, deployment guides

## Quick Start

Get running in 5 minutes:

```bash
# Clone repository
git clone https://github.com/grobertson/Rosey-Robot.git
cd Rosey-Robot

# Install dependencies
pip install -r requirements.txt

# Configure (edit config.json)
cp config.json config-local.json
nano config-local.json

# Run
python rosey.py --config config-local.json
```

See [QUICKSTART.md](QUICKSTART.md) for detailed setup.

## Architecture

Rosey v1.0 is built on three principles:

1. **Orchestration Only**: Core is ~100 lines of pure coordination
2. **Plugin Autonomy**: All business logic lives in plugins
3. **NATS-First**: All communication via message bus

```
rosey.py (orchestrator)
  ↓
  ├─ NATS Message Bus
  │   ├─ chat.message
  │   ├─ command.{name}
  │   ├─ plugin.{event}
  │   └─ cytube.{event}
  │
  └─ Plugins (self-contained)
      ├─ playlist/
      ├─ llm/
      ├─ trivia/
      └─ ...
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Migration from v0.9

v1.0 is a clean slate rebuild. If you're upgrading:

- See [MIGRATION-V1.md](MIGRATION-V1.md) for complete guide
- v0.9 code preserved in `archive/pre-v1-sprint-19` branch
- Breaking changes documented

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System design
- **[PLUGIN-DEVELOPMENT.md](docs/PLUGIN-DEVELOPMENT.md)** - Write plugins
- **[NATS-CONTRACTS.md](docs/NATS-CONTRACTS.md)** - Interface docs
- **[TESTING.md](docs/TESTING.md)** - Testing guide
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

1. Read [PLUGIN-DEVELOPMENT.md](docs/PLUGIN-DEVELOPMENT.md)
2. Check [issues](https://github.com/grobertson/Rosey-Robot/issues)
3. Submit PR with tests

## License

MIT License - see [LICENSE](LICENSE)

## Links

- **GitHub**: https://github.com/grobertson/Rosey-Robot
- **Issues**: https://github.com/grobertson/Rosey-Robot/issues
- **Releases**: https://github.com/grobertson/Rosey-Robot/releases
```

### QUICKSTART.md Structure

**Template**:
```markdown
# Quick Start Guide

Get Rosey running in 5 minutes.

## Prerequisites

- Python 3.12+
- NATS server (local or remote)
- CyTube account

## Setup Steps

### 1. Clone Repository

```bash
git clone https://github.com/grobertson/Rosey-Robot.git
cd Rosey-Robot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure

Copy config template:
```bash
cp config.json config-local.json
```

Edit `config-local.json`:
```json
{
  "nats": {
    "url": "nats://localhost:4222"
  },
  "cytube": {
    "url": "https://cytu.be",
    "channel": "your-channel-name",
    "username": "YourBotName",
    "password": "your-password"
  },
  "database": {
    "url": "sqlite:///bot_data.db"
  }
}
```

### 4. Start NATS (if local)

```bash
# Install NATS server (if not installed)
# macOS: brew install nats-server
# Linux: Download from nats.io

# Run NATS server
nats-server
```

### 5. Run Rosey

```bash
python rosey.py --config config-local.json
```

Expected output:
```
🤖 Rosey v1.0 starting...
✓ NATS connected: nats://localhost:4222
✓ Loaded 60 plugins
✓ Connected to CyTube: your-channel-name
🚀 Rosey v1.0 running!
```

### 6. Test

In CyTube chat, send: `!help`

Bot should respond with available commands.

## Next Steps

- **Customize plugins**: See [PLUGIN-DEVELOPMENT.md](docs/PLUGIN-DEVELOPMENT.md)
- **Deploy to production**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Write tests**: See [TESTING.md](docs/TESTING.md)

## Troubleshooting

**Bot doesn't connect to NATS**:
- Verify NATS server running: `nats-server -v`
- Check URL in config: `nats://localhost:4222`

**Bot doesn't connect to CyTube**:
- Verify credentials in config
- Check CyTube server URL
- Check channel name (case-sensitive)

**Plugins don't load**:
- Check plugins/ directory exists
- Check plugin __init__.py files
- Check logs for plugin errors

## Support

- **Issues**: https://github.com/grobertson/Rosey-Robot/issues
- **Documentation**: [docs/](docs/)
```

### MIGRATION-V1.md Structure

**Template**:
```markdown
# Migration Guide: v0.9 → v1.0

Complete guide for migrating from v0.9 (Sprint 19) to v1.0.

## What Changed

v1.0 is a clean slate rebuild with a plugin-first architecture.

**Major Changes**:
- ❌ **Removed**: `lib/` directory (74 files)
- ❌ **Removed**: `bot/rosey/rosey.py` wrapper (439 lines)
- ✅ **New**: `rosey.py` orchestrator (100 lines)
- ✅ **New**: NATS-first architecture
- ✅ **Consolidated**: `core/` directory (from `bot/rosey/core/`)

**Test Suite Changes**:
- 2000 tests → 600 focused tests
- lib/ internals tests → NATS interface tests
- 66% coverage → 78% coverage

## Why Clean Slate?

**Constraints**:
- Zero production deployments (architectural freedom)
- Sprint 19 broke test suite (`ModuleNotFoundError: No module named 'lib.playlist'`)
- Architectural confusion (lib/bot.py + bot/rosey/rosey.py)

**Benefits**:
- 1680 lines → 100 lines (core bot)
- Clear architecture (plugin-first)
- Correct tests (NATS interfaces)
- 3 weeks vs 3 months (incremental refactor)

## Access v0.9 Archives

v0.9 code preserved in archives:

```bash
# View Sprint 19 final state
git checkout archive/pre-v1-sprint-19

# Or use tag
git checkout v0.9-sprint-19-final

# Return to v1.0
git checkout main
```

Archives include:
- All 19 sprints of development history
- lib/ directory architecture
- bot/rosey/ wrapper
- 2000 tests
- All documentation through Sprint 19

## Migration Scenarios

### Scenario 1: Standard Installation

**v0.9 Setup**:
```bash
python bot/rosey/rosey.py --config config.json
```

**v1.0 Setup**:
```bash
python rosey.py --config config.json
```

**Configuration**: No changes needed (same format).

### Scenario 2: Custom Plugins

If you wrote custom plugins:

**v0.9 Plugin** (imported lib/):
```python
from lib.bot import Bot
from lib.plugin import Plugin

class MyPlugin(Plugin):
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def on_chat(self, user, msg):
        # Direct bot access
        await self.bot.send_chat("Hello!")
```

**v1.0 Plugin** (NATS-based):
```python
from core.plugin import Plugin

class MyPlugin(Plugin):
    def __init__(self, nc, event_bus):
        self.nc = nc
        self.event_bus = event_bus
    
    async def on_chat(self, user, msg):
        # Publish via NATS
        await self.event_bus.publish('chat.send', {
            'msg': 'Hello!'
        })
```

**Migration Steps**:
1. Remove `from lib.*` imports
2. Change constructor to accept `nc, event_bus`
3. Replace direct bot calls with NATS publish
4. Test with `pytest tests/plugins/test_myplugin.py`

See [PLUGIN-DEVELOPMENT.md](docs/PLUGIN-DEVELOPMENT.md) for complete guide.

### Scenario 3: Database Schema

**No changes required**. v1.0 uses same SQLAlchemy models in `common/models.py`.

Existing bot_data.db works without migration.

### Scenario 4: Configuration

**No changes required**. v1.0 uses same config.json format.

Optional new fields:
```json
{
  "nats": {
    "url": "nats://localhost:4222",
    "reconnect_attempts": 5  // NEW (optional)
  }
}
```

## Breaking Changes

### Removed APIs

**lib.bot.Bot class**: No longer exists
- **Replacement**: Use NATS `event_bus.publish()`
- **Migration**: See plugin migration above

**lib.playlist.Playlist class**: Removed in Sprint 19, now plugin
- **Replacement**: Use `plugins/playlist/`
- **Access**: Via NATS commands (`!play`, `!queue`, etc.)

**lib.llm.LLMClient class**: Removed in Sprint 19, now plugin
- **Replacement**: Use `plugins/llm/`
- **Access**: Via NATS commands (chat triggers)

### Changed Behavior

**Plugin Loading**:
- **v0.9**: Plugins imported directly
- **v1.0**: Plugins discovered in `plugins/` directory
- **Impact**: Plugin directory structure matters

**Command Routing**:
- **v0.9**: Commands routed via lib/bot.py
- **v1.0**: Commands routed via NATS (`command.{name}` subjects)
- **Impact**: Custom command handlers need NATS subscriptions

## Testing Migration

**v0.9 Tests**:
```bash
pytest tests/  # 2000 tests, many broken
```

**v1.0 Tests**:
```bash
pytest tests/  # 600 focused tests, all passing
```

**Test Patterns Changed**:
```python
# v0.9: Test lib/ internals
def test_bot_send_chat(bot):
    bot.send_chat("Hello")
    assert bot.connection.sent == ["Hello"]

# v1.0: Test NATS interfaces
async def test_chat_send_message(mock_nats):
    await event_bus.publish('chat.send', {'msg': 'Hello'})
    mock_nats.publish.assert_called_with('chat.message', ...)
```

## Deployment Migration

**v0.9 Deployment**:
```bash
python bot/rosey/rosey.py --config /etc/rosey/config.json
```

**v1.0 Deployment**:
```bash
# Start NATS server (NEW requirement)
nats-server --config /etc/nats/nats.conf

# Start Rosey
python rosey.py --config /etc/rosey/config.json
```

**New Dependency**: NATS server must be running.

See [DEPLOYMENT.md](DEPLOYMENT.md) for production setup.

## Timeline

**Recommended Migration Path**:
1. **Week 1**: Review v1.0 architecture (read docs)
2. **Week 2**: Test v1.0 locally (use QUICKSTART.md)
3. **Week 3**: Migrate custom plugins (if any)
4. **Week 4**: Deploy to production

## Support

**Questions**: Open issue at https://github.com/grobertson/Rosey-Robot/issues

**Bug Reports**: Include:
- v1.0 or v0.9?
- Error messages
- Configuration (sanitized)

## Rollback Plan

If v1.0 doesn't work for you:

```bash
# Use v0.9 archives
git checkout archive/pre-v1-sprint-19

# Run v0.9
python bot/rosey/rosey.py --config config.json
```

v0.9 will remain in archives indefinitely.
```

### NATS-CONTRACTS.md Structure

**Template**:
```markdown
# NATS Interface Contracts

Complete documentation of NATS subjects and message formats used in Rosey v1.0.

## Overview

All component communication happens via NATS message bus. This document defines the contracts (subjects, message formats) that components must follow.

## Subject Naming Convention

```
{domain}.{action}
```

**Examples**:
- `chat.message` - Chat message event
- `command.help` - Help command
- `plugin.loaded` - Plugin loaded event
- `cytube.connected` - CyTube connection event

## Core Subjects

### Chat Domain

#### `chat.message`
**Description**: Chat message from user or bot
**Publisher**: CyTubeConnector, plugins
**Subscribers**: CommandRouter, plugins
**Message Format**:
```json
{
  "username": "string",
  "msg": "string",
  "time": "number (Unix timestamp)",
  "meta": {
    "rank": "number",
    "is_bot": "boolean"
  }
}
```
**Example**:
```python
await event_bus.publish('chat.message', {
    'username': 'TestUser',
    'msg': 'Hello, Rosey!',
    'time': 1700000000,
    'meta': {'rank': 2, 'is_bot': False}
})
```

#### `chat.send`
**Description**: Send chat message to CyTube
**Publisher**: Plugins
**Subscribers**: CyTubeConnector
**Message Format**:
```json
{
  "msg": "string",
  "meta": {
    "priority": "string (optional: low|normal|high)"
  }
}
```
**Example**:
```python
await event_bus.publish('chat.send', {
    'msg': 'Hello, everyone!',
    'meta': {'priority': 'normal'}
})
```

### Command Domain

#### `command.{name}`
**Description**: Execute command by name
**Publisher**: CommandRouter
**Subscribers**: Plugin providing command
**Message Format**:
```json
{
  "username": "string",
  "args": ["string"],
  "msg": "string (original message)",
  "meta": {
    "rank": "number",
    "channel": "string"
  }
}
```
**Example**:
```python
# Subscribe to command
await nc.subscribe('command.help', cb=handle_help)

# Publish command
await nc.request('command.help', json.dumps({
    'username': 'TestUser',
    'args': [],
    'msg': '!help'
}).encode(), timeout=5.0)
```

**Response Format** (request/reply):
```json
{
  "success": "boolean",
  "response": "string (message to send)",
  "error": "string (optional, if success=false)"
}
```

### Plugin Domain

#### `plugin.register`
**Description**: Plugin registration announcement
**Publisher**: Plugins
**Subscribers**: PluginManager
**Message Format**:
```json
{
  "name": "string",
  "version": "string",
  "commands": ["string"],
  "events": ["string (NATS subjects subscribed)"]
}
```
**Example**:
```python
await event_bus.publish('plugin.register', {
    'name': 'playlist',
    'version': '1.0.0',
    'commands': ['play', 'queue', 'skip'],
    'events': ['chat.message', 'cytube.media']
})
```

#### `plugin.loaded`
**Description**: Plugin successfully loaded
**Publisher**: PluginManager
**Subscribers**: Monitoring, logging
**Message Format**:
```json
{
  "name": "string",
  "timestamp": "number (Unix timestamp)"
}
```

#### `plugin.error`
**Description**: Plugin error occurred
**Publisher**: PluginManager, plugins
**Subscribers**: Monitoring, logging
**Message Format**:
```json
{
  "plugin": "string",
  "error": "string",
  "traceback": "string (optional)",
  "timestamp": "number"
}
```

### CyTube Domain

#### `cytube.connected`
**Description**: Connected to CyTube channel
**Publisher**: CyTubeConnector
**Subscribers**: Plugins, monitoring
**Message Format**:
```json
{
  "channel": "string",
  "username": "string (bot username)",
  "timestamp": "number"
}
```

#### `cytube.disconnected`
**Description**: Disconnected from CyTube
**Publisher**: CyTubeConnector
**Subscribers**: Plugins, monitoring
**Message Format**:
```json
{
  "reason": "string",
  "timestamp": "number"
}
```

#### `cytube.user_join`
**Description**: User joined channel
**Publisher**: CyTubeConnector
**Subscribers**: Plugins
**Message Format**:
```json
{
  "username": "string",
  "rank": "number",
  "timestamp": "number"
}
```

#### `cytube.user_leave`
**Description**: User left channel
**Publisher**: CyTubeConnector
**Subscribers**: Plugins
**Message Format**:
```json
{
  "username": "string",
  "timestamp": "number"
}
```

#### `cytube.media`
**Description**: Media change event
**Publisher**: CyTubeConnector
**Subscribers**: Plugins (playlist, media trackers)
**Message Format**:
```json
{
  "type": "string (yt|vm|etc)",
  "id": "string",
  "title": "string",
  "duration": "number (seconds)",
  "user": "string (who queued)"
}
```

## Plugin-Specific Subjects

Plugins can define custom subjects for inter-plugin communication:

```
plugin.{plugin_name}.{action}
```

**Example** (playlist plugin):
```
plugin.playlist.query      # Query current playlist
plugin.playlist.updated    # Playlist changed event
```

**Best Practice**: Document custom subjects in plugin README.md.

## Request/Reply Pattern

For commands or queries that need responses, use NATS request/reply:

```python
# Request (with timeout)
response = await nc.request('command.help', data, timeout=5.0)
result = json.loads(response.data)

# Reply (in subscription callback)
async def handle_request(msg):
    result = {'success': True, 'response': 'Help text'}
    await msg.respond(json.dumps(result).encode())
```

## Error Handling

All NATS messages should handle errors gracefully:

```python
try:
    await event_bus.publish('chat.send', {'msg': 'Hello'})
except Exception as e:
    await event_bus.publish('plugin.error', {
        'plugin': 'my_plugin',
        'error': str(e)
    })
```

## Testing NATS Contracts

Use mocked NATS in tests:

```python
@pytest.fixture
async def mock_nats():
    nc = AsyncMock(spec=nats.NATS)
    nc.publish = AsyncMock()
    nc.subscribe = AsyncMock()
    return nc

@pytest.mark.asyncio
async def test_chat_message_contract(mock_nats):
    event_bus = EventBus(mock_nats)
    
    await event_bus.publish('chat.message', {
        'username': 'test',
        'msg': 'hello',
        'time': 123456,
        'meta': {'rank': 1, 'is_bot': False}
    })
    
    # Verify contract
    mock_nats.publish.assert_called_once()
    call_args = mock_nats.publish.call_args
    assert call_args[0][0] == 'chat.message'
    data = json.loads(call_args[0][1])
    assert 'username' in data
    assert 'msg' in data
```

## See Also

- [PLUGIN-DEVELOPMENT.md](PLUGIN-DEVELOPMENT.md) - Plugin authoring guide
- [TESTING.md](TESTING.md) - Testing strategies
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
```

---

## Implementation Steps

### Day 1: Core Documentation (6 hours)

**Step 1.1: Update README.md**
```markdown
# Use template above
# Add badges (CI, coverage)
# Update features for v1.0
# Update architecture diagram
# Update links
```

**Step 1.2: Create QUICKSTART.md**
```markdown
# Use template above
# Test all commands work
# Add screenshots
# Add troubleshooting section
```

**Step 1.3: Create ARCHITECTURE.md**
```markdown
# Document v1.0 architecture
# Include diagrams (create with diagrams.net or similar)
# Explain orchestrator pattern
# Explain plugin-first design
# Document core components
```

**Step 1.4: Commit Core Docs**
```powershell
git add README.md QUICKSTART.md ARCHITECTURE.md
git commit -m "Update core documentation for v1.0

- README.md: v1.0 overview, features, badges
- QUICKSTART.md: 5-minute setup guide
- ARCHITECTURE.md: Plugin-first architecture docs

All docs tested and verified

Relates-to: Sprint 20 Sortie 4 (Documentation)"

git push origin v1
```

### Day 2: Migration & Developer Docs (8 hours)

**Step 2.1: Create MIGRATION-V1.md**
```markdown
# Use template above
# Document all breaking changes
# Provide migration examples
# Add rollback plan
```

**Step 2.2: Create NATS-CONTRACTS.md**
```markdown
# Use template above
# Document all NATS subjects
# Include message format examples
# Add testing examples
```

**Step 2.3: Create PLUGIN-DEVELOPMENT.md**
```markdown
# Complete plugin authoring guide
# Include example plugin
# Document NATS patterns
# Add testing guide for plugins
```

**Step 2.4: Commit Migration & Developer Docs**
```powershell
git add MIGRATION-V1.md docs/NATS-CONTRACTS.md docs/PLUGIN-DEVELOPMENT.md
git commit -m "Add migration and developer documentation

- MIGRATION-V1.md: Complete v0.9 → v1.0 guide
- NATS-CONTRACTS.md: Interface documentation
- PLUGIN-DEVELOPMENT.md: Plugin authoring guide

All examples tested and working

Relates-to: Sprint 20 Sortie 4 (Documentation)"

git push origin v1
```

### Day 3: Update Existing Docs (6 hours)

**Step 3.1: Update docs/SETUP.md**
```markdown
# Update for v1.0 structure
# Remove lib/ references
# Add NATS server setup
# Update dependency list
```

**Step 3.2: Update docs/TESTING.md**
```markdown
# Document v1.0 test structure
# Update test patterns (NATS interfaces)
# Update coverage information
# Add CI/CD info
```

**Step 3.3: Update docs/guides/\*.md**
```bash
# Search for lib/ references
grep -r "lib/" docs/guides/

# Update each guide:
# - Remove lib/ references
# - Update code examples for v1.0
# - Update architecture references
```

**Step 3.4: Update DEPLOYMENT.md**
```markdown
# Add NATS server requirements
# Update systemd service example
# Update Docker example (if applicable)
# Add monitoring guidance
```

**Step 3.5: Update CHANGELOG.md**
```markdown
## [1.0.0] - 2025-12-17 - Release Ready

### Added
- Plugin-first architecture
- NATS-based communication
- 100-line orchestrator (rosey.py)
- 600 focused tests (78% coverage)
- CI/CD pipeline
- Complete documentation

### Changed
- Core architecture (lib/ → NATS-first)
- Test strategy (internals → interfaces)

### Removed
- lib/ directory (74 files)
- bot/rosey/rosey.py wrapper

### Migration
See [MIGRATION-V1.md](MIGRATION-V1.md) for v0.9 → v1.0 guide.
```

**Step 3.6: Commit Existing Docs Updates**
```powershell
git add docs/ DEPLOYMENT.md CHANGELOG.md
git commit -m "Update all existing documentation for v1.0

- docs/SETUP.md: v1.0 dev setup
- docs/TESTING.md: v1.0 test strategy
- docs/guides/*.md: Remove lib/ references
- DEPLOYMENT.md: Add NATS requirements
- CHANGELOG.md: v1.0.0 release notes

All lib/ references removed
All examples tested

Relates-to: Sprint 20 Sortie 4 (Documentation)"

git push origin v1
```

---

## Testing Strategy

### Documentation Testing

**Test 1: All Code Examples Work**
```powershell
# Extract code examples from docs
# Run each example
# Verify expected output
```

**Test 2: All Links Work**
```powershell
# Use markdown link checker
npm install -g markdown-link-check
markdown-link-check README.md
markdown-link-check docs/**/*.md
```

**Test 3: Spelling and Grammar**
```powershell
# Use spell checker
npm install -g markdown-spellcheck
mdspell '**/*.md' --en-us --ignore-numbers --ignore-acronyms
```

**Test 4: Quickstart Follows Successfully**
```powershell
# Fresh clone in temp directory
# Follow QUICKSTART.md step by step
# Verify bot runs
```

### Acceptance Criteria

- [ ] README.md updated and renders correctly on GitHub
- [ ] QUICKSTART.md tested (fresh install successful)
- [ ] ARCHITECTURE.md includes diagrams
- [ ] MIGRATION-V1.md comprehensive and tested
- [ ] NATS-CONTRACTS.md complete with examples
- [ ] PLUGIN-DEVELOPMENT.md complete with walkthrough
- [ ] All existing docs updated (zero lib/ references)
- [ ] All code examples tested
- [ ] All links work (no 404s)
- [ ] Spelling/grammar clean
- [ ] CHANGELOG.md updated with v1.0.0

---

## Dependencies

### Prerequisites
- Sortie 3 complete (tests passing, CI green)
- v1 branch stable and working

### External Dependencies
- markdown-link-check (link validation)
- markdown-spellcheck (spell checking)
- diagrams.net or similar (architecture diagrams)

### Blocks
- Sortie 5 (Main Branch Transition) - needs docs complete

---

## Risks & Mitigations

### Risk 1: Documentation Takes Longer Than Expected
**Likelihood**: Medium  
**Impact**: Low (can defer some docs to v1.1)  

**Mitigation**:
- Prioritize core docs (README, QUICKSTART, MIGRATION)
- Developer docs (NATS-CONTRACTS, PLUGIN-DEVELOPMENT) can be iterative
- Existing doc updates can be batch processed
- 3 days is realistic for core documentation

### Risk 2: Code Examples Don't Work
**Likelihood**: Low  
**Impact**: Medium (confusing for users)  

**Mitigation**:
- Test all code examples before committing
- Use actual working code from v1 branch
- Run examples in fresh environment
- CI can test examples (future enhancement)

### Risk 3: Architecture Diagrams Unclear
**Likelihood**: Medium  
**Impact**: Low (text explanations sufficient)  

**Mitigation**:
- Start with simple text diagrams (ASCII art)
- Can enhance with visual diagrams later
- Clarity more important than beauty
- Get feedback and iterate

---

## Notes

### Documentation Philosophy
- **Show, don't tell**: Code examples over prose
- **Start simple**: Quick wins before deep dives
- **Assume nothing**: Explain prerequisites
- **Test everything**: All examples must work

### Why Complete Documentation Matters
- New contributors can get started quickly
- Existing contributors understand v1.0 changes
- Plugin developers have clear contracts
- Future maintenance easier
- Professional appearance

### Ongoing Documentation
Post-v1.0, documentation should:
- Update with each release
- Include examples for new features
- Deprecate old patterns clearly
- Keep NATS-CONTRACTS.md current

---

## Completion Checklist

### Day 1: Core Docs
- [ ] README.md updated
- [ ] QUICKSTART.md created and tested
- [ ] ARCHITECTURE.md created with diagrams
- [ ] All core docs committed

### Day 2: Migration & Developer Docs
- [ ] MIGRATION-V1.md created and comprehensive
- [ ] NATS-CONTRACTS.md created with all subjects
- [ ] PLUGIN-DEVELOPMENT.md created with walkthrough
- [ ] All examples tested
- [ ] All docs committed

### Day 3: Existing Docs
- [ ] docs/SETUP.md updated
- [ ] docs/TESTING.md updated
- [ ] docs/guides/*.md updated (no lib/ references)
- [ ] DEPLOYMENT.md updated
- [ ] CHANGELOG.md updated with v1.0.0
- [ ] All links validated
- [ ] Spelling checked
- [ ] All docs committed

### Final Verification
- [ ] Fresh clone and quickstart successful
- [ ] All code examples work
- [ ] All links work
- [ ] No lib/ references anywhere
- [ ] Rendering correct on GitHub

---

**Estimated Time**: 3 days (Week 2-3)  
**Actual Time**: _[To be filled after completion]_  
**Completed By**: _[To be filled]_  
**Completion Date**: _[To be filled]_  

---

**Next Sortie**: [SPEC-Sortie-5-Main-Branch-Transition.md](SPEC-Sortie-5-Main-Branch-Transition.md)
