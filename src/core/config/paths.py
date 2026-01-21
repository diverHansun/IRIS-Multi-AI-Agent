"""
Utility helpers for locating bundled configuration files.

Search order helpers are intentionally kept free of heavy dependencies so they
can be reused across modules (including during package installation).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


def _normalize_relative_path(relative_path: str) -> Path:
    """
    Normalize a config-relative path.

    Accepts paths with or without a leading ``config/`` prefix and always
    returns a path relative to the ``config`` directory.
    """
    rel = Path(relative_path.strip().lstrip("/\\"))
    parts = rel.parts
    if parts and parts[0] == "config":
        rel = Path(*parts[1:]) if len(parts) > 1 else Path()
    return rel


def find_config_dir(start: Optional[Path] = None) -> Optional[Path]:
    """
    Locate the nearest usable ``config`` directory starting from ``start``
    (defaults to the current file) and walking up parent chain.

    A usable config目录需满足：包含子目录 ``llm``（即真正的配置资产，而非
    代码包目录）。这可避免误把 ``src/core/config`` 当成资产目录。
    """
    current = (start or Path(__file__)).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "config"
        if candidate.is_dir() and (candidate / "llm").is_dir():
            return candidate
    return None


def resolve_config_path(
    relative_path: str,
    *,
    project_dir: Optional[Path] = None,
    user_dir: Optional[Path] = None,
    fallback_dirs: Optional[Iterable[Path]] = None,
    project_first: bool = True,
) -> Optional[Path]:
    """
    Resolve a configuration file path using the standard priority order:

    1) Project-level .iris directory (if provided)
    2) User-level .iris directory (if provided)
    3) Additional fallback directories (e.g., bundled ``config``)

    The first existing file is returned; otherwise ``None``.
    """
    rel = _normalize_relative_path(relative_path)
    candidates = []

    if project_dir:
        candidates.append(project_dir / rel if project_first else None)
    if user_dir:
        candidates.append(user_dir / rel)

    # Add project dir again if project_first is False (user precedence)
    if project_dir and not project_first:
        candidates.append(project_dir / rel)

    if fallback_dirs:
        for base in fallback_dirs:
            candidates.append(base / rel)

    for path in candidates:
        if path and path.exists():
            return path
    return None
