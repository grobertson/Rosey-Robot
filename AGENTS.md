# GitHub Copilot Agent Workflow Guide

**Project:** Rosey-Robot  
**Workflow:** Nano-Sprint Development with GitHub Copilot  
**Last Updated:** November 21, 2025  

---

## Overview

This document describes the **agent-assisted development workflow** used in the Rosey-Robot project. We leverage GitHub Copilot using the Claude Sonnet 4.5 model as a collaborative AI agent to design, implement, and document features through structured nano-sprints with detailed specifications.

### Workflow Philosophy

- **Planning First**: Write comprehensive PRDs and specs before coding
- **Nano-Sprints**: Small, manageable development cycles (typically 1-3 days)
- **Sorties**: Logical bundles of changes within a nano-sprint (1+ commits per sortie)
- **Agent Collaboration**: Use GitHub Copilot for implementation, testing, and documentation
- **Documentation-Driven**: Maintain living documentation that evolves with the code
- **Iterative Refinement**: Each commit builds incrementally on the previous one

---

## Quick Reference: Development Phases

### Phase 1: Product Requirements (PRD)
Define the feature from a product perspective. Create comprehensive PRD documents covering problem statement, user stories, architecture, and rollout plans.

**Format**: `docs/sprints/{N}-{sprint-name}/PRD-{feature-name}.md`  
**Example**: [PRD-LLM-Integration.md](docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md)

### Phase 2: Technical Specifications (SPEC)
Break down PRD into logical sorties (work units that may span multiple commits). Each spec defines scope, requirements, design, implementation steps, tests, and acceptance criteria.

**Format**: `docs/sprints/{N}-{sprint-name}/SPEC-Sortie-{N}-{sortie-name}.md`  
**Example**: [SPEC-Sortie-1-LLM-Foundation.md](docs/sprints/completed/2-start-me-up/SPEC-Sortie-1-LLM-Foundation.md)

### Phase 3: Implementation (Code)
Execute specs with agent assistance. Agent reads specs, generates code following project conventions, creates tests, and verifies acceptance criteria.

**Key Actions**: Read specs, generate code, write tests, commit changes  
**Agent Capabilities**: Parallel file reading, code generation, test creation, documentation updates

### Phase 4: Documentation (Docs)
Keep documentation current with implementation. Update code docs (docstrings, type hints), user docs (README, guides), architecture docs, and deployment docs.

**Types**: Code docs, user guides, architecture diagrams, deployment checklists

### Phase 5: Review and Merge (PR)
Final review and integration. Perform self-review, create PR with links to PRD/specs, run automated checks (tests, linting), and merge to main.

**Steps**: Self-review → Create PR → Automated checks → Agent-assisted review → Merge

---

## Directory Structure

### Documentation Organization

```text
docs/
├── guides/                     # Feature and workflow guides
│   ├── AGENT_WORKFLOW_DETAILED.md    # Complete workflow reference
│   ├── AGENT_TOOLS_REFERENCE.md      # All tools and MCPs
│   ├── AGENT_PROMPTING_GUIDE.md      # Prompt patterns and examples
│   ├── LLM_CONFIGURATION.md          # LLM setup guide
│   ├── PM_GUIDE.md                   # Bot control guide
│   └── NATS_CONFIGURATION.md         # NATS event bus setup
├── sprints/
│   ├── completed/              # Finished sprints
│   │   ├── 2-start-me-up/     # LLM Integration
│   │   ├── 3-rest-assured/    # REST API Migration
│   │   ├── 4-test-assured/    # Testing Infrastructure
│   │   └── 6a-quicksilver/    # NATS Event Bus
│   ├── deferred/               # Postponed sprints
│   │   ├── 5-ship-it/         # Production Deployment
│   │   └── 6-make-it-real/    # Advanced Deployment
│   └── active/                 # Current/planned sprints
├── ARCHITECTURE.md             # System architecture
├── TESTING.md                  # Testing strategy
└── SETUP.md                    # Development setup

Top Level:
├── AGENTS.md                   # This file - workflow overview
├── README.md                   # Main project documentation
├── QUICKSTART.md               # Quick start guide
└── CHANGELOG.md                # Version history
```

### Sprint Naming Convention

Format: `{number}-{descriptive-name}` or `{number}-{movie-title}` (Sprint 6a+)

Examples:
- `2-start-me-up` - LLM Integration
- `3-rest-assured` - REST API Migration
- `6a-quicksilver` - NATS Event Bus

See [docs/SPRINT_NAMING.md](docs/SPRINT_NAMING.md) for complete naming convention.

---

## Quick Start: Creating a New Feature

### 1. Plan the Feature (PRD)

```markdown
Prompt: "Create a PRD for adding [feature] to Rosey. 
Include user stories, architecture, security considerations, and rollout plan."
```

Agent generates comprehensive PRD document.

### 2. Break Down into Specs

```markdown
Prompt: "Based on the [feature] PRD, create specs for a nano-sprint sortie.
Break into logical sorties: 1) Foundation, 2) Core feature, 3) Testing, 4) Documentation."
```

Agent generates detailed SPEC files for each sortie.

### 3. Implement with Agent

```markdown
Prompt: "Read SPEC-Sortie-1-Foundation.md and implement it.
Follow existing code patterns, include docstrings and type hints."
```

Agent generates code, tests, and documentation.

### 4. Commit and Review

```bash
git add .
git commit -m "Feature Foundation

- Add core methods
- Update configuration
- Add tests

Implements: SPEC-Sortie-1-Foundation.md
Related: PRD-Feature.md"
```

### 5. Create Pull Request

Create PR with:
- Title: `[Sprint Name] Feature Name`
- Description: Links to PRD, list of commits, testing notes
- Labels: `enhancement`, `documentation`, etc.

---

## Best Practices

### Working with the Agent

**✅ Do:**
- Provide context (reference files, PRDs, specs)
- Be specific with requirements
- Iterate through conversation
- Verify all generated code
- Document decisions in comments

**❌ Don't:**
- Skip planning (always write PRD/specs first)
- Assume agent understanding (verify requirements)
- Merge blindly (review and test all code)
- Ignore warnings (address security/performance)
- Skip tests (always generate and run tests)

### Code Quality Standards

- **Type Hints**: Use Python type hints for all functions
- **Docstrings**: Google-style docstrings for public APIs
- **Comments**: Explain "why" not "what"
- **Testing**: Aim for 85%+ coverage (66% minimum)
- **Naming**: Descriptive names, follow PEP 8
- **Async**: Use `async/await` consistently for I/O

### Git Commit Guidelines

**Format**:
```text
Short Title (50 chars max)

- Detailed change 1
- Detailed change 2

Implements: SPEC-Sortie-N-Name.md
Related: PRD-Feature-Name.md
```

**Granularity**: Commit as often as needed within a sortie. Each commit should be compilable and testable, but a sortie may contain multiple commits to complete its logical unit of work.

---

## Detailed Guides

For comprehensive documentation, see:

- **[Agent Workflow Detailed](docs/guides/AGENT_WORKFLOW_DETAILED.md)** - Complete workflow phases, PRD/SPEC templates, detailed examples, LLM integration walkthrough
- **[Agent Tools Reference](docs/guides/AGENT_TOOLS_REFERENCE.md)** - All GitHub Copilot tools, GitHub MCP, Hugging Face MCP, AI Toolkit, command line tools, selection strategies
- **[Agent Prompting Guide](docs/guides/AGENT_PROMPTING_GUIDE.md)** - All prompt patterns, advanced workflows, troubleshooting, multi-agent collaboration

---

## Example Sprint

See [Sprint 2: LLM Integration (2-start-me-up)](docs/sprints/completed/2-start-me-up/) for complete example:

- **Duration**: 3 days
- **Sorties**: 6 (Foundation → Remote Ollama → Triggers → Username → Deployment → Docs)
- **Commits**: Multiple commits per sortie as needed
- **Outcome**: Fully functional LLM chat integration with 95% test coverage
- **Files**: [PRD-LLM-Integration.md](docs/sprints/completed/2-start-me-up/PRD-LLM-Integration.md), SPEC-Sortie-1 through SPEC-Sortie-6

---

## Resources

### Project Documentation
- [README.md](README.md) - Main documentation
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [TESTING.md](docs/TESTING.md) - Testing guide
- [QUICKSTART.md](QUICKSTART.md) - Quick start

### Completed Sprints
- [2-start-me-up](docs/sprints/completed/2-start-me-up/) - LLM Integration ✅
- [3-rest-assured](docs/sprints/completed/3-rest-assured/) - REST API Migration ✅
- [4-test-assured](docs/sprints/completed/4-test-assured/) - Testing Infrastructure ✅
- [6a-quicksilver](docs/sprints/completed/6a-quicksilver/) - NATS Event Bus ✅

### External Resources
- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)

---

## Contributing

When contributing to Rosey-Robot:

1. **Propose Feature**: Open an issue
2. **Write PRD**: Create PRD in new sprint folder
3. **Create Specs**: Break down into sortie specs
4. **Implement**: Use agent assistance for each commit
5. **Test**: Write comprehensive tests
6. **Document**: Update all relevant docs
7. **Submit PR**: Link to PRD, list commits, provide testing notes
8. **Iterate**: Address review feedback with agent help

---

**Document Version**: 2.0  
**Last Updated**: November 21, 2025  
**Maintained By**: Rosey-Robot Team  
**Workflow Status**: ✅ Active and Proven
