"""
AgentFlow catalog service placeholder.
"""

from __future__ import annotations

from src.application.services.catalog import BaseCatalogService


class AgentFlowCatalogService(BaseCatalogService):
    async def get_catalog(self) -> dict:
        return {"graphs": []}

    def validate_model(self, provider: str, model: str | None) -> dict:
        return {"valid": False, "error": "AgentFlow catalog validation is not available yet."}
