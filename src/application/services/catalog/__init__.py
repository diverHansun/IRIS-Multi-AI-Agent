"""
Catalog service router for engine-specific catalog lookups.
"""

from __future__ import annotations

from typing import Dict, Type

from .langchain.catalog import LangChainCatalogService
from .langgraph.catalog import LangGraphCatalogService
from .dify.catalog import DifyCatalogService

CATALOG_SERVICES: Dict[str, Type["BaseCatalogService"]] = {}


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


CATALOG_SERVICES = {
    "langchain": LangChainCatalogService,
    "langgraph": LangGraphCatalogService,
    "dify": DifyCatalogService,
}


def get_catalog_service(engine: str) -> BaseCatalogService:
    if engine not in CATALOG_SERVICES:
        raise ValueError(f"Unknown engine '{engine}'")
    service_cls = CATALOG_SERVICES[engine]
    return service_cls()


async def get_engine_catalog(engine: str) -> dict:
    service = get_catalog_service(engine)
    return await service.get_catalog()

