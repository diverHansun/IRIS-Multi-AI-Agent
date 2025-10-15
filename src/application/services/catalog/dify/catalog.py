"""
Dify catalog service placeholder.
"""

from __future__ import annotations

from src.application.services.catalog import BaseCatalogService


class DifyCatalogService(BaseCatalogService):
    async def get_catalog(self) -> dict:
        return {"flows": []}

    def validate_model(self, provider: str, model: str | None) -> dict:
        return {"valid": False, "error": "Dify catalog does not support model validation."}

