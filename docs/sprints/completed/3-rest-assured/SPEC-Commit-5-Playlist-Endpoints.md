# SPEC: Playlist Management Endpoints

**Sprint:** nano-sprint/3-rest-assured  
**Commit:** 5 - Playlist Endpoints  
**Dependencies:** Commit 3 (FastAPI Foundation), Commit 4 (Chat Endpoints)  
**Estimated Effort:** Large

---

## Objective

Implement comprehensive playlist management API endpoints including single/bulk add, list, remove, and clear operations. This is the most complex commit with the bulk add endpoint being the primary use case.

---

## Changes Required

### 1. Bot Interface Updates

**File:** `web/bot_interface.py` (update)

Add playlist management methods:

```python
from typing import List, Dict, Optional


class BotInterface:
    """Interface for API to communicate with bot."""
    
    # ... existing methods ...
    
    async def get_playlist(self) -> List[Dict]:
        """
        Get current playlist.
        
        Returns:
            List of media items with metadata
        """
        if not self.bot or not self.bot.connected:
            return []
        
        try:
            playlist = await self.bot.channel.get_playlist()
            return [
                {
                    "id": item.uid,
                    "title": item.title,
                    "duration": item.seconds,
                    "user": item.queueby,
                    "position": idx
                }
                for idx, item in enumerate(playlist)
            ]
        except Exception as e:
            print(f"Error getting playlist: {e}")
            return []
    
    async def add_media(
        self,
        url: str,
        position: str = "end"
    ) -> Optional[Dict]:
        """
        Add single media item to playlist.
        
        Args:
            url: Media URL (YouTube, Vimeo, etc.)
            position: Where to add ('end', 'next', or numeric index)
            
        Returns:
            Media metadata if successful, None otherwise
        """
        if not self.bot or not self.bot.connected:
            return None
        
        try:
            # Add media to playlist
            media = await self.bot.channel.add_media(url, position)
            
            if media:
                return {
                    "id": media.uid,
                    "title": media.title,
                    "duration": media.seconds,
                    "url": url
                }
            return None
        except Exception as e:
            print(f"Error adding media: {e}")
            return None
    
    async def add_media_bulk(
        self,
        items: List[Dict[str, str]]
    ) -> Dict[str, any]:
        """
        Add multiple media items to playlist.
        
        Args:
            items: List of {url, position} dicts
            
        Returns:
            Dict with added count, failed count, and error details
        """
        if not self.bot or not self.bot.connected:
            return {
                "added": 0,
                "failed": len(items),
                "errors": [{"url": item["url"], "reason": "Bot not connected"} for item in items]
            }
        
        added = 0
        failed = 0
        errors = []
        
        for item in items:
            url = item.get("url")
            position = item.get("position", "end")
            
            try:
                result = await self.add_media(url, position)
                if result:
                    added += 1
                else:
                    failed += 1
                    errors.append({
                        "url": url,
                        "reason": "Failed to add media (invalid URL or unsupported type)"
                    })
                
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.1)
                
            except Exception as e:
                failed += 1
                errors.append({
                    "url": url,
                    "reason": str(e)
                })
        
        return {
            "added": added,
            "failed": failed,
            "errors": errors if errors else []
        }
    
    async def remove_media(self, media_id: str) -> bool:
        """
        Remove media item from playlist.
        
        Args:
            media_id: Media UID to remove
            
        Returns:
            True if removed successfully
        """
        if not self.bot or not self.bot.connected:
            return False
        
        try:
            await self.bot.channel.remove_media(media_id)
            return True
        except Exception as e:
            print(f"Error removing media: {e}")
            return False
    
    async def clear_playlist(self) -> int:
        """
        Remove all items from playlist.
        
        Returns:
            Number of items removed
        """
        if not self.bot or not self.bot.connected:
            return 0
        
        try:
            playlist = await self.get_playlist()
            count = len(playlist)
            
            for item in playlist:
                await self.remove_media(item["id"])
                await asyncio.sleep(0.05)  # Small delay
            
            return count
        except Exception as e:
            print(f"Error clearing playlist: {e}")
            return 0
```

### 2. API Endpoints for Playlist

**File:** `web/api_server.py` (update)

Add models and endpoints:

```python
# ============================================================================
# Pydantic Models - Playlist
# ============================================================================

class MediaItem(BaseModel):
    """Media item in playlist."""
    id: str = Field(..., description="Unique media ID")
    title: str = Field(..., description="Media title")
    duration: int = Field(..., description="Duration in seconds")
    user: str = Field(..., description="User who added the media")
    position: int = Field(..., description="Position in playlist (0-indexed)")


class PlaylistResponse(BaseModel):
    """Response containing playlist items."""
    items: List[MediaItem] = Field(..., description="Playlist items")
    total: int = Field(..., description="Total number of items")


class AddMediaRequest(BaseModel):
    """Request to add single media item."""
    url: str = Field(
        ...,
        description="Media URL (YouTube, Vimeo, etc.)",
        pattern=r"^https?://",
        example="https://youtube.com/watch?v=dQw4w9WgXcQ"
    )
    position: str = Field(
        "end",
        description="Where to add: 'end', 'next', or numeric index",
        example="end"
    )


class AddMediaResponse(BaseModel):
    """Response from add media endpoint."""
    success: bool = Field(..., description="Whether media was added")
    media: Optional[Dict] = Field(None, description="Media metadata if successful")


class BulkAddItem(BaseModel):
    """Single item for bulk add."""
    url: str = Field(
        ...,
        description="Media URL",
        pattern=r"^https?://",
        example="https://youtube.com/watch?v=dQw4w9WgXcQ"
    )
    position: str = Field(
        "end",
        description="Where to add: 'end', 'next', or numeric index",
        example="end"
    )


class BulkAddRequest(BaseModel):
    """Request to bulk add media items."""
    items: List[BulkAddItem] = Field(
        ...,
        description="List of media items to add (max 200)",
        min_items=1,
        max_items=200,
        example=[
            {"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "position": "end"},
            {"url": "https://youtube.com/watch?v=9bZkp7q19f0", "position": "end"}
        ]
    )


class BulkAddResponse(BaseModel):
    """Response from bulk add endpoint."""
    success: bool = Field(..., description="Overall success (true if any added)")
    added: int = Field(..., description="Number of items successfully added")
    failed: int = Field(..., description="Number of items that failed")
    errors: List[Dict] = Field([], description="Details of failed items")


class RemoveMediaResponse(BaseModel):
    """Response from remove media endpoint."""
    success: bool = Field(..., description="Whether media was removed")


class ClearPlaylistResponse(BaseModel):
    """Response from clear playlist endpoint."""
    success: bool = Field(..., description="Whether playlist was cleared")
    removed: int = Field(..., description="Number of items removed")


# ============================================================================
# Playlist Endpoints
# ============================================================================

@app.get(
    "/api/v1/playlist",
    response_model=PlaylistResponse,
    summary="Get playlist",
    description="Returns all items in the current playlist.",
    tags=["Playlist"]
)
async def get_playlist(
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Get current playlist."""
    username = await verify_auth(x_api_key)
    
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel."
        )
    
    items = await bot_interface.get_playlist()
    
    return PlaylistResponse(
        items=[MediaItem(**item) for item in items],
        total=len(items)
    )


@app.post(
    "/api/v1/playlist/add",
    response_model=AddMediaResponse,
    summary="Add media to playlist",
    description="Add a single media item to the playlist.",
    responses={
        200: {"description": "Media added successfully"},
        400: {"description": "Invalid URL or unsupported media type"},
        503: {"description": "Bot not connected"}
    },
    tags=["Playlist"]
)
async def add_media(
    request: AddMediaRequest,
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Add single media item to playlist."""
    username = await verify_auth(x_api_key)
    
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel."
        )
    
    media = await bot_interface.add_media(request.url, request.position)
    
    if not media:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add media. Check URL and try again."
        )
    
    return AddMediaResponse(
        success=True,
        media=media
    )


@app.post(
    "/api/v1/playlist/bulk-add",
    response_model=BulkAddResponse,
    summary="Bulk add media to playlist",
    description=(
        "Add multiple media items to playlist in one request. "
        "Maximum 200 items per request. "
        "Processing continues even if some items fail."
    ),
    responses={
        200: {"description": "Bulk add completed (check added/failed counts)"},
        503: {"description": "Bot not connected"}
    },
    tags=["Playlist"]
)
async def bulk_add_media(
    request: BulkAddRequest,
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Bulk add media items to playlist."""
    username = await verify_auth(x_api_key)
    
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel."
        )
    
    # Convert Pydantic models to dicts
    items = [{"url": item.url, "position": item.position} for item in request.items]
    
    result = await bot_interface.add_media_bulk(items)
    
    return BulkAddResponse(
        success=result["added"] > 0,
        added=result["added"],
        failed=result["failed"],
        errors=result["errors"]
    )


@app.delete(
    "/api/v1/playlist/{media_id}",
    response_model=RemoveMediaResponse,
    summary="Remove media from playlist",
    description="Remove a specific media item from the playlist by ID.",
    responses={
        200: {"description": "Media removed successfully"},
        404: {"description": "Media ID not found"},
        503: {"description": "Bot not connected"}
    },
    tags=["Playlist"]
)
async def remove_media(
    media_id: str,
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Remove media from playlist."""
    username = await verify_auth(x_api_key)
    
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel."
        )
    
    success = await bot_interface.remove_media(media_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Media with ID '{media_id}' not found in playlist."
        )
    
    return RemoveMediaResponse(success=True)


@app.delete(
    "/api/v1/playlist",
    response_model=ClearPlaylistResponse,
    summary="Clear entire playlist",
    description=(
        "Remove all items from the playlist. "
        "⚠️ This action cannot be undone! "
        "Requires 'confirm=true' query parameter."
    ),
    responses={
        200: {"description": "Playlist cleared successfully"},
        400: {"description": "Missing confirmation parameter"},
        503: {"description": "Bot not connected"}
    },
    tags=["Playlist"]
)
async def clear_playlist(
    confirm: bool = False,
    x_api_key: Annotated[Optional[str], Header()] = None
):
    """Clear entire playlist (requires confirmation)."""
    username = await verify_auth(x_api_key)
    
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This action requires confirmation. Add '?confirm=true' to the URL."
        )
    
    if not bot_interface.is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot is not connected to channel."
        )
    
    removed = await bot_interface.clear_playlist()
    
    return ClearPlaylistResponse(
        success=True,
        removed=removed
    )
```

---

## Testing Checklist

### Manual Tests

1. **Get Playlist**
   ```bash
   curl -H "X-API-Key: your-key" \
     http://localhost:8080/api/v1/playlist
   
   # Expected: {"items": [...], "total": N}
   ```

2. **Add Single Video**
   ```bash
   curl -X POST http://localhost:8080/api/v1/playlist/add \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://youtube.com/watch?v=dQw4w9WgXcQ", "position": "end"}'
   
   # Expected: {"success": true, "media": {...}}
   # Video should appear in playlist
   ```

3. **Bulk Add Videos**
   ```bash
   curl -X POST http://localhost:8080/api/v1/playlist/bulk-add \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{
       "items": [
         {"url": "https://youtube.com/watch?v=dQw4w9WgXcQ"},
         {"url": "https://youtube.com/watch?v=9bZkp7q19f0"},
         {"url": "https://youtube.com/watch?v=kJQP7kiw5Fk"}
       ]
     }'
   
   # Expected: {"success": true, "added": 3, "failed": 0, "errors": []}
   ```

4. **Bulk Add with Invalid URLs**
   ```bash
   curl -X POST http://localhost:8080/api/v1/playlist/bulk-add \
     -H "X-API-Key: your-key" \
     -H "Content-Type: application/json" \
     -d '{
       "items": [
         {"url": "https://youtube.com/watch?v=valid"},
         {"url": "https://invalid.url/broken"},
         {"url": "https://youtube.com/watch?v=another-valid"}
       ]
     }'
   
   # Expected: {"success": true, "added": 2, "failed": 1, "errors": [{...}]}
   ```

5. **Remove Media**
   ```bash
   # First get playlist to find media_id
   MEDIA_ID=$(curl -H "X-API-Key: your-key" \
     http://localhost:8080/api/v1/playlist | \
     jq -r '.items[0].id')
   
   curl -X DELETE \
     -H "X-API-Key: your-key" \
     "http://localhost:8080/api/v1/playlist/$MEDIA_ID"
   
   # Expected: {"success": true}
   ```

6. **Clear Playlist Without Confirmation**
   ```bash
   curl -X DELETE \
     -H "X-API-Key: your-key" \
     http://localhost:8080/api/v1/playlist
   
   # Expected: 400 Bad Request
   # {"error": "This action requires confirmation..."}
   ```

7. **Clear Playlist With Confirmation**
   ```bash
   curl -X DELETE \
     -H "X-API-Key: your-key" \
     "http://localhost:8080/api/v1/playlist?confirm=true"
   
   # Expected: {"success": true, "removed": N}
   # Playlist should be empty
   ```

### Bulk Operations from File

Create a text file with URLs (one per line):

```text
https://youtube.com/watch?v=dQw4w9WgXcQ
https://youtube.com/watch?v=9bZkp7q19f0
https://youtube.com/watch?v=kJQP7kiw5Fk
```

Load using script:

```bash
# Convert file to JSON array
jq -R -s 'split("\n") | map(select(length > 0)) | map({url: ., position: "end"}) | {items: .}' \
  playlist.txt | \
curl -X POST http://localhost:8080/api/v1/playlist/bulk-add \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d @-
```

---

## Success Criteria

- ✅ GET `/api/v1/playlist` returns all playlist items
- ✅ POST `/api/v1/playlist/add` adds single media
- ✅ POST `/api/v1/playlist/bulk-add` adds multiple media (max 200)
- ✅ Bulk add continues processing if some items fail
- ✅ Bulk add returns detailed error information
- ✅ DELETE `/api/v1/playlist/{id}` removes specific media
- ✅ DELETE `/api/v1/playlist` requires ?confirm=true
- ✅ Clear playlist removes all items
- ✅ All endpoints return 503 if bot disconnected
- ✅ URL validation via Pydantic regex pattern
- ✅ Position parameter supports 'end', 'next', or index
- ✅ Small delays between bulk operations (prevent overwhelming server)

---

## Performance Considerations

### Bulk Add Optimization

- **Rate Limiting:** Small delay between items to prevent overwhelming server
- **Maximum Items:** 200 per request (prevents timeout)
- **Error Handling:** Continue on failure, collect all errors
- **Response Time:** 1+ seconds per item is acceptable (200 items = 3-5 minutes)
- **Progress Feedback:** CLI provides real-time console output for each item added

### Future Improvements

- Queue-based processing with progress tracking
- WebSocket for real-time progress updates
- Parallel processing with semaphore (5 concurrent)
- Caching of media metadata to avoid redundant lookups
- Retry logic for transient failures

---

## CLI Tool Integration

This will be used in the next commit to create a command-line tool:

```bash
# Single add
rosey-cli playlist add "https://youtube.com/watch?v=..."

# Bulk add from file
rosey-cli playlist bulk playlist.txt

# Get playlist
rosey-cli playlist list

# Remove item
rosey-cli playlist remove <media-id>

# Clear all
rosey-cli playlist clear --confirm
```

---

## Rollback Plan

If issues arise:
1. Comment out playlist endpoints in `api_server.py`
2. Revert `bot_interface.py` changes
3. Bot continues to function normally
4. Can still manage playlist manually via CyTube UI
5. No database changes, so no data loss
