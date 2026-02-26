"""Session Manager with project-aware storage support."""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console

from src.core.project import ProjectContext, MetadataManager
from ..storage.session_storage import SessionStorage

console = Console()

logger = logging.getLogger(__name__)


class SessionManager:
    """Session manager handling session lifecycle for all modes."""

    def __init__(
        self,
        *,
        mode: str = "basic",
        project_context: Optional[ProjectContext] = None,
        storage_dirs: Optional[Dict[str, str]] = None,
        metadata_manager: Optional[MetadataManager] = None,
    ):
        """
        Initialize session manager.

        Args:
            mode: Active mode ("basic", "llm", "deep")
            project_context: Optional project context; used to resolve .iris paths
            storage_dirs: Optional custom storage directory mapping (overrides context)
            metadata_manager: Optional metadata manager to track last sessions
        """
        self.mode = mode
        self.project_context = project_context
        self.metadata_manager = metadata_manager

        if storage_dirs:
            self.storage_dirs = storage_dirs
        else:
            self.project_context = self.project_context or ProjectContext.from_cwd()
            self.project_context.ensure_structure()
            self.storage_dirs = self.project_context.get_storage_dirs_dict()

        self.storages: Dict[str, SessionStorage] = {
            m: SessionStorage(path) for m, path in self.storage_dirs.items()
        }
        self.current_session_id: Optional[str] = None

        logger.info("Session manager initialized (mode=%s)", mode)

    @property
    def storage(self) -> SessionStorage:
        """Return storage for current mode."""
        return self._resolve_storage(self.mode)

    def create_new_session(self, user_prefix: str = "user") -> str:
        """Create a new session and initialize storage."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        session_id = f"{user_prefix}_{timestamp}_{unique_id}"

        self.current_session_id = session_id
        self.storage.initialize_empty_session(session_id)
        console.print(f"[dim]Created new session: {session_id}[/]")
        self._update_metadata(self.mode, session_id)
        return session_id

    def get_or_create_default_session(self) -> str:
        """Return current session id, creating or loading recent if needed."""
        if not self.current_session_id:
            recent_session = self.get_most_recent_session()
            if recent_session:
                self.current_session_id = recent_session["session_id"]
                console.print(f"[dim]Loaded recent session: {self.current_session_id}[/]")
            else:
                self.current_session_id = self.create_new_session()
            self._update_metadata(self.mode, self.current_session_id)
        return self.current_session_id

    def prompt_for_session_choice(self) -> str:
        """Prompt user to restore recent session or create a new one."""
        if self.current_session_id:
            return self.current_session_id

        recent_session = self.get_most_recent_session()
        if recent_session:
            session_id = recent_session["session_id"]
            turn_count = recent_session.get("turn_count")
            msg_count = recent_session.get("message_count", 0)
            created_time = recent_session.get("created_at", "")[:19] if recent_session.get("created_at") else "Unknown"

            console.print("[yellow]Found recent session:[/]")
            console.print(f"[dim]  Session ID: {session_id}[/]")
            if turn_count is not None:
                console.print(f"[dim]  Turns: {turn_count} (messages: {msg_count})[/]")
            else:
                console.print(f"[dim]  Messages: {msg_count}[/]")
            console.print(f"[dim]  Created: {created_time}[/]")

            try:
                choice = console.input("\n[cyan]Choose action: [1]Restore recent [2]Create new (Default:1): [/]").strip()
                if choice == "2":
                    self.current_session_id = self.create_new_session()
                    console.print("[green]Created new conversation session[/]")
                else:
                    self.current_session_id = session_id
                    console.print(f"[green]Restored recent session: {session_id}[/]")
                    summary = self.get_current_session_summary()
                    if summary != "No conversation history":
                        console.print(f"[dim]Summary: {summary}[/]")
                    self._update_metadata(self.mode, self.current_session_id)
            except (KeyboardInterrupt, EOFError):
                self.current_session_id = session_id
                console.print(f"[dim]Defaulting to restore recent session: {session_id}[/]")
                self._update_metadata(self.mode, self.current_session_id)
        else:
            self.current_session_id = self.create_new_session()
            console.print("[green]First run, created new session[/]")
            self._update_metadata(self.mode, self.current_session_id)

        return self.current_session_id

    def switch_to_session(self, session_id: str) -> bool:
        """Switch to a specified session id."""
        if not self.session_exists(session_id):
            logger.error("Session does not exist: %s", session_id)
            return False

        old_session = self.current_session_id
        self.current_session_id = session_id
        logger.info("Switched session: %s -> %s", old_session, session_id)
        self._update_metadata(self.mode, session_id)
        return True

    def get_most_recent_session(self, mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return most recent session for the target mode."""
        target_mode = mode or self.mode
        sessions = self._resolve_storage(target_mode).list_sessions()
        if sessions:
            return sessions[0]
        return None

    def get_current_session_summary(self) -> str:
        """Return a simple summary of current session."""
        if not self.current_session_id:
            return "No active session"
        info = self._resolve_storage(self.mode).get_session_info(self.current_session_id)
        if not info:
            return "No conversation history"
        if "turn_count" in info:
            return f"Turns: {info.get('turn_count', 0)} (messages: {info.get('message_count', 0)})"
        return f"Messages: {info.get('message_count', 0)}"

    def clear_current_session(self) -> bool:
        """Delete current session from storage."""
        if not self.current_session_id:
            return False
        success = self._resolve_storage(self.mode).delete_session(self.current_session_id)
        if success:
            logger.info("Cleared current session: %s", self.current_session_id)
        return success

    def get_session_stats(self) -> Dict[str, Any]:
        """Return basic statistics for current mode."""
        sessions = self.list_sessions()
        return {
            "current_session_id": self.current_session_id,
            "session_count": len(sessions),
            "most_recent_session": sessions[0]["session_id"] if sessions else None,
        }

    def validate_session_id(self, session_id: str) -> bool:
        """Validate session id format."""
        if not session_id or not isinstance(session_id, str):
            return False
        parts = session_id.split("_")
        return len(parts) >= 3

    def list_sessions(self, mode: Optional[str] = None) -> List[Dict[str, Any]]:
        """List sessions for the specified mode (defaults to current)."""
        target_mode = mode or self.mode
        return self._resolve_storage(target_mode).list_sessions()

    def list_all_sessions(self) -> Dict[str, List[Dict[str, Any]]]:
        """List sessions grouped by mode."""
        return {mode: self._resolve_storage(mode).list_sessions() for mode in self.storage_dirs.keys()}

    def session_exists(self, session_id: str, mode: Optional[str] = None) -> bool:
        """Check whether a session exists in the selected mode."""
        target_mode = mode or self.mode
        return self._resolve_storage(target_mode).session_exists(session_id)

    def get_session_info(self, session_id: str, mode: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return session info if present."""
        target_mode = mode or self.mode
        return self._resolve_storage(target_mode).get_session_info(session_id)

    def cleanup_old_sessions(self, days: int = 30) -> int:
        """Remove sessions older than the given days for current mode."""
        try:
            return self.storage.cleanup_old_sessions(days)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to cleanup old sessions: %s", exc)
            return 0

    def check_session_consistency(self) -> Dict[str, List[str]]:
        """Check consistency between index and filesystem for current mode."""
        try:
            return self.storage.check_session_consistency()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to check session consistency: %s", exc)
            return {"orphaned_index_entries": [], "orphaned_files": []}

    def cleanup_orphaned_sessions(self) -> Dict[str, int]:
        """Cleanup orphaned sessions for current mode."""
        try:
            return self.storage.cleanup_orphaned_sessions()
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to cleanup orphaned sessions: %s", exc)
            return {"orphaned_index_entries": 0, "orphaned_files": 0}

    def _resolve_storage(self, mode: str) -> SessionStorage:
        """Resolve storage for a given mode."""
        if mode not in self.storages:
            logger.warning("Storage for mode '%s' not preconfigured; creating default SessionStorage", mode)
            self.storages[mode] = SessionStorage(self.storage_dirs.get(mode, f"data/{mode}/sessions"))
        return self.storages[mode]

    def _update_metadata(self, mode: str, session_id: str) -> None:
        if self.metadata_manager and self.project_context:
            try:
                self.metadata_manager.update_project(
                    project_path=self.project_context.project_path,
                    project_id=self.project_context.project_id,
                    project_name=self.project_context.project_name,
                    mode=mode,
                    session_id=session_id,
                )
            except Exception as exc:  # pragma: no cover - metadata should not block flows
                logger.debug("Metadata update skipped: %s", exc)
