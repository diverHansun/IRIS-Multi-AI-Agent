"""LLM catalog service implementation."""

from __future__ import annotations

from typing import Any, Dict, List

from src.llm.managers import get_available_providers

from src.application.services.catalog import BaseCatalogService


class LLMCatalogService(BaseCatalogService):
    async def get_catalog(self) -> dict:
        try:
            providers: List[Dict[str, Any]] = get_available_providers()
            return {"providers": providers}
        except Exception as exc:
            return {"error": "Failed to load LLM catalog.", "message": str(exc)}

    def validate_model(self, provider: str, model: str | None) -> dict:
        providers = {entry["provider"]: entry for entry in get_available_providers()}
        if provider not in providers:
            available = ", ".join(sorted(providers))
            return {"valid": False, "error": f"Unsupported LLM provider: {provider}", "message": f"Available providers: {available}"}
        return {"valid": True}
