from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

from .global_memory import GlobalMemoryManager
from .session_context import SessionContext
from .config import DEFAULT_MAX_MESSAGES

logger = logging.getLogger(__name__)


class MemorySyncAdapter:
    """
    Coordinates runtime and persistent memory across engines.

    Supports agent mode routing to enable both shared (basic/llm) and isolated (deep)
    memory architectures. Follows OCP by being extensible via agent_mode parameter.

    Key architectural decision:
    - Basic/LLM modes: Direct SessionStorage usage via GlobalMemoryManager
    - Deep mode: Runtime (MemorySaver) + Storage (SessionStorage) separation
      - enhance_runtime_input injects history as input (not via checkpointer)
      - persist_from_runtime extracts and saves messages after execution
    """

    def __init__(
        self,
        global_memory: GlobalMemoryManager,
        *,
        agent_mode: str = "basic",
        max_messages: int = DEFAULT_MAX_MESSAGES
    ):
        """
        Initialize memory sync adapter.

        Args:
            global_memory: GlobalMemoryManager instance
            agent_mode: Agent mode ("basic", "llm", or "deep")
            max_messages: Maximum messages to retain per session
        """
        self.global_memory = global_memory
        self.agent_mode = agent_mode
        self.max_messages = max_messages

        logger.info(f"MemorySyncAdapter initialized: agent_mode={agent_mode}")

    @property
    def storage(self):
        """Get storage instance for current mode."""
        return self.global_memory.get_storage_by_mode(self.agent_mode)

    def enhance_runtime_input(
        self,
        session_ctx: SessionContext,
        user_query: str,
        max_history: int = 10
    ) -> Dict[str, Any]:
        """
        Enhance runtime input with historical messages (Deep mode).

        This replaces the problematic load_into_runtime approach by injecting
        history directly into the input rather than loading it into the runtime
        checkpointer. This avoids channel_versions type conflicts between storage
        (integer) and runtime (string) formats.

        Args:
            session_ctx: Session context
            user_query: User query string
            max_history: Maximum historical messages to include (default: 10)

        Returns:
            Enhanced input dictionary with messages including history
        """
        messages = []
        try:
            stored_messages = self.storage.load_session(session_ctx.session_id)
            if stored_messages:
                # Take only the most recent max_history messages to avoid context overflow
                messages = stored_messages[-max_history:]
                logger.debug(
                    f"Enhanced input with {len(messages)} historical messages "
                    f"for session {session_ctx.session_id}"
                )
        except Exception as exc:
            logger.warning(f"Failed to load history for input enhancement: {exc}")

        # Append current user query
        messages.append(HumanMessage(content=user_query))

        return {"messages": messages}

    def load_into_runtime(
        self,
        session_ctx: SessionContext,
        runtime_checkpointer: Any,
        runtime_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        DEPRECATED: Load persisted history into runtime checkpointer.
        """
        logger.warning(
            "load_into_runtime() is deprecated. "
            "Use enhance_runtime_input() for Deep mode instead."
        )
        config = session_ctx.build_runtime_config(runtime_config)
        return config

    def persist_from_runtime(
        self,
        session_ctx: SessionContext,
        runtime_checkpointer: Any,
        runtime_config: Optional[Dict[str, Any]] = None,
        agent_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Persist the final runtime state back to storage.

        Extracts messages from agent_state (primary) or runtime checkpoint (fallback),
        filters for Human/AI messages only, and saves to storage.

        CRITICAL: This method must preserve all historical messages. The agent_state
        should contain ALL messages (history + new), not just the current turn.

        Args:
            session_ctx: Session context
            runtime_checkpointer: Runtime checkpointer (MemorySaver for Deep mode)
            runtime_config: Optional runtime configuration
            agent_state: Agent state dictionary (primary source for messages)
        """
        config = session_ctx.build_runtime_config(runtime_config)

        # Primary path: Extract messages from agent_state
        messages_to_persist: List[Any] = []
        if isinstance(agent_state, dict):
            state_messages = agent_state.get("messages") or []
            if isinstance(state_messages, list):
                messages_to_persist = state_messages
                logger.debug(
                    f"Extracting {len(messages_to_persist)} messages from agent_state"
                )

        # Fallback path: Try runtime checkpoint if agent_state has no messages
        if not messages_to_persist and runtime_checkpointer is not None:
            try:
                checkpoint_tuple = runtime_checkpointer.get_tuple(config)
                if checkpoint_tuple:
                    checkpoint_copy = checkpoint_tuple.checkpoint.copy()
                    channel_values = dict(checkpoint_copy.get("channel_values", {}))
                    messages_to_persist = channel_values.get("messages", [])
                    logger.debug(
                        f"Fallback to runtime checkpoint: {len(messages_to_persist)} messages"
                    )
            except Exception as exc:
                logger.warning(f"Failed to read runtime checkpoint: {exc}")

        # Flatten messages
        flattened = self._flatten_messages(messages_to_persist)

        # Filter: Only keep HumanMessage and AIMessage
        # KISS + SRP: Simple type-based filtering, excluding system notifications
        # This ensures SystemMessage and ToolMessage are never persisted
        filtered = [
            m for m in flattened
            if isinstance(m, (HumanMessage, AIMessage))
            # Automatically excludes: SystemMessage, ToolMessage, and other non-conversational types
        ]

        logger.debug(
            f"Filtered {len(filtered)} Human/AI messages from {len(flattened)} total "
            f"(excluded {len(flattened) - len(filtered)} system/tool messages)"
        )

        if not filtered:
            logger.warning(
                f"No Human/AI messages to persist for session {session_ctx.session_id}"
            )
            return

        # Deduplicate messages by content and type
        # This prevents duplicate messages when checkpoint contains history
        deduplicated = self._deduplicate_messages(filtered)
        if len(deduplicated) < len(filtered):
            logger.info(
                f"Removed {len(filtered) - len(deduplicated)} duplicate messages"
            )

        try:
            # Save directly to storage (JSON)
            # This REPLACES the entire session, so deduplicated must contain ALL messages
            self.storage.save_session(session_ctx.session_id, deduplicated)
            logger.debug(
                f"Persisted {len(deduplicated)} messages for session {session_ctx.session_id}"
            )
        except Exception as exc:
            logger.error(f"Failed to persist messages to storage: {exc}")

    @staticmethod
    def _deduplicate_messages(messages: List[BaseMessage]) -> List[BaseMessage]:
        """
        Remove duplicate messages while preserving order.
        
        Two messages are considered duplicates if they have:
        - Same type (HumanMessage, AIMessage)
        - Same content
        
        This is necessary because the checkpoint may contain history that was
        injected via enhance_runtime_input, leading to duplicates.
        """
        seen = set()
        deduplicated = []
        
        for msg in messages:
            # Create a unique key based on message type and content
            msg_type = type(msg).__name__
            msg_content = msg.content if hasattr(msg, 'content') else str(msg)
            key = (msg_type, msg_content)
            
            if key not in seen:
                seen.add(key)
                deduplicated.append(msg)
        
        return deduplicated

    @staticmethod
    def _flatten_messages(entries: Any) -> List[BaseMessage]:
        """
        Extract BaseMessage instances from nested checkpoint structures.
        """
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
