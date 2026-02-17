"""Types and constants for the skills system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class SkillSourceType(Enum):
    """Available source types for skills."""

    BUILT_IN = "built-in"
    USER = "user"
    PROJECT = "project"


@dataclass(frozen=True)
class SkillSource:
    """Represents a skill source directory."""

    type: SkillSourceType
    path: Path
    priority: int


@dataclass
class SkillResources:
    """Discovered resource files bundled with a skill."""

    scripts: List[Path] = field(default_factory=list)
    references: List[Path] = field(default_factory=list)
    assets: List[Path] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        """Return True when at least one resource bucket is non-empty."""

        return bool(self.scripts or self.references or self.assets)


@dataclass
class SkillMetadata:
    """Parsed metadata from a SKILL.md file."""

    # Agent Skills Spec (required)
    name: str
    description: str

    # Agent Skills Spec (optional)
    license: Optional[str] = None
    compatibility: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    allowed_tools: List[str] = field(default_factory=list)

    # Internal fields
    path: Path = field(default_factory=lambda: Path("."))
    source_type: SkillSourceType = SkillSourceType.BUILT_IN
    source_path: Path = field(default_factory=lambda: Path("."))
    resources: SkillResources = field(default_factory=SkillResources)


@dataclass
class SkillLoadError:
    """Records a skill loading error for reporting."""

    skill_name: Optional[str] = None
    source: Optional[Path] = None
    errors: List[str] = field(default_factory=list)
    severity: str = "warning"

    @property
    def path(self) -> Optional[Path]:
        """Alias for source, used by CLI display."""

        return self.source

    @property
    def message(self) -> str:
        """Joined error messages, used by CLI display."""

        return "; ".join(self.errors)


MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024
MAX_SKILL_COMPATIBILITY_LENGTH = 500
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024
SKILL_FILENAME = "SKILL.md"
SKILL_NAME_PATTERN = r"^[a-z0-9]([a-z0-9]*(-[a-z0-9]+)*)?$"
ANTHROPIC_FRONTMATTER_FIELDS = frozenset(
    {
        "name",
        "description",
        "license",
        "compatibility",
        "metadata",
        "allowed-tools",
    }
)

# CLI and middleware both import from here to avoid hard-coded paths.
BUILT_IN_SKILLS_DIR = Path(__file__).resolve().parent / "built_in_skills"
