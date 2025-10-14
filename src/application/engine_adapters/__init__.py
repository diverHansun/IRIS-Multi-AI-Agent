"""
Engine adapter router for delegating queries to engine services.
"""

from __future__ import annotations

from typing import Dict, Type

from .langchain_adapter import LangChainAdapter
from .langgraph_adapter import LangGraphAdapter
from .dify_adapter import DifyAdapter


class BaseAdapter:
    async def handle_query(self, ctx, query: str):
        raise NotImplementedError


ADAPTERS: Dict[str, Type[BaseAdapter]] = {
    "langchain": LangChainAdapter,
    "langgraph": LangGraphAdapter,
    "dify": DifyAdapter,
}


def get_adapter(engine: str) -> BaseAdapter:
    if engine not in ADAPTERS:
        raise ValueError(f"Unknown engine '{engine}'")
    adapter_cls = ADAPTERS[engine]
    return adapter_cls()

