"""Validation helpers for skill metadata."""

from __future__ import annotations

import logging
import re
from typing import List, Tuple

from .types import (
    MAX_SKILL_COMPATIBILITY_LENGTH,
    MAX_SKILL_DESCRIPTION_LENGTH,
    MAX_SKILL_NAME_LENGTH,
    SKILL_NAME_PATTERN,
    SkillMetadata,
)

logger = logging.getLogger(__name__)


class SkillValidator:
    """Validate skill names and metadata."""

    def __init__(
        self,
        *,
        strict_name_check: bool = True,
        warn_on_missing_description: bool = True,
    ) -> None:
        self._strict_name_check = strict_name_check
        self._warn_on_missing_description = warn_on_missing_description
        self._name_pattern = re.compile(SKILL_NAME_PATTERN)

    def validate_name(self, name: str, directory_name: str) -> Tuple[bool, List[str]]:
        """Validate a skill name against project rules."""

        errors: List[str] = []
        if not name:
            errors.append("name is required")
            return False, errors

        if len(name) > MAX_SKILL_NAME_LENGTH:
            errors.append(f"name exceeds max length {MAX_SKILL_NAME_LENGTH}")

        if "--" in name:
            errors.append("name must not contain consecutive hyphens")

        if not self._name_pattern.fullmatch(name):
            errors.append("name must use lowercase alphanumeric and hyphens only")

        if directory_name and name != directory_name:
            errors.append("name must match parent directory name")

        return len(errors) == 0, errors

    def validate_metadata(self, skill: SkillMetadata) -> Tuple[bool, List[str]]:
        """Validate non-name metadata and normalize bounded fields."""

        errors: List[str] = []

        if not skill.name or not skill.name.strip():
            errors.append("name is required")

        if not skill.description or not skill.description.strip():
            if self._warn_on_missing_description:
                errors.append("description is required")
        elif len(skill.description) > MAX_SKILL_DESCRIPTION_LENGTH:
            logger.warning(
                "Skill description too long (%d), truncating to %d",
                len(skill.description),
                MAX_SKILL_DESCRIPTION_LENGTH,
            )
            skill.description = skill.description[:MAX_SKILL_DESCRIPTION_LENGTH]

        if skill.compatibility and len(skill.compatibility) > MAX_SKILL_COMPATIBILITY_LENGTH:
            logger.warning(
                "Skill compatibility too long (%d), truncating to %d",
                len(skill.compatibility),
                MAX_SKILL_COMPATIBILITY_LENGTH,
            )
            skill.compatibility = skill.compatibility[:MAX_SKILL_COMPATIBILITY_LENGTH]

        if not isinstance(skill.metadata, dict):
            errors.append("metadata must be a dictionary")
        else:
            # Ensure map values are strings for predictable prompt rendering.
            skill.metadata = {str(k): str(v) for k, v in skill.metadata.items()}

        if not isinstance(skill.allowed_tools, list):
            errors.append("allowed-tools must be a list")
        else:
            skill.allowed_tools = [str(item) for item in skill.allowed_tools if str(item).strip()]

        return len(errors) == 0, errors

    def validate_basic(self, skill: SkillMetadata) -> Tuple[bool, List[str]]:
        """Run full basic validation for registry loading."""

        errors: List[str] = []

        if self._strict_name_check:
            name_ok, name_errors = self.validate_name(skill.name, skill.path.parent.name)
            if not name_ok:
                errors.extend(name_errors)

        metadata_ok, metadata_errors = self.validate_metadata(skill)
        if not metadata_ok:
            errors.extend(metadata_errors)

        return len(errors) == 0, errors

