"""
Service router for engine-specific business logic.
"""

from __future__ import annotations

from typing import Dict, Type

from .base import BaseEngineService
from .langchain.service import LangChainService
from .langgraph.service import LangGraphService
from .dify.service import DifyService

ENGINE_SERVICES: Dict[str, Type[BaseEngineService]] = {
    "langchain": LangChainService,
    "langgraph": LangGraphService,
    "dify": DifyService,
}


def get_current_service(ctx) -> BaseEngineService:
    """
    Instantiate a service for the current engine.
    """
    engine = getattr(ctx, "current_engine", None)
    if engine not in ENGINE_SERVICES:
        raise ValueError(f"Unknown engine '{engine}'")
    service_cls = ENGINE_SERVICES[engine]
    return service_cls()

