# PRD: Plugin Storage Foundation

## 1. Product overview

### 1.1 Document title and version

* PRD: Plugin Storage Foundation
* Version: 0.1-draft

### 1.2 Product summary

Rosey’s new plugin architecture needs a **first-class storage layer** that gives plugin authors a great experience without compromising stability. This project introduces a shared **database service** and a set of **NATS-based storage APIs** that plugins can rely on for both simple key/value data and structured relational data, while still allowing local SQLite for experiments.

The goal is to make it **trivial** to write plugins that persist state safely in production, while keeping the APIs small, consistent, and observable.

## 2. Goals

### 2.1 Business goals

* Enable third-party and first-party plugins to store state without each inventing its own DB strategy.
* Reduce operational risk by centralizing production DB access in a dedicated service.
* Improve debuggability and observability for all data access coming from plugins.
* Lay the foundation required for game-focused sprints (e.g., Funny Games) and future utilities.

### 2.2 User goals

* As a plugin author, I can persist small bits of state with a **simple KV API**.
* As a plugin author, I can define tables and run basic CRUD operations without writing raw SQL.
* As an advanced user, I can still use **parameterized SQL** for complex queries (handled in a follow-up advanced PRD).
* As an operator, I can see which plugins are hitting the DB and how.

### 2.3 Non-goals

* Providing a full ORM abstraction to plugins.
* Solving cross-plugin data sharing – each plugin owns its own logical schema/namespace.
* Implementing the advanced parameterized-SQL API (tracked in a separate PRD).

## 3. User personas

### 3.1 Key user types

* Plugin author (core maintainer)
* Plugin author (external contributor)
* Bot operator / SRE

### 3.2 Basic persona details

* **Core maintainer**: Deep knowledge of Rosey internals; wants powerful primitives but also guardrails for others.
* **External contributor**: Comfortable with Python and JSON, less so with DB and NATS internals; wants copy/pasteable examples.
* **Operator/SRE**: Cares about reliability, migrations, backups, and being able to answer “what is this plugin doing to my DB?”

### 3.3 Role-based access

* **Plugins**: May only access their own keyspace and tables via the database service.
* **Database service**: Full DB access; enforces per-plugin boundaries.
* **Operators**: Can configure DB backends, limits, and view metrics/logs for storage operations.

## 4. Functional requirements

* **Database service (core)** (Priority: Must-have)
  * Expose NATS request/reply subjects for plugin storage.
  * Own and manage the SQLAlchemy/Postgres (and dev SQLite) connections.
  * Enforce plugin-level isolation for all storage operations.

* **Key/value API** (Priority: Must-have)
  * Provide `set`, `get`, `delete`, and `list` semantics over NATS.
  * Support optional TTL for keys.

* **Named row/CRUD API** (Priority: Must-have)
  * Provide `insert`, `select`, `search`, `update`, and `delete` operations using structured JSON, not raw SQL.
  * Support simple operators (e.g., `$inc`, `$max`) for counters and best-of fields.

* **Migrations hook** (Priority: Should-have)
  * Allow a plugin to trigger its own migrations via a standard subject.
  * Integrate with existing Alembic migration tooling.

* **Dev vs prod storage modes** (Priority: Should-have)
  * Clearly support local SQLite per-plugin in development.
  * Require database service usage for production in official docs.

* **Observability** (Priority: Should-have)
  * Emit structured events for slow queries, errors, and migration operations.
  * Offer basic metrics suitable for consumption by the inspector plugin.

## 5. User experience

### 5.1 Entry points & first-time user flow

* Plugin author reads a **Plugin Storage guide** and copies a minimal example:
  * KV example: store per-user preferences.
  * Row example: insert and fetch a `quotes` row.
* Plugin config declares which mode(s) it uses (KV only, KV+rows).
* In dev, the same code works against SQLite; in prod, against Postgres.

### 5.2 Core experience

* **Write small state quickly**: One or two helper calls from plugin code to set or get KV pairs.
* **Scale up gracefully**: When a plugin needs more than KV, the row API feels like a natural next step, not a rewrite.
* **Stay safe by default**: Plugins can’t accidentally query or mutate another plugin’s tables.

### 5.3 Advanced features & edge cases

* Time-limited keys (e.g., game sessions) expire automatically.
* DB outages produce clear errors to plugins without crashing them.
* Requests exceeding limits (size, time) fail with explicit error payloads.

### 5.4 UI/UX highlights

* Simple, consistent JSON payloads across KV and row APIs.
* Copy-pasteable examples embedded in docs and plugin specs.
* Clear error codes and messages in responses.

## 6. Narrative

Plugin authors start by using KV storage for simple state, then graduate to named row operations when they need richer data. They never open their own production DB connections; instead, they send small, well-defined JSON payloads to the database service over NATS. Operations are transparent, logged, and observable, so when something goes wrong, both developers and operators can see what happened and why. This makes writing new plugins fast and safe, while setting Rosey up for long-term maintainability.

## 7. Success metrics

### 7.1 User-centric metrics

* Time to first persistent plugin (from spec to working code).
* Number of plugins that adopt the storage service rather than ad-hoc DB access.

### 7.2 Business metrics

* Reduction in storage-related bugs or outages caused by plugins.
* Increased contribution rate of storage-using plugins.

### 7.3 Technical metrics

* Error rate for storage operations (< 1% under normal operation).
* 95th percentile latency for KV and CRUD requests.
* Coverage of storage APIs by automated tests.

## 8. Technical considerations

### 8.1 Integration points

* NATS message bus for all request/reply flows.
* Existing SQLAlchemy/Postgres stack used by the database service.
* Future `inspector` plugin for metrics and health checks.

### 8.2 Data storage & privacy

* Per-plugin schema or table prefixes to prevent cross-contamination.
* Clear guidance that plugins must not store sensitive PII without explicit review.

### 8.3 Scalability & performance

* Designed initially for a single busy channel but must not preclude future scaling.
* Reasonable limits on request sizes and result sets to protect the DB.

### 8.4 Potential challenges

* Balancing simplicity with enough flexibility for non-trivial plugins.
* Ensuring migrations are safe and idempotent when triggered by plugins.
* Preventing abuse or accidental heavy queries from a single plugin.

## 9. Milestones & sequencing

### 9.1 Project estimate

* Size: Medium
* Time estimate: ~1.5–2 weeks of focused work.

### 9.2 Team size & composition

* Team size: 1–2 engineers (you + future contributors).

### 9.3 Suggested phases

* **Phase 1**: Design and stub database service NATS API.
* **Phase 2**: Implement KV layer and tests.
* **Phase 3**: Implement named row/CRUD layer and migrations hook.
* **Phase 4**: Wire up observability and basic metrics.
* **Phase 5**: Update plugin docs and one reference plugin (e.g., quote DB) to use the new APIs.

## 10. User stories

### 10.1 Simple KV storage for plugins

* **ID**: GH-PSF-001
* **Description**: As a plugin author, I can store and retrieve small pieces of state (like per-user settings or last game status) using a simple key/value API over NATS, without learning SQL.
* **Acceptance criteria**:
  * I can call a helper in my plugin to set, get, delete, and list keys.
  * Keys are automatically namespaced per plugin.
  * KV operations succeed within an acceptable latency for typical workloads.
  * When a key is missing or expired, I get a clear “not found” result, not an exception.

### 10.2 Named row CRUD for structured data

* **ID**: GH-PSF-002
* **Description**: As a plugin author, I can define a simple table and perform CRUD operations using a named row API, so I don’t have to write raw SQL for common patterns.
* **Acceptance criteria**:
  * I can insert, select, search, update, and delete rows in a plugin-owned table via NATS.
  * I can express simple counters and “best score so far” logic using `$inc` and `$max` style operators.
  * All operations are constrained to my plugin’s tables; cross-plugin access is not possible.

### 10.3 Migrations for plugin-owned tables

* **ID**: GH-PSF-003
* **Description**: As a plugin author, I can evolve my schema over time using migrations that are executed by the database service, so I don’t have to ship ad-hoc SQL upgrade scripts.
* **Acceptance criteria**:
  * I can declare migrations in a standard location in my plugin.
  * I can trigger migrations via a NATS subject or CLI.
  * Migrations are idempotent and safe to run multiple times.
  * Failures are logged with enough detail to diagnose the problem.

### 10.4 Safe dev vs prod storage modes

* **ID**: GH-PSF-004
* **Description**: As a plugin author, I can use local SQLite files for quick experimentation in development, but official documentation clearly guides me to use the database service for production deployments.
* **Acceptance criteria**:
  * There is a documented, simple API for getting a per-plugin SQLite path in dev.
  * The docs explicitly discourage relying on local SQLite for production.
  * Configuration makes it possible to disable local-SQLite mode in production environments.

### 10.5 Observability for storage operations

* **ID**: GH-PSF-005
* **Description**: As an operator, I can see basic metrics and logs for plugin storage operations so that I can troubleshoot performance or reliability issues.
* **Acceptance criteria**:
  * Slow or failing operations emit structured logs/events with plugin name and operation type.
  * Basic metrics (counts, error rates, latency buckets) are available for the inspector plugin or monitoring stack.
  * When a plugin misbehaves (e.g., many failing queries), I can identify it quickly.
