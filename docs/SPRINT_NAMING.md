# Sprint Naming Convention

## Overview

Rosey-Robot sprint directories follow a specific naming convention that evolved from descriptive names to movie titles.

## Convention Format

```text
{number}-{movie-title-slug}
```

Where:

- **number**: Sequential sprint number (or number with letter suffix for sub-sprints)
- **movie-title-slug**: Lowercase, hyphenated movie title with thematic relevance

## Historical Evolution

### Early Sprints (Descriptive Names)

The first sprints used descriptive names that directly indicated their purpose:

- **2-start-me-up**: LLM Integration - "starting up" the AI capabilities
- **3-rest-assured**: REST API Migration - RESTful API implementation
- **4-test-assured**: Test Coverage - ensuring code quality
- **5-ship-it**: Production Deployment - shipping to production
- **6-make-it-real**: Advanced Deployment - making production robust

### Movie Title Convention (6a+)

Starting with Sprint 6a, the naming convention shifted to movie titles with thematic meaning:

- **6a-quicksilver**: NATS Event Bus Architecture
  - Theme: Speed, fluidity, transformation (like the X-Men character or liquid metal)
  - Relevance: NATS provides lightning-fast message routing, transforming the monolithic architecture into a fluid, distributed system
  - Mercury/quicksilver reference: Fast, adaptable, flows through the system

## Guidelines for Future Sprints

When naming future sprints, select movie titles that:

1. **Have Thematic Relevance**: The movie's themes, plot, or title should relate to the sprint's technical goals
2. **Are Memorable**: Easy to remember and reference in conversation
3. **Can Be Tongue-in-Cheek**: Humor and clever references are encouraged
4. **Avoid Ambiguity**: Should be recognizable as a movie title

### Good Examples

- Sprint about resilience/fault tolerance: "The Martian" (survival under adversity)
- Sprint about security hardening: "The Rock" or "Die Hard" (defense against threats)
- Sprint about UI/UX improvements: "The Matrix" (alternate reality/interface)
- Sprint about performance optimization: "Speed" or "Fast & Furious" (self-explanatory)
- Sprint about data migration: "Planes, Trains, and Automobiles" or "Cannonball Run" (moving data)
- Sprint about multi-platform support: "Crossroads" or "The Bridge" (connecting different worlds)

### Examples to Avoid

- Excessively long titles (keep it concise for directory names)

## Sub-Sprint Notation

A sub-sprint can be useful when a significant change of plans has been identified and it has been assesed that the work required is more appropriately done sooner rather than later. I.e. Message passing with NATS requires changes when deploying servers, which was easiest done before environments were already configured.

Use letter suffixes (a, b, c...) for related sub-sprints:

```text
6-make-it-real/        # Main sprint
6a-quicksilver/        # Architecture sub-sprint
6b-{movie-title}/      # Future sub-sprint (if needed)
```

## Directory Structure

Each sprint directory contains:

```text
docs/{N}-{movie-title}/
├── PRD-{Feature}.md           # Product requirements
├── SPEC-Sortie-{N}-{Name}.md  # Technical specifications
└── ...                        # Additional documentation
```

## Current Sprints

| Sprint | Name | Theme | Status |
|--------|------|-------|--------|
| 2 | start-me-up | LLM Integration | ✅ Complete |
| 3 | rest-assured | REST API Migration | ✅ Complete |
| 4 | test-assured | Test Coverage | ✅ Complete |
| 5 | ship-it | Production Deployment | ⚠️ Needs Validation |
| 6 | make-it-real | Advanced Deployment | 🔄 In Progress |
| 6a | quicksilver | NATS Event Bus | ✅ Complete |
| 7 | the-divide | TBD | 📋 Planned |

## Why Movie Titles?

0. **420Grindhouse**: Our original reason for existing, watching grindhouse movies with other Grindhouse fans on Cytube.
1. **Memorable**: Easier to remember "quicksilver" than "nats-event-bus-refactor"
2. **Cultural Reference**: Provides shared context and mental models
3. **Fun**: Makes development more engaging
4. **Descriptive**: Good movie choices convey sprint intent metaphorically
5. **Scalable**: Infinite supply of movies to choose from

## References

- Project workflow: `AGENTS.md`
- Sprint documentation: `docs/{N}-{name}/`
- Changelog: `CHANGELOG.md`
