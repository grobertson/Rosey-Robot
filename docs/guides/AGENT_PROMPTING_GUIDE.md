# Agent Prompting Guide

**Project:** Rosey-Robot  
**Last Updated:** November 21, 2025  

This guide provides prompt patterns, advanced workflows, troubleshooting tips, and best practices for working with GitHub Copilot agents.

---

## Table of Contents

1. [Core Prompt Patterns](#core-prompt-patterns)
2. [Advanced Workflows](#advanced-workflows)
3. [Troubleshooting](#troubleshooting)
4. [Best Practices](#best-practices)
5. [Multi-Agent Collaboration](#multi-agent-collaboration)

---

## Core Prompt Patterns

### Pattern 1: Feature Planning

**Use**: Creating comprehensive Product Requirements Documents (PRDs)

**Template**:
```markdown
**Context**: We want to add [feature] to Rosey

**Task**: Create a comprehensive PRD that includes:
1. Executive summary and problem statement
2. User stories with acceptance criteria
3. Technical architecture with diagrams
4. Security and privacy considerations
5. Implementation timeline and rollout plan
6. Future enhancement roadmap

**Format**: Use the existing PRD template from 
docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md
```

**Example**:
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

**Output**: Complete PRD in `docs/sprints/{N}-{sprint-name}/PRD-{feature}.md`

---

### Pattern 2: Specification Breakdown

**Use**: Breaking PRD into implementable commit specifications

**Template**:
```markdown
**Context**: Given the PRD at docs/{N}-{sprint}/PRD-{feature}.md

**Task**: Break this into a logical sortie of atomic changes

**Requirements**:
- Each sortie can contain one or more commits
- Each commit must be independently testable
- Follow the SPEC template structure
- Include detailed implementation steps
- Define clear acceptance criteria

**Output**: Create SPEC-Sortie-N-Name.md files for the sortie
```

**Example**:
```markdown
Prompt: "Based on the LLM PRD at docs/sprints/2-start-me-up/PRD-LLM-Integration.md, 
create specs for a nano-sprint sortie. Break it into 6 logical commits:

1. Foundation - Basic LLM initialization and trigger detection
2. Remote Ollama - Support for remote Ollama servers
3. Trigger refinement - Improve case-insensitive matching
4. Username correction - Handle username changes mid-conversation
5. Deployment automation - Update systemd configuration
6. Documentation - Complete all docs and create PR

For each commit, create a detailed SPEC file following the template structure."
```

**Output**: 6 SPEC files in `docs/sprints/{N}-{sprint-name}/`

---

### Pattern 3: Implementation

**Use**: Executing a specification with agent assistance

**Template**:
```markdown
**Context**: Implement SPEC-Sortie-{N}-{name}.md

**Current State**: Read [relevant files] to understand existing patterns

**Task**: 
1. Add the methods/changes defined in section 4.1
2. Follow existing code style and conventions
3. Include docstrings and type hints
4. Update configuration files as specified

**Verification**: Check all items in section 7 (Acceptance Criteria)
```

**Example**:
```markdown
Prompt: "Implement SPEC-Sortie-1-LLM-Foundation.md. 
Read lib/bot.py and common/config.py first to understand existing patterns.
Then:
1. Add _setup_llm() method for provider initialization
2. Add _check_llm_trigger() for mention detection
3. Add _handle_llm_chat() for conversation management
4. Update configuration schema in bot/rosey/config.json.dist
5. Add dependencies to requirements.txt

Follow the async patterns used in _setup_db() and include comprehensive error handling."
```

**Output**: Code changes, tests, and documentation updates

---

### Pattern 4: Testing

**Use**: Creating comprehensive test suites

**Template**:
```markdown
**Context**: We just implemented [feature]

**Task**: Create comprehensive tests

**Requirements**:
1. Unit tests for each new method
2. Integration tests for end-to-end workflows
3. Edge case coverage
4. Mock external dependencies (API calls, etc.)

**Location**: tests/unit/test_[module].py and tests/integration/test_[feature].py
```

**Example**:
```markdown
Prompt: "Create tests/unit/test_llm.py with tests for:
1. LLM initialization:
   - Test OpenAI provider setup
   - Test Ollama provider setup
   - Test missing API key handling
2. Trigger detection:
   - Test bot mention detection
   - Test case-insensitive matching
   - Test trigger word variations
3. Chat handling:
   - Test conversation context management
   - Test rate limiting
   - Test error handling for API failures

Use pytest-asyncio for async tests and mock external API calls."
```

**Output**: Complete test file with 85%+ coverage

---

### Pattern 5: Documentation

**Use**: Updating documentation to match implementation

**Template**:
```markdown
**Context**: Feature [X] has been implemented

**Task**: Update all documentation

**Files to Update**:
1. README.md - Add feature to list, quick start example
2. docs/ARCHITECTURE.md - Add new components to diagrams
3. Create docs/guides/[FEATURE]_GUIDE.md - Detailed usage guide
4. Update CHANGELOG.md - Add entry for this version

**Style**: Follow existing documentation patterns and tone
```

**Example**:
```markdown
Prompt: "Update documentation for LLM integration:

1. README.md:
   - Add 'AI Chat Integration' to features list
   - Add LLM configuration example to quick start
   - Link to docs/guides/LLM_CONFIGURATION.md

2. docs/ARCHITECTURE.md:
   - Add LLM component to architecture diagram
   - Describe LLM provider initialization
   - Document conversation context management
   - Explain trigger detection flow

3. Create docs/guides/LLM_CONFIGURATION.md:
   - Step-by-step setup for OpenAI
   - Step-by-step setup for local Ollama
   - Step-by-step setup for remote Ollama
   - Configuration examples for each scenario
   - Troubleshooting section

4. Update CHANGELOG.md:
   - Add v0.4.0 entry with LLM features"
```

**Output**: Updated docs across project

---

### Pattern 6: Code Review

**Use**: Comprehensive review before merge

**Template**:
```markdown
**Context**: Review changes in branch [branch-name]

**Task**: Perform comprehensive code review

**Check for**:
1. **Correctness**: Does code match specification?
2. **Quality**: Is code readable, maintainable, idiomatic?
3. **Testing**: Are there adequate tests? Edge cases covered?
4. **Security**: Any vulnerabilities or unsafe patterns?
5. **Performance**: Any obvious bottlenecks?
6. **Documentation**: Code comments, docstrings, user docs?

**Output**: Detailed review comments with suggestions
```

**Example**:
```markdown
Prompt: "Review all changes in the 2-start-me-up nano-sprint for:

1. Code Quality:
   - Follows Python conventions (PEP 8)
   - Proper error handling
   - Comprehensive logging
   - Type hints on all methods

2. Test Coverage:
   - All new methods have tests
   - Edge cases covered (missing API keys, network errors, rate limits)
   - External dependencies mocked

3. Documentation:
   - All methods have Google-style docstrings
   - User guides updated (README, LLM_CONFIGURATION.md)
   - Architecture docs current

4. Security:
   - API keys handled securely (environment variables only)
   - Input validation present
   - Rate limiting implemented
   - No sensitive data in logs

Provide specific feedback with file names, line numbers, and suggestions."
```

**Output**: Detailed review report

---

## Advanced Workflows

### Multi-File Context Gathering

**Use**: Understanding complex feature interactions

**Pattern**:
```markdown
Prompt: "To understand [feature], read these files in parallel:
1. lib/bot.py - Main bot implementation
2. common/config.py - Configuration loading
3. lib/channel.py - Channel management
4. tests/unit/test_bot.py - Test patterns

Then explain how [feature] works across these components."
```

**Best Practice**: Request parallel reads for efficiency.

---

### Incremental Refactoring

**Use**: Large-scale code improvements

**Pattern**:
```markdown
Prompt: "Refactor [module] in phases:

Phase 1: Extract common patterns
- Identify repeated code
- Create helper methods
- Update all usages

Phase 2: Improve error handling
- Add try/except blocks
- Log errors comprehensively
- Raise appropriate exceptions

Phase 3: Add type hints and docstrings
- Type hint all methods
- Add Google-style docstrings
- Update tests for new signatures

Implement one phase at a time, testing after each phase."
```

**Best Practice**: Break large refactorings into testable increments.

---

### Dependency Update Workflow

**Use**: Updating project dependencies safely

**Pattern**:
```markdown
Prompt: "Update dependencies in requirements.txt:

1. Check current versions:
   - Read requirements.txt
   - Identify outdated packages

2. Research updates:
   - Check for breaking changes
   - Review release notes

3. Update incrementally:
   - Update one package at a time
   - Run tests after each update
   - Fix any breakages before next update

4. Document changes:
   - Update CHANGELOG.md
   - Note any API changes
   - Update code if needed

Start with security updates, then feature updates."
```

---

### Feature Flag Implementation

**Use**: Gradual feature rollout

**Pattern**:
```markdown
Prompt: "Add feature flag for [feature]:

1. Configuration:
   - Add 'enable_[feature]' to config schema
   - Default to false for safety
   - Document in config.json.dist

2. Implementation:
   - Check flag before feature execution
   - Log when feature is used
   - Graceful fallback when disabled

3. Testing:
   - Test with flag enabled
   - Test with flag disabled
   - Test flag toggle behavior

4. Documentation:
   - Document flag in README
   - Add to admin guide
   - Note in CHANGELOG"
```

---

### Performance Profiling

**Use**: Identifying and fixing bottlenecks

**Pattern**:
```markdown
Prompt: "Profile performance of [feature]:

1. Add profiling:
   - Import cProfile
   - Profile critical paths
   - Generate timing reports

2. Analyze results:
   - Identify slow operations
   - Find unnecessary loops
   - Detect blocking calls in async code

3. Optimize:
   - Cache repeated operations
   - Use async properly
   - Batch operations where possible

4. Verify:
   - Re-profile after changes
   - Ensure functionality unchanged
   - Update performance tests

Document optimizations in comments."
```

---

## Troubleshooting

### Problem: Agent Not Following Spec

**Symptoms**: Generated code doesn't match specification

**Solution**:
```markdown
Prompt: "The generated code doesn't match section 4.1 of SPEC-Sortie-1-Foundation.md. 
Please:
1. Re-read the spec file carefully
2. Compare your implementation to the spec requirements
3. Regenerate the code matching exactly:
   - Method signatures as specified
   - Error handling as described
   - Return types as documented
   
Show me what you changed and why."
```

---

### Problem: Inconsistent Code Style

**Symptoms**: Agent uses different patterns than existing code

**Solution**:
```markdown
Prompt: "Review the existing code in lib/bot.py for style patterns. 
Then regenerate the new methods to match:

1. Docstring format:
   - Google-style with Args, Returns, Raises, Side Effects
   - Include type information

2. Error handling:
   - Log at appropriate level
   - Raise specific exceptions
   - Include context in error messages

3. Logging conventions:
   - Use self.logger
   - Structured messages with context
   - Appropriate log levels (debug, info, warning, error)

4. Async patterns:
   - Use asyncio.create_task for background work
   - Proper await on all coroutines
   - Cancel tasks on shutdown

Show me the updated methods with these patterns applied."
```

---

### Problem: Missing Edge Cases

**Symptoms**: Agent doesn't consider error scenarios

**Solution**:
```markdown
Prompt: "Review the [feature] implementation and identify edge cases:

1. Input validation:
   - What if input is None?
   - What if input is wrong type?
   - What if input is empty?

2. External dependencies:
   - What if API key is invalid?
   - What if server is unreachable?
   - What if response is malformed?

3. State management:
   - What if operation is called twice?
   - What if state is inconsistent?
   - What if cleanup fails?

4. Rate limiting:
   - What if user exceeds limit?
   - What if rate limit resets during operation?
   - What if rate limit data is corrupted?

Add error handling for each scenario with tests."
```

---

### Problem: Incomplete Documentation

**Symptoms**: Generated docs lack examples or details

**Solution**:
```markdown
Prompt: "Expand the [FEATURE]_GUIDE.md documentation:

1. Setup section:
   - Step-by-step instructions for each scenario
   - Required dependencies
   - Configuration file examples
   - Environment variable examples

2. Usage section:
   - Basic usage example
   - Advanced usage examples
   - Common patterns
   - Best practices

3. Troubleshooting section:
   - Common issues with solutions
   - Error message explanations
   - How to verify configuration
   - Where to find logs

4. Reference section:
   - Configuration options table
   - API reference (if applicable)
   - Related documentation links

Use code blocks for all examples."
```

---

### Problem: Test Failures After Refactoring

**Symptoms**: Tests break after code changes

**Solution**:
```markdown
Prompt: "Fix failing tests after refactoring:

1. Analyze failures:
   - Read test output
   - Identify which tests failed
   - Understand why they failed

2. Categorize issues:
   - Outdated test expectations
   - Broken test fixtures
   - Changed method signatures
   - New error handling

3. Fix systematically:
   - Update test expectations if behavior correct
   - Fix fixtures for new patterns
   - Update mocks for new signatures
   - Add tests for new error cases

4. Verify:
   - Run all tests
   - Check coverage didn't decrease
   - Ensure no new failures

Show me what you fixed and why."
```

---

## Best Practices

### Providing Context

**✅ Good**:
```markdown
Prompt: "Implement LLM chat handling based on SPEC-Sortie-1-Foundation.md. 
Read lib/bot.py lines 100-200 first to understand the existing message 
handling pattern. Follow the same error handling approach used in 
_handle_pm() method."
```

**❌ Bad**:
```markdown
Prompt: "Add LLM chat"  # Too vague, no context
```

---

### Iterative Refinement

**✅ Good**:
```markdown
1. Prompt: "Create initial implementation of LLM integration"
2. Review output
3. Prompt: "Add error handling for API failures"
4. Review output
5. Prompt: "Add rate limiting with 5 messages per minute"
6. Review output
7. Prompt: "Add tests for all edge cases"
```

**❌ Bad**:
```markdown
Prompt: "Create perfect LLM integration with error handling, 
rate limiting, tests, docs, and deploy it"  # Too much at once
```

---

### Verification Steps

**✅ Good**:
```markdown
Prompt: "After implementing [feature]:
1. Run tests with pytest --cov
2. Check for lint errors with ruff
3. Verify type hints with mypy
4. Review changes with git diff
5. Test manually in development environment
6. Check documentation is updated

Report results of each step."
```

**❌ Bad**:
```markdown
Prompt: "Implement [feature]"  # No verification
```

---

### Explicit Requirements

**✅ Good**:
```markdown
Prompt: "Add rate limiting to LLM chat:
- Maximum 5 messages per user per minute
- Use sliding window algorithm
- Store state in memory (self._rate_limits dict)
- Return clear error message when limit exceeded
- Log rate limit violations at WARNING level
- Include user_id and timestamp in logs"
```

**❌ Bad**:
```markdown
Prompt: "Add rate limiting"  # Vague requirements
```

---

### Documentation Standards

**✅ Good**:
```markdown
Prompt: "Add docstring to _handle_llm_chat() following Google-style format:
- Summary line
- Detailed description (2-3 sentences)
- Args section with types
- Returns section (even if None)
- Raises section with exception types
- Side Effects section listing all side effects
- Example usage if non-obvious"
```

**❌ Bad**:
```markdown
Prompt: "Add docstring"  # No format specified
```

---

## Multi-Agent Collaboration

For complex features, use multiple specialized agent sessions:

### 1. Architecture Agent

**Focus**: System design and component interactions

```markdown
Prompt: "Act as an architecture specialist. Design the plugin system for Rosey:
1. Analyze existing bot architecture
2. Propose plugin interface (abstract base class)
3. Design plugin lifecycle (load, init, reload, unload)
4. Design event bus for plugin communication
5. Design service registry for shared services
6. Create architecture diagrams (text-based)
7. Identify potential issues and solutions

Deliverable: Architecture document with all designs."
```

---

### 2. Implementation Agent

**Focus**: Code generation and refactoring

```markdown
Prompt: "Act as an implementation specialist. Implement the plugin system 
based on the architecture document:
1. Create PluginBase abstract class
2. Implement PluginManager with lifecycle methods
3. Create EventBus for inter-plugin communication
4. Implement ServiceRegistry for shared services
5. Add hot reload functionality
6. Follow existing code patterns in lib/bot.py
7. Include comprehensive error handling

Deliverable: Working implementation with type hints and docstrings."
```

---

### 3. Testing Agent

**Focus**: Test case generation and coverage analysis

```markdown
Prompt: "Act as a testing specialist. Create comprehensive tests for plugin system:
1. Unit tests for PluginBase
2. Unit tests for PluginManager lifecycle
3. Unit tests for EventBus pub/sub
4. Unit tests for ServiceRegistry
5. Integration tests for hot reload
6. Edge case tests (missing plugins, circular deps, etc.)
7. Performance tests for event bus under load

Deliverable: Complete test suite with 85%+ coverage."
```

---

### 4. Documentation Agent

**Focus**: User guides and API references

```markdown
Prompt: "Act as a documentation specialist. Create plugin system documentation:
1. User guide: How to create a plugin
2. User guide: How to use event bus
3. User guide: How to access shared services
4. API reference: PluginBase methods
5. API reference: PluginManager API
6. Examples: Simple plugin, complex plugin, plugin with dependencies
7. Troubleshooting: Common issues and solutions

Deliverable: Complete documentation in docs/guides/PLUGIN_SYSTEM.md."
```

---

### 5. Review Agent

**Focus**: Code review and security analysis

```markdown
Prompt: "Act as a code reviewer and security specialist. Review plugin system:
1. Code quality: Readability, maintainability, idioms
2. Security: Plugin isolation, resource limits, safe loading
3. Performance: Bottlenecks, unnecessary work, memory leaks
4. Error handling: Coverage, clarity, recovery
5. Testing: Coverage, edge cases, mocking
6. Documentation: Completeness, accuracy, examples

Deliverable: Review report with specific issues and recommendations."
```

---

## Summary

Effective prompting requires:
1. **Clear Context**: Reference files, specs, and requirements
2. **Specific Tasks**: Break work into concrete, testable steps
3. **Verification**: Always check results and iterate
4. **Standards**: Enforce code quality, testing, and documentation
5. **Iteration**: Refine through conversation, don't expect perfection first try

Use the patterns in this guide as starting points and adapt them to your specific needs.

---

**Document Version**: 1.0  
**Last Updated**: November 21, 2025  
**See Also**: [AGENTS.md](../../AGENTS.md), [AGENT_WORKFLOW_DETAILED.md](AGENT_WORKFLOW_DETAILED.md), [AGENT_TOOLS_REFERENCE.md](AGENT_TOOLS_REFERENCE.md)
