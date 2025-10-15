from __future__ import annotations

from src.application.services.agent.basic import BasicAgentService
from src.application.engine_adapters.base import BaseAdapter


class AgentAdapter(BaseAdapter):
    def _resolve_service(self, ctx):
        config = ctx.get_engine_config("agent")
        agent_type = config.get("agent_type", "basic").lower()
        if agent_type in {"basic", ""}:
            return BasicAgentService()
        raise NotImplementedError("Deep agent mode is not implemented yet.")

    async def handle_query(self, ctx, query: str):
        service = self._resolve_service(ctx)
        config = ctx.get_engine_config("agent")
        if config.get("agent_instance") is None:
            await service.initialize(ctx)
        return await service.handle_query(ctx, query)
