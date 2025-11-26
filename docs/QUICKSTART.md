# Rosey v1.0 Quick Start Guide

Get Rosey running in **5 minutes**. This guide walks through installation, configuration, and your first bot commands.

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Docker** (for NATS server)
- **Git** (optional, for cloning)
- **CyTube channel** with bot account

## Step 1: Get the Code

```bash
git clone https://github.com/your-org/rosey-robot.git
cd rosey-robot
```

Or download and extract the ZIP from GitHub.

## Step 2: Start NATS Server

Rosey uses NATS for all internal communication. Start the NATS server via Docker:

```bash
docker-compose up -d nats
```

**Verify NATS is running**:

```bash
docker ps
# You should see: nats:latest with ports 4222, 6222, 8222
```

**Without Docker?** Install NATS standalone: [nats.io/download](https://nats.io/download/)

## Step 3: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Expected packages**: `nats-py`, `websockets`, `aiohttp`, `sqlalchemy`, `alembic`, `pytest`

## Step 4: Configure the Bot

Copy the sample config and edit it:

```bash
cp config.json.dist config.json
```

**Edit `config.json`** with your CyTube details:

```json
{
  "cytube": {
    "server": "your-cytube-server.com",
    "channel": "your-channel-name",
    "username": "RoseyBot",
    "password": "your-bot-password",
    "secure": true
  },
  "nats": {
    "servers": ["nats://localhost:4222"]
  },
  "database": {
    "url": "sqlite:///rosey.db"
  },
  "plugins": {
    "enabled": ["dice-roller", "8ball", "countdown", "trivia", "quote-db", "inspector"],
    "directory": "plugins"
  },
  "command_prefix": "!"
}
```

**Key fields**:
- `cytube.server`: Your CyTube server hostname
- `cytube.channel`: Channel name (not the full URL)
- `cytube.username`: Bot account username
- `cytube.password`: Bot account password
- `command_prefix`: Command trigger character (default: `!`)

## Step 5: Initialize Database

Run database migrations to set up tables:

```bash
alembic upgrade head
```

**Expected output**: "Running upgrade ... -> ... done"

## Step 6: Run the Bot

```bash
python rosey.py
```

**What you'll see**:

```
[2025-11-26 15:30:00] INFO - Rosey v1.0 starting...
[2025-11-26 15:30:00] INFO - EventBus connecting to nats://localhost:4222
[2025-11-26 15:30:01] INFO - Database service started
[2025-11-26 15:30:01] INFO - PluginManager discovered 6 plugins
[2025-11-26 15:30:01] INFO - Plugin 'dice-roller' started
[2025-11-26 15:30:01] INFO - Plugin '8ball' started
[2025-11-26 15:30:01] INFO - Plugin 'countdown' started
[2025-11-26 15:30:01] INFO - Plugin 'trivia' started
[2025-11-26 15:30:01] INFO - Plugin 'quote-db' started
[2025-11-26 15:30:01] INFO - Plugin 'inspector' started
[2025-11-26 15:30:02] INFO - CommandRouter started, subscribed to cytube.chat
[2025-11-26 15:30:02] INFO - CytubeConnector connecting to wss://your-server.com/socket.io/
[2025-11-26 15:30:03] INFO - Connected to CyTube channel 'your-channel-name'
[2025-11-26 15:30:03] INFO - Rosey is ready!
```

**Stuck at "CytubeConnector connecting..."?** Check your `config.json` credentials and server URL.

## Step 7: Test Commands

Go to your CyTube channel chat and try:

```
!roll 2d6        # Dice roller
!8ball will this work?  # Magic 8-ball
!quote add "Hello, world!" # Save a quote
!countdown test 2025-12-31 23:59  # Create countdown
!trivia start    # Start trivia game
```

**Expected responses**:
- Dice roller: "🎲 Rolled 2d6: [3, 5] = 8"
- 8-ball: "🔮 It is certain."
- Quote: "✅ Quote #1 added"
- Countdown: "⏰ Countdown 'test' created: 35 days remaining"
- Trivia: "🧠 Trivia started! Question 1/10: ..."

## Troubleshooting

### Bot connects but doesn't respond to commands

**Check command prefix**: Ensure `config.json` has `"command_prefix": "!"` and you're using `!command`.

**Check logs**: Look for "CommandRouter started" message. If missing, check NATS connection.

**Verify plugin loading**: Should see "Plugin 'dice-roller' started" messages for all enabled plugins.

### Connection errors

**NATS not running**:
```
ERROR - Failed to connect to NATS: Connection refused
```
→ Run `docker-compose up -d nats` and retry.

**CyTube credentials wrong**:
```
ERROR - CyTube authentication failed
```
→ Verify `cytube.username` and `cytube.password` in config.json.

**Server URL wrong**:
```
ERROR - Failed to connect to wss://...
```
→ Check `cytube.server` matches your CyTube instance (no `https://` prefix).

### Database errors

**Migration not run**:
```
sqlalchemy.exc.OperationalError: no such table: quotes
```
→ Run `alembic upgrade head`.

**Database locked** (SQLite):
```
sqlalchemy.exc.OperationalError: database is locked
```
→ Close other instances of the bot or delete `rosey.db-journal` file.

### Import errors

**Missing dependencies**:
```
ModuleNotFoundError: No module named 'nats'
```
→ Run `pip install -r requirements.txt` (ensure virtual environment is activated).

## Next Steps

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Understand how Rosey works
- **[PLUGIN-DEVELOPMENT.md](PLUGIN-DEVELOPMENT.md)** - Write your own plugins
- **[NATS-CONTRACTS.md](NATS-CONTRACTS.md)** - NATS event interfaces
- **[docs/guides/](guides/)** - Advanced topics (testing, deployment, agents)

## Common Tasks

### Enable/Disable Plugins

Edit `config.json` → `plugins.enabled` array:

```json
{
  "plugins": {
    "enabled": ["dice-roller", "8ball"]  // Only these will load
  }
}
```

Restart the bot (`Ctrl+C` then `python rosey.py`).

### Add New Plugins

1. Place plugin directory in `plugins/`
2. Add plugin name to `config.json` → `plugins.enabled`
3. Restart bot

See [PLUGIN-DEVELOPMENT.md](PLUGIN-DEVELOPMENT.md) for authoring guide.

### View Logs

Logs are written to stdout. For persistent logs:

```bash
python rosey.py 2>&1 | tee rosey.log
```

Or configure Python logging in `rosey.py` (see `logging.basicConfig()`).

### Update Rosey

```bash
git pull origin main
pip install -r requirements.txt  # In case dependencies changed
alembic upgrade head  # Apply new migrations
```

## Need Help?

- **GitHub Issues**: Report bugs or request features
- **Documentation**: [docs/](docs/) directory
- **CyTube Community**: Join the CyTube Discord/IRC

---

**Ready to build?** Check out [PLUGIN-DEVELOPMENT.md](PLUGIN-DEVELOPMENT.md) to create your first plugin!
