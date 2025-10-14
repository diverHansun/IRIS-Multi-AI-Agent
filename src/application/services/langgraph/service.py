"""
LangGraph service placeholder.
"""

from __future__ import annotations

from typing import Any, Dict

from ..base import BaseEngineService


class LangGraphService(BaseEngineService):
    """
    Placeholder service for future LangGraph integration.
    """

    async def initialize(self, ctx) -> Dict[str, Any]:
        return {"type": "info", "message": "LangGraph initialization is not implemented.", "payload": {}}

    async def handle_query(self, ctx, query: str) -> str:
        raise NotImplementedError("LangGraph query handling is reserved for future implementation.")

    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        return {"type": "error", "message": "LangGraph model switching is not available yet.", "payload": {}}

    def get_info(self, ctx) -> Dict[str, Any]:
        return {"engine": "langgraph", "status": "pending"}

