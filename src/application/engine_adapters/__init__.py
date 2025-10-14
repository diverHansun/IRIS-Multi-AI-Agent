"""
Engine adapter router used to dispatch queries to engine services.
"""

from __future__ import annotations

from typing import Dict, Type

from .base import BaseAdapter
from .dify_adapter import DifyAdapter
from .langchain_adapter import LangChainAdapter
from .langgraph_adapter import LangGraphAdapter


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
