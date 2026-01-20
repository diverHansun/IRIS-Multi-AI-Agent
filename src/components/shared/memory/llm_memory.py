from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.core.project import ProjectContext, MetadataManager
from ..storage.session_storage import SessionStorage

logger = logging.getLogger(__name__)


class LLMMemory:
    """Lightweight memory manager for LLM mode."""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        max_messages: int = 50,
        project_context: Optional[ProjectContext] = None,
        metadata_manager: Optional[MetadataManager] = None,
    ):
        self.project_context = project_context
        self.metadata_manager = metadata_manager

        resolved_dir = storage_dir
        if not resolved_dir:
            self.project_context = self.project_context or ProjectContext.from_cwd()
            self.project_context.ensure_structure()
            resolved_dir = str(self.project_context.get_storage_dir("llm"))

        self.storage = SessionStorage(resolved_dir)
        self.max_messages = max_messages

    def get_history(self, session_id: str, max_messages: Optional[int] = None) -> List[BaseMessage]:
        """Load history for a session with an optional cap."""
        messages = self.storage.load_session(session_id) or []
        limit = max_messages if max_messages is not None else self.max_messages
        if limit and len(messages) > limit:
            return messages[-limit:]
        return messages

    def add_conversation(
        self,
        session_id: str,
        user_message: str,
        ai_message: str,
        *,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Append a user/AI turn and persist."""
        try:
            messages = self.storage.load_session(session_id) or []
            messages.append(HumanMessage(content=user_message))
            messages.append(AIMessage(content=ai_message))

            trimmed = self._trim_messages(messages)
            saved = bool(self.storage.save_session(session_id, trimmed, metadata=metadata))
            if saved:
                self._update_metadata(session_id)
            return saved
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to add conversation for session %s: %s", session_id, exc)
            return False

    def _trim_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Ensure history length stays within the configured bound."""
        if self.max_messages and len(messages) > self.max_messages:
            return messages[-self.max_messages :]
        return messages

    def _update_metadata(self, session_id: str) -> None:
        if self.metadata_manager and self.project_context:
            try:
                self.metadata_manager.update_project(
                    project_path=self.project_context.project_path,
                    project_id=self.project_context.project_id,
                    project_name=self.project_context.project_name,
                    mode="llm",
                    session_id=session_id,
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Metadata update skipped: %s", exc)
