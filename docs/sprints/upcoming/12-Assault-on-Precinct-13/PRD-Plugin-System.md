# Product Requirements Document: Plugin System & Rosey CLI Management

**Version:** 2.0  
**Status:** Planning (Sprint 12)  
**Sprint Name:** Sprint 12 "Assault on Precinct 13" - *Defending the boundaries*  
**Target Release:** v0.7.0  
**Author:** GitHub Copilot (Claude Sonnet 4.5)  
**Date:** November 21, 2025  
**Priority:** HIGH - Architecture Foundation  
**Dependencies:** Sprint 11 (SQLAlchemy) MUST be complete  

---

## Executive Summary

Sprint 12 "Assault on Precinct 13" establishes a **pragmatic plugin system** with single-archive packaging (`.roseyplug` files), isolated storage, and a **unified `rosey` CLI** for managing all bot services. With Sprint 11's SQLAlchemy foundation, each plugin gets its own isolated SQLite database and sandboxed file access.

**The Opportunity**:

- Plugins are scattered directories with manual installation
- No service management tool (start/stop bot, NATS, database)
- No storage isolation between plugins
- No standardized plugin distribution format

**The Solution**:

1. **Single-Archive Packaging**: `.roseyplug` files (ZIP-based) with manifest, code, assets
2. **Isolated Storage**: Private SQLite database + sandboxed files per plugin
3. **Hot Reload**: Install/update/remove plugins without bot restart
4. **Unified CLI**: `rosey` command manages all services (bot, NATS, database, plugins)
5. **Simple Distribution**: Install from local files or Git repos (no marketplace infrastructure)
6. **Trust-Based Security**: Permissions declared but not enforced (users review before install)

**Key Achievement Goals**:

- **Plugin**: `rosey plugin install ./markov-chat.roseyplug` or `rosey plugin install https://github.com/user/plugin.git`
- **Services**: `rosey start`, `rosey status`, `rosey logs -f`, `rosey restart bot`
- **Database**: `rosey db migrate`, `rosey db backup`, `rosey db shell`

**Movie Connection**: *Assault on Precinct 13* (1976) - defending the precinct (bot core) through strong boundaries, but with pragmatic trust among the defenders (plugins).

---

## 1. Problem Statement

### 1.1 Current Pain Points

**Distribution Chaos**:

- Plugins are loose directories (`examples/markov/`, `examples/echo/`)
- Manual installation: copy files, install dependencies, edit config
- No version tracking or update mechanism
- Breaking changes not communicated

**Storage Anarchy**:

- Plugins share single database (`bot_data.db`)
- No storage isolation - markov plugin can corrupt echo plugin's data
- No cleanup on plugin removal - orphaned tables remain
- File system access unrestricted - plugins can read/write anywhere

**Service Management Gap**:

- No unified tool to start/stop bot, NATS, database
- Manual `python -m lib.bot`, `docker-compose up`, etc.
- No log aggregation across services
- No health monitoring

**Developer Friction**:

- No plugin template or scaffolding tools
- No testing framework for plugins
- Manual manifest creation (error-prone)
- No documentation generation

### 1.2 User Stories

**As a bot operator**, I want to:

- **Services**: `rosey start` to start all services, `rosey status` to check health
- **Plugins**: Install from file (`rosey plugin install ./plugin.roseyplug`) or Git (`rosey plugin install https://github.com/user/plugin.git`)
- **Management**: `rosey plugin list`, `rosey logs bot -f`, `rosey restart nats`
- **Database**: `rosey db migrate`, `rosey db backup`, `rosey db shell`
- **Development**: `rosey dev` to start all services in development mode
- **Cleanup**: `rosey plugin remove markov-chat` deletes all plugin data (no orphans)

**As a plugin developer**, I want to:

- **Scaffold**: `rosey plugin create my-plugin` generates template
- **Test**: `rosey plugin test my-plugin` runs isolated tests
- **Package**: `rosey plugin build` creates `.roseyplug` file
- **Share**: Push to GitHub, share `.roseyplug` file directly
- **Storage**: Automatic isolated database + sandboxed file directory
- **Discovery**: Tag repo with `rosey-plugin` for community findability

**As a system admin**, I want to:

- **Review**: See permissions during install (informational, trust-based)
- **Monitor**: `rosey logs` for all services, per-plugin logs available
- **Control**: Stop/start individual services without full bot restart
- **Backup**: `rosey db backup` for all databases (bot + plugins)

---

## 2. Goals & Success Metrics

### 2.1 Primary Goals

| Goal ID | Goal | Success Metric |
|---------|------|----------------|
| **PG-001** | **Single-Archive Packaging** | All plugins distributed as `.roseyplug` files (ZIP-based with manifest) |
| **PG-002** | **Isolated Storage** | Each plugin has private SQLite DB + sandboxed file directory |
| **PG-003** | **Hot Reload** | Install/update/remove plugins without bot restart (>99% success) |
| **PG-004** | **Unified CLI** | `rosey` command manages all services (bot, NATS, database, plugins) |
| **PG-005** | **Developer Tools** | CLI tool for create, test, build workflow |
| **PG-006** | **Storage Cleanup** | Plugin removal deletes all data (0 orphaned tables/files) |
| **PG-007** | **Git + File Install** | Install from local `.roseyplug` or Git repository URL |

### 2.2 Success Metrics

| Metric | Baseline (v0.6.0) | Target (v0.7.0) | Measurement |
|--------|-------------------|-----------------|-------------|
| Installation Steps | ~10 manual steps | 1 command | User testing |
| Install Time | ~5 minutes | <30 seconds | Automated tests |
| Storage Isolation | 0% (shared DB) | 100% (private DB) | Architecture review |
| Plugin Removal Cleanup | ~30% (manual) | 100% (automatic) | Automated tests |
| Service Management | Manual scripts | Unified CLI | Feature completion |
| Developer Onboarding | ~2 hours | <15 minutes | User testing |

---

## 3. High-Level Architecture

### 3.1 Plugin Archive Format (`.roseyplug`)

**Structure** (ZIP-based):

```text
markov-chat-1.2.0.roseyplug  (ZIP file)
├── manifest.yaml             # Plugin metadata and permissions
├── plugin.py                 # Main entry point (REQUIRED)
├── requirements.txt          # Python dependencies (optional)
├── assets/                   # Static files (optional)
│   ├── icon.png
│   ├── templates/
│   └── static/
├── migrations/               # Database migrations (optional)
│   ├── 001_initial.sql
│   └── 002_add_indexes.sql
├── tests/                    # Unit tests (optional)
│   ├── test_plugin.py
│   └── fixtures/
├── README.md                 # Documentation (optional)
└── LICENSE                   # License file (optional)
```

**Manifest Format** (`manifest.yaml`):

```yaml
# Identity
name: markov-chat
version: 1.2.0
display_name: Markov Chat Bot
description: Generates text responses using Markov chains trained on chat history
author: community_user
homepage: https://github.com/user/markov-chat
license: MIT

# Entry point
entry_point: plugin.py
main_class: MarkovPlugin  # Optional - defaults to Plugin

# Dependencies
python_requires: ">=3.10,<4.0"
dependencies:
  - markovify>=0.9.0
  - nltk>=3.8.0

# Permissions (informational - displayed during install, not enforced)
permissions:
  - read_messages      # Subscribe to rosey.chat.message.*
  - send_messages      # Publish to rosey.chat.send_message
  - database_access    # Access plugin-specific database
  - http_requests      # Make external HTTP/HTTPS requests
  - file_read          # Read from plugin storage directory
  - file_write         # Write to plugin storage directory

# Resource Limits (optional monitoring - not enforced)
resources:
  cpu_limit: 0.25           # Suggested max 25% CPU
  memory_limit: 100M        # Suggested max 100MB RAM
  storage_limit: 500M       # Suggested max 500MB storage

# Configuration Schema (validated at install)
config_schema:
  type: object
  properties:
    markov_order:
      type: integer
      minimum: 1
      maximum: 5
      default: 2
      description: Markov chain order (higher = more coherent but less random)
    learn_enabled:
      type: boolean
      default: false
      description: Learn from chat messages automatically
  required:
    - markov_order

# Metadata (optional - for discovery)
tags:
  - chat
  - ai
  - markov
  - text-generation
```

### 3.2 Isolated Storage Architecture

**Per-Plugin Storage**:

```text
data/
├── plugins/
│   ├── markov-chat/
│   │   ├── database.db         # Private SQLite database
│   │   ├── files/              # Sandboxed file directory
│   │   │   ├── markov_model.txt
│   │   │   └── cache/
│   │   └── config.yaml         # Plugin-specific config
│   ├── quote-bot/
│   │   ├── database.db
│   │   ├── files/
│   │   │   └── quotes.json
│   │   └── config.yaml
│   └── weather-alerts/
│       ├── database.db
│       ├── files/
│       │   └── api_cache/
│       └── config.yaml
└── bot_data.db                 # Bot core database (isolated)
```

**Database Isolation** (SQLAlchemy per-plugin):

```python
# Each plugin gets:
# 1. Private database URL
database_url = f"sqlite+aiosqlite:///data/plugins/{plugin_name}/database.db"

# 2. Sandboxed file access
plugin_storage_dir = Path(f"data/plugins/{plugin_name}/files")

# 3. No access to other plugins' data
# 4. No access to bot core database
```

**Storage API** (provided to plugins):

```python
class PluginStorage:
    """
    Storage API provided to each plugin.
    
    Automatically scoped to plugin's isolated directories.
    """
    
    def __init__(self, plugin_name: str):
        self.plugin_name = plugin_name
        self.db = self._init_database()
        self.files = PluginFileSystem(plugin_name)
    
    # Database API (SQLAlchemy)
    async def query(self, sql: str, params: dict = None):
        """Execute SELECT query"""
        pass
    
    async def execute(self, sql: str, params: dict = None):
        """Execute INSERT/UPDATE/DELETE"""
        pass
    
    async def get_session(self) -> AsyncSession:
        """Get SQLAlchemy session for ORM usage"""
        pass
    
    # File API (sandboxed)
    async def read_file(self, path: str) -> bytes:
        """Read file from plugin storage"""
        pass
    
    async def write_file(self, path: str, content: bytes):
        """Write file to plugin storage"""
        pass
    
    async def list_files(self, directory: str = "") -> List[str]:
        """List files in directory"""
        pass
    
    async def delete_file(self, path: str):
        """Delete file"""
        pass
    
    # Config API (type-safe)
    def get_config(self, key: str, default=None):
        """Get config value (validated against schema)"""
        pass
```

### 3.3 Permission System (Trust-Based)

**Permission Hierarchy**:

```yaml
permissions:
  # Communication
  - read_messages         # Subscribe to rosey.chat.message.*
  - send_messages         # Publish to rosey.chat.send_message
  - read_media            # Subscribe to rosey.media.*
  - control_media         # Publish media control commands
  
  # Data Access
  - database_access       # Access plugin-specific database
  - database_migrations   # Run migrations on plugin database
  - config_read           # Read plugin config
  - config_write          # Modify plugin config
  
  # File System
  - file_read             # Read from plugin storage directory
  - file_write            # Write to plugin storage directory
  - temp_files            # Create temporary files (auto-cleaned)
  
  # Network
  - http_requests         # Make HTTP/HTTPS requests
  - websocket_client      # Create WebSocket connections
  
  # Admin (informational warning)
  - bot_control           # Stop/restart bot
  - plugin_management     # Install/remove other plugins
  - system_commands       # Execute shell commands
```

**Permission Display** (trust-based approach):

- Declared in `manifest.yaml`
- **Displayed during install** for user review
- **NOT enforced** at runtime (users trust installed plugins)
- Storage isolation prevents accidental cross-plugin corruption
- Optional audit logging available for monitoring

**Rationale**: Rosey is typically single-operator with trusted plugins. Users review permissions at install time and make trust decisions. Storage isolation prevents accidents, not malice.

### 3.4 Plugin Lifecycle

```text
┌──────────────┐
│  PACKAGED    │  (.roseyplug file or Git repo)
└──────┬───────┘
       │ rosey plugin install <source>
       ↓
┌──────────────┐
│  INSTALLED   │  (extracted to data/plugins/<name>/)
└──────┬───────┘
       │ rosey start or rosey plugin enable
       ↓
┌──────────────┐
│   LOADING    │  (validate manifest, check deps)
└──────┬───────┘
       │ Success
       ↓
┌──────────────┐
│   STARTING   │  (run migrations, init process)
└──────┬───────┘
       │ Success
       ↓
┌──────────────┐     Crash      ┌──────────────┐
│   RUNNING    │ ────────────→  │   CRASHED    │
└──────┬───────┘                └──────┬───────┘
       │ rosey stop or disable           │ Auto-restart
       ↓                                 ↓
┌──────────────┐               ┌──────────────┐
│   STOPPING   │               │  RESTARTING  │
└──────┬───────┘               └──────────────┘
       │ Success
       ↓
┌──────────────┐
│   STOPPED    │
└──────┬───────┘
       │ rosey plugin remove <name>
       ↓
┌──────────────┐
│  REMOVING    │  (cleanup database, files, process)
└──────┬───────┘
       │ Success
       ↓
┌──────────────┐
│   REMOVED    │  (all data deleted)
└──────────────┘
```

---

## 4. Technical Implementation

### 4.1 Core Components

#### Component 1: Plugin Archive Manager

- Extract `.roseyplug` files (ZIP format)
- Validate manifest schema
- Support Git repository cloning (HTTPS + SSH)
- Check dependency compatibility
- Install to `data/plugins/<name>/`

#### Component 2: Plugin Storage Manager

- Create isolated database per plugin
- Create sandboxed file directory
- Enforce storage quotas (optional)
- Complete cleanup on plugin removal

#### Component 3: Plugin Loader

- Import plugin module from archive
- Inject storage API and NATS client
- Start plugin process (subprocess isolation)
- Handle crashes and restarts

#### Component 4: Unified Service Manager (`rosey` CLI)

- Manage bot service (start/stop/restart/logs)
- Manage NATS service (status/purge)
- Manage database (migrate/backup/shell)
- Manage plugins (install/remove/list)
- Development mode (start all services)

### 4.2 Rosey CLI Commands

```bash
# Service Management
rosey start [service]                 # Start bot/nats/web/plugins/all (default: all)
rosey stop [service]                  # Stop specific service or all
rosey restart [service]               # Restart service
rosey status                          # Show health of all services
rosey logs [service] [-f]             # Tail logs (service: bot/nats/plugin-name)
rosey dev                             # Start all services in dev mode (auto-reload)

# Plugin Management
rosey plugin create <name>            # Create from template
rosey plugin build [directory]        # Build .roseyplug from directory (default: current)
rosey plugin install <source>         # Install from:
                                      #   - Local file: ./markov-chat.roseyplug
                                      #   - Git HTTPS: https://github.com/user/plugin.git
                                      #   - Git SSH: git@github.com:user/plugin.git
rosey plugin list                     # List installed plugins (status, version)
rosey plugin enable <name>            # Enable plugin (auto-start)
rosey plugin disable <name>           # Disable plugin (don't auto-start)
rosey plugin remove <name>            # Remove plugin + all data
rosey plugin info <name>              # Show plugin details (permissions, config, storage)
rosey plugin test [directory]         # Run plugin tests

# Database Management
rosey db migrate                      # Run Alembic migrations
rosey db rollback [steps]             # Rollback migrations (default: 1)
rosey db backup [output]              # Backup all databases (bot + plugins)
rosey db restore <file>               # Restore from backup
rosey db shell [plugin]               # Open SQLite/PostgreSQL shell (default: bot)
rosey db status                       # Show migration status

# Configuration Management
rosey config show                     # Display current configuration
rosey config edit                     # Open config.json in $EDITOR
rosey config validate                 # Validate config syntax
rosey config path                     # Show config file path

# Utility Commands
rosey version                         # Show Rosey version
rosey doctor                          # Check system dependencies
rosey clean                           # Clean temporary files, logs
```

### 4.3 Plugin Discovery

**Community Plugins** (no central marketplace):

- **GitHub Topic**: Plugins tagged with `rosey-plugin` topic
- **Curated List**: `docs/COMMUNITY_PLUGINS.md` with verified plugins
- **Direct Sharing**: `.roseyplug` files shared via Discord, forums, etc.
- **Git Installation**: `rosey plugin install https://github.com/user/markov-chat`

**Discovery Workflow**:

```bash
# User finds plugin on GitHub (topic: rosey-plugin)
# Reviews README, permissions, code
# Installs directly from Git
rosey plugin install https://github.com/awesome-user/quote-bot

# Or downloads .roseyplug file and installs locally
rosey plugin install ~/Downloads/quote-bot-1.2.0.roseyplug
```

### 4.4 Migration Strategy

**Existing Plugins** (`examples/`):

- Use `rosey plugin build` to convert directories to `.roseyplug`
- Maintain 100% backward compatibility with adapter
- Migration guide for developers
- Example conversions in documentation

**Database Migration**:

- Detect existing plugin tables in `bot_data.db`
- `rosey db migrate` exports to plugin-specific databases
- Verify data integrity with checksums
- Rollback mechanism via backups

---

## 5. Implementation Phases (4 Sorties)

### Phase 1: Plugin Archive Format & CLI Foundation (Sortie 1) - 6-8 hours

**Goal**: Define `.roseyplug` format and basic `rosey` CLI structure

**Deliverables**:

- Manifest schema (`manifest.yaml`)
- Archive extractor/validator
- Plugin template generator
- Basic `rosey` CLI framework
- `rosey plugin create/build` commands
- Unit tests for archive handling

**Acceptance Criteria**:

- ✅ Create `.roseyplug` from directory
- ✅ Extract `.roseyplug` to `data/plugins/`
- ✅ Validate manifest schema
- ✅ `rosey plugin create` generates template
- ✅ `rosey plugin build` packages directory

### Phase 2: Isolated Storage & Plugin Management (Sortie 2) - 6-8 hours

**Goal**: Per-plugin storage and plugin install/remove commands

**Deliverables**:

- `PluginStorage` class (database + files)
- Database isolation (SQLAlchemy)
- File system sandboxing
- `rosey plugin install/remove/list` commands
- Git repository cloning support
- Complete cleanup on removal

**Acceptance Criteria**:

- ✅ Each plugin has private database
- ✅ File access restricted to plugin directory
- ✅ Install from local file works
- ✅ Install from Git HTTPS/SSH works
- ✅ Complete cleanup on removal
- ✅ No data leakage between plugins

### Phase 3: Service Management & Hot Reload (Sortie 3) - 8-10 hours

**Goal**: Unified service management and dynamic plugin loading

**Deliverables**:

- `rosey start/stop/restart/status` commands
- `rosey logs` with service filtering
- `rosey dev` development mode
- Plugin hot reload (no bot restart)
- Service health monitoring
- Process management

**Acceptance Criteria**:

- ✅ `rosey start` starts all services
- ✅ `rosey status` shows service health
- ✅ `rosey logs -f bot` tails bot logs
- ✅ `rosey dev` starts in watch mode
- ✅ Install plugin without bot restart
- ✅ Plugin crashes don't affect bot

### Phase 4: Database Management & Documentation (Sortie 4) - 6-8 hours

**Goal**: Database CLI commands and complete documentation

**Deliverables**:

- `rosey db migrate/backup/restore/shell` commands
- `rosey config show/edit/validate` commands
- `rosey version/doctor/clean` utilities
- Complete developer guide
- Complete operator guide
- Plugin migration guide (examples/ → `.roseyplug`)
- Community plugin discovery docs

**Acceptance Criteria**:

- ✅ `rosey db migrate` runs Alembic migrations
- ✅ `rosey db backup` saves all databases
- ✅ `rosey db shell` opens SQLite prompt
- ✅ `rosey config edit` opens in $EDITOR
- ✅ All documentation complete
- ✅ Migrated 3 example plugins

---

## 6. Security Considerations

### 6.1 Security Philosophy: Trust with Boundaries

**Approach**: Rosey assumes **trusted operators installing trusted plugins**. Security focuses on:

1. **Accidental Protection**: Storage isolation prevents plugins from accidentally corrupting each other
2. **Transparency**: Permissions displayed during install for user review
3. **Process Isolation**: Plugin crashes don't affect bot core
4. **Cleanup Guarantees**: Complete data removal on uninstall

**Not Goals**:

- Runtime permission enforcement (trust-based)
- Malicious code detection (user responsibility)
- Network traffic filtering (optional monitoring only)

### 6.2 Security Best Practices

**For Operators**:

- ✅ Review plugin source code before install (GitHub repos)
- ✅ Check permissions in manifest during install
- ✅ Install from known/trusted sources
- ✅ Monitor plugin behavior after install (`rosey logs`)
- ✅ Keep regular backups (`rosey db backup`)

**For Developers**:

- ✅ Declare all permissions honestly in manifest
- ✅ Use storage API (don't access file system directly)
- ✅ Handle errors gracefully (don't crash)
- ✅ Document required permissions in README
- ✅ Provide changelog for updates

**Accidental Protection Mechanisms**:

- ✅ Storage isolation (can't corrupt other plugins)
- ✅ Process isolation (crashes don't affect bot)
- ✅ Resource monitoring (detect runaway processes)
- ✅ Complete cleanup (no orphaned data)

---

## 7. Developer Experience

### 7.1 Plugin Template

**Generated by `rosey plugin create my-plugin`**:

```text
my-plugin/
├── manifest.yaml
├── plugin.py
├── requirements.txt
├── tests/
│   └── test_plugin.py
├── README.md
└── LICENSE
```

**`plugin.py` Template**:

```python
"""My Plugin - Description"""
from rosey.plugin import Plugin, on_event

class MyPlugin(Plugin):
    """Main plugin class"""
    
    def __init__(self, storage, config, nats, logger):
        """
        Initialize plugin.
        
        Args:
            storage: PluginStorage instance
            config: Plugin configuration dict
            nats: NATS client instance
            logger: Logger instance
        """
        super().__init__(storage, config, nats, logger)
        self.my_setting = config.get('my_setting', 'default')
    
    async def on_load(self):
        """Called when plugin loads (setup)"""
        self.logger.info("Plugin loaded!")
        # Initialize database tables, load models, etc.
    
    @on_event('rosey.chat.message.user_joined')
    async def handle_user_joined(self, event):
        """Handle user joined event"""
        username = event.data['username']
        self.logger.info(f"{username} joined!")
        
        # Send welcome message
        await self.send_message(f"Welcome {username}!")
    
    @on_event('rosey.chat.message.chat')
    async def handle_chat_message(self, event):
        """Handle chat message event"""
        user = event.data['user']
        content = event.data['content']
        
        # Check for command
        if content.startswith('!myplugin'):
            await self.send_message(f"{user}: Plugin is working!")
    
    async def on_unload(self):
        """Called when plugin unloads (cleanup)"""
        self.logger.info("Plugin unloaded!")
        # Save state, close connections, etc.
```

### 7.2 Testing Framework

```python
# tests/test_plugin.py
import pytest
from rosey.plugin.testing import PluginTestCase, MockStorage, MockNATS

class TestMyPlugin(PluginTestCase):
    plugin_class = MyPlugin
    
    @pytest.fixture
    def config(self):
        return {"my_setting": "test_value"}
    
    async def test_user_joined_sends_welcome(self):
        # Simulate user_joined event
        await self.emit_event('rosey.chat.message.user_joined', {
            'username': 'Alice'
        })
        
        # Assert message was sent
        messages = self.get_sent_messages()
        assert len(messages) == 1
        assert messages[0]['content'] == "Welcome Alice!"
    
    async def test_command_response(self):
        # Simulate chat message
        await self.emit_event('rosey.chat.message.chat', {
            'user': 'Bob',
            'content': '!myplugin'
        })
        
        # Assert response
        messages = self.get_sent_messages()
        assert "Plugin is working!" in messages[0]['content']
```

---

## 8. Success Criteria & Validation

### 8.1 Definition of Done

- [ ] `.roseyplug` archive format implemented
- [ ] Per-plugin SQLite databases working
- [ ] Sandboxed file system access
- [ ] Hot reload (install/update/remove without bot restart)
- [ ] Plugin CLI complete (`create`, `build`, `install`, `remove`, `list`)
- [ ] Service management CLI (`start`, `stop`, `restart`, `status`, `logs`)
- [ ] Database management CLI (`migrate`, `backup`, `restore`, `shell`)
- [ ] Config management CLI (`show`, `edit`, `validate`)
- [ ] Git repository installation working (HTTPS + SSH)
- [ ] Development mode (`rosey dev`) working
- [ ] Complete documentation (developer guide, operator guide)
- [ ] Migrated 3+ `examples/` plugins to `.roseyplug` format
- [ ] Community plugin discovery documentation
- [ ] 90%+ test coverage for plugin system

### 8.2 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Plugin Install Time | <30 seconds | CLI timing |
| Plugin Start Time | <5 seconds | Automated tests |
| Storage Overhead | <10MB per plugin | Disk usage |
| Memory Overhead | <50MB per plugin | Process monitoring |
| Hot Reload Success | >99% | Automated tests |
| Service Start Time | <10 seconds | CLI timing |

---

## 9. Rollout Plan

### Phase 1: Alpha Testing (v0.7.0-alpha1) - Week 1

- Internal testing with 3 migrated example plugins
- Stress test hot reload and service management
- Validate storage isolation
- Test Git installation (HTTPS + SSH)

### Phase 2: Beta Testing (v0.7.0-beta1) - Week 2

- Community testing with plugin developers
- Collect feedback on CLI usability
- Test on different platforms (Linux, macOS, Windows)
- Refine documentation

### Phase 3: Stable Release (v0.7.0) - Week 3

- General availability
- Complete documentation published
- Community plugins list published
- Migration guide for existing deployments

---

## 10. Future Enhancements (Sprint 13+)

**Plugin System**:

- **WebAssembly Plugins**: Run untrusted code in WASM sandbox
- **Plugin Analytics**: Usage metrics, error rates via NATS events
- **Cross-Plugin Communication**: Controlled inter-plugin APIs
- **Plugin Versioning**: Semantic version constraints and updates
- **Plugin Collections**: Bundles of related plugins
- **Plugin Themes**: Customize bot behavior with theme plugins

**CLI Enhancements**:

- **Interactive Mode**: `rosey shell` for interactive management
- **Web Dashboard**: `rosey web start` for browser-based management
- **Remote Management**: Control Rosey on remote servers
- **Deployment Tools**: `rosey deploy` for production deployments
- **Backup Automation**: Scheduled backups via `rosey db backup --schedule`
- **Performance Monitoring**: `rosey monitor` for real-time metrics

**Service Additions**:

- **Plugin Scheduler**: Cron-like scheduling for plugin tasks
- **API Gateway**: REST API for external integrations
- **Metrics Exporter**: Prometheus/Grafana integration
- **Alert System**: Configurable alerts for service health

---

## Appendices

### A. Example Plugins

**1. Markov Chat** (examples/markov → `.roseyplug`)

- Text generation using Markov chains
- Learns from chat history
- Storage: Markov model, chat history database

**2. Quote Bot** (new)

- Random quote responses
- Add/search/delete quotes
- Storage: Quote database with tags

**3. Weather Alerts** (new)

- Fetch weather from API
- Alert on severe weather
- Storage: API cache, user locations

### B. Community Plugin Discovery

**GitHub Topic**: `rosey-plugin`

Users can find plugins by:

1. Searching GitHub for `topic:rosey-plugin`
2. Checking `docs/COMMUNITY_PLUGINS.md` (curated list)
3. Browsing plugin authors' GitHub profiles
4. Community recommendations on Discord/forums

**Plugin Quality Indicators**:

- ⭐ GitHub stars
- 📝 Complete README with examples
- ✅ Test coverage badge
- 📦 Recent updates (active maintenance)
- 🔒 Clear permission declarations
- 📖 Changelog

### C. CLI Examples

See Sortie 3 SPEC for complete CLI command examples and workflows.

---

**Document Status**: ✅ Ready for Implementation Planning  
**Next Step**: Create Sortie 1 SPEC (Plugin Archive Format & CLI Foundation)  

**Key Decisions**:

- ✅ **No marketplace** - local files + Git repos only
- ✅ **Trust-based permissions** - display but don't enforce
- ✅ **Unified CLI** - manage all Rosey services from one command
- ✅ **Storage isolation** - prevent accidents, not malice
- ✅ **Community discovery** - GitHub topics + curated docs

**Movie Tagline**: *"They're defending the station through trust, strong boundaries, and a really good CLI!"* 🎬

