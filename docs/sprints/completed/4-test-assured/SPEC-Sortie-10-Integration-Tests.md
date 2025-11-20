# SPEC-Commit-10: Integration Tests

## Purpose

Create comprehensive integration tests that validate multi-component workflows and cross-module interactions. These tests verify that individual components work together correctly in realistic scenarios.

## Scope

- **Coverage**: Multi-component integration workflows
- **Complexity**: High (async coordination, real database, socket.io)
- **Test Count**: 30+ tests across 6 test scenarios
- **Coverage Target**: N/A (integration tests focus on workflows, not line coverage)
- **Dependencies**:
  - All previous SPECs (1-9): Uses all components together
  - Real components: Minimal mocking, prefer real implementations

## Integration Testing Philosophy

**Unit Tests vs Integration Tests**:
- **Unit Tests**: Test individual components in isolation with heavy mocking
- **Integration Tests**: Test multiple components together with minimal mocking

**What to Test**:
- ✅ Bot connection lifecycle with real socket.io behavior
- ✅ Database persistence across bot restarts
- ✅ Shell commands triggering bot actions that update database
- ✅ PM command flow: receive PM → authenticate → execute → respond
- ✅ Playlist manipulation: add → database log → state update → event propagation
- ✅ Error recovery: connection lost → reconnect → state restoration
- ✅ User tracking: join → chat → leave → database stats update

**What NOT to Test** (leave to unit tests):
- Individual method logic
- Edge cases for specific functions
- Mocked component behavior

## Test Strategy

**Fixtures**:
```python
@pytest.fixture
def integration_db(tmp_path):
    """Real database for integration testing"""
    db_path = str(tmp_path / "integration_test.db")
    db = BotDatabase(db_path)
    yield db
    db.close()

@pytest.fixture
def integration_bot(integration_db):
    """Bot instance with real database"""
    bot = Bot(
        domain="cytu.be",
        channel="test_integration",
        user="IntegrationTestBot",
        restart_delay=5,
        response_timeout=10,
        enable_db=True,
        db_path=integration_db.db_path
    )
    # Don't actually connect to real server
    bot.socket = MagicMock()
    yield bot
    bot.disconnect()

@pytest.fixture
def integration_shell(integration_bot):
    """Shell instance connected to integration bot"""
    shell = Shell("localhost:19999", integration_bot)
    yield shell
    shell.close()

@pytest.fixture
async def mock_socket_server():
    """Mock socket.io server for testing"""
    # Simplified mock that simulates server responses
    server = AsyncMock()
    server.emit = AsyncMock()
    server.on = MagicMock()
    return server
```

**Test Organization**: 6 test scenarios with 30+ tests

### Test Scenario 1: Bot Lifecycle Integration (6 tests)

Tests complete bot lifecycle from startup to shutdown.

```python
@pytest.mark.asyncio
async def test_bot_startup_sequence(integration_bot, integration_db):
    """Bot startup initializes all components"""
    # Verify initial state
    assert integration_bot.user.name == "IntegrationTestBot"
    assert integration_bot.channel_name == "test_integration"
    assert integration_bot.db is not None
    
    # Verify database is connected
    status = integration_db.get_current_status()
    assert status is not None

@pytest.mark.asyncio
async def test_bot_user_join_triggers_database(integration_bot, integration_db):
    """User joining is logged to database"""
    # Simulate user join event
    await integration_bot._on_addUser({
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    })
    
    # Verify database record
    stats = integration_db.get_user_stats('alice')
    assert stats is not None
    assert stats['username'] == 'alice'

@pytest.mark.asyncio
async def test_bot_user_chat_updates_database(integration_bot, integration_db):
    """Chat messages increment database counters"""
    # Add user first
    await integration_bot._on_addUser({
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    })
    
    # Simulate chat messages
    for i in range(5):
        await integration_bot._on_chatMsg({
            'username': 'alice',
            'msg': f'Test message {i}',
            'time': int(time.time())
        })
    
    # Verify count
    stats = integration_db.get_user_stats('alice')
    assert stats['total_chat_lines'] == 5

@pytest.mark.asyncio
async def test_bot_user_leave_finalizes_session(integration_bot, integration_db):
    """User leaving finalizes database session"""
    # Add user
    await integration_bot._on_addUser({
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    })
    
    # Wait briefly to simulate session time
    await asyncio.sleep(0.2)
    
    # User leaves
    await integration_bot._on_userLeave({'name': 'alice'})
    
    # Verify session finalized
    stats = integration_db.get_user_stats('alice')
    assert stats['total_time_connected'] > 0
    assert stats['current_session_start'] is None

@pytest.mark.asyncio
async def test_bot_high_water_mark_tracking(integration_bot, integration_db):
    """Bot updates high water marks"""
    # Add multiple users
    for i in range(5):
        await integration_bot._on_addUser({
            'name': f'user{i}',
            'rank': 1.0,
            'afk': False,
            'muted': False
        })
    
    # Trigger user count update
    await integration_bot._on_usercount({'chatcount': 5, 'usercount': 8})
    
    # Verify high water marks
    max_chat, _ = integration_db.get_high_water_mark()
    max_connected, _ = integration_db.get_high_water_mark_connected()
    
    assert max_chat == 5
    assert max_connected == 8

@pytest.mark.asyncio
async def test_bot_shutdown_finalizes_database(integration_bot, integration_db):
    """Bot shutdown finalizes all active sessions"""
    # Add users
    await integration_bot._on_addUser({'name': 'alice', 'rank': 1.0, 'afk': False, 'muted': False})
    await integration_bot._on_addUser({'name': 'bob', 'rank': 1.0, 'afk': False, 'muted': False})
    
    await asyncio.sleep(0.1)
    
    # Close database (simulates shutdown)
    integration_db.close()
    
    # Reopen and check sessions finalized
    db2 = BotDatabase(integration_db.db_path)
    alice_stats = db2.get_user_stats('alice')
    bob_stats = db2.get_user_stats('bob')
    
    assert alice_stats['current_session_start'] is None
    assert bob_stats['current_session_start'] is None
    db2.close()
```

### Test Scenario 2: Shell Command Integration (7 tests)

Tests shell commands that trigger bot actions and database updates.

```python
@pytest.mark.asyncio
async def test_shell_say_command_sends_chat(integration_bot, integration_shell):
    """Shell 'say' command sends chat message"""
    integration_bot.chat = AsyncMock()
    
    result = await integration_shell.handle_command("say Hello world", integration_bot)
    
    integration_bot.chat.assert_called_once_with("Hello world")
    assert "Sent:" in result

@pytest.mark.asyncio
async def test_shell_add_command_updates_playlist(integration_bot, integration_shell):
    """Shell 'add' command updates bot playlist"""
    integration_bot.add_media = AsyncMock()
    integration_bot.channel.playlist.queue = []
    
    result = await integration_shell.handle_command(
        "add https://youtu.be/dQw4w9WgXcQ yes",
        integration_bot
    )
    
    integration_bot.add_media.assert_called_once()

@pytest.mark.asyncio
async def test_shell_stats_command_queries_database(integration_bot, integration_shell, integration_db):
    """Shell 'stats' command queries real database"""
    # Populate database
    integration_db.user_joined('alice')
    for _ in range(10):
        integration_db.user_chat_message('alice')
    integration_db.update_high_water_mark(5, 10)
    
    result = await integration_shell.handle_command("stats", integration_bot)
    
    assert "Peak (chat): 5" in result
    assert "Peak (connected): 10" in result

@pytest.mark.asyncio
async def test_shell_user_command_with_database(integration_bot, integration_shell, integration_db):
    """Shell 'user' command includes database stats"""
    # Add user to bot
    await integration_bot._on_addUser({
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    })
    
    # Add chat messages
    for _ in range(5):
        await integration_bot._on_chatMsg({
            'username': 'alice',
            'msg': 'Test',
            'time': int(time.time())
        })
    
    result = await integration_shell.handle_command("user alice", integration_bot)
    
    assert "User: alice" in result
    assert "Chat msgs: 5" in result

@pytest.mark.asyncio
async def test_shell_kick_command_triggers_bot_action(integration_bot, integration_shell):
    """Shell 'kick' command triggers bot.kick()"""
    integration_bot.kick = AsyncMock()
    
    result = await integration_shell.handle_command("kick alice Spamming", integration_bot)
    
    integration_bot.kick.assert_called_once_with("alice", "Spamming")

@pytest.mark.asyncio
async def test_shell_playlist_command_shows_queue(integration_bot, integration_shell):
    """Shell 'playlist' command shows current queue"""
    # Add items to playlist
    from lib import MediaLink
    item1 = MagicMock()
    item1.title = "Video 1"
    item1.duration = 120
    
    item2 = MagicMock()
    item2.title = "Video 2"
    item2.duration = 180
    
    integration_bot.channel.playlist.queue = [item1, item2]
    integration_bot.channel.playlist.current = item1
    
    result = await integration_shell.handle_command("playlist", integration_bot)
    
    assert "Video 1" in result
    assert "Video 2" in result
    assert "►" in result  # Current marker

@pytest.mark.asyncio
async def test_shell_info_command_shows_live_state(integration_bot, integration_shell):
    """Shell 'info' command reflects current bot state"""
    # Add users
    await integration_bot._on_addUser({'name': 'alice', 'rank': 1.0, 'afk': False, 'muted': False})
    await integration_bot._on_addUser({'name': 'bob', 'rank': 1.0, 'afk': False, 'muted': False})
    
    result = await integration_shell.handle_command("info", integration_bot)
    
    assert "Bot: IntegrationTestBot" in result
    assert "Channel: test_integration" in result
```

### Test Scenario 3: PM Command Flow (5 tests)

Tests PM-based command flow with authentication and response.

```python
@pytest.mark.asyncio
async def test_pm_command_moderator_flow(integration_bot, integration_shell, integration_db):
    """Complete PM command flow for moderator"""
    # Add moderator user
    moderator = MagicMock()
    moderator.name = "ModUser"
    moderator.rank = 2.5
    
    integration_bot.channel.userlist['ModUser'] = moderator
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'ModUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: moderator
    integration_bot.pm = AsyncMock()
    
    # Send PM command
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'status'
    })
    
    # Verify response sent
    integration_bot.pm.assert_called()
    
    # Verify database logging
    cursor = integration_db.conn.cursor()
    cursor.execute('''
        SELECT * FROM user_actions 
        WHERE username = 'ModUser' AND action_type = 'pm_command'
    ''')
    assert cursor.fetchone() is not None

@pytest.mark.asyncio
async def test_pm_command_non_moderator_blocked(integration_bot, integration_shell):
    """Non-moderator PM commands are blocked"""
    # Add regular user
    regular = MagicMock()
    regular.name = "RegularUser"
    regular.rank = 1.0
    
    integration_bot.channel.userlist['RegularUser'] = regular
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'RegularUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: regular
    integration_bot.pm = AsyncMock()
    
    # Send PM command
    await integration_shell.handle_pm_command('pm', {
        'username': 'RegularUser',
        'msg': 'say test'
    })
    
    # Verify no response
    integration_bot.pm.assert_not_called()

@pytest.mark.asyncio
async def test_pm_command_triggers_bot_action(integration_bot, integration_shell):
    """PM command triggers actual bot action"""
    moderator = MagicMock()
    moderator.name = "ModUser"
    moderator.rank = 2.0
    
    integration_bot.channel.userlist['ModUser'] = moderator
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'ModUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: moderator
    integration_bot.pm = AsyncMock()
    integration_bot.chat = AsyncMock()
    
    # PM: "say Hello"
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'say Hello everyone'
    })
    
    # Verify chat message sent
    integration_bot.chat.assert_called_once_with("Hello everyone")

@pytest.mark.asyncio
async def test_pm_command_long_response_splits(integration_bot, integration_shell):
    """Long PM responses are split into multiple messages"""
    moderator = MagicMock()
    moderator.name = "ModUser"
    moderator.rank = 2.0
    
    integration_bot.channel.userlist['ModUser'] = moderator
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'ModUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: moderator
    integration_bot.pm = AsyncMock()
    
    # Command with long response (help text)
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'help'
    })
    
    # Should send multiple PM chunks (help text is >500 chars)
    assert integration_bot.pm.call_count >= 2

@pytest.mark.asyncio
async def test_pm_command_error_sends_error_message(integration_bot, integration_shell):
    """PM command errors send error message back"""
    moderator = MagicMock()
    moderator.name = "ModUser"
    moderator.rank = 2.0
    
    integration_bot.channel.userlist['ModUser'] = moderator
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'ModUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: moderator
    integration_bot.pm = AsyncMock()
    integration_bot.kick = AsyncMock(side_effect=Exception("Test error"))
    
    # Command that will error
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'kick alice'
    })
    
    # Should send error PM
    error_call = [call for call in integration_bot.pm.call_args_list 
                  if 'Error:' in str(call)]
    assert len(error_call) > 0
```

### Test Scenario 4: Database Persistence (5 tests)

Tests data persistence across bot restarts.

```python
@pytest.mark.asyncio
async def test_user_stats_persist_across_restart(tmp_path):
    """User statistics persist across database reopens"""
    db_path = str(tmp_path / "persist_test.db")
    
    # First session
    db1 = BotDatabase(db_path)
    db1.user_joined('alice')
    for _ in range(10):
        db1.user_chat_message('alice')
    db1.close()
    
    # Second session (reopen)
    db2 = BotDatabase(db_path)
    stats = db2.get_user_stats('alice')
    assert stats['total_chat_lines'] == 10
    db2.close()

@pytest.mark.asyncio
async def test_high_water_marks_persist(tmp_path):
    """High water marks persist across reopens"""
    db_path = str(tmp_path / "persist_test.db")
    
    # Set high water marks
    db1 = BotDatabase(db_path)
    db1.update_high_water_mark(42, 100)
    db1.close()
    
    # Reopen and verify
    db2 = BotDatabase(db_path)
    max_chat, _ = db2.get_high_water_mark()
    max_connected, _ = db2.get_high_water_mark_connected()
    assert max_chat == 42
    assert max_connected == 100
    db2.close()

@pytest.mark.asyncio
async def test_outbound_messages_persist(tmp_path):
    """Outbound message queue persists"""
    db_path = str(tmp_path / "persist_test.db")
    
    # Enqueue messages
    db1 = BotDatabase(db_path)
    db1.enqueue_outbound_message("Message 1")
    db1.enqueue_outbound_message("Message 2")
    db1.close()
    
    # Reopen and retrieve
    db2 = BotDatabase(db_path)
    messages = db2.get_unsent_outbound_messages()
    assert len(messages) == 2
    db2.close()

@pytest.mark.asyncio
async def test_api_tokens_persist(tmp_path):
    """API tokens persist across sessions"""
    db_path = str(tmp_path / "persist_test.db")
    
    # Generate token
    db1 = BotDatabase(db_path)
    token = db1.generate_api_token("Test token")
    db1.close()
    
    # Reopen and validate
    db2 = BotDatabase(db_path)
    assert db2.validate_api_token(token) is True
    db2.close()

@pytest.mark.asyncio
async def test_recent_chat_persists(tmp_path):
    """Recent chat messages persist"""
    db_path = str(tmp_path / "persist_test.db")
    
    # Store messages
    db1 = BotDatabase(db_path)
    db1.user_joined('alice')
    db1.user_chat_message('alice', 'Message 1')
    db1.user_chat_message('alice', 'Message 2')
    db1.close()
    
    # Reopen and retrieve
    db2 = BotDatabase(db_path)
    recent = db2.get_recent_chat(limit=10)
    assert len(recent) == 2
    assert recent[0]['message'] == 'Message 1'
    db2.close()
```

### Test Scenario 5: Error Recovery (4 tests)

Tests error handling and recovery across components.

```python
@pytest.mark.asyncio
async def test_bot_handles_database_error_gracefully(integration_bot):
    """Bot continues if database operation fails"""
    # Close database to simulate error
    if integration_bot.db:
        integration_bot.db.conn.close()
    
    # Bot should not crash on user join
    await integration_bot._on_addUser({
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    })
    
    # User should still be in memory
    assert 'alice' in integration_bot.channel.userlist

@pytest.mark.asyncio
async def test_shell_command_error_returns_message(integration_bot, integration_shell):
    """Shell command errors return user-friendly message"""
    # Make bot.chat raise an error
    integration_bot.chat = AsyncMock(side_effect=Exception("Connection lost"))
    
    result = await integration_shell.handle_command("say test", integration_bot)
    
    assert "Error:" in result
    assert "Connection lost" in result

@pytest.mark.asyncio
async def test_pm_command_bot_error_notifies_user(integration_bot, integration_shell):
    """PM command errors send error notification"""
    moderator = MagicMock()
    moderator.name = "ModUser"
    moderator.rank = 2.0
    
    integration_bot.channel.userlist['ModUser'] = moderator
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'ModUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: moderator
    integration_bot.pm = AsyncMock()
    integration_bot.pause = AsyncMock(side_effect=Exception("No permission"))
    
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'pause'
    })
    
    # Should send error PM
    calls = [str(call) for call in integration_bot.pm.call_args_list]
    assert any('Error:' in call for call in calls)

@pytest.mark.asyncio
async def test_database_maintenance_recovers_from_error(integration_db):
    """Database maintenance handles errors gracefully"""
    # Close connection to force error
    integration_db.conn.close()
    
    # Maintenance should raise exception but not crash
    with pytest.raises(Exception):
        integration_db.perform_maintenance()
    
    # Database can be reconnected
    integration_db._connect()
    assert integration_db.conn is not None
```

### Test Scenario 6: End-to-End Workflows (3 tests)

Tests complete user workflows from start to finish.

```python
@pytest.mark.asyncio
async def test_complete_user_session_workflow(integration_bot, integration_db):
    """Complete workflow: join → chat → stats query → leave"""
    # 1. User joins
    await integration_bot._on_addUser({
        'name': 'alice',
        'rank': 1.0,
        'afk': False,
        'muted': False
    })
    
    # 2. User chats
    for i in range(5):
        await integration_bot._on_chatMsg({
            'username': 'alice',
            'msg': f'Message {i}',
            'time': int(time.time())
        })
    
    # 3. Query stats
    stats = integration_db.get_user_stats('alice')
    assert stats['total_chat_lines'] == 5
    
    # 4. User leaves
    await asyncio.sleep(0.1)
    await integration_bot._on_userLeave({'name': 'alice'})
    
    # 5. Verify final stats
    final_stats = integration_db.get_user_stats('alice')
    assert final_stats['total_time_connected'] > 0
    assert final_stats['current_session_start'] is None

@pytest.mark.asyncio
async def test_playlist_manipulation_workflow(integration_bot, integration_shell):
    """Complete workflow: add → query → move → jump → remove"""
    integration_bot.add_media = AsyncMock()
    integration_bot.move_media = AsyncMock()
    integration_bot.set_current_media = AsyncMock()
    integration_bot.remove_media = AsyncMock()
    
    # Setup playlist
    item1 = MagicMock(title="Video 1", duration=120)
    item2 = MagicMock(title="Video 2", duration=180)
    item3 = MagicMock(title="Video 3", duration=240)
    integration_bot.channel.playlist.queue = [item1, item2, item3]
    integration_bot.channel.playlist.current = item1
    
    # 1. Add new item
    await integration_shell.handle_command("add https://youtu.be/xyz", integration_bot)
    
    # 2. Query playlist
    result = await integration_shell.handle_command("playlist", integration_bot)
    assert "Video 1" in result
    
    # 3. Move item
    await integration_shell.handle_command("move 2 3", integration_bot)
    
    # 4. Jump to item
    await integration_shell.handle_command("jump 2", integration_bot)
    
    # 5. Remove item
    await integration_shell.handle_command("remove 3", integration_bot)
    
    # Verify all commands executed
    integration_bot.add_media.assert_called_once()
    integration_bot.set_current_media.assert_called_once()

@pytest.mark.asyncio
async def test_moderator_control_workflow(integration_bot, integration_shell, integration_db):
    """Complete workflow: PM auth → command → bot action → database log"""
    moderator = MagicMock()
    moderator.name = "ModUser"
    moderator.rank = 3.0
    
    integration_bot.channel.userlist['ModUser'] = moderator
    integration_bot.channel.userlist.__contains__ = lambda self, name: name == 'ModUser'
    integration_bot.channel.userlist.__getitem__ = lambda self, name: moderator
    integration_bot.pm = AsyncMock()
    integration_bot.kick = AsyncMock()
    
    # 1. Moderator sends PM command
    await integration_shell.handle_pm_command('pm', {
        'username': 'ModUser',
        'msg': 'kick alice Spamming'
    })
    
    # 2. Verify bot action executed
    integration_bot.kick.assert_called_once_with('alice', 'Spamming')
    
    # 3. Verify database log
    cursor = integration_db.conn.cursor()
    cursor.execute('''
        SELECT * FROM user_actions 
        WHERE username = 'ModUser' AND action_type = 'pm_command'
    ''')
    log_entry = cursor.fetchone()
    assert log_entry is not None
    assert log_entry['details'] == 'kick alice Spamming'
    
    # 4. Verify response sent
    integration_bot.pm.assert_called()
```

## Expected Outcomes

**Integration Test Goals**:
- ✅ Verify components work together correctly
- ✅ Validate data flows between bot, database, and shell
- ✅ Ensure database persistence across sessions
- ✅ Test error propagation and recovery
- ✅ Validate authentication and authorization flows
- ✅ Confirm real-world workflows execute successfully

**Coverage**: Not applicable (integration tests validate workflows, not line coverage)

**Performance Considerations**:
- Integration tests slower than unit tests (real database I/O)
- Use tmp_path for isolated test databases
- Clean up resources properly (close connections)

## Manual Verification Commands

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run specific scenario
pytest tests/integration/test_bot_lifecycle.py -v

# Run with debug logging
pytest tests/integration/ -v -s --log-cli-level=DEBUG

# Run integration tests separately from unit tests
pytest tests/integration/ --tb=short

# Skip slow integration tests during development
pytest tests/unit/ -v  # Unit tests only
```

## Success Criteria

- ✅ All 30+ integration tests pass
- ✅ Bot lifecycle workflows validated
- ✅ Shell command integration verified
- ✅ PM command flow authenticated and executed
- ✅ Database persistence confirmed across restarts
- ✅ Error recovery tested
- ✅ End-to-end workflows complete successfully
- ✅ No resource leaks (database connections closed)
- ✅ Tests run in isolation (no cross-test contamination)

## Dependencies

- **All SPECs 1-9**: Integration tests use all components
- **Real implementations**: Minimal mocking, prefer actual components
- **pytest-asyncio**: For async test execution
- **tmp_path**: For isolated test databases

## Implementation Notes

1. **Test Organization**: Create `tests/integration/` directory separate from `tests/unit/`
2. **Real Components**: Use real Database, Shell instances (not mocks)
3. **Bot Mocking**: Mock socket.io connection but use real bot logic
4. **Database Isolation**: Each test gets fresh tmp_path database
5. **Cleanup**: Use fixtures with yield to ensure cleanup
6. **Async Coordination**: Use asyncio.sleep() for timing-sensitive tests
7. **Error Testing**: Test both happy path and error scenarios
8. **Workflow Focus**: Test realistic user stories, not edge cases
9. **Resource Management**: Close connections, cancel tasks in teardown
10. **Speed**: Keep integration tests reasonably fast (<5 seconds each)

## Notes

- **Purpose**: Validate multi-component interactions
- **Test Count**: 30+ tests across 6 scenarios
- **Scope**: Bot lifecycle, shell integration, PM flow, persistence, errors, workflows
- **Philosophy**: Minimal mocking, realistic scenarios
- **Key Workflows**:
  - User join → chat → stats → leave
  - PM command: auth → execute → respond → log
  - Playlist: add → move → jump → remove
  - Database: write → close → reopen → read
- **Testing Strategy**: Use real components with isolated databases
- **Next Step**: Ready for implementation after approval
