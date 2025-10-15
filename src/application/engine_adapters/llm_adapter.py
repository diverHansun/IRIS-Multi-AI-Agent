from __future__ import annotations

from .base import BaseAdapter
from ..services.llm import LLMService


class LLMAdapter(BaseAdapter):
    async def handle_query(self, ctx, query: str):
        service = LLMService()
        config = ctx.get_engine_config("llm")
        if config.get("llm_instance") is None:
            await service.initialize(ctx)
        return await service.handle_query(ctx, query)
