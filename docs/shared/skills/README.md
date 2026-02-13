# Skills System Documentation

> Deep Agent Skill Mechanism - Design & Implementation Guide

## Document Index

| Document | Description | Audience |
|----------|-------------|----------|
| [01-architecture.md](01-architecture.md) | Full architecture specification: data model, component design, middleware integration, security, error handling, configuration, implementation phases, testing strategy | Developers implementing the skill system |
| [02-skill-format-specification.md](02-skill-format-specification.md) | SKILL.md format reference: YAML frontmatter fields, naming rules, body guidelines, supporting directories, complete examples, validation checklist | Developers and skill authors |
| [03-integration-guide.md](03-integration-guide.md) | Step-by-step integration into the deep agent pipeline: factory changes, runtime.py modifications, project module extensions, config setup, security whitelist, CLI command registration, help system updates | Developers implementing Phase 1-3 |
| [04-cli-commands.md](04-cli-commands.md) | CLI command design using the project's `BaseCommand` pattern: `SkillsCommand` class implementation, sub-command dispatch (`list`, `create`, `info`), command registration, help system integration | Developers implementing Phase 3 |
| [05-implementation-analysis-and-brainstorming.md](05-implementation-analysis-and-brainstorming.md) | Code audit findings, design decisions (17 decisions across 2 rounds), security analysis (tuple immutability, read/write shared whitelist, built-in write protection), unified source resolution design, doc revision guide, implementation sequence | Developers and reviewers |

## Quick Reference

### Skill directory structure

```
<skill-name>/
  SKILL.md              Required: YAML frontmatter + Markdown instructions
  scripts/              Optional: executable code
  references/           Optional: on-demand documentation
  assets/               Optional: static resources
```

### Skill source priorities (low -> high)

```
built-in    src/components/shared/skills/built_in_skills/    (bundled)
user        ~/.iris/skills/                                   (personal)
project     <project_root>/.iris/skills/                      (project)
```

### Code locations

```
src/components/shared/skills/           Shared infrastructure (loader, registry, validator)
src/components/deepagents/
  runtime_middlewares/skills/            SkillsMiddleware (deep agent integration)
src/application/commands/shared/
  skills_commands.py                    CLI commands (SkillsCommand)
config/agents/deep/middleware/skills/    Configuration files
```

### Implementation phases

1. **Phase 1 - MVP**: types, validator, loader, registry, formatter, middleware, project module extensions, config
2. **Phase 2 - Built-in + Factory**: skill-creator SKILL.md, factory integration, security whitelist
3. **Phase 3 - CLI**: SkillsCommand (list, create, info), help system updates, command registration
4. **Phase 4 - Advanced**: validate, reload (with source fingerprint), context:fork, allowed-tools enforcement, basic mode support

### Related documents

- [deepagents-architecture/middleware.md](../../deepagents-architecture/middleware.md) - Middleware pipeline reference
- [shared/tools/middleware/filesystem.md](../tools/middleware/filesystem.md) - Real filesystem middleware
- [deepagents-architecture/architecture.md](../../deepagents-architecture/architecture.md) - Deep agent architecture
