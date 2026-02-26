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

from src.core.project import ProjectContext, MetadataManager
from .message_sequence_utils import dedup_identity_key, trim_messages_by_atomic_groups
from ..storage.session_storage import SessionStorage

logger = logging.getLogger(__name__)


class BasicAgentCheckpointer(BaseCheckpointSaver[int]):
    """LangGraph checkpointer backed by SessionStorage for Basic Agent."""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        max_messages: int = 50,
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
            resolved_dir = str(self.project_context.get_storage_dir("basic"))

        self.storage = SessionStorage(resolved_dir)
        self.max_messages = max_messages

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
        metadata: CheckpointMetadata = {
            "session_id": thread_id,
            "message_count": len(trimmed),
            "step": len(trimmed),  # align with langgraph AsyncPregelLoop expectation
        }

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
        """List available checkpoints (best-effort, latest per session)."""
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
        """Persist checkpoint to storage using merge + dedupe strategy."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        incoming = self._extract_messages(checkpoint)
        filtered = self._filter_messages(incoming)
        existing = self.storage.load_session(thread_id) or []

        merged = existing + filtered
        deduplicated = self._deduplicate_messages(merged)
        trimmed = self._trim_messages(deduplicated)

        # Ensure metadata contains step for langgraph AsyncPregelLoop
        metadata_out: CheckpointMetadata = dict(metadata or {})
        metadata_out.setdefault("step", len(trimmed))
        metadata_out["session_id"] = thread_id
        metadata_out["message_count"] = len(trimmed)

        if not self.storage.save_session(thread_id, trimmed, metadata=metadata_out):
            logger.error("Failed to save session %s", thread_id)
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
        """Basic checkpointer does not persist intermediate writes."""
        logger.debug(
            "put_writes ignored for BasicAgentCheckpointer (task_id=%s, writes=%d)",
            task_id,
            len(writes),
        )

    def delete_thread(self, thread_id: str) -> None:
        """Delete session data for a thread."""
        self.storage.delete_session(thread_id)

    def get_next_version(self, current: int | None, channel: None) -> int:
        """Return next integer version."""
        return (current or 0) + 1

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Async wrapper for get_tuple."""
        return self.get_tuple(config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """Async wrapper for list."""
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Async wrapper for put."""
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Async wrapper for put_writes."""
        return self.put_writes(config, writes, task_id, task_path)

    async def adelete_thread(self, thread_id: str) -> None:
        """Async wrapper for delete_thread."""
        return self.delete_thread(thread_id)

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
        """Keep only conversational messages."""
        flattened = self._flatten_messages(messages)
        return [m for m in flattened if isinstance(m, (HumanMessage, AIMessage, ToolMessage))]

    def _deduplicate_messages(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """Remove duplicates while keeping order."""
        seen = set()
        deduped: List[BaseMessage] = []
        for msg in messages:
            key = dedup_identity_key(msg)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(msg)
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
                    mode="basic",
                    session_id=session_id,
                )
            except Exception as exc:  # pragma: no cover
                logger.debug("Metadata update skipped: %s", exc)
