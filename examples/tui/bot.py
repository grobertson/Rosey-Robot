
"""CyTube TUI Chat Client - A terminal-based chat interface inspired by BitchX/IRCII.

This module provides a full-featured text user interface for CyTube chat rooms,
combining the nostalgic feel of classic IRC clients with modern terminal capabilities.

Features:
    - Full-color terminal interface using blessed
    - Scrollable chat history with username colorization
    - Real-time user list with rank indicators
    - Command-line input with history
    - Support for private messages
    - Media notifications
    - Status bar with connection info
    - Configurable color schemes

Usage:
    python -m bots.tui.bot config.json

Keybindings:
    - Enter: Send message
    - Up/Down: Navigate command history
    - Page Up/Down: Scroll chat history
    - Ctrl+C: Quit
    - Alt+1-9: Switch windows (future)
"""

import sys
import json
import signal
import platform
import textwrap
from pathlib import Path
from collections import deque
from datetime import datetime
import asyncio
import logging
import time

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from blessed import Terminal

from lib import Bot, MessageParser
from lib.error import CytubeError, SocketIOError

from common import get_config


class TUIBot(Bot):
    """CyTube bot with terminal user interface.

    This bot provides a rich terminal interface for interacting with CyTube
    chat rooms, inspired by classic IRC clients like BitchX and IRCII.

    Attributes:
        term (Terminal): Blessed terminal instance for rendering
        msg_parser (MessageParser): Parses HTML messages to plain text
        chat_history (deque): Scrollable message history buffer
        user_colors (dict): Username to color mapping for consistency
        input_buffer (str): Current input line being typed
        input_history (deque): Command history for up/down navigation
        history_pos (int): Current position in command history
        scroll_offset (int): Current scroll position in chat history
        running (bool): Whether the TUI loop is active
        status_message (str): Current status bar message
    """

    # Color palette for usernames (cycling through distinct colors)
    USERNAME_COLORS = [
        'cyan', 'green', 'yellow', 'blue', 'magenta',
        'bright_cyan', 'bright_green', 'bright_yellow',
        'bright_blue', 'bright_magenta'
    ]

    # Rank symbols for user list
    RANK_SYMBOLS = {
        0: ' ',      # Guest
        1: '+',      # Registered
        2: '@',      # Moderator
        3: '%',      # Admin
        4: '~',      # Owner
        5: '&',      # Founder
    }

    def __init__(self, *args, tui_config=None, **kwargs):
        """Initialize the TUI bot.

        Args:
            *args: Positional arguments passed to Bot.__init__
            tui_config (dict): TUI-specific configuration options
            **kwargs: Keyword arguments passed to Bot.__init__
        """
        super().__init__(*args, **kwargs)

        # Initialize terminal
        self.term = Terminal()

        # TUI configuration
        self.tui_config = tui_config or {}
        self.show_join_quit = self.tui_config.get('show_join_quit', True)
        self.clock_format = self.tui_config.get('clock_format', '12h')  # '12h' or '24h'
        self.hide_afk_users = self.tui_config.get('hide_afk_users', False)  # Hide AFK users from list

        # Store config file path for persistence
        self.config_file = args[0] if args else 'config.json'

        # Load theme
        theme_name = self.tui_config.get('theme', 'default')
        self.current_theme_name = theme_name
        self.theme = self._load_theme(theme_name)

        # Message parsing
        self.msg_parser = MessageParser()

        # Chat history buffer (max 1000 messages)
        self.chat_history = deque(maxlen=1000)

        # Username color mapping for consistency
        self.user_colors = {}
        self._color_index = 0

        # Input handling
        self.input_buffer = ''
        self.input_history = deque(maxlen=100)
        self.history_pos = -1
        self.tab_completion_matches = []
        self.tab_completion_index = 0
        self.tab_completion_start = 0

        # Scrolling
        self.scroll_offset = 0

        # State
        self.running = False
        self.status_message = 'Connecting...'
        self.session_start = datetime.now()
        self.current_media_title = None  # Cache current media title for display
        self.current_media_duration = None  # Total duration in seconds
        self.current_media_start_time = None  # When the media started playing
        self.current_media_paused = False  # Whether media is paused
        self.pending_media_uid = None  # Store UID if setCurrent happens before queue

        # Terminal size tracking (for Windows resize detection)
        self.last_terminal_size = (self.term.width, self.term.height)
        self.is_windows = platform.system() == 'Windows'
        self.last_size_check = time.time()
        self.size_check_interval = 10.0  # Check every 10 seconds on Windows
        self.last_status_update = time.time()
        self.status_update_interval = 1.0  # Update status bars every second

        # Setup logging to file
        self._setup_logging()

        # Setup resize handler (Unix only - Windows doesn't support SIGWINCH)
        if not self.is_windows and hasattr(signal, 'SIGWINCH'):
            signal.signal(signal.SIGWINCH, self._handle_resize)

        # Register event handlers
        self.on('chatMsg', self.handle_chat)
        self.on('pm', self.handle_pm)
        self.on('userlist', self.handle_userlist)
        self.on('addUser', self.handle_user_join)
        self.on('userLeave', self.handle_user_leave)
        self.on('setCurrent', self.handle_media_change)
        self.on('queue', self.handle_queue)
        self.on('playlist', self.handle_playlist)
        self.on('login', self.handle_login)

    def _on_queue(self, _, data):
        """Override base Bot's queue handler to add retry logic.

        Called when the server adds a single item to the playlist.
        After the base class adds it, check if it matches our pending media UID.
        """
        # Call parent to add the item
        super()._on_queue(_, data)

        # If we have a pending media UID, check if this is the item we're waiting for
        if self.pending_media_uid:
            item_uid = data.get('item', {}).get('uid')
            if item_uid == self.pending_media_uid:
                self.logger.info('_on_queue: found pending UID %s, setting current', self.pending_media_uid)
                try:
                    item = self.channel.playlist.get(self.pending_media_uid)
                    if item:
                        self.channel.playlist._current = item
                        self.current_media_title = str(item.title)
                        self.add_system_message(f'Now playing: {item.title}', color='bright_blue')
                        self.render_top_status()
                        self.pending_media_uid = None
                        self.logger.info('_on_queue: successfully set current to %s', item.title)
                except (ValueError, AttributeError) as e:
                    self.logger.warning('_on_queue: failed to set current: %s', e)

    def _on_playlist(self, _, data):
        """Override base Bot's playlist handler to add debugging and retry logic.

        Called when the server sends the full playlist. After the base class
        populates the queue, we check if there's a pending media UID to retry.
        """
        # Log what we're receiving
        self.logger.info('_on_playlist: received %d items', len(data) if data else 0)

        # Call parent to populate the queue
        super()._on_playlist(_, data)

        # Log the queue state after population
        queue_len = len(self.channel.playlist.queue) if self.channel.playlist.queue else 0
        self.logger.info('_on_playlist: queue now has %d items', queue_len)

        # If we have a pending media UID, try to set it now
        if self.pending_media_uid and queue_len > 0:
            self.logger.info('_on_playlist: retrying pending UID %s', self.pending_media_uid)
            try:
                item = self.channel.playlist.get(self.pending_media_uid)
                if item:
                    self.channel.playlist._current = item
                    self.current_media_title = str(item.title)
                    self.add_system_message(f'Now playing: {item.title}', color='bright_blue')
                    self.render_top_status()
                    self.pending_media_uid = None
                    self.logger.info('_on_playlist: successfully set current to %s', item.title)
            except (ValueError, AttributeError) as e:
                self.logger.warning('_on_playlist: failed to set pending UID: %s', e)

    def _on_changeMedia(self, _, data):
        """Handle changeMedia event which contains current media info.

        This event arrives after setCurrent and contains the full media details
        including title, duration, and playback state. Use this as the primary
        source for current media info since it doesn't depend on the playlist queue.
        """
        try:
            title = data.get('title', 'Unknown')
            seconds = data.get('seconds', 0)  # Total duration
            current_time = data.get('currentTime', 0)  # Current position
            paused = data.get('paused', False)

            # Store media info
            self.current_media_title = title
            self.current_media_duration = seconds
            self.current_media_paused = paused

            # Calculate when media started (current time in video - elapsed real time = start time)
            import time as time_module
            self.current_media_start_time = time_module.time() - current_time

            self.logger.info('changeMedia: %s (duration: %ds, at: %ds, paused: %s)', 
                           title, seconds, int(current_time), paused)
            self.add_system_message(f'Now playing: {title}', color='bright_blue')
            self.render_top_status()
            # Clear pending UID since we have the media info now
            self.pending_media_uid = None
        except Exception as e:
            self.logger.warning('changeMedia failed: %s', e)

    def _on_setCurrent(self, _, data):
        """Override base Bot's setCurrent handler to handle missing UIDs gracefully.

        The base handler tries to look up UIDs in the playlist queue, but sometimes
        setCurrent is called before the item is in the queue, causing a ValueError.
        This override catches that error and logs it without crashing.
        """
        try:
            # Call the parent class handler
            super()._on_setCurrent(_, data)
        except ValueError as e:
            # UID not in playlist queue yet - save it for later
            self.logger.warning('setCurrent: Item not in queue yet: %s', e)
            # Store the UID so we can retry when the playlist is populated
            if isinstance(data, int):
                self.pending_media_uid = data
            # Set current to None so we don't have stale data
            self.channel.playlist._current = None

    def _load_theme(self, theme_name):
        """Load theme configuration from themes directory.

        Args:
            theme_name (str): Theme name (without .json extension) or full path

        Returns:
            dict: Theme configuration
        """
        # If it's a relative path to old theme.json, convert to default
        if theme_name == 'theme.json':
            theme_name = 'default'

        # Check if it's a full path or just a name
        if '/' in theme_name or '\\' in theme_name:
            theme_path = Path(theme_name)
        else:
            # Look in themes directory
            theme_path = Path(__file__).parent / 'themes' / f'{theme_name}.json'

        try:
            with open(theme_path, 'r') as f:
                theme = json.load(f)
                self.logger.info(f'Loaded theme: {theme.get("name", theme_name)}')
                return theme
        except Exception as e:
            self.logger.warning(f'Failed to load theme {theme_name}: {e}')
            # Return default theme
            return {
                'name': 'Fallback Theme',
                'description': 'Built-in fallback theme',
                'colors': {
                    'status_bar': {'background': 'cyan', 'text': 'black'},
                    'borders': 'bright_black',
                    'timestamps': 'bright_black',
                    'user_ranks': {
                        'owner': 'bright_yellow',
                        'admin': 'bright_yellow',
                        'moderator': 'bright_yellow',
                        'registered': 'green',
                        'guest': 'white'
                    },
                    'user_list_header': {'background': 'bright_white', 'text': 'black'},
                    'messages': {
                        'private': 'bright_magenta',
                        'system_join': 'bright_green',
                        'system_leave': 'bright_red',
                        'system_media': 'bright_blue',
                        'system_info': 'cyan',
                        'mention_highlight': 'reverse'
                    },
                    'input': {'prompt': 'bright_white', 'text': 'white'}
                },
                'symbols': {
                    'rank_owner': '~',
                    'rank_admin': '%',
                    'rank_moderator': '@',
                    'rank_registered': '+',
                    'rank_guest': ' ',
                    'leader_marker': '[*]',
                    'muted_marker': '[m]',
                    'shadow_muted_marker': '[s]'
                }
            }

    def list_themes(self):
        """List all available themes from the themes directory.

        Returns:
            list: List of tuples (theme_name, theme_info_dict)
        """
        themes_dir = Path(__file__).parent / 'themes'
        themes = []

        if not themes_dir.exists():
            return themes

        for theme_file in sorted(themes_dir.glob('*.json')):
            try:
                with open(theme_file, 'r') as f:
                    theme_data = json.load(f)
                    theme_name = theme_file.stem  # filename without .json
                    themes.append((theme_name, theme_data))
            except Exception as e:
                self.logger.warning(f'Failed to read theme {theme_file}: {e}')

        return themes

    def change_theme(self, theme_name):
        """Change to a different theme and persist the choice.

        Args:
            theme_name (str): Name of theme to switch to

        Returns:
            bool: True if successful, False otherwise
        """
        # Try to load the theme
        new_theme = self._load_theme(theme_name)

        # Check if it loaded successfully (has required keys)
        if 'colors' not in new_theme:
            return False

        # Apply the theme
        self.theme = new_theme
        self.current_theme_name = theme_name

        # Trigger full screen redraw to update all themed elements
        self.render_screen()

        # Save to config file
        try:
            # Use absolute path if relative path was provided
            config_path = Path(self.config_file)
            if not config_path.is_absolute():
                config_path = config_path.resolve()

            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'tui' not in config:
                config['tui'] = {}
            config['tui']['theme'] = theme_name

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)

            return True
        except Exception as e:
            self.logger.warning(f'Failed to save theme preference: {e}')
            # Show inline error message
            self.add_system_message(f'Failed to save config file: {e}', color='bright_red')
            return False

    def _handle_resize(self, signum=None, frame=None):
        """Handle terminal resize events.

        Args:
            signum: Signal number (optional, for signal handler)
            frame: Current stack frame (optional, for signal handler)
        """
        # Redraw the entire screen
        if self.running:
            self.render_screen()

    def _check_terminal_size(self):
        """Check if terminal size has changed (for Windows polling).

        Returns:
            bool: True if size changed, False otherwise
        """
        current_size = (self.term.width, self.term.height)
        if current_size != self.last_terminal_size:
            self.last_terminal_size = current_size
            self._handle_resize()
            return True
        return False

    def _setup_logging(self):
        """Setup file logging for errors and chat history."""
        # Create logs directory if it doesn't exist
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)

        # Error log file
        error_log = log_dir / 'tui_errors.log'
        error_handler = logging.FileHandler(error_log, encoding='utf-8')
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        self.logger.addHandler(error_handler)

        # Chat history log file
        chat_log = log_dir / f'chat_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        self.chat_log_file = open(chat_log, 'a', encoding='utf-8')
        self.logger.info(f'Chat logging to: {chat_log}')
        self.logger.info(f'Error logging to: {error_log}')

    @staticmethod
    def format_duration(seconds):
        """Format seconds into human-readable duration.

        Args:
            seconds: Duration in seconds

        Returns:
            str: Formatted duration like "1h 23m 45s" or "Unknown"
        """
        if seconds < 0:
            return "Unknown"

        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")

        return ' '.join(parts)

    def _log_chat(self, username, message, prefix=''):
        """Log a chat message to the chat history file.

        Args:
            username (str): Username of the sender
            message (str): Message content
            prefix (str, optional): Prefix for the message (e.g., '[PM]', '*')
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if prefix:
            log_line = f'[{timestamp}] {prefix} <{username}> {message}\n'
        else:
            log_line = f'[{timestamp}] <{username}> {message}\n'
        try:
            self.chat_log_file.write(log_line)
            self.chat_log_file.flush()
        except Exception as e:
            self.logger.error(f'Failed to write to chat log: {e}')

    def get_username_color(self, username):
        """Get a consistent color for a username.

        Assigns each username a color from the palette that remains consistent
        throughout the session.

        Args:
            username (str): The username to colorize

        Returns:
            str: Color name from blessed (e.g., 'cyan', 'bright_green')
        """
        if username not in self.user_colors:
            color = self.USERNAME_COLORS[self._color_index % len(self.USERNAME_COLORS)]
            self.user_colors[username] = color
            self._color_index += 1
        return self.user_colors[username]

    def add_chat_line(self, username, message, prefix='', color_override=None):
        """Add a line to the chat history buffer.

        Args:
            username (str): Username of the sender
            message (str): Message content
            prefix (str, optional): Prefix for the line (e.g., '*', '@')
            color_override (str, optional): Override the username color
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        color = color_override or self.get_username_color(username)

        self.chat_history.append({
            'timestamp': timestamp,
            'username': username,
            'message': message,
            'prefix': prefix,
            'color': color
        })

        # Auto-scroll to bottom when new message arrives
        if self.scroll_offset == 0:
            self.render_chat()
            self.render_input()

    def add_system_message(self, message, color='bright_black'):
        """Add a system message to chat history.

        Args:
            message (str): System message content
            color (str, optional): Color for the message
        """
        timestamp = datetime.now().strftime('%H:%M:%S')

        self.chat_history.append({
            'timestamp': timestamp,
            'username': '*',
            'message': message,
            'prefix': '',
            'color': color
        })

        # Log system messages too
        self._log_chat('*', message, prefix='*')

        if self.scroll_offset == 0:
            self.render_chat()
            self.render_input()

    async def handle_chat(self, _, data):
        """Handle incoming chat messages.

        Args:
            _ (str): Event name (unused)
            data (dict): Message data from CyTube
        """
        username = data.get('username', '<unknown>')
        msg = self.msg_parser.parse(data.get('msg', ''))

        self.add_chat_line(username, msg)
        self._log_chat(username, msg)

    async def handle_pm(self, _, data):
        """Handle incoming private messages.

        Args:
            _ (str): Event name (unused)
            data (dict): PM data from CyTube
        """
        username = data.get('username', '<unknown>')
        msg = self.msg_parser.parse(data.get('msg', ''))

        self.add_chat_line(username, msg, prefix='[PM]', color_override='bright_magenta')
        self._log_chat(username, msg, prefix='[PM]')

    async def handle_userlist(self, _, data):
        """Handle initial userlist event.

        Args:
            _ (str): Event name (unused)
            data (list): List of user data from CyTube
        """
        # The userlist event provides the initial list of users
        # Render the user list once it's populated
        self.render_users()

    async def handle_user_join(self, _, data):
        """Handle user join events.

        Args:
            _ (str): Event name (unused)
            data (dict): User data from CyTube
        """
        username = data.get('name', '<unknown>')
        if self.show_join_quit:
            color = self.theme['colors']['messages']['system_join']
            self.add_system_message(f'{username} has joined', color=color)
        self.render_users()

    async def handle_user_leave(self, _, data):
        """Handle user leave events.

        Args:
            _ (str): Event name (unused)
            data (dict): User data from CyTube
        """
        username = data.get('name', '<unknown>')
        if self.show_join_quit:
            color = self.theme['colors']['messages']['system_leave']
            self.add_system_message(f'{username} has left', color=color)
        self.render_users()

    async def handle_media_change(self, _, data):
        """Handle media change events.

        Args:
            _ (str): Event name (unused)
            data (dict): Media data from CyTube (can be uid or PlaylistItem)
        """
        # If data is a PlaylistItem object, use it directly
        from lib.playlist import PlaylistItem
        if isinstance(data, PlaylistItem):
            title = data.title
            self.current_media_title = str(title)
            self.add_system_message(f'Now playing: {title}', color='bright_blue')
            self.render_top_status()
            return

        # If data is a UID, try to look it up in the playlist
        if isinstance(data, int):
            try:
                if self.channel and self.channel.playlist:
                    item = self.channel.playlist.get(data)
                    if item:
                        title = item.title
                        self.current_media_title = str(title)
                        self.add_system_message(f'Now playing: {title}', color='bright_blue')
                        self.render_top_status()
                        return
            except (ValueError, AttributeError):
                # Item not in queue yet, will be updated when playlist populates
                pass

        # Fallback: check if playlist.current was set successfully
        if self.channel and self.channel.playlist and self.channel.playlist.current:
            title = self.channel.playlist.current.title
            self.current_media_title = str(title)
            self.add_system_message(f'Now playing: {title}', color='bright_blue')
            self.render_top_status()

    async def handle_queue(self, _, data):
        """Handle queue event when an item is added to the playlist.

        If we have a pending media UID that failed to set because it wasn't
        in the queue yet, retry setting it now.
        """
        if self.pending_media_uid:
            try:
                item = self.channel.playlist.get(self.pending_media_uid)
                if item:
                    self.channel.playlist._current = item
                    self.current_media_title = str(item.title)
                    self.add_system_message(f'Now playing: {item.title}', color='bright_blue')
                    self.render_top_status()
                    self.pending_media_uid = None
            except (ValueError, AttributeError):
                pass

    async def handle_playlist(self, _, data):
        """Handle playlist event when the full playlist is sent.

        If we have a pending media UID that failed to set because it wasn't
        in the queue yet, retry setting it now that we have the full playlist.
        """
        if self.pending_media_uid:
            try:
                item = self.channel.playlist.get(self.pending_media_uid)
                if item:
                    self.channel.playlist._current = item
                    self.current_media_title = str(item.title)
                    self.add_system_message(f'Now playing: {item.title}', color='bright_blue')
                    self.render_top_status()
                    self.pending_media_uid = None
            except (ValueError, AttributeError):
                pass

    async def handle_login(self, _, data):
        """Handle successful login.

        Args:
            _ (str): Event name (unused)
            data: Bot instance (self)
        """
        self.status_message = f'Connected to {self.channel.name}'
        self.render_status()

    def render_screen(self):
        """Render the complete TUI layout.

        Layout:
            ┌────────────────────────────────────────────────────────┐
            │ Top Status Bar (clock, session, movie info)            │
            ├────────────────────────────────────────────────────────┤
            │                                                         │
            │                                                         │
            │               Chat Area (scrollable)                    │
            │                                                         │
            │                                                         │
            ├────────────────────────────────────────────────────────┤
            │ Bottom Status (username, viewers, high water mark)     │
            │ Input Line: >                                          │
            └────────────────────────────────────────────────────────┘

            User List (right side, 22 chars wide):
            ┌──────────────────────┐
            │ Users (15)           │
            │ ~owner               │
            │ @moderator           │
            │ +user1               │
            │  guest               │
            └──────────────────────┘
        """
        print(self.term.clear)
        self.render_top_status()
        self.render_chat()
        self.render_users()
        self.render_bottom_status()
        self.render_input()

    def render_top_status(self):
        """Render the top status bar with real-time information."""
        with self.term.location(0, 0):
            # Get theme colors
            bg_color = self.theme['colors']['status_bar']['background']
            text_color = self.theme['colors']['status_bar']['text']

            # Left side: Channel name and connection status
            if self.channel:
                left_text = f"📺 {self.channel.name}"
            else:
                left_text = "📺 Connecting..."

            # Right side: Clock with configurable format (show seconds)
            if self.clock_format == '12h':
                current_time = datetime.now().strftime('%I:%M:%S %p')
            else:
                current_time = datetime.now().strftime('%H:%M:%S')
            right_text = f"🕐 {current_time}"

            # Calculate spacing to right-justify clock (5 columns from edge)
            left_len = len(left_text)
            right_len = len(right_text)
            # Reserve total space: left + right + 5 spaces on right
            total_needed = left_len + right_len + 5

            if total_needed <= self.term.width:
                # Enough space - calculate padding between left and right
                padding = self.term.width - total_needed
                status_line = left_text + ' ' * padding + right_text + ' ' * 5
            else:
                # Not enough space, truncate left side
                truncated_left = left_text[:self.term.width - right_len - 8] + '...'
                padding = self.term.width - len(truncated_left) - right_len - 5
                if padding < 1:
                    padding = 1
                status_line = truncated_left + ' ' * padding + right_text + ' ' * 5

            # Should be exact width now, but ensure it
            status_line = status_line[:self.term.width]

            # Apply theme colors
            color_func = getattr(self.term, f'{text_color}_on_{bg_color}', self.term.black_on_cyan)
            print(color_func(status_line), end='', flush=True)

    def render_bottom_status(self):
        """Render the bottom status bar with user info and stats."""
        status_y = self.term.height - 2

        with self.term.location(0, status_y):
            # Get theme colors
            bg_color = self.theme['colors']['status_bar']['background']
            text_color = self.theme['colors']['status_bar']['text']

            # Left side parts
            left_parts = []

            # Current media title - "Now Playing: <title>"
            # Try to get from current playlist, otherwise use cached title
            title = None
            if self.channel and self.channel.playlist and self.channel.playlist.current:
                current = self.channel.playlist.current
                # The current object should have a title attribute
                if hasattr(current, 'title'):
                    title = str(current.title)
            elif self.current_media_title:
                # Use cached title if current isn't available
                title = self.current_media_title

            if title:
                title = title[:40] + '...' if len(title) > 40 else title
                left_parts.append(f"▶ {title}")

            # Viewer count vs chat users
            if self.channel and hasattr(self.channel, 'userlist') and self.channel.userlist:
                chat_users = len(self.channel.userlist)
                total_viewers = self.channel.userlist.count if hasattr(self.channel.userlist, 'count') else chat_users
                left_parts.append(f"👥 {chat_users}/{total_viewers}")

            # 24h high water mark (if available from database)
            if hasattr(self, 'db') and self.db:
                try:
                    high_water = self.db.get_high_water_mark()
                    if high_water:
                        left_parts.append(f"📊 Peak: {high_water}")
                except Exception:
                    pass

            # Media runtime and remaining - use cached values from changeMedia
            if self.current_media_duration:
                # Total runtime - show seconds now
                total_mins, total_secs = divmod(int(self.current_media_duration), 60)
                if total_mins >= 60:
                    total_hours = total_mins // 60
                    total_mins = total_mins % 60
                    left_parts.append(f"⏱  Runtime: {total_hours}h {total_mins}m {total_secs}s")
                else:
                    left_parts.append(f"⏱  Runtime: {total_mins}m {total_secs}s")

                # Calculate current position and time remaining - show seconds
                if self.current_media_start_time and not self.current_media_paused:
                    import time as time_module
                    elapsed = time_module.time() - self.current_media_start_time
                    remaining = self.current_media_duration - elapsed
                    if remaining > 0:
                        rem_mins, rem_secs = divmod(int(remaining), 60)
                        if rem_mins >= 60:
                            rem_hours = rem_mins // 60
                            rem_mins = rem_mins % 60
                            left_parts.append(f"⏳ Remaining: {rem_hours}h {rem_mins}m {rem_secs}s")
                        else:
                            left_parts.append(f"⏳ Remaining: {rem_mins}m {rem_secs}s")

            # Right side parts (will be right-justified)
            right_parts = []

            # Session duration - show seconds
            session_duration = datetime.now() - self.session_start
            hours, remainder = divmod(int(session_duration.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                right_parts.append(f"⏱  Session: {hours}h {minutes}m {seconds}s")
            else:
                right_parts.append(f"⏱  Session: {minutes}m {seconds}s")

            # My username
            if self.user and hasattr(self.user, 'name') and self.user.name:
                right_parts.append(f"👤 {self.user.name}")

            # Build the status line
            left_text = "  │  ".join(left_parts) if left_parts else ""
            right_text = "  │  ".join(right_parts) if right_parts else ""

            # Calculate the actual display widths (accounting for emojis being wider)
            # Emojis can take 2 display columns, so we need to be careful
            left_display_len = len(left_text)
            right_display_len = len(right_text)

            # Calculate spacing - ensure 1-2 spaces after username (on right side)
            available_width = self.term.width - left_display_len - right_display_len - 2

            if available_width < 1:
                # Not enough space, just show left side
                status_line = left_text
                if len(status_line) < self.term.width:
                    status_line = status_line + ' ' * (self.term.width - len(status_line))
                else:
                    status_line = status_line[:self.term.width]
            else:
                # Add spacing between left and right
                status_line = left_text + ' ' * available_width + right_text
                # Ensure we fill exactly to width
                if len(status_line) < self.term.width:
                    status_line = status_line + ' ' * (self.term.width - len(status_line))
                elif len(status_line) > self.term.width:
                    status_line = status_line[:self.term.width]

            # Apply theme colors
            color_func = getattr(self.term, f'{text_color}_on_{bg_color}', self.term.black_on_cyan)
            print(color_func(status_line), end='', flush=True)

    def render_status(self):
        """Legacy method - redirect to top status bar."""
        self.render_top_status()

    def render_chat(self):
        """Render the chat history area with scrolling support."""
        # Calculate dimensions - now we have 4 lines used (top status, separator, bottom status, input)
        chat_height = self.term.height - 4
        user_list_width = 22
        chat_width = self.term.width - user_list_width - 1

        # Get visible messages based on scroll offset
        total_messages = len(self.chat_history)
        start_idx = max(0, total_messages - chat_height - self.scroll_offset)
        end_idx = total_messages - self.scroll_offset
        visible_messages = list(self.chat_history)[start_idx:end_idx]

        # Render separator line
        border_color = self.theme['colors']['borders']
        border_func = getattr(self.term, border_color, self.term.bright_black)
        with self.term.location(0, 1):
            print(border_func('─' * (chat_width)), end='', flush=True)

        # Render chat messages
        for i, msg_data in enumerate(visible_messages):
            line_num = 2 + i

            with self.term.location(0, line_num):
                # Clear the line
                print(' ' * chat_width, end='')

            with self.term.location(0, line_num):
                timestamp = msg_data['timestamp']
                username = msg_data['username']
                message = msg_data['message']
                prefix = msg_data['prefix']
                color = msg_data['color']

                # Format: [HH:MM:SS] <username> message
                # or:      [HH:MM:SS] [PM] <username> message
                time_str = self.term.bright_black(f'[{timestamp}]')

                # Get the color function from terminal
                color_func = getattr(self.term, color, self.term.white)

                if prefix:
                    username_str = f'{prefix} {color_func(f"<{username}>")} '
                else:
                    username_str = f'{color_func(f"<{username}>")} '

                # Calculate max message width
                prefix_len = len(f'[{timestamp}] ')
                if prefix:
                    prefix_len += len(f'{prefix} ')
                prefix_len += len(f'<{username}> ')

                max_msg_width = chat_width - prefix_len

                # Wrap message if needed (with 2 column padding after wrap)
                wrapped_lines = textwrap.wrap(message, width=max_msg_width, 
                                             break_long_words=True, 
                                             break_on_hyphens=True)

                # Check if my username is mentioned in the message
                if self.user and self.user.name and self.user.name in message:
                    # Highlight the entire message with reverse video
                    wrapped_lines = [self.term.reverse(line) for line in wrapped_lines]

                # Print first line with full prefix
                if wrapped_lines:
                    print(f'{time_str} {username_str}{wrapped_lines[0]}', end='', flush=True)

                    # Print continuation lines with padding (2 spaces after wrap point)
                    for wrap_line_idx, continuation in enumerate(wrapped_lines[1:], 1):
                        continuation_line_num = line_num + wrap_line_idx
                        # Stop if we've run out of screen space
                        if continuation_line_num >= chat_height + 2:
                            break
                        with self.term.location(0, continuation_line_num):
                            print(' ' * chat_width, end='')
                        with self.term.location(0, continuation_line_num):
                            indent = ' ' * (prefix_len + 2)  # 2 column padding
                            print(f'{indent}{continuation}', end='', flush=True)
                else:
                    # Empty message
                    print(f'{time_str} {username_str}', end='', flush=True)

        # Clear any remaining lines
        for i in range(len(visible_messages), chat_height):
            line_num = 2 + i
            with self.term.location(0, line_num):
                print(' ' * chat_width, end='', flush=True)

    def render_users(self):
        """Render the user list on the right side of the screen.

        Features:
        - Color coding by rank (brighter for mods+)
        - AFK users in italics, pushed to bottom, alphabetical
        - Active users grouped by rank
        - Muted users marked with [m]
        - Shadow muted users marked with [s]
        - Leader marked with [*]
        """
        if not self.channel or not self.channel.userlist:
            return

        user_list_width = 22
        user_list_x = self.term.width - user_list_width
        chat_height = self.term.height - 4  # Updated for new layout

        # Get theme colors
        header_bg = self.theme['colors']['user_list_header']['background']
        header_text = self.theme['colors']['user_list_header']['text']
        border_color = self.theme['colors']['borders']

        # Header
        with self.term.location(user_list_x, 1):
            user_count = len(self.channel.userlist)
            header = f' Users ({user_count}) '
            header = header.ljust(user_list_width - 1)
            header_func = getattr(self.term, f'{header_text}_on_{header_bg}', self.term.black_on_bright_white)
            print(header_func(header), end='', flush=True)

        # Vertical separator
        border_func = getattr(self.term, border_color, self.term.bright_black)
        for i in range(2, self.term.height - 2):
            with self.term.location(user_list_x - 1, i):
                print(border_func('│'), end='', flush=True)

        # Separate users into three groups: mods (rank >= 2), regular users, and AFK
        mods = []
        regular_users = []
        afk_users = []

        for user in self.channel.userlist.values():
            if user.afk:
                afk_users.append(user)
            elif user.rank >= 2:  # Moderator or higher
                mods.append(user)
            else:
                regular_users.append(user)

        # Sort each group alphabetically by name (case-insensitive)
        mods.sort(key=lambda u: u.name.lower())
        regular_users.sort(key=lambda u: u.name.lower())
        afk_users.sort(key=lambda u: u.name.lower())

        # Combine lists: mods first, then regular users, then AFK (if not hidden)
        sorted_users = mods + regular_users
        if not self.hide_afk_users:
            sorted_users += afk_users

        # Get rank colors from theme
        rank_colors = self.theme['colors']['user_ranks']
        symbols = self.theme['symbols']

        # Render users
        for i, user in enumerate(sorted_users[:chat_height]):
            line_num = 2 + i

            # IMPORTANT: Clear the entire line first to prevent artifacts
            with self.term.location(user_list_x, line_num):
                print(' ' * (user_list_width - 1), end='', flush=True)

            with self.term.location(user_list_x, line_num):
                # Get rank symbol from theme
                if user.rank >= 4:
                    rank_symbol = symbols.get('rank_owner', '~')
                    color_name = rank_colors.get('owner', 'bright_yellow')
                elif user.rank >= 3:
                    rank_symbol = symbols.get('rank_admin', '%')
                    color_name = rank_colors.get('admin', 'bright_yellow')
                elif user.rank >= 2:
                    rank_symbol = symbols.get('rank_moderator', '@')
                    color_name = rank_colors.get('moderator', 'bright_yellow')
                elif user.rank >= 1:
                    rank_symbol = symbols.get('rank_registered', '+')
                    color_name = rank_colors.get('registered', 'green')
                else:
                    rank_symbol = symbols.get('rank_guest', ' ')
                    color_name = rank_colors.get('guest', 'white')

                color_func = getattr(self.term, color_name, self.term.white)

                # Build username string
                user_str = f'{rank_symbol}{user.name}'

                # Add status indicators from theme
                if user.smuted:
                    user_str += symbols.get('shadow_muted_marker', '[s]')
                elif user.muted:
                    user_str += symbols.get('muted_marker', '[m]')

                # Add leader indicator
                if self.channel.userlist.leader == user:
                    user_str += symbols.get('leader_marker', '[*]')

                # Truncate if too long
                max_width = user_list_width - 2
                if len(user_str) > max_width:
                    user_str = user_str[:max_width - 1] + '…'

                # Apply formatting for AFK users (italic instead of dim)
                if user.afk:
                    try:
                        user_str = self.term.italic(user_str)
                    except (TypeError, AttributeError):
                        # Fallback if italic not supported
                        pass

                # Apply color
                colored_str = color_func(user_str)

                print(f' {colored_str}', end='', flush=True)

        # Clear remaining lines to prevent artifacts
        for i in range(len(sorted_users), chat_height):
            line_num = 2 + i
            with self.term.location(user_list_x, line_num):
                print(' ' * (user_list_width - 1), end='', flush=True)

    def render_input(self):
        """Render the input line at the bottom of the screen."""
        input_y = self.term.height - 1
        user_list_width = 22
        input_width = self.term.width - user_list_width - 1

        with self.term.location(0, input_y):
            # Clear the line
            print(' ' * input_width, end='')

        with self.term.location(0, input_y):
            # Input prompt
            prompt = self.term.bright_white('> ')
            print(prompt, end='', flush=True)

            # Calculate visible portion of input
            prompt_len = 2  # "> "
            max_input_width = input_width - prompt_len

            if len(self.input_buffer) > max_input_width:
                # Show the end of the input if it's too long
                visible_input = self.input_buffer[-(max_input_width):]
            else:
                visible_input = self.input_buffer

            print(visible_input, end='', flush=True)

    async def handle_input(self):
        """Handle keyboard input in an async loop.

        This is the main input loop that processes user keyboard input,
        including regular typing, special keys, and commands.
        """
        with self.term.cbreak(), self.term.hidden_cursor():
            while self.running:
                current_time = time.time()

                # Periodic terminal size check on Windows (every 10 seconds)
                if self.is_windows and current_time - self.last_size_check >= self.size_check_interval:
                    self._check_terminal_size()
                    self.last_size_check = current_time

                # Periodic status bar update (every second)
                if current_time - self.last_status_update >= self.status_update_interval:
                    self.render_top_status()
                    self.render_bottom_status()
                    # Restore cursor to input position
                    self.render_input()
                    self.last_status_update = current_time

                key = self.term.inkey(timeout=0.1)

                if not key:
                    await asyncio.sleep(0.01)
                    continue

                # Handle special keys
                if key.name == 'KEY_ENTER':
                    await self.process_command()
                elif key.name == 'KEY_TAB':
                    self.handle_tab_completion()
                elif key.name == 'KEY_BACKSPACE' or key.name == 'KEY_DELETE':
                    if self.input_buffer:
                        self.input_buffer = self.input_buffer[:-1]
                        # Reset tab completion on edit
                        self.tab_completion_matches = []
                        self.render_input()
                elif key.name == 'KEY_UP':
                    self.navigate_history_up()
                elif key.name == 'KEY_DOWN':
                    self.navigate_history_down()
                elif key.name == 'KEY_PGUP':
                    self.scroll_up()
                elif key.name == 'KEY_PGDOWN':
                    self.scroll_down()
                # Ctrl+Up and Ctrl+Down for scrolling
                elif key == '\x1b[1;5A':  # Ctrl+Up
                    self.scroll_up()
                elif key == '\x1b[1;5B':  # Ctrl+Down
                    self.scroll_down()
                elif key.name == 'KEY_ESCAPE':
                    # Could be used for commands/menus in the future
                    pass
                elif key.is_sequence:
                    # Ignore other special sequences
                    pass
                else:
                    # Regular character input
                    self.input_buffer += key
                    # Reset tab completion on new input
                    self.tab_completion_matches = []
                    self.render_input()

    def handle_tab_completion(self):
        """Handle tab completion for usernames and emotes.

        CyTube-specific tab completion:
        - Emotes: Start with '#' (e.g., #smi<TAB> -> #smile)
        - Usernames: After 2+ alphanumeric characters anywhere in text (e.g., ali<TAB> -> alice)

        Pressing Tab multiple times cycles through matches alphabetically.
        No matches = tab is ignored.
        """
        if not self.input_buffer:
            return

        # If we have existing matches, cycle through them
        if self.tab_completion_matches:
            self.tab_completion_index = (self.tab_completion_index + 1) % len(self.tab_completion_matches)
            match = self.tab_completion_matches[self.tab_completion_index]

            # Replace from the start position to the end
            self.input_buffer = self.input_buffer[:self.tab_completion_start] + match
            self.render_input()
            return

        cursor_pos = len(self.input_buffer)

        # Check for emote completion (starts with #)
        # Find the last # in the buffer
        last_hash = self.input_buffer.rfind('#')
        if last_hash >= 0 and last_hash < cursor_pos:
            # Make sure there's no whitespace between # and cursor
            text_after_hash = self.input_buffer[last_hash + 1:cursor_pos]
            if ' ' not in text_after_hash:
                # Extract partial emote name after #
                partial = text_after_hash
                matches = self._get_emote_matches(partial)

                if matches:
                    # Store state for cycling
                    self.tab_completion_matches = matches
                    self.tab_completion_index = 0
                    self.tab_completion_start = last_hash

                    # Apply first match (includes the # prefix)
                    self.input_buffer = self.input_buffer[:last_hash] + matches[0]
                    self.render_input()
                return

        # Check for username completion (2+ alphanumeric chars)
        # Find the start of the current word (working backwards from cursor)
        start_pos = cursor_pos - 1
        while start_pos >= 0 and self.input_buffer[start_pos].isalnum():
            start_pos -= 1
        start_pos += 1  # Move to first char of the word

        # Extract the partial username
        partial = self.input_buffer[start_pos:cursor_pos]

        # Only attempt username completion if we have 2+ characters
        if len(partial) >= 2:
            matches = self._get_username_matches(partial)

            if matches:
                # Store state for cycling
                self.tab_completion_matches = matches
                self.tab_completion_index = 0
                self.tab_completion_start = start_pos

                # Apply first match (no prefix or suffix)
                self.input_buffer = self.input_buffer[:start_pos] + matches[0]
                self.render_input()

    def _get_username_matches(self, partial):
        """Get list of usernames matching the partial string.

        Args:
            partial (str): Partial username to match (minimum 2 characters)

        Returns:
            list: List of matching usernames, sorted alphabetically
        """
        if not self.channel or not self.channel.userlist:
            return []

        partial_lower = partial.lower()
        matches = []

        for username in self.channel.userlist.keys():
            # Skip usernames with underscores (CyTube bug workaround)
            if '_' in username:
                continue

            if username.lower().startswith(partial_lower):
                matches.append(username)

        # Sort matches alphabetically (case-insensitive)
        matches.sort(key=str.lower)
        return matches

    def _get_emote_matches(self, partial):
        """Get list of emotes matching the partial string.

        Args:
            partial (str): Partial emote name to match (without # prefix)

        Returns:
            list: List of matching emotes (with # prefix, no suffix)
        """
        # Common CyTube emotes - in a real implementation, this would come from channel config
        # These are typical emotes found on CyTube channels
        common_emotes = [
            'smile', 'sad', 'laugh', 'lol', 'angry', 'rage', 'heart', 'love',
            'thumbsup', 'thumbsdown', 'thinking', 'think', 'wave', 'hello',
            'party', 'dance', 'fire', 'hot', 'cool', 'sunglasses', 'eyes',
            'shrug', 'idk', 'check', 'yes', 'cross', 'no', 'question',
            'exclamation', 'star', 'sparkles', 'kappa', 'pogchamp', 'lul',
            'monkas', 'omegalul', 'pepega', 'pepe', 'sadge', 'pog', 'copium'
        ]

        partial_lower = partial.lower()
        matches = []

        for emote in common_emotes:
            if emote.startswith(partial_lower):
                # Return with # prefix, no suffix
                matches.append('#' + emote)

        # Sort matches alphabetically
        matches.sort(key=str.lower)
        return matches

    def navigate_history_up(self):
        """Navigate backward in command history (up arrow)."""
        if not self.input_history:
            return

        if self.history_pos == -1:
            # Save current input before navigating
            self._temp_input = self.input_buffer
            self.history_pos = len(self.input_history) - 1
        elif self.history_pos > 0:
            self.history_pos -= 1

        if 0 <= self.history_pos < len(self.input_history):
            self.input_buffer = self.input_history[self.history_pos]
            self.render_input()

    def navigate_history_down(self):
        """Navigate forward in command history (down arrow)."""
        if not self.input_history or self.history_pos == -1:
            return

        self.history_pos += 1

        if self.history_pos >= len(self.input_history):
            # Restore temporary input or clear
            self.input_buffer = getattr(self, '_temp_input', '')
            self.history_pos = -1
        else:
            self.input_buffer = self.input_history[self.history_pos]

        self.render_input()

    def scroll_up(self):
        """Scroll chat history up (Page Up)."""
        max_scroll = max(0, len(self.chat_history) - (self.term.height - 3))
        self.scroll_offset = min(self.scroll_offset + 10, max_scroll)
        self.render_chat()
        self.render_input()

    def scroll_down(self):
        """Scroll chat history down (Page Down)."""
        self.scroll_offset = max(0, self.scroll_offset - 10)
        self.render_chat()
        self.render_input()

    async def process_command(self):
        """Process the current input buffer as a command or message.

        Commands start with '/' and are handled specially. Regular messages
        are sent to the chat.

        Commands:
            /help - Show available commands
            /pm <user> <message> - Send private message
            /me <action> - Send action message
            /quit - Exit the application
            /clear - Clear chat history
            /scroll - Scroll to bottom
            /togglejoins - Toggle join/quit messages
        """
        if not self.input_buffer.strip():
            return

        # Add to history
        self.input_history.append(self.input_buffer)
        self.history_pos = -1

        # Parse command
        text = self.input_buffer.strip()
        self.input_buffer = ''
        self.render_input()

        try:
            if text.startswith('/'):
                await self.handle_slash_command(text)
            else:
                # Regular chat message
                await self.chat(text)
        except Exception as e:
            self.add_system_message(f'Error: {e}', color='bright_red')

    async def handle_slash_command(self, text):
        """Handle slash commands.

        Args:
            text (str): The command text starting with '/'
        """
        parts = text[1:].split(None, 1)
        if not parts:
            return

        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        if command == 'help':
            self.show_help()
        elif command == 'pm':
            await self.handle_pm_command(args)
        elif command == 'me':
            await self.chat(f'/me {args}')
        elif command == 'quit' or command == 'exit':
            self.running = False
        elif command == 'clear':
            self.chat_history.clear()
            self.render_screen()
        elif command == 'scroll':
            self.scroll_offset = 0
            self.render_chat()
            self.render_input()
        elif command == 'togglejoins':
            self.show_join_quit = not self.show_join_quit
            status = "enabled" if self.show_join_quit else "disabled"
            self.add_system_message(f'Join/quit messages {status}', color='bright_cyan')
        elif command == 'current' or command == 'np':
            # Show current media information
            if self.channel and self.channel.playlist and self.channel.playlist.current:
                current = self.channel.playlist.current
                self.add_system_message('━━━ Current Media Info ━━━', color='bright_cyan')
                self.add_system_message(f'Title: {current.title if hasattr(current, "title") else "N/A"}', color='bright_white')
                self.add_system_message(f'Duration: {current.duration if hasattr(current, "duration") else "N/A"}s', color='bright_white')
                self.add_system_message(f'Current time: {current.seconds if hasattr(current, "seconds") else "N/A"}s', color='bright_white')
                self.add_system_message(f'Username: {current.username if hasattr(current, "username") else "N/A"}', color='bright_white')
                self.add_system_message(f'Object type: {type(current).__name__}', color='bright_black')
                self.add_system_message(f'Cached title: {self.current_media_title or "None"}', color='bright_black')
            else:
                self.add_system_message('No media currently playing', color='bright_red')
                self.add_system_message(f'Channel: {self.channel is not None}', color='bright_black')
                self.add_system_message(f'Playlist: {self.channel.playlist is not None if self.channel else "N/A"}', color='bright_black')
                self.add_system_message(f'Current: {self.channel.playlist.current is not None if self.channel and self.channel.playlist else "N/A"}', color='bright_black')
                self.add_system_message(f'Cached title: {self.current_media_title or "None"}', color='bright_black')
        elif command == 'debug':
            # Show detailed debug information about playlist
            self.add_system_message('━━━ Playlist Debug Info ━━━', color='bright_cyan')
            if self.channel and self.channel.playlist:
                queue = self.channel.playlist.queue
                self.add_system_message(f'Queue length: {len(queue)}', color='bright_white')
                self.add_system_message(f'Pending UID: {self.pending_media_uid or "None"}', color='bright_white')
                if queue:
                    self.add_system_message('First 5 items in queue:', color='bright_cyan')
                    for item in queue[:5]:
                        self.add_system_message(f'  UID {item.uid}: {item.title[:40]}', color='bright_black')
                # Try to manually find what should be current
                if self.pending_media_uid and queue:
                    try:
                        item = self.channel.playlist.get(self.pending_media_uid)
                        self.add_system_message(f'Found pending UID {self.pending_media_uid}: {item.title}', color='bright_green')
                    except:
                        self.add_system_message(f'Pending UID {self.pending_media_uid} NOT in queue', color='bright_red')
            else:
                self.add_system_message('No playlist available', color='bright_red')
        elif command == 'theme':
            # Theme management
            if not args:
                # List available themes
                themes = self.list_themes()
                self.add_system_message('━━━ Available Themes ━━━', color='bright_cyan')
                self.add_system_message(f'Current: {self.current_theme_name} - {self.theme.get("name", "Unknown")}', color='bright_green')
                self.add_system_message('', color='white')
                for theme_name, theme_data in themes:
                    theme_data.get('name', theme_name)
                    desc = theme_data.get('description', 'No description')
                    marker = ' ⭐' if theme_name == self.current_theme_name else ''
                    self.add_system_message(f'  {theme_name}{marker}', color='bright_white')
                    self.add_system_message(f'    {desc}', color='bright_black')
                self.add_system_message('', color='white')
                self.add_system_message('Usage: /theme <name> to switch themes', color='bright_black')
            else:
                # Change theme
                theme_name = args.strip().lower()
                if self.change_theme(theme_name):
                    self.add_system_message(f'Theme changed to: {self.theme.get("name", theme_name)}', color='bright_green')
                    self.render_screen()  # Redraw with new theme
                else:
                    self.add_system_message(f'Failed to load theme: {theme_name}', color='bright_red')
                    self.add_system_message('Use /theme to list available themes', color='bright_black')

        # === Info & Status Commands ===
        elif command == 'info':
            await self.cmd_info()
        elif command == 'status':
            await self.cmd_status()

        # === User Management ===
        elif command == 'users':
            await self.cmd_users()
        elif command == 'user':
            await self.cmd_user(args)
        elif command == 'afk':
            await self.cmd_afk(args)

        # === Chat Commands ===
        elif command == 'say':
            await self.cmd_say(args)

        # === Playlist Commands ===
        elif command == 'playlist':
            await self.cmd_playlist(args)
        elif command == 'add':
            await self.cmd_add(args)
        elif command == 'remove':
            await self.cmd_remove(args)
        elif command == 'move':
            await self.cmd_move(args)
        elif command == 'jump':
            await self.cmd_jump(args)
        elif command == 'next' or command == 'skip':
            await self.cmd_next()

        # === Channel Control ===
        elif command == 'pause':
            await self.cmd_pause()
        elif command == 'kick':
            await self.cmd_kick(args)
        elif command == 'voteskip':
            await self.cmd_voteskip()

        else:
            self.add_system_message(f'Unknown command: /{command}', color='bright_red')

    async def handle_pm_command(self, args):
        """Handle /pm command.

        Args:
            args (str): Arguments in format "<username> <message>"
        """
        parts = args.split(None, 1)
        if len(parts) < 2:
            self.add_system_message('Usage: /pm <username> <message>', color='bright_red')
            return

        username, message = parts
        await self.pm(username, message)
        self.add_chat_line(
            username,
            message,
            prefix='[PM->]',
            color_override='bright_magenta'
        )

    # === Command Implementations ===

    async def cmd_info(self):
        """Show bot and channel information."""
        self.add_system_message('━━━ Bot & Channel Info ━━━', color='bright_cyan')
        self.add_system_message(f'Bot: {self.user.name}', color='bright_white')
        self.add_system_message(f'Rank: {self.user.rank}', color='bright_white')
        self.add_system_message(f'AFK: {"Yes" if self.user.afk else "No"}', color='bright_white')

        if self.channel:
            self.add_system_message(f'Channel: {self.channel.name}', color='bright_white')

            # Show both chat users and total connected viewers
            chat_users = len(self.channel.userlist)
            total_viewers = self.channel.userlist.count
            if total_viewers and total_viewers != chat_users:
                self.add_system_message(f'Users: {chat_users} in chat, {total_viewers} connected', color='bright_white')
            else:
                self.add_system_message(f'Users: {chat_users}', color='bright_white')

            if self.channel.playlist:
                total = len(self.channel.playlist.queue)
                self.add_system_message(f'Playlist: {total} items', color='bright_white')
                # Calculate total playlist duration
                total_time = sum(item.duration for item in self.channel.playlist.queue)
                if total_time > 0:
                    duration = self.format_duration(total_time)
                    self.add_system_message(f'Duration: {duration}', color='bright_white')
                if self.channel.playlist.current:
                    title = self.channel.playlist.current.title
                    self.add_system_message(f'Now playing: {title}', color='bright_white')

    async def cmd_status(self):
        """Show connection status."""
        self.add_system_message('━━━ Connection Status ━━━', color='bright_cyan')

        # Bot uptime (session start)
        uptime = (datetime.now() - self.session_start).total_seconds()
        self.add_system_message(f'Uptime: {self.format_duration(uptime)}', color='bright_white')

        # Connection status
        self.add_system_message(f'Connected: {"Yes" if self.socket else "No"}', color='bright_white')
        if self.socket:
            self.add_system_message(f'Server: {self.server}', color='bright_white')

        if self.channel:
            self.add_system_message(f'Channel: {self.channel.name}', color='bright_white')
            if self.channel.userlist.leader:
                self.add_system_message(f'Leader: {self.channel.userlist.leader.name}', color='bright_white')
            if self.channel.playlist:
                paused = self.channel.playlist.paused
                self.add_system_message(f'Playback: {"Paused" if paused else "Playing"}', color='bright_white')

    async def cmd_users(self):
        """List all users in channel."""
        if not self.channel or not self.channel.userlist:
            self.add_system_message('No users information available', color='bright_red')
            return

        self.add_system_message(f'━━━ Users in Channel ({len(self.channel.userlist)}) ━━━', color='bright_cyan')

        users = sorted(self.channel.userlist.values(), key=lambda u: u.rank, reverse=True)
        for user in users:
            flags = []
            if user.afk:
                flags.append("AFK")
            if user.muted:
                flags.append("MUTED")
            if self.channel.userlist.leader == user:
                flags.append("LEADER")

            flag_str = f" [{', '.join(flags)}]" if flags else ""
            self.add_system_message(f'  [{user.rank}] {user.name}{flag_str}', color='bright_white')

    async def cmd_user(self, username):
        """Show detailed info about a user."""
        if not username:
            self.add_system_message('Usage: /user <username>', color='bright_red')
            return

        if not self.channel or username not in self.channel.userlist:
            self.add_system_message(f'User "{username}" not found', color='bright_red')
            return

        user = self.channel.userlist[username]
        self.add_system_message(f'━━━ User Info: {user.name} ━━━', color='bright_cyan')
        self.add_system_message(f'Rank: {user.rank}', color='bright_white')
        self.add_system_message(f'AFK: {"Yes" if user.afk else "No"}', color='bright_white')
        self.add_system_message(f'Muted: {"Yes" if user.muted else "No"}', color='bright_white')
        if self.channel.userlist.leader == user:
            self.add_system_message('Status: LEADER', color='bright_yellow')

    async def cmd_afk(self, args):
        """Set bot AFK status."""
        if not args:
            status = "On" if self.user.afk else "Off"
            self.add_system_message(f'Current AFK status: {status}', color='bright_cyan')
            return

        args_lower = args.lower()
        if args_lower in ('on', 'yes', 'true', '1'):
            await self.set_afk(True)
            self.add_system_message('AFK status: On', color='bright_green')
        elif args_lower in ('off', 'no', 'false', '0'):
            await self.set_afk(False)
            self.add_system_message('AFK status: Off', color='bright_green')
        else:
            self.add_system_message('Usage: /afk [on|off]', color='bright_red')

    async def cmd_say(self, message):
        """Send a chat message."""
        if not message:
            self.add_system_message('Usage: /say <message>', color='bright_red')
            return

        await self.chat(message)

    async def cmd_playlist(self, args):
        """Show playlist."""
        if not self.channel or not self.channel.playlist:
            self.add_system_message('No playlist information available', color='bright_red')
            return

        # Parse optional limit argument
        limit = 10
        if args:
            try:
                limit = int(args)
            except ValueError:
                self.add_system_message('Usage: /playlist [number]', color='bright_red')
                return

        queue = self.channel.playlist.queue
        self.add_system_message(f'━━━ Playlist ({len(queue)} items) ━━━', color='bright_cyan')

        for i, item in enumerate(queue[:limit], 1):
            marker = "► " if item == self.channel.playlist.current else "  "
            duration = self.format_duration(item.duration)
            title = item.title[:50] + '...' if len(item.title) > 50 else item.title
            self.add_system_message(f'{marker}{i}. {title} ({duration})', color='bright_white')

        if len(queue) > limit:
            self.add_system_message(f'  ... and {len(queue) - limit} more', color='bright_black')

    async def cmd_add(self, args):
        """Add media to playlist."""
        parts = args.split()
        if not parts:
            self.add_system_message('Usage: /add <url> [temp]  (temp: yes/no, default=yes)', color='bright_red')
            return

        url = parts[0]
        temp = True

        if len(parts) > 1:
            temp_arg = parts[1].lower()
            if temp_arg in ('no', 'false', '0', 'perm'):
                temp = False

        try:
            from lib.media_link import MediaLink
            link = MediaLink.from_url(url)
            await self.add_media(link, append=True, temp=temp)
            temp_str = 'temporary' if temp else 'permanent'
            self.add_system_message(f'Added: {url} ({temp_str})', color='bright_green')
        except Exception as e:
            self.add_system_message(f'Failed to add media: {e}', color='bright_red')

    async def cmd_remove(self, args):
        """Remove item from playlist."""
        if not args:
            self.add_system_message('Usage: /remove <position>', color='bright_red')
            return

        try:
            pos = int(args)
        except ValueError:
            self.add_system_message('Invalid position number', color='bright_red')
            return

        if not self.channel or not self.channel.playlist:
            self.add_system_message('No playlist available', color='bright_red')
            return

        queue = self.channel.playlist.queue
        if pos < 1 or pos > len(queue):
            self.add_system_message(f'Position must be between 1 and {len(queue)}', color='bright_red')
            return

        item = queue[pos - 1]
        await self.remove_media(item)
        self.add_system_message(f'Removed: {item.title}', color='bright_green')

    async def cmd_move(self, args):
        """Move playlist item."""
        parts = args.split()
        if len(parts) < 2:
            self.add_system_message('Usage: /move <from_pos> <to_pos>', color='bright_red')
            return

        try:
            from_pos = int(parts[0])
            to_pos = int(parts[1])
        except ValueError:
            self.add_system_message('Invalid position numbers', color='bright_red')
            return

        if not self.channel or not self.channel.playlist:
            self.add_system_message('No playlist available', color='bright_red')
            return

        queue = self.channel.playlist.queue
        if from_pos < 1 or from_pos > len(queue):
            self.add_system_message(f'From position must be between 1 and {len(queue)}', color='bright_red')
            return
        if to_pos < 1 or to_pos > len(queue):
            self.add_system_message(f'To position must be between 1 and {len(queue)}', color='bright_red')
            return

        from_item = queue[from_pos - 1]
        # After position in CyTube is the item before the target position
        after_item = queue[to_pos - 2] if to_pos > 1 else None

        if after_item:
            await self.move_media(from_item, after_item)
            self.add_system_message(f'Moved "{from_item.title}" from position {from_pos} to {to_pos}', color='bright_green')
        else:
            self.add_system_message('Moving to beginning not yet supported', color='bright_red')

    async def cmd_jump(self, args):
        """Jump to playlist item."""
        if not args:
            self.add_system_message('Usage: /jump <position>', color='bright_red')
            return

        try:
            pos = int(args)
        except ValueError:
            self.add_system_message('Invalid position number', color='bright_red')
            return

        if not self.channel or not self.channel.playlist:
            self.add_system_message('No playlist available', color='bright_red')
            return

        queue = self.channel.playlist.queue
        if pos < 1 or pos > len(queue):
            self.add_system_message(f'Position must be between 1 and {len(queue)}', color='bright_red')
            return

        item = queue[pos - 1]
        await self.set_current_media(item)
        self.add_system_message(f'Jumped to: {item.title}', color='bright_green')

    async def cmd_next(self):
        """Skip to next item."""
        if not self.channel or not self.channel.playlist:
            self.add_system_message('No playlist available', color='bright_red')
            return

        current = self.channel.playlist.current
        if not current:
            self.add_system_message('Nothing is currently playing', color='bright_red')
            return

        queue = self.channel.playlist.queue
        try:
            current_idx = queue.index(current)
            if current_idx + 1 < len(queue):
                next_item = queue[current_idx + 1]
                await self.set_current_media(next_item)
                self.add_system_message(f'Skipped to: {next_item.title}', color='bright_green')
            else:
                self.add_system_message('Already at last item', color='bright_red')
        except ValueError:
            self.add_system_message('Current item not in queue', color='bright_red')

    async def cmd_pause(self):
        """Pause playback."""
        await self.pause()
        self.add_system_message('Paused', color='bright_green')

    async def cmd_kick(self, args):
        """Kick a user."""
        parts = args.split(None, 1)
        if not parts:
            self.add_system_message('Usage: /kick <user> [reason]', color='bright_red')
            return

        username = parts[0]
        reason = parts[1] if len(parts) > 1 else ""

        await self.kick(username, reason)
        reason_str = f': {reason}' if reason else ''
        self.add_system_message(f'Kicked {username}{reason_str}', color='bright_green')

    async def cmd_voteskip(self):
        """Show voteskip status."""
        if not self.channel:
            self.add_system_message('No channel information available', color='bright_red')
            return

        count = self.channel.voteskip_count
        need = self.channel.voteskip_need
        self.add_system_message(f'Voteskip: {count}/{need}', color='bright_cyan')

    def show_help(self):
        """Display help information about available commands."""
        help_lines = [
            '━━━ Available Commands ━━━',
            '',
            '📋 General:',
            '  /help or /h - Show this help message',
            '  /info - Show user & channel info',
            '  /status - Show connection status & uptime',
            '  /theme [name] - List themes or change theme',
            '  /quit or /q - Exit the chat client',
            '',
            '👥 Users:',
            '  /users - List all users in channel',
            '  /user <name> - Show details about a specific user',
            '  /afk [on|off] - Set your AFK status',
            '',
            '💬 Chat:',
            '  /pm <user> <msg> - Send private message',
            '  /me <action> - Send action message',
            '  /clear - Clear chat history from display',
            '  /scroll - Scroll to bottom of chat',
            '  /togglejoins - Show/hide join/quit messages',
            '',
            '🎵 Playlist:',
            '  /playlist [n] - Show queue (default 10)',
            '  /current or /np - Show current media info',
            '  /add <url> [temp] - Add video (temp: yes/no)',
            '  /remove <#> - Remove item by position',
            '  /move <#> <#> - Move item position',
            '  /jump <#> - Jump to position',
            '',
            '⚙️  Control:',
            '  /pause - Pause playback',
            '  /kick <user> [reason] - Kick user',
            '  /voteskip - Show voteskip status',
            '',
            '━━━ Keybindings ━━━',
            'Enter - Send your message',
            'Tab - Auto-complete usernames and #emotes',
            'Up/Down - Navigate through command history',
            'PgUp/PgDn - Scroll chat history up/down',
            'Ctrl+Up/Down - Alternative scroll keys',
            'Ctrl+C - Force quit',
        ]

        info_color = self.theme['colors']['messages']['system_info']
        for line in help_lines:
            self.add_system_message(line, color=info_color)

    async def run_tui(self):
        """Run the TUI main loop.

        This creates the asyncio tasks for both the bot connection and
        the input handling, managing their lifecycle.
        """
        self.running = True

        # Initial screen render
        self.render_screen()

        # Create tasks
        input_task = asyncio.create_task(self.handle_input())
        bot_task = asyncio.create_task(self.run())

        try:
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [input_task, bot_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            self.add_system_message(f'Fatal error: {e}', color='bright_red')
            self.logger.exception('Fatal error in TUI')
        finally:
            self.running = False
            # Close chat log file
            if hasattr(self, 'chat_log_file'):
                try:
                    self.chat_log_file.close()
                except Exception as e:
                    self.logger.error(f'Error closing chat log: {e}')


async def run_tui_bot():
    """Run the TUI bot with proper async handling.

    This is the main entry point that loads configuration, creates the bot
    instance, and starts the TUI loop.
    """
    # Load configuration
    conf, kwargs = get_config()

    # Extract TUI-specific configuration
    tui_config = conf.get('tui', {})

    # Disable database tracking for TUI (keep it lightweight)
    kwargs['enable_db'] = False

    # Create bot instance with TUI config
    bot = TUIBot(tui_config=tui_config, **kwargs)

    try:
        # Run the TUI
        await bot.run_tui()
    except KeyboardInterrupt:
        bot.running = False
    except (CytubeError, SocketIOError) as ex:
        print(f'\nConnection error: {ex}', file=sys.stderr)
    finally:
        # Cleanup terminal
        print(bot.term.normal)
        print(bot.term.clear)
        print('Goodbye!')


def main():
    """Main entry point for the TUI bot.

    Returns:
        int: Exit code (0 for success, 1 for error)
    """
    try:
        asyncio.run(run_tui_bot())
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        print(f'\nFatal error: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
