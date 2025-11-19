# Rosey - A Python CyTube Bot Framework

[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/grobertson/Rosey-Robot/releases)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

**Rosey** is a Python-based framework for building bots that interact with [CyTube](https://github.com/calzoneman/sync) channels. Designed as a monolithic application for easier development and customization, Rosey provides a feature-rich main bot along with simple examples to help you get started.

## 🎯 Project Goals

Rosey aims to provide:
- **Feature-Rich Main Bot**: Full-featured CyTube bot with shell control, logging, and database tracking
- **Simple Examples**: Multiple working examples (TUI chat client, logging, echo, markov)
- **Modern Python**: Built for Python 3.8+ with proper asyncio patterns
- **Monolithic Architecture**: All core library code alongside bot implementations for easier development
- **Playlist Management**: Full support for CyTube playlist operations
- **Shell Interface**: Built-in remote control for bot management

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

1. Clone this repository:
```bash
git clone <repository-url>
cd cytube-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Running Rosey (Main Bot)

Rosey is the full-featured CyTube bot with logging, shell control, and database tracking:

```bash
cd bot/rosey
python rosey.py config.json
```

Copy `config.json.dist` to `config.json` and customize with your credentials.

### Running Examples

Each example includes a `config.json.dist` file. Copy it to `config.json` and customize.

**TUI Chat Client** ⭐ (Feature-complete terminal interface):
```bash
cd examples/tui
python bot.py config.yaml
```
See [examples/tui/USER_GUIDE.md](examples/tui/USER_GUIDE.md) for complete documentation.

**Simple Logger** (minimal chat and media logging):
```bash
cd examples/log
python bot.py config.json
```

**Echo Bot** (repeats messages back):
```bash
cd examples/echo
python bot.py config.json
```

**Markov Bot** (learns from chat and generates responses):
```bash
cd examples/markov
python bot.py config.json
```

### Configuration Format

Example `config.json`:
```json
{
  "domain": "https://cytu.be",
  "channel": ["YourChannelName", "optional-password"],
  "user": ["BotUsername", "optional-password"],
  "response_timeout": 0.1,
  "restart_delay": 5,
  "log_level": "INFO",
  "shell": "127.0.0.1:8888"
}
```

#### Configuration Options

- **domain**: CyTube server URL (e.g., `https://cytu.be`)
- **channel**: Channel name or `[name, password]` for password-protected channels
- **user**: `null` (anonymous), `"GuestName"` (guest), or `["Username", "password"]` (registered)
- **response_timeout**: Socket.IO response timeout in seconds
- **restart_delay**: Delay before reconnecting after disconnect (`null` to disable auto-reconnect)
- **log_level**: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- **shell**: REPL server address (`"host:port"` or `null` to disable)
- **proxy**: Optional proxy server (`"host:port"`)

### Using the REPL Shell

If you enable the shell in your config, you can connect via telnet:

```bash
telnet 127.0.0.1 8888
```

Then interact with the bot directly:
```python
>>> bot.user.name
'YourBotName'
>>> await bot.chat("Hello from the shell!")
>>> bot.channel.playlist.current
<PlaylistItem ...>
```

## 🤖 LLM Integration

**NEW in v0.2:** Rosey now supports AI-powered chat responses using Large Language Models!

### Supported Providers

- **OpenAI** - GPT-4, GPT-3.5-turbo (cloud, paid)
- **Azure OpenAI** - OpenAI models hosted on Azure
- **Ollama** - Run models locally (Llama 3, Mistral, etc.) - FREE!
- **OpenRouter** - Access multiple providers through one API
- **LocalAI / LM Studio** - OpenAI-compatible local servers

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

- **[Complete LLM Configuration Guide](docs/LLM_CONFIGURATION.md)** - Setup for all providers, trigger configuration, troubleshooting
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

See [docs/LLM_CONFIGURATION.md](docs/LLM_CONFIGURATION.md) for complete details.

### Web Status Dashboard

View live statistics and metrics in your browser:

```bash
# Windows
run_status_server.bat

# Linux/Mac
./run_status_server.sh
```

Then open: http://127.0.0.1:5000

Features:
- Real-time user count graphs
- Peak statistics (high water marks)
- Top chatters leaderboard
- Historical data (1h/6h/24h/7d views)
- Auto-refreshing every 30 seconds

See [web/README.md](web/README.md) for detailed documentation.

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

## 🤖 Creating Your Own Bot

Create a new directory under `examples/` and subclass the `Bot` class:

```python
#!/usr/bin/env python3
import sys
from pathlib import Path

# Add project root to Python path (allows running from any directory)
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from lib import Bot, MessageParser
from common import get_config

class MyBot(Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg_parser = MessageParser()
        
        # Register event handlers
        self.on('chatMsg', self.handle_chat)
        self.on('setCurrent', self.handle_media_change)
    
    async def handle_chat(self, event, data):
        username = data['username']
        msg = self.msg_parser.parse(data['msg'])
        self.logger.info(f'{username}: {msg}')
        
        # Example: respond to mentions
        if self.user.name in msg:
            await self.chat(f"{username}: You mentioned me!")
    
    async def handle_media_change(self, event, data):
        current = self.channel.playlist.current
        if current:
            self.logger.info(f'Now playing: {current.title}')

async def run_bot():
    conf, kwargs = get_config()
    bot = MyBot(**kwargs)
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        return 0
    
    return 1

def main():
    return asyncio.run(run_bot())

if __name__ == '__main__':
    sys.exit(main())
```

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
- ✅ Database Integration with PostgreSQL for data persistence
- ✅ PM Command Interface for administrative control via private messages
- ✅ **LLM Chat Integration** - AI-powered responses with OpenAI, Ollama, and OpenRouter support. Smart triggers, conversation context, flexible configuration. See [docs/LLM_CONFIGURATION.md](docs/LLM_CONFIGURATION.md)

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

See **[TESTING.md](TESTING.md)** for comprehensive testing guide including:

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

### Why Monolithic?

This project was restructured from a traditional Python package into a monolithic codebase for several reasons:

1. **Easier Development**: No need to reinstall packages after every change
2. **Better Debugging**: All code is local and easy to inspect
3. **Simpler Deployment**: Copy the directory and run
4. **Faster Iteration**: Modify library and bot code together
5. **Learning Friendly**: Everything is visible and accessible

### Project History

Originally based on [dead-beef's cytube-bot](https://github.com/dead-beef/cytube-bot), Rosey has been significantly updated and restructured:

- Updated for modern Python 3.8+ with proper asyncio patterns
- Restructured as a monolithic application for easier development
- Added comprehensive examples including a feature-complete TUI client
- Enhanced with database tracking, web dashboard, and shell control
- Renamed from "CyTube Bot" to "Rosey" to reflect its evolution into a complete application

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
