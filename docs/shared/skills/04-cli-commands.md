# CLI Commands Design

> Phase 3: Skill management commands integrated into the project CLI

## 1. Overview

Skills commands follow the project's existing `BaseCommand` + sub-command dispatch pattern
(same pattern used by `DeepCommand` and `MCPCommand`).

A single `SkillsCommand` class handles all sub-commands. It lives in the shared commands
directory because skills are shared infrastructure, not engine-specific.

### Commands

| Sub-command | Usage | Description |
|-------------|-------|-------------|
| `list` | `/skills list` | List all available skills grouped by source |
| `create` | `/skills create <name> [--project]` | Create a new skill from template |
| `info` | `/skills info <name>` | Display detailed skill information |
These three commands cover the essential workflow: discover, create, inspect.
Additional commands (`validate`, `reload`) can be added later if needed.

### File Location

```
src/application/commands/shared/skills_commands.py   <-- SkillsCommand class
```

---

## 2. Command Class Design

### `SkillsCommand` (BaseCommand)

Follows the sub-command dispatch pattern from `DeepCommand`:

```python
"""
Skill management commands.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.application.commands.base import BaseCommand, CommandResult

logger = logging.getLogger(__name__)

# Skill name validation pattern (same as SkillValidator)
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9]*(-[a-z0-9]+)*)?$")
MAX_SKILL_NAME_LENGTH = 64


class SkillsCommand(BaseCommand):
    """Manage agent skills: list, create, and inspect."""

    name = "skills"
    engine_scope = ("agent",)
    help_text = "Manage agent skills (list, create, info)."

    async def execute(self, ctx, args: str) -> CommandResult:
        parts = args.strip().split()
        if not parts:
            return CommandResult.info(self._usage())

        action = parts[0].lower()
        rest = parts[1:]

        handlers = {
            "list": self._handle_list,
            "create": self._handle_create,
            "info": self._handle_info,
        }

        handler = handlers.get(action)
        if handler is None:
            return CommandResult.error(self._usage())

        return await handler(ctx, rest)

    # ------------------------------------------------------------------ usage

    def _usage(self) -> str:
        return (
            "Usage:\n"
            "  /skills list\n"
            "  /skills create <name> [--project]\n"
            "  /skills info <name>"
        )

    # ------------------------------------------------------------------ list

    async def _handle_list(self, ctx, args: list[str]) -> CommandResult:
        """List all available skills grouped by source."""
        try:
            from src.components.shared.skills import SkillRegistry

            registry = SkillRegistry.get_instance()
            self._ensure_initialized(registry, ctx)

            skills = registry.get_all_skills()
            errors = registry.get_load_errors()

            if not skills and not errors:
                return CommandResult.info("No skills found.")

            message = self._format_skill_list(skills, errors)
            return CommandResult.success(message)
        except Exception as exc:
            logger.warning("Failed to list skills: %s", exc, exc_info=True)
            return CommandResult.error(f"Failed to list skills: {exc}")

    # ------------------------------------------------------------------ create

    async def _handle_create(self, ctx, args: list[str]) -> CommandResult:
        """Create a new skill from template."""
        if not args:
            return CommandResult.error(
                "Usage: /skills create <name> [--project]\n"
                "  Name must be lowercase alphanumeric with hyphens (e.g. web-research)"
            )

        name = args[0]
        use_project = "--project" in args

        # Validate name
        if not self._validate_skill_name(name):
            return CommandResult.error(
                f"Name '{name}' is invalid.\n"
                "  Skill names must use lowercase letters, digits, and hyphens only.\n"
                "  Examples: web-research, code-review, my-tool-v2"
            )

        # Determine target directory
        target_dir = self._resolve_target_dir(ctx, name, project=use_project)
        if target_dir is None:
            return CommandResult.error(
                "Not in a project directory. Cannot use --project flag.\n"
                "  Run this command from a directory containing .iris, .git, or pyproject.toml."
            )

        # Check existing
        if target_dir.exists():
            return CommandResult.error(
                f"Skill '{name}' already exists at {target_dir}/\n"
                "  Use a different name or delete the existing skill first."
            )

        # Create from template
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            skill_file = target_dir / "SKILL.md"
            skill_file.write_text(self._skill_template(name), encoding="utf-8")

            return CommandResult.success(
                f"Created skill '{name}' at:\n"
                f"  {skill_file}\n\n"
                "Edit the SKILL.md file to add your skill instructions.\n"
                "The skill will be available in your next agent session."
            )
        except Exception as exc:
            logger.warning("Failed to create skill '%s': %s", name, exc, exc_info=True)
            return CommandResult.error(f"Failed to create skill: {exc}")

    # ------------------------------------------------------------------ info

    async def _handle_info(self, ctx, args: list[str]) -> CommandResult:
        """Display detailed information about a skill."""
        if not args:
            return CommandResult.error("Usage: /skills info <name>")

        name = args[0]

        try:
            from src.components.shared.skills import SkillRegistry

            registry = SkillRegistry.get_instance()
            self._ensure_initialized(registry, ctx)

            skill = registry.get_skill(name)
            if skill is None:
                all_names = [s.name for s in registry.get_all_skills()]
                hint = ", ".join(all_names[:5]) if all_names else "(none)"
                return CommandResult.error(
                    f"Skill '{name}' not found.\n"
                    f"  Available skills: {hint}\n"
                    "  Run '/skills list' to see all available skills."
                )

            message = self._format_skill_info(skill)
            return CommandResult.success(message)
        except Exception as exc:
            logger.warning("Failed to get skill info for '%s': %s", name, exc, exc_info=True)
            return CommandResult.error(f"Failed to get skill info: {exc}")

    # ------------------------------------------------------------------ helpers

    def _ensure_initialized(self, registry, ctx) -> None:
        """Initialize registry with skill sources if not already done."""
        if registry.is_initialized():
            return

        from src.components.shared.skills import SkillRegistry

        # Use the unified resolve_sources() — same logic as Factory/Middleware
        project_ctx = getattr(ctx, "project_context", None)
        project_skills_dir = project_ctx.skills_dir if project_ctx else None

        sources = SkillRegistry.resolve_sources(
            config=None,  # CLI uses default config (all sources enabled)
            project_skills_dir=project_skills_dir,
        )

        registry.initialize(sources)

    @staticmethod
    def _validate_skill_name(name: str) -> bool:
        """Check if a skill name follows naming rules."""
        if not name or len(name) > MAX_SKILL_NAME_LENGTH:
            return False
        if "--" in name:
            return False
        return bool(SKILL_NAME_PATTERN.match(name))

    @staticmethod
    def _resolve_target_dir(ctx, name: str, *, project: bool) -> Optional[Path]:
        """Determine where to create the skill directory."""
        if project:
            project_ctx = getattr(ctx, "project_context", None)
            if project_ctx is None:
                return None
            return project_ctx.skills_dir / name

        from src.core.project.share import IrisShareDir
        return IrisShareDir.get_skills_dir() / name

    @staticmethod
    def _skill_template(name: str) -> str:
        """Generate SKILL.md content from template."""
        return (
            "---\n"
            f"name: {name}\n"
            "description: >\n"
            "  TODO: Describe what this skill does and when to use it.\n"
            "  Include keywords that help the agent recognize relevant tasks.\n"
            "metadata:\n"
            '  author: ""\n'
            '  version: "1.0.0"\n'
            "  category: general\n"
            "---\n"
            "\n"
            f"# {name}\n"
            "\n"
            "TODO: Add skill instructions here.\n"
            "\n"
            "## When to Use\n"
            "\n"
            "Describe the scenarios where this skill should be activated.\n"
            "\n"
            "## Workflow\n"
            "\n"
            "### Step 1: ...\n"
            "\n"
            "### Step 2: ...\n"
            "\n"
            "## Edge Cases\n"
            "\n"
            "- TODO: Document edge cases\n"
        )

    @staticmethod
    def _format_skill_list(skills, errors) -> str:
        """Format skills grouped by source type."""
        from src.components.shared.skills import SkillSourceType

        grouped: Dict[str, List] = {
            "Built-in": [],
            "User": [],
            "Project": [],
        }
        source_labels = {
            SkillSourceType.BUILT_IN: "Built-in",
            SkillSourceType.USER: "User",
            SkillSourceType.PROJECT: "Project",
        }

        for skill in skills:
            label = source_labels.get(skill.source_type, "Unknown")
            grouped[label].append(skill)

        lines = ["Skills:"]
        total = 0
        for label, group in grouped.items():
            if not group:
                continue
            lines.append(f"\n  {label}:")
            for skill in group:
                desc = (skill.description or "")[:60]
                lines.append(f"    {skill.name:<24} {desc}")
                total += 1

        if errors:
            lines.append("\n  Warnings:")
            for err in errors:
                lines.append(f"    [WARN] {err.path}: {err.message}")

        lines.append(f"\n  Total: {total} skill(s)")
        return "\n".join(lines)

    @staticmethod
    def _format_skill_info(skill) -> str:
        """Format detailed skill information."""
        lines = [
            f"Skill: {skill.name}",
            f"Source: {skill.source_type.value} ({skill.path.parent})",
            f"Description: {skill.description or '(none)'}",
        ]

        if skill.metadata:
            lines.append("\nMetadata:")
            for key, value in skill.metadata.items():
                lines.append(f"  {key}: {value}")

        if skill.allowed_tools:
            lines.append(f"\nAllowed Tools: {', '.join(skill.allowed_tools)}")
        if skill.user_invocable is not None:
            lines.append(f"User Invocable: {skill.user_invocable}")

        return "\n".join(lines)


__all__ = ["SkillsCommand"]
```

### Key Design Decisions

1. **Single class, sub-command dispatch**: Same pattern as `DeepCommand` in
   [deep_commands.py](../../src/application/commands/agent/deep/deep_commands.py).
   Parse `parts[0]` as action, delegate to handler method.

2. **`engine_scope = ("agent",)`**: Skills are only relevant in agent mode (deep agent).
   Not available in `llm`, `agentflow`, or `dify` engines.

3. **All handlers are `async`**: Even though some could be sync, using `async` for
   consistency avoids the `inspect.isawaitable()` check pattern.

4. **Uses `SkillRegistry` from shared infrastructure**: The same registry instance used
   by `SkillsMiddleware` at runtime. This ensures CLI output matches what the agent sees.

5. **Lazy initialization**: `_ensure_initialized()` sets up registry sources on first use.
   No startup cost if skills commands are never invoked.

---

## 3. Registration

### `src/application/commands/__init__.py`

Add `SkillsCommand` to the import list and command registration:

```python
# In register_default_commands():
from src.application.commands.shared.skills_commands import SkillsCommand

commands: list[BaseCommand] = [
    # ... existing commands ...
    SkillsCommand(),       # NEW
]
```

This follows the exact pattern of all other commands in the registry.

---

## 4. Help System Updates

### `src/application/cli/gui/render.py`

Add a new command list constant for skills:

```python
# After AGENT_TOOL_COMMANDS definition:
SKILL_COMMANDS = [
    ("/skills list", "List available skills (built-in, user, project)"),
    ("/skills create <name>", "Create a new skill from template"),
    ("/skills info <name>", "Show detailed skill information"),
]
```

Include the section in both `print_welcome()` and `print_help()`:

```python
# In print_welcome():
sections = [
    _format_command_section("Global Commands", GLOBAL_COMMANDS),
    _format_command_section("Session Management", SESSION_COMMANDS),
    _format_command_section("LLM Engine", LLM_ENGINE_COMMANDS),
    _format_command_section("Agent Engine", AGENT_ENGINE_COMMANDS),
    _format_command_section("Deep Agent Commands", DEEP_AGENT_COMMANDS),
    _format_command_section("Agent Tools", AGENT_TOOL_COMMANDS),
    _format_command_section("Skills", SKILL_COMMANDS),                # NEW
]

# In print_help() (non-dify branch):
sections = [
    _format_command_section("Global Commands", GLOBAL_COMMANDS),
    _format_command_section("Session Management", SESSION_COMMANDS),
    _format_command_section("LLM Engine", LLM_ENGINE_COMMANDS),
    _format_command_section("Agent Engine", AGENT_ENGINE_COMMANDS),
    _format_command_section("Deep Agent Commands", DEEP_AGENT_COMMANDS),
    _format_command_section("Agent Tools", AGENT_TOOL_COMMANDS),
    _format_command_section("Skills", SKILL_COMMANDS),                # NEW
]
```

### Help Output Preview

```
Skills
------
  /skills list                   List available skills (built-in, user, project)
  /skills create <name>          Create a new skill from template
  /skills info <name>            Show detailed skill information
```

---

## 5. Command Behavior Details

### `/skills list`

Displays all discovered skills grouped by source.

```
Skills:

  Built-in:
    skill-creator            Guide for creating new skills with proper structure

  User:
    web-research             Structured methodology for web research
    code-review              Systematic code review checklist

  Project:
    custom-workflow           Project-specific deployment workflow

  Total: 4 skill(s)
```

If there are load warnings:

```
Skills:

  Built-in:
    skill-creator            Guide for creating new skills with proper structure

  Warnings:
    [WARN] ~/.iris/skills/broken-skill/SKILL.md: Invalid YAML frontmatter

  Total: 1 skill(s)
```

### `/skills create <name>`

Creates a new skill directory with a `SKILL.md` template file.

**Default (user-level):**
```
> /skills create web-research
Created skill 'web-research' at:
  ~/.iris/skills/web-research/SKILL.md

Edit the SKILL.md file to add your skill instructions.
The skill will be available in your next agent session.
```

**Project-level:**
```
> /skills create deploy-helper --project
Created skill 'deploy-helper' at:
  /path/to/project/.iris/skills/deploy-helper/SKILL.md

Edit the SKILL.md file to add your skill instructions.
The skill will be available in your next agent session.
```

**Error cases:**

```
> /skills create Bad_Name
Error: Name 'Bad_Name' is invalid.
  Skill names must use lowercase letters, digits, and hyphens only.
  Examples: web-research, code-review, my-tool-v2

> /skills create web-research
Error: Skill 'web-research' already exists at ~/.iris/skills/web-research/
  Use a different name or delete the existing skill first.
```

### `/skills info <name>`

Displays detailed metadata for a specific skill.

```
> /skills info web-research
Skill: web-research
Source: user (~/.iris/skills/web-research/)
Description: Structured methodology for conducting thorough web research

Metadata:
  author: iris-team
  version: 1.0.0
  category: research

Allowed Tools: read_real_file, tavily_search
User Invocable: true
```

**When skill not found:**

```
> /skills info nonexistent
Error: Skill 'nonexistent' not found.
  Available skills: skill-creator, web-research, code-review
  Run '/skills list' to see all available skills.
```

---

## 6. Error Handling

All sub-commands follow the project's existing error handling conventions:

1. **Never raise unhandled exceptions** -- all handlers wrap logic in try/except
   and return `CommandResult.error()` with a user-friendly message
2. **Log internal errors** -- use `logger.warning()` with `exc_info=True` for debugging
3. **Return `CommandResult` types consistently**:
   - `CommandResult.success(message)` for successful operations
   - `CommandResult.error(message)` for user errors and failures
   - `CommandResult.info(message)` for usage hints (no args provided)

---

## 7. Future Extensions (Phase 4)

These commands are intentionally deferred to Phase 4.
They can be added to the `handlers` dict when needed:

| Command | Description | When to Add |
|---------|-------------|-------------|
| `/skills validate [name]` | Validate SKILL.md format | When users start creating custom skills at scale |
| `/skills reload` | Reload skills without restarting agent | When rapid skill iteration workflow is common |
| `/skills remove <name>` | Remove a user/project skill | When CLI-based skill lifecycle management is needed |

Adding a new sub-command requires only:
1. Add a handler method `_handle_<action>(self, ctx, args)` to `SkillsCommand`
2. Add an entry in the `handlers` dict
3. Update `_usage()` string
4. Add help text to `SKILL_COMMANDS` in `render.py`
