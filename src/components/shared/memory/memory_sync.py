from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

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
                logger.info(
                    f"[PERSIST] Extracting {len(messages_to_persist)} raw messages from agent_state"
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
        filtered = [
            m for m in flattened 
            if isinstance(m, (HumanMessage, AIMessage))
        ]

        logger.info(
            f"[PERSIST] After filtering: {len(filtered)} messages "
            f"(from {len(flattened)} flattened messages)"
        )

        if not filtered:
            logger.warning(
                f"[PERSIST] No Human/AI messages to persist for thread_id="
                f"{config.get('configurable', {}).get('thread_id')}"
            )
            return

        try:
            # Save directly to storage (JSON)
            self.storage.save_session(session_ctx.session_id, filtered)
            logger.info(
                f"Successfully persisted {len(filtered)} messages "
                f"for session {session_ctx.session_id}"
            )
        except Exception as exc:
            logger.error(f"Failed to persist messages to storage: {exc}")

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
