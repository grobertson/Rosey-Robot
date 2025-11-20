# SPEC: Database Schema for API Keys

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 1 - Database Schema  
**Dependencies:** None  
**Estimated Effort:** Small

---

## Objective

Create PostgreSQL schema to support API key storage and audit logging. This provides the data layer for API authentication before implementing the API itself.

---

## Changes Required

### 1. Database Migration Script

**File:** `common/migrations/003_api_keys.sql` (new)

```sql
-- API Keys table
-- Stores hashed API keys mapped to moderator usernames
CREATE TABLE IF NOT EXISTS api_keys (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP
);

CREATE INDEX idx_api_keys_username ON api_keys(username);
CREATE INDEX idx_api_keys_revoked ON api_keys(revoked);

-- API Audit Log table
-- Tracks all API requests for security and debugging
CREATE TABLE IF NOT EXISTS api_audit_log (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(500) NOT NULL,
    status_code INT NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_audit_log_username ON api_audit_log(username);
CREATE INDEX idx_api_audit_log_timestamp ON api_audit_log(timestamp);
CREATE INDEX idx_api_audit_log_status ON api_audit_log(status_code);

-- Comments
COMMENT ON TABLE api_keys IS 'API authentication keys for moderators';
COMMENT ON COLUMN api_keys.key_hash IS 'bcrypt hash of API key (never store plaintext)';
COMMENT ON COLUMN api_keys.last_used IS 'Last successful API request timestamp';
COMMENT ON COLUMN api_keys.revoked IS 'Whether key has been revoked';

COMMENT ON TABLE api_audit_log IS 'Audit trail of all API requests';
COMMENT ON COLUMN api_audit_log.username IS 'Moderator who made the request';
COMMENT ON COLUMN api_audit_log.ip_address IS 'Source IP address';
```

### 2. Database Helper Functions

**File:** `common/database.py` (update)

Add methods to existing Database class:

```python
async def create_api_key(self, username: str, key_hash: str) -> bool:
    """
    Create or update API key for a moderator.
    
    Args:
        username: CyTube moderator username
        key_hash: bcrypt hash of the API key
        
    Returns:
        True if successful
    """
    query = """
        INSERT INTO api_keys (username, key_hash, created_at)
        VALUES ($1, $2, CURRENT_TIMESTAMP)
        ON CONFLICT (username) 
        DO UPDATE SET 
            key_hash = $2,
            created_at = CURRENT_TIMESTAMP,
            revoked = FALSE,
            revoked_at = NULL
    """
    await self.execute(query, username, key_hash)
    return True

async def get_api_key_hash(self, username: str) -> Optional[str]:
    """
    Get hashed API key for username.
    
    Args:
        username: CyTube moderator username
        
    Returns:
        bcrypt hash if key exists and not revoked, None otherwise
    """
    query = """
        SELECT key_hash 
        FROM api_keys 
        WHERE username = $1 AND revoked = FALSE
    """
    row = await self.fetchrow(query, username)
    return row['key_hash'] if row else None

async def revoke_api_key(self, username: str) -> bool:
    """
    Revoke API key for a moderator.
    
    Args:
        username: CyTube moderator username
        
    Returns:
        True if key was revoked, False if no key existed
    """
    query = """
        UPDATE api_keys 
        SET revoked = TRUE, revoked_at = CURRENT_TIMESTAMP
        WHERE username = $1 AND revoked = FALSE
    """
    result = await self.execute(query, username)
    return result != "UPDATE 0"

async def update_api_key_last_used(self, username: str) -> None:
    """
    Update last_used timestamp for API key.
    
    Args:
        username: CyTube moderator username
    """
    query = """
        UPDATE api_keys 
        SET last_used = CURRENT_TIMESTAMP
        WHERE username = $1
    """
    await self.execute(query, username)

async def log_api_request(
    self,
    username: str,
    method: str,
    path: str,
    status_code: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """
    Log API request to audit trail.
    
    Args:
        username: Moderator who made the request
        method: HTTP method (GET, POST, etc.)
        path: Request path
        status_code: HTTP status code
        ip_address: Source IP address
        user_agent: User agent string
    """
    query = """
        INSERT INTO api_audit_log 
        (username, method, path, status_code, ip_address, user_agent, timestamp)
        VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
    """
    await self.execute(
        query,
        username,
        method,
        path,
        status_code,
        ip_address,
        user_agent
    )

async def get_api_key_info(self, username: str) -> Optional[dict]:
    """
    Get API key information for a moderator.
    
    Args:
        username: CyTube moderator username
        
    Returns:
        Dict with created_at, last_used, revoked, or None if no key
    """
    query = """
        SELECT created_at, last_used, revoked, revoked_at
        FROM api_keys
        WHERE username = $1
    """
    row = await self.fetchrow(query, username)
    return dict(row) if row else None
```

### 3. Migration Runner Update

**File:** `common/database.py` (update)

Update the migration runner to execute new migration:

```python
async def run_migrations(self) -> None:
    """Run all pending database migrations."""
    migrations = [
        'common/migrations/001_initial.sql',
        'common/migrations/002_playlist.sql',
        'common/migrations/003_api_keys.sql',  # Add this
    ]
    
    for migration_file in migrations:
        if os.path.exists(migration_file):
            with open(migration_file, 'r') as f:
                sql = f.read()
                await self.execute(sql)
                print(f"Executed migration: {migration_file}")
```

---

## Testing Checklist

### Manual Tests

1. **Migration Execution**
   ```python
   # In Python REPL or test script
   from common.database import Database
   db = Database()
   await db.connect()
   await db.run_migrations()
   # Should execute without errors
   ```

2. **Create API Key**
   ```python
   import bcrypt
   key_hash = bcrypt.hashpw(b"test-key", bcrypt.gensalt()).decode()
   await db.create_api_key("testuser", key_hash)
   # Verify in database: SELECT * FROM api_keys;
   ```

3. **Get API Key Hash**
   ```python
   hash_value = await db.get_api_key_hash("testuser")
   assert hash_value is not None
   assert bcrypt.checkpw(b"test-key", hash_value.encode())
   ```

4. **Revoke API Key**
   ```python
   result = await db.revoke_api_key("testuser")
   assert result == True
   hash_after = await db.get_api_key_hash("testuser")
   assert hash_after is None  # Revoked keys return None
   ```

5. **Log API Request**
   ```python
   await db.log_api_request(
       "testuser",
       "GET",
       "/api/v1/status",
       200,
       "192.168.1.100",
       "curl/7.68.0"
   )
   # Verify in database: SELECT * FROM api_audit_log;
   ```

6. **Update Last Used**
   ```python
   # Create fresh key
   await db.create_api_key("testuser2", key_hash)
   info_before = await db.get_api_key_info("testuser2")
   assert info_before['last_used'] is None
   
   await db.update_api_key_last_used("testuser2")
   info_after = await db.get_api_key_info("testuser2")
   assert info_after['last_used'] is not None
   ```

### Database Verification

```sql
-- Verify tables created
\dt

-- Check table structures
\d api_keys
\d api_audit_log

-- Verify indexes
\di

-- Check constraints
SELECT conname, contype 
FROM pg_constraint 
WHERE conrelid = 'api_keys'::regclass;
```

---

## Success Criteria

- ✅ Migration script executes without errors
- ✅ Tables `api_keys` and `api_audit_log` created with correct schema
- ✅ All indexes created successfully
- ✅ Database helper methods work correctly
- ✅ Can create, retrieve, and revoke API keys
- ✅ Audit logging functions properly
- ✅ Unique constraint on username enforced
- ✅ Revoked keys return None from get_api_key_hash

---

## Notes

- Migration is idempotent (uses `IF NOT EXISTS`)
- bcrypt hashing will be implemented in next commit
- No API endpoints yet - this is data layer only
- Consider adding retention policy for audit logs (future enhancement)

---

## Rollback Plan

If issues arise:

```sql
-- Rollback migration
DROP TABLE IF EXISTS api_audit_log;
DROP TABLE IF EXISTS api_keys;
```

Remove migration from `run_migrations()` list in `common/database.py`.
