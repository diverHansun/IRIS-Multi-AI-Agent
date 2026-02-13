# Skills System Architecture

> Deep Agent Skill Mechanism - Technical Specification v1.0

## 1. Overview

### 1.1 What is a Skill?

Skill is a self-contained package of **knowledge, workflows, and best practices** that an AI agent can dynamically discover and invoke. Skills follow the [Agent Skills](https://agentskills.io/specification) open standard and are compatible with Claude Code's skill extensions.

**Key distinction:**

| Concept | What it provides | Example |
|---------|-----------------|---------|
| **Tool** | Ability (atomic action) | `read_real_file`, `tavily_search` |
| **MCP** | Connectivity (external access) | GitHub server, database connector |
| **Skill** | Knowledge (workflow guidance) | "How to do code review", "Research methodology" |

### 1.2 Scope

- **Current phase**: Deep mode agent only (via `SkillsMiddleware`)
- **Future phase**: Basic mode agent support (via prompt enhancement)
- **Standard compliance**: Agent Skills Specification + Claude Code extensions

### 1.3 Architecture Position

```
┌─────────────────────────────────────────────────────────────┐
│                    Deep Agent Runtime                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Middleware Pipeline                      │    │
│  │                                                      │    │
│  │  JsonArgsParser                                      │    │
│  │       |                                              │    │
│  │  TodoListMiddleware                                  │    │
│  │       |                                              │    │
│  │  SkillsMiddleware  <- NEW (injects skill knowledge)  │    │
│  │       |                                              │    │
│  │  RealFilesystemMiddleware (agent reads SKILL.md)     │    │
│  │       |                                              │    │
│  │  VirtualFilesystemMiddleware                         │    │
│  │       |                                              │    │
│  │  ShellMiddleware                                     │    │
│  │       |                                              │    │
│  │  SubAgentMiddleware                                  │    │
│  │       |                                              │    │
│  │  SummarizationMiddleware                             │    │
│  │       |                                              │    │
│  │  PatchToolCallsMiddleware                            │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌───────────────────────┐  ┌───────────────────────────┐   │
│  │   Shared Components   │  │   Skill Sources           │   │
│  │                       │  │                           │   │
│  │  SkillLoader          │  │  built-in (lowest)        │   │
│  │  SkillRegistry        │  │  ~/.iris/skills/ (user)   │   │
│  │  SkillValidator       │  │  .iris/skills/ (project)  │   │
│  │  SkillMetadata        │  │                           │   │
│  └───────────────────────┘  └───────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Directory Layout

### 2.1 Skill Sources (Priority: low -> high)

Following Claude Code convention, adapted to our `.iris` project structure:

| Level | Path | Scope | Priority |
|-------|------|-------|----------|
| **Built-in** | `src/components/shared/skills/built_in_skills/` | All users, all projects | 0 (lowest) |
| **User** | `~/.iris/skills/` | Current user, all projects | 1 |
| **Project** | `<project_root>/.iris/skills/` | Current project only | 2 (highest) |

**Precedence rule**: When skills share the same name, higher-priority source wins (last-one-wins).

### 2.2 Skill Package Structure

Each skill is a directory containing at minimum a `SKILL.md` file:

```
my-skill/
├── SKILL.md           # Required: metadata + instructions
├── scripts/           # Optional: executable scripts (Python, Bash)
├── references/        # Optional: documentation loaded on demand
└── assets/            # Optional: static resources (templates, data)
```

### 2.3 Code Layout

```
src/components/
├── shared/
│   └── skills/                          # Shared infrastructure
│       ├── __init__.py                  # Public API exports
│       ├── types.py                     # SkillMetadata, SkillSource, constants
│       ├── loader.py                    # SKILL.md discovery & parsing
│       ├── registry.py                  # SkillRegistry (singleton, caching)
│       ├── validator.py                 # Validation logic (name, format, deps)
│       ├── formatter.py                 # System prompt formatting
│       └── built_in_skills/             # Built-in skills
│           └── skill-creator/
│               └── SKILL.md
│
└── deepagents/
    └── runtime_middlewares/
        └── skills/                      # Deep mode integration
            ├── __init__.py
            └── middleware.py             # SkillsMiddleware(AgentMiddleware)

config/agents/deep/middleware/
└── skills/
    ├── skills.json                      # Main configuration
    └── skills.example.json              # Example configuration

src/core/project/
└── share.py                             # Extend IrisShareDir with skills paths
```

---

## 3. Core Design Decisions

### 3.1 Independent SkillProvider (NOT ToolProvider)

Skills are **not** tools. They have fundamentally different interfaces and lifecycles:

```
ToolProvider:
  initialize() -> get_tools() -> List[BaseTool]  (tools always available)

SkillProvider:
  load_metadata() -> inject_to_prompt() -> agent_reads_on_demand()
```

**Rationale**:
- `ToolProvider.get_tools()` returns `List[BaseTool]`, but skills are not `BaseTool`
- Tool lifecycle: always-loaded, directly callable
- Skill lifecycle: metadata-loaded -> prompt-injected -> on-demand-read
- Mixing them violates Interface Segregation Principle (ISP)

### 3.2 Hybrid Loading Strategy

```
                 ┌──────────────────┐
                 │   Application    │
                 │     Startup      │
                 └────────┬─────────┘
                          │
                 ┌────────v─────────┐
                 │  SkillRegistry   │
                 │  .get_instance() │
                 │                  │
                 │  Scan all source │
                 │  directories     │
                 │                  │
                 │  Parse YAML      │
                 │  frontmatter     │
                 │                  │
                 │  Cache metadata  │
                 │  (name + desc)   │
                 └────────┬─────────┘
                          │
              ┌───────────v───────────┐
              │  Agent Creation       │
              │                       │
              │  SkillsMiddleware     │
              │  reads cached metadata│
              │  from registry        │
              │                       │
              │  Injects skill list   │
              │  into system prompt   │
              └───────────┬───────────┘
                          │
              ┌───────────v───────────┐
              │  Runtime (on-demand)  │
              │                       │
              │  LLM decides to       │
              │  use a skill          │
              │       |               │
              │  read_real_file()     │
              │  reads full SKILL.md  │
              │       |               │
              │  LLM follows skill    │
              │  instructions         │
              └───────────────────────┘
```

**Why Hybrid?**
- **Eager** metadata loading: avoids repeated filesystem I/O per agent turn
- **Lazy** content reading: full SKILL.md loaded only when agent actually needs it
- **Manual reload**: CLI `skills reload` for hot-update without restart

### 3.3 Progressive Disclosure (3 Levels)

| Level | What | When | Token Cost |
|-------|------|------|------------|
| **L1: Metadata** | `name` + `description` | Always in system prompt | ~50 tokens/skill |
| **L2: Instructions** | Full SKILL.md body | Agent reads via `read_real_file` | ~500-2000 tokens |
| **L3: Resources** | scripts/, references/, assets/ | Agent accesses on-demand | Variable |

### 3.4 read_real_file Integration

Skills are read using the **existing** `read_real_file` tool. No new tool is needed.

**Security consideration**: `read_real_file` validates paths against `allowed_paths` in `real_filesystem.json`. Skill directories outside `${PROJECT_ROOT}` (e.g., `~/.iris/skills/`, built-in skills) must be whitelisted.

**Solution**: `SkillsMiddleware.before_agent()` dynamically extends the `RealFilesystemMiddleware`'s `allowed_paths` to include skill source directories. See [Section 5.4](#54-security-path-whitelisting).

### 3.5 User-Level / Project-Level Design

Following the existing `ProjectContext` + `IrisShareDir` pattern in `src/core/project/`:

**User-level skills** (`~/.iris/skills/`):
- Managed by `IrisShareDir` (extend with `get_skills_dir()`)
- Shared across all projects for the current user
- Created via `cli.py skills create <name>`

**Project-level skills** (`<project>/.iris/skills/`):
- Managed by `ProjectContext` (extend with `skills_dir` property)
- Scoped to the current project only
- Created via `cli.py skills create <name> --project`
- Detected via `detect_project_root()` -> `.iris/skills/`

**Built-in skills** (`src/components/shared/skills/built_in_skills/`):
- Bundled with the application
- Lowest priority (overridable by user/project skills)
- Read-only (users cannot modify)

---

## 4. Data Model

### 4.1 SkillMetadata

```python
# src/components/shared/skills/types.py

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from enum import Enum


class SkillSourceType(Enum):
    BUILT_IN = "built-in"
    USER = "user"
    PROJECT = "project"


@dataclass(frozen=True)
class SkillSource:
    """Represents a skill source directory."""
    type: SkillSourceType
    path: Path
    priority: int  # 0=lowest


@dataclass
class SkillMetadata:
    """
    Parsed metadata from a SKILL.md file.

    Follows Agent Skills Specification required fields
    plus Claude Code extension fields.
    """
    # --- Agent Skills Spec (required) ---
    name: str                              # Max 64 chars, lowercase + hyphens
    description: str                       # Max 1024 chars

    # --- Agent Skills Spec (optional) ---
    license: Optional[str] = None
    compatibility: Optional[str] = None    # Max 500 chars
    metadata: Dict[str, str] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)

    # --- Claude Code extensions ---
    user_invocable: bool = True            # Show in /skill menu
    disable_model_invocation: bool = False # Prevent auto-loading
    argument_hint: Optional[str] = None    # e.g., "[topic]"
    context: Optional[str] = None          # "fork" for subagent execution
    agent: Optional[str] = None            # Subagent type when context=fork

    # --- Internal fields ---
    path: Path = field(default_factory=lambda: Path("."))  # Absolute path to SKILL.md
    source_type: SkillSourceType = SkillSourceType.BUILT_IN
    source_path: Path = field(default_factory=lambda: Path("."))  # Source directory


# --- Constants ---
MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024
MAX_SKILL_COMPATIBILITY_LENGTH = 500
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
SKILL_FILENAME = "SKILL.md"

# Name validation pattern: lowercase alphanumeric + hyphens
# Must not start/end with hyphen, no consecutive hyphens
SKILL_NAME_PATTERN = r'^[a-z0-9]([a-z0-9]*(-[a-z0-9]+)*)?$'

# Built-in skills directory (resolved from package location)
# CLI and Middleware both import from here — avoid hardcoding.
BUILT_IN_SKILLS_DIR = Path(__file__).resolve().parent / "built_in_skills"
```

### 4.2 SKILL.md Format

```yaml
---
# === Agent Skills Spec (required) ===
name: my-skill                          # Unique identifier
description: >
  What this skill does and when to use it.
  Include keywords for agent matching.

# === Agent Skills Spec (optional) ===
license: MIT
compatibility: Python 3.8+, requires tavily_search tool
metadata:
  author: your-team
  version: "1.0.0"
  category: research
allowed-tools: read_real_file grep_real_files

# === Claude Code Extensions ===
user-invocable: true                    # Default: true
disable-model-invocation: false         # Default: false
argument-hint: "[search-query]"
# context: fork                         # Uncomment for subagent execution
# agent: general-purpose                # Subagent type
---

# My Skill Instructions

Step-by-step workflow instructions in Markdown.
Keep under 500 lines. Move detailed reference material to references/ directory.
```

### 4.3 Configuration Schema

```jsonc
// config/agents/deep/middleware/skills/skills.json
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

---

## 5. Component Design

### 5.1 SkillLoader

**Responsibility**: Discover and parse SKILL.md files from source directories.

```python
# src/components/shared/skills/loader.py

class SkillLoader:
    """
    Discovers and parses SKILL.md files from skill source directories.

    Follows SRP: only responsible for I/O and parsing.
    Validation is delegated to SkillValidator.
    """

    def load_from_source(self, source: SkillSource) -> List[SkillMetadata]:
        """
        Scan a source directory and parse all valid skills.

        Steps:
        1. List subdirectories in source.path
        2. For each subdirectory, check for SKILL.md
        3. Parse YAML frontmatter
        4. Return list of SkillMetadata (invalid skills are skipped with warning)
        """
        ...

    def load_from_sources(self, sources: List[SkillSource]) -> Dict[str, SkillMetadata]:
        """
        Load skills from multiple sources with precedence resolution.

        Last-one-wins: skills from higher-priority sources override
        same-name skills from lower-priority sources.
        """
        ...

    @staticmethod
    def parse_skill_md(content: str, skill_path: Path, directory_name: str) -> Optional[SkillMetadata]:
        """
        Parse a SKILL.md file content into SkillMetadata.

        Steps:
        1. Check file size (skip if > MAX_SKILL_FILE_SIZE)
        2. Extract YAML frontmatter between --- delimiters
        3. Parse YAML with safe_load
        4. Validate required fields (name, description)
        5. Map optional fields with defaults
        6. Return SkillMetadata or None on error
        """
        ...
```

### 5.2 SkillRegistry

**Responsibility**: Global singleton managing all loaded skills with caching.

```python
# src/components/shared/skills/registry.py

class SkillRegistry:
    """
    Singleton registry for managing loaded skills.

    Follows the Hybrid loading strategy:
    - Pre-loads all metadata at initialization
    - Provides cached access for middleware
    - Supports manual reload for hot-update

    Usage:
        registry = SkillRegistry.get_instance()
        skills = registry.get_all_skills()
        skill = registry.get_skill("web-research")
    """

    _instance: Optional[SkillRegistry] = None

    def __init__(self):
        self._loader = SkillLoader()
        self._validator = SkillValidator()
        self._skills: Dict[str, SkillMetadata] = {}
        self._sources: List[SkillSource] = []
        self._load_errors: List[SkillLoadError] = []
        self._initialized = False

    @classmethod
    def get_instance(cls) -> SkillRegistry:
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    def initialize(self, sources: List[SkillSource]) -> None:
        """
        Initialize registry with given sources.
        Loads all skill metadata into cache.
        """
        self._sources = sorted(sources, key=lambda s: s.priority)
        self._load_all()
        self._initialized = True

    def reload(self) -> None:
        """
        Reload all skills from configured sources.
        Used for hot-update via CLI command.
        """
        self._skills.clear()
        self._load_errors.clear()
        self._load_all()

    def is_initialized(self) -> bool:
        """Check whether the registry has been initialized."""
        return self._initialized

    def get_all_skills(self) -> List[SkillMetadata]:
        """Return all loaded skills (deduplicated by precedence)."""
        ...

    def get_skill(self, name: str) -> Optional[SkillMetadata]:
        """Get a skill by name."""
        return self._skills.get(name)

    def get_skill_content(self, name: str) -> Optional[str]:
        """Read full SKILL.md content for a skill (L2 loading)."""
        ...

    def get_load_errors(self) -> List[SkillLoadError]:
        """Return errors from last load operation."""
        return list(self._load_errors)

    @staticmethod
    def resolve_sources(
        *,
        config: Dict[str, Any] | None = None,
        project_skills_dir: Path | None = None,
    ) -> List[SkillSource]:
        """
        Unified source resolution — shared by CLI and Middleware.

        Args:
            config: skills config dict (contains sources.built_in/user/project switches)
            project_skills_dir: project-level skills dir (None when no project context)

        Returns:
            SkillSource list sorted by ascending priority.
        """
        from .types import BUILT_IN_SKILLS_DIR, SkillSource, SkillSourceType
        from src.core.project.share import IrisShareDir

        cfg = config or {}
        sources_cfg = cfg.get("sources", {})
        sources: List[SkillSource] = []

        if sources_cfg.get("built_in", True) and BUILT_IN_SKILLS_DIR.is_dir():
            sources.append(SkillSource(
                type=SkillSourceType.BUILT_IN,
                path=BUILT_IN_SKILLS_DIR,
                priority=0,
            ))

        if sources_cfg.get("user", True):
            sources.append(SkillSource(
                type=SkillSourceType.USER,
                path=IrisShareDir.get_skills_dir(),
                priority=1,
            ))

        if sources_cfg.get("project", True) and project_skills_dir and project_skills_dir.is_dir():
            sources.append(SkillSource(
                type=SkillSourceType.PROJECT,
                path=project_skills_dir,
                priority=2,
            ))

        return sources

    def _load_all(self) -> None:
        """Internal: load skills from all sources with precedence."""
        for source in self._sources:
            try:
                skills = self._loader.load_from_source(source)
                for skill in skills:
                    is_valid, errors = self._validator.validate_basic(skill)
                    if is_valid:
                        if skill.name in self._skills:
                            old = self._skills[skill.name]
                            logger.warning(
                                "Skill '%s' from %s shadows skill from %s",
                                skill.name, source.type.value, old.source_type.value
                            )
                        self._skills[skill.name] = skill
                    else:
                        self._load_errors.append(
                            SkillLoadError(skill_name=skill.name, errors=errors)
                        )
            except Exception as e:
                logger.error("Failed to load skills from %s: %s", source.path, e)
                self._load_errors.append(
                    SkillLoadError(source=source.path, errors=[str(e)])
                )
```

### 5.3 SkillsMiddleware

**Responsibility**: Integrate skills into the Deep Agent middleware pipeline.

```python
# src/components/deepagents/runtime_middlewares/skills/middleware.py

class SkillsMiddleware(AgentMiddleware):
    """
    Middleware that injects skill knowledge into the agent's system prompt.

    Lifecycle:
    1. before_agent(): Load skill metadata from registry, resolve paths
    2. wrap_model_call(): Inject skill list into system prompt
    3. Agent uses read_real_file to read full SKILL.md when needed

    Position in pipeline: After TodoList, before Filesystem.
    """

    def __init__(
        self,
        *,
        config: Dict[str, Any] | None = None,
        sources: List[SkillSource] | None = None,
        registry: SkillRegistry | None = None,
    ) -> None:
        super().__init__()
        self._config = self._load_config(config)
        self._sources = sources  # Pre-computed by Factory via resolve_sources()
        self._registry = registry
        self._formatter = SkillPromptFormatter()

    def before_agent(self, state, runtime) -> Dict[str, Any] | None:
        """
        Initialize skill registry if not already done.

        NOTE: Skill source paths are computed by the Factory at
        creation time (via SkillRegistry.resolve_sources()) and
        passed to this middleware as the `sources` parameter.
        The Factory also extends RealFilesystem allowed_paths
        directly — this middleware does NOT touch path whitelists.
        """
        if self._registry is None:
            self._registry = SkillRegistry.get_instance()
            if not self._registry.is_initialized() and self._sources:
                self._registry.initialize(self._sources)

        return None

    def wrap_model_call(self, request: ModelRequest, handler) -> ModelResponse:
        """Inject skill list into system prompt."""
        if self._registry and self._config.get("enabled", True):
            skills = self._registry.get_all_skills()
            if skills:
                skill_prompt = self._formatter.format(skills)
                if request.system_prompt:
                    request.system_prompt = f"{request.system_prompt}\n\n{skill_prompt}"
                else:
                    request.system_prompt = skill_prompt
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler):
        """Async version of wrap_model_call."""
        if self._registry and self._config.get("enabled", True):
            skills = self._registry.get_all_skills()
            if skills:
                skill_prompt = self._formatter.format(skills)
                if request.system_prompt:
                    request.system_prompt = f"{request.system_prompt}\n\n{skill_prompt}"
                else:
                    request.system_prompt = skill_prompt
        return await handler(request)

    @staticmethod
    def _load_config(config: Dict[str, Any] | None) -> Dict[str, Any]:
        """Load config from dict or file."""
        ...
```

### 5.4 Security: Path Whitelisting

**Problem**: `read_real_file` validates against `allowed_paths` (default: `${PROJECT_ROOT}` only). User-level skills at `~/.iris/skills/` and built-in skills are outside the project root.

**Critical constraint**:
- `RealFilesystemSecurityOptions.allowed_paths` is `tuple[Path, ...]`（`@dataclass(slots=True)`）— **cannot** `.append()`, must rebuild tuple.
- `validate_file()`（read）and `validate_new_file_path()`（write）both go through `ensure_directory_access()` → `_is_within(allowed_paths)`. Adding a directory to `allowed_paths` enables both read **and** write.

**Solution**: The **factory** coordinates path whitelisting with **write protection** for built-in skills:

```python
# BaseDeepAgentFactory._extend_filesystem_for_skills()

def _extend_filesystem_for_skills(
    self,
    skill_source_paths: List[Path],
    filesystem_middlewares: List[AgentMiddleware],
) -> None:
    """
    Extend RealFilesystemMiddleware allowed_paths with skill sources,
    and add built-in skills dir to excluded_paths (write-protect).
    """
    from src.components.shared.skills.types import BUILT_IN_SKILLS_DIR

    for mw in filesystem_middlewares:
        if isinstance(mw, RealFilesystemMiddleware):
            sec = mw.options.security

            # 1. Rebuild allowed_paths (tuple — cannot append)
            existing = sec.allowed_paths
            new_paths = tuple(
                p for p in skill_source_paths
                if p.exists() and p not in existing
            )
            if new_paths:
                sec.allowed_paths = existing + new_paths

            # 2. Write-protect built-in skills dir via excluded_paths
            if BUILT_IN_SKILLS_DIR.exists() and BUILT_IN_SKILLS_DIR not in sec.excluded_paths:
                sec.excluded_paths = sec.excluded_paths + (BUILT_IN_SKILLS_DIR,)

            break
```

**Access matrix after whitelisting**:

| Skill source | read (`read_real_file`) | write (`write_real_file`) |
|-------------|------------------------|---------------------------|
| built-in | ✅ via `allowed_paths` | ❌ blocked via `excluded_paths` |
| user `~/.iris/skills/` | ✅ | ✅ (user may edit own skills) |
| project `.iris/skills/` | ✅ | ✅ (user may edit own skills) |

**Why factory-level coordination?**
- Middlewares don't communicate directly (SRP)
- Factory is the natural composition point — paths are known before `before_agent()`
- `SkillRegistry.resolve_sources()` computes paths; Factory passes them to both SkillsMiddleware and Filesystem
- No runtime overhead

---

## 6. System Prompt Injection

### 6.1 Format: Simple List

```python
# src/components/shared/skills/formatter.py

class SkillPromptFormatter:
    """Format skill metadata for system prompt injection."""

    def format(self, skills: List[SkillMetadata], max_skills: int = 20) -> str:
        """
        Format skills as simple list for system prompt.
        Optimized for minimal token usage.

        Args:
            skills: All available skills.
            max_skills: Maximum number of skills to include in prompt.
                        Controlled by config `prompt.max_skills_in_prompt`.
        """
        if not skills:
            return ""

        display_skills = skills[:max_skills]

        lines = ["## Available Skills", ""]
        lines.append(
            "You have access to specialized skills. "
            "To activate a skill, use read_real_file to read its SKILL.md."
        )
        lines.append("")

        for skill in display_skills:
            path_str = str(skill.path)
            lines.append(f"- {skill.name}: {skill.description}")
            lines.append(f"  Path: {path_str}")

        if len(skills) > max_skills:
            lines.append(f"\n(showing {max_skills} of {len(skills)} skills)")

        lines.append("")
        lines.append(
            "Only read a skill's SKILL.md when the user's task "
            "matches the skill's description."
        )

        return "\n".join(lines)
```

**Example output** (~150 tokens for 2 skills):

```markdown
## Available Skills

You have access to specialized skills. To activate a skill, use read_real_file to read its SKILL.md.

- skill-creator: Guide for creating new skills with proper structure and validation
  Path: /path/to/built_in_skills/skill-creator/SKILL.md
- web-research: Conduct thorough web research with structured methodology
  Path: /home/user/.iris/skills/web-research/SKILL.md

Only read a skill's SKILL.md when the user's task matches the skill's description.
```

---

## 7. Integration with Project Module

### 7.1 Extend IrisShareDir

```python
# src/core/project/share.py - Add to IrisShareDir class

@classmethod
def get_skills_dir(cls) -> Path:
    """Get user-level skills directory (~/.iris/skills/)."""
    skills_dir = cls.get_share_dir() / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir
```

Updated `~/.iris/` structure:

```
~/.iris/
├── config.toml
├── .env
├── llm/
├── agents/
├── tools/
├── skills/                    # NEW: user-level skills
│   ├── web-research/
│   │   └── SKILL.md
│   └── code-review/
│       └── SKILL.md
├── sessions/
└── metadata.json
```

### 7.2 Extend ProjectContext

```python
# src/core/project/context.py - Add to ProjectContext class

@property
def skills_dir(self) -> Path:
    """Project-level skills directory (<project>/.iris/skills/)."""
    return self.iris_dir / "skills"

def ensure_structure(self) -> None:
    """Create .iris and session subdirectories if missing."""
    for mode in ("llm", "basicagent", "deepagent"):
        (self.iris_dir / "sessions" / mode).mkdir(parents=True, exist_ok=True)
    # NOTE: Do NOT auto-create skills directory here.
    # The skills_dir property returns the path but does not guarantee existence.
    # The directory is created on-demand only when the user explicitly
    # runs `/skills create <name> --project`.
```

Updated `<project>/.iris/` structure:

```
<project>/.iris/
├── config.json
├── agent.md
├── skills/                    # NEW: project-level skills
│   └── custom-workflow/
│       └── SKILL.md
└── sessions/
    ├── llm/
    ├── basicagent/
    └── deepagent/
```

---

## 8. Error Handling Strategy

### 8.1 Graceful Loading, Strict Validation

**Principle**: A single broken skill must NEVER prevent the system from functioning. All other skills and the agent itself must continue to work normally.

```
Load Phase:
  skill-a/ -> parse OK -> validate OK -> [loaded]
  skill-b/ -> parse FAIL (bad YAML) -> [warn, skip]
  skill-c/ -> parse OK -> validate FAIL (bad name) -> [warn, skip]
  skill-d/ -> parse OK -> validate OK -> [loaded]

  Result: 2 skills loaded, 2 warnings logged
  Agent: runs normally with skill-a and skill-d
```

### 8.2 Error Categories

| Error | Severity | Action | User Impact |
|-------|----------|--------|-------------|
| Invalid YAML frontmatter | Warning | Skip skill, log error | Skill unavailable |
| Missing required field | Warning | Skip skill, log error | Skill unavailable |
| Invalid name format | Warning | Load with warning | Skill works, lint warning |
| File > 10MB | Warning | Skip skill, log error | Skill unavailable |
| Directory inaccessible | Error | Skip directory, log error | All skills from that source unavailable |
| All sources fail | Error | Agent runs without skills | No skill support |
| read_real_file fails at runtime | Info | LLM receives error message | LLM adapts without skill |

### 8.3 Error Reporting

```python
@dataclass
class SkillLoadError:
    """Records a skill loading error for reporting."""
    skill_name: Optional[str] = None
    source: Optional[Path] = None
    errors: List[str] = field(default_factory=list)
    severity: str = "warning"  # "warning" | "error"

    @property
    def path(self) -> Optional[Path]:
        """Alias for source — used by CLI display."""
        return self.source

    @property
    def message(self) -> str:
        """Joined error messages — used by CLI display."""
        return "; ".join(self.errors)
```

Errors are collected during loading and available via:
- `SkillRegistry.get_load_errors()` - programmatic access
- `cli.py skills list` - displays warnings inline
- `cli.py skills validate --all` - dedicated validation report *(Phase 4)*

---

## 9. Validation Rules

### 9.1 Name Validation (Agent Skills Spec)

```
Rules:
- 1-64 characters
- Lowercase alphanumeric and hyphens only: [a-z0-9-]
- Must NOT start or end with hyphen
- Must NOT contain consecutive hyphens (--)
- Must match parent directory name

Valid:   web-research, skill-creator, my-tool-v2
Invalid: Web-Research, _private, my--skill, -start, end-
```

### 9.2 Metadata Validation

```
Required:
  - name: non-empty, valid format
  - description: non-empty

Truncated if exceeding limits:
  - description: max 1024 chars
  - compatibility: max 500 chars

Type-checked:
  - metadata: must be Dict[str, str]
  - allowed-tools: space-delimited string -> List[str]
  - user-invocable: boolean (default: true)
  - disable-model-invocation: boolean (default: false)
```

---

## 10. Configuration

### 10.1 File Location

```
config/agents/deep/middleware/skills/
├── skills.json              # Active configuration
└── skills.example.json      # Example with comments
```

### 10.2 Full Configuration Schema

```jsonc
// config/agents/deep/middleware/skills/skills.json
{
  // Master switch
  "enabled": true,

  // Source control
  "sources": {
    "built_in": true,          // Load built-in skills
    "user": true,              // Load from ~/.iris/skills/
    "project": true            // Load from <project>/.iris/skills/
  },

  // System prompt injection
  "prompt": {
    "format": "simple",        // "simple" (name + desc + path)
    "max_skills_in_prompt": 20 // Limit skills injected into prompt
  },

  // Validation settings
  "validation": {
    "strict_name_check": true,     // Enforce Agent Skills naming rules
    "warn_on_missing_description": true
  }
}
```

### 10.3 Example Configuration

```jsonc
// config/agents/deep/middleware/skills/skills.example.json
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

---

## 11. Runtime Flow

### 11.1 Agent Creation

```
1. Factory loads skills config from config/agents/deep/middleware/skills/skills.json
2. Factory calls SkillRegistry.resolve_sources(config, project_skills_dir)
   → returns [SkillSource(built-in, 0), SkillSource(user, 1), SkillSource(project, 2)]
3. Factory calls _extend_filesystem_for_skills(source_paths, filesystem_middlewares)
   a. Rebuilds allowed_paths tuple: existing + new_paths
   b. Adds BUILT_IN_SKILLS_DIR to excluded_paths (write-protect)
4. Factory creates SkillsMiddleware(config=skills_config, sources=sources)
5. create_deep_agent_runtime(skills_middleware=skills_middleware)
6. SkillsMiddleware.before_agent() initializes registry with pre-computed sources
```

### 11.2 Agent Turn (per LLM call)

```
1. User sends message
2. Middleware pipeline processes:
   a. JsonArgsParser: fix arguments
   b. TodoList: manage tasks
   c. SkillsMiddleware.wrap_model_call():
      - Get all skills from registry (cached)
      - Format skill list (name + description + path)
      - Append to system prompt
   d. RealFilesystem: provide file tools
   e. ... other middlewares
3. LLM receives system prompt with skill list
4. LLM decides:
   - Task matches "skill-creator" description?
     -> Call read_real_file("/.../skill-creator/SKILL.md")
     -> Follow skill instructions
   - Task doesn't match any skill?
     -> Proceed normally without using skills
5. Response returned to user
```

### 11.3 Skill Creation (via CLI)

```
1. User runs: cli.py skills create web-research
2. CLI resolves target directory: ~/.iris/skills/web-research/
3. CLI validates:
   a. Name format (Agent Skills spec)
   b. No path traversal
   c. Directory doesn't already exist
4. CLI creates:
   a. ~/.iris/skills/web-research/ (directory)
   b. ~/.iris/skills/web-research/SKILL.md (from template)
5. User edits SKILL.md to add instructions
6. Next agent session automatically discovers the new skill
```

---

## 12. Built-in Skill: skill-creator

### 12.1 Location

```
src/components/shared/skills/built_in_skills/skill-creator/SKILL.md
```

### 12.2 Purpose

Teaches the agent how to create new skills following the Agent Skills specification. This is a meta-skill: a skill about creating skills.

### 12.3 Content Outline

```yaml
---
name: skill-creator
description: >
  Guide for creating new skills with proper SKILL.md structure,
  naming conventions, and best practices. Use when user asks to
  create a custom skill or workflow.
metadata:
  author: iris-team
  version: "1.0.0"
  category: meta
allowed-tools: read_real_file write_real_file list_real_files
---
```

Body includes:
1. Skill structure requirements (SKILL.md format, directories)
2. Naming rules (Agent Skills spec)
3. YAML frontmatter reference
4. Best practices (concise context, progressive disclosure)
5. Validation checklist
6. Example skill templates

---

## 13. Implementation Phases

### Phase 1: MVP (Core Infrastructure)

| Task | Location | Description |
|------|----------|-------------|
| 1.1 | `src/components/shared/skills/types.py` | Data models and constants |
| 1.2 | `src/components/shared/skills/validator.py` | Name and metadata validation |
| 1.3 | `src/components/shared/skills/loader.py` | SKILL.md discovery and parsing |
| 1.4 | `src/components/shared/skills/registry.py` | Singleton registry with caching |
| 1.5 | `src/components/shared/skills/formatter.py` | System prompt formatting |
| 1.6 | `src/components/shared/skills/__init__.py` | Public API exports |
| 1.7 | `src/components/deepagents/runtime_middlewares/skills/middleware.py` | SkillsMiddleware |
| 1.8 | `src/core/project/share.py` | Extend IrisShareDir with skills dir |
| 1.9 | `src/core/project/context.py` | Extend ProjectContext with skills dir |
| 1.10 | `config/agents/deep/middleware/skills/` | Configuration files |

### Phase 2: Built-in Skill + Factory Integration

| Task | Location | Description |
|------|----------|-------------|
| 2.1 | `src/components/shared/skills/built_in_skills/skill-creator/SKILL.md` | Built-in skill-creator |
| 2.2 | `src/agents/deepagents/factories/` | Integrate SkillsMiddleware into factories |
| 2.3 | `src/components/deepagents/runtime.py` | Add SkillsMiddleware to pipeline |
| 2.4 | Security integration | Extend allowed_paths for skill directories |

### Phase 3: CLI Commands

| Task | Description |
|------|-------------|
| 3.1 | `/skills list` - List all available skills with source info |
| 3.2 | `/skills create <name>` - Create new skill from template |
| 3.3 | `/skills info <name>` - Display skill details |

### Phase 4: Advanced Features (Future)

| Task | Description |
|------|-------------|
| 4.1 | `/skills validate [--all]` - Validate skill format |
| 4.2 | `/skills reload` - Reload skills without restart |
| 4.3 | `context: fork` support (skill runs as subagent) |
| 4.4 | `allowed-tools` enforcement |
| 4.5 | Skill dependency checking (`requires_tools`, `requires_mcp`) |
| 4.6 | Basic mode integration |

---

## 14. Testing Strategy

### 14.1 Unit Tests

```
tests/unit/components/shared/skills/
├── test_types.py           # SkillMetadata creation and validation
├── test_loader.py          # SKILL.md parsing, frontmatter extraction
├── test_registry.py        # Singleton, caching, precedence resolution
├── test_validator.py       # Name validation, metadata validation
└── test_formatter.py       # System prompt formatting

tests/unit/components/deepagents/runtime_middlewares/skills/
└── test_middleware.py       # SkillsMiddleware lifecycle
```

### 14.2 Integration Tests

```
tests/integration/skills/
├── test_skill_discovery.py     # Full discovery from multiple sources
├── test_skill_in_prompt.py     # Skill appears in system prompt
└── test_skill_read.py          # Agent can read SKILL.md via read_real_file
```

### 14.3 Test Fixtures

```
tests/fixtures/skills/
├── valid-skill/
│   └── SKILL.md                # Well-formed skill
├── invalid-name/
│   └── SKILL.md                # Invalid name for testing validation
├── missing-description/
│   └── SKILL.md                # Missing required field
└── oversized/
    └── SKILL.md                # > MAX_SKILL_FILE_SIZE
```
