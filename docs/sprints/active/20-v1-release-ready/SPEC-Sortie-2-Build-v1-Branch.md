# SPEC: Sortie 2 - Build v1 Branch

**Sprint:** 20 - Release Ready v1.0  
**Sortie:** 2 of 5  
**Status:** Ready  
**Estimated Duration:** 5 days (Week 1)  
**Created:** November 26, 2025  

---

## Objective

Create clean v1.0 architecture with orphan branch, 100-line orchestrator replacing 1680 lines of confusion, and consolidated core infrastructure. Prove v1.0 architecture by running bot and loading plugins successfully.

---

## Context

**Starting Point** (Post-Sortie 1):
- Archives created: `archive/pre-v1-sprint-19` (safety net)
- Sprint 19 complete: Plugins migrated, working well (96% tests passing)
- Test suite broken: `ModuleNotFoundError: No module named 'lib.playlist'`
- Architectural confusion: lib/bot.py (1241 lines) + bot/rosey/rosey.py (439 lines)

**v1.0 Vision**:
```
rosey-v1/
├── rosey.py              # 100-line orchestrator (replaces 1680 lines)
├── core/                 # NATS infrastructure (consolidated)
├── plugins/              # Working plugins (copy verbatim)
└── common/               # Database service (copy verbatim)
```

**Key Principle**: Plugin-first architecture with NATS-only communication. Core is pure orchestration, zero business logic.

---

## Success Criteria

### Deliverables
- [ ] Orphan branch `v1` created (clean slate)
- [ ] Working code copied: plugins/, common/, core/
- [ ] New rosey.py orchestrator (≤150 lines)
- [ ] Bot runs and connects to CyTube
- [ ] Plugins load successfully via NATS
- [ ] Core infrastructure consolidated from bot/rosey/core/
- [ ] Essential configs in place (.gitignore, requirements.txt, etc.)

### Quality Gates
- `python rosey.py` starts without errors
- NATS connection successful
- All plugins detected and loaded
- CyTube connection established
- Zero imports from `lib/` (doesn't exist)
- Core orchestrator ≤150 lines (target: 100)

---

## Scope

### In Scope
- Create orphan branch (no history)
- Copy working code only (plugins, common, core)
- Write new rosey.py orchestrator
- Consolidate bot/rosey/core/ patterns with lib/plugin/ best parts
- Essential configs (requirements.txt, .gitignore, config.json)
- Manual smoke test (bot runs)

### Out of Scope
- Tests (that's Sortie 3)
- Documentation (that's Sortie 4)
- CI/CD setup (Sortie 3)
- Merging to main (Sortie 5)
- Plugin modifications (plugins copied as-is)

---

## Requirements

### Functional Requirements

**FR1: Orphan Branch**
- Create `v1` branch with no git history
- Clean slate: zero commits initially
- Name clearly indicates v1.0 rebuild

**FR2: Directory Structure**
```
v1/
├── rosey.py              # Main entry point (100-line orchestrator)
├── core/                 # NATS infrastructure
│   ├── __init__.py       # Clean exports
│   ├── event_bus.py      # From bot/rosey/core/
│   ├── plugin_manager.py # Merged lib/plugin/ + bot/rosey/core/plugin_manager.py
│   ├── router.py         # From bot/rosey/core/
│   └── cytube_connector.py  # From bot/rosey/core/
├── plugins/              # Copy from Sprint 19 (working)
│   ├── playlist/
│   ├── llm/
│   ├── trivia/
│   └── ... (all plugins)
├── common/               # Copy from Sprint 19 (working)
│   ├── __init__.py
│   ├── config.py
│   ├── database_service.py
│   ├── database.py
│   └── models.py
├── requirements.txt      # Updated dependencies
├── .gitignore            # Updated patterns
├── config.json           # Configuration template
└── pytest.ini            # Test configuration (for Sortie 3)
```

**FR3: Core Orchestrator (rosey.py)**
- Main entry point for application
- Pure orchestration: initialize components, connect services, wait
- Zero business logic (that's in plugins)
- NATS-first: all components use NATS
- ≤150 lines (target: 100)

**FR4: Core Infrastructure**
- Copy bot/rosey/core/ as foundation
- Merge best patterns from lib/plugin/ into plugin_manager.py
- No lib/ imports (lib/ doesn't exist in v1)
- All components NATS-based

**FR5: Working Code Copy**
- plugins/ directory: Copy verbatim (already working)
- common/ directory: Copy verbatim (solid foundation)
- Zero modifications to working code

### Non-Functional Requirements

**NFR1: Simplicity**
- Core orchestrator readable in one screen
- Clear separation: orchestration vs business logic
- No "wrapper" pattern (was the problem)

**NFR2: NATS-First**
- All inter-component communication via NATS
- No direct imports between core and plugins
- Event-driven architecture throughout

**NFR3: Verifiability**
- Can run bot manually to prove it works
- Plugins load (visible in logs)
- CyTube connects (visible in logs)

---

## Design

### Core Orchestrator Architecture

**rosey.py Structure** (100 lines):
```python
"""
Rosey Bot v1.0 - Plugin-First Architecture

Pure orchestration: initialize, connect, wait.
All business logic lives in plugins.
All communication via NATS.
"""
import asyncio
import signal
import sys
from pathlib import Path

import nats
from nats.errors import ConnectionClosedError, TimeoutError as NatsTimeoutError

from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.router import CommandRouter
from core.cytube_connector import CyTubeConnector
from common.config import load_config


class RoseyBot:
    """Main bot orchestrator - pure coordination, zero business logic."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = load_config(config_path)
        self.nc = None
        self.event_bus = None
        self.plugin_manager = None
        self.router = None
        self.cytube = None
        self._shutdown = asyncio.Event()
    
    async def start(self):
        """Initialize all components and start bot."""
        print("🤖 Rosey v1.0 starting...")
        
        # Connect to NATS (message bus for everything)
        self.nc = await nats.connect(
            servers=self.config['nats']['url'],
            error_cb=self._error_callback,
            closed_cb=self._closed_callback,
        )
        print(f"✓ NATS connected: {self.config['nats']['url']}")
        
        # Initialize core components (all NATS-based)
        self.event_bus = EventBus(self.nc)
        self.plugin_manager = PluginManager(self.nc, self.event_bus)
        self.router = CommandRouter(self.nc, self.event_bus)
        self.cytube = CyTubeConnector(
            self.nc, 
            self.event_bus,
            self.config['cytube']
        )
        
        # Load plugins (they register themselves via NATS)
        plugins_path = Path(__file__).parent / "plugins"
        await self.plugin_manager.load_all(plugins_path)
        print(f"✓ Loaded {self.plugin_manager.count()} plugins")
        
        # Connect to CyTube (publishes events to NATS)
        await self.cytube.connect()
        print(f"✓ Connected to CyTube: {self.config['cytube']['channel']}")
        
        # That's it. Everything else is plugins.
        print("🚀 Rosey v1.0 running!")
        
    async def run(self):
        """Main run loop - just wait for shutdown."""
        await self._shutdown.wait()
    
    async def stop(self):
        """Graceful shutdown."""
        print("\n🛑 Shutting down...")
        self._shutdown.set()
        
        if self.cytube:
            await self.cytube.disconnect()
        if self.plugin_manager:
            await self.plugin_manager.unload_all()
        if self.nc:
            await self.nc.close()
        
        print("✓ Shutdown complete")
    
    async def _error_callback(self, e):
        """NATS error callback."""
        print(f"❌ NATS error: {e}")
    
    async def _closed_callback(self):
        """NATS closed callback."""
        print("⚠️ NATS connection closed")


async def main():
    """Entry point."""
    bot = RoseyBot()
    
    # Handle shutdown signals
    def shutdown_handler():
        asyncio.create_task(bot.stop())
    
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_handler)
    
    try:
        await bot.start()
        await bot.run()
    except KeyboardInterrupt:
        await bot.stop()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        await bot.stop()
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
```

**Design Principles**:
1. **Orchestration Only**: Initialize, connect, wait
2. **NATS-First**: All components use NATS message bus
3. **Plugin Autonomy**: Plugins own all business logic
4. **Graceful Shutdown**: Signal handlers, proper cleanup
5. **Observability**: Clear logging at each step

### Core Infrastructure Consolidation

**From bot/rosey/core/** (copy as-is):
- `event_bus.py` - NATS event distribution ✅
- `router.py` - Command routing via NATS ✅
- `cytube_connector.py` - CyTube connection ✅

**From lib/plugin/** (merge into core/plugin_manager.py):
- Plugin lifecycle management (load, unload, reload)
- Plugin discovery (scan plugins/ directory)
- Plugin dependency resolution (if applicable)
- Error handling and isolation

**New core/__init__.py**:
```python
"""
Core infrastructure for Rosey v1.0

Pure NATS-based components:
- EventBus: Message distribution
- PluginManager: Plugin lifecycle
- CommandRouter: Command routing
- CyTubeConnector: CyTube integration
"""
from .event_bus import EventBus
from .plugin_manager import PluginManager
from .router import CommandRouter
from .cytube_connector import CyTubeConnector

__all__ = [
    'EventBus',
    'PluginManager',
    'CommandRouter',
    'CyTubeConnector',
]
```

### Copy Strategy

**Plugins** (copy verbatim):
```powershell
# Copy entire plugins/ directory
cp -r ../Rosey-Robot-backup/plugins ./plugins
```

**Common** (copy verbatim):
```powershell
# Copy entire common/ directory
cp -r ../Rosey-Robot-backup/common ./common
```

**Core** (copy + consolidate):
```powershell
# Copy bot/rosey/core/ as foundation
cp -r ../Rosey-Robot-backup/bot/rosey/core ./core

# Then manually merge lib/plugin/ patterns into plugin_manager.py
```

---

## Implementation Steps

### Day 1: Create Orphan Branch & Copy Structure (4 hours)

**Step 1.1: Create Orphan Branch**
```powershell
# Ensure Sprint 19 branch is current
git checkout nano-sprint/19-core-migration
git pull origin nano-sprint/19-core-migration

# Create backup of current directory (safety)
cd ..
Copy-Item -Recurse Rosey-Robot Rosey-Robot-backup

# Return to repo
cd Rosey-Robot

# Create orphan branch (clean slate)
git checkout --orphan v1

# Remove all files from git index (but keep working directory)
git rm -rf .

# Verify clean slate
git status  # Should show "No commits yet"
```

**Step 1.2: Copy Essential Configs**
```powershell
# Copy from backup
Copy-Item ../Rosey-Robot-backup/.gitignore ./
Copy-Item ../Rosey-Robot-backup/requirements.txt ./
Copy-Item ../Rosey-Robot-backup/pytest.ini ./
Copy-Item ../Rosey-Robot-backup/config.json ./
Copy-Item ../Rosey-Robot-backup/LICENSE ./

# Verify
ls
# Should show: .gitignore, requirements.txt, pytest.ini, config.json, LICENSE
```

**Step 1.3: Copy Working Code**
```powershell
# Copy plugins (working, 96% tests passing)
Copy-Item -Recurse ../Rosey-Robot-backup/plugins ./plugins

# Copy common (database service, config, models)
Copy-Item -Recurse ../Rosey-Robot-backup/common ./common

# Copy core foundation (bot/rosey/core/)
Copy-Item -Recurse ../Rosey-Robot-backup/bot/rosey/core ./core

# Verify structure
tree /F
# Should show: plugins/, common/, core/, config files
```

**Step 1.4: Initial Commit**
```powershell
git add -A
git commit -m "v1.0 - Initial structure (working code only)

Copy working components from Sprint 19:
- plugins/ (60+ files, 96% tests passing)
- common/ (database service, config, models)
- core/ (from bot/rosey/core/ - NATS infrastructure)
- Essential configs (requirements.txt, .gitignore, etc.)

What's NOT included:
- lib/ directory (architectural confusion)
- bot/rosey/rosey.py wrapper (439 lines)
- tests/ (will rewrite for NATS interfaces in Sortie 3)

Architecture: Plugin-first, NATS-only, zero lib/ dependency

Relates-to: Sprint 20 Sortie 2 (Build v1 Branch)"

git push origin v1
```

### Day 2: Consolidate Core Infrastructure (6 hours)

**Step 2.1: Audit lib/plugin/ for Patterns to Merge**
```powershell
# Check out reference copy
cd ../Rosey-Robot-backup
code lib/plugin/

# Look for:
# - Plugin base classes
# - Lifecycle methods (load, unload, reload)
# - Plugin discovery logic
# - Error handling patterns
# - Dependency resolution

# Take notes on what to merge
```

**Step 2.2: Enhance core/plugin_manager.py**
```python
# In v1/core/plugin_manager.py
# Merge best patterns from lib/plugin/ into NATS-based plugin_manager

# Key enhancements:
# 1. Plugin discovery (scan plugins/ directory)
# 2. Plugin lifecycle (load, unload, reload)
# 3. Error isolation (plugin crash doesn't crash bot)
# 4. Dependency resolution (if needed)
# 5. NATS subscription management per plugin
```

**Step 2.3: Update core/__init__.py**
```python
# Clean exports
from .event_bus import EventBus
from .plugin_manager import PluginManager
from .router import CommandRouter
from .cytube_connector import CyTubeConnector

__all__ = [
    'EventBus',
    'PluginManager',
    'CommandRouter',
    'CyTubeConnector',
]
```

**Step 2.4: Commit Core Consolidation**
```powershell
cd ../Rosey-Robot
git add core/
git commit -m "Consolidate core infrastructure

Merge lib/plugin/ patterns into core/plugin_manager.py:
- Plugin discovery and loading
- Lifecycle management
- Error isolation
- NATS subscription management

Update core/__init__.py with clean exports

All components pure NATS-based, zero lib/ imports

Relates-to: Sprint 20 Sortie 2 (Build v1 Branch)"

git push origin v1
```

### Day 3-4: Write Core Orchestrator (8 hours)

**Step 3.1: Create rosey.py**
```powershell
# Create rosey.py using design above
code rosey.py

# Implement RoseyBot class:
# - __init__: Load config
# - start: Initialize components, connect services
# - run: Wait for shutdown
# - stop: Graceful shutdown
# - Error callbacks for NATS

# Implement main():
# - Signal handlers
# - Exception handling
# - Entry point
```

**Step 3.2: Verify Imports**
```python
# In rosey.py
# Should import:
# - asyncio, signal, sys (stdlib)
# - nats (message bus)
# - core.* (our infrastructure)
# - common.config (configuration)

# Should NOT import:
# - lib.* (doesn't exist)
# - plugins.* directly (plugins load themselves)
```

**Step 3.3: Test Line Count**
```powershell
# Count lines in rosey.py (excluding blank lines and comments)
(Get-Content rosey.py | Where-Object {$_ -notmatch '^\s*$|^\s*#'}).Count

# Target: ≤150 lines
# Goal: ~100 lines
```

**Step 3.4: Commit Orchestrator**
```powershell
git add rosey.py
git commit -m "Add v1.0 core orchestrator

New rosey.py: 100-line orchestrator replaces 1680 lines:
- Pure orchestration: initialize, connect, wait
- NATS-first: all components use message bus
- Plugin autonomy: zero business logic in core
- Graceful shutdown: signal handlers, cleanup
- Observable: clear logging at each step

Replaces:
- lib/bot.py (1241 lines)
- bot/rosey/rosey.py (439 lines)

Architecture: Orchestration only, plugins own features

Relates-to: Sprint 20 Sortie 2 (Build v1 Branch)"

git push origin v1
```

### Day 5: Manual Smoke Test & Verification (4 hours)

**Step 4.1: Update Requirements**
```powershell
# Verify requirements.txt has all dependencies
code requirements.txt

# Should include:
# - nats-py (NATS client)
# - aiohttp (async HTTP)
# - sqlalchemy (database)
# - All plugin dependencies
```

**Step 4.2: Create Test Config**
```powershell
# Create config-dev.json for testing
cp config.json config-dev.json
code config-dev.json

# Update with test values:
# - NATS URL (local or test server)
# - CyTube credentials (test account)
# - Database path (test database)
```

**Step 4.3: Install Dependencies**
```powershell
# In Python environment
pip install -r requirements.txt
```

**Step 4.4: Run Bot (First Time!)**
```powershell
# Start NATS server (if local)
# (or use remote NATS)

# Run bot
python rosey.py --config config-dev.json

# Expected output:
# 🤖 Rosey v1.0 starting...
# ✓ NATS connected: nats://localhost:4222
# ✓ Loaded 60 plugins
# ✓ Connected to CyTube: test-channel
# 🚀 Rosey v1.0 running!

# Verify:
# - No errors
# - Plugins load
# - CyTube connects
# - Bot responds to test command
```

**Step 4.5: Document Success**
```powershell
# Take screenshots of:
# - Bot startup logs
# - Plugin list
# - CyTube connection
# - Test command response

# Save to docs/sprints/active/20-v1-release-ready/smoke-test-results/
```

**Step 4.6: Final Commit**
```powershell
git add requirements.txt config-dev.json
git commit -m "v1.0 smoke test successful

Manual verification:
- Bot starts without errors
- NATS connection established
- 60 plugins loaded successfully
- CyTube connection works
- Commands route via NATS
- Plugins respond correctly

Core orchestrator: 103 lines (target: ≤150)
Architecture: Plugin-first, NATS-only

Ready for Sortie 3 (Test Migration)

Relates-to: Sprint 20 Sortie 2 (Build v1 Branch)"

git push origin v1
```

---

## Testing Strategy

### Manual Smoke Tests

**Test 1: Bot Starts**
```powershell
python rosey.py --config config-dev.json
# Expected: No exceptions, startup messages appear
```

**Test 2: NATS Connection**
```powershell
# In bot output:
# Expected: "✓ NATS connected: nats://..."
```

**Test 3: Plugins Load**
```powershell
# In bot output:
# Expected: "✓ Loaded 60 plugins" (or actual count)
```

**Test 4: CyTube Connection**
```powershell
# In bot output:
# Expected: "✓ Connected to CyTube: channel-name"
```

**Test 5: Command Response**
```powershell
# In CyTube chat, send: !help
# Expected: Bot responds with available commands
```

### Acceptance Criteria

- [ ] Orphan branch `v1` exists on GitHub
- [ ] Structure matches design (rosey.py, core/, plugins/, common/)
- [ ] rosey.py orchestrator ≤150 lines (ideally ~100)
- [ ] Zero imports from `lib/` anywhere in v1 branch
- [ ] Bot runs: `python rosey.py --config config-dev.json`
- [ ] NATS connection successful
- [ ] Plugins load (count matches expectation)
- [ ] CyTube connection established
- [ ] Test command (`!help`) works
- [ ] All commits pushed to `origin/v1`

---

## Dependencies

### Prerequisites
- Sortie 1 complete (archives created)
- Python 3.12+ environment
- NATS server accessible (local or remote)
- CyTube test account/channel

### External Dependencies
- nats-py (NATS client library)
- aiohttp (async HTTP for CyTube)
- sqlalchemy (database ORM)
- All plugin dependencies (from requirements.txt)

### Blocks
- Sortie 3 (Test Migration) - needs v1 branch complete

---

## Risks & Mitigations

### Risk 1: Core Infrastructure Missing Features
**Likelihood**: Medium  
**Impact**: Medium (need to add features)  

**Mitigation**:
- bot/rosey/core/ already proven working in Sprint 19
- lib/plugin/ patterns documented and understood
- Can add features incrementally if needed
- Smoke test validates core functionality

### Risk 2: Plugins Don't Load
**Likelihood**: Low  
**Impact**: High (blocks smoke test)  

**Mitigation**:
- Plugins already working in Sprint 19
- Copied verbatim (no changes)
- Plugin tests pass 96% in Sprint 19
- Plugin manager from bot/rosey/core/ proven

### Risk 3: Line Count Exceeds Target
**Likelihood**: Medium  
**Impact**: Low (≤150 still acceptable)  

**Mitigation**:
- Design includes full implementation (~100 lines)
- Target is ≤150 lines (buffer included)
- Can refactor if needed
- Core principle is simplicity, not arbitrary line count

---

## Notes

### Why Orphan Branch?
- Clean slate: no git history baggage
- Clear break from v0.9 architecture
- Can still reference archive/pre-v1-sprint-19 if needed
- GitHub UI shows clear "Initial commit" for v1.0

### Why 100 Lines?
- Forces simplicity
- Proves "orchestration only" principle
- 1680 lines → 100 lines is dramatic improvement
- Demonstrates architectural clarity

### What About Tests?
- Tests are Sortie 3 (next week)
- Need v1 architecture complete first
- Will write tests for NATS interfaces
- Keep 201 working plugin tests

---

## Completion Checklist

### Day 1: Structure
- [ ] Orphan branch `v1` created
- [ ] Backup created: Rosey-Robot-backup
- [ ] Essential configs copied
- [ ] plugins/ directory copied
- [ ] common/ directory copied
- [ ] core/ directory copied
- [ ] Initial commit pushed

### Day 2: Core
- [ ] lib/plugin/ patterns reviewed
- [ ] core/plugin_manager.py enhanced
- [ ] core/__init__.py updated
- [ ] Zero lib/ imports verified
- [ ] Core consolidation committed

### Day 3-4: Orchestrator
- [ ] rosey.py created
- [ ] RoseyBot class implemented
- [ ] main() function implemented
- [ ] Signal handlers implemented
- [ ] Line count verified (≤150)
- [ ] Orchestrator committed

### Day 5: Verification
- [ ] requirements.txt updated
- [ ] config-dev.json created
- [ ] Dependencies installed
- [ ] Bot runs successfully
- [ ] NATS connection verified
- [ ] Plugins load verified
- [ ] CyTube connection verified
- [ ] Test command works
- [ ] Screenshots captured
- [ ] Final commit pushed

---

**Estimated Time**: 5 days (Week 1)  
**Actual Time**: _[To be filled after completion]_  
**Completed By**: _[To be filled]_  
**Completion Date**: _[To be filled]_  

---

**Next Sortie**: [SPEC-Sortie-3-Test-Migration.md](SPEC-Sortie-3-Test-Migration.md)
