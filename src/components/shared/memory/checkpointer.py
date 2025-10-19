"""Utility helpers for LangGraph checkpointer integration."""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver


@dataclass
class BaseAgentCheckpointer:
    """Wrapper around a LangGraph checkpointer used by BaseAgent."""

    checkpointer: MemorySaver

    def build_config(self, session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Create the runnable config used to route state by session."""
        configurable: Dict[str, Any] = {"thread_id": session_id}
        if user_id:
            configurable["user_id"] = user_id
        return {"configurable": configurable}


def create_default_checkpointer() -> BaseAgentCheckpointer:
    """Create a default in-memory checkpointer."""
    return BaseAgentCheckpointer(checkpointer=MemorySaver())
