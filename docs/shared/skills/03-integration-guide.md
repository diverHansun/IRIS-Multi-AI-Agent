# Integration Guide

> Step-by-step guide for integrating the Skills system into the Deep Agent pipeline

## 1. Overview

This document describes the concrete code changes required to integrate the Skills system. It follows the implementation phases defined in [01-architecture.md](01-architecture.md).

### Integration Points

```
Phase 1 - Shared infrastructure:
  src/components/shared/skills/          New module (types, loader, registry, validator, formatter)

Phase 1 - Project module extensions:
  src/core/project/share.py              Add get_skills_dir()
  src/core/project/context.py            Add skills_dir property

Phase 2 - Deep agent integration:
  src/components/deepagents/
    runtime_middlewares/skills/           New module (SkillsMiddleware)
  src/agents/deepagents/factories/
    base.py                              Add _inject_skills_middleware()
  src/components/deepagents/runtime.py   Accept skills_middleware parameter
  config/agents/deep/middleware/skills/   New config files

Phase 3 - CLI commands:
  src/application/commands/shared/
    skills_commands.py                   New file (SkillsCommand class)
  src/application/commands/__init__.py   Register SkillsCommand
  src/application/cli/gui/render.py      Add SKILL_COMMANDS to help output
```

---

## 2. Phase 1: Shared Infrastructure

### 2.1 Create `src/components/shared/skills/`

Create the following files in order (each depends on the previous):

#### Step 1: `types.py`

Define data models and constants. No external dependencies beyond stdlib and dataclasses.

Key types:
- `SkillSourceType` (enum: BUILT_IN, USER, PROJECT)
- `SkillSource` (dataclass: type, path, priority)
- `SkillMetadata` (dataclass: all frontmatter fields + internal fields)
- `SkillLoadError` (dataclass: error reporting)
- Constants: `MAX_SKILL_NAME_LENGTH`, `MAX_SKILL_FILE_SIZE`, `SKILL_FILENAME`, `SKILL_NAME_PATTERN`

See [01-architecture.md Section 4.1](01-architecture.md#41-skillmetadata) for the complete data model.

#### Step 2: `validator.py`

Implement validation logic. Depends only on `types.py`.

Key methods:
- `validate_name(name: str, directory_name: str) -> Tuple[bool, List[str]]`
  - Check length (1-64)
  - Check pattern (lowercase alphanumeric + hyphens)
  - Check no consecutive hyphens
  - Check name matches directory
- `validate_metadata(skill: SkillMetadata) -> Tuple[bool, List[str]]`
  - Check required fields (name, description)
  - Truncate overlong fields
  - Type-check metadata dict

#### Step 3: `loader.py`

Implement SKILL.md discovery and parsing. Depends on `types.py` and `validator.py`.

Key methods:
- `load_from_source(source: SkillSource) -> List[SkillMetadata]`
  - List subdirectories in source.path
  - For each, look for SKILL.md
  - Parse YAML frontmatter
  - Skip invalid skills with warning
- `parse_skill_md(content: str, skill_path: Path, directory_name: str) -> Optional[SkillMetadata]`
  - Extract YAML between `---` delimiters using regex
  - Parse with `yaml.safe_load`
  - Map fields to SkillMetadata
  - Return None on any error

Dependencies: `pyyaml` (already in project dependencies via langchain).

#### Step 4: `registry.py`

Implement singleton registry with caching. Depends on `types.py`, `loader.py`, `validator.py`.

Key methods:
- `get_instance() -> SkillRegistry` (singleton)
- `initialize(sources: List[SkillSource]) -> None`
- `reload() -> None`
- `get_all_skills() -> List[SkillMetadata]`
- `get_skill(name: str) -> Optional[SkillMetadata]`
- `get_load_errors() -> List[SkillLoadError]`

Precedence: iterate sources in priority order, later entries override same-name earlier entries.

#### Step 5: `formatter.py`

Implement system prompt formatting. Depends on `types.py`.

Key method:
- `format(skills: List[SkillMetadata]) -> str`
  - Simple list format (see [01-architecture.md Section 6](01-architecture.md#6-system-prompt-injection))
  - Include skill name, description, and absolute path to SKILL.md

#### Step 6: `__init__.py`

Export public API:
```python
from .types import SkillMetadata, SkillSource, SkillSourceType, SkillLoadError
from .registry import SkillRegistry
from .loader import SkillLoader
from .validator import SkillValidator
from .formatter import SkillPromptFormatter
```

### 2.2 Extend Project Module

#### `src/core/project/share.py`

Add to `IrisShareDir` class:

```python
@classmethod
def get_skills_dir(cls) -> Path:
    """Get user-level skills directory (~/.iris/skills/)."""
    skills_dir = cls.get_share_dir() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir
```

This follows the existing pattern of `get_tools_dir()`, `get_agents_dir()`, etc.

Update the directory structure docstring at the top of the class to include the `skills/` entry.

#### `src/core/project/context.py`

Add to `ProjectContext` class:

```python
@property
def skills_dir(self) -> Path:
    """Project-level skills directory (<project>/.iris/skills/)."""
    return self.iris_dir / "skills"
```

Do **NOT** modify `ensure_structure()` — the skills directory must not be auto-created.
It is only created on-demand when the user explicitly runs `/skills create --project`.

The `skills_dir` property returns the path but does not guarantee the directory exists.

---

## 3. Phase 2: Deep Agent Integration

### 3.1 Create `src/components/deepagents/runtime_middlewares/skills/`

#### `middleware.py`

```python
class SkillsMiddleware(AgentMiddleware):
    """Inject skill knowledge into the agent's system prompt."""

    def __init__(
        self,
        *,
        config: Dict[str, Any] | None = None,
        sources: List[SkillSource] | None = None,
        registry: SkillRegistry | None = None,
    ):
        # `sources` is pre-computed by Factory via SkillRegistry.resolve_sources()
        ...

    def before_agent(self, state, runtime) -> Dict[str, Any] | None:
        # Initialize registry with pre-computed sources if needed.
        # Does NOT compute paths — Factory already handled filesystem whitelist.
        ...

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        # Format skill list and append to system prompt
        ...

    async def awrap_model_call(self, request: ModelRequest, handler):
        # Async version
        ...
```

> **Note**: `get_skill_source_paths()` is no longer needed — the Factory uses
> `SkillRegistry.resolve_sources()` to directly compute paths before creating the middleware.

Pattern reference: Follow `RealFilesystemMiddleware` (same file structure, same `AgentMiddleware` interface). See [runtime_middlewares/real_filesystem/middleware.py](../../src/components/deepagents/runtime_middlewares/real_filesystem/middleware.py).

#### `__init__.py`

```python
from .middleware import SkillsMiddleware

__all__ = ["SkillsMiddleware"]
```

### 3.2 Modify `BaseDeepAgentFactory` (`src/agents/deepagents/factories/base.py`)

The factory is the composition point where middlewares are assembled. Add skills support following the existing `_inject_filesystem_tools` and `_inject_shell_tool` patterns.

#### Changes to `create_agent()` method:

```python
async def create_agent(self, *, ..., **user_params):
    resolved_middleware = self._resolve_middleware_config(adapter, middleware_config)

    # ... existing code ...

    # Inject filesystem tools (existing)
    tools, filesystem_middlewares = self._inject_filesystem_tools(tools, resolved_middleware)

    # Inject skills middleware (NEW)
    skills_middleware = self._inject_skills_middleware(resolved_middleware, filesystem_middlewares)

    # Inject shell tool (existing)
    tools, shell_middleware = self._inject_shell_tool(tools, resolved_middleware)

    # ... existing code ...

    runtime = create_deep_agent_runtime(
        # ... existing params ...
        filesystem_middlewares=filesystem_middlewares,
        shell_middleware=shell_middleware,
        skills_middleware=skills_middleware,  # NEW parameter
    )
```

#### New method `_inject_skills_middleware()`:

```python
def _inject_skills_middleware(
    self,
    middleware_config: Dict[str, Any],
    filesystem_middlewares: List[Any],
    project_context=None,
) -> Optional[Any]:
    """
    Create SkillsMiddleware if enabled.

    Uses SkillRegistry.resolve_sources() to compute paths DIRECTLY,
    then extends RealFilesystemMiddleware's allowed_paths (tuple rebuild)
    and adds built-in write protection (excluded_paths).
    """
    skills_config = middleware_config.get("skills", {})

    if not isinstance(skills_config, dict) or not skills_config.get("enabled", True):
        return None

    try:
        from src.components.deepagents.runtime_middlewares.skills import SkillsMiddleware
        from src.components.shared.skills import SkillRegistry

        # 1. Compute source paths directly (not via middleware.before_agent)
        project_skills_dir = project_context.skills_dir if project_context else None
        sources = SkillRegistry.resolve_sources(
            config=skills_config,
            project_skills_dir=project_skills_dir,
        )
        skill_source_paths = [s.path for s in sources if s.path.exists()]

        # 2. Extend filesystem whitelist + built-in write protection
        self._extend_filesystem_for_skills(skill_source_paths, filesystem_middlewares)

        # 3. Create middleware with pre-computed sources
        skills_middleware = SkillsMiddleware(config=skills_config, sources=sources)
        return skills_middleware
    except Exception as exc:
        logger.warning("Failed to create SkillsMiddleware: %s", exc, exc_info=True)
        return None
```

#### New method `_extend_filesystem_for_skills()`:

```python
def _extend_filesystem_for_skills(
    self,
    skill_source_paths: List[Path],
    filesystem_middlewares: List[Any],
) -> None:
    """
    Extend RealFilesystemMiddleware's allowed_paths with skill source
    directories and add built-in write protection.

    CRITICAL: allowed_paths is tuple[Path, ...] — cannot .append().
    Must rebuild: existing + new_paths.

    Also adds BUILT_IN_SKILLS_DIR to excluded_paths to prevent
    agent from writing to built-in skills.
    """
    if not skill_source_paths:
        return

    from src.components.deepagents.runtime_middlewares.real_filesystem import (
        RealFilesystemMiddleware,
    )
    from src.components.shared.skills.types import BUILT_IN_SKILLS_DIR

    for mw in filesystem_middlewares:
        if isinstance(mw, RealFilesystemMiddleware):
            sec = mw.options.security

            # 1. Rebuild allowed_paths tuple (immutable — cannot append)
            existing = sec.allowed_paths
            new_paths = tuple(
                p for p in skill_source_paths
                if p.exists() and p not in existing
            )
            if new_paths:
                sec.allowed_paths = existing + new_paths
                logger.debug("Extended real filesystem allowed_paths with: %s", new_paths)

            # 2. Write-protect built-in skills dir via excluded_paths
            if BUILT_IN_SKILLS_DIR.exists() and BUILT_IN_SKILLS_DIR not in sec.excluded_paths:
                sec.excluded_paths = sec.excluded_paths + (BUILT_IN_SKILLS_DIR,)
                logger.debug("Added built-in skills dir to excluded_paths (write-protect)")

            break
```

#### Update `_resolve_middleware_config()`:

Add `"skills"` to the resolution loop:

```python
def _resolve_middleware_config(self, adapter, global_config):
    provider_middleware = adapter.get_middleware_config()
    resolved = {}
    for key in ("filesystem", "subagents", "patch_tool_calls", "shell", "skills"):  # Added "skills"
        value = provider_middleware.get(key)
        if isinstance(value, dict):
            resolved[key] = value
        elif isinstance(value, str) and value != "default":
            resolved[key] = global_config.get(value, {})
        else:
            resolved[key] = global_config.get(key, {})
    return resolved
```

> **Note**: The actual `_resolve_middleware_config` at
> [base.py](../../src/agents/deepagents/factories/base.py) currently iterates
> over `("filesystem", "subagents", "patch_tool_calls", "shell")`.
> Adding `"skills"` to this tuple is the only change needed.

### 3.3 Modify `create_deep_agent_runtime()` (`src/components/deepagents/runtime.py`)

Add `skills_middleware` parameter and insert it into the middleware pipeline.

#### Changes to function signature:

```python
def create_deep_agent_runtime(
    *,
    # ... existing params ...
    skills_middleware: Any | None = None,  # NEW
) -> CompiledStateGraph:
```

#### Changes to middleware pipeline construction:

```python
# Build main agent middleware list
deepagent_middleware: List[AgentMiddleware] = [
    JsonArgsParserMiddleware(enable_logging=True),
    TodoListMiddleware(),
]

# Add skills middleware if provided (after TodoList, before filesystem)
if skills_middleware is not None:
    deepagent_middleware.append(skills_middleware)

# Add filesystem middleware if enabled
deepagent_middleware.extend(provided_filesystem_middlewares)

# ... rest of existing pipeline ...
```

### 3.4 Create Configuration Files

#### `config/agents/deep/middleware/skills/skills.json`

```json
{
  "enabled": true,
  "sources": {
    "built_in": true,
    "user": true,
    "project": true
  },
  "prompt": {
    "format": "simple",
    "max_skills_in_prompt": 20
  },
  "validation": {
    "strict_name_check": true,
    "warn_on_missing_description": true
  }
}
```

#### `config/agents/deep/middleware/skills/skills.example.json`

Same content with comments explaining each field.

### 3.5 Create Built-in Skill

#### `src/components/shared/skills/built_in_skills/skill-creator/SKILL.md`

See [01-architecture.md Section 12](01-architecture.md#12-built-in-skill-skill-creator) for content outline.

---

## 4. Security: Filesystem Whitelist

### The Problem

`read_real_file` validates all file paths against `security.allowed_paths` in `real_filesystem.json`. By default, only `${PROJECT_ROOT}` is allowed.

Skill directories that need to be accessible:
- Built-in: `src/components/shared/skills/built_in_skills/` (inside project, OK)
- User: `~/.iris/skills/` (OUTSIDE project root, BLOCKED)
- Project: `<project>/.iris/skills/` (may be inside project, depends on `.iris` exclusion)

### The Solution

The factory uses `SkillRegistry.resolve_sources()` to compute skill source paths directly,
then dynamically extends `RealFilesystemMiddleware.options.security.allowed_paths` at agent
creation time (see `_extend_filesystem_for_skills()` in §3.2).

**Whitelist strategy: Source Roots** (decided in [05-implementation-analysis-and-brainstorming.md](05-implementation-analysis-and-brainstorming.md))

We whitelist the three source root directories (built-in root, `~/.iris/skills/`, `<project>/.iris/skills/`) rather than individual skill directories.

Rationale:
1. Simpler implementation
2. `~/.iris/skills/` only contains user-created skills — no sensitive file leakage risk
3. Newly created skills are immediately accessible via `read_real_file` without reload
4. Built-in directory is inside the codebase with standard code protection

This approach:
- Does not require modifying `real_filesystem.json`
- Is transparent to the user
- Only adds paths that actually exist
- Follows SRP: factory handles composition, middlewares stay independent

### Security Considerations

**Critical**: `allowed_paths` is `tuple[Path, ...]` — it must be rebuilt, not appended to.

**Critical**: `allowed_paths` controls **both** read and write operations. `validate_file()` (read) and `validate_new_file_path()` (write) both use `ensure_directory_access()` → `_is_within(allowed_paths)`.

**Access matrix after whitelisting**:

| Skill source | read (`read_real_file`) | write (`write_real_file`) |
|-------------|------------------------|---------------------------|
| built-in | ✅ via `allowed_paths` | ❌ blocked via `excluded_paths` |
| user `~/.iris/skills/` | ✅ | ✅ (user may edit own skills) |
| project `.iris/skills/` | ✅ | ✅ (user may edit own skills) |

**Write protection for built-in**: `BUILT_IN_SKILLS_DIR` is added to `excluded_paths` by `_extend_filesystem_for_skills()`. The `excluded_paths` check takes precedence over `allowed_paths` for write operations.

---

## 5. Configuration Loading

### How Skills Config Enters the Pipeline

```
1. DeepAgentManager.create_agent() is called
     |
2. middleware_config = provider_registry.get_middleware_config()
     |
     This loads from config/agents/deep/middleware/ hierarchy.
     Currently loads: filesystem, shell.
     Skills config needs to be added here.
     |
3. Factory._resolve_middleware_config() resolves per-key
     |
     Now includes "skills" key (added to iteration tuple).
     |
4. Factory calls SkillRegistry.resolve_sources(config, project_skills_dir)
     |
     This computes the source list using:
     - BUILT_IN_SKILLS_DIR             -> src/.../built_in_skills/
     - IrisShareDir.get_skills_dir()   -> ~/.iris/skills/
     - ProjectContext.skills_dir       -> <project>/.iris/skills/
     |
5. Factory._inject_skills_middleware() creates SkillsMiddleware(sources=sources)
     |
     Factory also calls _extend_filesystem_for_skills()
     to rebuild allowed_paths tuple + add built-in to excluded_paths
```

### Adding Skills to Middleware Config Loading

The middleware config loading happens in `src/core/providers/deepagents_provider_registry.py`.
Add skills config to `_load_middleware_config()`:

```python
def _load_middleware_config(self, *, use_cache: bool = True) -> Dict[str, Any]:
    # ... existing filesystem and shell loading ...

    skills_cfg: Dict[str, Any] = (
        self._config_loader.load_shared_json(
            "agents/deep/middleware/skills/skills.json"
        )
        or {}
    )

    # Fallback to explicit base_path
    if not skills_cfg and self.base_path:
        skills_path = self.base_path / "middleware" / "skills" / "skills.json"
        if skills_path.exists():
            skills_cfg = self._load_json(skills_path, use_cache=use_cache)

    return {
        "filesystem": {
            "virtual": virtual_cfg,
            "real": real_cfg,
        },
        "shell": shell_cfg,
        "skills": skills_cfg,    # NEW
    }
```

### Source Resolution and Project Context

- **With project context**: Three sources are resolved (built-in + user + project)
- **Without project** or `sources.project: false`: Only built-in + user sources
- CLI and Middleware share `SkillRegistry.resolve_sources()` as the unified entry point
- The Factory passes the computed `sources` list to `SkillsMiddleware` at construction time — the middleware does **not** compute sources itself

---

## 6. Phase 3: CLI Commands Integration

Phase 3 adds `/skills` commands to the interactive CLI. See [04-cli-commands.md](04-cli-commands.md) for the full command class design and implementation code.

### 6.1 Create `src/application/commands/shared/skills_commands.py`

Implement `SkillsCommand(BaseCommand)` following the sub-command dispatch pattern from
`DeepCommand` (`src/application/commands/agent/deep/deep_commands.py`).

Key attributes:
```python
class SkillsCommand(BaseCommand):
    name = "skills"
    engine_scope = ("agent",)
    help_text = "Manage agent skills (list, create, info)."
```

Sub-commands: `list`, `create`, `info`. Each maps to a `_handle_<action>()` method
in the `handlers` dict.

See [04-cli-commands.md Section 2](04-cli-commands.md#2-command-class-design) for the
complete class implementation.

### 6.2 Register Command in `src/application/commands/__init__.py`

Add `SkillsCommand` to the `register_default_commands()` function:

```python
def register_default_commands() -> None:
    # ... existing imports ...
    from src.application.commands.shared.skills_commands import SkillsCommand

    commands: list[BaseCommand] = [
        # ... existing commands ...
        ToolsCommand(),
        MCPCommand(),
        ConnectorCommand(),
        SkillsCommand(),       # NEW -- after other shared commands
        # ... rest ...
    ]
```

### 6.3 Update Help System in `src/application/cli/gui/render.py`

#### Add command list constant

After the `AGENT_TOOL_COMMANDS` list (around line 66), add:

```python
SKILL_COMMANDS = [
    ("/skills list", "List available skills (built-in, user, project)"),
    ("/skills create <name>", "Create a new skill from template"),
    ("/skills info <name>", "Show detailed skill information"),
]
```

#### Update `print_welcome()` sections

Add the skills section to the `sections` list in `print_welcome()`:

```python
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

#### Update `print_help()` sections

Add the same section to the non-dify branch in `print_help()`:

```python
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

Note: The dify-mode help section does NOT need skills commands because
skills are only available in agent mode (`engine_scope = ("agent",)`).

---

## 7. Checklist

### Phase 1 Checklist

- [ ] `src/components/shared/skills/types.py` created
- [ ] `src/components/shared/skills/validator.py` created
- [ ] `src/components/shared/skills/loader.py` created
- [ ] `src/components/shared/skills/registry.py` created
- [ ] `src/components/shared/skills/formatter.py` created
- [ ] `src/components/shared/skills/__init__.py` created
- [ ] `src/core/project/share.py` extended with `get_skills_dir()`
- [ ] `src/core/project/context.py` extended with `skills_dir`
- [ ] Unit tests for all shared skill components

### Phase 2 Checklist

- [ ] `src/components/deepagents/runtime_middlewares/skills/middleware.py` created
- [ ] `src/components/deepagents/runtime_middlewares/skills/__init__.py` created
- [ ] `src/agents/deepagents/factories/base.py` modified (3 changes)
- [ ] `src/components/deepagents/runtime.py` modified (accept skills_middleware)
- [ ] `config/agents/deep/middleware/skills/skills.json` created
- [ ] `config/agents/deep/middleware/skills/skills.example.json` created
- [ ] `src/components/shared/skills/built_in_skills/skill-creator/SKILL.md` created
- [ ] Middleware config loading includes skills
- [ ] Filesystem whitelist extends for skill directories
- [ ] Integration tests: skill appears in system prompt
- [ ] Integration tests: agent reads SKILL.md via read_real_file

### Phase 3 Checklist

- [ ] `src/application/commands/shared/skills_commands.py` created (SkillsCommand class)
- [ ] `src/application/commands/__init__.py` updated (register SkillsCommand)
- [ ] `src/application/cli/gui/render.py` updated (SKILL_COMMANDS list, print_welcome, print_help)
- [ ] `/skills list` sub-command works
- [ ] `/skills create <name>` sub-command works
- [ ] `/skills create <name> --project` sub-command works
- [ ] `/skills info <name>` sub-command works
- [ ] Help output (`/help`) shows skills section
