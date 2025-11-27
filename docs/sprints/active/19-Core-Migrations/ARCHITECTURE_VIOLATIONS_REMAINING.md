# Architecture Violations Analysis - Remaining Sorties (3, 5, 6, 7, 8)

**Sprint:** 19 - Core Migrations  
**Date:** 2025-01-20  
**Status:** Analysis Complete  
**Reviewed Sorties:** 3, 5, 6, 7, 8

---

## Executive Summary

Reviewed the remaining 5 sorties in Sprint 19 for NATS architecture compliance violations. **GOOD NEWS**: None of the remaining sorties have the critical `get_service()` violations found in Sorties 2, 4, and 6.

### Findings Overview

| Sortie | Status | Violations | Severity | Action Required |
|--------|--------|------------|----------|-----------------|
| 3 - Playlist Persistence | ✅ CLEAN | None | N/A | None - already compliant |
| 5 - LLM Memory | ⚠️ MINOR | Database service access | Low | Clarification only |
| 6 - LLM Service | ✅ CLEAN* | Already NATS-based | N/A | Already correct pattern |
| 7 - MCP Foundation | ✅ CLEAN | None | N/A | None - internal only |
| 8 - Integration | ✅ CLEAN | None | N/A | None - cleanup only |

**\* Note:** Sortie 6 was originally written with NATS architecture from the start, unlike Sorties 2 and 4 which required major rewrites.

---

## Sortie 3: Playlist Persistence - ✅ CLEAN

**File:** `SPEC-Sortie-3-PlaylistPersistence.md`

### Analysis

This sortie focuses on database persistence for the playlist plugin. It's **CLEAN** - no architecture violations.

### Key Observations

1. **Database Access Pattern**:
   - Uses `await get_database_service()` (line 317)
   - This is **ACCEPTABLE** - database is infrastructure, not plugin-to-plugin communication
   - Pattern: Infrastructure services (DB, NATS) are OK; plugin services must use NATS

2. **Internal Classes Only**:
   - `PlaylistStorage` - internal helper for DB operations ✅
   - `QuotaManager` - internal helper for rate limiting ✅
   - Neither exposed to other plugins ✅

3. **No Cross-Plugin Communication**:
   - No `get_service()` calls for other plugins ✅
   - No service registration ✅
   - Purely internal persistence layer ✅

### Verdict

**NO CHANGES REQUIRED** - Sortie 3 is already compliant with NATS architecture.

### Pattern Clarification

For future reference, the acceptable pattern is:

```python
# ✅ ACCEPTABLE: Infrastructure access
db_service = await get_database_service()  # Database is shared infrastructure
nats_client = await get_nats_client()      # NATS is shared infrastructure

# ❌ VIOLATION: Plugin-to-plugin access
playlist_service = await get_service("playlist")  # Cross-plugin Python object
llm_service = await get_service("llm")           # Should use NATS instead
```

---

## Sortie 5: LLM Memory - ⚠️ MINOR ISSUE

**File:** `SPEC-Sortie-5-LLMMemory.md`

### Analysis

This sortie adds conversation memory to the LLM plugin. Mostly clean, with one minor clarification needed.

### Key Observations

1. **Database Access**:
   - Line 760: `db_service = await get_database_service()`
   - Same pattern as Sortie 3 - **ACCEPTABLE** infrastructure access
   - Used only for persistence, not cross-plugin communication ✅

2. **Internal Components**:
   - `ConversationMemory` - internal memory manager ✅
   - `ConversationSummarizer` - internal summarization ✅
   - `LLMStorage` - internal database operations ✅
   - All are internal to LLM plugin ✅

3. **No Service Exposure**:
   - Memory is managed internally ✅
   - No new services exposed to other plugins ✅
   - Other plugins access memory via existing NATS subjects (from Sortie 6) ✅

### Minor Issue

**Line 760 context** shows the plugin initialization:
```python
# Initialize storage
db_service = await get_database_service()
self.storage = LLMStorage(db_service)
await self.storage.create_tables()
```

This is the same acceptable database infrastructure pattern as Sortie 3. However, for clarity, the spec should explicitly note that this is infrastructure access, not plugin-to-plugin communication.

### Recommended Clarification

Add a note to the spec:

```markdown
**Note:** `get_database_service()` is used to access the shared database infrastructure 
(established in Sprint 17). This is NOT cross-plugin communication and is acceptable 
under the NATS-only architecture. Database service is infrastructure (like NATS), 
not a plugin service.
```

### Verdict

**MINOR CLARIFICATION RECOMMENDED** - Add note about database infrastructure access pattern. No code changes required - already compliant.

---

## Sortie 6: LLM Service - ✅ CLEAN (Already NATS-Based)

**File:** `SPEC-Sortie-6-LLMService.md`

### Analysis

This sortie exposes LLM functionality via NATS service interface. It's **ALREADY WRITTEN CORRECTLY** with NATS architecture from the start.

### Key Observations

1. **NATS Service Subjects Defined**:
   ```python
   SUBJECTS = {
       "rosey.llm.chat": "Simple chat message",
       "rosey.llm.complete": "Raw completion request",
       "rosey.llm.summarize": "Summarize text",
       "rosey.llm.memory.add": "Add memory",
       "rosey.llm.memory.recall": "Recall memories",
       ...
   }
   ```
   Perfect NATS-based architecture ✅

2. **Request/Response Schemas**:
   - Complete dataclass definitions for all requests ✅
   - Complete dataclass definitions for all responses ✅
   - Proper JSON serialization ✅

3. **NATS Handlers**:
   ```python
   async def _handle_chat(self, msg) -> None:
       """Handle chat request from NATS."""
       data = json.loads(msg.data.decode())
       req = ChatRequest(**data)
       response = await self.chat(...)
       await msg.respond(json.dumps(asdict(response)).encode())
   ```
   Perfect request/reply pattern ✅

4. **No get_service() Violations**:
   - No plugin-to-plugin Python imports ✅
   - All communication via NATS ✅
   - Service is internal `LLMService` class (not exposed directly) ✅

5. **Event Publishing**:
   ```python
   await self._nc.publish(
       "rosey.event.llm.response",
       json.dumps(asdict(event)).encode()
   )
   ```
   Proper event-driven architecture ✅

### Usage Examples (From Spec)

The spec includes excellent examples of NATS usage:

```python
# From Trivia Plugin
response = await self._nc.request(
    "rosey.llm.chat",
    json.dumps({
        "channel": self._channel,
        "user": "trivia-bot",
        "message": f"Give a clever hint...",
    }).encode(),
    timeout=5.0
)
```

Perfect NATS request/reply pattern ✅

### Comparison to Sortie 2/4

**Sortie 2 (Playlist) - BEFORE FIX:**
```python
# ❌ OLD: Python object sharing
class PlaylistPlugin:
    def setup(self):
        self.service = PlaylistService()
        await register_service("playlist", self.service)  # WRONG
```

**Sortie 6 (LLM) - ALREADY CORRECT:**
```python
# ✅ CORRECT: NATS-based from start
class LLMService:
    async def start(self) -> None:
        await self._nc.subscribe("rosey.llm.chat", cb=self._handle_chat)
        await self._nc.subscribe("rosey.llm.complete", cb=self._handle_complete)
        # All via NATS, no register_service() calls
```

### Verdict

**NO CHANGES REQUIRED** - Sortie 6 was written correctly from the start with full NATS architecture. This is the pattern that Sorties 2 and 4 were rewritten to match.

---

## Sortie 7: MCP Foundation - ✅ CLEAN

**File:** `SPEC-Sortie-7-MCPFoundation.md`

### Analysis

This sortie implements Model Context Protocol (MCP) tools for the LLM plugin. It's **CLEAN** - all components are internal to the LLM plugin.

### Key Observations

1. **Internal Tool Framework**:
   - `ToolRegistry` - internal tool registration ✅
   - `ToolExecutor` - internal tool execution ✅
   - `ToolParser` - internal parsing ✅
   - All internal to LLM plugin ✅

2. **Built-in Tools**:
   - `calculator` - math operations ✅
   - `get_time` - time/date queries ✅
   - `roll_dice` - dice rolling ✅
   - All executed within LLM plugin ✅

3. **No Cross-Plugin Violations**:
   - Tools are registered internally ✅
   - Tools are called by LLM provider (internal) ✅
   - No `get_service()` calls ✅
   - No plugin-to-plugin Python imports ✅

4. **External Tool Access Pattern**:
   The spec mentions future plugin-provided tools. This would use NATS:
   ```python
   # Future pattern (not in this sortie)
   response = await nats_client.request(
       "rosey.dice.roll",  # Call dice-roller plugin via NATS
       json.dumps({"notation": "2d6"}).encode()
   )
   ```
   If implemented, this would be NATS-based ✅

### Tool Framework Architecture

```python
# All internal to LLM plugin
class ToolRegistry:
    def register(self, definition: ToolDefinition, handler: Callable):
        # Register tool handler (internal function)
        
class ToolExecutor:
    async def execute(self, tool_calls: List[ToolCall], context: dict):
        # Execute tools via registered handlers
```

This is similar to the plugin system itself - internal registry and execution. No violations.

### Verdict

**NO CHANGES REQUIRED** - Sortie 7 is fully internal to the LLM plugin with no cross-plugin communication.

---

## Sortie 8: Integration - ✅ CLEAN

**File:** `SPEC-Sortie-8-Integration.md`

### Analysis

This sortie removes deprecated code and performs final integration testing. It's **CLEAN** and actually **enforces** the NATS architecture.

### Key Observations

1. **Removes Deprecated Code**:
   - Removes `lib/playlist.py` ✅
   - Removes `lib/llm/` directory ✅
   - Forces all consumers to use NATS-based plugins ✅

2. **Updates Bot Core**:
   ```python
   # BEFORE (WRONG):
   from lib.llm import LLMChat
   from lib.playlist import Playlist
   
   # AFTER (CORRECT):
   # Use NATS for communication
   async def request_llm(self, message: str, channel: str, user: str):
       response = await self._nc.request("rosey.llm.chat", ...)
   ```
   Perfect NATS migration ✅

3. **Integration Tests**:
   - Tests cross-plugin communication via NATS ✅
   - Tests event flow ✅
   - No direct Python imports between plugins ✅

4. **Documentation Updates**:
   - Documents NATS-based architecture ✅
   - Provides migration guide ✅
   - Shows correct NATS usage patterns ✅

### Example Integration Test

```python
@pytest.mark.integration
async def test_trivia_uses_llm_for_hints(trivia_plugin, llm_plugin, mock_nats):
    """Test trivia can get hints from LLM."""
    # Via NATS, not direct Python calls
    await mock_nats.publish("rosey.command.trivia.hint", ...)
```

Perfect NATS-based testing ✅

### Verdict

**NO CHANGES REQUIRED** - Sortie 8 completes the migration to NATS architecture and removes all deprecated Python-based communication patterns.

---

## Summary of All Findings

### Clean Sorties (No Changes)

1. **Sortie 3 (Playlist Persistence)** - Internal persistence only, acceptable database access
2. **Sortie 6 (LLM Service)** - Already written with NATS architecture from start
3. **Sortie 7 (MCP Foundation)** - Internal tool framework, no cross-plugin communication
4. **Sortie 8 (Integration)** - Enforces NATS architecture, removes deprecated code

### Minor Clarification Needed

1. **Sortie 5 (LLM Memory)** - Add note clarifying database infrastructure access is acceptable

---

## Recommended Actions

### Immediate Actions

1. **Sortie 5**: Add clarification note about database infrastructure access
2. **All Sorties**: No code changes required

### Documentation Updates

Update the sprint PRD to clarify infrastructure vs. plugin services:

```markdown
## Architecture Patterns

### Acceptable Patterns

**Infrastructure Access** (Shared services, NOT plugin-to-plugin):
- Database: `db_service = await get_database_service()`
- NATS: `nc = await get_nats_client()`
- Config: `config = await get_config_service()`

**Plugin Communication** (MUST use NATS):
- Request/Reply: `response = await nc.request("rosey.plugin.method", data)`
- Pub/Sub: `await nc.publish("rosey.event.type", data)`

### Violation Pattern (AVOID)

**Plugin-to-Plugin Python Objects** (NOT allowed):
- `service = await get_service("plugin_name")` ❌
- `from plugins.other import Service` ❌
- Direct Python object sharing between plugins ❌
```

---

## Conclusion

After comprehensive review of all remaining sorties (3, 5, 6, 7, 8):

- **0 critical violations** - No `get_service()` plugin-to-plugin communication
- **0 major rewrites needed** - All follow NATS architecture
- **1 minor clarification** - Sortie 5 database access note
- **Sprint 19 is architecturally sound** - All sorties comply with NATS-only architecture

The sprint can proceed to implementation without additional architecture rewrites. The fixes to Sorties 1, 2, and 4 were sufficient to establish the correct pattern, and all remaining sorties already follow it.

---

**Document Status:** Complete  
**Next Steps:** Add clarification note to Sortie 5, then proceed with implementation  
**Overall Assessment:** ✅ Sprint 19 architecture is NATS-compliant
