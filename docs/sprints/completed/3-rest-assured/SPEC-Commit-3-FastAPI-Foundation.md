# SPEC: FastAPI Application Foundation

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 3 - FastAPI Foundation  
**Dependencies:** Commit 1 (Database Schema), Commit 2 (PM Key Management)  
**Estimated Effort:** Medium

---

## Objective

Create the FastAPI application structure with authentication middleware, basic endpoints, and OpenAPI documentation. This establishes the foundation for all REST API functionality.

---

## Changes Required

### 1. FastAPI Application

**File:** `web/api_server.py` (new)

```python
"""
FastAPI server for Rosey bot REST API.
Provides programmatic access to bot functionality with API key authentication.
"""
from typing import Optional, Annotated
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import asyncio

from common.database import Database
from common.api_key_utils import verify_api_key
from common.config import load_config


# ============================================================================
# Pydantic Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Standard success response format."""
    success: bool = Field(..., description="Whether operation succeeded")
    message: Optional[str] = Field(None, description="Optional success message")


class StatusResponse(BaseModel):
    """Bot status information."""
    connected: bool = Field(..., description="Whether bot is connected to CyTube")
    uptime_seconds: int = Field(..., description="Bot uptime in seconds")
    api_version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current server time (ISO 8601)")


# ============================================================================
# Application Setup
# ============================================================================

app = FastAPI(
    title="Rosey Bot API",
    description=(
        "REST API for programmatic control of Rosey CyTube bot. "
        "Provides endpoints for chat, playlist management, and status monitoring. "
        "Authentication required via X-API-Key header."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Global state
db: Optional[Database] = None
config: Optional[dict] = None
bot_start_time: Optional[datetime] = None


# ============================================================================
# CORS Configuration
# ============================================================================

# Allow access from local network
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this based on config file
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Authentication Middleware
# ============================================================================

async def verify_auth(
    x_api_key: Annotated[Optional[str], Header()] = None
) -> str:
    """
    Verify API key and return username.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        Username associated with the API key
        
    Raises:
        HTTPException: If authentication fails
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header. Include your API key in the request.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Get all non-revoked API keys and check each one
    # This is a simple implementation; could be optimized with caching
    query = "SELECT username, key_hash FROM api_keys WHERE revoked = FALSE"
    rows = await db.fetch(query)
    
    for row in rows:
        if verify_api_key(x_api_key, row['key_hash']):
            username = row['username']
            # Update last_used timestamp
            await db.update_api_key_last_used(username)
            return username
    
    # No matching key found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key. Use !apikey in PM to get your key.",
        headers={"WWW-Authenticate": "ApiKey"},
    )


# ============================================================================
# Logging Middleware
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all API requests to audit trail."""
    start_time = datetime.utcnow()
    
    # Extract API key for logging (if present)
    api_key = request.headers.get("x-api-key")
    username = None
    
    if api_key:
        # Try to identify user (without full verification)
        try:
            query = "SELECT username, key_hash FROM api_keys WHERE revoked = FALSE"
            rows = await db.fetch(query)
            for row in rows:
                if verify_api_key(api_key, row['key_hash']):
                    username = row['username']
                    break
        except Exception:
            pass  # Don't let logging break the request
    
    # Process request
    response = await call_next(request)
    
    # Log to audit trail
    if username:
        try:
            await db.log_api_request(
                username=username,
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent"),
            )
        except Exception as e:
            print(f"Failed to log API request: {e}")
    
    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standardize HTTP exception responses."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "detail": None
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    print(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal server error",
            "detail": "An unexpected error occurred. Please try again."
        }
    )


# ============================================================================
# Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    global db, config, bot_start_time
    
    print("Starting Rosey API server...")
    
    # Load configuration
    config = load_config("bot/rosey/config.json")
    
    # Connect to database
    db = Database(config.get('database', {}))
    await db.connect()
    
    bot_start_time = datetime.utcnow()
    
    print("API server ready!")
    print(f"Documentation: http://localhost:8080/docs")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up database connection on shutdown."""
    global db
    
    print("Shutting down API server...")
    
    if db:
        await db.disconnect()
    
    print("API server stopped.")


# ============================================================================
# Public Endpoints (No Authentication)
# ============================================================================

@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API documentation."""
    return {
        "message": "Rosey Bot API",
        "documentation": "/docs",
        "openapi_schema": "/openapi.json"
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    
    Returns basic service health without requiring authentication.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "api_version": "1.0.0"
    }


# ============================================================================
# Status Endpoints
# ============================================================================

@app.get(
    "/api/v1/status",
    response_model=StatusResponse,
    summary="Get bot status",
    description="Returns current bot status including connection state and uptime.",
    tags=["Status"]
)
async def get_status(
    username: Annotated[str, Header()] = Header(None, include_in_schema=False, alias="x-api-key")
):
    """Get current bot status."""
    # Use dependency injection for auth
    username = await verify_auth(username)
    
    uptime = (datetime.utcnow() - bot_start_time).total_seconds()
    
    return StatusResponse(
        connected=True,  # TODO: Get actual bot connection status
        uptime_seconds=int(uptime),
        api_version="1.0.0",
        timestamp=datetime.utcnow().isoformat()
    )


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Run the API server."""
    uvicorn.run(
        "web.api_server:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
        reload=False  # Set to True for development
    )


if __name__ == "__main__":
    main()
```

### 2. Configuration Update

**File:** `bot/rosey/config.json.dist` (update)

Add API server configuration section:

```json
{
  "existing": "config...",
  
  "api": {
    "enabled": true,
    "host": "0.0.0.0",
    "port": 8080,
    "cors_origins": ["http://localhost:3000", "http://192.168.1.0/24"],
    "rate_limit_per_minute": 100
  }
}
```

### 3. Dependencies Update

**File:** `requirements.txt` (update)

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6
```

### 4. Systemd Service File

**File:** `systemd/rosey-api.service` (new)

```ini
[Unit]
Description=Rosey Bot REST API Server
Documentation=https://github.com/grobertson/Rosey-Robot
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=cytube
Group=cytube
WorkingDirectory=/opt/rosey-robot
ExecStart=/opt/rosey-robot/.venv/bin/python -m web.api_server

# Restart configuration
Restart=always
RestartSec=10
StartLimitBurst=5
StartLimitIntervalSec=60

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/rosey-robot/logs

# Resource limits
LimitNOFILE=65536

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=rosey-api

[Install]
WantedBy=multi-user.target
```

### 5. API Server Launcher Script

**File:** `run_api_server.sh` (new)

```bash
#!/bin/bash
# Launch script for Rosey API server

cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Run API server
python -m web.api_server
```

**File:** `run_api_server.bat` (new)

```batch
@echo off
REM Launch script for Rosey API server (Windows)

cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Run API server
python -m web.api_server
pause
```

---

## Testing Checklist

### Manual Tests

1. **Server Startup**
   ```bash
   python -m web.api_server
   # Should start without errors
   # Should print "API server ready!"
   # Should show documentation URL
   ```

2. **Health Check (No Auth)**
   ```bash
   curl http://localhost:8080/health
   # Expected: {"status": "healthy", "timestamp": "...", "api_version": "1.0.0"}
   ```

3. **Documentation Access**
   - Open browser to http://localhost:8080/docs
   - Should see Swagger UI with API documentation
   - Open browser to http://localhost:8080/redoc
   - Should see ReDoc alternative documentation

4. **OpenAPI Schema**
   ```bash
   curl http://localhost:8080/openapi.json
   # Should return OpenAPI 3.0 JSON schema
   ```

5. **Missing API Key**
   ```bash
   curl http://localhost:8080/api/v1/status
   # Expected: 401 Unauthorized
   # {"error": "Missing X-API-Key header..."}
   ```

6. **Invalid API Key**
   ```bash
   curl -H "X-API-Key: invalid-key" http://localhost:8080/api/v1/status
   # Expected: 401 Unauthorized
   # {"error": "Invalid API key..."}
   ```

7. **Valid API Key**
   ```bash
   # First, get API key via PM: !apikey
   curl -H "X-API-Key: your-actual-key" http://localhost:8080/api/v1/status
   # Expected: 200 OK
   # {
   #   "connected": true,
   #   "uptime_seconds": 123,
   #   "api_version": "1.0.0",
   #   "timestamp": "2025-11-10T..."
   # }
   ```

8. **Audit Logging**
   ```sql
   -- After making API requests, verify logging
   SELECT * FROM api_audit_log ORDER BY timestamp DESC LIMIT 5;
   -- Should show recent API requests with username, method, path, status
   ```

9. **Last Used Update**
   ```sql
   -- Before API request
   SELECT username, last_used FROM api_keys WHERE username = 'testuser';
   -- last_used should be NULL or old timestamp
   
   -- Make API request with key
   
   -- After API request
   SELECT username, last_used FROM api_keys WHERE username = 'testuser';
   -- last_used should be updated to recent timestamp
   ```

### Interactive Testing with Swagger UI

1. Navigate to http://localhost:8080/docs
2. Click "Authorize" button in top right
3. Enter API key in `X-API-Key` field
4. Click "Authorize" then "Close"
5. Try the `/api/v1/status` endpoint
   - Click "Try it out"
   - Click "Execute"
   - Should see 200 response with status data

---

## Success Criteria

- ✅ FastAPI server starts without errors
- ✅ `/docs` shows Swagger UI with complete API documentation
- ✅ `/redoc` shows ReDoc documentation
- ✅ `/openapi.json` returns valid OpenAPI 3.0 schema
- ✅ `/health` endpoint works without authentication
- ✅ All authenticated endpoints require X-API-Key header
- ✅ Invalid/missing API keys return 401 Unauthorized
- ✅ Valid API keys are verified against database hashes
- ✅ Successful API requests update last_used timestamp
- ✅ All API requests logged to api_audit_log table
- ✅ Standard error response format used consistently
- ✅ CORS configured for local network access
- ✅ Server gracefully handles database connection issues

---

## API Documentation Notes

The OpenAPI schema automatically includes:
- All endpoint paths, methods, parameters
- Request/response models with field descriptions
- Authentication requirements (security scheme)
- Response status codes and error formats
- Example requests and responses

Users can:
- View documentation at `/docs` (Swagger) or `/redoc` (ReDoc)
- Download OpenAPI schema from `/openapi.json`
- Import schema into Postman, Insomnia, etc.
- Generate client SDKs using OpenAPI generators

---

## Architecture Notes

### Separation of Concerns

- **API Server:** Handles HTTP, authentication, logging
- **Bot:** Maintains CyTube connection, business logic
- **Database:** Shared data layer between API and bot

The API server runs independently of the bot:
- API can restart without affecting bot
- Bot can restart without affecting API
- Both can scale independently if needed

### Authentication Flow

1. Client sends request with `X-API-Key` header
2. Middleware extracts API key
3. Database lookup for non-revoked keys
4. bcrypt verification of key against each hash
5. On match, username extracted and last_used updated
6. Username available to endpoint handler
7. Request logged to audit trail

### Future Enhancements

- Redis caching for API key lookups (performance)
- Rate limiting per API key (prevent abuse)
- IP allowlisting per API key (additional security)
- API key scopes/permissions (read-only vs full access)
- WebSocket endpoints for real-time events

---

## Rollback Plan

If issues arise:
1. Stop API server: `systemctl stop rosey-api`
2. Remove systemd service: `systemctl disable rosey-api`
3. Bot continues to function normally
4. API key management via PM still works
5. Can restart API server once issues resolved

No data loss - database tables persist.
