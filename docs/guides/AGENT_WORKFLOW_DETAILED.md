# Agent Workflow Detailed Guide

**Project:** Rosey-Robot  
**Last Updated:** November 21, 2025  

This guide provides comprehensive details on each phase of the agent-assisted development workflow.

---

## Table of Contents

1. [Phase 1: Product Requirements (PRD)](#phase-1-product-requirements-prd)
2. [Phase 2: Technical Specifications (SPEC)](#phase-2-technical-specifications-spec)
3. [Phase 3: Implementation (Code)](#phase-3-implementation-code)
4. [Phase 4: Documentation (Docs)](#phase-4-documentation-docs)
5. [Phase 5: Review and Merge (PR)](#phase-5-review-and-merge-pr)
6. [Example: LLM Integration Walkthrough](#example-llm-integration-walkthrough)

---

## Phase 1: Product Requirements (PRD)

### Purpose
Define the feature from a product perspective before writing any code.

### Format
`docs/sprints/{N}-{sprint-name}/PRD-{feature-name}.md`

### Contents

1. **Executive Summary**: High-level feature overview
2. **Problem Statement**: What problem are we solving?
3. **Goals and Success Metrics**: Measurable outcomes
4. **User Stories**: Detailed acceptance criteria
5. **Technical Architecture**: System design and data flow
6. **Dependencies**: External services, libraries, system requirements
7. **Security and Privacy**: Considerations and mitigations
8. **Rollout Plan**: Deployment phases and monitoring
9. **Future Enhancements**: Post-release roadmap
10. **Open Questions**: Unresolved issues to address

### Example
See [`docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md`](../../sprints/completed/2-start-me-up/PRD-LLM-Integration.md) for a complete PRD example.

### Agent Usage

```markdown
Prompt: "Create a PRD for adding LLM chat integration to Rosey. 
The bot should respond to mentions using OpenAI or Ollama. Include:
- Problem statement and goals
- User stories with acceptance criteria
- Technical architecture with data flow
- Security considerations
- Rollout plan and monitoring strategy"

Agent generates: Complete PRD with all sections filled out based on 
project context and requirements.
```

### Best Practices

- **Be Comprehensive**: Cover all aspects even if they seem obvious
- **Include Examples**: Provide concrete use cases and scenarios
- **Define Success**: Clear metrics for measuring feature success
- **Consider Edge Cases**: Security, performance, error scenarios
- **Link Resources**: Reference external docs, APIs, similar implementations

---

## Phase 2: Technical Specifications (SPEC)

### Purpose
Break down PRD into logical sorties (work units that may span multiple commits).

### Format
`docs/sprints/{N}-{sprint-name}/SPEC-Sortie-{N}-{sortie-name}.md`

### Contents per Sortie

1. **Overview**: What this sortie achieves
2. **Scope and Non-Goals**: What's included/excluded
3. **Requirements**: Functional and non-functional
4. **Design**: Architecture diagrams, data structures, API interactions
5. **Implementation**: Modified files, new methods, code structure
6. **Testing**: Unit tests, integration tests, manual checklist
7. **Acceptance Criteria**: Concrete checkboxes for completion
8. **Rollout**: Deployment steps and monitoring
9. **Documentation**: Code comments, API docs, user guides

### Example
See [`docs/sprints/completed/2-start-me-up/SPEC-Sortie-1-LLM-Foundation.md`](../../sprints/completed/2-start-me-up/SPEC-Sortie-1-LLM-Foundation.md) for a complete SPEC example.

### Agent Usage

```markdown
Prompt: "Based on the LLM PRD at docs/sprints/2-start-me-up/PRD-LLM-Integration.md, 
create specs for a nano-sprint sortie. Break it into 6 logical sorties:

1. Foundation - Basic LLM initialization and trigger detection
2. Remote Ollama - Support for remote Ollama servers
3. Trigger refinement - Improve case-insensitive matching
4. Username correction - Handle username changes mid-conversation
5. Deployment automation - Update systemd configuration
6. Documentation - Complete all docs and create PR

For each sortie, create a detailed SPEC file following the template structure."

Agent generates: 6 detailed SPEC files (SPEC-Sortie-1 through SPEC-Sortie-6) 
with implementation plans.
```

### Best Practices

- **Logical Sorties**: Each sortie should be a cohesive unit of work
- **Flexible Commits**: Make commits as often as needed within a sortie
- **Clear Dependencies**: Specify which sorties must come first
- **Detailed Implementation**: List specific files, methods, and changes
- **Comprehensive Testing**: Define unit tests, integration tests, manual checks
- **Acceptance Criteria**: Concrete checkboxes that can be verified

---

## Phase 3: Implementation (Code)

### Purpose
Execute the spec with agent assistance using iterative development.

### Approach
Work through each commit in the sortie sequentially, implementing, testing, and committing before moving to the next.

### Steps per Commit

#### 1. Read the Spec

```markdown
Prompt: "Read SPEC-Sortie-1-LLM-Foundation.md and implement it. 
Review the existing code in lib/bot.py and common/config.py first 
to understand the current patterns."
```

#### 2. Generate Code

The agent will:
- Create/modify files based on spec
- Follow existing code patterns and conventions
- Include docstrings and inline comments
- Add type hints for all parameters and returns

```markdown
Prompt: "Implement the _setup_llm() method as specified in section 4.1.
Follow the async patterns used in _setup_db() and include error handling."
```

#### 3. Write Tests

```markdown
Prompt: "Create unit tests for the LLM trigger detection system in 
tests/unit/test_llm.py. Test:
- Trigger detection for mentions
- Case-insensitive matching
- Rate limiting
- Error handling for API failures"
```

#### 4. Verify Acceptance Criteria

```markdown
Prompt: "Check all items in section 7 (Acceptance Criteria) of 
SPEC-Sortie-1-LLM-Foundation.md. Run the tests and verify each criterion."
```

#### 5. Commit Changes

```bash
git add .
git commit -m "LLM Foundation

- Add LLM provider initialization (OpenAI/Ollama)
- Implement message trigger detection
- Add in-memory conversation context
- Update configuration schema
- Add dependencies to requirements.txt

Implements: SPEC-Sortie-1-LLM-Foundation.md
Related: PRD-LLM-Integration.md"
```

### Agent Capabilities

- **Parallel Context Gathering**: Read multiple files simultaneously
- **Pattern Recognition**: Follow existing code conventions automatically
- **Test Generation**: Create comprehensive test suites
- **Documentation Updates**: Keep docs in sync with code changes
- **Edge Case Identification**: Suggest improvements and corner cases

### Troubleshooting

**Problem**: Agent generates code that doesn't match specification

**Solution**:
```markdown
Prompt: "The generated code doesn't match section 4.1 of the spec. 
Please re-read SPEC-Sortie-1-LLM-Foundation.md and implement exactly 
as specified, particularly the method signatures and error handling."
```

**Problem**: Agent uses different patterns than existing code

**Solution**:
```markdown
Prompt: "Review the existing code in lib/bot.py for style patterns. 
Then regenerate the new methods to match:
- Docstring format (Google-style)
- Error handling approach (log and raise)
- Logging conventions (self.logger with structured messages)
- Async patterns (use asyncio.create_task for background work)"
```

---

## Phase 4: Documentation (Docs)

### Purpose
Keep documentation current with implementation.

### 4.1 Code Documentation

**Requirements**:
- Docstrings for all public methods (Google-style)
- Inline comments for complex logic
- Type hints for all parameters and returns

**Example**:

```python
async def _handle_llm_chat(self, username: str, message: str) -> None:
    """Generate and send LLM response to channel.
    
    This method handles the complete LLM interaction cycle:
    1. Check rate limits
    2. Add message to conversation context
    3. Query LLM provider
    4. Send response to channel
    5. Update rate limit state
    
    Args:
        username: Sender's current username (not user_id)
        message: The trigger message text that initiated the chat
    
    Raises:
        RateLimitError: If user has exceeded rate limits
        LLMError: If LLM provider returns an error
        
    Side Effects:
        - Sends response to channel chat via send_chat()
        - Updates rate limit state in memory
        - Appends message and response to conversation context
        - Logs interaction to debug log
    """
```

**Agent Usage**:

```markdown
Prompt: "Add comprehensive docstrings to all new methods in lib/bot.py. 
Follow Google-style format with Args, Returns, Raises, and Side Effects 
sections. Include type hints."
```

### 4.2 User Documentation

**Files to Update**:
- `README.md` - Feature list, quick start examples
- `docs/guides/{FEATURE}_GUIDE.md` - Detailed usage guide
- `QUICKSTART.md` - Quick setup instructions

**Agent Usage**:

```markdown
Prompt: "Update README.md to include LLM integration:
1. Add 'AI Chat Integration' to features list
2. Add LLM configuration example to quick start
3. Link to docs/guides/LLM_CONFIGURATION.md

Then create docs/guides/LLM_CONFIGURATION.md with:
- Step-by-step setup for OpenAI
- Step-by-step setup for local Ollama
- Step-by-step setup for remote Ollama
- Configuration examples for each scenario
- Troubleshooting section"
```

### 4.3 Architecture Documentation

**Files to Update**:
- `docs/ARCHITECTURE.md` - System components and data flow
- Architecture diagrams (if applicable)

**Agent Usage**:

```markdown
Prompt: "Update docs/ARCHITECTURE.md to include LLM integration:
1. Add LLM component to architecture diagram (text-based is fine)
2. Describe LLM provider initialization
3. Document conversation context management
4. Explain trigger detection flow
5. Add to component interaction diagram"
```

### 4.4 Deployment Documentation

**Files to Update**:
- Systemd service files
- Environment variable documentation
- Deployment checklists

**Agent Usage**:

```markdown
Prompt: "Update systemd/cytube-bot.service to include LLM environment variables:
- OPENAI_API_KEY (optional)
- OLLAMA_HOST (optional, default localhost:11434)

Add comments explaining each variable and update systemd/README.md 
with LLM configuration section."
```

---

## Phase 5: Review and Merge (PR)

### Purpose
Final review and integration into main branch.

### Steps

#### 1. Self-Review

```markdown
Prompt: "Review all changes in the 2-start-me-up nano-sprint for:
1. Code Quality:
   - Follows Python conventions (PEP 8)
   - Proper error handling
   - Comprehensive logging
   - Type hints on all methods
2. Test Coverage:
   - All new methods have tests
   - Edge cases covered
   - Mocking external dependencies
3. Documentation:
   - All methods have docstrings
   - User guides updated
   - Architecture docs current
4. Security:
   - API keys handled securely
   - Input validation present
   - Rate limiting implemented"
```

#### 2. Create Pull Request

**Title**: `[Sprint Name] Feature Name`

**Description Template**:
```markdown
## Summary
Brief description of the feature and why it was implemented.

## Related Documents
- PRD: docs/sprints/2-start-me-up/PRD-LLM-Integration.md
- Specs: SPEC-Sortie-1 through SPEC-Sortie-6

## Changes
### Commit 1: LLM Foundation
- Add LLM provider initialization
- Implement trigger detection

### Commit 2: Remote Ollama Support
- Add ollama_host configuration

[... list all commits ...]

## Testing
- [ ] All tests pass locally
- [ ] Manual testing completed
- [ ] Integration testing with OpenAI
- [ ] Integration testing with Ollama

## Deployment Notes
- Requires OPENAI_API_KEY or OLLAMA_HOST environment variable
- See docs/guides/LLM_CONFIGURATION.md for setup

## Checklist
- [ ] Code reviewed by agent
- [ ] Documentation updated
- [ ] Tests pass
- [ ] No security issues
```

#### 3. Automated Checks

Run full test suite:
```bash
pytest --cov --cov-report=term-missing
```

Lint code:
```bash
ruff check .
mypy lib/ bot/
```

#### 4. Agent-Assisted Review

```markdown
Prompt: "Act as a code reviewer. Review this PR for:

1. Architectural Consistency:
   - Does it follow existing patterns?
   - Are there better ways to structure this?
   
2. Potential Bugs:
   - Race conditions in async code
   - Error handling gaps
   - Edge cases not covered
   
3. Performance:
   - Inefficient loops or operations
   - Unnecessary blocking calls
   - Memory leaks
   
4. Security:
   - API key exposure risks
   - Input validation gaps
   - Rate limiting effectiveness

Provide specific feedback with line numbers and suggestions."
```

#### 5. Merge to Main

After review and CI passes:
- Squash commits if needed (one commit per sortie is fine)
- Update `CHANGELOG.md` with new feature entry
- Tag release if applicable: `v0.4.0`

---

## Example: LLM Integration Walkthrough

### Timeline

**Sprint**: `2-start-me-up`  
**Feature**: LLM Chat Integration  
**Duration**: 3 days  
**Commits**: 6  

### Day 1: Planning (2 hours)

#### Write PRD

```markdown
Prompt: "Create a PRD for adding LLM integration to Rosey. 
The bot should:
- Support OpenAI and Ollama providers
- Respond when mentioned in chat
- Maintain conversation context
- Implement rate limiting
- Work with both local and remote Ollama servers

Include user stories, architecture, security considerations, 
cost analysis, and deployment plan."
```

Output: [`docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md`](../../sprints/completed/2-start-me-up/PRD-LLM-Integration.md)

#### Create Commit Specs

```markdown
Prompt: "Break the LLM PRD into 6 commit specs covering:
1. Basic OpenAI/Ollama support and trigger detection
2. Remote Ollama server configuration
3. Case-insensitive trigger matching improvements
4. Username correction for mid-conversation name changes
5. Systemd service deployment automation
6. Complete documentation and PR creation

Create SPEC-Sortie-1 through SPEC-Sortie-6 with full implementation details."
```

Output: 6 SPEC files in `docs/sprints/completed/2-start-me-up/`

### Day 2: Implementation (6 hours)

#### Commit 1: Foundation (90 minutes)

```markdown
Prompt: "Implement SPEC-Sortie-1-LLM-Foundation.md. 
Read lib/bot.py and common/config.py first to understand existing patterns."
```

**Changes**:
- Modified: `lib/bot.py` - Added `_setup_llm()`, `_check_llm_trigger()`, `_handle_llm_chat()`
- Modified: `common/config.py` - Added LLM config validation
- Modified: `bot/rosey/config.json.dist` - Added LLM configuration section
- Added: `requirements.txt` - `openai`, `ollama` dependencies

**Tests**:
```markdown
Prompt: "Create tests/unit/test_llm.py with tests for:
- LLM initialization with OpenAI
- LLM initialization with Ollama
- Trigger detection for mentions
- Rate limiting behavior
- Error handling for missing API keys"
```

**Commit**:
```bash
git commit -m "LLM Foundation

- Add LLM provider initialization (OpenAI/Ollama)
- Implement message trigger detection
- Add in-memory conversation context
- Update configuration schema
- Add dependencies to requirements.txt

Implements: SPEC-Sortie-1-LLM-Foundation.md
Related: PRD-LLM-Integration.md"
```

#### Commit 2: Remote Ollama (45 minutes)

```markdown
Prompt: "Implement SPEC-Sortie-2-Ollama-Remote-Support.md"
```

**Changes**:
- Modified: `lib/bot.py` - Updated `_setup_llm()` to support `ollama_host`
- Modified: `bot/rosey/config.json.dist` - Added `ollama_host` example

**Commit**:
```bash
git commit -m "Add remote Ollama server support

- Support ollama_host in configuration
- Default to localhost:11434 if not specified
- Update config example with remote Ollama

Implements: SPEC-Sortie-2-Ollama-Remote-Support.md"
```

#### Commit 3: Trigger Refinement (30 minutes)

```markdown
Prompt: "Implement SPEC-Sortie-3-Trigger-System-Refinement.md"
```

**Changes**:
- Modified: `lib/bot.py` - Update `_check_llm_trigger()` for case-insensitive matching

**Commit**:
```bash
git commit -m "Improve trigger detection system

- Add case-insensitive bot name matching
- Improve trigger word detection logic

Implements: SPEC-Sortie-3-Trigger-System-Refinement.md"
```

#### Commit 4: Username Correction (60 minutes)

```markdown
Prompt: "Implement SPEC-Sortie-4-Username-Correction.md"
```

**Changes**:
- Modified: `lib/bot.py` - Added `_on_set_user_profile()` handler
- Added: Context correction logic in conversation history

**Tests**:
```markdown
Prompt: "Add tests for username correction in test_llm.py"
```

**Commit**:
```bash
git commit -m "Add username correction system

- Track username changes via setUserProfile events
- Update conversation context when usernames change
- Maintain accurate conversation history

Implements: SPEC-Sortie-4-Username-Correction.md"
```

### Day 3: Deployment & Documentation (3 hours)

#### Commit 5: Deployment (60 minutes)

```markdown
Prompt: "Implement SPEC-Sortie-5-Deployment-Automation.md"
```

**Changes**:
- Modified: `systemd/cytube-bot.service` - Added LLM environment variables
- Updated: `systemd/README.md` - LLM configuration section

**Commit**:
```bash
git commit -m "Add systemd LLM configuration

- Add OPENAI_API_KEY environment variable
- Add OLLAMA_HOST environment variable
- Document LLM configuration in systemd README

Implements: SPEC-Sortie-5-Deployment-Automation.md"
```

#### Commit 6: Documentation (90 minutes)

```markdown
Prompt: "Implement SPEC-Sortie-6-Documentation-PR.md

Update:
1. README.md - Add LLM to features, add quick start example
2. docs/ARCHITECTURE.md - Add LLM component and flow
3. Create docs/guides/LLM_CONFIGURATION.md - Complete setup guide
4. CHANGELOG.md - Add v0.4.0 entry"
```

**Changes**:
- Updated: `README.md`
- Updated: `docs/ARCHITECTURE.md`
- Created: `docs/guides/LLM_CONFIGURATION.md`
- Updated: `CHANGELOG.md`

**Commit**:
```bash
git commit -m "Complete LLM documentation

- Update README with LLM features and examples
- Add LLM to architecture documentation
- Create comprehensive LLM configuration guide
- Add CHANGELOG entry for v0.4.0

Implements: SPEC-Sortie-6-Documentation-PR.md
Completes: PRD-LLM-Integration.md"
```

#### Create Pull Request

```markdown
Title: [2-start-me-up] LLM Chat Integration

Description:
Complete implementation of LLM chat integration for Rosey.

Related Documents:
- PRD: docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md
- Specs: SPEC-Sortie-1 through SPEC-Sortie-6

Testing: All tests pass, manual testing completed with OpenAI and Ollama.
```

### Outcome

- **Code**: Fully functional LLM integration with 95% test coverage
- **Docs**: Complete user guide, architecture updates, deployment docs
- **Time**: 11 hours total (2 planning, 6 implementation, 3 documentation)
- **Quality**: No security issues, comprehensive error handling, production-ready

---

## Summary

This detailed workflow ensures:

1. **Clear Planning**: PRDs define "what" and "why" before "how"
2. **Structured Implementation**: SPECs break work into logical, testable sorties
3. **Quality Code**: Agent assistance maintains consistency and coverage
4. **Living Documentation**: Docs stay current with implementation
5. **Thorough Review**: Multi-layered checks catch issues before merge

By following this workflow, features are delivered rapidly without sacrificing quality, testing, or documentation.

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**See Also**: [AGENTS.md](../../AGENTS.md), [AGENT_TOOLS_REFERENCE.md](AGENT_TOOLS_REFERENCE.md), [AGENT_PROMPTING_GUIDE.md](AGENT_PROMPTING_GUIDE.md)
