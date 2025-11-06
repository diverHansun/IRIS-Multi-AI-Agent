"""
UnifiedCheckpointer implementation integrating LangGraph standard interface with GlobalMemoryManager.

Provides:
1. LangGraph BaseCheckpointSaver interface compliance
2. File-based persistence via GlobalMemoryManager
3. Cross-session management capabilities
4. Backward compatibility with BaseAgentCheckpointer wrapper

This file replaces the old checkpointer.py, providing both new unified functionality
and backward compatibility for existing code (including deep agents).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointTuple,
    CheckpointMetadata,
)
from langgraph.checkpoint.memory import MemorySaver

from src.components.shared.memory.global_memory import GlobalMemoryManager

logger = logging.getLogger(__name__)


@dataclass
class BaseAgentCheckpointer:
    """
    Backward compatibility wrapper for old checkpointer.py interface.

    This wrapper is used by deep agents and legacy code.
    It provides the same interface as the old BaseAgentCheckpointer class.
    """

    checkpointer: MemorySaver

    def build_config(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create the runnable config used to route state by session."""
        configurable: Dict[str, Any] = {"thread_id": session_id}
        if user_id:
            configurable["user_id"] = user_id
        return {"configurable": configurable}


def create_default_checkpointer() -> BaseAgentCheckpointer:
    """
    Create a default in-memory checkpointer.

    Backward compatibility function for old checkpointer.py interface.
    Used by deep agents and legacy code.

    Returns:
        BaseAgentCheckpointer wrapper with MemorySaver
    """
    return BaseAgentCheckpointer(checkpointer=MemorySaver())


class UnifiedCheckpointer(BaseCheckpointSaver):
    """
    Unified checkpointer integrating LangGraph standard with GlobalMemoryManager.

    This class bridges the gap between LangGraph's checkpoint interface and our
    existing GlobalMemoryManager, providing:
    - Standard LangGraph checkpoint interface for create_agent()
    - File-based persistence for conversation history
    - Session management across multiple conversations

    The checkpointer creates its own GlobalMemoryManager instance, ensuring all
    agents share the same storage directory for consistent session management.
    """

    def __init__(
        self,
        storage_dir: str = "data/sessions",
        max_messages: int = 50,
        serde: Optional[Any] = None,
    ):
        """
        Initialize unified checkpointer.

        Args:
            storage_dir: Directory for session storage (default: "data/sessions")
            max_messages: Maximum messages to retain per session (default: 50)
            serde: Optional serializer (uses default if None)
        """
        super().__init__(serde=serde)

        # Create GlobalMemoryManager instance for persistence
        self.global_memory = GlobalMemoryManager(
            storage_dir=storage_dir,
            max_messages=max_messages
        )

        self.storage_dir = storage_dir
        self.max_messages = max_messages

        logger.info(
            f"UnifiedCheckpointer initialized: storage_dir={storage_dir}, "
            f"max_messages={max_messages}"
        )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """
        Retrieve checkpoint tuple from GlobalMemoryManager.

        Implements LangGraph BaseCheckpointSaver interface.

        Args:
            config: Runnable configuration containing thread_id (session_id)

        Returns:
            CheckpointTuple if session exists, None otherwise
        """
        session_id = config["configurable"]["thread_id"]

        # Load messages from GlobalMemoryManager
        history = self.global_memory.get_session_history(session_id)
        messages = history.messages

        if not messages:
            logger.debug(f"No checkpoint found for session: {session_id}")
            return None

        # Convert to LangGraph Checkpoint format
        checkpoint = Checkpoint(
            v=1,
            id=str(uuid.uuid4()),
            ts=datetime.now().isoformat(),
            channel_values={"messages": messages},
            channel_versions={"messages": len(messages)},
            versions_seen={},
            updated_channels=["messages"],
        )

        metadata = CheckpointMetadata(
            source="input",
            step=-1,
            parents={},
        )

        logger.debug(f"Loaded checkpoint for session {session_id}: {len(messages)} messages")

        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
        )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """
        Save checkpoint to GlobalMemoryManager.

        Implements LangGraph BaseCheckpointSaver interface.

        Args:
            config: Runnable configuration containing thread_id (session_id)
            checkpoint: Checkpoint data to save
            metadata: Checkpoint metadata
            new_versions: Channel versions

        Returns:
            Updated configuration
        """
        session_id = config["configurable"]["thread_id"]

        # Extract messages from checkpoint
        messages: List[BaseMessage] = checkpoint["channel_values"].get("messages", [])

        # Save to GlobalMemoryManager (replace mode)
        history = self.global_memory.get_session_history(session_id)
        history.clear()
        history.add_messages(messages)

        logger.debug(f"Saved checkpoint for session {session_id}: {len(messages)} messages")

        return config

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """
        List checkpoints matching criteria.

        Simplified implementation: returns current session checkpoint only.

        Args:
            config: Base configuration (must contain thread_id)
            filter: Additional filtering criteria (not used)
            before: List checkpoints before this configuration (not used)
            limit: Maximum number of checkpoints (not used)

        Yields:
            CheckpointTuple for the current session if exists
        """
        if config and "configurable" in config and "thread_id" in config["configurable"]:
            checkpoint_tuple = self.get_tuple(config)
            if checkpoint_tuple:
                yield checkpoint_tuple

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """
        Async version of get_tuple.

        Args:
            config: Runnable configuration containing thread_id

        Returns:
            CheckpointTuple if exists, None otherwise
        """
        return self.get_tuple(config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """
        Async version of put.

        Args:
            config: Runnable configuration
            checkpoint: Checkpoint data
            metadata: Checkpoint metadata
            new_versions: Channel versions

        Returns:
            Updated configuration
        """
        return self.put(config, checkpoint, metadata, new_versions)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ):
        """
        Async version of list.

        Args:
            config: Base configuration
            filter: Filtering criteria
            before: List before this config
            limit: Maximum results

        Yields:
            CheckpointTuple for matching sessions
        """
        if config and "configurable" in config and "thread_id" in config["configurable"]:
            checkpoint_tuple = await self.aget_tuple(config)
            if checkpoint_tuple:
                yield checkpoint_tuple

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Any,
        task_id: str,
        task_path: str = "",
    ) -> None:
        """
        Save intermediate writes.

        For file-based persistence, writes are captured in final checkpoint.

        Args:
            config: Runnable configuration
            writes: Writes to save
            task_id: Task identifier
            task_path: Task path
        """
        pass

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Any,
        task_id: str,
        task_path: str = "",
    ) -> None:
        """
        Async version of put_writes.

        Args:
            config: Runnable configuration
            writes: Writes to save
            task_id: Task identifier
            task_path: Task path
        """
        self.put_writes(config, writes, task_id, task_path)

    # Extended methods (non-LangGraph standard, for Agent usage)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """
        List all available sessions.

        Extended method beyond LangGraph interface.

        Returns:
            List of session information dictionaries
        """
        return self.global_memory.list_sessions()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a specific session.

        Extended method beyond LangGraph interface.

        Args:
            session_id: Session identifier to delete

        Returns:
            True if deletion successful, False otherwise
        """
        try:
            result = self.global_memory.storage.delete_session(session_id)
            if result:
                logger.info(f"Deleted session: {session_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False

    def clear_all_sessions(self) -> int:
        """
        Clear all sessions from storage.

        Extended method beyond LangGraph interface.

        Returns:
            Number of sessions cleared
        """
        sessions = self.list_sessions()
        count = 0
        for session in sessions:
            session_id = session.get("session_id")
            if session_id and self.delete_session(session_id):
                count += 1

        logger.info(f"Cleared {count} sessions")
        return count

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific session.

        Extended method beyond LangGraph interface.

        Args:
            session_id: Session identifier

        Returns:
            Session information dictionary or None if not found
        """
        if hasattr(self.global_memory, 'get_session_info'):
            return self.global_memory.get_session_info(session_id)
        return None

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"UnifiedCheckpointer(storage_dir={self.storage_dir}, "
            f"max_messages={self.max_messages})"
        )
