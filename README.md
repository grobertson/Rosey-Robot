# Rosey v1.0 - Plugin-First CyTube Bot

**Clean Slate Architecture** - Built from scratch November 2025

## Architecture

```
rosey.py (117 lines)      # Orchestrator - startup/shutdown only
core/                     # Infrastructure (NATS, plugins, CyTube)
├── event_bus.py          # NATS messaging
├── plugin_manager.py     # Plugin lifecycle
├── cytube_connector.py   # CyTube WebSocket bridge
└── router.py             # Command routing
plugins/                  # All functionality lives here (60+ files)
├── dice-roller/
├── 8ball/
├── countdown/
├── trivia/
├── quote-db/
└── inspector/
common/                   # Services
├── database_service.py   # NATS-based database
└── config.py             # Configuration
```

## Quick Start

```bash
# Start NATS
docker-compose up -d nats

# Install dependencies
pip install -r requirements.txt

# Configure
cp config.json.dist config.json
# Edit config.json with your CyTube channel

# Run
python rosey.py
```

## Design Principles

1. **Plugin-First**: All business logic in plugins, zero in orchestrator
2. **NATS Everything**: All communication via event bus
3. **Process Isolation**: Plugins run independently, can't crash core
4. **100-Line Orchestrator**: Forces simplicity, proves "orchestration only"

## What Changed from v0.9

- **Removed**: 1680 lines of confused bot architecture (lib/bot.py + bot/rosey/rosey.py)
- **Replaced with**: 117-line orchestrator (this file: rosey.py)
- **Result**: Plugin-first from day 1, zero architectural confusion

## Migration from v0.9

v0.9 is archived in:
- Branch: `archive/pre-v1-main`
- Tag: `v0.9-main-final`

See [docs/MIGRATION-V1.md](docs/MIGRATION-V1.md) for details (coming soon).

## Documentation

- **QUICKSTART.md** - 5-minute setup (coming soon)
- **ARCHITECTURE.md** - System design (coming soon)
- **PLUGIN-DEVELOPMENT.md** - Writing plugins (coming soon)
- **NATS-CONTRACTS.md** - Event interfaces (coming soon)

## Status

**v1.0-alpha** - Active development (Sprint 20)
- ✅ Sortie 1: Archives created
- ✅ Sortie 2: v1 branch built (YOU ARE HERE)
- ⏳ Sortie 3: Test migration (next)
- ⏳ Sortie 4: Documentation
- ⏳ Sortie 5: Main branch transition

## License

MIT - See [LICENSE](LICENSE)
