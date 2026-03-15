"""
EnvWriter -- .env read/write with format preservation.

Reads, updates, and appends key-value pairs in ~/.iris/.env while
preserving comments and blank lines.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Known provider -> env var mapping for get_configured_providers()
_PROVIDER_KEY_MAP = {
    "zhipu": "ZHIPU_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "tongyi": "TONGYI_API_KEY",
    "ollama": None,  # no key needed
}

# Encodings to try when reading .env (matches env_loader.py)
_ENCODINGS = ["utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gbk"]


class SetupError(Exception):
    """Raised when a setup operation fails."""


class EnvWriter:
    """Read/write ~/.iris/.env with comment and format preservation."""

    def __init__(self, env_path: Path):
        self.env_path = env_path

    def read_key(self, key: str) -> Optional[str]:
        """Read a single key value from .env. Returns None if not found or placeholder."""
        entries = self._read_entries()
        value = entries.get(key)
        if value and not value.startswith("your_"):
            return value
        return None

    def has_key(self, key: str) -> bool:
        """Check if a key has a valid (non-placeholder) value."""
        return self.read_key(key) is not None

    def write_key(self, key: str, value: str) -> None:
        """Write or update a single key in .env, preserving other content."""
        try:
            lines = self._read_lines()
            updated = False

            for i, line in enumerate(lines):
                if self._line_matches_key(line, key):
                    lines[i] = f"{key}={value}\n"
                    updated = True
                    break

            if not updated:
                if lines and not lines[-1].endswith("\n"):
                    lines[-1] += "\n"
                lines.append(f"{key}={value}\n")

            self._write_lines(lines)
            # Also set in current process environment
            os.environ[key] = value
            logger.debug("Wrote %s to %s", key, self.env_path)

        except PermissionError:
            raise SetupError(
                f"Cannot write to {self.env_path}. "
                f"Please check file permissions or edit manually."
            )

    def write_keys(self, pairs: Dict[str, str]) -> None:
        """Write multiple key-value pairs at once."""
        for key, value in pairs.items():
            self.write_key(key, value)

    def get_configured_providers(self) -> List[str]:
        """Return list of provider names that have valid API keys configured."""
        providers = []
        for provider, env_var in _PROVIDER_KEY_MAP.items():
            if env_var is None:
                providers.append(provider)  # ollama always available
                continue
            # Check both .env file and current environment
            value = os.getenv(env_var)
            if value and not value.startswith("your_"):
                providers.append(provider)
                continue
            if self.has_key(env_var):
                providers.append(provider)
        return providers

    def _read_entries(self) -> Dict[str, str]:
        """Parse .env into a dict of key=value pairs."""
        entries: Dict[str, str] = {}
        for line in self._read_lines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)", stripped)
            if match:
                entries[match.group(1)] = match.group(2).strip().strip("\"'")
        return entries

    def _read_lines(self) -> List[str]:
        """Read .env file lines with multi-encoding fallback."""
        if not self.env_path.exists():
            return []

        for enc in _ENCODINGS:
            try:
                return self.env_path.read_text(encoding=enc).splitlines(keepends=True)
            except (UnicodeDecodeError, UnicodeError):
                continue

        logger.warning("Could not decode %s with any supported encoding", self.env_path)
        return []

    def _write_lines(self, lines: List[str]) -> None:
        """Write lines back to .env file."""
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        self.env_path.write_text("".join(lines), encoding="utf-8")

    @staticmethod
    def _line_matches_key(line: str, key: str) -> bool:
        """Check if a line sets the given key (including commented-out lines)."""
        stripped = line.strip()
        # Match both KEY=value and # KEY=value
        if stripped.startswith("#"):
            stripped = stripped.lstrip("#").strip()
        return stripped.startswith(f"{key}=")
