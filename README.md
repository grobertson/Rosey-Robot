# Rosey - A Python CyTube Bot Framework

![Rosey Robot Logo](assets/Rosey-Robot-Logo.webp)

**Fair warning: This implementation is over-engineered. I may do crazy things here at any time. If you're not a person who likes reading documentation, this may not be the project for you. With that said, welcome! As with most of my hobby projects this is MIT licensed, keep FOSS fun and open!**

[![Version](https://img.shields.io/badge/version-0.7.0-blue.svg)](https://github.com/grobertson/Rosey-Robot/releases)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Database](https://img.shields.io/badge/database-SQLite%20%7C%20PostgreSQL-green.svg)](docs/DATABASE_SETUP.md)

**Rosey** is an event-driven Python bot framework for [CyTube](https://github.com/calzoneman/sync) channels, built on an **Event-Driven Microservices** architecture. Services communicate through [NATS](https://nats.io/) messaging, enabling loosely-coupled components that can scale independently while staying simple to develop and deploy.

## 🎮 Features & Plugins

**Core Framework:**
- **Event-Driven Architecture**: NATS pub/sub and request/reply messaging
- **Service-Oriented**: Database, LLM, and connection layers as independent services
- **Modern Python**: Async/await, SQLAlchemy 2.0 ORM, comprehensive type hints
- **Dual Database**: SQLite (dev) and PostgreSQL (prod) with Alembic migrations
- **Production Ready**: Systemd services, monitoring, hot reload, 85%+ test coverage

**Games & Entertainment** (Sprint 18 - Funny Games):
- **🎲 Dice Roller**: Full D&D dice notation (`!roll 2d6+3`, `!roll 4d6kh3`)
- **🔮 Magic 8-Ball**: Mystical fortune telling with personality
- **⏰ Countdowns**: One-time and recurring timers with T-minus alerts
- **🧠 Trivia**: Multi-category quiz game with scoring and leaderboards

**AI & Automation:**
- **💬 LLM Chat**: OpenAI, Ollama, Azure OpenAI, and OpenRouter support
- **📝 Quote Database**: Save and recall memorable quotes
- **🎵 Playlist Manager**: Media queue management

**Admin & Observability:**
- **🔍 Inspector**: Real-time NATS event monitoring (admin-only)
- **📊 Web Dashboard**: Status and metrics (coming soon)

See **[docs/PLUGINS.md](docs/PLUGINS.md)** for complete plugin documentation.

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

## 🤖 LLM Integration

The LLM service runs independently and subscribes to chat events via NATS. Supports **OpenAI**, **Ollama**, **Azure OpenAI**, and **OpenRouter**.

See [docs/guides/LLM_CONFIGURATION.md](docs/guides/LLM_CONFIGURATION.md) for complete details.

## 🛠️ Development

Want to hack on Rosey?

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest --cov
```

**Creating Your Own Service:**

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
        print(f"Chat: {data['message']}")
    
    await nc.subscribe('rosey.chat.message', cb=message_handler)
    while True: await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(run_my_service())
```

## 📝 License

MIT License - See LICENSE file for details.

## 🙏 Thanks

- **dead-beef** for the original [cytube-bot](https://github.com/dead-beef/cytube-bot) that started it all.
- **calzoneman** for creating [CyTube](https://github.com/calzoneman/sync) and keeping it running.
- **The NATS Team** for building an incredible messaging system.
- **KGMoon**, who started and runs the 420Grindhouse channel this project was built for.
- All the mods at **420Grindhouse** ("It's not a Grindhouse, it's a Grindhome!").
- Everyone who endured my rants about over-engineered architecture, "nano-sprints", and naming sprints after grindhouse movies.
- And special thanks to the crew of the **Satellite of Love**. Keep circulating the tapes. 🎬
