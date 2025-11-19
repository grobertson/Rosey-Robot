# CyTube TUI Chat Client

A standalone terminal user interface (TUI) for CyTube chat rooms, inspired by classic IRC clients like BitchX and IRCII, with modern features and colorful themes.

![CyTube TUI](https://img.shields.io/badge/terminal-TUI-blue) ![Python](https://img.shields.io/badge/python-3.7+-green)

## ✨ Features

- 🎨 **Rich Terminal Interface** - Full-color display with blessed library
- 🤖 **10 Robot Themes** - HAL 9000, R2-D2, C-3PO, T-800, WALL-E, and more!
- 💬 **Full Chat Support** - Messages, PMs, mentions, emotes
- ⌨️ **Smart Input** - Tab completion for usernames and emotes
- 📜 **Scrollable History** - Up to 1000 messages with Page Up/Down
- 👥 **User List** - Rank-based coloring, AFK tracking, status indicators
- 🎵 **Media Info** - Now playing, duration, time remaining
- 📊 **Stats** - Session time, viewer counts, uptime
- 📝 **Logging** - Chat history and error logs
- 🖥️ **Responsive** - Dynamic layout adapts to terminal size

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/grobertson/Rosey-Robot.git
cd Rosey-Robot

# Install dependencies
pip install -r requirements.txt blessed

# Or use virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt blessed
```

### Configuration

1. Copy the example config:
   ```bash
   cp tui_app/configs/config.yaml.example tui_app/configs/my_config.yaml
   ```

2. Edit `my_config.yaml`:
   ```yaml
   domain: https://cytu.be
   channel: YourChannelName
   user:
     - YourUsername
     - YourPassword
   
   tui:
     theme: hal9000  # Choose your robot theme!
     show_join_quit: true
     clock_format: 12h
   ```

### Running

```bash
# From project root
python -m tui_app tui_app/configs/my_config.yaml

# Or use the launcher scripts
# Windows:
tui_app\run.bat

# Linux/Mac:
chmod +x tui_app/run.sh
./tui_app/run.sh
```

## 🎨 Robot Themes

Choose from 10 robot-themed color schemes:

| Theme | Robot | Source | Style |
|-------|-------|--------|-------|
| `default` | - | - | Classic cyan/white |
| `hal9000` | HAL 9000 | 2001: A Space Odyssey | Red menacing |
| `r2d2` | R2-D2 | Star Wars | Blue/white astromech |
| `c3po` | C-3PO | Star Wars | Golden protocol droid |
| `t800` | T-800 | Terminator | Red HUD cyborg |
| `walle` | WALL-E | WALL-E | Rusty yellow/brown |
| `robby` | Robby | Forbidden Planet | Cyan retro |
| `marvin` | Marvin | Hitchhiker's Guide | Depressed green |
| `johnny5` | Johnny 5 | Short Circuit | Bright friendly |
| `robocop` | RoboCop | RoboCop | Blue steel |
| `data` | Data | Star Trek: TNG | Yellow Starfleet |

Change themes anytime with `/theme <name>` command!

## ⌨️ Keyboard Controls

### Navigation
- `Enter` - Send message
- `↑` / `↓` - Navigate command history
- `Page Up` / `Page Down` - Scroll chat
- `Ctrl+↑` / `Ctrl+↓` - Alternative scroll
- `Tab` - Auto-complete usernames and emotes
- `Ctrl+C` - Quit

### Commands

#### General
- `/help` or `/h` - Show all commands
- `/info` - User and channel information
- `/status` - Connection status and uptime
- `/quit` or `/q` - Exit
- `/clear` - Clear chat display
- `/theme [name]` - List or change themes

#### Chat
- `/pm <user> <msg>` - Send private message
- `/me <action>` - Send action message
- `/say <message>` - Send chat message
- `/togglejoins` - Show/hide join/quit messages

#### Users
- `/users` - List all users
- `/user <name>` - Show user details
- `/afk [on|off]` - Set AFK status

#### Playlist (if you have permissions)
- `/playlist [n]` - Show playlist (default 10 items)
- `/current` or `/np` - Current media info
- `/add <url> [temp]` - Add video
- `/remove <#>` - Remove item
- `/jump <#>` - Jump to position
- `/next` or `/skip` - Skip to next

#### Control (moderator+)
- `/pause` - Pause playback
- `/kick <user> [reason]` - Kick user

## 🎯 Tab Completion

Smart auto-completion like modern shells:

**Usernames:**
- Type 2+ letters of a username, press Tab
- Example: `he<Tab>` → `hello_user`
- Press Tab again to cycle through matches
- Works anywhere in your message

**Emotes:**
- Type `#` + 1+ letters, press Tab
- Example: `#sm<Tab>` → `#smile`
- Press Tab to cycle through emote matches

## 📁 Directory Structure

```
tui_app/
├── __init__.py           # Package initialization
├── __main__.py           # Entry point (python -m tui_app)
├── tui_bot.py            # Main TUI bot implementation
├── run.bat               # Windows launcher
├── run.sh                # Linux/Mac launcher
├── README.md             # This file
├── configs/
│   └── config.yaml.example   # Example configuration
├── themes/
│   ├── default.json
│   ├── hal9000.json
│   ├── r2d2.json
│   └── ...               # 8 more robot themes
└── logs/
    ├── chat_YYYYMMDD_HHMMSS.log
    └── tui_errors.log
```

## 🖥️ Interface Layout

```
┌────────────────────────────────────────────────────┐
│ 📺 420Grindhouse              🕐 07:48:10 PM       │
├────────────────────────────────────────────────────┤
│ [19:48:10] <alice> Hey!     │ Users (15)          │
│ [19:48:15] <bob> What's up? │ ~owner              │
│ [19:48:20] * charlie joined │ @moderator          │
│ [19:48:25] [PM] <dave> Hi!  │ +alice              │
│ [19:48:30] * Now playing... │ +bob                │
│                              │  charlie            │
├────────────────────────────────────────────────────┤
│ ▶ Cool Video     │ 👥 15/96 │ ⏱ Session: 1h 23m │
│ > Type here_                                       │
└────────────────────────────────────────────────────┘
```

## 🔧 Configuration Options

### Connection Settings
```yaml
domain: https://cytu.be          # CyTube server URL
channel: YourChannel             # Channel to join
user: [username, password]       # Bot credentials
response_timeout: 1              # Socket timeout (seconds)
restart_delay: 5                 # Reconnect delay (seconds)
log_level: WARNING               # DEBUG|INFO|WARNING|ERROR|CRITICAL
```

### TUI Settings
```yaml
tui:
  theme: hal9000                 # Theme name (see themes/)
  show_join_quit: true           # Show join/leave messages
  clock_format: 12h              # 12h (AM/PM) or 24h
  hide_afk_users: false          # Hide AFK from userlist
```

## 🛠️ Troubleshooting

### Colors not showing
```bash
# Check terminal color support
echo $TERM  # Should be xterm-256color or similar

# Test colors
python -c "from blessed import Terminal; t=Terminal(); print(t.green('OK'))"
```

### Terminal too small
Minimum: 80 columns × 24 rows
```bash
echo "Size: $COLUMNS × $LINES"
```

### Unicode issues
```bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

### Connection fails
- Verify domain URL includes `https://`
- Check channel name is correct
- Test credentials on web interface first
- Check network connectivity

## 📝 Logs

All logs are saved in `tui_app/logs/`:

- **chat_YYYYMMDD_HHMMSS.log** - Complete chat history with timestamps
- **tui_errors.log** - Errors and warnings for troubleshooting

## 🤝 Contributing

Contributions welcome! This TUI is part of the larger Rosey-Robot project.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📜 License

See main project LICENSE file.

## 🙏 Acknowledgments

- **blessed** - Excellent terminal manipulation library
- **BitchX** & **IRCII** - Interface design inspiration
- **CyTube** - The awesome synchronized media platform
- All the robots that inspired our themes! 🤖

## 🔗 See Also

- [Main Project README](../README.md)
- [API Documentation](../docs/)
- [CyTube](https://github.com/calzoneman/sync)
- [blessed docs](https://blessed.readthedocs.io/)

---

**Enjoy your terminal-based CyTube experience!** 🎉

*"I'm sorry Dave, I'm afraid I can't do that... but I can chat in your terminal!"* - HAL 9000 theme
