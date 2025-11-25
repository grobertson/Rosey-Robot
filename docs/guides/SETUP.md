# Rosey Bot Setup Guide

Quick deployment automation for fresh Rosey instances.

## Quick Start

### Interactive Setup (Recommended for first-time users)

```bash
python setup_bot.py
```

Follow the prompts to configure:
- CyTube domain and channel
- Bot username and password
- Optional LLM integration (Ollama)

### Command Line Setup (Fast deployment)

```bash
python setup_bot.py \
  --username CynthiaRothbot \
  --password "your-secure-password" \
  --channel yourroom \
  --ollama-url http://192.168.1.100:11434
```

### From Config File

If you have a pre-configured JSON file:

```bash
python setup_bot.py --from-file my_bot_config.json
```

## Setup Options

### Required
- `--username` - Bot's CyTube username
- `--channel` - Channel name to join (without domain/path)

### Optional
- `--password` - Bot password (prompted if not provided)
- `--domain` - CyTube server (default: `https://cytu.be`)
- `--ollama-url` - Ollama server URL (enables LLM if provided)
- `--ollama-model` - Model name (default: `llama3`)
- `--output` - Config file path (default: `bot/rosey/config.json`)

## Complete Example Workflow

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Rosey-Robot.git
cd Rosey-Robot
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Database Setup (Optional: PostgreSQL)

**Default**: Uses SQLite (`bot_data.db`) with zero configuration

**For Production (PostgreSQL)**:

```bash
# Start PostgreSQL via Docker
docker-compose up -d postgres

# Set database URL
export DATABASE_URL="postgresql+asyncpg://rosey:rosey_dev_password@localhost/rosey_dev"

# Run migrations
alembic upgrade head
```

See [DATABASE_SETUP.md](DATABASE_SETUP.md) for complete PostgreSQL setup guide and [MIGRATIONS.md](MIGRATIONS.md) for migration workflow.

### 4. Run Setup

**With LLM (Ollama):**
```bash
python setup_bot.py \
  --username SaveTheRobots \
  --channel toddy-temple \
  --ollama-url http://192.168.1.100:11434 \
  --ollama-model llama3
```

**Without LLM:**
```bash
python setup_bot.py \
  --username SaveTheRobots \
  --channel toddy-temple
```

**Interactive Mode:**
```bash
python setup_bot.py
# Answer the prompts
```

### 4. Customize (Optional)

Edit the bot's personality:
```bash
nano bot/rosey/prompt.md
```

Adjust LLM triggers in `bot/rosey/config.json`:
- Keywords and probabilities
- Greeting behavior
- Ambient chat frequency

### 5. Test LLM (if enabled)

```bash
cd bot/rosey
python test_llm.py
```

### 6. Start the Bot

```bash
cd bot/rosey
python rosey.py config.json
```

## Configuration File Structure

The setup script creates a `config.json` with this structure:

```json
{
  "domain": "https://cytu.be",
  "channel": "yourroom",
  "user": ["BotUsername", "password"],
  "response_timeout": 1,
  "restart_delay": 5,
  "log_level": "INFO",
  "chat_log_file": "chat.log",
  "media_log_file": "media.log",
  "shell": "localhost:5555",
  "db": "bot_data.db",
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "ollama": {
      "base_url": "http://192.168.1.100:11434",
      "model": "llama3"
    },
    "triggers": {
      "enabled": true,
      "direct_mention": true,
      "commands": ["!ai", "!ask"]
    }
  }
}
```

## Multiple Bot Instances

Deploy multiple bots with different usernames:

```bash
# First bot (CynthiaRothbot)
python setup_bot.py \
  --username CynthiaRothbot \
  --channel myroom \
  --output bot/cynthia/config.json

# Second bot (SaveTheRobots)
python setup_bot.py \
  --username SaveTheRobots \
  --channel myroom \
  --output bot/savethebots/config.json
```

Create the directories first:
```bash
mkdir -p bot/cynthia bot/savethebots
cp bot/rosey/rosey.py bot/cynthia/
cp bot/rosey/rosey.py bot/savethebots/
cp bot/rosey/prompt.md bot/cynthia/
cp bot/rosey/prompt.md bot/savethebots/
```

## Deployment Scenarios

### Local Testing
```bash
python setup_bot.py \
  --username TestBot \
  --channel test-room \
  --ollama-url http://localhost:11434
```

### Remote Ollama Server
```bash
python setup_bot.py \
  --username ProductionBot \
  --channel main-room \
  --ollama-url http://192.168.1.100:11434
```

### No LLM (Simple Logger)
```bash
python setup_bot.py \
  --username LoggerBot \
  --channel archive-room
# Don't specify --ollama-url to disable LLM
```

## Troubleshooting

### Setup script not found
Make sure you're in the repository root:
```bash
cd /path/to/Rosey-Robot
ls setup_bot.py  # Should exist
```

### Permission denied
Make the script executable:
```bash
chmod +x setup_bot.py
```

### Module not found
Install dependencies first:
```bash
pip install -r requirements.txt
```

### Config already exists
Backup existing config:
```bash
mv bot/rosey/config.json bot/rosey/config.json.backup
```

Or specify a different output path:
```bash
python setup_bot.py --output bot/rosey/config2.json
```

## Advanced Configuration

After setup, you can manually edit `config.json` to enable:

- **Ambient chat** - Bot comments randomly every N messages
- **Keyword triggers** - Respond to specific phrases with probability
- **User greetings** - Welcome users on join with custom probabilities
- **OpenRouter** - Use cloud LLMs instead of local Ollama

See `bot/rosey/config.json.dist` for all available options.

## Next Steps

1. **Review Configuration** - Check `bot/rosey/config.json`
2. **Test Connection** - Run the bot and verify it joins the channel
3. **Test LLM** - If enabled, try mentioning the bot or using `!ai`
4. **Tune Triggers** - Adjust probabilities and cooldowns
5. **Customize Personality** - Edit `prompt.md` for your bot's character

## See Also

- [QUICKSTART.md](QUICKSTART.md) - General bot development guide
- [LLM_GUIDE.md](bot/rosey/LLM_GUIDE.md) - LLM integration details
- [BRAIN_SURGERY_SUMMARY.md](bot/rosey/BRAIN_SURGERY_SUMMARY.md) - Trigger system overview
- [README.md](README.md) - Full project documentation
