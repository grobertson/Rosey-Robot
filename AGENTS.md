# GitHub Copilot Agent Workflow Guide

**Project:** Rosey-Robot  
**Workflow:** Nano-Sprint Development with GitHub Copilot  
**Last Updated:** November 18, 2025  

---

## Overview

This document describes the **agent-assisted development workflow** used in the Rosey-Robot project. We leverage GitHub Copilot using the Claude Sonnet 4.5 model as a collaborative AI agent to design, implement, and document features through structured nano-sprints with detailed specifications.

### Workflow Philosophy

- **Planning First**: Write comprehensive PRDs and specs before coding
- **Nano-Sprints**: Small, manageable development cycles designed to complete in a single day or less
- **Sorties**: Logical bundles of changes within a nano-sprint (1 or more commits per sortie)
- **Agent Collaboration**: Use GitHub Copilot for implementation, testing, and documentation
- **Documentation-Driven**: Maintain living documentation that evolves with the code
- **Iterative Refinement**: Each commit builds incrementally on the previous one
- **Completion**: When each sortie is complete, the nano-sprint is complete

---

## Development Workflow

### Phase 1: Product Requirements (PRD)

**Purpose**: Define the feature from a product perspective

**Format**: `docs/{sprint-number}-{sprint-name}/PRD-{feature-name}.md`

**Contents**:

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

**Example**: [`docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md`](docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md)

**Agent Usage**:

```markdown
Prompt: "Create a PRD for adding LLM chat integration to Rosey. 
The bot should respond to mentions using OpenAI or Ollama."

Agent generates: Complete PRD with user stories, architecture, 
security considerations, cost analysis, etc.
```

---

### Phase 2: Technical Specifications (SPEC)

**Purpose**: Break down PRD into a logical sortie of atomic, implementable commits

**Format**: `docs/{sprint-number}-{sprint-name}/SPEC-Sortie-{N}-{sortie-name}.md`

**Contents per Sortie**:

1. **Overview**: What this commit achieves
2. **Scope and Non-Goals**: What's included/excluded
3. **Requirements**: Functional and non-functional
4. **Design**: Architecture diagrams, data structures, API interactions
5. **Implementation**: Modified files, new methods, code structure
6. **Testing**: Unit tests, integration tests, manual checklist
7. **Acceptance Criteria**: Concrete checkboxes for completion
8. **Rollout**: Deployment steps and monitoring
9. **Documentation**: Code comments, API docs, user guides

**Example**: [`docs/sprints/completed/2-start-me-up/SPEC-Sortie-1-LLM-Foundation.md`](docs/sprints/completed/2-start-me-up/SPEC-Sortie-1-LLM-Foundation.md)

**Agent Usage**:

```markdown
Prompt: "Based on the LLM PRD, create specs for a nano-sprint sortie. 
Break it into logical changes: 1) Foundation, 2) Remote Ollama, 3) Trigger refinement, 
4) Username correction, 5) Deployment automation, 6) Documentation PR."

Agent generates: Detailed spec files for the sortie with implementation plans
```

---

### Phase 3: Implementation (Code)

**Purpose**: Execute the spec with agent assistance

**Approach**: Iterative development with Copilot

**Steps per Sortie**:

1. **Read the Spec**

   ```markdown
   Prompt: "Read SPEC-Sortie-1-LLM-Foundation.md and implement it"
   ```

2. **Generate Code**
   - Agent creates/modifies files based on spec
   - Follows existing code patterns and conventions
   - Includes docstrings and inline comments

3. **Write Tests**

   ```markdown
   Prompt: "Create unit tests for the LLM trigger detection system"
   ```

4. **Verify Acceptance Criteria**
   - Agent checks off spec requirements
   - Runs tests and validates functionality

5. **Commit Changes**

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

**Agent Capabilities**:

- Read multiple files in parallel for context
- Generate code following project conventions
- Create tests based on specification
- Update documentation automatically
- Suggest improvements and edge cases

---

### Phase 4: Documentation (Docs)

**Purpose**: Keep documentation current with implementation

**Types**:

#### 4.1 Code Documentation

- Docstrings for all public methods
- Inline comments for complex logic
- Type hints for parameters and returns

**Example**:

```python
async def _handle_llm_chat(self, username: str, message: str):
    """Generate and send LLM response.
    
    Args:
        username: Sender's current username
        message: Trigger message text
    
    Side Effects:
        - Sends response to channel chat
        - Updates rate limit state
        - Appends to conversation context
    """
```

#### 4.2 User Documentation

- Update README.md with new features
- Create feature-specific guides (e.g., `LLM_CONFIGURATION.md`)
- Update quickstart guides

**Agent Usage**:

```markdown
Prompt: "Update README.md to include LLM integration in the 
features section, quick start, and configuration examples"
```

#### 4.3 Architecture Documentation

- Update `ARCHITECTURE.md` with new components
- Add diagrams for data flow
- Document extension points

#### 4.4 Deployment Documentation

- Update systemd service files
- Document environment variables
- Create deployment checklists

---

### Phase 5: Review and Merge (PR)

**Purpose**: Final review and integration

**Steps**:

1. **Self-Review**

   ```markdown
   Prompt: "Review all changes in this nano-sprint for:
   - Code quality and consistency
   - Test coverage
   - Documentation completeness
   - Security considerations"
   ```

2. **Create Pull Request**
   - Title: `[Sprint Name] Feature Name`
   - Description: Link to PRD, list of commits, testing notes
   - Labels: `enhancement`, `documentation`, etc.

3. **Automated Checks**
   - Run full test suite: `pytest --cov`
   - Lint code: `flake8`, `mypy`
   - Check documentation: Verify all TODOs resolved

4. **Agent-Assisted Review**

   ```markdown
   Prompt: "Act as a code reviewer. Review this PR for:
   - Architectural consistency
   - Potential bugs or edge cases
   - Performance implications
   - Security vulnerabilities"
   ```

5. **Merge to Main**
   - Squash commits if needed
   - Update CHANGELOG.md
   - Tag release if applicable

---

## Directory Structure

### Documentation Organization

```text
docs/
├── sprints/
│   ├── completed/              # Completed sprints
│   │   ├── 2-start-me-up/     # LLM Integration
│   │   ├── 5-ship-it/         # Production Deployment
│   │   └── 6a-quicksilver/    # NATS Event Bus
│   └── active/                 # Active/planned sprints
│       ├── 3-rest-assured/    # REST API Migration
│       ├── 4-test-assured/    # Testing Infrastructure
│       └── 6-make-it-real/    # Advanced Deployment
├── guides/                     # Feature guides
│   ├── LLM_CONFIGURATION.md
│   ├── PM_GUIDE.md
│   ├── API_TOKENS.md
│   └── NATS_CONFIGURATION.md
├── ARCHITECTURE.md
├── TESTING.md
└── SETUP.md

Top Level:
├── AGENTS.md                   # This file - workflow guide
├── README.md                   # Main documentation
├── QUICKSTART.md               # Quick start guide
└── CHANGELOG.md                # Version history
```

Each sprint directory contains:

```text
docs/sprints/{completed|active}/{N}-{sprint-name}/
├── PRD-{Feature}.md           # Product requirements
├── SPEC-Sortie-{N}-{Name}.md  # Technical specifications
└── ...                        # Additional documentation
```

### Sprint Naming Convention

Format: `{number}-{descriptive-name}` or `{number}-{movie-title}` (6a+)

Examples:

- `2-start-me-up` - LLM Integration sprint
- `3-rest-assured` - REST API Migration sprint
- `4-test-assured` - Testing Infrastructure sprint
- `5-ship-it` - Production Deployment sprint
- `6-make-it-real` - Advanced Deployment sprint
- `6a-quicksilver` - NATS Event Bus architecture

See [docs/SPRINT_NAMING.md](docs/SPRINT_NAMING.md) for the complete naming convention guide.

---

## Agent Prompting Patterns

### Pattern 1: Feature Planning

```markdown
**Context**: We want to add [feature] to Rosey

**Task**: Create a comprehensive PRD that includes:
1. Executive summary and problem statement
2. User stories with acceptance criteria
3. Technical architecture with diagrams
4. Security and privacy considerations
5. Implementation timeline and rollout plan
6. Future enhancement roadmap

**Format**: Use the existing PRD template from docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md
```

### Pattern 2: Specification Breakdown

```markdown
**Context**: Given the PRD at docs/X-sprint/PRD-Feature.md

**Task**: Break this into a logical sortie of atomic changes

**Requirements**:
- Each sortie can contain one or more commits
- Each commit must be independently testable
- Follow the SPEC template structure
- Include detailed implementation steps
- Define clear acceptance criteria

**Output**: Create SPEC-Sortie-N-Name.md files for the sortie
```

### Pattern 3: Implementation

```markdown
**Context**: Implement SPEC-Sortie-1-Foundation.md

**Current State**: Read lib/bot.py, common/config.py, bot/rosey/config.json.dist

**Task**: 
1. Add the methods defined in section 4.1
2. Follow existing code style and conventions
3. Include docstrings and type hints
4. Update configuration files as specified

**Verification**: Check all items in section 7 (Acceptance Criteria)
```

### Pattern 4: Testing

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

### Pattern 5: Documentation

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

### Pattern 6: Code Review

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

---

## Best Practices

### Working with the Agent

#### ✅ Do's

- **Provide Context**: Reference related files, PRDs, specs
- **Be Specific**: Clear requirements lead to better results
- **Iterate**: Refine outputs through conversation
- **Verify**: Always review agent-generated code
- **Document Decisions**: Capture rationale in comments and docs

#### ❌ Don'ts

- **Don't Skip Planning**: Always write PRD/specs first
- **Don't Assume**: Verify agent's understanding of requirements
- **Don't Merge Blindly**: Review and test all generated code
- **Don't Ignore Warnings**: Address security and performance concerns
- **Don't Skip Tests**: Always generate and run tests

### Code Quality Standards

- **Type Hints**: Use Python type hints for all functions
- **Docstrings**: Google-style docstrings for public APIs
- **Comments**: Explain "why" not "what"
- **Testing**: Aim for 85%+ coverage (66% minimum)
- **Naming**: Descriptive names, follow PEP 8
- **Async**: Use `async/await` consistently for I/O

### Git Commit Guidelines

#### Commit Message Format

```text
Short Title (50 chars max)

- Detailed change 1
- Detailed change 2
- Detailed change 3

Implements: SPEC-Commit-N-Name.md
Related: PRD-Feature-Name.md
Fixes: #123 (if applicable)
```

#### Commit Granularity

- **One Logical Change**: Each commit should be atomic
- **Compilable**: Each commit should leave the code in a working state
- **Testable**: Each commit should pass all tests
- **Documentable**: Each commit should update relevant docs

All commits will be flattened when merged with the pull request.

---

## Example: LLM Integration Nano-Sprint

### Timeline

**Sprint**: `2-start-me-up`  
**Feature**: LLM Chat Integration  
**Duration**: 3 days  
**Commits**: 6  

### Step-by-Step

#### Day 1: Planning (2 hours)

1. **Write PRD**

   ```markdown
   Prompt: "Create a PRD for adding LLM integration to Rosey. 
   Support OpenAI and Ollama providers, trigger-based responses, 
   conversation context, and rate limiting."
   ```

   - Output: `docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md`

2. **Create Commit Specs**

   ```markdown
   Prompt: "Break the LLM PRD into 6 commit specs covering:
   1. Basic OpenAI/Ollama support
   2. Remote Ollama configuration
   3. Trigger system improvements
   4. Username correction
   5. Deployment automation
   6. Documentation and PR"

   ```

   - Output: `SPEC-Sortie-1` through `SPEC-Sortie-6`

#### Day 2: Implementation (6 hours)

1. **Commit 1: Foundation**

   ```markdown
   Prompt: "Implement SPEC-Sortie-1-LLM-Foundation.md"
   ```

   - Modified: `lib/bot.py`
   - Added: LLM initialization, trigger detection, context management
   - Commit: "LLM Foundation"

2. **Commit 2: Remote Ollama**

   ```markdown
   Prompt: "Implement SPEC-Commit-2-Ollama-Remote-Support.md"
   ```

   - Modified: `lib/bot.py` (_setup_llm method)
   - Added: `ollama_host` configuration support
   - Commit: "Add remote Ollama server support"

3. **Commit 3: Trigger Refinement**

   ```markdown
   Prompt: "Implement SPEC-Commit-3-Trigger-System-Refinement.md"
   ```

   - Modified: `_check_llm_trigger()` for case-insensitive matching
   - Commit: "Improve trigger detection system"

4. **Commit 4: Username Correction**

   ```markdown
   Prompt: "Implement SPEC-Commit-4-Username-Correction.md"
   ```

   - Added: `_on_set_user_profile()` event handler
   - Commit: "Add username correction system"

#### Day 3: Deployment & Documentation (3 hours)

1. **Commit 5: Deployment**

   ```markdown
   Prompt: "Implement SPEC-Commit-5-Deployment-Automation.md"
   ```

   - Modified: `systemd/cytube-bot.service`
   - Updated: `systemd/README.md`
   - Commit: "Add systemd LLM configuration"

2. **Commit 6: Documentation**

   ```markdown
   Prompt: "Implement SPEC-Commit-6-Documentation-PR.md"
   ```

   - Updated: `README.md`, `docs/ARCHITECTURE.md`
   - Created: `docs/guides/LLM_CONFIGURATION.md`
   - Commit: "Complete LLM documentation"

3. **Create PR**

   - Title: "[2-start-me-up] LLM Chat Integration"
   - Description: Links to PRD, lists 6 commits, testing notes
   - Merge: After CI passes and review

### Outcome

- **Code**: Fully functional LLM integration
- **Tests**: 95% coverage for new code
- **Docs**: Comprehensive guides and examples
- **Time**: 11 hours total (planning → merge)

---

## Troubleshooting

### Agent Not Following Spec

**Problem**: Agent generates code that doesn't match specification

**Solution**:

```markdown
Prompt: "The generated code doesn't match section 4.1 of the spec. 
Please re-read SPEC-Sortie-1-Foundation.md and implement exactly 
as specified, particularly the method signatures and error handling."
```

### Inconsistent Code Style

**Problem**: Agent uses different patterns than existing code

**Solution**:

```markdown
Prompt: "Review the existing code in lib/bot.py for style patterns. 
Then regenerate the new methods to match:
- Docstring format
- Error handling approach
- Logging conventions
- Async patterns"
```

### Missing Edge Cases

**Problem**: Agent doesn't consider error scenarios

**Solution**:

```markdown
Prompt: "Review the implementation and identify potential edge cases:
- What if the API key is invalid?
- What if the LLM server is unreachable?
- What if the response is empty or malformed?
- What if the user is rate-limited?

Add error handling for each scenario."
```

### Incomplete Documentation

**Problem**: Generated docs lack examples or details

**Solution**:

```markdown
Prompt: "Expand the LLM_CONFIGURATION.md guide with:
1. Step-by-step setup for OpenAI
2. Step-by-step setup for local Ollama
3. Step-by-step setup for remote Ollama
4. Configuration examples for each scenario
5. Troubleshooting section with common issues"
```

---

## Advanced Workflows

### Multi-Agent Collaboration

For complex features, use multiple agent sessions:

1. **Architecture Agent**: System design and component interactions
2. **Implementation Agent**: Code generation and refactoring
3. **Testing Agent**: Test case generation and coverage analysis
4. **Documentation Agent**: User guides and API references
5. **Review Agent**: Code review and security analysis

### Continuous Refinement

Use agents for ongoing maintenance:

```markdown
# Weekly Maintenance Prompt
"Review the codebase for:
1. Outdated dependencies (check requirements.txt)
2. Deprecated patterns (check Python version compatibility)
3. Missing tests (identify untested code paths)
4. Documentation gaps (check for undocumented features)
5. Performance opportunities (profile slow operations)

Generate a maintenance backlog with prioritized tasks."
```

### Knowledge Transfer

Use agents to onboard new contributors:

```markdown
Prompt: "Create an ONBOARDING.md guide for new contributors that covers:
1. Project architecture overview
2. Development workflow
3. How to create a new feature (with example)
4. Testing strategy
5. Documentation standards
6. Common pitfalls and gotchas"
```

---

## Metrics and Success

### Track Agent Effectiveness

- **Time Savings**: Compare manual vs. agent-assisted development
- **Code Quality**: Defect rates, test coverage, review findings
- **Documentation**: Completeness, clarity, accuracy
- **Velocity**: Features shipped per sprint

### Continuous Improvement

- **Retrospectives**: Review what worked and what didn't
- **Prompt Library**: Maintain effective prompts for reuse
- **Template Updates**: Evolve PRD/spec templates based on learnings
- **Agent Feedback**: Provide feedback to improve future interactions

---

## Resources

### Project Documentation

- [README.md](README.md) - Main project documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [TESTING.md](docs/TESTING.md) - Testing guide
- [PM_GUIDE.md](docs/guides/PM_GUIDE.md) - Bot control guide
- [QUICKSTART.md](QUICKSTART.md) - Quick start guide

### Example Sprints

- [2-start-me-up](docs/sprints/completed/2-start-me-up/) - LLM Integration sprint (✅ Complete)
- [3-rest-assured](docs/sprints/completed/3-rest-assured/) - REST API Migration sprint (✅ Complete)
- [4-test-assured](docs/sprints/completed/4-test-assured/) - Testing Infrastructure sprint (✅ Complete)
- [5-ship-it](docs/sprints/deferred/5-ship-it/) - Production Deployment sprint (⏸️ Deferred - using manual deployment)
- [6-make-it-real](docs/sprints/deferred/6-make-it-real/) - Advanced Deployment sprint (⏸️ Deferred - cost constraints)
- [6a-quicksilver](docs/sprints/completed/6a-quicksilver/) - NATS Event Bus sprint (✅ Complete)

### External Resources

- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [Agent-Driven Development](https://github.blog/2023-11-08-universe-2023-copilot-transforms-github-into-the-ai-powered-developer-platform/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

---

## Contributing

When contributing to Rosey-Robot, follow this workflow:

1. **Propose Feature**: Open an issue describing the feature
2. **Write PRD**: Create PRD in a new sprint folder
3. **Create Specs**: Break down into sortie specs
4. **Implement**: Use agent assistance for each commit
5. **Test**: Write comprehensive tests
6. **Document**: Update all relevant documentation
7. **Submit PR**: Link to PRD, list commits, provide testing notes
8. **Iterate**: Address review feedback with agent help

---

## Conclusion

This agent-assisted workflow enables rapid, high-quality feature development while maintaining comprehensive documentation and test coverage. By structuring work into PRDs, specs, and atomic commits, we create a clear development path that both humans and AI agents can follow effectively.

The key to success is **planning first, implementing incrementally, and documenting continuously**. GitHub Copilot serves as a collaborative partner throughout this process, accelerating development while maintaining quality standards.

**Remember**: Each nano-sprint consists of one or more sorties (logical bundles of changes), and each sortie may contain one or more commits. When each sortie is complete, the nano-sprint is complete.

---

**Document Version**: 1.0  
**Last Updated**: November 18, 2025  
**Maintained By**: Rosey-Robot Team  
**Workflow Status**: ✅ Active and Proven
