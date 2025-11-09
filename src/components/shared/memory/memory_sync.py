from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from .global_memory import GlobalMemoryManager
from .session_context import SessionContext
from .unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class MemorySyncAdapter:
    """Coordinates runtime and persistent memory across engines."""

    def __init__(self, global_memory: GlobalMemoryManager, *, max_messages: int = 50):
        self.global_memory = global_memory
        storage_dir = str(getattr(global_memory.storage, "storage_dir", "data/sessions"))
        shared_max = getattr(global_memory, "max_messages", max_messages)
        self.storage_checkpointer = UnifiedCheckpointer(
            storage_dir=storage_dir,
            max_messages=shared_max,
            global_memory=global_memory,
        )

    def get_storage_checkpointer(self) -> UnifiedCheckpointer:
        return self.storage_checkpointer

    def load_into_runtime(
        self,
        session_ctx: SessionContext,
        runtime_checkpointer: Any,
        runtime_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Load persisted history into runtime checkpointer if available."""
        config = session_ctx.build_runtime_config(runtime_config)
        if runtime_checkpointer is None:
            return config

        try:
            checkpoint_tuple = self.storage_checkpointer.get_tuple(config)
            if checkpoint_tuple:
                metadata = dict(checkpoint_tuple.metadata or {})
                metadata.setdefault(
                    "checkpoint_ns",
                    config.get("configurable", {}).get("checkpoint_ns"),
                )
                result = runtime_checkpointer.put(
                    config,
                    checkpoint_tuple.checkpoint,
                    metadata,
                    checkpoint_tuple.checkpoint.get("channel_versions", {}),
                )
                checkpoint_id = self._extract_checkpoint_id(result)
                if checkpoint_id:
                    config.setdefault("configurable", {})["checkpoint_id"] = checkpoint_id
                session_ctx.update_checkpoint_id(checkpoint_id)
                logger.debug(
                    "Loaded history for thread_id=%s",
                    config.get("configurable", {}).get("thread_id"),
                )
            else:
                logger.debug(
                    "No stored checkpoint for thread_id=%s",
                    config.get("configurable", {}).get("thread_id"),
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to load history into runtime: %s", exc)
        return config

    def persist_from_runtime(
        self,
        session_ctx: SessionContext,
        runtime_checkpointer: Any,
        runtime_config: Optional[Dict[str, Any]] = None,
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist the final runtime state back to storage."""
        config = session_ctx.build_runtime_config(runtime_config)
        checkpoint_tuple = None
        if runtime_checkpointer is not None:
            try:
                checkpoint_tuple = runtime_checkpointer.get_tuple(config)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to read runtime checkpoint: %s", exc)

        if checkpoint_tuple:
            try:
                checkpoint_copy = checkpoint_tuple.checkpoint.copy()
                channel_values = dict(checkpoint_copy.get("channel_values", {}))
                messages = channel_values.get("messages", [])
                filtered = self._flatten_messages(messages)
                channel_values["messages"] = filtered
                checkpoint_copy["channel_values"] = channel_values
                self.storage_checkpointer.put(
                    config,
                    checkpoint_copy,
                    checkpoint_tuple.metadata,
                    checkpoint_copy.get("channel_versions", {}),
                )
                session_ctx.update_checkpoint_id(checkpoint_copy.get("id"))
                logger.debug(
                    "Persisted runtime checkpoint for thread_id=%s",
                    config.get("configurable", {}).get("thread_id"),
                )
                return
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to persist runtime checkpoint: %s", exc)

        fallback_messages: List[Any] = []
        if isinstance(agent_state, dict):
            state_messages = agent_state.get("messages") or []
            if isinstance(state_messages, list):
                fallback_messages = state_messages

        filtered = self._flatten_messages(fallback_messages)
        if not filtered:
            logger.debug(
                "No messages to persist for thread_id=%s",
                config.get("configurable", {}).get("thread_id"),
            )
            return

        checkpoint_id = str(uuid.uuid4())
        checkpoint_structure = {
            "v": 1,
            "id": checkpoint_id,
            "ts": datetime.now().isoformat(),
            "channel_values": {"messages": filtered},
            "channel_versions": {"messages": len(filtered)},
            "versions_seen": {},
            "updated_channels": ["messages"],
        }
        metadata = {
            "source": "update",
            "step": -1,
            "parents": {},
        }

        try:
            self.storage_checkpointer.put(
                config,
                checkpoint_structure,
                metadata,
                checkpoint_structure["channel_versions"],
            )
            session_ctx.update_checkpoint_id(checkpoint_id)
            logger.debug(
                "Fallback persistence stored %d messages for thread_id=%s",
                len(filtered),
                config.get("configurable", {}).get("thread_id"),
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to persist fallback history: %s", exc)

    @staticmethod
    def _extract_checkpoint_id(result: Any) -> Optional[str]:
        if isinstance(result, dict):
            return result.get("configurable", {}).get("checkpoint_id")
        return None

    @staticmethod
    def _flatten_messages(entries: Any) -> List[BaseMessage]:
        """Extract BaseMessage instances from nested checkpoint structures, preserving order."""

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
