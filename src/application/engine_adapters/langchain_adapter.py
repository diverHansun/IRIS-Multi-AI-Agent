"""
LangChain engine adapter.
"""

from __future__ import annotations

from ..services.langchain import LangChainService
from .base import BaseAdapter


class LangChainAdapter(BaseAdapter):
    async def handle_query(self, ctx, query: str):
        service = LangChainService()
        return await service.handle_query(ctx, query)
