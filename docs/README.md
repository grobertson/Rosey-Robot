# Documentation Directory

This directory contains all comprehensive documentation for the Rosey-Robot project.

## Directory Structure

```text
docs/
├── README.md                    # This file
├── ARCHITECTURE.md              # System architecture and design
├── TESTING.md                   # Testing strategy and guide
├── SETUP.md                     # Detailed setup instructions
├── SPRINT_NAMING.md             # Sprint naming convention guide
│
├── guides/                      # Feature-specific guides
│   ├── API_TOKENS.md           # API token authentication
│   ├── LLM_CONFIGURATION.md    # LLM integration setup
│   ├── LLM_GUIDE.md            # LLM usage guide
│   ├── NATS_CONFIGURATION.md   # NATS event bus setup
│   └── PM_GUIDE.md             # PM command reference
│
├── sprints/                     # Sprint documentation
│   ├── completed/              # Completed sprints
│   │   ├── 2-start-me-up/     # LLM Integration
│   │   ├── 3-rest-assured/    # REST API Migration
│   │   ├── 4-test-assured/    # Test Coverage
│   │   └── 6a-quicksilver/    # NATS Event Bus
│   │
│   ├── deferred/               # Deferred sprints (postponed)
│   │   ├── 5-ship-it/         # Production Deployment (deferred - using manual deployment)
│   │   └── 6-make-it-real/    # Advanced Deployment (deferred - cost constraints)
│   │
│   └── active/                 # Active/planned sprints
│       ├── 7-the-divide/      # Architecture refactoring (planned)
│       ├── 8-inception/       # TBD
│       └── 9-funny-games/     # TBD
│
└── archive/                     # Historical/deprecated documents
    ├── BRAIN_SURGERY_SUMMARY.md    # Historical LLM sprint notes
    ├── TUI_FUTURE.md              # TUI migration notes
    ├── WEB_STATUS_SUMMARY.md      # Web status implementation notes
    └── roadmap-sprint-7-9.md      # Old roadmap (superseded)
```

## Quick Links

### Getting Started

- **[Quickstart Guide](../QUICKSTART.md)** - Get up and running in 5 minutes
- **[Setup Guide](SETUP.md)** - Detailed installation and configuration
- **[README](../README.md)** - Project overview and features

### Development

- **[Agent Workflow](../AGENTS.md)** - Development workflow with GitHub Copilot
- **[Architecture](ARCHITECTURE.md)** - System design and NATS event bus
- **[Testing](TESTING.md)** - Testing strategy and coverage
- **[Sprint Naming](SPRINT_NAMING.md)** - Sprint naming convention (movie titles)

### Feature Guides

- **[PM Commands](guides/PM_GUIDE.md)** - Moderator command reference
- **[LLM Integration](guides/LLM_GUIDE.md)** - AI chat features
- **[NATS Configuration](guides/NATS_CONFIGURATION.md)** - Event bus setup
- **[API Tokens](guides/API_TOKENS.md)** - Token authentication

### Sprint Documentation

- **[Completed Sprints](sprints/completed/)** - Finished work (2, 3, 4, 6a)
- **[Deferred Sprints](sprints/deferred/)** - Postponed work (5, 6)
- **[Active Sprints](sprints/active/)** - Current and planned work (7-9)

## Document Organization

### Root Directory

Only essential quick-reference documents remain in the project root:

- **AGENTS.md** - Agent-assisted development workflow
- **CHANGELOG.md** - Version history and release notes
- **QUICKSTART.md** - 5-minute getting started guide
- **README.md** - Main project documentation

### Guides Directory

Feature-specific setup and usage guides:

- Configuration guides (NATS, LLM, API)
- Command references (PM commands)
- User-facing documentation

### Sprints Directory

All sprint documentation organized by status:

- **completed/** - Sprints that have been fully implemented and merged
- **deferred/** - Sprints that are postponed due to cost or priority constraints
- **active/** - Sprints currently in progress or planned for future work

Each sprint contains:
- **PRD-{Feature}.md** - Product requirements document
- **SPEC-Sortie-{N}-{Name}.md** - Technical specifications for each sortie

### Archive Directory

Historical documents that are no longer actively maintained but kept for reference:

- Sprint summaries and notes
- Deprecated feature documentation
- Old roadmaps and planning documents

## Maintenance

When adding new documentation:

1. **Feature guides** → `docs/guides/`
2. **New sprints** → `docs/sprints/active/` (until completed)
3. **Completed sprints** → Move to `docs/sprints/completed/`
4. **Deferred sprints** → Move to `docs/sprints/deferred/` if postponed
5. **Root-level docs** → Only for AGENTS, CHANGELOG, QUICKSTART, README
6. **Historical docs** → `docs/archive/` when no longer relevant

## See Also

- [Contributing Guidelines](../README.md#contributing)
- [License](../LICENSE)
- [Version History](../CHANGELOG.md)
