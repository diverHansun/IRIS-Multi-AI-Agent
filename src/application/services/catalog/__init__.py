"""
Catalog service router for engine-specific catalog lookups.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, Type


class BaseCatalogService:
    """
    Base class for catalog services.
    """

    async def get_catalog(self) -> dict:
        raise NotImplementedError

    def validate_model(self, provider: str, model: str | None) -> dict:
        raise NotImplementedError

    def reload_config(self) -> bool:
        return True


@lru_cache(maxsize=1)
def _load_catalog_services() -> Dict[str, Type[BaseCatalogService]]:
    from src.application.services.catalog.agent.basic import BasicAgentCatalogService
    from src.application.services.catalog.agentflow import AgentFlowCatalogService
    from src.application.services.catalog.llm import LLMCatalogService
    from src.application.services.catalog.dify.catalog import DifyCatalogService

    return {
        "agent.basic": BasicAgentCatalogService,
        "agentflow": AgentFlowCatalogService,
        "llm": LLMCatalogService,
        "dify": DifyCatalogService,
    }


def get_catalog_service(engine: str) -> BaseCatalogService:
    services = _load_catalog_services()
    if engine not in services:
        raise ValueError(f"Unknown engine '{engine}'")
    service_cls = services[engine]
    return service_cls()


async def get_engine_catalog(engine: str) -> dict:
    service = get_catalog_service(engine)
    return await service.get_catalog()
