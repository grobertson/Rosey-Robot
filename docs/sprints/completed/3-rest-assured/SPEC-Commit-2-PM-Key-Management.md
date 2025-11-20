# SPEC: API Key Management via PM Commands

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 2 - PM Key Management  
**Dependencies:** Commit 1 (Database Schema)  
**Estimated Effort:** Medium

---

## Objective

Implement PM commands for moderators to request, regenerate, and revoke API keys. This provides self-service key management before the API itself exists, and allows testing of the authentication data layer.

---

## Changes Required

### 1. API Key Utility Module

**File:** `common/api_key_utils.py` (new)

```python
"""
Utilities for API key generation and validation.
"""
import secrets
import string
import bcrypt
from typing import Tuple


def generate_api_key() -> str:
    """
    Generate a secure random API key.
    
    Returns:
        32-character URL-safe API key
    """
    alphabet = string.ascii_letters + string.digits + '-_'
    key = ''.join(secrets.choice(alphabet) for _ in range(32))
    return key


def hash_api_key(api_key: str) -> str:
    """
    Hash API key using bcrypt.
    
    Args:
        api_key: Plaintext API key
        
    Returns:
        bcrypt hash as string
    """
    key_bytes = api_key.encode('utf-8')
    salt = bcrypt.gensalt(rounds=12)
    hash_bytes = bcrypt.hashpw(key_bytes, salt)
    return hash_bytes.decode('utf-8')


def verify_api_key(api_key: str, key_hash: str) -> bool:
    """
    Verify API key against stored hash.
    
    Args:
        api_key: Plaintext API key to check
        key_hash: Stored bcrypt hash
        
    Returns:
        True if key matches hash
    """
    try:
        key_bytes = api_key.encode('utf-8')
        hash_bytes = key_hash.encode('utf-8')
        return bcrypt.checkpw(key_bytes, hash_bytes)
    except (ValueError, AttributeError):
        return False


def create_api_key_pair() -> Tuple[str, str]:
    """
    Generate API key and its hash.
    
    Returns:
        Tuple of (plaintext_key, hash)
    """
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    return api_key, key_hash
```

### 2. PM Command Handler Updates

**File:** `common/shell.py` (update)

Extend the existing `handle_command` method to support API key management. The existing `handle_pm_command` already validates moderator rank (2.0+), so we don't need to duplicate that logic.

Add to imports:

```python
from common.api_key_utils import create_api_key_pair
```

Add new command handlers in the `handle_command` method (after existing commands):

```python
# In handle_command method, add to command routing section:

# === API Key Management Commands (new) ===
elif command == 'apikey':
    return await self.cmd_apikey(bot)

elif command == 'apikey-info':
    return await self.cmd_apikey_info(bot)

elif command == 'apikey-regenerate':
    return await self.cmd_apikey_regenerate(bot)

elif command == 'apikey-revoke':
    return await self.cmd_apikey_revoke(bot)
```

Add the command implementation methods to the Shell class:

```python
# Add these methods to Shell class

async def cmd_apikey(self, bot) -> str:
    """
    Generate or show API key info for moderator.
    
    Note: Username is available via bot.user context from PM handler.
    Rank check already done by handle_pm_command.
    """
    # Get username from PM context (set by handle_pm_command)
    username = getattr(bot, '_pm_username', None)
    if not username:
        return "Error: Could not determine username"
    
    # Check if user already has a key
    if bot.db:
        existing_info = await bot.db.get_api_key_info(username)
        if existing_info and not existing_info['revoked']:
            created = existing_info['created_at'].strftime('%Y-%m-%d %H:%M UTC')
            last_used = existing_info['last_used']
            last_used_str = last_used.strftime('%Y-%m-%d %H:%M UTC') if last_used else 'Never'
            
            return (
                f"You already have an active API key (created {created}).\n"
                f"Last used: {last_used_str}\n\n"
                "To regenerate your key, use: apikey-regenerate\n"
                "To revoke your key, use: apikey-revoke\n\n"
                "⚠️ Your API key was sent when you first requested it. "
                "If you've lost it, you'll need to regenerate a new one."
            )
    
    # Generate new API key
    api_key, key_hash = create_api_key_pair()
    if bot.db:
        await bot.db.create_api_key(username, key_hash)
    
    return (
        f"✅ Your API key: {api_key}\n\n"
        "⚠️ IMPORTANT: Save this key securely!\n"
        "This is the ONLY time you'll see the full key.\n\n"
        "Usage:\n"
        "  curl -H 'X-API-Key: {key}' http://localhost:8080/api/v1/status\n\n"
        "API Documentation: http://localhost:8080/docs\n\n"
        "Commands:\n"
        "  apikey-regenerate - Generate a new key (old one stops working)\n"
        "  apikey-revoke - Disable your API access"
    )


async def cmd_apikey_regenerate(self, bot) -> str:
    """Regenerate API key for moderator."""
    username = getattr(bot, '_pm_username', None)
    if not username:
        return "Error: Could not determine username"
    
    if not bot.db:
        return "Database not available"
    
    # Check if user has existing key
    existing_info = await bot.db.get_api_key_info(username)
    if not existing_info:
        return "You don't have an API key yet. Use 'apikey' to create one."
    
    # Generate new key (automatically revokes old one via ON CONFLICT)
    api_key, key_hash = create_api_key_pair()
    await bot.db.create_api_key(username, key_hash)
    
    return (
        f"✅ Your NEW API key: {api_key}\n\n"
        "⚠️ Your old key has been revoked and will no longer work.\n"
        "Save this new key securely - you won't see it again!\n\n"
        "API Documentation: http://localhost:8080/docs"
    )


async def cmd_apikey_revoke(self, bot) -> str:
    """Revoke API key for moderator."""
    username = getattr(bot, '_pm_username', None)
    if not username:
        return "Error: Could not determine username"
    
    if not bot.db:
        return "Database not available"
    
    # Attempt to revoke key
    revoked = await bot.db.revoke_api_key(username)
    
    if revoked:
        return (
            "✅ Your API key has been revoked.\n"
            "All API requests with your old key will now fail.\n\n"
            "To create a new key, use: apikey"
        )
    else:
        return "You don't have an active API key to revoke.\nUse 'apikey' to create one."


async def cmd_apikey_info(self, bot) -> str:
    """Show API key information (without revealing the key)."""
    username = getattr(bot, '_pm_username', None)
    if not username:
        return "Error: Could not determine username"
    
    if not bot.db:
        return "Database not available"
    
    info = await bot.db.get_api_key_info(username)
    
    if not info:
        return "You don't have an API key yet.\nUse 'apikey' to create one."
    
    created = info['created_at'].strftime('%Y-%m-%d %H:%M UTC')
    last_used = info['last_used']
    last_used_str = last_used.strftime('%Y-%m-%d %H:%M UTC') if last_used else 'Never'
    status = 'REVOKED' if info['revoked'] else 'Active'
    
    message = (
        f"API Key Status: {status}\n"
        f"Created: {created}\n"
        f"Last Used: {last_used_str}\n"
    )
    
    if info['revoked']:
        revoked_at = info['revoked_at'].strftime('%Y-%m-%d %H:%M UTC')
        message += f"Revoked: {revoked_at}\n"
        message += "\nUse 'apikey' to create a new key."
    else:
        message += (
            "\nCommands:\n"
            "  apikey-regenerate - Generate new key\n"
            "  apikey-revoke - Disable API access"
        )
    
    return message
```

Also update `handle_pm_command` to store username in bot context:

```python
# In handle_pm_command method, after rank check and before handle_command call:

# Store username in bot context for command handlers
bot._pm_username = username

# Process the command
try:
    result = await self.handle_command(message, bot)
    """
    Generate or retrieve API key for moderator.
    
    Args:
        username: User requesting API key
        rank: User's rank
        
    Returns:
        Response message
    """
    # Check if user is moderator (rank >= 2)
    if rank < 2:
        return (
            "Sorry, API access is only available to moderators. "
            "If you need API access, please contact a channel administrator."
        )
    
    # Check if user already has a key
    existing_info = await self.db.get_api_key_info(username)
    if existing_info and not existing_info['revoked']:
        created = existing_info['created_at'].strftime('%Y-%m-%d %H:%M UTC')
        last_used = existing_info['last_used']
        last_used_str = last_used.strftime('%Y-%m-%d %H:%M UTC') if last_used else 'Never'
        
        return (
            f"You already have an active API key (created {created}).\n"
            f"Last used: {last_used_str}\n\n"
            "To regenerate your key, use: !apikey-regenerate\n"
            "To revoke your key, use: !apikey-revoke\n\n"
            "⚠️ Your API key was sent when you first requested it. "
            "If you've lost it, you'll need to regenerate a new one."
        )
    
    # Generate new API key
    api_key, key_hash = create_api_key_pair()
    await self.db.create_api_key(username, key_hash)
    
    return (
        f"✅ Your API key: {api_key}\n\n"
        "⚠️ IMPORTANT: Save this key securely!\n"
        "This is the ONLY time you'll see the full key.\n\n"
        "Usage:\n"
        "  curl -H 'X-API-Key: {key}' http://localhost:8080/api/v1/status\n\n"
        "API Documentation: http://localhost:8080/docs\n\n"
        "Commands:\n"
        "  !apikey-regenerate - Generate a new key (old one stops working)\n"
        "  !apikey-revoke - Disable your API access"
    )


async def handle_apikey_regenerate_command(self, username: str, rank: int) -> str:
    """
    Regenerate API key for moderator.
    
    Args:
        username: User requesting regeneration
        rank: User's rank
        
    Returns:
        Response message
    """
    if rank < 2:
        return "Sorry, API access is only available to moderators."
    
    # Check if user has existing key
    existing_info = await self.db.get_api_key_info(username)
    if not existing_info:
        return (
            "You don't have an API key yet. Use !apikey to create one."
        )
    
    # Generate new key (this automatically revokes old one via ON CONFLICT)
    api_key, key_hash = create_api_key_pair()
    await self.db.create_api_key(username, key_hash)
    
    return (
        f"✅ Your NEW API key: {api_key}\n\n"
        "⚠️ Your old key has been revoked and will no longer work.\n"
        "Save this new key securely - you won't see it again!\n\n"
        "API Documentation: http://localhost:8080/docs"
    )


async def handle_apikey_revoke_command(self, username: str, rank: int) -> str:
    """
    Revoke API key for moderator.
    
    Args:
        username: User requesting revocation
        rank: User's rank
        
    Returns:
        Response message
    """
    if rank < 2:
        return "Sorry, API access is only available to moderators."
    
    # Attempt to revoke key
    revoked = await self.db.revoke_api_key(username)
    
    if revoked:
        return (
            "✅ Your API key has been revoked.\n"
            "All API requests with your old key will now fail.\n\n"
            "To create a new key, use: !apikey"
        )
    else:
        return (
            "You don't have an active API key to revoke.\n"
            "Use !apikey to create one."
        )


async def handle_apikey_info_command(self, username: str, rank: int) -> str:
    """
    Show API key information (without revealing the key).
    
    Args:
        username: User requesting info
        rank: User's rank
        
    Returns:
        Response message
    """
    if rank < 2:
        return "Sorry, API access is only available to moderators."
    
    info = await self.db.get_api_key_info(username)
    
    if not info:
        return (
            "You don't have an API key yet.\n"
            "Use !apikey to create one."
        )
    
    created = info['created_at'].strftime('%Y-%m-%d %H:%M UTC')
    last_used = info['last_used']
    last_used_str = last_used.strftime('%Y-%m-%d %H:%M UTC') if last_used else 'Never'
    status = 'REVOKED' if info['revoked'] else 'Active'
    
    message = (
        f"API Key Status: {status}\n"
        f"Created: {created}\n"
        f"Last Used: {last_used_str}\n"
    )
    
    if info['revoked']:
        revoked_at = info['revoked_at'].strftime('%Y-%m-%d %H:%M UTC')
        message += f"Revoked: {revoked_at}\n"
        message += "\nUse !apikey to create a new key."
    else:
        message += (
            "\nCommands:\n"
            "  !apikey-regenerate - Generate new key\n"
            "  !apikey-revoke - Disable API access"
        )
    
    return message


# Update command router to include new commands
async def handle_pm(self, username: str, message: str, rank: int) -> str:
    """
    Route PM command to appropriate handler.
    
    Args:
        username: User who sent PM
        message: PM message content
        rank: User's rank
        
    Returns:
        Response message
    """
    message = message.strip()
    
    # Existing commands...
    if message == '!help':
        return await self.handle_help_command(username, rank)
    
    # API Key commands
    elif message == '!apikey':
        return await self.handle_apikey_command(username, rank)
    
    elif message == '!apikey-regenerate':
        return await self.handle_apikey_regenerate_command(username, rank)
    
    elif message == '!apikey-revoke':
        return await self.handle_apikey_revoke_command(username, rank)
    
    elif message == '!apikey-info':
        return await self.handle_apikey_info_command(username, rank)
    
    # ... other commands
    
    else:
        return "Unknown command. Send !help for available commands."
```

### 3. Help Command Update

**File:** `common/shell.py` (update)

Update the existing HELP_TEXT constant to include API key management commands:

```python
HELP_TEXT = """
Bot Commands:
───────────────────────────────
Info:
 help - Show commands
 info - Bot & channel
 status - Connection
 stats - Database stats

Users:
 users - List all
 user <name> - User info
 afk [on|off] - Set AFK

Chat:
 say <msg> - Chat msg
 pm <u> <msg> - Private msg

Playlist:
 playlist [n] - Show queue
 current - Now playing
 add <url> [t] - Add video
 remove <#> - Delete item
 move <#> <#> - Reorder
 jump <#> - Jump to
 next - Skip video

Control:
 pause - Pause vid
 kick <u> [r] - Kick user
 voteskip - Skip vote

API Access:
 apikey - Get your API key
 apikey-info - View key status
 apikey-regenerate - New key
 apikey-revoke - Disable access

Examples:
 say Hello everyone!
 add youtu.be/xyz yes
 apikey
 playlist 5
"""
```

No need for rank-based help filtering since `handle_pm_command` already filters by rank (2.0+).

### 4. Dependencies Update

**File:** `requirements.txt` (update)

Add bcrypt if not already present:

```
bcrypt>=4.1.0
```

---

## Testing Checklist

### Manual Tests

1. **First-Time Key Request**

   ```
   Moderator: apikey
   Bot: ✅ Your API key: abc123def456ghi789jkl012mno345pqr
        
        ⚠️ IMPORTANT: Save this key securely!
        This is the ONLY time you'll see the full key.
        
        [usage instructions]
   ```

2. **Duplicate Key Request**

   ```
   Moderator: apikey
   Bot: You already have an active API key (created 2025-11-10 14:30 UTC).
        Last used: Never
        
        To regenerate your key, use: apikey-regenerate
        [etc]
   ```

3. **Key Regeneration**

   ```
   Moderator: apikey-regenerate
   Bot: ✅ Your NEW API key: xyz789uvw456rst123opq890lmn567abc
        
        ⚠️ Your old key has been revoked and will no longer work.
        [etc]
   ```

4. **Key Revocation**

   ```
   Moderator: apikey-revoke
   Bot: ✅ Your API key has been revoked.
        All API requests with your old key will now fail.
        
        To create a new key, use: apikey
   ```

5. **Info Command**

   ```
   Moderator: apikey-info
   Bot: API Key Status: Active
        Created: 2025-11-10 14:30 UTC
        Last Used: Never
        
        Commands:
          apikey-regenerate - Generate new key
          apikey-revoke - Disable API access
   ```

6. **Help Command**

   ```
   Moderator: help
   Bot: [Shows all commands including API key commands in "API Access" section]
   ```

**Note:** Non-moderators (rank < 2.0) will receive no response as per existing `handle_pm_command` behavior.

### Database Verification

After each operation, verify database state:

```sql
-- Check API keys
SELECT username, created_at, last_used, revoked 
FROM api_keys;

-- Verify hash is stored (not plaintext)
SELECT username, 
       length(key_hash) as hash_length,
       key_hash LIKE '$2b$%' as is_bcrypt
FROM api_keys;
```

### Unit Tests (Optional for this Sprint)

```python
# test_api_key_utils.py
import pytest
from common.api_key_utils import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    create_api_key_pair
)

def test_generate_api_key():
    key = generate_api_key()
    assert len(key) == 32
    assert all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in key)

def test_hash_api_key():
    key = "test-key-123"
    hash1 = hash_api_key(key)
    hash2 = hash_api_key(key)
    
    assert hash1 != hash2  # Different salts
    assert hash1.startswith('$2b$')  # bcrypt format
    assert len(hash1) == 60  # bcrypt hash length

def test_verify_api_key():
    key = "test-key-456"
    key_hash = hash_api_key(key)
    
    assert verify_api_key(key, key_hash) == True
    assert verify_api_key("wrong-key", key_hash) == False

def test_create_api_key_pair():
    key, key_hash = create_api_key_pair()
    
    assert len(key) == 32
    assert verify_api_key(key, key_hash) == True
```

---

## Success Criteria

- ✅ Non-moderators cannot request API keys (rank check works)
- ✅ Moderators can request API key via `!apikey`
- ✅ API keys are 32 characters, URL-safe
- ✅ API keys are hashed with bcrypt before storage
- ✅ Plaintext keys are never stored in database
- ✅ Duplicate `!apikey` requests show existing key info (don't reveal key)
- ✅ `!apikey-regenerate` creates new key and revokes old one
- ✅ `!apikey-revoke` disables API access
- ✅ `!apikey-info` shows status without revealing key
- ✅ `!help` includes API key commands for moderators
- ✅ All commands send responses via PM (not in channel)

---

## Security Considerations

1. **Key Storage:** Keys hashed with bcrypt (12 rounds), never stored plaintext
2. **Key Transmission:** Keys only shown once via PM (secure channel)
3. **Key Length:** 32 characters provides ~191 bits of entropy
4. **Revocation:** Instant via database flag check
5. **Audit Trail:** All key operations should be logged (future enhancement)

---

## User Experience Notes

- Keys are shown once to encourage users to save them securely
- Clear instructions provided in every response
- Commands use kebab-case for consistency (`!apikey-regenerate`)
- Error messages are helpful and guide users to correct action
- Status command shows last usage to help users identify stale keys

---

## Future Enhancements

- Email key to user (if email configured)
- Key expiration (90 days, renewable)
- Multiple keys per user (with labels: "laptop", "automation", etc.)
- Admin command to revoke any user's key
- Audit log showing key operations

---

## Rollback Plan

If issues arise:
1. Remove API key commands from `pm_commands.py`
2. Remove `common/api_key_utils.py`
3. Keys remain in database but are inaccessible
4. No API endpoints exist yet, so no functionality is broken
