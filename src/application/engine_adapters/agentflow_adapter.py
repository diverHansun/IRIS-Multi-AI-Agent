from __future__ import annotations

from src.application.services.agentflow import AgentFlowService
from src.application.engine_adapters.base import BaseAdapter


class AgentFlowAdapter(BaseAdapter):
    async def handle_query(self, ctx, query: str):
        raise NotImplementedError("AgentFlow adapter is not implemented yet.")

    async def execute_graph(self, ctx, graph_name: str, input_state: dict | None = None):
        service = AgentFlowService()
        return await service.handle_query(ctx, graph_name)
