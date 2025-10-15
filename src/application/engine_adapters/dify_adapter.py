"""
Dify engine adapter.
"""

from __future__ import annotations

from src.application.services.dify import DifyService
from src.application.engine_adapters.base import BaseAdapter


class DifyAdapter(BaseAdapter):
    async def handle_query(self, ctx, query: str):
        service = DifyService()
        return await service.handle_query(ctx, query)

