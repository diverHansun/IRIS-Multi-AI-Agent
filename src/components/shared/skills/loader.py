"""Skill discovery and SKILL.md parsing."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml

from .types import (
    ANTHROPIC_FRONTMATTER_FIELDS,
    MAX_SKILL_FILE_SIZE,
    SKILL_FILENAME,
    SkillLoadError,
    SkillMetadata,
    SkillResources,
    SkillSource,
)

logger = logging.getLogger(__name__)

_FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_RESOURCE_DIRS = {
    "scripts": ("scripts",),
    "references": ("references", "reference"),
    "assets": ("assets",),
}


class SkillLoader:
    """Discover and parse skills from configured source directories."""

    def __init__(self) -> None:
        self._last_errors: List[SkillLoadError] = []

    def get_last_errors(self) -> List[SkillLoadError]:
        """Return load errors from the most recent source scan."""

        return list(self._last_errors)

    def load_from_source(self, source: SkillSource) -> List[SkillMetadata]:
        """Scan one source directory and parse valid skills."""

        self._last_errors.clear()
        skills: List[SkillMetadata] = []

        if not source.path.exists():
            logger.debug("Skill source does not exist, skipping: %s", source.path)
            return skills

        if not source.path.is_dir():
            raise NotADirectoryError(f"Skill source is not a directory: {source.path}")

        for skill_dir in sorted(source.path.iterdir(), key=lambda item: item.name):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / SKILL_FILENAME
            if not skill_file.is_file():
                continue

            try:
                if skill_file.stat().st_size > MAX_SKILL_FILE_SIZE:
                    self._last_errors.append(
                        SkillLoadError(
                            skill_name=skill_dir.name,
                            source=skill_file,
                            errors=[f"SKILL.md exceeds max size {MAX_SKILL_FILE_SIZE} bytes"],
                        )
                    )
                    continue
            except OSError as exc:
                self._last_errors.append(
                    SkillLoadError(
                        skill_name=skill_dir.name,
                        source=skill_file,
                        errors=[f"failed to inspect file: {exc}"],
                    )
                )
                continue

            try:
                content = skill_file.read_text(encoding="utf-8")
            except Exception as exc:  # pylint: disable=broad-except
                self._last_errors.append(
                    SkillLoadError(
                        skill_name=skill_dir.name,
                        source=skill_file,
                        errors=[f"failed to read SKILL.md: {exc}"],
                    )
                )
                continue

            skill, errors = self._parse_with_errors(content, skill_file, skill_dir.name)
            if skill is None:
                self._last_errors.append(
                    SkillLoadError(
                        skill_name=skill_dir.name,
                        source=skill_file,
                        errors=errors or ["failed to parse SKILL.md"],
                    )
                )
                continue

            skill.resources = self._scan_resources(skill_dir)
            skill.source_type = source.type
            skill.source_path = source.path
            skills.append(skill)

        return skills

    @staticmethod
    def parse_skill_md(content: str, skill_path: Path, directory_name: str) -> Optional[SkillMetadata]:
        """Parse SKILL.md content into SkillMetadata, returning None on error."""

        skill, _ = SkillLoader()._parse_with_errors(content, skill_path, directory_name)
        return skill

    def _parse_with_errors(
        self,
        content: str,
        skill_path: Path,
        _directory_name: str,
    ) -> Tuple[Optional[SkillMetadata], List[str]]:
        normalized = content.replace("\r\n", "\n")
        match = _FRONTMATTER_PATTERN.search(normalized)
        if not match:
            return None, ["missing YAML frontmatter delimited by ---"]

        frontmatter_raw = match.group(1)
        try:
            frontmatter = yaml.safe_load(frontmatter_raw) or {}
        except yaml.YAMLError as exc:
            return None, [f"invalid YAML frontmatter: {exc}"]

        if not isinstance(frontmatter, dict):
            return None, ["frontmatter must be a YAML mapping"]

        frontmatter_keys = {str(key) for key in frontmatter.keys()}
        unexpected_fields = sorted(frontmatter_keys - ANTHROPIC_FRONTMATTER_FIELDS)
        if unexpected_fields:
            return None, [f"unexpected frontmatter field(s): {', '.join(unexpected_fields)}"]

        metadata_field = frontmatter.get("metadata") or {}
        if not isinstance(metadata_field, dict):
            return None, ["metadata must be a mapping"]
        metadata: dict[str, str] = {
            str(key): str(value) for key, value in metadata_field.items()
        }

        allowed_tools_raw = frontmatter.get("allowed-tools")
        allowed_tools, allowed_tools_err = self._parse_allowed_tools(allowed_tools_raw)
        if allowed_tools_err:
            return None, [allowed_tools_err]

        name = str(frontmatter.get("name") or "").strip()
        if not name:
            return None, ["name is required"]

        description = str(frontmatter.get("description") or "").strip()
        if not description:
            return None, ["description is required"]

        license_value = self._optional_str(frontmatter.get("license"))
        compatibility = self._optional_str(frontmatter.get("compatibility"))

        skill = SkillMetadata(
            name=name,
            description=description,
            license=license_value,
            compatibility=compatibility,
            metadata=metadata,
            allowed_tools=allowed_tools,
            path=skill_path.resolve(),
            source_path=skill_path.parent.resolve(),
        )
        return skill, []

    @staticmethod
    def _optional_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _parse_allowed_tools(raw_value: Any) -> Tuple[List[str], Optional[str]]:
        if raw_value is None:
            return [], None
        if isinstance(raw_value, str):
            values = [item.strip() for item in raw_value.split() if item.strip()]
            return values, None
        if isinstance(raw_value, list):
            values = [str(item).strip() for item in raw_value if str(item).strip()]
            return values, None
        return [], "allowed-tools must be a string or list"

    @staticmethod
    def _scan_resources(skill_dir: Path) -> SkillResources:
        """Scan standard skill resource directories and collect immediate files."""

        resources = SkillResources()
        for resource_type, candidates in _RESOURCE_DIRS.items():
            collected: List[Path] = []
            for dirname in candidates:
                target_dir = skill_dir / dirname
                if not target_dir.is_dir():
                    continue
                collected.extend(
                    sorted(
                        (
                            entry.resolve()
                            for entry in target_dir.iterdir()
                            if entry.is_file() and not entry.name.startswith(".")
                        ),
                        key=lambda item: item.name,
                    )
                )
            setattr(resources, resource_type, collected)
        return resources
