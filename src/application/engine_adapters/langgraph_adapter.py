"""
LangGraph engine adapter placeholder.
"""

from __future__ import annotations

from ..services.langgraph import LangGraphService  # pyright: ignore[reportMissingImports]
from .base import BaseAdapter


class LangGraphAdapter(BaseAdapter):
    async def handle_query(self, ctx, query: str):
        raise NotImplementedError("LangGraph adapter is not implemented yet.")

    async def execute_graph(self, ctx, graph_name: str, input_state: dict | None = None):
        service = LangGraphService()
        return await service.handle_query(ctx, graph_name)
