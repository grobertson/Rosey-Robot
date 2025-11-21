# Technical Specification: Database Service Layer with NATS

**Sprint**: Sprint 9 "The Accountant"  
**Sortie**: 3 of 6  
**Status**: Ready for Implementation  
**Estimated Effort**: 5-7 hours  
**Dependencies**: Sortie 1 (Event Normalization) MUST be complete  
**Blocking**: Sortie 4 (Bot NATS Migration), Sortie 5 (Config v2)  

---

## Overview

**Purpose**: Create `DatabaseService` wrapper around `BotDatabase` that subscribes to NATS events and handles database operations asynchronously. This enables process isolation - the database can run in a separate process from the bot.

**Scope**: Create new `common/database_service.py` that wraps existing `common/database.py` with NATS event handlers.

**Key Principle**: *"All layers communicate via NATS - no direct calls between bot/database/plugins."*

**Non-Goals**:
- Database schema changes (schema unchanged)
- Bot layer changes (Sortie 4)
- Configuration changes (Sortie 5)

---

## 1. Requirements

### 1.1 Functional Requirements

**FR-001**: DatabaseService MUST subscribe to all relevant NATS subjects  
**FR-002**: DatabaseService MUST handle both pub/sub (fire-and-forget) and request/reply (query) patterns  
**FR-003**: DatabaseService MUST wrap existing BotDatabase without modifying its implementation  
**FR-004**: DatabaseService MUST be runnable as standalone service (separate process)  
**FR-005**: DatabaseService MUST handle errors gracefully (log but don't crash)  
**FR-006**: DatabaseService MUST support graceful shutdown (cleanup subscriptions)  

### 1.2 Non-Functional Requirements

**NFR-001**: Database operations remain synchronous internally (no need to async-ify BotDatabase)  
**NFR-002**: NATS communication is asynchronous (async/await wrappers)  
**NFR-003**: Performance parity with direct calls (<5% overhead acceptable)  
**NFR-004**: Logging preserves existing database log messages  

---

## 2. Architecture

### 2.1 Component Overview

```text
┌─────────────────────────────────────────────────┐
│              NATS Event Bus                     │
└─────────────────────────────────────────────────┘
         ↑                            ↓
         │ Publishes                  │ Subscribes
         │                            │
┌────────┴─────────┐        ┌─────────┴──────────┐
│   Bot Layer      │        │ DatabaseService    │
│   (lib/bot.py)   │        │ (NEW)              │
│                  │        │                    │
│ - Publishes      │        │ - Subscribes       │
│   events to NATS │        │   to subjects      │
│                  │        │ - Handles events   │
│ - Request/reply  │        │ - Wraps BotDB      │
│   for queries    │        │ - Process isolated │
└──────────────────┘        └────────────────────┘
                                     │
                                     │ Wraps
                                     ↓
                            ┌────────────────────┐
                            │   BotDatabase      │
                            │  (UNCHANGED)       │
                            │                    │
                            │ - SQLite ops       │
                            │ - user_joined()    │
                            │ - message_logged() │
                            │ - etc.             │
                            └────────────────────┘
```

### 2.2 NATS Subject Design

**Subject Hierarchy**:

```text
rosey.db.*                        # All database operations
  ├── user.joined                 # User joined channel (pub/sub)
  ├── user.left                   # User left channel (pub/sub)
  ├── message.log                 # Log chat message (pub/sub)
  ├── stats.user_count            # Update user count stats (pub/sub)
  ├── stats.high_water            # Update high water mark (pub/sub)
  ├── status.update               # Bot status update (pub/sub)
  ├── messages.outbound.get       # Query outbound messages (request/reply)
  ├── messages.outbound.mark_sent # Mark message as sent (pub/sub)
  └── stats.recent_chat.get       # Get recent chat (request/reply)
```

**Pub/Sub Pattern** (Fire-and-forget):
- Bot publishes event to NATS
- DatabaseService subscribes and handles
- No response needed
- Examples: user_joined, message_log, stats updates

**Request/Reply Pattern** (Query):
- Bot publishes request to subject
- DatabaseService receives, queries database, replies
- Bot awaits response
- Examples: get outbound messages, get recent chat

---

## 3. Implementation

### 3.1 DatabaseService Class

**File**: `common/database_service.py` (NEW)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NATS-enabled database service for process isolation"""
import asyncio
import json
import logging
import time
from typing import Optional
from nats.aio.client import Client as NATS
from common.database import BotDatabase


class DatabaseService:
    """NATS-enabled wrapper around BotDatabase for process isolation.
    
    This service subscribes to NATS subjects and forwards database operations
    to the underlying BotDatabase. Enables running database in separate process.
    
    Example Usage:
        # Start database service
        nats = await nats.connect("nats://localhost:4222")
        db_service = DatabaseService(nats, "bot_data.db")
        await db_service.start()
        
        # Service now handles all database operations via NATS
        # Can run in separate process from bot
    """
    
    def __init__(self, nats_client: NATS, db_path: str = 'bot_data.db'):
        """Initialize database service.
        
        Args:
            nats_client: Connected NATS client
            db_path: Path to SQLite database file
        """
        self.nats = nats_client
        self.db = BotDatabase(db_path)
        self.logger = logging.getLogger(__name__)
        self._subscriptions = []
        self._running = False
    
    async def start(self):
        """Subscribe to all database subjects and start handling events."""
        if self._running:
            self.logger.warning("DatabaseService already running")
            return
        
        self.logger.info("Starting DatabaseService...")
        
        # Pub/Sub subscriptions (fire-and-forget events)
        self._subscriptions.extend([
            await self.nats.subscribe('rosey.db.user.joined', cb=self._handle_user_joined),
            await self.nats.subscribe('rosey.db.user.left', cb=self._handle_user_left),
            await self.nats.subscribe('rosey.db.message.log', cb=self._handle_message_log),
            await self.nats.subscribe('rosey.db.stats.user_count', cb=self._handle_user_count),
            await self.nats.subscribe('rosey.db.stats.high_water', cb=self._handle_high_water),
            await self.nats.subscribe('rosey.db.status.update', cb=self._handle_status_update),
            await self.nats.subscribe('rosey.db.messages.outbound.mark_sent', cb=self._handle_mark_sent),
        ])
        
        # Request/Reply subscriptions (queries)
        self._subscriptions.extend([
            await self.nats.subscribe('rosey.db.messages.outbound.get', cb=self._handle_outbound_query),
            await self.nats.subscribe('rosey.db.stats.recent_chat.get', cb=self._handle_recent_chat_query),
        ])
        
        self._running = True
        self.logger.info(f"DatabaseService started with {len(self._subscriptions)} subscriptions")
    
    async def stop(self):
        """Unsubscribe from all subjects and stop service."""
        if not self._running:
            return
        
        self.logger.info("Stopping DatabaseService...")
        
        for sub in self._subscriptions:
            await sub.unsubscribe()
        
        self._subscriptions = []
        self._running = False
        self.logger.info("DatabaseService stopped")
    
    # Event Handlers (Pub/Sub)
    
    async def _handle_user_joined(self, msg):
        """Handle user joined event."""
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')
            
            if username:
                self.db.user_joined(username)
                self.logger.debug(f"[NATS] User joined: {username}")
        except Exception as e:
            self.logger.error(f"Error handling user_joined: {e}", exc_info=True)
    
    async def _handle_user_left(self, msg):
        """Handle user left event."""
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')
            
            if username:
                self.db.user_left(username)
                self.logger.debug(f"[NATS] User left: {username}")
        except Exception as e:
            self.logger.error(f"Error handling user_left: {e}", exc_info=True)
    
    async def _handle_message_log(self, msg):
        """Handle chat message logging."""
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')
            message = data.get('message', '')
            
            if username and message:
                self.db.message_logged(username, message)
                self.logger.debug(f"[NATS] Message logged: {username}")
        except Exception as e:
            self.logger.error(f"Error handling message_log: {e}", exc_info=True)
    
    async def _handle_user_count(self, msg):
        """Handle user count statistics update."""
        try:
            data = json.loads(msg.data.decode())
            chat_count = data.get('chat_count', 0)
            connected_count = data.get('connected_count', 0)
            
            self.db.update_user_count(chat_count, connected_count)
            self.logger.debug(f"[NATS] User count updated: chat={chat_count}, connected={connected_count}")
        except Exception as e:
            self.logger.error(f"Error handling user_count: {e}", exc_info=True)
    
    async def _handle_high_water(self, msg):
        """Handle high water mark update."""
        try:
            data = json.loads(msg.data.decode())
            chat_count = data.get('chat_count', 0)
            connected_count = data.get('connected_count', 0)
            
            self.db.update_high_water_mark(chat_count, connected_count)
            self.logger.debug(f"[NATS] High water updated: chat={chat_count}, connected={connected_count}")
        except Exception as e:
            self.logger.error(f"Error handling high_water: {e}", exc_info=True)
    
    async def _handle_status_update(self, msg):
        """Handle bot status update."""
        try:
            data = json.loads(msg.data.decode())
            status = data.get('status', 'unknown')
            details = data.get('details', '')
            
            # Log status (database doesn't store this currently)
            self.logger.info(f"[NATS] Bot status: {status} - {details}")
        except Exception as e:
            self.logger.error(f"Error handling status_update: {e}", exc_info=True)
    
    async def _handle_mark_sent(self, msg):
        """Handle marking outbound message as sent."""
        try:
            data = json.loads(msg.data.decode())
            message_id = data.get('message_id')
            
            if message_id:
                self.db.mark_outbound_message_sent(message_id)
                self.logger.debug(f"[NATS] Marked message sent: {message_id}")
        except Exception as e:
            self.logger.error(f"Error handling mark_sent: {e}", exc_info=True)
    
    # Query Handlers (Request/Reply)
    
    async def _handle_outbound_query(self, msg):
        """Handle query for outbound messages (request/reply)."""
        try:
            data = json.loads(msg.data.decode())
            username = data.get('username', '')
            limit = data.get('limit', 10)
            
            if username:
                messages = self.db.get_unsent_outbound_messages(username, limit=limit)
                response = json.dumps(messages).encode()
            else:
                response = json.dumps([]).encode()
            
            await self.nats.publish(msg.reply, response)
            self.logger.debug(f"[NATS] Replied to outbound query for {username}")
        except Exception as e:
            self.logger.error(f"Error handling outbound_query: {e}", exc_info=True)
            # Send empty response on error
            await self.nats.publish(msg.reply, json.dumps([]).encode())
    
    async def _handle_recent_chat_query(self, msg):
        """Handle query for recent chat messages (request/reply)."""
        try:
            data = json.loads(msg.data.decode())
            limit = data.get('limit', 50)
            
            messages = self.db.get_recent_chat(limit=limit)
            response = json.dumps(messages).encode()
            
            await self.nats.publish(msg.reply, response)
            self.logger.debug(f"[NATS] Replied to recent_chat query")
        except Exception as e:
            self.logger.error(f"Error handling recent_chat_query: {e}", exc_info=True)
            await self.nats.publish(msg.reply, json.dumps([]).encode())


async def main():
    """Standalone database service entry point.
    
    Run this file directly to start database service as separate process:
        python -m common.database_service
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Connect to NATS
    logger.info("Connecting to NATS...")
    nats = NATS()
    await nats.connect("nats://localhost:4222")
    logger.info("Connected to NATS")
    
    # Start database service
    db_service = DatabaseService(nats, "bot_data.db")
    await db_service.start()
    
    logger.info("DatabaseService running - press Ctrl+C to stop")
    
    try:
        # Keep service running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        await db_service.stop()
        await nats.close()
        logger.info("DatabaseService shutdown complete")


if __name__ == '__main__':
    asyncio.run(main())
```

---

## 4. Implementation Plan

### Phase 1: Create DatabaseService Skeleton (1 hour)

1. Create `common/database_service.py`
2. Implement `__init__`, `start()`, `stop()` methods
3. Add NATS subscription setup
4. Add basic error handling

### Phase 2: Implement Pub/Sub Handlers (2 hours)

1. `_handle_user_joined()` - calls `db.user_joined()`
2. `_handle_user_left()` - calls `db.user_left()`
3. `_handle_message_log()` - calls `db.message_logged()`
4. `_handle_user_count()` - calls `db.update_user_count()`
5. `_handle_high_water()` - calls `db.update_high_water_mark()`
6. `_handle_status_update()` - logs status
7. `_handle_mark_sent()` - calls `db.mark_outbound_message_sent()`

### Phase 3: Implement Request/Reply Handlers (1.5 hours)

1. `_handle_outbound_query()` - queries and replies with messages
2. `_handle_recent_chat_query()` - queries and replies with chat history

### Phase 4: Standalone Service Support (1 hour)

1. Add `main()` function for standalone execution
2. Add command-line argument parsing (database path, NATS URL)
3. Add proper logging setup
4. Test standalone execution

### Phase 5: Testing (1.5 hours)

1. Create `tests/unit/test_database_service.py`
2. Test subscription setup
3. Test each event handler
4. Test error handling
5. Test graceful shutdown

---

## 5. Testing Strategy

### 5.1 Unit Tests

**New Test File**: `tests/unit/test_database_service.py`

```python
import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from common.database_service import DatabaseService

@pytest.fixture
async def nats_client():
    """Mock NATS client."""
    client = Mock()
    client.subscribe = AsyncMock()
    client.publish = AsyncMock()
    return client

@pytest.fixture
def db_service(nats_client):
    """DatabaseService with mocked NATS and database."""
    with patch('common.database_service.BotDatabase') as MockDB:
        service = DatabaseService(nats_client, ':memory:')
        service.db = MockDB()
        return service

@pytest.mark.asyncio
async def test_start_subscribes_to_subjects(db_service, nats_client):
    """Verify start() subscribes to all subjects."""
    await db_service.start()
    
    # Should have subscribed to 9 subjects
    assert nats_client.subscribe.call_count == 9
    assert db_service._running

@pytest.mark.asyncio
async def test_handle_user_joined(db_service):
    """Verify user_joined handler calls database."""
    msg = Mock()
    msg.data = json.dumps({'username': 'alice'}).encode()
    
    await db_service._handle_user_joined(msg)
    
    db_service.db.user_joined.assert_called_once_with('alice')

@pytest.mark.asyncio
async def test_handle_outbound_query_replies(db_service, nats_client):
    """Verify outbound query handler replies with data."""
    msg = Mock()
    msg.data = json.dumps({'username': 'alice', 'limit': 10}).encode()
    msg.reply = 'reply.subject'
    
    db_service.db.get_unsent_outbound_messages.return_value = [
        {'id': 1, 'message': 'Hello'}
    ]
    
    await db_service._handle_outbound_query(msg)
    
    # Verify database queried
    db_service.db.get_unsent_outbound_messages.assert_called_once_with('alice', limit=10)
    
    # Verify reply sent
    nats_client.publish.assert_called_once()
    call_args = nats_client.publish.call_args
    assert call_args[0][0] == 'reply.subject'

@pytest.mark.asyncio
async def test_stop_unsubscribes(db_service):
    """Verify stop() unsubscribes from all subjects."""
    await db_service.start()
    
    # Mock subscriptions
    mock_subs = [Mock(unsubscribe=AsyncMock()) for _ in range(9)]
    db_service._subscriptions = mock_subs
    
    await db_service.stop()
    
    # All subscriptions unsubscribed
    for sub in mock_subs:
        sub.unsubscribe.assert_called_once()
    
    assert not db_service._running
    assert len(db_service._subscriptions) == 0
```

### 5.2 Integration Tests

**Manual Test**:

1. Start NATS server: `nats-server`
2. Start DatabaseService: `python -m common.database_service`
3. Use `nats` CLI to publish test events:
   ```bash
   nats pub rosey.db.user.joined '{"username":"alice"}'
   nats pub rosey.db.message.log '{"username":"alice","message":"Hello"}'
   nats req rosey.db.messages.outbound.get '{"username":"alice","limit":10}'
   ```
4. Verify database updated (check SQLite)

---

## 6. Acceptance Criteria

**Definition of Done**:

- [ ] DatabaseService class implemented in `common/database_service.py`
- [ ] All 7 pub/sub handlers implemented
- [ ] All 2 request/reply handlers implemented
- [ ] Standalone service executable (`python -m common.database_service`)
- [ ] Error handling for all handlers (log but don't crash)
- [ ] Graceful shutdown (unsubscribe all)
- [ ] Unit tests for all handlers
- [ ] Integration test with real NATS server
- [ ] Documentation in module docstrings
- [ ] Logging at appropriate levels

---

## 7. Dependencies

**Requires**:
- ✅ Sortie 1 (Event Normalization) - event structures defined
- ✅ Sprint 6a (NATS infrastructure) - NATS server available

**Blocks**:
- Sortie 4 (Bot NATS Migration) - bot needs service to publish to
- Sortie 5 (Config v2) - configuration needs service support

**Does NOT Block**:
- Sortie 2 (Bot Handler Migration) - independent change

---

## 8. Next Steps

**After Completion**:

1. Mark Sortie 3 complete
2. Begin Sortie 4: Bot NATS Migration (replace bot->db direct calls)
3. Test database service in standalone mode
4. Prepare for process isolation testing

---

**Sortie Status**: Ready for Implementation  
**Priority**: HIGH (Enables Process Isolation)  
**Estimated Effort**: 5-7 hours  
**Success Metric**: Database service handles all operations via NATS, runnable as standalone process
