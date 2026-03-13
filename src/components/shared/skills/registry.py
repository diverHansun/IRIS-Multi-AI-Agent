"""Singleton registry for loaded skill metadata."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.project.share import IrisShareDir

from .loader import SkillLoader
from .types import BUILT_IN_SKILLS_DIR, SkillLoadError, SkillMetadata, SkillSource, SkillSourceType
from .validator import SkillValidator

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Global singleton for skill metadata cache."""

    _instance: Optional["SkillRegistry"] = None

    def __init__(self) -> None:
        self._loader = SkillLoader()
        self._validator = SkillValidator()
        self._skills: Dict[str, SkillMetadata] = {}
        self._sources: List[SkillSource] = []
        self._load_errors: List[SkillLoadError] = []
        self._initialized = False

    @classmethod
    def get_instance(cls) -> "SkillRegistry":
        """Return singleton instance."""

        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton, mainly for tests."""

        cls._instance = None

    def initialize(self, sources: List[SkillSource]) -> None:
        """Initialize registry with source list and load metadata."""

        self._sources = sorted(sources, key=lambda source: source.priority)
        self._skills.clear()
        self._load_errors.clear()
        self._load_all()
        self._initialized = True

    def reload(self) -> None:
        """Reload all skills from current sources."""

        self._skills.clear()
        self._load_errors.clear()
        self._load_all()

    def is_initialized(self) -> bool:
        """Check whether registry is initialized."""

        return self._initialized

    def get_all_skills(self) -> List[SkillMetadata]:
        """Return loaded skills, sorted by name."""

        return sorted(self._skills.values(), key=lambda skill: skill.name)

    def get_skill(self, name: str) -> Optional[SkillMetadata]:
        """Get one skill by name."""

        return self._skills.get(name)

    def get_skill_content(self, name: str) -> Optional[str]:
        """Read full SKILL.md file content for a loaded skill."""

        skill = self.get_skill(name)
        if skill is None:
            return None
        try:
            return skill.path.read_text(encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to read skill content for '%s': %s", name, exc)
            return None

    def get_load_errors(self) -> List[SkillLoadError]:
        """Return load errors from latest load."""

        return list(self._load_errors)

    @staticmethod
    def resolve_sources(
        *,
        config: Dict[str, Any] | None = None,
        project_skills_dir: Path | None = None,
    ) -> List[SkillSource]:
        """Resolve source roots shared by CLI and middleware."""

        cfg = config or {}
        sources_cfg = cfg.get("sources", {}) if isinstance(cfg, dict) else {}
        sources: List[SkillSource] = []

        if sources_cfg.get("built_in", True) and BUILT_IN_SKILLS_DIR.is_dir():
            sources.append(
                SkillSource(
                    type=SkillSourceType.BUILT_IN,
                    path=BUILT_IN_SKILLS_DIR,
                    priority=0,
                )
            )

        if sources_cfg.get("user", True):
            sources.append(
                SkillSource(
                    type=SkillSourceType.USER,
                    path=IrisShareDir.get_skills_dir(),
                    priority=1,
                )
            )

        if sources_cfg.get("project", True) and project_skills_dir and project_skills_dir.is_dir():
            sources.append(
                SkillSource(
                    type=SkillSourceType.PROJECT,
                    path=project_skills_dir,
                    priority=2,
                )
            )

        return sorted(sources, key=lambda source: source.priority)

    def _load_all(self) -> None:
        for source in self._sources:
            try:
                skills = self._loader.load_from_source(source)
                self._load_errors.extend(self._loader.get_last_errors())

                for skill in skills:
                    is_valid, errors = self._validator.validate_basic(skill)
                    if not is_valid:
                        self._load_errors.append(
                            SkillLoadError(
                                skill_name=skill.name or skill.path.parent.name,
                                source=skill.path,
                                errors=errors,
                            )
                        )
                        continue

                    if skill.name in self._skills:
                        old = self._skills[skill.name]
                        logger.debug(
                            "Skill '%s' from %s shadows skill from %s",
                            skill.name,
                            source.type.value,
                            old.source_type.value,
                        )

                    self._skills[skill.name] = skill
                    logger.debug(
                        "Loaded skill '%s' from %s",
                        skill.name,
                        source.type.value,
                    )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Failed to load skills from %s: %s", source.path, exc)
                self._load_errors.append(
                    SkillLoadError(
                        source=source.path,
                        errors=[str(exc)],
                        severity="error",
                    )
                )

        logger.info(
            "Skill registry initialized: %d skill(s), %d error(s)",
            len(self._skills),
            len(self._load_errors),
        )

