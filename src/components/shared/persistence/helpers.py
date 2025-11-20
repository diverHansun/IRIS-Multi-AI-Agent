"""
Shared persistence helpers for conversation state management.

This module provides unified persistence utilities used across different components:
- MainAgent conversation handling (conversation.py)
- SubAgent timeout handling (subagents/middleware.py)

Design Principles Applied:
- DRY: Centralized persistence logic to avoid duplication
- SRP: Single responsibility - persist conversation state to storage
- KISS: Simple, straightforward implementation without over-engineering
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.components.shared.memory.memory_sync import MemorySyncAdapter
    from src.components.shared.memory.session_context import SessionContext

logger = logging.getLogger(__name__)


async def persist_conversation_state(
    session_ctx: "SessionContext",
    runtime_checkpointer,
    runtime_config: Dict[str, Any],
    agent_memory_sync: Optional["MemorySyncAdapter"],
    reason: str = "normal",
    ctx=None
) -> bool:
    """
    Unified persistence helper to save conversation state.

    This function extracts state from the runtime checkpointer (MemorySaver)
    and persists it to storage, automatically filtering out system messages.

    Workflow:
    1. Extract state from runtime checkpointer (MemorySaver)
    2. Call persist_from_runtime which automatically filters SystemMessage/ToolMessage
    3. Save only HumanMessage and AIMessage to persistent storage (data/sessions/*.json)

    Args:
        session_ctx: Session context containing session_id
        runtime_checkpointer: Runtime checkpointer (MemorySaver)
        runtime_config: Runtime configuration with thread_id
        agent_memory_sync: Memory sync adapter (handles filtering and persistence)
        reason: Reason for persistence (for logging/debugging)
        ctx: Optional CLI context for console output (for user feedback)

    Returns:
        True if persistence succeeded, False otherwise

    Design Principles:
        - DRY: Centralized logic used by MainAgent and SubAgent handlers
        - SRP: Single responsibility - persist state to storage
        - KISS: Simple implementation without complex branching

    Example:
        ```python
        from src.components.shared.persistence import persist_conversation_state

        # In MainAgent exception handler
        success = await persist_conversation_state(
            session_ctx, runtime_checkpointer, runtime_config,
            agent_memory_sync, reason="step_timeout"
        )

        # In SubAgent timeout handler
        success = await persist_conversation_state(
            session_ctx, runtime_checkpointer, runtime_config,
            agent_memory_sync, reason="subagent_timeout", ctx=None
        )
        ```
    """
    if not agent_memory_sync:
        logger.warning(f"Cannot persist ({reason}): agent_memory_sync is None")
        if ctx:
            ctx.console.print(f"[yellow]Warning: Memory sync not available[/]")
        return False

    try:
        # Extract state from runtime checkpoint
        checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config)
        if checkpoint_tuple:
            # Get channel values (contains messages and other state)
            complete_state = checkpoint_tuple.checkpoint.get("channel_values")

            # Persist to storage (automatically filters to Human/AI messages only)
            # This calls MemorySyncAdapter.persist_from_runtime() which:
            # - Flattens messages from checkpoint structure
            # - Filters out SystemMessage, ToolMessage (system notifications)
            # - Deduplicates messages
            # - Saves to SessionStorage (data/sessions/{session_id}.json)
            agent_memory_sync.persist_from_runtime(
                session_ctx,
                runtime_checkpointer,
                runtime_config,
                complete_state,
            )

            logger.info(f"Conversation persisted successfully ({reason})")
            if ctx:
                ctx.console.print(f"[dim]Conversation saved ({reason}).[/]")
            return True
        else:
            logger.warning(f"No checkpoint available to persist ({reason})")
            if ctx:
                ctx.console.print(f"[yellow]No checkpoint to save ({reason})[/]")
            return False

    except Exception as exc:
        logger.error(f"Failed to persist conversation ({reason}): {exc}", exc_info=True)
        if ctx:
            ctx.console.print(f"[yellow]Warning: Could not save conversation ({reason})[/]")
        return False
