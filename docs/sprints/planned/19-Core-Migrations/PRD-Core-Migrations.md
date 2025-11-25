# PRD: Sprint 19 - Core Migrations

**Version:** 1.0  
**Sprint Name:** Core Migrations  
**Status:** Planned  
**Last Updated:** November 24, 2025

---

## 1. Product overview

### 1.1 Document title and version

- PRD: Sprint 19 - Core Migrations
- Version: 1.0

### 1.2 Product summary

Sprint 19 "Core Migrations" transforms Rosey's monolithic core features into proper NATS-based plugins. This sprint migrates two critical subsystems that were built before the plugin architecture matured:

1. **Playlist Plugin** - Migrate playlist/media management from `lib/playlist.py` to a standalone plugin
2. **LLM Plugin** - Migrate LLM integration from `lib/llm/` to a standalone plugin with service provider pattern

Unlike Sprint 18's "greenfield" plugins, Sprint 19 deals with **existing, working code** that must be carefully refactored without breaking functionality. The goal is to bring these features into the plugin ecosystem so they can:

- Evolve independently of core bot code
- Be hot-reloaded without restarting the bot
- Expose services that other plugins can consume (e.g., LLM for trivia questions)
- Be configured, enabled, or disabled per-channel

### 1.3 Why now?

Sprint 18 validated the plugin architecture with fun, experimental plugins. With confidence in the system, we can now safely migrate production features. Additionally:

- **Playlist** needs to integrate with external movie/TV catalogs (future feature)
- **LLM** should be consumable by other plugins (e.g., LLM-Trivia, weather via MCP)
- Both systems would benefit from isolated configuration and hot-reload

---

## 2. Goals

### 2.1 Business goals

- Unify all major features under the plugin architecture
- Enable future playlist integrations (Plex, Jellyfin, TMDb)
- Make LLM accessible as a service for other plugins
- Reduce core bot complexity ("boring core, fun plugins")

### 2.2 User goals

- **Playlist users**: No visible change - commands work the same, but with improved reliability
- **LLM users**: No visible change - chat responses work the same
- **Future**: New capabilities enabled by plugin architecture (catalog integration, LLM-trivia)

### 2.3 Non-goals

- **No new playlist features** - This is a migration, not enhancement
- **No new LLM features** - LLM-trivia and MCP weather come after migration
- **No breaking changes** - All existing commands must continue working
- **No performance regression** - Migration should not slow down responses

---

## 3. User personas

### 3.1 Key user types

- **Channel Moderators** - Manage playlists, queue media
- **Chat Users** - Interact with LLM-powered responses
- **Bot Administrators** - Configure and manage plugins
- **Plugin Developers** - Consume LLM service for custom plugins

### 3.2 Basic persona details

- **DJDave**: Manages the music/video queue, needs reliable playlist commands
- **ChattyCathy**: Enjoys Rosey's LLM-powered responses and personality
- **AdminAlex**: Needs to configure LLM providers, rate limits, and playlist sources
- **DevDana**: Wants to build an LLM-trivia plugin that uses the LLM service

### 3.3 Role-based access

- **Everyone**: View playlist, basic LLM interactions
- **Moderators**: Add/remove from playlist, skip, manage queue
- **Administrators**: Configure LLM providers, playlist sources, enable/disable plugins

---

## 4. Functional requirements

### 4.1 Playlist Plugin (Priority: HIGH)

**Migration scope**: Move `lib/playlist.py` and related code to `plugins/playlist/`

- **FR-PLAY-001**: Migrate all existing playlist commands to plugin
  - `!add <url>` - Add media to queue
  - `!skip` - Skip current item (moderator+)
  - `!queue` - View current queue
  - `!now` - Show now playing
  - `!clear` - Clear queue (moderator+)
  
- **FR-PLAY-002**: Expose PlaylistService for other plugins
  - `get_current_item()` - Returns currently playing media info
  - `get_queue()` - Returns upcoming items
  - `add_item(url, user)` - Programmatically add to queue
  - `on_media_change(callback)` - Subscribe to media change events

- **FR-PLAY-003**: Emit events for media lifecycle
  - `playlist.item_added` - When media is queued
  - `playlist.item_started` - When media begins playing
  - `playlist.item_ended` - When media finishes
  - `playlist.queue_cleared` - When queue is emptied

- **FR-PLAY-004**: Channel-specific playlist configuration
  - Enable/disable playlist per channel
  - Configure max queue length per channel
  - Configure allowed media sources per channel

- **FR-PLAY-005**: Persist queue state across bot restarts
  - Save current queue to database
  - Restore queue on startup (configurable)

- **FR-PLAY-006**: Prepare for external catalog integration (future)
  - Abstract media source interface
  - Support for URL-based, catalog-based, and search-based additions
  - Metadata enrichment hooks (title, duration, thumbnail)

### 4.2 LLM Plugin (Priority: HIGH)

**Migration scope**: Move `lib/llm/` to `plugins/llm/`

- **FR-LLM-001**: Migrate all existing LLM functionality to plugin
  - Chat response generation
  - Trigger-based responses (mentioned, specific phrases)
  - Context-aware responses (knows current media, recent chat)

- **FR-LLM-002**: Expose LLMService for other plugins
  - `generate_response(prompt, context)` - Generate text response
  - `generate_structured(prompt, schema)` - Generate JSON following schema
  - `is_available()` - Check if LLM is configured and responding
  - `get_usage_stats()` - Return token usage, rate limit status

- **FR-LLM-003**: Support multiple LLM providers (abstraction)
  - Ollama (local, current default)
  - OpenAI-compatible APIs
  - Anthropic Claude
  - Future: MCP-based providers

- **FR-LLM-004**: Rate limiting and cost controls
  - Configurable tokens per minute
  - Configurable requests per minute
  - Per-user rate limits (prevent spam)
  - Cost tracking for paid APIs

- **FR-LLM-005**: Context management
  - Sliding window of recent chat messages
  - Current media context (what's playing)
  - Channel-specific personality configuration

- **FR-LLM-006**: Emit events for LLM operations
  - `llm.response_generated` - When LLM produces response
  - `llm.rate_limited` - When rate limit is hit
  - `llm.error` - When LLM call fails

- **FR-LLM-007**: MCP (Model Context Protocol) integration foundation
  - Support MCP tool definitions
  - Allow LLM to call external tools (weather, search, etc.)
  - Sandboxed execution with configurable permissions

---

## 5. User experience

### 5.1 Entry points & first-time user flow

- **No change for end users** - All existing commands work identically
- **Administrators**: New configuration options in plugin config files
- **Developers**: New service APIs available for consumption

### 5.2 Core experience

Users should notice **no difference** in behavior. The migration is internal.

- Playlist commands respond the same way
- LLM chat responses have the same personality
- All timing and rate limits preserved

### 5.3 Advanced features & edge cases

- **Hot reload**: Playlist plugin reload should not lose queue state
- **LLM failover**: If LLM provider fails, graceful degradation (no crash)
- **Service availability**: Plugins consuming LLMService handle unavailability gracefully

### 5.4 UI/UX highlights

- Commands unchanged
- Response formats unchanged  
- Error messages improved with plugin-specific context

---

## 6. Narrative

The migration is invisible to users. On the surface, nothing changes. But under the hood, Rosey becomes more modular, more maintainable, and more extensible.

**Before Sprint 19**: Playlist and LLM are tangled into core bot code. Adding features means touching core files. A bug in LLM could theoretically affect CyTube connectivity.

**After Sprint 19**: Playlist and LLM are proper plugins. They can be:
- Hot-reloaded independently
- Configured per-channel
- Extended without core changes
- Disabled if needed without affecting other features

**The real payoff comes in future sprints**: 
- Sprint 20+: Add TMDb integration to playlist for movie info
- Sprint 20+: Add LLM-trivia using LLMService
- Sprint 20+: Add MCP-based weather tool for LLM
- Sprint 20+: Add Plex/Jellyfin playlist sources

---

## 7. Success metrics

### 7.1 User-centric metrics

- **Zero regressions**: All existing commands work identically
- **No user complaints**: Migration is invisible
- **Response time unchanged**: Commands respond as fast as before

### 7.2 Business metrics

- Core bot codebase reduced (less code in `lib/`, more in `plugins/`)
- Plugin count increases by 2 (playlist, llm)
- Foundation laid for 3+ future features (catalog, llm-trivia, mcp-weather)

### 7.3 Technical metrics

- **Test coverage maintained**: 90%+ for migrated code
- **Hot reload works**: Playlist and LLM can be reloaded without restart
- **Service consumption works**: At least one plugin uses LLMService (even if just a test)
- **Event emission works**: Inspector shows playlist.* and llm.* events

---

## 8. Technical considerations

### 8.1 Integration points

- **NATS Event Bus**: Plugins communicate via NATS
- **Database Service**: Playlist queue persistence, LLM usage tracking
- **Plugin Manager**: Hot-reload, lifecycle management
- **CyTube Connection**: Playlist plugin subscribes to media events from CyTube
- **Service Registry**: LLMService and PlaylistService registered for other plugins

### 8.2 Data storage & privacy

- **Playlist**: Queue data (URLs, titles, who added) stored temporarily
- **LLM**: Chat context (recent messages) stored in memory, not persisted
- **LLM**: Token usage stats stored for rate limiting
- No new PII collected; existing data handling unchanged

### 8.3 Scalability & performance

- Migration should not introduce latency
- LLMService calls are already async; this is preserved
- Playlist operations are low-latency (in-memory queue with DB backup)

### 8.4 Potential challenges

- **CyTube event integration**: Playlist needs to listen to CyTube media events
- **State during migration**: Ensure no queue loss during deployment
- **LLM provider abstraction**: Different providers have different APIs
- **Backward compatibility**: All existing config must work or have clear migration path

---

## 9. Milestones & sequencing

### 9.1 Project estimate

- **Size**: Medium-Large (2 significant migrations, 2-3 weeks)
- **Complexity**: Medium-High (working with existing code)

### 9.2 Team size & composition

- **Team**: 1 developer + 1 AI pair programmer (GitHub Copilot)
- **Roles**: Development, testing, documentation

### 9.3 Suggested phases

**Sortie 1: Playlist Plugin Foundation** (2-3 days)
- Create plugin structure in `plugins/playlist/`
- Extract playlist logic from core
- Implement basic commands (add, queue, now, skip)
- Preserve existing behavior exactly

**Sortie 2: Playlist Service & Events** (2 days)
- Implement PlaylistService for other plugins
- Add event emission (item_added, item_started, etc.)
- Add channel-specific configuration
- Write tests

**Sortie 3: Playlist Persistence & Polish** (1-2 days)
- Add queue persistence across restarts
- Implement queue restoration on startup
- Remove old code from `lib/`
- Integration testing

**Sortie 4: LLM Plugin Foundation** (2-3 days)
- Create plugin structure in `plugins/llm/`
- Extract LLM logic from `lib/llm/`
- Implement core chat response functionality
- Preserve existing trigger behavior

**Sortie 5: LLM Service & Provider Abstraction** (2-3 days)
- Implement LLMService for other plugins
- Abstract provider interface (Ollama, OpenAI, etc.)
- Add rate limiting and cost controls
- Write tests

**Sortie 6: LLM Context & Events** (2 days)
- Implement context management (chat history, current media)
- Add event emission (response_generated, rate_limited, error)
- Channel-specific personality configuration
- Integration testing

**Sortie 7: MCP Foundation** (2 days)
- Design MCP tool interface
- Implement basic tool calling support
- Create example MCP tool (simple, not weather yet)
- Document MCP integration for future sprints

**Sortie 8: Integration & Cleanup** (2-3 days)
- Full integration testing
- Remove migrated code from `lib/`
- Update imports across codebase
- Documentation updates
- Performance verification

---

## 10. User stories

### 10.1 Playlist migration stories

- **ID**: GH-PLAY-001
- **Description**: As a moderator, I want playlist commands to work exactly as before so that my workflow isn't disrupted.
- **Acceptance criteria**:
  - `!add`, `!skip`, `!queue`, `!now`, `!clear` work identically
  - Response messages unchanged
  - Permission checks unchanged

- **ID**: GH-PLAY-002
- **Description**: As a plugin developer, I want to access playlist information so that I can build features that react to what's playing.
- **Acceptance criteria**:
  - PlaylistService.get_current_item() returns media info
  - PlaylistService.get_queue() returns upcoming items
  - Events emitted on media changes

- **ID**: GH-PLAY-003
- **Description**: As an administrator, I want the queue to survive bot restarts so that users don't lose their queued items.
- **Acceptance criteria**:
  - Queue persisted to database
  - Queue restored on startup (if configured)
  - Clear indication if queue restoration is disabled

### 10.2 LLM migration stories

- **ID**: GH-LLM-001
- **Description**: As a chat user, I want LLM responses to work exactly as before so that Rosey's personality isn't disrupted.
- **Acceptance criteria**:
  - Trigger conditions unchanged
  - Response style/personality unchanged
  - Rate limiting unchanged

- **ID**: GH-LLM-002
- **Description**: As a plugin developer, I want to use the LLM service so that I can build AI-powered features.
- **Acceptance criteria**:
  - LLMService.generate_response() works
  - LLMService.is_available() reflects actual status
  - Rate limiting applies to service calls

- **ID**: GH-LLM-003
- **Description**: As an administrator, I want to configure LLM providers so that I can use different AI services.
- **Acceptance criteria**:
  - Provider selection in config
  - API key/endpoint configuration
  - Rate limit configuration

- **ID**: GH-LLM-004
- **Description**: As a plugin developer, I want the LLM to call external tools so that AI responses can include real-time data.
- **Acceptance criteria**:
  - MCP tool interface defined
  - Basic tool execution works
  - Tool permissions configurable

---

## 11. Dependencies

### 11.1 Required infrastructure (already complete)

- ✅ NATS event bus (Sprint 14)
- ✅ Plugin manager with hot-reload (Sprint 14)
- ✅ Database service (Sprint 15)
- ✅ Storage API with parameterized SQL (Sprint 17)
- ✅ Sprint 18 plugin patterns (reference implementations)

### 11.2 Existing code to migrate

- `lib/playlist.py` - Current playlist implementation
- `lib/llm/` - Current LLM integration
- Related configuration in `config.json`
- Related tests in `tests/`

### 11.3 New dependencies

- None required for migration
- MCP libraries (optional, for tool calling)

---

## 12. Risks & mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking existing commands | Medium | High | Extensive testing, side-by-side comparison |
| Queue data loss during migration | Low | High | Database backup, gradual rollout |
| LLM provider API differences | Medium | Medium | Thorough provider abstraction, fallback handling |
| Performance regression | Low | Medium | Benchmark before/after, optimize if needed |
| CyTube event integration complexity | Medium | Medium | Careful study of existing event flow |

---

## 13. Future considerations (enabled by this sprint)

### 13.1 Playlist futures

- **TMDb integration**: Search movies, auto-populate metadata
- **Plex/Jellyfin integration**: Queue from personal media servers
- **Smart playlists**: Auto-generate based on criteria
- **Playlist sharing**: Export/import queue lists

### 13.2 LLM futures

- **LLM-Trivia**: Generate trivia questions using LLMService
- **MCP Weather**: Weather via MCP tool (not external API dependency)
- **MCP Search**: Web search via MCP tool
- **Multi-model**: Use different models for different tasks
- **Fine-tuning**: Custom Rosey personality model

### 13.3 Cross-plugin features

- Trivia plugin asks LLM for questions about current playlist item
- Countdown plugin announces LLM-generated movie descriptions
- Inspector reports LLM usage statistics

---

## 14. Migration checklist

### 14.1 Pre-migration

- [ ] Document all existing playlist commands and behaviors
- [ ] Document all existing LLM triggers and behaviors
- [ ] Backup production configuration
- [ ] Create comprehensive test suite for existing behavior

### 14.2 During migration

- [ ] New plugin code matches existing behavior exactly
- [ ] All tests pass for new plugin
- [ ] Side-by-side comparison shows identical responses
- [ ] Performance benchmarks show no regression

### 14.3 Post-migration

- [ ] Old code removed from `lib/`
- [ ] All imports updated across codebase
- [ ] Documentation updated
- [ ] Production deployment successful
- [ ] One week of monitoring shows no issues

---

**Document Status:** Ready for Review  
**Prerequisites:** Sprint 18 completion  
**Next Steps:** Begin after Sprint 18 is merged
