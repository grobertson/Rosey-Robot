# CyTube TUI Chat Client

A full-featured terminal user interface (TUI) for CyTube chat rooms, inspired by classic IRC clients like BitchX and IRCII, but with a modern, colorful interface.

![CyTube TUI Demo](demo.gif)

## Features

### 🎨 Rich Terminal Interface

- **Full-color support** using the blessed library
- **Rank-based coloring** - brighter colors for moderators and above
- **Rank indicators** - visual symbols for moderators, admins, etc.
- **Dual status bars** - top bar shows connection/media info, bottom shows user stats
- **Smart user list** - grouped by rank (active users), AFK at bottom, with status indicators:
  - `[m]` - Muted user
  - `[s]` - Shadow muted user
  - `[*]` - Channel leader
  - *Italics* - AFK users
- **Configurable themes** - customize colors and symbols via JSON
- **Terminal resize support** - dynamic layout adjustment

### 💬 Chat Features

- **Scrollable history** - maintains up to 1000 messages
- **Mention highlighting** - messages containing your username are highlighted
- **Private messages** - send and receive PMs with visual indicators
- **Command history** - navigate with up/down arrows
- **Action messages** - `/me` command support
- **System notifications** - user joins/leaves, media changes (configurable)
- **Chat history logging** - All messages saved to timestamped log files
- **Error logging** - Exceptions and warnings logged for troubleshooting

### ⌨️ Keyboard Navigation

- `Enter` - Send message
- `Tab` - Username/emote completion (cycle through matches)
- `↑` / `↓` - Navigate command history
- `Page Up` / `Page Down` - Scroll chat history
- `Ctrl+↑` / `Ctrl+↓` - Scroll chat history (alternative)
- `Ctrl+C` - Quit gracefully

### 🎯 Modern Improvements Over Classic IRC Clients

Unlike BitchX and IRCII, this TUI includes:

1. **Rank-based coloring** - Brighter colors for moderators and admins
2. **UTF-8 support** - Full Unicode character support
3. **Async architecture** - Non-blocking, responsive interface
4. **Smart scrolling** - Auto-scrolls to new messages, manual scroll supported
5. **Responsive layout** - Adapts to terminal size
6. **Visual hierarchy** - Clear separation of UI elements with borders and colors
7. **Intelligent user list** - Active users grouped by rank, AFK users at bottom
8. **Status indicators** - Muted, shadow-muted, and leader markers
9. **Mention highlighting** - Your username mentions are highlighted
10. **Tab completion** - Auto-complete usernames and emotes
11. **Persistent logging** - Chat and error logs saved to disk

## Installation

### Prerequisites

```bash
# Python 3.7 or higher required
python --version

# Install dependencies
pip install blessed
```

Or install all project requirements:

```bash
cd /path/to/cytube-bot
pip install -r requirements.txt blessed
```

### Configuration

1. Copy the example config:
   ```bash
   cd examples/tui
   cp config.json my_config.json
   ```

2. Edit `my_config.json`:
   ```json
   {
     "domain": "https://cytu.be",
     "channel": "yourchannel",
     "user": ["yourusername", "yourpassword"],
     "response_timeout": 0.1,
     "restart_delay": 5,
     "log_level": "WARNING",
     "tui": {
       "theme": "theme.json",
       "show_join_quit": true
     }
   }
   ```

   **Fields:**
   - `domain` - CyTube server URL (usually `https://cytu.be`)
   - `channel` - Channel name to join
   - `user` - Array of `[username, password]` for authentication
     - Use `null` or `["username"]` for guest/unauthenticated access
   - `response_timeout` - Socket response timeout in seconds
   - `restart_delay` - Delay before reconnecting on error
   - `log_level` - Logging level (WARNING recommended for TUI)
   - `tui.theme` - Path to theme JSON file (optional, defaults to `theme.json`)
   - `tui.show_join_quit` - Show join/quit messages (optional, defaults to `true`)
   - `tui.clock_format` - Clock format: `12h` for AM/PM or `24h` for 24-hour (optional, defaults to `12h`)

### Themes

Customize the TUI appearance by editing `theme.json`. You can configure:
- Status bar colors
- User rank colors (owner, admin, moderator, registered, guest)
- Message colors (PMs, system messages, mentions)
- Border and timestamp colors
- Rank symbols and status markers

See `theme.json` for the full structure.

## Usage

### Basic Usage

```bash
### Running

From project root:
```bash
python -m examples.tui.bot examples/tui/my_config.json
```

Or from the examples/tui directory:
```

### Commands

| Command | Description |
|---------|-------------|
| `/quit` or `/q` | Exit the TUI |
| `/clear` | Clear chat history |
| `/help` or `/h` | Show help message |
| `/togglejoins` | Toggle join/quit message display |
| Tab | Autocomplete usernames and #emotes |
| Ctrl+Up/Down | Scroll chat history |
| Ctrl+C | Exit (forceful) |

### Tips & Tricks

1. **Tab completion**: CyTube-specific auto-completion for usernames and emotes:
   - **Emotes**: Type `#` followed by at least one character, then press Tab (e.g., `#sm<Tab>` → `#smile`)
   - **Usernames**: Type at least 2 alphanumeric characters anywhere in your message, then press Tab (e.g., `ali<Tab>` → `alice`)
   - Press Tab multiple times to cycle through matches alphabetically
   - No matches = Tab is silently ignored
   - Note: Usernames with underscores are excluded due to a CyTube bug

2. **Log files**: The TUI automatically creates two types of log files in the `examples/tui/logs/` directory:
   - `tui_errors.log` - Contains errors and warnings for troubleshooting
   - `chat_YYYYMMDD_HHMMSS.log` - Complete chat history with timestamps
   
3. **Scrolling shortcuts**: Use either Page Up/Down or Ctrl+Up/Down to scroll through chat history

4. **Multiple instances**: Run multiple TUIs in different terminal windows/tabs for multi-channel monitoring

5. **tmux/screen integration**: Perfect for long-running sessions
   ```bash
   tmux new -s cytube
   python -m bots.tui.bot config.json
   # Detach: Ctrl+B, D
   # Reattach: tmux attach -t cytube
   ```

3. **Custom color schemes**: The terminal's color scheme affects the TUI appearance

4. **Terminal recommendations**:
   - **Linux**: gnome-terminal, konsole, alacritty
   - **macOS**: iTerm2, Terminal.app
   - **Windows**: Windows Terminal, ConEmu, mintty

## Interface Layout

```
┌────────────────────────────────────────────────────────────────────────────┐
│ Connected to yourchannel                                                    │
├────────────────────────────────────────────────────────────────────────────┤
│ [12:34:56] <alice> Hey everyone!                              │ Users (5)  │
│ [12:35:01] <bob> What's up?                                   │ ~owner     │
│ [12:35:15] * charlie has joined                               │ @moderator │
│ [12:35:20] [PM] <dave> Private message                        │ +alice     │
│ [12:35:30] * Now playing: Cool Video Title                    │ +bob       │
│                                                                │  guest     │
│                                                                │            │
│                                                                │            │
├────────────────────────────────────────────────────────────────────────────┤
│ > Hello chat!                                                               │
└────────────────────────────────────────────────────────────────────────────┘
```

### Status Bar (Top)
- Shows connection status, channel name, and current time
- Background color changes based on connection state

### Chat Area (Main)
- **Timestamps** - `[HH:MM:SS]` format in gray
- **Usernames** - Color-coded and wrapped in `<>`
- **Messages** - Plain text, automatically wrapped
- **System messages** - Prefixed with `*` in various colors
  - Green: User joins
  - Red: User leaves
  - Blue: Media changes
  - Cyan: Help/info messages
- **Private messages** - Prefixed with `[PM]` in bright magenta

### User List (Right)
- **Rank symbols**:
  - `~` - Owner/Founder
  - `%` - Admin
  - `@` - Moderator
  - `+` - Registered user
  - (space) - Guest
- **Bold** - Current video leader
- **Dimmed** - AFK users
- Color-coded usernames matching chat

### Input Line (Bottom)
- Prompt: `> `
- Shows current input with cursor position
- Automatically truncates if input exceeds width

## Color Scheme

The TUI uses a carefully selected color palette for readability and aesthetics:

| Element | Color | Purpose |
|---------|-------|---------|
| Status bar | Black on cyan | High visibility header |
| Timestamps | Bright black (gray) | De-emphasized metadata |
| Usernames | Cycling palette | Cyan, green, yellow, blue, magenta (bright variants) |
| System messages | Various | Color-coded by message type |
| PM messages | Bright magenta | High visibility for direct messages |
| Borders | Bright black | Visual separators |
| Input prompt | Bright white | Clear input area |

## Troubleshooting

### Issue: Colors not displaying correctly

**Solution**: Ensure your terminal supports 256 colors:
```bash
echo $TERM
# Should show: xterm-256color or similar

# Test colors
python -c "from blessed import Terminal; t = Terminal(); print(t.green('Green') + ' ' + t.red('Red'))"
```

### Issue: Terminal too small

**Minimum recommended size**: 80x24 (columns x rows)

**Solution**: Resize your terminal window or check size:
```bash
echo "Columns: $COLUMNS, Rows: $LINES"
```

### Issue: Unicode characters display incorrectly

**Solution**: Set UTF-8 encoding:
```bash
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
```

### Issue: Connection errors

**Solution**: Check your config.json:
- Verify domain URL (include `https://`)
- Confirm channel name is correct
- Test credentials on the web interface first
- Check network connectivity

### Issue: Input lag or slow response

**Solution**:
- Close other terminal applications
- Reduce scroll history size in code (edit `maxlen=1000`)
- Check CPU usage
- Try a different terminal emulator

## Development

### Architecture

The TUI bot extends the base `Bot` class from `lib/bot.py` with terminal-specific rendering and input handling:

```python
Bot (lib/bot.py)
  ↓ extends
TUIBot (examples/tui/bot.py)
  ├── Terminal rendering (blessed)
  ├── Input handling (keyboard events)
  ├── Chat history management (deque)
  └── User colorization (consistent mapping)
```

### Key Components

1. **Event Handlers** - React to CyTube events:
   - `handle_chat()` - Process incoming messages
   - `handle_pm()` - Handle private messages
   - `handle_user_join/leave()` - Track user list changes
   - `handle_media_change()` - Show media notifications

2. **Rendering Methods** - Draw UI elements:
   - `render_screen()` - Full screen layout
   - `render_status()` - Status bar
   - `render_chat()` - Scrollable message area
   - `render_users()` - User list sidebar
   - `render_input()` - Input line with cursor

3. **Input Processing** - Handle user interaction:
   - `handle_input()` - Main keyboard event loop
   - `process_command()` - Parse and execute commands
   - `navigate_history_up/down()` - Command history navigation
   - `scroll_up/down()` - Chat history scrolling

### Extending the TUI

Want to add features? Here are some ideas:

1. **Multiple windows** - Alt+1-9 to switch between channels
2. **Notification sounds** - Beep on PM or mention
3. **Tab completion** - Auto-complete usernames
4. **Themes** - Configurable color schemes
5. **Mouse support** - Click to scroll, select users
6. **Channel list** - Browse available channels
7. **Media controls** - Skip, pause from TUI
8. **Logging** - Save chat to file

## Comparison to Classic IRC Clients

### BitchX Inspiration
- Status bar at top
- User list on right
- Command prefix (`/`)
- Color-coded usernames

### IRCII Inspiration
- Simple, keyboard-driven interface
- Command history
- Message scrollback
- Clean, distraction-free design

### Modern Improvements
- **Async I/O** - Non-blocking architecture using asyncio
- **Unicode** - Full emoji and international character support
- **Rich colors** - 256-color terminal support
- **Dynamic layout** - Adapts to window size
- **Better UX** - Clear visual hierarchy, helpful system messages
- **Modern Python** - Type hints, docstrings, clean code structure

## Contributing

Found a bug or want to add a feature? Contributions welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

See the main project LICENSE file.

## Acknowledgments

- **blessed** library - Excellent terminal manipulation toolkit
- **BitchX** and **IRCII** - Inspiration for the interface design
- **CyTube** - The awesome synchronized media platform

## See Also

- [Main README](../../README.md) - Project overview
- [ARCHITECTURE.md](../../docs/ARCHITECTURE.md) - System architecture
- [lib/bot.py](../../lib/bot.py) - Core bot implementation
- [blessed documentation](https://blessed.readthedocs.io/) - Terminal library docs

---

**Enjoy your terminal-based CyTube experience!** 🎉
