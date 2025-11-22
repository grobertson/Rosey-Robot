# Rosey - A Python CyTube Bot Framework

**Fair warning: This implementation is over-engineered. I may do crazy things here at any time. If you're not a person who likes reading documentation, this may not be the project for you. With that said, welcome! As with most of my hobby projects this is MIT licensed, keep FOSS fun and open!**

[![Version](https://img.shields.io/badge/version-0.6.1-blue.svg)](https://github.com/grobertson/Rosey-Robot/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Database](https://img.shields.io/badge/database-SQLite%20%7C%20PostgreSQL-green.svg)](docs/DATABASE_SETUP.md)

**Rosey** is an event-driven Python bot framework for [CyTube](https://github.com/calzoneman/sync) channels, built on a **microservices-on-a-bus** architecture. Services communicate through [NATS](https://nats.io/) messaging, enabling loosely-coupled components that can scale independently while staying simple to develop and deploy.

## 🎯 Architecture: Microservices on a Bus

Rosey uses **NATS** as a lightweight message bus to connect independent services:

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CyTube    │────▶│  NATS Bus   │◀────│  Database   │
│ Connection  │     │   (pub/sub  │     │   Service   │
└─────────────┘     │  req/reply) │     └─────────────┘
                    └─────────────┘
                          ▲ │
                          │ ▼
                    ┌─────────────┐
                    │   LLM/AI    │
                    │   Service   │
                    └─────────────┘
```

**Benefits:**
- **Loose Coupling**: Services don't know about each other, only events
- **Independent Scaling**: Add LLM servers, database replicas independently
- **Hot Reload**: Restart services without dropping connections
- **Testing**: Mock any service by subscribing to its topics
- **Observability**: Monitor all events flowing through the bus

**Example**: When a user chats, the connection publishes `chat.message` → Database subscribes for logging → LLM subscribes for trigger matching → Both process independently in parallel.

## 🎯 Project Goals

- **Event-Driven**: Everything communicates through NATS pub/sub and request/reply
- **Service-Oriented**: Database, LLM, and connection layers run as independent services
- **Modern Python**: Async/await throughout, SQLAlchemy 2.0 ORM, type hints
- **Dual Database**: SQLite for development, PostgreSQL for production (with migrations)
- **AI-Powered**: OpenAI, Ollama, and custom LLM providers with smart triggers
- **Production Ready**: Systemd services, monitoring, hot reload, comprehensive testing

## 📁 Project Structure

```
rosey-robot/
├── lib/                    # Core CyTube interaction library
│   ├── bot.py             # Main bot class
│   ├── channel.py         # Channel state management
│   ├── playlist.py        # Playlist operations
│   ├── socket_io.py       # Socket.IO connection handling
│   ├── user.py            # User representation
│   ├── media_link.py      # Media link parsing
│   ├── util.py            # Utility functions
│   ├── error.py           # Custom exceptions
│   └── proxy.py           # Proxy support
│
├── bot/                   # Main Rosey bot application
│   └── rosey/            # Rosey - full-featured CyTube bot
│       ├── rosey.py      # Main bot script
│       ├── prompt.md     # AI personality prompt (for future LLM integration)
│       └── config.json.dist  # Example configuration
│
├── examples/              # Example bot implementations
│   ├── tui/              # Terminal UI chat client ⭐ Featured!
│   ├── log/              # Simple chat/media logging bot
│   ├── echo/             # Echo bot example
│   └── markov/           # Markov chain text generation bot
│
├── common/                # Shared utilities
│   ├── config.py         # Configuration management
│   ├── database.py       # SQLite database for stats tracking
│   └── shell.py          # Interactive shell for remote control
│
├── web/                   # Web status dashboard
│   ├── status_server.py  # Flask web server
│   ├── templates/        # HTML templates
│   └── README.md         # Web server documentation
│
└── requirements.txt       # Python dependencies
```

## 🚀 Quick Start

### Installation

```bash
# Clone and install
git clone https://github.com/grobertson/Rosey-Robot.git
cd Rosey-Robot
pip install -r requirements.txt

# Start NATS server (required for all services)
docker-compose up -d nats

# Run database migrations
alembic upgrade head

# Start the bot
python -m lib.bot config.json
```

### Configuration

Copy `config.json.dist` to `config.json` and customize:

```json
{
  "domain": "https://cytu.be",
  "channel": ["YourChannel", "optional-password"],
  "user": ["BotUsername", "optional-password"],
  "database_url": "sqlite+aiosqlite:///bot_data.db",
  "nats": {
    "servers": ["nats://localhost:4222"]
  }
}
```

**Database options:**
- SQLite (dev): `sqlite+aiosqlite:///bot_data.db` (default)
- PostgreSQL (prod): `postgresql+asyncpg://user:pass@host/db`
- See [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md) for details

### Services Architecture

Run services independently or together:

**All-in-one (development):**
```bash
python -m lib.bot config.json
# Starts: Connection + Database + NATS in one process
```

**Separate services (production):**
```bash
# Terminal 1: NATS server
docker-compose up -d nats

# Terminal 2: Database service
python -m common.database_service config.json

# Terminal 3: Bot connection
python -m lib.bot config.json

# Terminal 4: LLM service (optional)
python -m bot.rosey.llm_service config.json
```

**Why separate?**
- Restart LLM service without dropping CyTube connection
- Scale database service to multiple replicas
- Hot-reload code changes per service
- Independent logging and monitoring

### NATS Event Bus

All services communicate through NATS subjects:

**Subjects:**
- `rosey.chat.message` - Incoming chat messages
- `rosey.database.*` - Database operations (pub/sub)
- `rosey.llm.request` - LLM completion requests (req/reply)
- `rosey.connection.command` - Bot commands (req/reply)

**Example:** Subscribe to all events:
```bash
nats sub "rosey.>" --server=nats://localhost:4222
```

This shows every event flowing through the system in real-time—perfect for debugging!

## 🤖 LLM Integration (Microservice)

The LLM service runs independently and subscribes to chat events via NATS:

**Supported Providers:**
- **OpenAI** - GPT-4, GPT-4o, GPT-3.5-turbo
- **Ollama** - Local models (Llama 3, Mistral, etc.) - FREE!
- **Azure OpenAI** - Enterprise OpenAI hosting
- **OpenRouter** - Multi-provider access

### Quick Setup

**1. Choose a Provider:**

**Option A: OpenAI (easiest, paid)**
```json
{
  "llm": {
    "enabled": true,
    "provider": "openai",
    "openai": {
      "api_key": "sk-YOUR_API_KEY",
      "model": "gpt-4o-mini"
    },
    "triggers": {
      "enabled": true,
      "direct_mention": true
    }
  }
}
```

**Option B: Ollama (free, runs locally)**
```bash
# Install Ollama
curl https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3

# Start server
ollama serve
```

```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "llama3"
    },
    "triggers": {
      "enabled": true,
      "direct_mention": true
    }
  }
}
```

**2. Install Dependencies:**
```bash
pip install "openai>=1.0.0"  # For OpenAI provider
pip install "aiohttp>=3.9.0"  # For all providers
```

**3. Run Bot:**
```bash
python bot/rosey/rosey.py bot/rosey/config.json
```

Bot will now respond when mentioned:
```
User: "hey Rosey, tell me a joke"
Rosey: "Why did the bot go to therapy? It had too many connection issues!"
```

### Features

- **Smart Triggers**: Respond to mentions, commands, keywords, or ambient chat
- **Conversation Context**: Remembers recent conversation per user
- **Flexible Configuration**: Control response probability, cooldowns, greetings
- **Production Ready**: Works with systemd, supports remote Ollama servers
- **Cost Control**: Rate limiting, configurable token limits

### Documentation

- **[Complete LLM Configuration Guide](docs/guides/LLM_CONFIGURATION.md)** - Setup for all providers, trigger configuration, troubleshooting
- **[Systemd Deployment with LLM](systemd/README.md)** - Production deployment guide

### Example Configurations

**Simple (mention only):**
```json
{"llm": {"enabled": true, "provider": "openai", "openai": {"api_key": "sk-...", "model": "gpt-4o-mini"}}}
```

**Advanced (keywords, ambient, greetings):**
```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "ollama": {"base_url": "http://localhost:11434", "model": "llama3"},
    "triggers": {
      "enabled": true,
      "direct_mention": true,
      "commands": ["!ai", "!ask"],
      "ambient_chat": {"enabled": true, "every_n_messages": 20},
      "keywords": [
        {"phrases": ["interesting"], "probability": 0.1, "cooldown_seconds": 300}
      ],
      "greetings": {
        "enabled": true,
        "on_join": {"enabled": true, "probability": 0.2}
      }
    }
  }
}
```

See [docs/guides/LLM_CONFIGURATION.md](docs/guides/LLM_CONFIGURATION.md) for complete details.

### Web Dashboard (Service)

The web dashboard queries database via NATS request/reply:

```bash
python web/status_server.py
# Opens: http://127.0.0.1:5000
```

**Features:**
- Real-time user count graphs
- Top chatters leaderboard
- Historical data (1h/6h/24h/7d)
- Auto-refresh every 30s
- Queries through NATS (no direct DB access)

See [web/README.md](web/README.md) for details.

## 🚀 Production Deployment

For production environments, use systemd services to run the bot and web server:

### Linux (systemd)

```bash
# Copy service files
sudo cp systemd/*.service /etc/systemd/system/

# Create log directory
sudo mkdir -p /var/log/cytube-bot
sudo chown youruser:youruser /var/log/cytube-bot

# Edit service files to match your setup
sudo nano /etc/systemd/system/cytube-bot.service
sudo nano /etc/systemd/system/cytube-web.service

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable cytube-bot cytube-web
sudo systemctl start cytube-bot cytube-web

# Check status
sudo systemctl status cytube-bot
sudo systemctl status cytube-web
```

See [systemd/README.md](systemd/README.md) for complete documentation.

### Windows

Use Windows Task Scheduler or NSSM (Non-Sucking Service Manager):

**Task Scheduler:**
1. Create a basic task for the bot
2. Create another task for the web server
3. Set both to run at startup
4. Use `pythonw.exe` to run without console window

**NSSM (recommended):**
```cmd
# Download from https://nssm.cc/
nssm install CyTubeBot "C:\Python\python.exe" "H:\bots\echo\bot.py" "config.json"
nssm install CyTubeWeb "C:\Python\python.exe" "H:\cytube-bot\web\status_server.py"
nssm start CyTubeBot
nssm start CyTubeWeb
```

## 🔧 Creating Your Own Service

Extend Rosey by subscribing to NATS topics:

```python
import asyncio
import json
from nats.aio.client import Client as NATS

async def run_my_service():
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    
    async def message_handler(msg):
        data = json.loads(msg.data.decode())
        username = data['username']
        message = data['message']
        
        # Your logic here
        if "keyword" in message.lower():
            # Publish response back to connection service
            await nc.publish('rosey.connection.command', json.dumps({
                'action': 'chat',
                'message': f"@{username} I noticed that!"
            }).encode())
    
    # Subscribe to chat messages
    await nc.subscribe('rosey.chat.message', cb=message_handler)
    
    print("Service running! Listening for messages...")
    
    # Keep running
    while True:
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(run_my_service())
```

**Your service automatically:**
- Gets all chat messages in real-time
- Can trigger bot actions (chat, PM, playlist)
- Runs independently (restart without dropping connection)
- Scales horizontally (multiple instances)

## 📚 Core Library API

### Bot Class

The main `Bot` class provides methods for interacting with CyTube:

#### Chat Methods
- `await bot.chat(msg, meta=None)` - Send a chat message
- `await bot.pm(to, msg, meta=None)` - Send a private message
- `await bot.clear_chat()` - Clear the chat (requires permissions)

#### Playlist Methods
- `await bot.add_media(link, append=True, temp=True)` - Add media to playlist
- `await bot.remove_media(item)` - Remove a playlist item
- `await bot.move_media(item, after)` - Reorder playlist
- `await bot.set_current_media(item)` - Jump to a specific item

#### User Management
- `await bot.kick(user, reason='')` - Kick a user
- `await bot.set_leader(user)` - Assign leader
- `await bot.set_afk(value=True)` - Set AFK status

#### Event System
- `bot.on(event, *handlers)` - Register event handlers
- `bot.off(event, *handlers)` - Unregister event handlers
- `await bot.trigger(event, data)` - Manually trigger an event

#### Available Events
- `'chatMsg'` - Chat message received
- `'pm'` - Private message received
- `'setCurrent'` - Media changed
- `'queue'` - Media added to playlist
- `'delete'` - Media removed from playlist
- `'userlist'` - User list updated
- `'addUser'` - User joined
- `'userLeave'` - User left
- `'login'` - Bot logged in
- And many more...

### Channel State

Access channel information through `bot.channel`:

```python
bot.channel.name          # Channel name
bot.channel.motd          # Message of the day
bot.channel.userlist      # Dictionary of users
bot.channel.playlist      # Playlist object
bot.channel.permissions   # Channel permissions
```

### Playlist

Access playlist through `bot.channel.playlist`:

```python
playlist.current          # Currently playing item
playlist.queue            # List of queued items
playlist.locked           # Whether playlist is locked
playlist.get(uid)         # Get item by UID
```

## 🔮 Future Development

### Implemented Features

- ✅ Web Dashboard for monitoring bot status
- ✅ **Database Integration** - Dual-database support with SQLite (development) and PostgreSQL (production). Environment-aware connection pooling, async ORM, migrations via Alembic. See [docs/DATABASE_SETUP.md](docs/DATABASE_SETUP.md) and [docs/MIGRATIONS.md](docs/MIGRATIONS.md)
- ✅ PM Command Interface for administrative control via private messages
- ✅ **LLM Chat Integration** - AI-powered responses with OpenAI, Ollama, and OpenRouter support. Smart triggers, conversation context, flexible configuration. See [docs/guides/LLM_CONFIGURATION.md](docs/guides/LLM_CONFIGURATION.md)

### Planned Features

1. **Advanced Playlist Features**
   - Smart playlist management
   - Media recommendations
   - Duplicate detection
   - Automatic queue filling

2. **Enhanced Bot Capabilities**
   - Plugin system for easy extensibility
   - Multi-channel support (one bot, multiple channels)

3. **AI-Powered Features**
   - Sentiment analysis for channel mood tracking
   - Enhanced content moderation
   - Learning from user preferences over time
   - Multi-turn conversation improvements

## 🧪 Testing

This project has comprehensive test coverage with 600+ tests across unit and integration suites.

### Quick Start

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest --cov

# Run unit tests only (faster)
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Generate coverage report
pytest --cov --cov-report=html
start htmlcov/index.html  # Windows
open htmlcov/index.html   # macOS
```

### Test Organization

- **Unit Tests** (`tests/unit/`): Test individual components in isolation with heavy mocking
- **Integration Tests** (`tests/integration/`): Test multi-component workflows with real implementations
- **Coverage Target**: 85% overall (66% minimum floor)
- **Current Coverage**: ~92% average across all modules

### Test Coverage by Module

| Module | Tests | Coverage |
|--------|-------|----------|
| lib/user.py | 48 | 100% |
| lib/util.py | 58 | 93% |
| lib/media_link.py | 75 | 100% |
| lib/playlist.py | 66 | 100% |
| lib/channel.py | 44 | 100% |
| lib/bot.py | 73 | 44% |
| common/database.py | 102 | 96% |
| common/shell.py | 65 | 86% |
| Integration | 30 | N/A |
| **Total** | **567** | **~92%** |

### Testing Documentation

See **[TESTING.md](docs/TESTING.md)** for comprehensive testing guide including:

- Writing new tests
- Test fixtures and utilities
- Running specific tests
- Debugging test failures
- Best practices

### Running Specific Tests

```bash
# Run specific module tests
pytest tests/unit/test_user.py -v

# Run specific test
pytest tests/unit/test_user.py::TestUserInit::test_init_basic

# Run tests matching pattern
pytest -k "test_database" -v

# Show coverage for specific module
pytest tests/unit/test_user.py --cov=lib.user --cov-report=term-missing
```

## 🛠️ Development

### Why Microservices-on-a-Bus?

**The Problem:** Traditional monolithic bots require full restarts for any change—dropping connections and losing state.

**The Solution:** Services communicate through NATS messaging:
- **Loose Coupling**: Services don't import each other, only publish/subscribe to topics
- **Hot Reload**: Restart LLM service without dropping CyTube connection
- **Independent Scaling**: Run 5 LLM workers, 2 database replicas, 1 connection
- **Easy Testing**: Mock any service by subscribing to its topics
- **Observability**: `nats sub "rosey.>"` shows all events in real-time

### Project Evolution

Originally forked from [dead-beef's cytube-bot](https://github.com/dead-beef/cytube-bot), Rosey has evolved significantly:

**v0.1-0.5:** Traditional monolithic bot  
**v0.6:** Microservices-on-a-bus architecture with NATS  
**v0.6.1:** SQLAlchemy ORM, PostgreSQL support, async throughout

**Major Changes:**
- Async/await everywhere (Python 3.11+)
- NATS message bus for service communication
- SQLAlchemy 2.0 ORM with Alembic migrations
- Dual database: SQLite (dev) + PostgreSQL (prod)
- LLM integration as independent service
- 1000+ tests, 61% coverage

## 📝 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Rosey is an ongoing project with goals of creating a flexible, modern CyTube bot framework with potential AI capabilities.

## ⚠️ Notes

- Requires Python 3.8+
- Uses asyncio for all I/O operations
- Socket.IO connection via websockets
- Some features require specific channel permissions

## 📞 Support

For CyTube-related questions, see the [CyTube documentation](https://github.com/calzoneman/sync/wiki).

For Rosey-specific issues, please open an issue in this repository.
