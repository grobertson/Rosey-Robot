# Product Requirements Document: REST API Migration

**Sprint:** nano-sprint/3-rest-assured  
**Status:** Planning  
**Date:** November 10, 2025  
**Version:** 1.0

---

## Executive Summary

Replace the legacy REPL shell interface with a modern FastAPI-based REST API to provide programmatic bot control from the local network. This migration removes the telnet-accessible shell in favor of a more secure, standardized, and automatable HTTP API with API key authentication tied to moderator accounts.

---

## Objectives

### Primary Goals
1. **Remove Legacy Shell:** Sunset `common/shell.py` and the telnet-accessible REPL interface
2. **Implement FastAPI:** Create modern REST API with OpenAPI/Swagger documentation
3. **API Key Authentication:** Secure endpoints with API keys mapped to moderator usernames
4. **Bot Command Interface:** Enable programmatic bot control (chat messages, playlist management, system commands)
5. **Bulk Operations:** Support bulk playlist loading via API
6. **Self-Service Key Management:** Allow moderators to request/regenerate API keys via PM

### Secondary Goals
- OpenAPI/Swagger auto-documentation
- Generated markdown API reference
- Postman collection examples
- cURL command examples
- Command-line utility for common operations

---

## Background

### Current State
- Bot exposes REPL shell via `common/shell.py` accessible through telnet
- Shell provides interactive Python environment for bot management
- `test_shell.py` demonstrates shell usage
- PM command interface exists for basic bot control
- Web status dashboard (`web/status_server.py`) provides read-only monitoring

### Problems with Current Approach
1. **Security:** Telnet-accessible Python REPL is inherently risky
2. **Automation:** Interactive shell difficult to script/automate
3. **Documentation:** No formal API contract or documentation
4. **Scalability:** Not suitable for programmatic access or integration
5. **Maintainability:** Shell code is separate from bot logic, increasing maintenance burden

### Why REST API?
- **Industry Standard:** HTTP REST is universal, well-understood
- **Tooling:** Rich ecosystem (Postman, curl, SDKs, client libraries)
- **Documentation:** OpenAPI/Swagger provides self-documenting contracts
- **Security:** API key authentication is simple, auditable
- **Automation:** Easy to script with any language/tool
- **Network Ready:** Works seamlessly over local network (and internet when needed)

---

## User Stories

### US-1: As a Bot Administrator
**I want to** send commands to the bot via REST API  
**So that** I can automate bot operations without using an interactive shell  
**Acceptance Criteria:**
- API accepts authenticated requests via API key in HTTP header
- Can send chat messages to the channel
- Can execute administrative commands (warn of reboot, status checks)
- Returns clear success/error responses

### US-2: As a Moderator
**I want to** bulk-load a playlist from a file  
**So that** I can quickly populate the queue without manual entry  
**Acceptance Criteria:**
- API endpoint accepts playlist data (array of media URLs/IDs)
- Validates media links before adding
- Returns summary of successful/failed additions
- Supports large playlists (100+ items)

### US-3: As a Developer
**I want to** view OpenAPI documentation  
**So that** I can understand available endpoints without reading code  
**Acceptance Criteria:**
- Swagger UI available at `/docs` endpoint
- OpenAPI schema available at `/openapi.json`
- All endpoints documented with parameters, responses, examples
- Markdown reference generated from OpenAPI schema

### US-4: As a Moderator
**I want to** request my API key via PM  
**So that** I can access the API without administrator assistance  
**Acceptance Criteria:**
- Can PM bot with command like `!apikey` or `!api-key-request`
- Bot generates unique API key tied to username
- Bot sends key via PM (secure, not in channel)
- Can regenerate key if compromised
- Non-moderators receive appropriate error message

### US-5: As a System Operator
**I want to** use curl or Postman to test API endpoints  
**So that** I can verify API functionality and create example requests  
**Acceptance Criteria:**
- Postman collection with example requests for all endpoints
- Documented curl commands for common operations
- Examples include authentication headers
- Can import Postman collection and run immediately

---

## Functional Requirements

### FR-1: FastAPI Application
- **FR-1.1:** Create new FastAPI application in `web/api_server.py`
- **FR-1.2:** Implement async endpoints matching bot's async architecture
- **FR-1.3:** Enable CORS for local network access (configurable origins)
- **FR-1.4:** Serve OpenAPI schema at `/openapi.json`
- **FR-1.5:** Serve Swagger UI at `/docs`
- **FR-1.6:** Serve ReDoc at `/redoc` (alternative documentation view)

### FR-2: Authentication System
- **FR-2.1:** Implement API key authentication middleware
- **FR-2.2:** Store API keys in database with moderator username mapping
- **FR-2.3:** Accept API key via `X-API-Key` HTTP header
- **FR-2.4:** Return 401 Unauthorized for missing/invalid keys
- **FR-2.5:** Return 403 Forbidden if key exists but user lacks permissions
- **FR-2.6:** Log all API requests with username for audit trail

### FR-3: API Key Management
- **FR-3.1:** Implement PM command `!apikey` to request key
- **FR-3.2:** Implement PM command `!apikey-regenerate` to regenerate key
- **FR-3.3:** Implement PM command `!apikey-revoke` to revoke key
- **FR-3.4:** Verify user is moderator before generating key
- **FR-3.5:** Generate secure random keys (32+ characters, URL-safe)
- **FR-3.6:** Store hashed keys in database (never plaintext)
- **FR-3.7:** Send plaintext key to user once via PM, then discard

### FR-4: Bot Command Endpoints

#### FR-4.1: Send Message
```
POST /api/v1/chat/send
Body: {"message": "string"}
Response: {"success": bool, "timestamp": "ISO8601"}
```
- Send message to channel as bot
- Respects rate limiting
- Returns error if bot disconnected

#### FR-4.2: System Announcement
```
POST /api/v1/system/announce
Body: {"message": "string", "priority": "normal|high"}
Response: {"success": bool, "timestamp": "ISO8601"}
```
- Send formatted system message (e.g., "Server reboot in 5 minutes")
- High priority messages may use visual styling

#### FR-4.3: Bot Status
```
GET /api/v1/status
Response: {
  "connected": bool,
  "uptime_seconds": int,
  "current_users": int,
  "queue_length": int,
  "current_media": {title, duration, time_elapsed}
}
```
- Return current bot/channel status
- Include connection state, runtime stats

### FR-5: Playlist Management Endpoints

#### FR-5.1: Add Single Media
```
POST /api/v1/playlist/add
Body: {"url": "string", "position": "end|next|int"}
Response: {"success": bool, "media": {id, title, duration}}
```

#### FR-5.2: Bulk Add Media
```
POST /api/v1/playlist/bulk-add
Body: {
  "items": [
    {"url": "string", "position": "end"},
    ...
  ]
}
Response: {
  "success": bool,
  "added": int,
  "failed": int,
  "errors": [{url, reason}]
}
```
- Process up to 200 items per request
- Validate all URLs before adding
- Return detailed results for each item
- Continue processing even if some items fail

#### FR-5.3: Get Playlist
```
GET /api/v1/playlist
Response: {
  "items": [{id, title, duration, user, position}],
  "total": int
}
```

#### FR-5.4: Remove Media
```
DELETE /api/v1/playlist/{media_id}
Response: {"success": bool}
```

#### FR-5.5: Clear Playlist
```
DELETE /api/v1/playlist
Response: {"success": bool, "removed": int}
```
- Requires additional confirmation parameter
- Admin-only endpoint

### FR-6: Shell Removal
- **FR-6.1:** Remove `common/shell.py`
- **FR-6.2:** Remove `test_shell.py`
- **FR-6.3:** Remove shell-related dependencies from `requirements.txt`
- **FR-6.4:** Remove shell documentation from README.md
- **FR-6.5:** Update CHANGELOG.md to note shell deprecation

### FR-7: Command-Line Utility
- **FR-7.1:** Create `tools/rosey-cli.py` command-line tool
- **FR-7.2:** Support commands: `send`, `announce`, `playlist-add`, `playlist-bulk`
- **FR-7.3:** Load API key from environment variable or config file
- **FR-7.4:** Provide `--help` documentation for all commands
- **FR-7.5:** Return appropriate exit codes (0=success, 1=error)

Example usage:
```bash
# Send message
rosey-cli send "Hello everyone!"

# Bulk load playlist
rosey-cli playlist-bulk playlist.txt

# Announce reboot
rosey-cli announce "Server reboot in 5 minutes" --priority high
```

---

## Non-Functional Requirements

### NFR-1: Performance
- API response time < 200ms for simple operations (status, send message)
- Bulk playlist operations < 5 seconds for 100 items
- Support 10+ concurrent API requests

### NFR-2: Security
- All API keys stored as bcrypt hashes (never plaintext)
- Keys minimum 32 characters, URL-safe base64
- Rate limiting: 100 requests/minute per API key
- HTTPS recommended for production (documentation note)
- No API functionality exposed without valid key

### NFR-3: Reliability
- API server runs independently of bot (separate process)
- API server restart doesn't affect bot
- Bot restart doesn't affect API server
- Graceful error handling for all endpoints
- Database connection pooling for concurrent requests

### NFR-4: Documentation
- 100% endpoint coverage in OpenAPI schema
- Every endpoint has description, parameters, response examples
- Postman collection includes all endpoints with working examples
- cURL examples for common workflows
- CLI tool has comprehensive `--help` output

### NFR-5: Maintainability
- Type hints for all Python functions
- Pydantic models for request/response validation
- Consistent error response format across all endpoints
- Logging for all API requests (method, path, user, status)

---

## Technical Architecture

### Components

```
┌─────────────────────────────────────────────────┐
│                   Moderators                    │
│          (PM Commands, API Clients)             │
└────────────┬────────────────────┬───────────────┘
             │                    │
             │ PM Commands        │ HTTP/REST
             │                    │
┌────────────▼────────────┐  ┌───▼──────────────────┐
│    CyTube Bot Process   │  │  FastAPI Server      │
│  (bot/rosey/rosey.py)   │  │  (web/api_server.py) │
│                         │  │                      │
│  - PM Handler           │  │  - Auth Middleware   │
│  - API Key Management   │  │  - REST Endpoints    │
│  - Bot Commands         │  │  - OpenAPI/Swagger   │
└────────────┬────────────┘  └───┬──────────────────┘
             │                    │
             │     Database       │
             └────────▼───────────┘
           ┌──────────────────────┐
           │   PostgreSQL         │
           │  - api_keys table    │
           │  - audit_log table   │
           └──────────────────────┘
```

### Database Schema

#### New Table: `api_keys`
```sql
CREATE TABLE api_keys (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP
);

CREATE INDEX idx_api_keys_username ON api_keys(username);
```

#### New Table: `api_audit_log`
```sql
CREATE TABLE api_audit_log (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    path VARCHAR(500) NOT NULL,
    status_code INT NOT NULL,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_audit_log_username ON api_audit_log(username);
CREATE INDEX idx_api_audit_log_timestamp ON api_audit_log(timestamp);
```

### Technology Stack
- **FastAPI:** Modern async web framework
- **Pydantic:** Request/response validation
- **bcrypt:** API key hashing
- **uvicorn:** ASGI server
- **httpx:** HTTP client for CLI tool

### Dependencies to Add
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
bcrypt>=4.1.0
httpx>=0.25.0
```

---

## API Endpoint Summary

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/docs` | Swagger UI | No |
| GET | `/redoc` | ReDoc UI | No |
| GET | `/openapi.json` | OpenAPI schema | No |
| GET | `/api/v1/status` | Bot status | Yes |
| POST | `/api/v1/chat/send` | Send message | Yes |
| POST | `/api/v1/system/announce` | System announcement | Yes |
| GET | `/api/v1/playlist` | Get playlist | Yes |
| POST | `/api/v1/playlist/add` | Add media | Yes |
| POST | `/api/v1/playlist/bulk-add` | Bulk add media | Yes |
| DELETE | `/api/v1/playlist/{media_id}` | Remove media | Yes |
| DELETE | `/api/v1/playlist` | Clear playlist | Yes |

---

## Success Metrics

### Must Have
- ✅ All shell functionality available via REST API
- ✅ Shell code removed from codebase
- ✅ API key authentication working
- ✅ PM commands for key management functional
- ✅ OpenAPI documentation auto-generated
- ✅ Bulk playlist endpoint handles 100+ items
- ✅ CLI tool supports basic operations

### Should Have
- ✅ Postman collection with all endpoints
- ✅ cURL examples documented
- ✅ Markdown API reference generated
- ✅ Rate limiting implemented
- ✅ Audit logging for all requests

### Nice to Have
- 🎯 CLI tool with bash/zsh completion
- 🎯 Python SDK for API (separate package)
- 🎯 Metrics endpoint for monitoring
- 🎯 WebSocket endpoint for real-time events

---

## Migration Plan

### Phase 1: Foundation
1. Create FastAPI application structure
2. Implement authentication middleware
3. Create database schema and migrations
4. Implement PM commands for API key management

### Phase 2: Core Endpoints
1. Implement status endpoint
2. Implement chat/send endpoint
3. Implement system/announce endpoint
4. Add comprehensive error handling

### Phase 3: Playlist Management
1. Implement single add endpoint
2. Implement bulk add endpoint
3. Implement get/remove/clear endpoints
4. Add validation and rate limiting

### Phase 4: Tooling & Documentation
1. Generate OpenAPI schema
2. Create Postman collection
3. Write cURL examples
4. Build CLI tool
5. Generate markdown API reference

### Phase 5: Shell Removal
1. Verify all shell functionality covered by API
2. Remove shell code
3. Update documentation
4. Update systemd configuration

### Phase 6: Deployment
1. Update systemd service files
2. Create deployment guide
3. Test in production environment
4. Create rollback plan

---

## Risks & Mitigations

### Risk: Breaking Existing Workflows
**Impact:** High  
**Probability:** Medium  
**Mitigation:** Document shell-to-API command mapping. Provide CLI tool as drop-in replacement.

### Risk: API Key Compromise
**Impact:** High  
**Probability:** Low  
**Mitigation:** Keys are hashed, can be revoked instantly. Audit logging tracks usage. Rate limiting prevents abuse.

### Risk: API Server Downtime Affects Bot
**Impact:** Medium  
**Probability:** Low  
**Mitigation:** API and bot run as separate processes. Bot continues functioning if API crashes.

### Risk: Bulk Operations Overload Bot
**Impact:** Medium  
**Probability:** Medium  
**Mitigation:** Rate limiting on bulk endpoint. Maximum items per request. Queue processing with feedback.

---

## Future Enhancements

1. **WebSocket Support:** Real-time channel events (new messages, playlist changes)
2. **API Analytics:** Dashboard showing API usage patterns, popular endpoints
3. **Multi-Bot Support:** Single API server controlling multiple bot instances
4. **Advanced Permissions:** Role-based access control beyond moderator/non-moderator
5. **API Versioning:** Support multiple API versions simultaneously
6. **Python SDK:** Published package for easy integration
7. **Rate Limiting Tiers:** Different limits for different users/use cases
8. **Webhook Support:** Push notifications for events to external services

---

## Appendix A: Example Requests

### Send Message
```bash
curl -X POST http://localhost:8080/api/v1/chat/send \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from the API!"}'
```

### Bulk Add Playlist
```bash
curl -X POST http://localhost:8080/api/v1/playlist/bulk-add \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
      {"url": "https://youtube.com/watch?v=9bZkp7q19f0"},
      {"url": "https://youtube.com/watch?v=kJQP7kiw5Fk"}
    ]
  }'
```

### Get Status
```bash
curl -X GET http://localhost:8080/api/v1/status \
  -H "X-API-Key: your-api-key-here"
```

---

## Appendix B: CLI Tool Usage

```bash
# Configure API key (one-time setup)
export ROSEY_API_KEY="your-api-key-here"
# or
echo "your-api-key-here" > ~/.rosey-api-key

# Send a message
rosey-cli send "Hello everyone!"

# System announcement
rosey-cli announce "Server reboot in 5 minutes" --priority high

# Add single video
rosey-cli playlist add "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Bulk add from file (one URL per line)
rosey-cli playlist bulk playlist.txt

# Get current status
rosey-cli status

# Get current playlist
rosey-cli playlist list
```

---

## Appendix C: PM Commands

```
User: !apikey
Bot: Your API key: abc123def456ghi789jkl012mno345pqr
     Keep this secret! Use it in the X-API-Key header.
     API Documentation: http://localhost:8080/docs

User: !apikey-regenerate
Bot: Your new API key: xyz789uvw456rst123opq890lmn567abc
     Your old key has been revoked and will no longer work.

User: !apikey-revoke
Bot: Your API key has been revoked. Use !apikey to generate a new one.

Non-Moderator: !apikey
Bot: Sorry, API access is only available to moderators.
```

---

## Sign-off

**Product Owner:** [Your Name]  
**Technical Lead:** GitHub Copilot  
**Sprint Goal:** Replace legacy shell with modern REST API for programmatic bot control

**Approved:** ⬜ Yes  ⬜ No  ⬜ Needs Revision

---

*End of PRD*
