from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.memory import MemorySaver

from src.core.project import ProjectContext, MetadataManager
from .message_sequence_utils import (
    are_consecutive_duplicates,
    extract_recent_turns,
    trim_messages_by_atomic_groups,
)
from ..storage.session_storage import SessionStorage

logger = logging.getLogger(__name__)


class DeepAgentCheckpointer(BaseCheckpointSaver[int]):
    """Checkpointer for Deep Agent with runtime + persistent storage support."""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        runtime_checkpointer: MemorySaver | None = None,
        max_messages: int = 100,
        project_context: Optional[ProjectContext] = None,
        metadata_manager: Optional[MetadataManager] = None,
    ) -> None:
        super().__init__()
        self.project_context = project_context
        self.metadata_manager = metadata_manager

        resolved_dir = storage_dir
        if not resolved_dir:
            self.project_context = self.project_context or ProjectContext.from_cwd()
            self.project_context.ensure_structure()
            resolved_dir = str(self.project_context.get_storage_dir("deep"))

        self.storage = SessionStorage(resolved_dir)
        self.runtime_checkpointer = runtime_checkpointer or MemorySaver()
        self.max_messages = max_messages

    def enhance_runtime_input(
        self,
        session_id: str,
        user_query: str,
        max_history: int = 10,
    ) -> Dict[str, Any]:
        """Inject recent history for Deep Agent runtime execution."""
        messages: List[BaseMessage] = []
        try:
            stored = self.storage.load_session(session_id)
            if stored:
                messages = extract_recent_turns(stored, max_turns=max_history)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to load history for session %s: %s", session_id, exc)

        messages.append(HumanMessage(content=user_query))
        return {"messages": messages}

    def persist_from_runtime(
        self,
        session_id: str,
        runtime_checkpointer: Any = None,
        runtime_config: Optional[Dict[str, Any]] = None,
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Persist runtime state back to storage, preserving HITL history."""
        config = runtime_config or {"configurable": {"thread_id": session_id, "checkpoint_ns": ""}}
        runtime_cp = runtime_checkpointer or self.runtime_checkpointer

        messages_to_persist: List[Any] = []
        if isinstance(agent_state, dict):
            candidate = agent_state.get("messages") or []
            if isinstance(candidate, list):
                messages_to_persist = candidate
                logger.debug("[PERSIST] Got %d messages from agent_state", len(messages_to_persist))

        if not messages_to_persist and runtime_cp is not None:
            try:
                checkpoint_tuple = runtime_cp.get_tuple(config)
                if checkpoint_tuple:
                    channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})
                    messages_to_persist = channel_values.get("messages", []) or []
                    logger.debug("[PERSIST] Got %d messages from runtime checkpoint", len(messages_to_persist))
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Failed to read runtime checkpoint for %s: %s", session_id, exc)

        logger.debug("[PERSIST] Messages to persist (raw): %d messages", len(messages_to_persist))
        for idx, msg in enumerate(messages_to_persist[:5]):
            msg_type = type(msg).__name__ if hasattr(msg, "__class__") else str(type(msg))
            msg_content = getattr(msg, "content", str(msg))[:50] if hasattr(msg, "content") else str(msg)[:50]
            logger.debug("[PERSIST]   [%d] %s: %s...", idx, msg_type, msg_content)

        filtered = self._filter_messages(messages_to_persist)
        if not filtered:
            logger.warning("No messages to persist for session %s", session_id)
            return False

        logger.debug("[PERSIST] After filtering: %d conversational messages", len(filtered))
        for idx, msg in enumerate(filtered[:5]):
            logger.debug("[PERSIST]   [%d] %s: %s...", idx, type(msg).__name__, msg.content[:50])

        deduplicated = self._deduplicate_messages(filtered)
        logger.debug("[PERSIST] After deduplication: %d messages (no merge, direct replacement)", len(deduplicated))

        trimmed = self._trim_messages(deduplicated)
        logger.debug("[PERSIST] After trimming: %d final messages", len(trimmed))

        metadata: CheckpointMetadata = {"session_id": session_id, "message_count": len(trimmed)}
        if not self.storage.save_session(session_id, trimmed, metadata=metadata):
            logger.error("Failed to persist messages for session %s", session_id)
            return False

        self._update_metadata(session_id)
        return True

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Load checkpoint tuple from persistent storage."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        messages = self.storage.load_session(thread_id) or []
        if not messages:
            return None

        trimmed = self._trim_messages(messages)
        checkpoint_id = self._make_checkpoint_id(len(trimmed))
        checkpoint = self._messages_to_checkpoint(checkpoint_id, trimmed)
        metadata: CheckpointMetadata = {"session_id": thread_id, "message_count": len(trimmed)}

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=None,
            pending_writes=[],
        )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """List available checkpoints (latest per session)."""
        if config:
            item = self.get_tuple(config)
            if item:
                yield item
            return

        remaining = limit
        for session in self.storage.list_sessions():
            if remaining is not None and remaining <= 0:
                break
            session_id = session.get("session_id")
            if not session_id:
                continue
            item = self.get_tuple({"configurable": {"thread_id": session_id, "checkpoint_ns": ""}})
            if item:
                yield item
                if remaining is not None:
                    remaining -= 1

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Persist checkpoint to storage with merge + dedupe."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        incoming = self._extract_messages(checkpoint)
        filtered = self._filter_messages(incoming)
        existing = self.storage.load_session(thread_id) or []

        merged = existing + filtered
        deduplicated = self._deduplicate_messages(merged)
        trimmed = self._trim_messages(deduplicated)

        if not self.storage.save_session(thread_id, trimmed, metadata=metadata):
            logger.error("Failed to save checkpoint for session %s", thread_id)
        else:
            self._update_metadata(thread_id)

        checkpoint_id = self._make_checkpoint_id(len(trimmed))
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Delegate intermediate writes to runtime checkpointer when available."""
        runtime_cp = self.runtime_checkpointer
        if runtime_cp and hasattr(runtime_cp, "put_writes"):
            runtime_cp.put_writes(config, writes, task_id, task_path)

    def delete_thread(self, thread_id: str) -> None:
        """Delete all data for a thread."""
        self.storage.delete_session(thread_id)
        if hasattr(self.runtime_checkpointer, "delete_thread"):
            try:
                self.runtime_checkpointer.delete_thread(thread_id)
            except Exception:  # pragma: no cover - defensive cleanup
                logger.warning("Failed to delete runtime thread %s", thread_id)

    def get_next_version(self, current: int | None, channel: None) -> int:
        """Return next integer version."""
        return (current or 0) + 1

    def _messages_to_checkpoint(self, checkpoint_id: str, messages: List[BaseMessage]) -> Checkpoint:
        """Convert messages into a LangGraph checkpoint structure."""
        return {
            "v": 1,
            "id": checkpoint_id,
            "ts": datetime.utcnow().isoformat(),
            "channel_values": {"messages": messages},
            "channel_versions": {"messages": len(messages)},
            "versions_seen": {},
            "updated_channels": ["messages"],
        }

    def _extract_messages(self, checkpoint: Checkpoint) -> List[Any]:
        """Extract raw messages from checkpoint payload."""
        channel_values = checkpoint.get("channel_values", {})
        return channel_values.get("messages", []) or []

    def _filter_messages(self, messages: List[Any]) -> List[BaseMessage]:
        """Keep only conversational messages (Human/AI/Tool)."""
        flattened = self._flatten_messages(messages)
        filtered = [m for m in flattened if isinstance(m, (HumanMessage, AIMessage, ToolMessage))]

        human_count = sum(1 for m in filtered if isinstance(m, HumanMessage))
        ai_count = sum(1 for m in filtered if isinstance(m, AIMessage))
        tool_count = sum(1 for m in filtered if isinstance(m, ToolMessage))
        logger.debug(
            "[FILTER] Input: %d messages, Flattened: %d, Filtered: %d (Human: %d, AI: %d, Tool: %d)",
            len(messages),
            len(flattened),
            len(filtered),
            human_count,
            ai_count,
            tool_count,
        )

        return filtered

    def _deduplicate_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Remove consecutive duplicates only.

        This preserves non-consecutive duplicates (e.g., user asks the same question twice).
        """
        if not messages:
            return []

        deduped: List[BaseMessage] = [messages[0]]
        duplicates_removed = 0

        for msg in messages[1:]:
            prev = deduped[-1]
            if are_consecutive_duplicates(prev, msg):
                duplicates_removed += 1
                logger.debug(
                    "[DEDUP] Removing consecutive duplicate: %s: %s...",
                    type(msg).__name__,
                    (msg.content[:30] if hasattr(msg, "content") else ""),
                )
                continue

            deduped.append(msg)

        if duplicates_removed > 0:
            logger.debug("[DEDUP] Removed %d consecutive duplicate messages", duplicates_removed)

        return deduped

    def _flatten_messages(self, entries: Any) -> List[BaseMessage]:
        """Extract BaseMessage instances from nested structures."""
        def walk(value: Any, collector: List[BaseMessage]) -> None:
            if isinstance(value, BaseMessage):
                collector.append(value)
                return
            if value is None:
                return
            if isinstance(value, dict):
                item_type = value.get("type")
                item_value = value.get("value")
                if item_type == "message" and isinstance(item_value, BaseMessage):
                    collector.append(item_value)
                    return
                for dict_value in value.values():
                    walk(dict_value, collector)
                return
            if isinstance(value, (list, tuple)):
                for element in value:
                    walk(element, collector)
                return
            if isinstance(value, set):
                for element in sorted(value, key=lambda x: id(x)):
                    walk(element, collector)

        flattened: List[BaseMessage] = []
        walk(entries, flattened)
        return flattened

    def _trim_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Trim history to max_messages if needed."""
        return trim_messages_by_atomic_groups(messages, self.max_messages)

    def _make_checkpoint_id(self, length: int) -> str:
        """Create a monotonic checkpoint id based on message count."""
        return f"{length:016d}"

    def _update_metadata(self, session_id: str) -> None:
        if self.metadata_manager and self.project_context:
            try:
                self.metadata_manager.update_project(
                    project_path=self.project_context.project_path,
                    project_id=self.project_context.project_id,
                    project_name=self.project_context.project_name,
                    mode="deep",
                    session_id=session_id,
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Metadata update skipped: %s", exc)
