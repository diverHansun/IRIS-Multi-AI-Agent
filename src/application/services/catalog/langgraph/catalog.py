"""
LangGraph catalog service placeholder.
"""

from __future__ import annotations

from .. import BaseCatalogService


class LangGraphCatalogService(BaseCatalogService):
    async def get_catalog(self) -> dict:
        return {"graphs": []}

    def validate_model(self, provider: str, model: str | None) -> dict:
        return {"valid": False, "error": "LangGraph model validation is not available."}

