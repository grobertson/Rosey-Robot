# Sprint 12: Funny Games - Product Requirements Document

**Sprint Name:** Funny Games (1997)

**Sprint Goal:** Ship a first wave of NATS-native chat game plugins that stress-test the new event-driven plugin architecture, showcase Rosey’s personality, and prove that user plugins can be powerful without ever endangering the core services.

**Status:** Draft

---

## 1. Overview

Sprint 12 is the first **game-focused, plugin-first** sprint built for the new Rosey architecture:

- Core services (CyTube connection, database service, Rosey core logic) stay small, stable, and boring.
- Everything playful (games, toys, utilities) runs as **plugins** that talk over **NATS**.
- Plugins can crash, restart, and evolve independently without taking down the bot.

This sprint delivers a **small but representative set of plugins**:

- `dice-roller` – Simple, stateless, baseline example.
- `quote-db` – Stateful, DB-backed, migration-friendly example.
- `trivia` – Long-lived game state, timers, high fan-out events.
- `inspector` – Introspection/ops plugin for observability.
- (Optional) `llm-trivia` – LLM-assisted trivia/riffing extension, if time.

The emphasis is on **architecture validation via fun features**: if these plugins feel rock-solid and easy to develop, the plugin system is ready for broader adoption.

---

## 2. Architecture Alignment

### 2.1 Current Architecture Snapshot

Rosey now runs as **Event-Driven Microservices** on a NATS bus:

- **Core Services (Stable)**
  - `cytube-connection` – Maintains websocket connection to CyTube and translates chat events into NATS messages.
  - `database-service` – Owns DB connections and exposes CRUD-style NATS subjects.
  - `rosey-core` – Handles basic commands (help, info, status), plugin bootstrap, and routing from chat commands to plugin subjects.

- **Plugins (Flexible)**
  - Each plugin is either:
    - An **in-process module** loaded by `rosey-core` that talks to NATS, or
    - A separate **microservice** that subscribes to NATS subjects directly.
  - Plugins must not hold references into core internals; all cross-talk goes through NATS and/or well-defined service APIs.

Architecture reference: see `README.md` diagram and the **Core vs Plugins** explanation already in the repo.

### 2.2 Plugin Architecture Principles

1. **Isolation by Default**
   - Plugins cannot crash the core process.
   - If a plugin fails, it is restarted or disabled without impacting CyTube connectivity.

2. **NATS-First Communication**
   - All plugin interactions (commands, events, callbacks) flow over NATS subjects:
     - Commands: `rosey.command.<plugin>.<action>` (e.g., `rosey.command.trivia.start`).
     - Replies: `rosey.reply.<plugin>.<corr_id>` for request/reply patterns.
     - Events: `<plugin>.<event>` (e.g., `trivia.game_started`, `quotes.added`).

3. **Storage Through Services**
   - Plugins NEVER own global DB connections to production databases.
   - Persistent state is accessed via:
     - `database-service` (preferred): `db.query.<plugin>....`, `db.exec.<plugin>....` subjects.
     - Small, private SQLite files for experimental/local-only data (dev mode only), behind a storage abstraction.

4. **Hot-Reload Friendly**
   - `rosey-core` can reload plugin code/config without restarting core services.
   - Long-lived plugins (like `trivia`) must respond gracefully to reload signals (flush timers, save state if needed).

5. **Observable by Design**
   - All plugins emit structured events on success/failure paths.
   - `inspector` consumes these events to build health dashboards (chat + web).

---

## 3. Target Plugin Set (Sprint 12)

### 3.1 Dice Roller (Plugin `dice-roller`)

**Role:** Introductory stateless plugin and example template.

**Responsibilities:**
- Listen on `rosey.command.dice.roll`.
- Parse notation like `2d6`, `d20`, `3d8+5`.
- Respond on the provided reply subject with a formatted result.
- Emit `dice.roll_performed` events with anonymized metrics (count, sides, total).

**Architecture Notes:**
- Runs in-process with `rosey-core` initially, but spec must not depend on that.
- No direct DB access; purely CPU-bound.
- Serves as canonical “Hello, plugin” reference implementation.

### 3.2 Quote Database (Plugin `quote-db`)

**Role:** First stateful plugin using the shared database service.

**Responsibilities:**
- Commands (via NATS or chat):
  - `!quote add <text>`
  - `!quote get <id>`
  - `!quote random`
  - `!quote search <text>`
  - `!quote stats`
- Store quotes (text, added_by, timestamps) using `database-service` APIs.
- Emit `quote.added`, `quote.deleted` events for logging/analytics plugins.

**Storage Model:**
- Schema managed by `database-service` migrations.
- Plugin calls:
  - `db.exec.quote-db.insert` for writes.
  - `db.query.quote-db.search` / `db.query.quote-db.random` for reads.
- In dev mode, MAY use a private SQLite file via storage abstraction; in prod, must use the shared DB.

### 3.3 Trivia Game (Plugin `trivia`)

**Role:** Flagship game; validates complex state, timers, concurrency, and event publishing.

**Responsibilities:**
- Subscribe to:
  - `rosey.command.trivia.start|answer|skip|stop|stats|leaderboard`.
- Maintain per-channel game state.
- Use timers (async or scheduling service) for question timeouts.
- Persist player stats and history via `database-service`.
- Emit rich events:
  - `trivia.game_started`, `trivia.question_asked`, `trivia.answer_submitted`, `trivia.game_finished`.

**Deployment Shape:**
- Strong candidate for a **separate process plugin** that:
  - Connects to NATS.
  - Does not share memory with `rosey-core`.
- Gracefully handles reconnects to NATS and hot configuration updates.

### 3.4 Plugin Inspector / Introspection Service (Plugin `inspector`)

**Role:** Operational observability for plugins, events, and services.

**Responsibilities:**
- Subscribe to `plugin.*`, `trivia.*`, `quote.*`, and other key event families.
- Maintain a small in-memory metrics snapshot.
- Provide query endpoints over NATS:
  - `inspector.query.plugins`
  - `inspector.query.plugin.<name>`
  - `inspector.query.events`
  - `inspector.query.health`
- Expose chat commands via `rosey-core` front-end:
  - `!inspect plugins|plugin <name>|events|services|health`.

**Architecture Notes:**
- Lives as a service on the bus; `rosey-core` is just one client.
- Future integration: web dashboard can reuse the same `inspector` subjects.

### 3.5 Optional: LLM Trivia / Riffing Plugin (`llm-trivia`)

**Role:** Showcase integration between the LLM service and games.

**Responsibilities (if included):**
- Given the current playlist item (from a playlist/now-playing plugin), ask the LLM for one of:
  - A custom trivia question and answer.
  - A riff or MST3K-style “heckle” line.
- Expose commands like `!llmtrivia` or augment `!trivia` with a mode that sources questions from LLM.

**Constraints:**
- Must respect rate limits and cost controls on the LLM service.
- Output must be filtered/sanitized to stay within channel norms.

---

## 4. Storage Model for Plugins (High-Level)

> Detailed storage contracts will be refined with you after this PRD; this section captures intent, not final schema.

### 4.1 Database Service Contracts

Plugins use a shared `database-service` accessed over NATS. The service:

- Owns the **SQLAlchemy/Postgres** connections.
- Provides a small set of **plugin-scoped subjects**, e.g.:
  - `db.exec.<plugin>.migrate`
  - `db.exec.<plugin>.write`
  - `db.query.<plugin>.read`
- Enforces that each plugin only touches its own tables/schemas.

Each Sprint 12 plugin will define:

- Its **logical schema** (tables, columns) in its SPEC.
- A set of **query primitives** it needs (insert quote, get random quote, fetch stats, etc.).

### 4.2 Local vs Shared Storage

- **Development / experiments:**
  - Plugins MAY use local SQLite via `plugin_storage.get_path("plugin-name.db")` for quick iteration.
  - This mode is explicitly non-production and can be disabled in prod configs.

- **Production:**
  - Plugins must use the shared database service so operations are traceable and centrally managed.
  - Migration scripts live alongside plugin code but are executed by `database-service`.

### 4.3 Failure Modes

- If `database-service` is down:
  - Plugins must degrade gracefully:
    - `quote-db` responds with a friendly error instead of crashing.
    - `trivia` may run in **stateless mode** (no stats), or refuse to start new games.

---

## 5. Testing & Validation Goals

Sprint 12 is “Funny Games,” but also a **validation sprint** for the plugin model.

### 5.1 Functional Validation

- All command paths work via chat → `rosey-core` → NATS → plugin → NATS → chat.
- Plugins can be started, stopped, and hot-reloaded without impacting CyTube connectivity.
- Storage operations are correctly routed through `database-service`.

### 5.2 Isolation & Resilience

- Intentionally crash a plugin process:
  - Core connection remains healthy.
  - Other plugins unaffected.
- Drop NATS temporarily:
  - Plugins reconnect and resume without manual intervention.
- Simulate DB outages:
  - Plugins fail gracefully with clear chat errors and log entries.

### 5.3 Observability

- `inspector` can answer:
  - Which plugins are loaded and healthy.
  - Basic metrics (command counts, error counts, event traffic).
  - A simple “system health” rollup suitable for chat and web display.

---

## 6. Out of Scope

For Sprint 12, we explicitly **do not**:

- Migrate existing legacy bot logic into plugins (that’s a later sprint).
- Implement full web dashboards (we only ensure that `inspector` is ready for one).
- Optimize for extreme scale; we’re targeting a single active channel with modest traffic to start.

---

## 7. Acceptance Criteria (Sprint 12)

Sprint 12 is considered complete when:

1. **Architecture**
   - [ ] All Sprint 12 plugins communicate exclusively via NATS subjects.
   - [ ] No plugin holds a direct production DB connection; all persistent writes go through `database-service`.

2. **Plugins**
   - [ ] `dice-roller` responds to roll commands and emits roll events.
   - [ ] `quote-db` supports add/get/random/search/stats and persists via `database-service`.
   - [ ] `trivia` runs full games with timers, multi-player scoring, and persistent stats.
   - [ ] `inspector` can list plugins, show basic metrics, and provide a system health summary.
   - [ ] (Optional) `llm-trivia` can generate at least one LLM-backed trivia or riffing interaction.

3. **Resilience & Observability**
   - [ ] Killing a plugin process does not drop CyTube connectivity or crash `rosey-core`.
   - [ ] NATS disconnect/reconnect scenarios are handled without manual restarts.
   - [ ] `inspector` provides enough data to debug a misbehaving plugin from chat.

4. **Documentation**
   - [ ] Updated SPECS for each plugin reflect the new architecture and storage model.
   - [ ] README/architecture docs reference Sprint 12 as the canonical example of “safe, powerful plugins on a bus.”

---

**Document Status:** Draft for review

**Next Steps:**
- Align on the `database-service` contract for plugin storage.
- Update each SPEC (`SPEC-Plugin-*.md`) to match this PRD.
- Decide whether `llm-trivia` lands in Sprint 12 or a follow-on sprint.
