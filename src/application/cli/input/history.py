"""
Input history path strategy.

Resolves a prompt_toolkit History instance for the current AppState.

Priority (high to low):
  1. <project>/.iris/input_history  — project-level, via ProjectContext.iris_dir
  2. ~/.iris/input_history           — user-level fallback, via IrisShareDir.get_share_dir()
  3. InMemoryHistory                 — final fallback when no file is writable

Path conventions follow the existing two-tier storage model used throughout
the project: project-scoped data lives under ProjectContext.iris_dir,
user-scoped data lives under IrisShareDir.get_share_dir().
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from prompt_toolkit.history import History, FileHistory, InMemoryHistory

from src.core.project.share import IrisShareDir

if TYPE_CHECKING:
    from src.application.cli.state import AppState

logger = logging.getLogger(__name__)

_HISTORY_FILENAME = "input_history"


class HistoryPathResolver:
    """Map AppState paths to a concrete prompt_toolkit History instance."""

    def resolve(self, ctx: "AppState") -> History:
        # Level 1: project-scoped — <project>/.iris/input_history
        if ctx.project_context is not None:
            history = self._try_file(ctx.project_context.iris_dir / _HISTORY_FILENAME)
            if history is not None:
                return history

        # Level 2: user-scoped — ~/.iris/input_history
        # IrisShareDir.get_share_dir() is the canonical accessor for ~/.iris/
        # and creates the directory if it does not yet exist.
        history = self._try_file(IrisShareDir.get_share_dir() / _HISTORY_FILENAME)
        if history is not None:
            return history

        # Level 3: in-memory — valid only for the current process lifetime
        logger.warning(
            "Input history file is not writable; falling back to in-memory history."
        )
        return InMemoryHistory()

    @staticmethod
    def _try_file(path: Path) -> FileHistory | None:
        """Return a FileHistory for the given path, or None if the file cannot be opened."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return FileHistory(str(path))
        except OSError as exc:
            logger.debug("Cannot use history file %s: %s", path, exc)
            return None
