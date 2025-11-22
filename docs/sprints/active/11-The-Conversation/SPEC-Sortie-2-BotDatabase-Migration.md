# Technical Specification: BotDatabase SQLAlchemy Migration

**Sprint**: Sprint 11 "The Conversation"  
**Sortie**: 2 of 4  
**Status**: Ready for Implementation  
**Estimated Effort**: 6-8 hours  
**Dependencies**: Sortie 1 complete (ORM models, Alembic setup)  
**Blocking**: Sortie 3 (PostgreSQL support), Sortie 4 (documentation)  

---

## Overview

**Purpose**: Migrate `common/database.py` from raw sqlite3 queries to SQLAlchemy ORM, making the codebase database-agnostic and enabling PostgreSQL support. This sortie refactors all 38 methods in BotDatabase to use async SQLAlchemy sessions and ORM queries.

**Scope**: 
- Replace `sqlite3` imports with `sqlalchemy` async engine
- Convert all 38 methods from raw SQL to ORM queries
- Implement async session management
- Add connection pooling and session lifecycle
- Maintain 100% backward compatibility (method signatures unchanged)
- Keep all existing tests passing (1,198 tests)

**Non-Goals**: 
- PostgreSQL testing (Sortie 3)
- Schema changes (already done in Sortie 1)
- Performance optimization (future sprint)
- Breaking API changes (keep method signatures)
- Foreign key relationships (keep simple for v0.6.0)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: BotDatabase MUST use SQLAlchemy async engine  
**FR-002**: All 38 methods MUST be converted to ORM queries  
**FR-003**: Method signatures MUST remain unchanged (backward compatibility)  
**FR-004**: All 1,198 existing tests MUST pass  
**FR-005**: Connection pooling MUST be implemented  
**FR-006**: Session lifecycle MUST be properly managed (no leaks)  
**FR-007**: Error handling MUST match sqlite3 behavior  
**FR-008**: Logging MUST maintain same verbosity/format  

### 1.2 Non-Functional Requirements

**NFR-001**: Zero downtime migration (config change only)  
**NFR-002**: Performance parity with sqlite3 (±10%)  
**NFR-003**: Memory usage comparable to sqlite3  
**NFR-004**: Code maintainability improved (ORM vs raw SQL)  
**NFR-005**: Database URL configurable via config.json  

---

## 2. Problem Statement

### 2.1 Current Implementation Issues

**File**: `common/database.py` (938 lines)  
**Database**: sqlite3 (synchronous, SQLite-only)

```python
import sqlite3

class BotDatabase:
    def __init__(self, db_path='bot_data.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        # ... raw SQL queries everywhere ...
    
    def get_user_stats(self, username):
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT * FROM user_stats WHERE username = ?',
            (username,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
```

**Problems**:
1. **SQLite-Locked**: Hardcoded to SQLite, can't use PostgreSQL
2. **Synchronous**: All operations blocking (no async/await)
3. **No Pooling**: Single connection (bottleneck for concurrent access)
4. **Fragile SQL**: 140+ lines of raw SQL strings (typo-prone)
5. **No Type Safety**: Queries return generic Row objects

### 2.2 Target SQLAlchemy Architecture

**File**: `common/database.py` (UPDATED - ~800 lines)  
**Database**: SQLAlchemy (async, multi-database)

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import select
from common.models import UserStats

class BotDatabase:
    def __init__(self, database_url='sqlite+aiosqlite:///bot_data.db'):
        self.engine = create_async_engine(database_url, echo=False)
        self.session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def get_user_stats(self, username):
        async with self.session_factory() as session:
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()
            return {
                'username': user.username,
                'first_seen': user.first_seen,
                # ... type-safe access ...
            } if user else None
```

**Benefits**:
- ✅ Database-agnostic: SQLite, PostgreSQL, MySQL
- ✅ Async: Non-blocking operations
- ✅ Pooled: Connection pooling built-in
- ✅ Type-safe: ORM models with type hints
- ✅ Maintainable: Clear, readable code

---

## 3. Detailed Design

### 3.1 Database URL Configuration

**File**: `config.json`  
**New Field**: `database_url` (replaces `database` path)

**v0.5.0 (Old)**:
```json
{
  "database": "bot_data.db",
  "channel": "examplechannel",
  "server": "https://cytu.be"
}
```

**v0.6.0 (New)**:
```json
{
  "database_url": "sqlite+aiosqlite:///bot_data.db",
  "channel": "examplechannel",
  "server": "https://cytu.be"
}
```

**Backward Compatibility** (Sortie 2 maintains):
```python
# Load config
config = load_config()

# Support both old and new formats
if 'database_url' in config:
    db_url = config['database_url']
elif 'database' in config:
    # Convert old path to new URL
    db_path = config['database']
    db_url = f'sqlite+aiosqlite:///{db_path}'
else:
    db_url = 'sqlite+aiosqlite:///bot_data.db'
```

**PostgreSQL Example** (Sortie 3):
```json
{
  "database_url": "postgresql+asyncpg://rosey:password@localhost/rosey_db"
}
```

### 3.2 BotDatabase Architecture

**Class Structure**:
```
BotDatabase
├── __init__(database_url)               # Engine + session factory
├── connect() [async]                    # New in v0.6.0 (Sprint 10)
├── close() [async]                      # New in v0.6.0 (Sprint 10)
├── _get_session() [context manager]     # Session lifecycle
├── _create_tables() [async]             # Alembic handles this now
│
├── User Tracking (8 methods)
│   ├── user_joined(username)
│   ├── user_left(username)
│   ├── user_chat_message(username, message)
│   ├── get_user_stats(username)
│   ├── get_top_chatters(limit)
│   └── get_total_users_seen()
│
├── Audit Logging (1 method)
│   └── log_user_action(username, action_type, details)
│
├── Channel Stats (3 methods)
│   ├── update_high_water_mark(users, connected)
│   ├── get_high_water_mark()
│   └── get_high_water_mark_connected()
│
├── Historical Tracking (3 methods)
│   ├── log_user_count(chat_users, connected_users)
│   ├── get_user_count_history(hours)
│   └── cleanup_old_history(days)
│
├── Recent Chat (2 methods)
│   ├── get_recent_chat(limit)
│   └── get_recent_chat_since(minutes, limit)
│
├── Outbound Messages (4 methods)
│   ├── enqueue_outbound_message(message)
│   ├── get_unsent_outbound_messages(limit, max_retries)
│   ├── mark_outbound_sent(outbound_id)
│   └── mark_outbound_failed(outbound_id, error_msg, is_permanent)
│
├── Current Status (2 methods)
│   ├── update_current_status(**kwargs)
│   └── get_current_status()
│
└── API Tokens (3 methods)
    ├── generate_api_token(description)
    ├── validate_api_token(token)
    └── revoke_api_token(token)

Total: 38 methods to migrate
```

### 3.3 Session Management Pattern

**Pattern**: Async context manager for session lifecycle

```python
from contextlib import asynccontextmanager

class BotDatabase:
    @asynccontextmanager
    async def _get_session(self):
        """
        Get async session from pool.
        
        Usage:
            async with self._get_session() as session:
                result = await session.execute(...)
                await session.commit()
        
        Automatically handles:
        - Session acquisition from pool
        - Transaction commit on success
        - Rollback on exception
        - Session cleanup
        """
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Usage in Methods**:
```python
async def user_joined(self, username):
    """Record a user joining the channel"""
    now = int(time.time())
    
    async with self._get_session() as session:
        # Check if user exists
        result = await session.execute(
            select(UserStats).where(UserStats.username == username)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update existing
            user.last_seen = now
            user.current_session_start = now
        else:
            # Create new
            user = UserStats(
                username=username,
                first_seen=now,
                last_seen=now,
                current_session_start=now,
                total_chat_lines=0,
                total_time_connected=0
            )
            session.add(user)
        
        # Commit handled by context manager
```

---

## 4. Implementation Changes

### Change 1: Update BotDatabase __init__ (Engine Setup)

**File**: `common/database.py`  
**Lines**: 8-22 (current __init__)  

**Current Code**:
```python
class BotDatabase:
    """Database for tracking bot state and user statistics"""

    def __init__(self, db_path='bot_data.db'):
        """Initialize database connection and create tables

        Args:
            db_path: Path to SQLite database file
        """
        self.logger = logging.getLogger(__name__)
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_tables()

    def _connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.logger.info('Connected to database: %s', self.db_path)
```

**New Code**:
```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, update, delete, func
from common.models import (
    Base, UserStats, UserAction, ChannelStats, UserCountHistory,
    RecentChat, CurrentStatus, OutboundMessage, ApiToken
)

class BotDatabase:
    """
    Database for tracking bot state and user statistics.
    
    Uses SQLAlchemy ORM with async support for database operations.
    Supports SQLite (dev/test) and PostgreSQL (production).
    
    Attributes:
        engine: SQLAlchemy async engine
        session_factory: Factory for creating async sessions
        database_url: Database connection URL
    """

    def __init__(self, database_url='sqlite+aiosqlite:///bot_data.db'):
        """
        Initialize database engine and session factory.
        
        Args:
            database_url: SQLAlchemy database URL
                SQLite: 'sqlite+aiosqlite:///path/to/db.db'
                PostgreSQL: 'postgresql+asyncpg://user:pass@host/db'
        
        Note:
            Tables are created via Alembic migrations, not here.
            Call connect() after initialization to ensure tables exist.
        """
        self.logger = logging.getLogger(__name__)
        self.database_url = database_url
        
        # Create async engine with connection pooling
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set True to log all SQL queries
            pool_pre_ping=True,  # Verify connections before use
            pool_size=5,  # Connection pool size
            max_overflow=10,  # Max overflow connections
        )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
        )
        
        self.logger.info('Initialized database: %s', database_url)
    
    async def connect(self):
        """
        Connect to database and ensure tables exist.
        
        This is a no-op in v0.6.0 (tables created via Alembic),
        but maintained for compatibility with Sprint 10 tests.
        """
        # Verify connection by executing simple query
        async with self._get_session() as session:
            result = await session.execute(select(func.count()).select_from(UserStats))
            count = result.scalar()
            self.logger.info('Database connection verified (%d users)', count)
    
    async def close(self):
        """
        Close database engine and all pooled connections.
        
        Should be called during application shutdown.
        """
        await self.engine.dispose()
        self.logger.info('Database engine closed')
    
    @asynccontextmanager
    async def _get_session(self):
        """
        Get async session from pool (context manager).
        
        Automatically handles commit/rollback/cleanup.
        
        Usage:
            async with self._get_session() as session:
                result = await session.execute(select(...))
                # Commit happens automatically on success
        """
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

**Rationale**: 
- Replaces sqlite3 with SQLAlchemy async engine
- Connection pooling for concurrent access
- Maintains compatibility with Sprint 10 async methods
- Alembic handles table creation (removes _create_tables)

---

### Change 2: Migrate user_joined() Method

**File**: `common/database.py`  
**Current Lines**: 207-234  

**Current Code** (sqlite3):
```python
    def user_joined(self, username):
        """Record a user joining the channel

        Args:
            username: Username that joined
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Check if user exists
        cursor.execute('SELECT username FROM user_stats WHERE username = ?',
                       (username,))
        exists = cursor.fetchone() is not None

        if exists:
            # Update existing user - start new session
            cursor.execute('''
                UPDATE user_stats
                SET last_seen = ?,
                    current_session_start = ?
                WHERE username = ?
            ''', (now, now, username))
        else:
            # New user - create entry
            cursor.execute('''
                INSERT INTO user_stats
                (username, first_seen, last_seen, current_session_start)
                VALUES (?, ?, ?, ?)
            ''', (username, now, now, now))

        self.conn.commit()
```

**New Code** (SQLAlchemy ORM):
```python
    async def user_joined(self, username):
        """
        Record a user joining the channel.

        Args:
            username: Username that joined
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Check if user exists
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                # Update existing user - start new session
                user.last_seen = now
                user.current_session_start = now
            else:
                # New user - create entry
                user = UserStats(
                    username=username,
                    first_seen=now,
                    last_seen=now,
                    current_session_start=now,
                    total_chat_lines=0,
                    total_time_connected=0
                )
                session.add(user)
            
            # Commit handled by context manager
```

**Rationale**: Type-safe ORM query, async/await pattern

---

### Change 3: Migrate user_left() Method

**File**: `common/database.py`  
**Current Lines**: 236-265  

**Current Code**:
```python
    def user_left(self, username):
        """Record a user leaving the channel

        Args:
            username: Username that left
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Get session start time
        cursor.execute('''
            SELECT current_session_start, total_time_connected
            FROM user_stats WHERE username = ?
        ''', (username,))

        row = cursor.fetchone()
        if row and row['current_session_start']:
            session_duration = now - row['current_session_start']
            new_total = row['total_time_connected'] + session_duration

            # Update user stats
            cursor.execute('''
                UPDATE user_stats
                SET last_seen = ?,
                    total_time_connected = ?,
                    current_session_start = NULL
                WHERE username = ?
            ''', (now, new_total, username))

            self.conn.commit()
```

**New Code**:
```python
    async def user_left(self, username):
        """
        Record a user leaving the channel.

        Args:
            username: Username that left
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Get user
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()

            if user and user.current_session_start:
                # Calculate session duration
                session_duration = now - user.current_session_start
                
                # Update stats
                user.last_seen = now
                user.total_time_connected += session_duration
                user.current_session_start = None
                
                # Commit handled by context manager
```

**Rationale**: ORM attribute access, clearer logic

---

### Change 4: Migrate user_chat_message() Method

**File**: `common/database.py`  
**Current Lines**: 267-298  

**Current Code**:
```python
    def user_chat_message(self, username, message=None):
        """Increment chat message count for user and optionally log message

        Args:
            username: Username that sent a message
            message: Optional message text to store in recent_chat
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Update user stats
        cursor.execute('''
            UPDATE user_stats
            SET total_chat_lines = total_chat_lines + 1,
                last_seen = ?
            WHERE username = ?
        ''', (now, username))

        # Store in recent chat if message provided
        if message and username and username.lower() != 'server':
            cursor.execute('''
                INSERT INTO recent_chat (timestamp, username, message)
                VALUES (?, ?, ?)
            ''', (now, username, message))

            # Cleanup old messages
            retention_hours = 150
            cutoff = int(time.time()) - (retention_hours * 3600)
            cursor.execute('''
                DELETE FROM recent_chat
                WHERE timestamp < ?
            ''', (cutoff,))

        self.conn.commit()
```

**New Code**:
```python
    async def user_chat_message(self, username, message=None):
        """
        Increment chat message count for user and optionally log message.

        Args:
            username: Username that sent a message
            message: Optional message text to store in recent_chat
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Update user stats (increment counter)
            await session.execute(
                update(UserStats)
                .where(UserStats.username == username)
                .values(
                    total_chat_lines=UserStats.total_chat_lines + 1,
                    last_seen=now
                )
            )

            # Store in recent chat if message provided
            if message and username and username.lower() != 'server':
                # Add message
                chat = RecentChat(
                    timestamp=now,
                    username=username,
                    message=message
                )
                session.add(chat)

                # Cleanup old messages (retention: 150 hours)
                retention_hours = 150
                cutoff = now - (retention_hours * 3600)
                await session.execute(
                    delete(RecentChat).where(RecentChat.timestamp < cutoff)
                )
            
            # Commit handled by context manager
```

**Rationale**: ORM update() with expressions, bulk operations

---

### Change 5: Migrate log_user_action() Method

**File**: `common/database.py`  
**Current Lines**: 305-320  

**Current Code**:
```python
    def log_user_action(self, username, action_type, details=None):
        """Log a user action (PM command, moderation, etc.)

        Args:
            username: Username performing the action
            action_type: Type of action (e.g., 'pm_command', 'kick')
            details: Optional details about the action
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        cursor.execute('''
            INSERT INTO user_actions (timestamp, username, action_type, details)
            VALUES (?, ?, ?, ?)
        ''', (now, username, action_type, details))

        self.conn.commit()
```

**New Code**:
```python
    async def log_user_action(self, username, action_type, details=None):
        """
        Log a user action (PM command, moderation, etc.).

        Args:
            username: Username performing the action
            action_type: Type of action (e.g., 'pm_command', 'kick')
            details: Optional details about the action
        """
        now = int(time.time())

        async with self._get_session() as session:
            action = UserAction(
                timestamp=now,
                username=username,
                action_type=action_type,
                details=details
            )
            session.add(action)
            # Commit handled by context manager
```

**Rationale**: Simple ORM insert, type-safe

---

### Change 6: Migrate update_high_water_mark() Method

**File**: `common/database.py`  
**Current Lines**: 321-370  

**Current Code**:
```python
    def update_high_water_mark(self, current_user_count,
                               current_connected_count=None):
        """Update high water mark if current count exceeds it

        Args:
            current_user_count: Current number of chat users
            current_connected_count: Current number of connected viewers
        """
        cursor = self.conn.cursor()
        now = int(time.time())

        # Initialize if not exists
        cursor.execute('SELECT id FROM channel_stats WHERE id = 1')
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO channel_stats (id, max_users, last_updated)
                VALUES (1, 0, ?)
            ''', (now,))

        # Get current max
        cursor.execute('SELECT max_users, max_connected FROM channel_stats WHERE id = 1')
        row = cursor.fetchone()
        current_max = row['max_users'] if row else 0
        current_max_connected = row['max_connected'] if row and row['max_connected'] else 0

        # Update if exceeded
        updates = ['last_updated = ?']
        params = [now]

        if current_user_count > current_max:
            updates.append('max_users = ?')
            updates.append('max_users_timestamp = ?')
            params.extend([current_user_count, now])

        if current_connected_count and current_connected_count > current_max_connected:
            updates.append('max_connected = ?')
            updates.append('max_connected_timestamp = ?')
            params.extend([current_connected_count, now])

        query = f'UPDATE channel_stats SET {", ".join(updates)} WHERE id = 1'
        cursor.execute(query, params)
        self.conn.commit()
```

**New Code**:
```python
    async def update_high_water_mark(self, current_user_count,
                                    current_connected_count=None):
        """
        Update high water mark if current count exceeds it.

        Args:
            current_user_count: Current number of chat users
            current_connected_count: Current number of connected viewers
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Get or create channel stats (singleton)
            result = await session.execute(
                select(ChannelStats).where(ChannelStats.id == 1)
            )
            stats = result.scalar_one_or_none()

            if not stats:
                # Initialize
                stats = ChannelStats(
                    id=1,
                    max_users=0,
                    last_updated=now
                )
                session.add(stats)

            # Update high water marks
            if current_user_count > stats.max_users:
                stats.max_users = current_user_count
                stats.max_users_timestamp = now

            if current_connected_count and current_connected_count > (stats.max_connected or 0):
                stats.max_connected = current_connected_count
                stats.max_connected_timestamp = now

            stats.last_updated = now
            # Commit handled by context manager
```

**Rationale**: ORM singleton pattern, cleaner logic

---

### Change 7: Migrate Query Methods (8 methods)

**Methods to Convert** (same pattern):
- `get_user_stats(username)` → ORM select
- `get_high_water_mark()` → ORM select singleton
- `get_high_water_mark_connected()` → ORM select singleton
- `get_top_chatters(limit)` → ORM select + order_by + limit
- `get_total_users_seen()` → ORM select count
- `get_user_count_history(hours)` → ORM select + filter + order_by
- `get_recent_chat(limit)` → ORM select + order_by + limit
- `get_recent_chat_since(minutes, limit)` → ORM select + filter

**Example** (get_user_stats):

**Current Code**:
```python
    def get_user_stats(self, username):
        """Get statistics for a specific user"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM user_stats WHERE username = ?
        ''', (username,))
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None
```

**New Code**:
```python
    async def get_user_stats(self, username):
        """
        Get statistics for a specific user.
        
        Args:
            username: Username to look up
        
        Returns:
            dict: User stats or None if not found
        """
        async with self._get_session() as session:
            result = await session.execute(
                select(UserStats).where(UserStats.username == username)
            )
            user = result.scalar_one_or_none()

            if user:
                return {
                    'username': user.username,
                    'first_seen': user.first_seen,
                    'last_seen': user.last_seen,
                    'total_chat_lines': user.total_chat_lines,
                    'total_time_connected': user.total_time_connected,
                    'current_session_start': user.current_session_start
                }
            return None
```

**Pattern for All Query Methods**:
1. Wrap in `async with self._get_session()`
2. Use `select(Model).where(...)` for queries
3. Use `result.scalar_one_or_none()` for single results
4. Use `result.scalars().all()` for multiple results
5. Convert ORM objects to dicts (maintain API compatibility)

---

### Change 8: Migrate Outbound Message Methods (4 methods)

**Methods**:
- `enqueue_outbound_message(message)` → ORM insert
- `get_unsent_outbound_messages(limit, max_retries)` → ORM complex query
- `mark_outbound_sent(outbound_id)` → ORM update
- `mark_outbound_failed(outbound_id, error_msg, is_permanent)` → ORM update

**Example** (get_unsent_outbound_messages - complex query):

**Current Code**:
```python
    def get_unsent_outbound_messages(self, limit=50, max_retries=3):
        """Fetch unsent outbound messages ready for sending"""
        cursor = self.conn.cursor()
        now = int(time.time())

        cursor.execute('''
            SELECT id, timestamp, message, retry_count, last_error
            FROM outbound_messages
            WHERE sent = 0
              AND retry_count < ?
              AND (retry_count = 0 OR timestamp + (1 << retry_count) * 60 <= ?)
            ORDER BY timestamp ASC
            LIMIT ?
        ''', (max_retries, now, limit))
        return [dict(row) for row in cursor.fetchall()]
```

**New Code**:
```python
    async def get_unsent_outbound_messages(self, limit=50, max_retries=3):
        """
        Fetch unsent outbound messages ready for sending.
        
        Uses exponential backoff: 2^retry_count minutes delay.
        
        Args:
            limit: Max messages to fetch
            max_retries: Maximum retry attempts
        
        Returns:
            list of dicts: Messages ready to send
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Complex query with bitshift expression
            from sqlalchemy import literal_column
            
            result = await session.execute(
                select(OutboundMessage)
                .where(
                    OutboundMessage.sent == False,
                    OutboundMessage.retry_count < max_retries,
                    (OutboundMessage.retry_count == 0) |
                    (OutboundMessage.timestamp + 
                     literal_column(f'(1 << retry_count) * 60') <= now)
                )
                .order_by(OutboundMessage.timestamp.asc())
                .limit(limit)
            )
            messages = result.scalars().all()

            return [
                {
                    'id': msg.id,
                    'timestamp': msg.timestamp,
                    'message': msg.message,
                    'retry_count': msg.retry_count,
                    'last_error': msg.error_message
                }
                for msg in messages
            ]
```

**Rationale**: Complex query with bitshift, maintains exact logic

---

### Change 9: Migrate Status and Token Methods (5 methods)

**Methods**:
- `update_current_status(**kwargs)` → ORM dynamic update
- `get_current_status()` → ORM select singleton
- `generate_api_token(description)` → ORM insert + secrets
- `validate_api_token(token)` → ORM select + update
- `revoke_api_token(token)` → ORM update with LIKE

**Example** (update_current_status - dynamic fields):

**Current Code**:
```python
    def update_current_status(self, **kwargs):
        """Update current bot status"""
        cursor = self.conn.cursor()

        fields = []
        values = []

        for key, value in kwargs.items():
            if key in ['bot_name', 'bot_rank', ...]:
                fields.append(f'{key} = ?')
                values.append(value)

        if not fields:
            return

        fields.append('last_updated = ?')
        values.append(int(time.time()))

        query = f'UPDATE current_status SET {", ".join(fields)} WHERE id = 1'
        cursor.execute(query, values)
        self.conn.commit()
```

**New Code**:
```python
    async def update_current_status(self, **kwargs):
        """
        Update current bot status.
        
        Args:
            **kwargs: Status fields to update (bot_name, bot_rank, etc.)
        """
        now = int(time.time())

        async with self._get_session() as session:
            # Get or create status (singleton)
            result = await session.execute(
                select(CurrentStatus).where(CurrentStatus.id == 1)
            )
            status = result.scalar_one_or_none()

            if not status:
                status = CurrentStatus(id=1, last_updated=now)
                session.add(status)

            # Update fields dynamically
            allowed_fields = [
                'bot_name', 'bot_rank', 'bot_afk', 'channel_name',
                'current_chat_users', 'current_connected_users',
                'playlist_items', 'current_media_title',
                'current_media_duration', 'bot_start_time', 'bot_connected'
            ]

            for key, value in kwargs.items():
                if key in allowed_fields and hasattr(status, key):
                    setattr(status, key, value)

            status.last_updated = now
            # Commit handled by context manager
```

**Rationale**: ORM setattr for dynamic updates, type-safe

---

### Change 10: Update Import Statements

**File**: `common/database.py`  
**Lines**: 1-6  

**Current Imports**:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite database for bot state persistence and statistics tracking"""
import logging
import sqlite3
import time
```

**New Imports**:
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database for bot state persistence and statistics tracking.

Uses SQLAlchemy ORM with async support.
Supports SQLite (dev/test) and PostgreSQL (production).
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy import select, update, delete, func, literal_column
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)

from common.models import (
    Base,
    UserStats,
    UserAction,
    ChannelStats,
    UserCountHistory,
    RecentChat,
    CurrentStatus,
    OutboundMessage,
    ApiToken
)
```

**Rationale**: Replace sqlite3 with SQLAlchemy imports

---

## 5. Testing Strategy

### 5.1 Existing Tests (Must Pass)

**Test Count**: 1,198 tests (all must pass)  
**Test Suites**:
- `tests/unit/test_database.py` - Database unit tests
- `tests/integration/test_bot_integration.py` - Bot integration tests
- `tests/integration/test_nats_integration.py` - NATS integration tests

**Test Execution**:
```bash
# Run all tests
pytest -v

# Expected: 1,198 passed, 0 failed
```

**Key Test Coverage**:
- User tracking (join/leave/chat)
- Audit logging
- High water marks
- Historical data
- Recent chat
- Outbound message queue
- Current status
- API tokens

### 5.2 New Unit Tests (ORM-Specific)

**File**: `tests/unit/test_database_orm.py` (NEW)

**Test Cases**:
```python
import pytest
from common.database import BotDatabase

@pytest.mark.asyncio
async def test_database_initialization():
    """Test async database initialization"""
    db = BotDatabase('sqlite+aiosqlite:///:memory:')
    await db.connect()
    
    # Should succeed without errors
    status = await db.get_current_status()
    assert status is None or isinstance(status, dict)
    
    await db.close()

@pytest.mark.asyncio
async def test_user_lifecycle():
    """Test complete user lifecycle (join → chat → leave)"""
    db = BotDatabase('sqlite+aiosqlite:///:memory:')
    await db.connect()
    
    # User joins
    await db.user_joined('TestUser')
    
    # Check stats
    stats = await db.get_user_stats('TestUser')
    assert stats['username'] == 'TestUser'
    assert stats['total_chat_lines'] == 0
    
    # User chats
    await db.user_chat_message('TestUser', 'Hello world')
    
    # Check updated stats
    stats = await db.get_user_stats('TestUser')
    assert stats['total_chat_lines'] == 1
    
    # User leaves
    await db.user_left('TestUser')
    
    # Check session ended
    stats = await db.get_user_stats('TestUser')
    assert stats['current_session_start'] is None
    
    await db.close()

@pytest.mark.asyncio
async def test_session_cleanup():
    """Test session cleanup on errors"""
    db = BotDatabase('sqlite+aiosqlite:///:memory:')
    await db.connect()
    
    # Force an error (invalid username type)
    with pytest.raises(Exception):
        await db.user_joined(12345)  # Should be string
    
    # Database should still be functional
    await db.user_joined('ValidUser')
    stats = await db.get_user_stats('ValidUser')
    assert stats is not None
    
    await db.close()

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent database operations"""
    import asyncio
    
    db = BotDatabase('sqlite+aiosqlite:///:memory:')
    await db.connect()
    
    # Simulate 10 concurrent user joins
    tasks = [db.user_joined(f'User{i}') for i in range(10)]
    await asyncio.gather(*tasks)
    
    # Verify all users created
    total = await db.get_total_users_seen()
    assert total == 10
    
    await db.close()
```

**Coverage Target**: 95%+ (all new session management code)

---

### 5.3 Integration Tests (Database Service)

**File**: `tests/integration/test_database_service_migration.py` (NEW)

**Test Cases**:
```python
import pytest
from common.database_service import DatabaseService

@pytest.mark.asyncio
async def test_database_service_migration():
    """Test DatabaseService with SQLAlchemy backend"""
    config = {
        'database_url': 'sqlite+aiosqlite:///:memory:',
        'nats_url': 'nats://localhost:4222'
    }
    
    service = DatabaseService(config)
    await service.start()
    
    # Test NATS request/reply
    # (Existing integration tests should pass)
    
    await service.stop()

@pytest.mark.asyncio
async def test_stats_command_migration():
    """Test stats command via NATS with ORM"""
    # (Tests from Sprint 10 Sortie 2 should pass)
    pass
```

**Coverage**: All existing integration tests must pass

---

### 5.4 Performance Benchmarks

**File**: `tests/performance/test_orm_performance.py` (NEW)

**Benchmarks**:
```python
import pytest
import time
from common.database import BotDatabase

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_user_joined_performance(benchmark):
    """Benchmark user_joined() operation"""
    db = BotDatabase('sqlite+aiosqlite:///:memory:')
    await db.connect()
    
    async def operation():
        await db.user_joined(f'User{time.time()}')
    
    result = await benchmark.pedantic(operation, iterations=100, rounds=10)
    
    # Should complete in <5ms per operation
    assert result.stats.mean < 0.005
    
    await db.close()

@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_query_performance(benchmark):
    """Benchmark query operations"""
    db = BotDatabase('sqlite+aiosqlite:///:memory:')
    await db.connect()
    
    # Setup: 1000 users
    for i in range(1000):
        await db.user_joined(f'User{i}')
    
    async def operation():
        await db.get_top_chatters(10)
    
    result = await benchmark.pedantic(operation, iterations=100, rounds=10)
    
    # Should complete in <10ms
    assert result.stats.mean < 0.010
    
    await db.close()
```

**Performance Targets**:
- Single insert: <5ms (SQLite) / <10ms (PostgreSQL)
- Simple query: <5ms (SQLite) / <10ms (PostgreSQL)
- Complex query: <10ms (SQLite) / <20ms (PostgreSQL)
- Concurrent ops: 100+ ops/sec

---

## 6. Implementation Steps

### Phase 1: Preparation (30 minutes)

1. ✅ Review Sortie 1 deliverables (models, Alembic)
2. ✅ Create feature branch: `git checkout -b sprint-11-sortie-2-database-migration`
3. ✅ Run existing tests: `pytest -v` (baseline)
4. ✅ Document current test results (1,198 tests status)

### Phase 2: Core Migration (3-4 hours)

5. ✅ Update imports (remove sqlite3, add SQLAlchemy)
6. ✅ Replace `__init__` (engine + session factory)
7. ✅ Implement `_get_session()` context manager
8. ✅ Add `connect()` and `close()` methods
9. ✅ Migrate user tracking methods (6 methods)
    - user_joined, user_left, user_chat_message
    - get_user_stats, get_top_chatters, get_total_users_seen
10. ✅ Migrate audit logging (1 method)
    - log_user_action
11. ✅ Migrate channel stats (3 methods)
    - update_high_water_mark, get_high_water_mark, get_high_water_mark_connected
12. ✅ Test after each method: `pytest tests/unit/test_database.py -v`

### Phase 3: Advanced Migration (2-3 hours)

13. ✅ Migrate historical tracking (3 methods)
    - log_user_count, get_user_count_history, cleanup_old_history
14. ✅ Migrate recent chat (2 methods)
    - get_recent_chat, get_recent_chat_since
15. ✅ Migrate outbound messages (4 methods)
    - enqueue_outbound_message, get_unsent_outbound_messages
    - mark_outbound_sent, mark_outbound_failed
16. ✅ Migrate status and tokens (5 methods)
    - update_current_status, get_current_status
    - generate_api_token, validate_api_token, revoke_api_token
17. ✅ Test after each section: `pytest tests/unit/ -v`

### Phase 4: Testing (1-2 hours)

18. ✅ Run all unit tests: `pytest tests/unit/ -v`
19. ✅ Run all integration tests: `pytest tests/integration/ -v`
20. ✅ Run all tests: `pytest -v` (expect 1,198 passed)
21. ✅ Create new ORM tests: `tests/unit/test_database_orm.py`
22. ✅ Create performance benchmarks: `tests/performance/test_orm_performance.py`
23. ✅ Run benchmarks: `pytest tests/performance/ -v --benchmark`

### Phase 5: Integration and Cleanup (30 minutes)

24. ✅ Update config loading (support database_url)
25. ✅ Update database_service.py (if needed)
26. ✅ Test with real config: `python -m common.database`
27. ✅ Verify backward compatibility (old config format)
28. ✅ Run CI locally: `pytest -v --cov=common`

### Phase 6: Documentation (30 minutes)

29. ✅ Update docstrings (async, SQLAlchemy references)
30. ✅ Update ARCHITECTURE.md (database section)
31. ✅ Update TESTING.md (new ORM tests)
32. ✅ Update CHANGELOG.md (v0.6.0 migration notes)
33. ✅ Commit: "Sprint 11 Sortie 2: BotDatabase SQLAlchemy migration"

---

## 7. Acceptance Criteria

### 7.1 Code Migration Complete

- [ ] All 38 methods migrated to SQLAlchemy ORM
- [ ] No sqlite3 imports remaining
- [ ] All methods use async/await
- [ ] Session management via context manager
- [ ] Connection pooling configured
- [ ] Type hints maintained/improved

### 7.2 Tests Passing

- [ ] All 1,198 existing tests pass
- [ ] New ORM unit tests pass (10+ tests)
- [ ] Integration tests pass (database service)
- [ ] No test regressions
- [ ] Code coverage ≥85%

### 7.3 Performance Acceptable

- [ ] Performance benchmarks created
- [ ] Performance within ±10% of v0.5.0
- [ ] No memory leaks detected
- [ ] Connection pool tested (concurrent ops)

### 7.4 Backward Compatibility

- [ ] Method signatures unchanged
- [ ] Return types unchanged (dicts, not ORM objects)
- [ ] Old config format supported (database path)
- [ ] New config format works (database_url)
- [ ] No breaking API changes

### 7.5 Documentation Updated

- [ ] All docstrings updated (async, ORM)
- [ ] ARCHITECTURE.md updated (SQLAlchemy)
- [ ] TESTING.md updated (new tests)
- [ ] CHANGELOG.md updated (v0.6.0)

---

## 8. Deliverables

### 8.1 Code Changes

**Modified Files**:
- `common/database.py` - Migrated to SQLAlchemy ORM (~800 lines)
- `common/config.py` - Support database_url field (if needed)

**New Files**:
- `tests/unit/test_database_orm.py` - ORM-specific tests (~200 lines)
- `tests/integration/test_database_service_migration.py` - Service tests (~100 lines)
- `tests/performance/test_orm_performance.py` - Benchmarks (~150 lines)

### 8.2 Documentation

**Updated**:
- `docs/ARCHITECTURE.md` - SQLAlchemy architecture
- `docs/TESTING.md` - New test suites
- `CHANGELOG.md` - v0.6.0 migration

---

## 9. Related Issues

**Depends On**:
- Sprint 11 Sortie 1 complete (ORM models, Alembic)

**Blocks**:
- Sortie 3: PostgreSQL support testing
- Sortie 4: Documentation and deployment

**Related**:
- Sprint 10 Sortie 1: Async BotDatabase.connect()
- Sprint 11 PRD: SQLAlchemy Migration

---

## 10. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Methods Migrated | 38/38 | Code review |
| Tests Passing | 1,198/1,198 | pytest output |
| Performance | Within ±10% | Benchmark results |
| Coverage | ≥85% | pytest-cov |
| Session Leaks | 0 | Memory profiling |

---

## Appendix A: Method Migration Checklist

**User Tracking** (8 methods):
- [ ] user_joined(username)
- [ ] user_left(username)
- [ ] user_chat_message(username, message)
- [ ] get_user_stats(username)
- [ ] get_top_chatters(limit)
- [ ] get_total_users_seen()

**Audit Logging** (1 method):
- [ ] log_user_action(username, action_type, details)

**Channel Stats** (3 methods):
- [ ] update_high_water_mark(users, connected)
- [ ] get_high_water_mark()
- [ ] get_high_water_mark_connected()

**Historical Tracking** (3 methods):
- [ ] log_user_count(chat_users, connected_users)
- [ ] get_user_count_history(hours)
- [ ] cleanup_old_history(days)

**Recent Chat** (2 methods):
- [ ] get_recent_chat(limit)
- [ ] get_recent_chat_since(minutes, limit)

**Outbound Messages** (4 methods):
- [ ] enqueue_outbound_message(message)
- [ ] get_unsent_outbound_messages(limit, max_retries)
- [ ] mark_outbound_sent(outbound_id)
- [ ] mark_outbound_failed(outbound_id, error_msg, is_permanent)

**Current Status** (2 methods):
- [ ] update_current_status(**kwargs)
- [ ] get_current_status()

**API Tokens** (3 methods):
- [ ] generate_api_token(description)
- [ ] validate_api_token(token)
- [ ] revoke_api_token(token)

**Total**: 38 methods

---

## Appendix B: SQLAlchemy Query Patterns

### Pattern 1: Single Record Query
```python
async with self._get_session() as session:
    result = await session.execute(
        select(Model).where(Model.field == value)
    )
    obj = result.scalar_one_or_none()
```

### Pattern 2: Multiple Record Query
```python
async with self._get_session() as session:
    result = await session.execute(
        select(Model)
        .where(Model.field > value)
        .order_by(Model.field.desc())
        .limit(10)
    )
    objs = result.scalars().all()
```

### Pattern 3: Insert
```python
async with self._get_session() as session:
    obj = Model(field1=value1, field2=value2)
    session.add(obj)
    # Commit automatic
```

### Pattern 4: Update (Attribute)
```python
async with self._get_session() as session:
    result = await session.execute(
        select(Model).where(Model.id == id)
    )
    obj = result.scalar_one()
    obj.field = new_value
    # Commit automatic
```

### Pattern 5: Update (Bulk)
```python
async with self._get_session() as session:
    await session.execute(
        update(Model)
        .where(Model.field == value)
        .values(field2=new_value)
    )
    # Commit automatic
```

### Pattern 6: Delete
```python
async with self._get_session() as session:
    await session.execute(
        delete(Model).where(Model.field < cutoff)
    )
    # Commit automatic
```

### Pattern 7: Count
```python
async with self._get_session() as session:
    result = await session.execute(
        select(func.count()).select_from(Model)
    )
    count = result.scalar()
```

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**Author**: GitHub Copilot (Claude Sonnet 4.5)  
**Status**: Ready for Implementation ✅

**Next Steps**:
1. Review Sortie 1 deliverables (models complete?)
2. Create feature branch: `sprint-11-sortie-2-database-migration`
3. Run baseline tests: `pytest -v` (record results)
4. Start migration: Update imports and __init__
5. Migrate methods one-by-one, testing after each
6. Run full test suite: Expect 1,198 passed
7. Create new ORM tests and benchmarks
8. Commit: "Sprint 11 Sortie 2: SQLAlchemy migration complete"

---

**"You're a conversation. You got 38 methods. Each one is a dialogue between the code and the database. Let's make that conversation type-safe."** 🎬
