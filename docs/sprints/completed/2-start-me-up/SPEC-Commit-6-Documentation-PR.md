# Technical Specification: Commit 6 - Documentation & PR

**Commit Title:** Documentation & PR  
**Feature:** Comprehensive Documentation and Pull Request Creation  
**Status:** ✅ Implemented  
**Related PRD Section:** 5.1 Nano-Sprint Deliverables (Item 6)  
**Dependencies:** All previous commits (1-5)  
**Target Release:** v2.1.0  

---

## 1. Overview

### 1.1 Purpose

Consolidate all LLM integration work into comprehensive documentation and create a pull request for review and merging to main branch, completing the nano-sprint development cycle.

### 1.2 Scope

- Update README.md with LLM integration information
- Create/update configuration guide
- Document deployment procedures
- Document API changes
- Create pull request with detailed description
- Tag commits appropriately
- Prepare for release v2.1.0

### 1.3 Non-Goals

- Code changes (all functionality complete in commits 1-5)
- Testing (covered in previous commits)
- Changelog updates (separate task for release)

---

## 2. Requirements

### 2.1 Functional Requirements

**FR-001: README Updates**
- Add LLM integration to Features section
- Add LLM configuration to Configuration section
- Add quick start guide for LLM setup
- Link to detailed documentation
- Include examples for OpenAI and Ollama

**FR-002: Configuration Guide**
- Document all `llm` configuration fields
- Provide examples for common scenarios
- Explain trigger patterns
- Document environment variable support
- Include troubleshooting tips

**FR-003: Deployment Documentation**
- Update systemd deployment guide (from Commit 5)
- Document remote Ollama setup
- Document security best practices
- Include monitoring and logging instructions

**FR-004: API Documentation**
- Document new methods: `_setup_llm()`, `_check_llm_trigger()`, `_handle_llm_chat()`, `_on_set_user_profile()`
- Document configuration schema changes
- Document event handling changes
- Include code examples

**FR-005: Pull Request**
- Create PR from `nano-sprint/brain-surgery` to `main`
- PR title: "feat: LLM Integration (OpenAI + Ollama)"
- PR description includes summary of all 6 commits
- PR description includes testing performed
- PR description includes breaking changes (none expected)
- PR references related issues/discussions

### 2.2 Non-Functional Requirements

**NFR-001: Documentation Quality**
- Clear, concise language
- Consistent formatting (Markdown)
- Code examples tested and working
- Links verified (no 404s)
- Screenshots/diagrams where helpful

**NFR-002: Discoverability**
- Table of contents in long documents
- Cross-references between related docs
- Searchable keywords
- Examples for common use cases

---

## 3. Design

### 3.1 Documentation Structure

```
README.md               (updated)
├── Features           (+ LLM integration)
├── Quickstart         (+ LLM setup)
├── Configuration      (+ llm section)
└── Documentation      (+ links to guides)

docs/
├── LLM_CONFIGURATION.md     (new)
│   ├── Overview
│   ├── OpenAI Setup
│   ├── Ollama Setup (local)
│   ├── Ollama Setup (remote)
│   ├── Trigger Configuration
│   ├── Advanced Topics
│   └── Troubleshooting
│
├── API_REFERENCE.md         (updated)
│   ├── LLM Methods
│   ├── Configuration Schema
│   └── Events
│
└── PRD-LLM-Integration.md   (already created)

systemd/
└── README.md          (updated in Commit 5)
```

### 3.2 Pull Request Template

```markdown
## PR Title
feat: LLM Integration (OpenAI + Ollama)

## Description
Adds LLM (Large Language Model) integration to Rosey, enabling the bot to respond to chat messages using OpenAI or Ollama. This nano-sprint implements complete LLM functionality including local and remote Ollama support, intelligent trigger detection, username correction, and production-ready deployment.

## Changes Summary

### Commit 1: LLM Foundation
- Basic OpenAI and Ollama provider support
- Message trigger system
- In-memory conversation context management
- Configuration schema for LLM settings

### Commit 2: Ollama Remote Support
- `ollama_host` configuration parameter
- Remote server connectivity via HTTP/HTTPS
- Connection validation on startup
- Network error handling

### Commit 3: Trigger System Refinement
- Case-insensitive username matching
- Multiple trigger pattern support
- Enhanced debug logging
- Edge case handling (punctuation, Unicode)

### Commit 4: Username Correction
- Automatic detection of username changes
- Context migration across name changes
- Rate limit state migration
- `setUserProfile` event handler

### Commit 5: Deployment Automation
- Updated systemd service file
- `OLLAMA_HOST` environment variable support
- Production deployment documentation
- Security hardening

### Commit 6: Documentation & PR
- Comprehensive README updates
- LLM configuration guide
- API reference updates
- This pull request

## Testing Performed

- [x] Unit tests for all core functions
- [x] Integration tests with live Ollama server (local)
- [x] Integration tests with remote Ollama server
- [x] Manual testing in CyTube channel
- [x] Username change testing
- [x] Rate limiting testing
- [x] Systemd service deployment testing
- [x] Documentation review

## Breaking Changes

None. All changes are additive and backward compatible.

## Configuration Migration

No migration needed. Existing configurations work as-is. To enable LLM features, add `llm` section to `config.json`:

```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "model": "llama3.2:3b"
  }
}
```

## Checklist

- [x] Code follows project style guidelines
- [x] Self-review completed
- [x] Comments added for complex code
- [x] Documentation updated
- [x] Tests added/updated
- [x] Tests pass locally
- [x] No new warnings
- [x] Dependent changes merged
- [x] Ready for review

## Related Issues

Closes #[issue-number] (if applicable)

## Reviewers

@[reviewer-username]

## Additional Notes

This PR represents 6 commits totaling ~1200 lines of new code and documentation. Key features:
- Supports OpenAI API and Ollama (local/remote)
- Production-ready with systemd deployment
- Comprehensive error handling and logging
- Full documentation and examples
```

---

## 4. Implementation

### 4.1 README.md Updates

**Section: Features** (add):
```markdown
### LLM Integration

- **AI-Powered Responses**: Respond to mentions using OpenAI or Ollama
- **Multiple Providers**: Support for OpenAI API, Ollama (local or remote)
- **Smart Triggers**: Configurable activation patterns (mentions, keywords)
- **Conversation Context**: Per-user conversation history tracking
- **Rate Limiting**: Prevent spam and manage API costs
- **Username Tracking**: Automatically handle username changes
- **Production Ready**: Systemd service with auto-restart and logging
```

**Section: Quickstart** (add subsection):
```markdown
#### With LLM Integration

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Choose LLM provider:**

   **Option A: Local Ollama**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Pull a model
   ollama pull llama3.2:3b
   ```

   **Option B: OpenAI API**
   - Get API key from https://platform.openai.com/

3. **Configure bot:**
   ```bash
   cp bot/rosey/config.json.dist bot/rosey/config.json
   nano bot/rosey/config.json
   ```

   Add LLM configuration:
   ```json
   {
     "llm": {
       "enabled": true,
       "provider": "ollama",
       "model": "llama3.2:3b",
       "llm_triggers": ["rosey", "@rosey"]
     }
   }
   ```

4. **Run bot:**
   ```bash
   python -m lib bot/rosey/config.json
   ```

5. **Test in channel:**
   ```
   You: hey rosey!
   Bot: Hello! How can I help you?
   ```

For detailed LLM configuration, see [docs/LLM_CONFIGURATION.md](docs/LLM_CONFIGURATION.md).
```

**Section: Configuration** (add):
```markdown
### LLM Configuration

Add `llm` section to enable AI responses:

```json
{
  "llm": {
    "enabled": true,
    "provider": "ollama",
    "model": "llama3.2:3b",
    "ollama_host": "http://localhost:11434",
    "system_prompt": "You are Rosey, a helpful chat bot.",
    "llm_triggers": ["rosey", "@rosey"],
    "llm_cooldown": 10,
    "max_history_messages": 10
  }
}
```

**Fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | bool | No | `false` | Enable LLM features |
| `provider` | string | Yes | - | "openai" or "ollama" |
| `model` | string | Yes | - | Model name |
| `ollama_host` | string | For Ollama | "http://localhost:11434" | Ollama server URL |
| `openai_api_key` | string | For OpenAI | - | OpenAI API key |
| `system_prompt` | string | No | Default | Bot personality |
| `llm_triggers` | array | No | `[bot_username]` | Activation patterns |
| `llm_cooldown` | number | No | `10` | Seconds between requests |
| `max_history_messages` | number | No | `10` | Context window size |

See [docs/LLM_CONFIGURATION.md](docs/LLM_CONFIGURATION.md) for detailed guide.
```

### 4.2 New Document: docs/LLM_CONFIGURATION.md

```markdown
# LLM Configuration Guide

Complete guide to configuring Rosey's LLM integration.

## Table of Contents

- [Overview](#overview)
- [Provider Setup](#provider-setup)
  - [OpenAI](#openai-setup)
  - [Ollama (Local)](#ollama-local-setup)
  - [Ollama (Remote)](#ollama-remote-setup)
- [Trigger Configuration](#trigger-configuration)
- [Advanced Topics](#advanced-topics)
- [Troubleshooting](#troubleshooting)

## Overview

Rosey can respond to chat messages using Large Language Models (LLMs) from:
- **OpenAI**: Cloud-based API (GPT-4o, GPT-4o-mini, etc.)
- **Ollama**: Self-hosted models (Llama 3.2, Llama 3.3, etc.)

## Provider Setup

### OpenAI Setup

1. **Get API Key:**
   - Go to https://platform.openai.com/
   - Create account and add payment method
   - Generate API key (Settings > API keys)

2. **Add to config.json:**
   ```json
   {
     "llm": {
       "enabled": true,
       "provider": "openai",
       "model": "gpt-4o-mini",
       "openai_api_key": "sk-proj-...",
       "system_prompt": "You are Rosey, a friendly chat bot.",
       "llm_triggers": ["rosey", "@rosey"],
       "llm_cooldown": 10
     }
   }
   ```

3. **Test:**
   ```bash
   python -m lib bot/rosey/config.json
   # In channel: "hey rosey!"
   ```

**Models:**
- `gpt-4o-mini`: Fast, cheap ($0.15/1M input tokens)
- `gpt-4o`: Smarter, more expensive ($2.50/1M input tokens)
- `gpt-3.5-turbo`: Older, budget option ($0.50/1M input tokens)

### Ollama Local Setup

1. **Install Ollama:**
   ```bash
   # Linux/Mac
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Windows
   # Download from https://ollama.ai/download
   ```

2. **Pull Model:**
   ```bash
   ollama pull llama3.2:3b   # 3B parameters (2GB RAM)
   # or
   ollama pull llama3.3:70b  # 70B parameters (40GB RAM, GPU recommended)
   ```

3. **Start Server:**
   ```bash
   ollama serve
   # Server runs on http://localhost:11434
   ```

4. **Add to config.json:**
   ```json
   {
     "llm": {
       "enabled": true,
       "provider": "ollama",
       "model": "llama3.2:3b",
       "system_prompt": "You are Rosey, a witty chat bot.",
       "llm_triggers": ["rosey"],
       "llm_cooldown": 5
     }
   }
   ```

5. **Test:**
   ```bash
   # Test Ollama directly
   curl http://localhost:11434/api/tags
   
   # Run bot
   python -m lib bot/rosey/config.json
   ```

### Ollama Remote Setup

Run Ollama on a separate GPU server for better performance.

1. **On GPU Server (192.168.1.100):**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   
   # Pull model
   ollama pull llama3.2:3b
   
   # Start server (listen on all interfaces)
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   
   # Configure firewall
   sudo ufw allow from 192.168.1.0/24 to any port 11434
   ```

2. **On Bot Server:**
   ```json
   {
     "llm": {
       "enabled": true,
       "provider": "ollama",
       "model": "llama3.2:3b",
       "ollama_host": "http://192.168.1.100:11434",
       "system_prompt": "You are Rosey.",
       "llm_triggers": ["rosey"]
     }
   }
   ```

3. **Test Connection:**
   ```bash
   curl http://192.168.1.100:11434/api/tags
   # Should return JSON with models
   ```

## Trigger Configuration

Triggers determine when the bot activates LLM responses.

### Basic Triggers

```json
{
  "llm_triggers": ["rosey"]
}
```

Bot responds to any message containing "rosey" (case-insensitive):
- "hey rosey!" ✅
- "ROSEY help" ✅
- "tell rosey to..." ✅

### Multiple Triggers

```json
{
  "llm_triggers": ["rosey", "@rosey", "hey rosey"]
}
```

Bot responds if **any** trigger matches:
- "rosey what time?" ✅ (matches "rosey")
- "@rosey help" ✅ (matches "@rosey")
- "hey rosey how are you?" ✅ (matches "hey rosey")

### Specific Phrases

```json
{
  "llm_triggers": ["rosey what", "rosey how", "rosey why"]
}
```

More specific = fewer false positives:
- "rosey what is this?" ✅
- "rosey how does it work?" ✅
- "tell rosey about..." ❌ (doesn't match any trigger)

### Tips

- Use `@mentions` to avoid false positives
- Add common phrases users actually say
- Test triggers in low-traffic channel first
- Monitor logs for unintended triggers

## Advanced Topics

### System Prompts

System prompts define bot personality and behavior.

**Basic:**
```json
{
  "system_prompt": "You are Rosey, a helpful assistant."
}
```

**Advanced:**
```json
{
  "system_prompt": "You are Rosey, a knowledgeable assistant in a gaming chat. You know about retro games, speedrunning, and streaming. Keep responses under 200 characters. Use casual language. Never spoil games."
}
```

**From File:**
```json
{
  "system_prompt_file": "bot/rosey/prompt.md"
}
```

**File Example (prompt.md):**
```markdown
# Identity
You are Rosey, a friendly chat bot for a CyTube channel.

# Personality
- Helpful and friendly
- Casual tone
- Occasionally witty

# Guidelines
- Keep responses under 200 characters
- If you don't know something, say so
- Don't discuss politics or religion
- Use emojis sparingly

# Channel Context
This is a video streaming channel where users watch videos together.
```

### Rate Limiting

Prevent spam and manage costs:

```json
{
  "llm_cooldown": 10  // Seconds between requests per user
}
```

Example:
```
14:30:00 - User: "hey rosey"
14:30:02 - Bot: "Hello!"
14:30:05 - User: "rosey help"  // Ignored (only 5s elapsed)
14:30:12 - User: "rosey help"  // ✅ Responded (12s elapsed)
```

**Per-User vs Global:**
- Current: Per-user cooldown (User A and User B can both trigger)
- Future: Global cooldown option

### Context Window

Control conversation history size:

```json
{
  "max_history_messages": 10  // Last N messages per user
}
```

**Memory Usage:**
- 10 messages ≈ 500-1000 tokens ≈ 0.5-1 KB per user
- 100 active users = 50-100 KB total

**Token Limits:**
- GPT-4o: 128k tokens (~64k messages)
- GPT-4o-mini: 128k tokens
- Llama 3.2: 4k tokens (~2k messages)

### Environment Variables

Override config with environment variables:

```bash
# Systemd service
[Service]
Environment="OLLAMA_HOST=http://192.168.1.100:11434"
Environment="OPENAI_API_KEY=sk-..."

# Or use environment file
EnvironmentFile=/etc/rosey-robot/env
```

**Environment file (/etc/rosey-robot/env):**
```bash
OLLAMA_HOST=http://192.168.1.100:11434
OPENAI_API_KEY=sk-proj-...
```

## Troubleshooting

### Bot Doesn't Respond

**Check 1: Is LLM enabled?**
```bash
grep "LLM enabled" logs/bot.log
# Expected: "LLM enabled: provider=..."
```

**Check 2: Does message match trigger?**
```bash
# Enable DEBUG logging
"log_level": "DEBUG"

# Look for trigger checks
grep "LLM trigger" logs/bot.log
```

**Check 3: Is user on cooldown?**
```bash
grep "cooldown" logs/bot.log
```

**Check 4: Is provider reachable?**
```bash
# Ollama
curl http://localhost:11434/api/tags

# OpenAI
curl -H "Authorization: Bearer $OPENAI_API_KEY" \
  https://api.openai.com/v1/models
```

### Slow Responses

**Ollama Local:**
- Use smaller model (3b instead of 70b)
- Use GPU if available
- Increase system RAM

**Ollama Remote:**
- Check network latency: `ping 192.168.1.100`
- Use faster network (1Gbps+ recommended)
- Move bot closer to Ollama server (same datacenter)

**OpenAI:**
- Use faster model (gpt-4o-mini)
- Check API status: https://status.openai.com/
- Increase timeout in code (default 30s)

### High API Costs

**OpenAI:**
1. Use gpt-4o-mini instead of gpt-4o
2. Reduce `max_history_messages`
3. Increase `llm_cooldown`
4. Set daily spending limit in OpenAI dashboard

**Example Savings:**
- gpt-4o-mini: $0.15/1M input tokens
- gpt-4o: $2.50/1M input tokens
- **Savings: 94%**

### False Positives

Bot responds to messages not intended for it.

**Solution 1: More specific triggers**
```json
// BAD: Too generic
"llm_triggers": ["bot"]

// GOOD: More specific
"llm_triggers": ["@rosey", "hey rosey"]
```

**Solution 2: Update system prompt**
```
"system_prompt": "You are Rosey. Only respond when directly addressed. If the message is not directed at you, say 'I think you're talking to someone else.'"
```

### Username Issues

**Problem:** Bot addresses user by old name after name change.

**Solution:** Already handled automatically! Bot listens for `setUserProfile` events and updates usernames.

**Verify:**
```bash
grep "Username changed" logs/bot.log
# Should show: "Username changed: 'Old' -> 'New'"
```

### Permission Denied (Systemd)

```bash
# Fix permissions
sudo chown -R cytube:cytube /opt/rosey-robot
sudo chmod 600 /opt/rosey-robot/bot/rosey/config.json
```

### Ollama Connection Refused

```bash
# Check if Ollama is running
systemctl status ollama

# Start Ollama
ollama serve

# Check port
netstat -tulpn | grep 11434
```

## Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Ollama Documentation](https://ollama.ai/docs)
- [Rosey Architecture](../ARCHITECTURE.md)
- [Systemd Deployment](../systemd/README.md)
```

### 4.3 Update API_REFERENCE.md

Add new section:

```markdown
## LLM Integration Methods

### `_setup_llm()`

Initialize LLM provider based on configuration.

**Signature:**
```python
async def _setup_llm(self) -> None
```

**Description:**
- Initializes OpenAI or Ollama client
- Tests connection to provider
- Logs success or failure
- Sets `self.llm_client` on success

**Side Effects:**
- May log errors if provider unavailable
- Sets `self.llm_client = None` on failure

**Example:**
```python
bot.llm_config = {"provider": "ollama", "model": "llama3.2"}
await bot._setup_llm()
```

---

### `_check_llm_trigger(message, username)`

Check if message matches configured trigger patterns.

**Signature:**
```python
def _check_llm_trigger(self, message: str, username: str = None) -> bool
```

**Parameters:**
- `message` (str): Raw chat message text
- `username` (str, optional): Username for logging

**Returns:**
- `True` if any trigger matched
- `False` if no trigger matched

**Description:**
- Case-insensitive substring matching
- Supports multiple trigger patterns
- Logs matches at DEBUG and INFO levels

**Example:**
```python
if bot._check_llm_trigger("hey rosey!", "Alice"):
    # Trigger matched
    await bot._handle_llm_chat("Alice", "hey rosey!")
```

---

### `_handle_llm_chat(username, message)`

Generate and send LLM response.

**Signature:**
```python
async def _handle_llm_chat(self, username: str, message: str) -> None
```

**Parameters:**
- `username` (str): Sender's username
- `message` (str): Trigger message text

**Description:**
- Checks rate limit (cooldown)
- Assembles conversation context
- Calls LLM API (OpenAI or Ollama)
- Posts response to channel
- Updates context and rate limit state

**Side Effects:**
- Updates `self.llm_user_contexts[username]`
- Updates `self.llm_last_request[username]`
- Sends message to channel via `bot.chat()`

**Example:**
```python
await bot._handle_llm_chat("Alice", "what time is it?")
# Bot generates response and posts to channel
```

---

### `_on_set_user_profile(event, data)`

Handle username changes and migrate context.

**Signature:**
```python
async def _on_set_user_profile(self, event: str, data: dict) -> None
```

**Parameters:**
- `event` (str): Event name ('setUserProfile')
- `data` (dict): Event data
  - `name` (str): Old username
  - `profile.name` (str): New username

**Description:**
- Detects username changes
- Migrates conversation context
- Migrates rate limit state
- Logs migration results

**Side Effects:**
- Moves data from old to new username
- Deletes old username data

**Example:**
```python
# CyTube emits event when user changes name
# Handler automatically called:
await bot._on_set_user_profile('setUserProfile', {
    'name': 'Guest_123',
    'profile': {'name': 'Alice'}
})
# Context migrated from Guest_123 to Alice
```

---

## Configuration Schema Changes

### New Section: `llm`

```json
{
  "llm": {
    "enabled": true,
    "provider": "openai" | "ollama",
    "model": "string",
    "ollama_host": "string",
    "openai_api_key": "string",
    "system_prompt": "string",
    "llm_triggers": ["string"],
    "llm_cooldown": 10,
    "max_history_messages": 10
  }
}
```

See [LLM_CONFIGURATION.md](LLM_CONFIGURATION.md) for field descriptions.
```

### 4.4 Create Pull Request

**GitHub CLI:**
```bash
# Push all commits
git push origin nano-sprint/brain-surgery

# Create PR
gh pr create \
  --title "feat: LLM Integration (OpenAI + Ollama)" \
  --body-file docs/PR_DESCRIPTION.md \
  --base main \
  --head nano-sprint/brain-surgery
```

**PR Description File (docs/PR_DESCRIPTION.md):**

(Use the PR template from section 3.2)

---

## 5. Testing

### 5.1 Documentation Review

**Checklist:**
- [ ] README.md updated with LLM features
- [ ] Configuration examples tested and working
- [ ] Links verified (no 404s)
- [ ] Code examples have correct syntax
- [ ] Markdown renders correctly on GitHub
- [ ] Table of contents accurate
- [ ] Cross-references work

**Tools:**
```bash
# Check Markdown syntax
npx markdownlint-cli docs/*.md README.md

# Check links
npx markdown-link-check README.md

# Preview locally
grip README.md  # Opens in browser
```

### 5.2 PR Validation

**Pre-PR Checklist:**
- [ ] All tests pass
- [ ] No merge conflicts
- [ ] Branch up-to-date with main
- [ ] Commit messages follow convention
- [ ] No debug code or TODOs
- [ ] No commented-out code
- [ ] No secrets in commits

**Commands:**
```bash
# Update branch
git checkout nano-sprint/brain-surgery
git fetch origin
git rebase origin/main

# Run tests
python -m pytest tests/

# Check diff
git diff main...nano-sprint/brain-surgery

# Check for secrets
git log -p | grep -i "api.key\|password\|secret"
```

---

## 6. Acceptance Criteria

- [x] README.md updated with LLM integration section
- [x] README.md includes quickstart guide for LLM
- [x] README.md includes configuration table
- [x] docs/LLM_CONFIGURATION.md created with comprehensive guide
- [x] docs/API_REFERENCE.md updated with new methods
- [x] systemd/README.md updated (from Commit 5)
- [x] Pull request created with detailed description
- [x] PR includes testing summary
- [x] PR includes all 6 commits
- [x] All documentation links verified
- [x] All code examples tested
- [x] Markdown linting passes

---

## 7. Deployment

### 7.1 Post-Merge Tasks

After PR is merged to `main`:

1. **Tag Release:**
   ```bash
   git checkout main
   git pull
   git tag -a v2.1.0 -m "Release v2.1.0: LLM Integration"
   git push origin v2.1.0
   ```

2. **Update CHANGELOG.md:**
   ```markdown
   ## [2.1.0] - 2025-11-10
   
   ### Added
   - LLM integration with OpenAI and Ollama support
   - Automatic username change detection and context migration
   - Remote Ollama server connectivity
   - Case-insensitive trigger matching
   - Systemd deployment with environment variable support
   - Comprehensive LLM configuration guide
   
   ### Changed
   - Updated README with LLM documentation
   - Enhanced systemd service file
   
   ### Fixed
   - (none)
   ```

3. **Create GitHub Release:**
   ```bash
   gh release create v2.1.0 \
     --title "v2.1.0: LLM Integration" \
     --notes-file docs/RELEASE_NOTES_v2.1.0.md
   ```

4. **Announce:**
   - Update Discord/Slack announcement
   - Post to project forum/discussion board
   - Update documentation site (if any)

---

## 8. Documentation Maintenance

### 8.1 Ongoing Updates

**When to Update Docs:**
- New configuration options added
- New providers supported (e.g., Anthropic Claude)
- Breaking changes to API
- Common issues discovered
- User feedback suggests missing information

**Review Schedule:**
- After each release: Update CHANGELOG
- Monthly: Review and update troubleshooting guide
- Quarterly: Review all documentation for accuracy

### 8.2 Documentation Standards

**Formatting:**
- Use Markdown
- Include code examples in fenced blocks with language
- Use tables for reference information
- Use bullet lists for steps
- Use numbered lists for sequential procedures

**Writing Style:**
- Active voice
- Present tense
- Clear, concise sentences
- Define acronyms on first use
- Include examples

---

## 9. Related Specifications

- **SPEC-Commit-1-LLM-Foundation.md**: Core functionality documented
- **SPEC-Commit-2-Ollama-Remote-Support.md**: Remote setup documented
- **SPEC-Commit-3-Trigger-System-Refinement.md**: Trigger config documented
- **SPEC-Commit-4-Username-Correction.md**: Username handling documented
- **SPEC-Commit-5-Deployment-Automation.md**: Deployment guide documented

---

## 10. Sign-Off

**Specification Author:** GitHub Copilot  
**Review Date:** 2025-11-10  
**Implementation Status:** ✅ Complete  
**Pull Request:** #7 (nano-sprint/brain-surgery → main)  
**Target Release:** v2.1.0
