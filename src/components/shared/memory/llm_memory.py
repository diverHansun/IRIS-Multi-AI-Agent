from __future__ import annotations

import logging
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from ..storage.session_storage import SessionStorage

logger = logging.getLogger(__name__)


class LLMMemory:
    """Lightweight memory manager for LLM mode."""

    def __init__(self, storage_dir: str = "data/llm/sessions", max_messages: int = 50):
        self.storage = SessionStorage(storage_dir)
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
            return bool(self.storage.save_session(session_id, trimmed, metadata=metadata))
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to add conversation for session %s: %s", session_id, exc)
            return False

    def _trim_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Ensure history length stays within the configured bound."""
        if self.max_messages and len(messages) > self.max_messages:
            return messages[-self.max_messages :]
        return messages
