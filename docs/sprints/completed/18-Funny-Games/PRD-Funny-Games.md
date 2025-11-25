# PRD: Sprint 18 - Funny Games

**Version:** 2.0  
**Sprint Name:** Funny Games (1997)  
**Status:** Draft  
**Last Updated:** November 24, 2025

---

## 1. Product overview

### 1.1 Document title and version

- PRD: Sprint 18 - Funny Games
- Version: 2.0 (Complete rewrite from stale Sprint 12 PRD)

### 1.2 Product summary

Sprint 18 "Funny Games" delivers the first wave of **fun, interactive chat plugins** for Rosey. These plugins showcase the mature NATS-based plugin architecture built over Sprints 14-17, turning Rosey from a capable bot into an entertaining chat companion.

This sprint focuses on **new plugin development** rather than migration of existing features. Each plugin is designed to be small, focused, and demonstrate different aspects of the plugin system:

- **Stateless plugins** (dice-roller, 8ball) - Pure functions, no persistence
- **Timer-based plugins** (countdown) - Async scheduling, recurring events
- **Stateful game plugins** (trivia) - Complex state, scoring, persistence
- **Observability plugins** (inspector) - System introspection, debugging

By the end of Sprint 18, Rosey will be ready to entertain a chatroom with dice rolls, fortune telling, timed announcements, trivia games, and self-diagnostic capabilities.

### 1.3 What's already done

The following infrastructure and plugins are **already complete** from previous sprints:

- ✅ **NATS Event Bus** (Sprint 14) - Plugin communication backbone
- ✅ **Plugin Manager** (Sprint 14) - Hot-reload, lifecycle management
- ✅ **Database Service** (Sprint 15) - Shared storage with migrations
- ✅ **Storage API** (Sprint 17) - Parameterized SQL for safe queries
- ✅ **Quote-DB Plugin** (Sprint 16) - Reference implementation, fully functional

---

## 2. Goals

### 2.1 Business goals

- Deliver entertaining features that make Rosey fun to interact with
- Validate the plugin architecture with diverse plugin types
- Establish plugin development patterns for future contributors
- Prepare the chatroom for Rosey's "grand debut" with engaging features

### 2.2 User goals

- Roll dice for games and decisions (`!roll 2d6`, `!flip`)
- Get fun fortune-telling responses (`!8ball Will today be good?`)
- Set up timed announcements for events (`!countdown friday 12:00 Movie time!`)
- Play interactive trivia games with friends (`!trivia start`)
- Debug and monitor bot health (`!inspect plugins`)

### 2.3 Non-goals

- **No weather plugin** - Will be handled via MCP in LLM integration (Sprint 19+)
- **No LLM-trivia** - Deferred to Sprint 19 when LLM becomes a plugin
- **No migration of existing features** - Playlist and LLM migration is Sprint 19
- **No poll system** - CyTube has native polls; integration may come later
- **No external API dependencies** - All plugins use only internal services

---

## 3. User personas

### 3.1 Key user types

- **Chat Regulars** - Daily users who want entertainment and utility
- **Game Night Hosts** - Users running movie nights, game sessions
- **Bot Administrators** - Technical users managing Rosey
- **Plugin Developers** - Future contributors learning from examples

### 3.2 Basic persona details

- **MovieNightMike**: Hosts Friday movie nights, needs countdown announcements and trivia during intermissions
- **CasualCarla**: Drops in occasionally, enjoys quick interactions like dice rolls and 8ball
- **AdminAlex**: Manages the bot, needs diagnostic tools to troubleshoot issues
- **DevDana**: Wants to build custom plugins, needs clear reference implementations

### 3.3 Role-based access

- **Everyone**: dice-roller, 8ball, trivia (play), countdown (view)
- **Moderators**: countdown (create/delete), trivia (stop games)
- **Administrators**: inspector (full access), all plugin management

---

## 4. Functional requirements

### 4.1 Dice Roller Plugin (Priority: HIGH)

- **FR-DICE-001**: Parse standard dice notation (XdY, XdY+Z, XdY-Z)
- **FR-DICE-002**: Support common dice types (d4, d6, d8, d10, d12, d20, d100)
- **FR-DICE-003**: Roll up to 20 dice per command with modifier range ±100
- **FR-DICE-004**: Display individual roll results and total
- **FR-DICE-005**: Provide coin flip command (`!flip`)
- **FR-DICE-006**: Emit `dice.rolled` events for analytics

### 4.2 Magic 8-Ball Plugin (Priority: HIGH)

- **FR-8BALL-001**: Accept questions via `!8ball <question>`
- **FR-8BALL-002**: Respond with classic 8-ball answers (20 standard responses)
- **FR-8BALL-003**: Responses categorized: positive (10), neutral (5), negative (5)
- **FR-8BALL-004**: Include personality flavor text matching Rosey's character
- **FR-8BALL-005**: Emit `8ball.consulted` events for analytics
- **FR-8BALL-006**: Rate limit to prevent spam (configurable cooldown)

### 4.3 Countdown Plugin (Priority: HIGH)

- **FR-COUNT-001**: Create one-time countdowns (`!countdown 5m Movie starting!`)
- **FR-COUNT-002**: Create recurring countdowns (`!countdown friday 12:00 Weekend movies!`)
- **FR-COUNT-003**: Support time formats: minutes (5m), hours (2h), specific time (14:30), day+time (friday 12:00)
- **FR-COUNT-004**: Channel-specific countdowns (different channels, different schedules)
- **FR-COUNT-005**: Announce at configurable intervals (1 hour, 30 min, 10 min, 5 min, 1 min, start)
- **FR-COUNT-006**: List active countdowns (`!countdown list`)
- **FR-COUNT-007**: Cancel countdowns (`!countdown cancel <id>`) - moderator+
- **FR-COUNT-008**: Persist recurring countdowns across bot restarts
- **FR-COUNT-009**: Emit `countdown.announced`, `countdown.completed` events

### 4.4 Trivia Plugin (Priority: HIGH)

- **FR-TRIVIA-001**: Start trivia games (`!trivia start`)
- **FR-TRIVIA-002**: Submit answers (`!trivia answer <choice>`)
- **FR-TRIVIA-003**: Skip questions via voting (`!trivia skip`)
- **FR-TRIVIA-004**: Stop games (`!trivia stop`) - moderator+
- **FR-TRIVIA-005**: View personal stats (`!trivia stats`)
- **FR-TRIVIA-006**: View leaderboard (`!trivia leaderboard`)
- **FR-TRIVIA-007**: Support multiple choice and text answer types
- **FR-TRIVIA-008**: Configurable question timeout (default 30 seconds)
- **FR-TRIVIA-009**: Fast-answer bonus points
- **FR-TRIVIA-010**: Per-channel game instances (concurrent games in different channels)
- **FR-TRIVIA-011**: Persist player statistics and game history
- **FR-TRIVIA-012**: Emit rich events: `trivia.game_started`, `trivia.question_asked`, `trivia.answer_submitted`, `trivia.game_finished`

### 4.5 Inspector Plugin (Priority: MEDIUM)

- **FR-INSP-001**: List loaded plugins (`!inspect plugins`)
- **FR-INSP-002**: Show plugin details (`!inspect plugin <name>`)
- **FR-INSP-003**: Show event bus statistics (`!inspect events`)
- **FR-INSP-004**: Show registered services (`!inspect services`)
- **FR-INSP-005**: Perform health check (`!inspect health`)
- **FR-INSP-006**: Provide InspectorService for programmatic access
- **FR-INSP-007**: Subscribe to all events for monitoring (wildcard subscription)
- **FR-INSP-008**: Track plugin uptime, command counts, error counts

---

## 5. User experience

### 5.1 Entry points & first-time user flow

- Users discover commands through `!help` or seeing others use them
- Each plugin responds with helpful usage examples on invalid input
- Commands are intuitive and follow established bot conventions

### 5.2 Core experience

- **Dice Rolling**: User types `!roll 2d6` → Bot responds with `🎲 [4, 3] = 7`
- **8-Ball**: User types `!8ball Should I watch another movie?` → Bot responds with fortune
- **Countdown**: Moderator sets up Friday movies → Bot announces automatically each week
- **Trivia**: User starts game → Questions appear → Players compete → Leaderboard shown
- **Inspector**: Admin checks health → Gets instant system status

### 5.3 Advanced features & edge cases

- Dice roller handles invalid notation gracefully with clear error messages
- Countdown handles timezone considerations (server time documented)
- Trivia gracefully handles player disconnects, hot reloads during games
- Inspector provides enough detail to debug misbehaving plugins

### 5.4 UI/UX highlights

- Consistent emoji usage across plugins (🎲 for dice, 🎱 for 8ball, ⏰ for countdown, 🎮 for trivia, 🔍 for inspector)
- Results formatted for chat readability (not too long, not too terse)
- Error messages are helpful, not cryptic

---

## 6. Narrative

Picture this: It's Friday at 11:55 AM. The countdown plugin announces "🎬 Weekend movies starting in 5 minutes!" in the chat. Users start trickling in, rolling dice to see who picks the first movie (`!roll d20`). Someone asks the 8-ball if the movie will be good (`!8ball Will this movie be a banger?`). During the intermission, a trivia game breaks out (`!trivia start`), and players compete for the top of the leaderboard. Meanwhile, the bot admin quickly checks that everything is running smoothly (`!inspect health`). 

This is Rosey in her element - entertaining, reliable, and fun.

---

## 7. Success metrics

### 7.1 User-centric metrics

- Commands used per day (target: 50+ across all fun plugins)
- Unique users interacting with plugins per week
- Trivia games completed per week
- Countdown announcements delivered on time (target: 100%)

### 7.2 Business metrics

- Zero bot crashes caused by plugin failures
- Plugin hot-reload success rate (target: 100%)
- Time to develop new plugin using patterns established (target: <4 hours for simple plugin)

### 7.3 Technical metrics

- Plugin load time: <100ms each
- Command response time: <50ms (95th percentile)
- Memory usage: <10MB per plugin
- Test coverage: >90% per plugin

---

## 8. Technical considerations

### 8.1 Integration points

- **NATS Event Bus**: All plugin communication via NATS subjects
- **Database Service**: Trivia and countdown use `database-service` for persistence
- **Plugin Manager**: Hot-reload, lifecycle management
- **Storage API**: Parameterized SQL from Sprint 17 for safe database access

### 8.2 Data storage & privacy

- Trivia stores: player stats, game history (username, scores, timestamps)
- Countdown stores: recurring schedules, channel associations
- No sensitive data collected; all data is gameplay-related
- Data can be purged per-user on request

### 8.3 Scalability & performance

- Plugins are designed for single-channel to multi-channel use
- Trivia supports concurrent games across different channels
- Countdown uses efficient timer scheduling (not polling)
- All database operations use parameterized queries (Sprint 17)

### 8.4 Potential challenges

- **Timer accuracy**: Countdown announcements should be within ±5 seconds
- **Game state recovery**: Trivia must handle bot restarts gracefully
- **Event ordering**: Multiple rapid answers in trivia must be processed correctly
- **Hot reload during game**: Active trivia games should pause/resume gracefully

---

## 9. Milestones & sequencing

### 9.1 Project estimate

- **Size**: Medium (5 plugins, 2-3 weeks)
- **Complexity**: Varied (simple to complex)

### 9.2 Team size & composition

- **Team**: 1 developer + 1 AI pair programmer (GitHub Copilot)
- **Roles**: Development, testing, documentation

### 9.3 Suggested phases

**Sortie 1: Dice Roller** (1-2 days)
- Create plugin structure
- Implement dice parsing and rolling
- Add flip command
- Write tests
- Document usage

**Sortie 2: Magic 8-Ball** (1 day)
- Create plugin structure
- Implement response selection
- Add Rosey personality flavor
- Write tests
- Document usage

**Sortie 3: Countdown - Foundation** (2 days)
- Create plugin structure with timer infrastructure
- Implement one-time countdowns
- Add announcement intervals
- Write tests

**Sortie 4: Countdown - Advanced** (2 days)
- Add recurring countdown support
- Implement channel-specific schedules
- Add persistence across restarts
- Add list/cancel commands
- Write integration tests

**Sortie 5: Trivia - Foundation** (2-3 days)
- Create plugin structure with game state machine
- Implement start/answer/skip commands
- Add question database (JSON)
- Add timer-based question timeout
- Write tests

**Sortie 6: Trivia - Scoring & Persistence** (2 days)
- Implement scoring system with fast-answer bonus
- Add stats and leaderboard commands
- Add database persistence for player stats
- Write integration tests

**Sortie 7: Inspector** (2 days)
- Create plugin structure
- Implement all inspect commands
- Provide InspectorService
- Add wildcard event monitoring
- Write tests

**Sortie 8: Integration & Polish** (2-3 days)
- Integration testing across all plugins
- Performance profiling
- Documentation updates
- Plugin best practices guide
- Final review and merge

---

## 10. User stories

### 10.1 Dice roller stories

- **ID**: GH-DICE-001
- **Description**: As a chat user, I want to roll dice using standard notation so that I can make random decisions for games.
- **Acceptance criteria**:
  - `!roll 2d6` returns two d6 results and their sum
  - `!roll d20+5` returns one d20 result plus 5
  - Invalid notation shows helpful error message
  - Results display individual rolls and total

- **ID**: GH-DICE-002
- **Description**: As a chat user, I want to flip a coin so that I can make binary decisions.
- **Acceptance criteria**:
  - `!flip` returns either "Heads" or "Tails"
  - Result includes fun emoji (🪙)

### 10.2 Magic 8-Ball stories

- **ID**: GH-8BALL-001
- **Description**: As a chat user, I want to ask the 8-ball questions so that I can get fun fortune-telling responses.
- **Acceptance criteria**:
  - `!8ball <question>` returns a classic 8-ball response
  - Response includes 🎱 emoji
  - Response reflects Rosey's personality
  - Without a question, shows usage hint

### 10.3 Countdown stories

- **ID**: GH-COUNT-001
- **Description**: As a moderator, I want to create one-time countdowns so that I can announce upcoming events.
- **Acceptance criteria**:
  - `!countdown 5m Movie starting!` creates a 5-minute countdown
  - Announcements at 5m, 1m, and 0 (start)
  - Countdown ID returned for management

- **ID**: GH-COUNT-002
- **Description**: As a moderator, I want to create recurring countdowns so that weekly events are announced automatically.
- **Acceptance criteria**:
  - `!countdown friday 12:00 Weekend movies!` creates recurring Friday noon countdown
  - Countdown persists across bot restarts
  - Announces each Friday automatically

- **ID**: GH-COUNT-003
- **Description**: As a moderator, I want to manage countdowns so that I can see what's scheduled and cancel if needed.
- **Acceptance criteria**:
  - `!countdown list` shows all active countdowns
  - `!countdown cancel <id>` removes a countdown
  - Only moderators+ can cancel

### 10.4 Trivia stories

- **ID**: GH-TRIVIA-001
- **Description**: As a chat user, I want to start and play trivia games so that I can compete with friends.
- **Acceptance criteria**:
  - `!trivia start` begins a new game (if none active)
  - Questions display with A/B/C/D choices or text prompt
  - `!trivia answer B` submits an answer
  - Correct/incorrect feedback is immediate
  - Game ends after configured number of questions

- **ID**: GH-TRIVIA-002
- **Description**: As a trivia player, I want to track my stats and see the leaderboard so that I can compete over time.
- **Acceptance criteria**:
  - `!trivia stats` shows my games played, score, accuracy
  - `!trivia leaderboard` shows top 10 players
  - Stats persist across sessions

- **ID**: GH-TRIVIA-003
- **Description**: As a moderator, I want to stop trivia games so that I can manage the channel flow.
- **Acceptance criteria**:
  - `!trivia stop` ends the current game (moderator+)
  - Final scores displayed even when stopped early

### 10.5 Inspector stories

- **ID**: GH-INSP-001
- **Description**: As a bot administrator, I want to inspect plugin status so that I can diagnose issues.
- **Acceptance criteria**:
  - `!inspect plugins` lists all plugins with status
  - `!inspect plugin trivia` shows detailed trivia plugin info
  - `!inspect health` shows overall system health
  - Only administrators can use inspect commands

- **ID**: GH-INSP-002
- **Description**: As a bot administrator, I want to see event bus activity so that I can understand system behavior.
- **Acceptance criteria**:
  - `!inspect events` shows recent events and statistics
  - `!inspect services` shows registered services

---

## 11. Dependencies

### 11.1 Required infrastructure (already complete)

- ✅ NATS event bus (Sprint 14)
- ✅ Plugin manager with hot-reload (Sprint 14)
- ✅ Database service (Sprint 15)
- ✅ Storage API with parameterized SQL (Sprint 17)
- ✅ Quote-DB reference plugin (Sprint 16)

### 11.2 New dependencies

- None! All Sprint 18 plugins use existing infrastructure.

---

## 12. Risks & mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Timer drift in countdown | Low | Medium | Use absolute timestamps, not relative deltas |
| Trivia state corruption on hot-reload | Medium | Medium | Graceful pause/resume, state serialization |
| Scope creep (adding features) | Medium | Low | Strict adherence to PRD scope |
| Complex countdown scheduling | Medium | Medium | Start simple, iterate on recurring logic |

---

## 13. Future considerations

- **LLM-Trivia**: Generate questions dynamically (Sprint 19+)
- **Custom trivia categories**: User-submitted questions
- **Countdown integrations**: Discord webhooks, external calendars
- **Achievement system**: Badges for trivia champions, dice streaks
- **Polls integration**: If CyTube API allows, integrate with native polls

---

**Document Status:** Ready for Review  
**Next Steps:** Create SPEC files for each sortie after PRD approval
