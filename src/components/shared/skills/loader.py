"""Skill discovery and SKILL.md parsing."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

import yaml

from .types import (
    MAX_SKILL_FILE_SIZE,
    SKILL_FILENAME,
    SkillLoadError,
    SkillMetadata,
    SkillSource,
)

logger = logging.getLogger(__name__)

_FRONTMATTER_PATTERN = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


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
        directory_name: str,
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
        description = str(frontmatter.get("description") or "").strip()
        license_value = self._optional_str(frontmatter.get("license"))
        compatibility = self._optional_str(frontmatter.get("compatibility"))
        argument_hint = self._optional_str(frontmatter.get("argument-hint"))
        context = self._optional_str(frontmatter.get("context"))
        agent = self._optional_str(frontmatter.get("agent"))

        skill = SkillMetadata(
            name=name or directory_name,
            description=description,
            license=license_value,
            compatibility=compatibility,
            metadata=metadata,
            allowed_tools=allowed_tools,
            user_invocable=self._coerce_bool(frontmatter.get("user-invocable"), default=True),
            disable_model_invocation=self._coerce_bool(
                frontmatter.get("disable-model-invocation"), default=False
            ),
            argument_hint=argument_hint,
            context=context,
            agent=agent,
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
    def _coerce_bool(value: Any, *, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "yes", "1", "on"}:
                return True
            if lowered in {"false", "no", "0", "off"}:
                return False
        return bool(value)

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

