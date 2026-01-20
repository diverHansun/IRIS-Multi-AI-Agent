from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

# Project markers searched from closest directory upward
PROJECT_MARKERS: Tuple[str, ...] = (
    ".iris",
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
)

# Heuristics to detect iris-code source repository
IRIS_SOURCE_MARKERS: Tuple[str, ...] = (
    "src/core/project",
    "src/application/cli",
    "src/components/shared/memory",
)


def detect_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    Walk upward from start_path to find the first directory containing
    any known project marker.
    """
    current = Path(start_path or Path.cwd()).resolve()
    for parent in [current, *list(current.parents)]:
        if parent == Path.home():
            break
        for marker in PROJECT_MARKERS:
            marker_path = parent / marker
            if marker_path.exists():
                # Ignore user-home .git which is often a global config repo
                if marker == ".git" and parent == Path.home():
                    continue
                return parent
    return None


def is_iris_source_project(project_root: Path) -> bool:
    """Return True when the path looks like the iris-code source tree."""
    for marker in IRIS_SOURCE_MARKERS:
        if (project_root / marker).exists():
            return True
    return False
