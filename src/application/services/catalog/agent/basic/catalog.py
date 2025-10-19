"""
Catalog service implementation for basic-mode agents.
"""

from __future__ import annotations

from typing import Any, Dict

from src.agents.basicagents.managers import agent_manager
from src.core.providers.utils import list_ollama_models

from src.application.services.catalog import BaseCatalogService


class BasicAgentCatalogService(BaseCatalogService):
    """
    Provide catalog data for basic-mode agent providers and models.
    """

    async def get_catalog(self) -> dict:
        try:
            available_agents = agent_manager.get_available_agents()
            if not available_agents:
                return {
                    "error": "No available agent providers.",
                    "message": "Please configure at least one API key (for example ZHIPU_API_KEY or OPENAI_API_KEY).",
                }

            provider_map: Dict[str, Dict[str, Any]] = {}
            for agent in available_agents:
                provider = agent["provider"]
                entry = provider_map.setdefault(
                    provider,
                    {
                        "name": provider,
                        "provider": provider,
                        "default_model": agent.get("model"),
                        "models_detail": [],
                    },
                )
                entry["models_detail"].append(
                    {
                        "model": agent["model"],
                        "agent_type": agent.get("agent_type"),
                        "supports_tools": agent.get("supports_tools"),
                        "recommended": agent.get("recommended"),
                        "description": agent.get("description"),
                    }
                )

            catalog = {
                "providers": [],
                "recommended": [],
                "default": {},
            }

            for provider_info in provider_map.values():
                if provider_info["provider"] == "ollama":
                    try:
                        local_models = await list_ollama_models()
                        provider_info["local_models"] = local_models
                        provider_info["default_model"] = local_models[0] if local_models else None
                        if not local_models:
                            provider_info["message"] = (
                                "No local models available. Use 'ollama pull <model>' to install models."
                            )
                    except Exception as exc:
                        provider_info["error"] = str(exc)
                catalog["providers"].append(provider_info)

            if catalog["providers"]:
                first = catalog["providers"][0]
                catalog["default"] = {
                    "provider": first.get("provider"),
                    "model": first.get("default_model"),
                }

            return catalog
        except Exception as exc:
            return {"error": "Failed to load basic agent catalog.", "message": str(exc)}

    def validate_model(self, provider: str, model: str | None) -> dict:
        catalog = agent_manager.get_available_agents()
        providers = {entry["provider"]: entry for entry in catalog}
        if provider not in providers:
            available = ", ".join(sorted(providers))
            return {
                "valid": False,
                "error": f"Unsupported agent provider: {provider}",
                "message": f"Available providers: {available}",
            }
        return {"valid": True}
