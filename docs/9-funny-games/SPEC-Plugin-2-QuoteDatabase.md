# Sprint 9 - Plugin 2: Quote Database

**Complexity:** ⭐⭐⭐☆☆ (Medium)  
**Effort:** 4 hours  
**Priority:** Storage validation  
**Status:** Specification Complete

## Overview

The Quote Database plugin allows users to save, retrieve, and search memorable chat quotes. This plugin validates storage adapter integration, data persistence, and hot reload with existing data.

### Purpose

- **User Value:** Preserve memorable chat moments and inside jokes
- **Architecture Value:** Validates storage adapter, persistence, hot reload
- **Learning Value:** Demonstrates database integration patterns

### Features

- Add quotes with attribution
- Retrieve specific quotes by ID
- Get random quotes
- Search quotes by text
- View quote statistics
- Persistent SQLite storage

## Commands

### `!quote add <text>`

Add a new quote to the database.

**Examples:**
```
!quote add That was hilarious!
✅ Quote #1 added

!quote add The bot is becoming sentient...
✅ Quote #2 added
```

**Limits:**
- Maximum 500 characters per quote
- Duplicate detection (warns if similar quote exists)

### `!quote get <id>`

Retrieve a specific quote by ID.

**Examples:**
```
!quote get 1
Quote #1 (added by user123 on 2025-11-12):
  "That was hilarious!"

!quote get 999
❌ Quote #999 not found
```

### `!quote random`

Get a random quote from the database.

**Examples:**
```
!quote random
Quote #5 (added by alice on 2025-11-10):
  "I can't believe that worked!"

!quote random
(No quotes available)
```

### `!quote search <text>`

Search for quotes containing text (case-insensitive).

**Examples:**
```
!quote search hilarious
Found 2 quotes:
  #1: "That was hilarious!" (user123, 2025-11-12)
  #7: "This is hilariously broken" (bob, 2025-11-11)

!quote search xyz
No quotes found matching "xyz"
```

**Limits:**
- Returns up to 5 results
- Shows preview (first 50 characters)

### `!quote stats`

Show quote database statistics.

**Examples:**
```
!quote stats
📊 Quote Database Stats:
  Total quotes: 42
  Contributors: 8 users
  Most recent: "The bot is alive!" by alice (5 minutes ago)
  Most active contributor: user123 (12 quotes)
```

### `!quote help`

Show command help.

## Configuration

File: `plugins/quote_db/config.json`

```json
{
  "max_quote_length": 500,
  "search_result_limit": 5,
  "preview_length": 50,
  "enable_duplicate_detection": true,
  "duplicate_similarity_threshold": 0.8
}
```

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    added_by TEXT NOT NULL,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quotes_text ON quotes(text);
```

## Implementation

### File Structure

```
plugins/quote_db/
├── __init__.py
├── plugin.py
└── config.json
```

### Code: `plugins/quote_db/__init__.py`

```python
"""Quote database plugin for cytube-bot."""

from .plugin import QuoteDBPlugin

__all__ = ['QuoteDBPlugin']
```

### Code: `plugins/quote_db/config.json`

```json
{
  "max_quote_length": 500,
  "search_result_limit": 5,
  "preview_length": 50,
  "enable_duplicate_detection": true,
  "duplicate_similarity_threshold": 0.8
}
```

### Code: `plugins/quote_db/plugin.py`

```python
"""
Quote Database Plugin

Stores and retrieves memorable chat quotes with SQLite persistence.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from lib.plugin import Plugin
from lib.channel import Channel
from lib.user import User


class QuoteDBPlugin(Plugin):
    """Plugin for storing and retrieving chat quotes."""
    
    def __init__(self, manager):
        """Initialize the quote database plugin."""
        super().__init__(manager)
        self.name = "quote_db"
        self.version = "1.0.0"
        self.description = "Store and retrieve memorable chat quotes"
        self.author = "cytube-bot"
        
        # Configuration (loaded during setup)
        self.max_quote_length = 500
        self.search_result_limit = 5
        self.preview_length = 50
        self.enable_duplicate_detection = True
        self.duplicate_similarity_threshold = 0.8
        
        # Database connection
        self.db = None
    
    async def setup(self):
        """Set up the plugin (database and commands)."""
        # Load configuration
        config = self.get_config()
        self.max_quote_length = config.get('max_quote_length', 500)
        self.search_result_limit = config.get('search_result_limit', 5)
        self.preview_length = config.get('preview_length', 50)
        self.enable_duplicate_detection = config.get('enable_duplicate_detection', True)
        self.duplicate_similarity_threshold = config.get('duplicate_similarity_threshold', 0.8)
        
        # Initialize database
        await self._init_database()
        
        # Register commands
        await self.register_command('quote', self._handle_quote)
        
        self.logger.info(f"Quote Database plugin loaded")
    
    async def teardown(self):
        """Clean up plugin resources."""
        if self.db:
            self.db.close()
            self.db = None
        self.logger.info(f"Quote Database plugin unloaded")
    
    async def _init_database(self):
        """Initialize SQLite database with schema."""
        # Get database path from storage adapter
        db_path = self.get_storage_path('quotes.db')
        
        # Connect to database
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        
        # Create schema
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                added_by TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index for search performance
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_quotes_text ON quotes(text)
        ''')
        
        self.db.commit()
        self.logger.info(f"Database initialized at {db_path}")
    
    async def _handle_quote(self, channel: Channel, user: User, args: str):
        """
        Handle the !quote command.
        
        Subcommands:
            add <text>     - Add a quote
            get <id>       - Get quote by ID
            random         - Get random quote
            search <text>  - Search quotes
            stats          - Show statistics
            help           - Show help
        """
        if not args.strip():
            await self._handle_help(channel)
            return
        
        # Parse subcommand
        parts = args.strip().split(maxsplit=1)
        subcommand = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""
        
        # Route to handler
        if subcommand == "add":
            await self._handle_add(channel, user, subargs)
        elif subcommand == "get":
            await self._handle_get(channel, subargs)
        elif subcommand == "random":
            await self._handle_random(channel)
        elif subcommand == "search":
            await self._handle_search(channel, subargs)
        elif subcommand == "stats":
            await self._handle_stats(channel)
        elif subcommand == "help":
            await self._handle_help(channel)
        else:
            await channel.send_message(f"❌ Unknown subcommand: {subcommand}")
            await self._handle_help(channel)
    
    async def _handle_add(self, channel: Channel, user: User, text: str):
        """Add a new quote."""
        if not text.strip():
            await channel.send_message("❌ Quote text cannot be empty")
            return
        
        # Validate length
        if len(text) > self.max_quote_length:
            await channel.send_message(
                f"❌ Quote too long (max {self.max_quote_length} characters)"
            )
            return
        
        # Check for duplicates
        if self.enable_duplicate_detection:
            similar = await self._find_similar_quotes(text)
            if similar:
                quote_id, similar_text = similar
                await channel.send_message(
                    f"⚠️ Similar quote already exists: #{quote_id}"
                )
                # Don't add duplicate
                return
        
        # Insert quote
        cursor = self.db.cursor()
        cursor.execute(
            'INSERT INTO quotes (text, added_by) VALUES (?, ?)',
            (text, user.username)
        )
        self.db.commit()
        
        quote_id = cursor.lastrowid
        await channel.send_message(f"✅ Quote #{quote_id} added")
    
    async def _handle_get(self, channel: Channel, id_str: str):
        """Get a specific quote by ID."""
        if not id_str.strip():
            await channel.send_message("❌ Please provide a quote ID")
            return
        
        try:
            quote_id = int(id_str.strip())
        except ValueError:
            await channel.send_message("❌ Invalid quote ID (must be a number)")
            return
        
        # Query quote
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT id, text, added_by, added_at FROM quotes WHERE id = ?',
            (quote_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            await channel.send_message(f"❌ Quote #{quote_id} not found")
            return
        
        # Format and send
        message = self._format_quote(row)
        await channel.send_message(message)
    
    async def _handle_random(self, channel: Channel):
        """Get a random quote."""
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT id, text, added_by, added_at FROM quotes ORDER BY RANDOM() LIMIT 1'
        )
        row = cursor.fetchone()
        
        if not row:
            await channel.send_message("(No quotes available)")
            return
        
        # Format and send
        message = self._format_quote(row)
        await channel.send_message(message)
    
    async def _handle_search(self, channel: Channel, query: str):
        """Search quotes by text."""
        if not query.strip():
            await channel.send_message("❌ Please provide search text")
            return
        
        # Query database (case-insensitive search)
        cursor = self.db.cursor()
        cursor.execute(
            '''
            SELECT id, text, added_by, added_at 
            FROM quotes 
            WHERE text LIKE ? 
            ORDER BY added_at DESC 
            LIMIT ?
            ''',
            (f'%{query}%', self.search_result_limit)
        )
        rows = cursor.fetchall()
        
        if not rows:
            await channel.send_message(f'No quotes found matching "{query}"')
            return
        
        # Format results
        await channel.send_message(f"Found {len(rows)} quote(s):")
        for row in rows:
            preview = row['text']
            if len(preview) > self.preview_length:
                preview = preview[:self.preview_length] + "..."
            
            # Format time
            time_ago = self._format_time_ago(row['added_at'])
            
            await channel.send_message(
                f"  #{row['id']}: \"{preview}\" ({row['added_by']}, {time_ago})"
            )
    
    async def _handle_stats(self, channel: Channel):
        """Show quote database statistics."""
        cursor = self.db.cursor()
        
        # Total quotes
        cursor.execute('SELECT COUNT(*) as count FROM quotes')
        total = cursor.fetchone()['count']
        
        # Unique contributors
        cursor.execute('SELECT COUNT(DISTINCT added_by) as count FROM quotes')
        contributors = cursor.fetchone()['count']
        
        # Most recent quote
        cursor.execute(
            'SELECT text, added_by, added_at FROM quotes ORDER BY added_at DESC LIMIT 1'
        )
        recent = cursor.fetchone()
        
        # Most active contributor
        cursor.execute(
            '''
            SELECT added_by, COUNT(*) as count 
            FROM quotes 
            GROUP BY added_by 
            ORDER BY count DESC 
            LIMIT 1
            '''
        )
        top_contributor = cursor.fetchone()
        
        # Format message
        message = "📊 Quote Database Stats:\n"
        message += f"  Total quotes: {total}\n"
        message += f"  Contributors: {contributors} users\n"
        
        if recent:
            preview = recent['text']
            if len(preview) > 30:
                preview = preview[:30] + "..."
            time_ago = self._format_time_ago(recent['added_at'])
            message += f"  Most recent: \"{preview}\" by {recent['added_by']} ({time_ago})\n"
        
        if top_contributor:
            message += f"  Most active: {top_contributor['added_by']} ({top_contributor['count']} quotes)"
        
        await channel.send_message(message)
    
    async def _handle_help(self, channel: Channel):
        """Show command help."""
        await channel.send_message("Quote Database Commands:")
        await channel.send_message("  !quote add <text> - Add a quote")
        await channel.send_message("  !quote get <id> - Get quote by ID")
        await channel.send_message("  !quote random - Get random quote")
        await channel.send_message("  !quote search <text> - Search quotes")
        await channel.send_message("  !quote stats - Show statistics")
    
    def _format_quote(self, row: sqlite3.Row) -> str:
        """Format a quote for display."""
        time_ago = self._format_time_ago(row['added_at'])
        return (
            f"Quote #{row['id']} (added by {row['added_by']} {time_ago}):\n"
            f"  \"{row['text']}\""
        )
    
    def _format_time_ago(self, timestamp: str) -> str:
        """Format timestamp as relative time."""
        dt = datetime.fromisoformat(timestamp)
        now = datetime.now()
        delta = now - dt
        
        seconds = delta.total_seconds()
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    
    async def _find_similar_quotes(self, text: str) -> Optional[tuple]:
        """
        Find similar quotes using fuzzy matching.
        
        Returns:
            Tuple of (id, text) if similar quote found, None otherwise
        """
        cursor = self.db.cursor()
        cursor.execute('SELECT id, text FROM quotes')
        
        for row in cursor.fetchall():
            similarity = SequenceMatcher(None, text.lower(), row['text'].lower()).ratio()
            if similarity >= self.duplicate_similarity_threshold:
                return (row['id'], row['text'])
        
        return None
```

## Testing Strategy

### Unit Tests

```python
"""Tests for quote database plugin."""

import pytest
import sqlite3
from plugins.quote_db.plugin import QuoteDBPlugin


@pytest.mark.asyncio
async def test_add_quote(plugin, mock_channel, mock_user):
    """Test adding a quote."""
    await plugin._handle_add(mock_channel, mock_user, "Test quote")
    
    # Verify quote was added
    cursor = plugin.db.cursor()
    cursor.execute('SELECT text FROM quotes WHERE text = ?', ("Test quote",))
    row = cursor.fetchone()
    
    assert row is not None
    assert row['text'] == "Test quote"


@pytest.mark.asyncio
async def test_get_quote(plugin, mock_channel):
    """Test retrieving a quote by ID."""
    # Add a quote first
    cursor = plugin.db.cursor()
    cursor.execute(
        'INSERT INTO quotes (text, added_by) VALUES (?, ?)',
        ("Test quote", "testuser")
    )
    plugin.db.commit()
    quote_id = cursor.lastrowid
    
    # Retrieve it
    await plugin._handle_get(mock_channel, str(quote_id))
    
    # Verify response
    assert "Test quote" in mock_channel.last_message


@pytest.mark.asyncio
async def test_search_quotes(plugin, mock_channel):
    """Test searching quotes."""
    # Add test quotes
    cursor = plugin.db.cursor()
    cursor.execute('INSERT INTO quotes (text, added_by) VALUES (?, ?)', ("Funny thing", "user1"))
    cursor.execute('INSERT INTO quotes (text, added_by) VALUES (?, ?)', ("Another funny", "user2"))
    plugin.db.commit()
    
    # Search
    await plugin._handle_search(mock_channel, "funny")
    
    # Should find both
    assert "Found 2" in mock_channel.last_message


@pytest.mark.asyncio
async def test_duplicate_detection(plugin, mock_channel, mock_user):
    """Test that duplicate quotes are detected."""
    # Add original quote
    await plugin._handle_add(mock_channel, mock_user, "This is a test")
    
    # Try to add duplicate
    await plugin._handle_add(mock_channel, mock_user, "This is a test")
    
    # Should be rejected
    assert "Similar quote" in mock_channel.last_message
```

### Hot Reload Test

**Critical:** This plugin must maintain database across reloads!

1. Add quotes:
   ```
   !quote add First quote
   !quote add Second quote
   ```

2. Edit `plugin.py` (change MAX_QUOTE_LENGTH)

3. Save file (plugin should reload)

4. Verify quotes still exist:
   ```
   !quote get 1
   !quote random
   ```

5. Verify new config applied:
   ```
   !quote add [very long quote matching new limit]
   ```

**Success criteria:** Quotes persist across reload, new config active.

## Architecture Validation

This plugin validates:

- ✅ **Storage adapter:** Uses `get_storage_path()`
- ✅ **Database persistence:** SQLite with schema
- ✅ **Hot reload:** Data survives plugin reload
- ✅ **Configuration:** Loads from config.json
- ✅ **Multiple commands:** Subcommand routing pattern
- ✅ **Error handling:** Validates input, handles not found
- ✅ **Logging:** Uses `self.logger`

## Implementation Steps

### Step 1: Create Plugin Structure (15 minutes)

1. Create directory and files
2. Create config.json with defaults

### Step 2: Database Setup (45 minutes)

1. Implement `_init_database()`
2. Define schema
3. Add indexes
4. Test connection

### Step 3: Command Handlers (2 hours)

1. Implement subcommand routing
2. Implement `_handle_add()`
3. Implement `_handle_get()`
4. Implement `_handle_random()`
5. Implement `_handle_search()`
6. Implement `_handle_stats()`
7. Implement `_handle_help()`

### Step 4: Helpers (30 minutes)

1. Implement `_format_quote()`
2. Implement `_format_time_ago()`
3. Implement `_find_similar_quotes()`

### Step 5: Testing (30 minutes)

1. Unit tests
2. Integration tests
3. Hot reload testing
4. Manual testing

**Total:** ~4 hours

---

**Estimated Implementation:** 4 hours  
**Lines of Code:** ~400  
**External Dependencies:** None (uses stdlib sqlite3)  
**Architecture Features Validated:** 7/16
