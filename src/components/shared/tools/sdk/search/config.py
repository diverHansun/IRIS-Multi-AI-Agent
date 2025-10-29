"""
Search Configuration Utilities Module

Provides common utilities for search tool configuration management.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_project_root(start_path: Path) -> Path:
    """
    Find project root directory by looking for .git or config directory.

    Args:
        start_path: Starting path to search from

    Returns:
        Path to project root directory

    Raises:
        RuntimeError: If project root cannot be found
    """
    current = start_path.resolve()

    # Traverse up the directory tree
    while current != current.parent:
        # Check for project markers
        if (current / ".git").exists() or (current / "config").exists():
            logger.debug(f"Found project root at: {current}")
            return current
        current = current.parent

    # If we reach here, we couldn't find the project root
    raise RuntimeError(
        f"Cannot find project root from {start_path}. "
        "Expected to find .git or config directory."
    )
