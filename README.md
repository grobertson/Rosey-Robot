# Rosey v1.0 - Plugin-First CyTube Bot

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-v1.0--alpha-orange.svg)

**Clean Slate Architecture** - Plugin-first bot framework built from scratch (November 2025)

Rosey is an event-driven Python bot for [CyTube](https://github.com/calzoneman/sync) with a radical simplicity approach: **117-line orchestrator, zero business logic in core**. All functionality lives in plugins communicating via NATS.

## ✨ What Makes v1.0 Different

**Before (v0.9)**: 1680 lines of confused architecture (lib/bot.py + bot/rosey/rosey.py)  
**After (v1.0)**: 117-line orchestrator, plugin-first from day 1

- 🎯 **100% Plugin-Based**: All commands, features, and logic in plugins
- ⚡ **NATS Everything**: Zero direct dependencies between components
- 🔒 **Process Isolation**: Plugins can't crash the core
- 🧪 **Test-Driven**: 43 core tests + 22 plugin test suites
- 📦 **Clean Architecture**: 93% reduction in core bot complexity

## 🚀 Quick Start

```bash
# 1. Start NATS
docker-compose up -d nats

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp config.json.dist config.json
# Edit config.json with your CyTube channel details

# 4. Run
python rosey.py
```

**Full guide**: [QUICKSTART.md](docs/QUICKSTART.md)

## 🎮 Built-in Plugins

- **🎲 Dice Roller** - D&D notation (`!roll 2d6+3`, `!roll 4d6kh3`)
- **🔮 Magic 8-Ball** - Fortune telling (`!8ball will it work?`)
- **⏰ Countdowns** - Event timers with alerts (`!countdown movie 2025-12-31 23:59`)
- **🧠 Trivia** - Interactive quiz game with scoring (`!trivia start`)
- **💬 Quote DB** - Save memorable quotes (`!quote add "epic quote"`)
- **🔍 Inspector** - Event monitoring (admin-only, `!inspect events *`)

## 🏗️ Architecture

```
rosey.py (117 lines)      # Orchestrator - startup/shutdown ONLY
├── core/                 # Infrastructure (NATS, plugins, CyTube)
│   ├── event_bus.py      # NATS messaging wrapper
│   ├── plugin_manager.py # Plugin lifecycle management
│   ├── cytube_connector.py # CyTube WebSocket bridge
│   └── router.py         # Command routing
├── plugins/              # ALL functionality (60+ files)
│   ├── dice-roller/
│   ├── 8ball/
│   ├── countdown/
│   ├── trivia/
│   ├── quote-db/
│   └── inspector/
├── common/               # Shared services
│   ├── database_service.py # NATS-based database
│   ├── config.py
│   └── models.py
└── tests/                # Test infrastructure
    ├── unit/             # Core component tests
    ├── integration/      # End-to-end tests
    └── conftest.py       # Shared fixtures
```

**See**: [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design

## 📚 Documentation

### User Guides

- **[QUICKSTART.md](docs/QUICKSTART.md)** - Get running in 5 minutes
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System design and principles
- **[MIGRATION-V1.md](docs/MIGRATION-V1.md)** - Upgrading from v0.9

### Developer Guides

- **[PLUGIN-DEVELOPMENT.md](docs/PLUGIN-DEVELOPMENT.md)** - Writing plugins
- **[NATS-CONTRACTS.md](docs/NATS-CONTRACTS.md)** - Event interfaces
- **[docs/guides/](docs/guides/)** - Agent workflows, testing, database

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test suites
pytest tests/unit -m unit          # Core unit tests
pytest plugins -m plugin           # Plugin tests
pytest tests/integration -m integration  # Integration tests

# With coverage
pytest --cov=. --cov-report=html
```

**Test Status**: 22 passing core tests, 22 plugin test suites, CI via GitHub Actions

## 🔄 Migration from v0.9

v0.9 is **archived and preserved**:

- Branch: `archive/pre-v1-main`
- Tag: `v0.9-main-final`

**Key Changes**:

- `lib/bot.py` (1241 lines) → **removed**
- `bot/rosey/rosey.py` (439 lines) → **removed**
- New: `rosey.py` (117 lines) → **orchestrator only**

See [MIGRATION-V1.md](docs/MIGRATION-V1.md) for complete upgrade guide.

## 🎯 Design Principles

1. **Plugin-First**: All business logic in plugins, zero in orchestrator
2. **NATS Everything**: All communication via event bus (no direct calls)
3. **Process Isolation**: Plugins run independently, can't crash core
4. **100-Line Orchestrator**: Forces simplicity, proves "orchestration only" works
5. **Interface-First Testing**: Test NATS contracts, not implementation details

## 🚧 Status

**v1.0-alpha** - Active development (Sprint 20: v1.0 Release Ready)

- ✅ **Sortie 1**: Archives created (safety nets)
- ✅ **Sortie 2**: v1 branch built (clean slate)
- ✅ **Sortie 3**: Test migration (infrastructure ready)
- ✅ **Sortie 4**: Documentation (YOU ARE HERE)
- ⏳ **Sortie 5**: Main branch transition (next)

**Target**: Production-ready v1.0.0 by December 17, 2025

## 📄 License

MIT - See [LICENSE](LICENSE)

## 🤝 Contributing

See [PLUGIN-DEVELOPMENT.md](docs/PLUGIN-DEVELOPMENT.md) to write your own plugins!

---

**Built with** ❤️ **and a chainsaw** 🪚 (to cut out 1680 lines of cruft)
