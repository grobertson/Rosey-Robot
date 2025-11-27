# Sprint 19 NATS Architecture Violations

**Date**: November 27, 2025  
**Status**: CRITICAL - Must Fix Before Implementation  
**Reviewed By**: GitHub Copilot Agent  
**Impact**: HIGH - Violates core NATS-only architecture

---

## Executive Summary

**CRITICAL FINDING**: Sprint 19 specifications violate the NATS-only architecture by using **direct Python service imports** instead of NATS request/reply for inter-plugin communication.

### Violation Pattern Found

**❌ WRONG (as currently written):**
```python
# From another plugin - VIOLATES ARCHITECTURE
playlist = await get_service("playlist")  # Direct Python import/reference
result = await playlist.add_item(channel, url, user)
```

**✅ CORRECT (NATS-based):**
```python
# From another plugin - NATS request/reply
response = await nats_client.request(
    "service.playlist.add_item",
    json.dumps({"channel": channel, "url": url, "user": user})
)
result = json.loads(response.data)
```

### Architecture Requirements (from AGENTS.md)

> Plugins should each run separately with the only touchpoint being NATS. All plugins simply consume from NATS queues, and respond or emit via NATS queues.

**This means:**
- ❌ No `get_service()` or direct Python imports between plugins
- ❌ No shared Python objects or classes across plugins
- ❌ No direct method calls on service instances
- ✅ All communication via NATS pub/sub or request/reply
- ✅ Services expose NATS subjects, not Python APIs
- ✅ Plugins can run as separate processes

---

## Violations by Sortie

### Sortie 1: Playlist Foundation

**Status**: ⚠️ PARTIAL VIOLATION

**Found:**
- Line 415: `from lib.plugin.base import PluginBase` - This is OK if `lib.plugin.base` is a shared library
- Line 444: `self.service: Optional['PlaylistService'] = None` - Setup for violation in Sortie 2

**Issue:**
- Sets up service instance that will be exposed via Python import in Sortie 2

**Recommendation:**
- Remove `self.service` instance variable
- Do not create PlaylistService as Python class for cross-plugin use
- Service pattern should be internal to plugin only

---

### Sortie 2: PlaylistService & Events

**Status**: 🚨 **CRITICAL VIOLATION**

**Found:**

**Line 196-205 (Service Usage Example):**
```python
# From another plugin
playlist = await get_service("playlist")  # ❌ VIOLATION

# Add an item
result = await playlist.add_item("lobby", "https://youtube.com/...", "user1")
if result.success:
    print(f"Added at #{result.position}")

# Get queue
items = playlist.get_queue("lobby")

# Vote to skip
vote = await playlist.vote_skip("lobby", "user2")
```

**Issue:**
This pattern creates direct Python object references between plugins:
1. `get_service("playlist")` returns Python object instance
2. `playlist.add_item()` is direct method call
3. Plugins are tightly coupled via shared Python memory
4. Plugins CANNOT run as separate processes
5. No isolation between plugins

**Impact:**
- Violates NATS-only architecture requirement
- Prevents plugins from running independently
- Creates tight coupling between plugins
- Makes hot-reload unreliable
- Breaks process isolation

**Recommendation:**
Replace with NATS request/reply pattern (see "Corrected Architecture" section below).

---

### Sortie 4: LLM Plugin Foundation

**Status**: ⚠️ LIKELY VIOLATION (not fully reviewed)

**Expected Pattern:**
Based on Sortie 2, likely shows similar service exposure:
```python
# Expected violation pattern
llm = await get_service("llm")  # ❌ VIOLATION
response = await llm.complete(messages)
```

**Recommendation:**
Review and correct to use NATS request/reply.

---

### Sorties 3, 5, 6, 7, 8

**Status**: ⏳ NOT YET REVIEWED

**Expected:**
- Sortie 3 (PlaylistPersistence): May violate with database service access
- Sortie 5 (LLMMemory): May violate with memory/context sharing
- Sortie 6 (LLMService): Likely violates with service exposure pattern
- Sortie 7 (MCPFoundation): May violate with tool service exposure
- Sortie 8 (Integration): May show end-to-end violation patterns

---

## Corrected Architecture: NATS Request/Reply Pattern

### Service Exposure Pattern

**Instead of Python service classes, use NATS request/reply subjects.**

### Example: Playlist Service via NATS

#### Service Implementation (plugins/playlist/plugin.py)

```python
class PlaylistPlugin(PluginBase):
    """Playlist plugin - exposes service via NATS."""
    
    async def setup(self) -> None:
        """Set up NATS subscriptions for service requests."""
        
        # Subscribe to service request subjects
        await self.subscribe("service.playlist.add_item", self._service_add_item)
        await self.subscribe("service.playlist.remove_item", self._service_remove_item)
        await self.subscribe("service.playlist.get_queue", self._service_get_queue)
        await self.subscribe("service.playlist.get_current", self._service_get_current)
        await self.subscribe("service.playlist.vote_skip", self._service_vote_skip)
        await self.subscribe("service.playlist.shuffle", self._service_shuffle)
        await self.subscribe("service.playlist.clear", self._service_clear)
        
        # ... existing command subscriptions ...
    
    async def _service_add_item(self, msg) -> None:
        """Service method: Add item to playlist."""
        try:
            # Parse request
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            url = data["url"]
            user = data["user"]
            
            # Parse URL
            media_type, media_id = MediaParser.parse(url)
            
            # Create item
            item = PlaylistItem(
                id="",
                media_type=media_type,
                media_id=media_id,
                title=f"Loading...",
                duration=0,
                added_by=user,
            )
            
            # Add to queue
            queue = self._get_queue(channel)
            if not queue.add(item):
                # Reply with error
                await msg.respond(json.dumps({
                    "success": False,
                    "error": "Queue is full"
                }).encode())
                return
            
            position = queue.length
            
            # Start metadata fetch (async)
            asyncio.create_task(
                self._fetch_and_update_metadata(channel, item)
            )
            
            # Emit event
            await self.publish("playlist.item.added", {
                "channel": channel,
                "item": item.to_dict(),
                "position": position,
            })
            
            # Reply with success
            await msg.respond(json.dumps({
                "success": True,
                "item": item.to_dict(),
                "position": position,
            }).encode())
            
        except Exception as e:
            # Reply with error
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    async def _service_get_queue(self, msg) -> None:
        """Service method: Get queue for channel."""
        try:
            data = json.loads(msg.data.decode())
            channel = data["channel"]
            
            queue = self._get_queue(channel)
            items = [item.to_dict() for item in queue.items]
            
            await msg.respond(json.dumps({
                "success": True,
                "items": items,
            }).encode())
            
        except Exception as e:
            await msg.respond(json.dumps({
                "success": False,
                "error": str(e)
            }).encode())
    
    # ... similar patterns for other service methods ...
```

#### Service Consumer (another plugin)

```python
class SomeOtherPlugin(PluginBase):
    """Another plugin that needs playlist functionality."""
    
    async def some_command_handler(self, msg) -> None:
        """Example: Add item to playlist via NATS."""
        
        # Prepare request
        request = {
            "channel": "lobby",
            "url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "user": "Alice",
        }
        
        # Send request via NATS (with timeout)
        try:
            response = await self.nats_client.request(
                "service.playlist.add_item",
                json.dumps(request).encode(),
                timeout=5.0,  # 5 second timeout
            )
            
            # Parse response
            result = json.loads(response.data.decode())
            
            if result["success"]:
                item = result["item"]
                position = result["position"]
                await self.logger.info(f"Added to playlist at #{position}: {item['title']}")
            else:
                await self.logger.error(f"Failed to add: {result['error']}")
                
        except asyncio.TimeoutError:
            await self.logger.error("Playlist service timeout")
        except Exception as e:
            await self.logger.error(f"Playlist service error: {e}")
```

### NATS Subject Table for Playlist Service

| Subject | Type | Purpose | Request Schema | Response Schema |
|---------|------|---------|----------------|-----------------|
| `service.playlist.add_item` | Request/Reply | Add item to queue | `{channel, url, user}` | `{success, item?, position?, error?}` |
| `service.playlist.remove_item` | Request/Reply | Remove item | `{channel, item_id, user, is_admin}` | `{success, item?, error?}` |
| `service.playlist.get_queue` | Request/Reply | Get queue items | `{channel}` | `{success, items[], error?}` |
| `service.playlist.get_current` | Request/Reply | Get current item | `{channel}` | `{success, item?, error?}` |
| `service.playlist.vote_skip` | Request/Reply | Vote to skip | `{channel, user}` | `{success, votes, needed, passed, error?}` |
| `service.playlist.shuffle` | Request/Reply | Shuffle queue | `{channel}` | `{success, count, error?}` |
| `service.playlist.clear` | Request/Reply | Clear queue | `{channel, user}` | `{success, count, error?}` |

### Benefits of NATS Request/Reply

✅ **Process Isolation**: Plugins can run as separate processes  
✅ **No Shared Memory**: No direct Python object references  
✅ **Independent Deployment**: Restart one plugin without affecting others  
✅ **Language Agnostic**: Plugins can be written in different languages  
✅ **Network Transparent**: Plugins can run on different machines  
✅ **Reliable**: NATS handles connection management, retries, timeouts  
✅ **Observable**: All service calls visible in NATS monitoring  
✅ **Testable**: Easy to mock service responses in tests  

---

## Service Registry Pattern (NATS-Based)

### Problem

How do plugins discover available services?

### Solution: NATS Subject Namespacing + Discovery

**Service Naming Convention:**
```
service.<plugin_name>.<operation>
```

**Discovery via NATS:**
```python
# Plugin announces availability on startup
await nats_client.publish("service.registry.announce", json.dumps({
    "plugin": "playlist",
    "version": "1.0.0",
    "services": [
        {"subject": "service.playlist.add_item", "description": "Add item to queue"},
        {"subject": "service.playlist.get_queue", "description": "Get queue items"},
        # ... all service methods ...
    ]
}))

# Other plugins can query available services
response = await nats_client.request(
    "service.registry.query",
    json.dumps({"plugin": "playlist"})
)
services = json.loads(response.data)
```

**Service Registry Plugin:**
```python
class ServiceRegistryPlugin(PluginBase):
    """Tracks available services via NATS."""
    
    def __init__(self):
        self._services = {}  # plugin -> service list
    
    async def setup(self):
        await self.subscribe("service.registry.announce", self._handle_announce)
        await self.subscribe("service.registry.query", self._handle_query)
    
    async def _handle_announce(self, msg):
        data = json.loads(msg.data)
        plugin = data["plugin"]
        self._services[plugin] = data["services"]
        self.logger.info(f"Registered {len(data['services'])} services from {plugin}")
    
    async def _handle_query(self, msg):
        data = json.loads(msg.data)
        plugin = data.get("plugin")
        
        if plugin:
            services = self._services.get(plugin, [])
        else:
            services = self._services
        
        await msg.respond(json.dumps(services).encode())
```

---

## Required Corrections

### 1. Update PRD-Core-Migrations.md

**Section to Revise:** "Integration Points"

**Current (implied):**
- Service Registry for Python object lookup
- Direct service imports

**Corrected:**
- NATS-based service exposure via request/reply
- Service registry via NATS announcements
- No direct Python imports between plugins
- All communication via NATS subjects

### 2. Update All Sortie Specs

**Changes Needed:**

1. **Remove `PlaylistService` / `LLMService` Python Classes**
   - These should be internal helper classes only
   - Not exposed to other plugins
   
2. **Add Service Request Handler Methods**
   - Each service operation becomes a NATS subscription
   - Use `msg.respond()` for request/reply pattern
   
3. **Update Service Usage Examples**
   - Replace `get_service()` with NATS `request()`
   - Show proper request/response JSON schemas
   
4. **Add NATS Subject Tables**
   - Document all service request subjects
   - Include request and response schemas
   
5. **Update Architecture Diagrams**
   - Show NATS message flow, not Python object references

### 3. Add NATS Service Best Practices Guide

**Create new document:** `docs/guides/NATS_SERVICE_PATTERN.md`

**Contents:**
- Request/reply pattern overview
- Schema design guidelines
- Error handling patterns
- Timeout strategies
- Testing service calls
- Service discovery pattern
- Migration from Python APIs to NATS

---

## Implementation Checklist

### Documentation Updates

- [ ] Update PRD-Core-Migrations.md with NATS-only architecture
- [ ] Revise SPEC-Sortie-1 to remove service instance setup
- [ ] Revise SPEC-Sortie-2 to use NATS request/reply pattern
- [ ] Revise SPEC-Sortie-4 to use NATS request/reply pattern
- [ ] Review and fix Sorties 3, 5, 6, 7, 8 (not yet reviewed)
- [ ] Create docs/guides/NATS_SERVICE_PATTERN.md
- [ ] Update all code examples to show NATS patterns
- [ ] Add NATS subject tables to all relevant specs

### Validation

- [ ] All plugin communication is NATS-based
- [ ] No `get_service()` calls
- [ ] No direct Python object sharing between plugins
- [ ] Each plugin can conceptually run as separate process
- [ ] All service operations have documented NATS subjects
- [ ] Request/response schemas documented
- [ ] Error handling patterns shown

---

## Notes for Implementation

**When implementing Sprint 19:**

1. **Start with Plugin Base Class**
   - Ensure `PluginBase` provides helper methods for NATS request/reply
   - Add `self.request(subject, data, timeout)` method
   - Add `self.respond(msg, data)` helper

2. **Create Shared Request/Reply Helpers**
   - Common request timeout handling
   - Common error response format
   - Schema validation utilities

3. **Test Each Service Method Independently**
   - Mock NATS request/reply in tests
   - Test timeout scenarios
   - Test error handling

4. **Document Service Contracts**
   - Each service subject gets schema documentation
   - Include examples of requests and responses
   - Document error conditions

5. **Consider Service Versioning**
   - Use subject namespacing: `service.playlist.v1.add_item`
   - Allows gradual migration of service APIs

---

## Questions for Clarification

1. **Service Registry**: Should we implement a service registry plugin in Sprint 19, or defer to later sprint?

2. **Helper Library**: Should `lib/plugin/base.py` provide convenience wrappers for NATS request/reply to make plugin code cleaner?

3. **Schema Validation**: Should we use JSON Schema or similar to validate request/response payloads?

4. **Backwards Compatibility**: If `lib/playlist.py` exists, should we maintain it for now or remove immediately?

---

**Status**: Awaiting approval to proceed with corrections  
**Next Steps**: Update PRD and all sortie specs with corrected NATS-only architecture  
**Estimated Effort**: 1-2 days to revise all documentation  

---

**Document Version**: 1.0  
**Created**: November 27, 2025  
**Author**: GitHub Copilot (Claude Sonnet 4.5)
