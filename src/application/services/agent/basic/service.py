"""
Agent engine basic-mode service implementation.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.agents.basicagents.managers import agent_manager
from src.llm.managers import reload_llm_config

from src.application.services.base import BaseEngineService
from src.application.services.catalog import get_catalog_service
from src.application.services.agent.basic.agent_lifecycle import create_default_agent, switch_agent
from src.application.services.agent.basic.conversation import handle_agent_query
from src.application.services.agent.basic.streaming import register_llm


class BasicAgentService(BaseEngineService):
    """
    Service coordinating single-agent operations for the basic mode.
    """

    @staticmethod
    def _config(ctx) -> Dict[str, Any]:
        return ctx.get_engine_config("agent")

    @staticmethod
    def _available_providers() -> List[str]:
        return [meta["provider"] for meta in agent_manager.get_available_agents()]

    async def initialize(self, ctx) -> Dict[str, Any]:
        providers = self._available_providers()
        if not providers:
            return {
                "type": "error",
                "message": "No agent providers available. Please configure API keys.",
                "payload": {"providers": providers},
            }

        config = self._config(ctx)
        config["agent_type"] = "basic"
        agent = config.get("agent_instance")
        if agent is None:
            agent, info = await create_default_agent(ctx, target="basic")
        else:
            info = agent.get_info() if hasattr(agent, "get_info") else {}
            if hasattr(agent, "get_llm"):
                register_llm(info.get("provider"), agent.get_llm())

        config["agent_instance"] = agent

        return {
            "type": "success",
            "message": "Agent engine (basic mode) initialized.",
            "payload": {
                "agent": info,
                "mode": {
                    "mode": "agent",
                    "agent_type": "basic",
                    "streaming": bool(config.get("streaming", True)),
                    "session_id": ctx.session_id,
                },
            },
        }

    async def handle_query(self, ctx, query: str) -> str:
        return await handle_agent_query(ctx, query)

    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        providers = self._available_providers()
        if provider not in providers:
            return {
                "type": "error",
                "message": f"Unsupported agent provider: {provider}",
                "payload": {"available_providers": providers},
            }

        agent, info = await switch_agent(ctx, provider=provider, model=model, target="basic")
        config = self._config(ctx)
        config["agent_instance"] = agent

        return {
            "type": "success",
            "message": f"Switched to {info.get('provider')} / {info.get('model')}",
            "payload": {
                "agent": info,
                "mode": {
                    "mode": "agent",
                    "agent_type": config.get("agent_type", "basic"),
                    "streaming": bool(config.get("streaming", True)),
                    "session_id": ctx.session_id,
                },
            },
        }

    def get_info(self, ctx) -> Dict[str, Any]:
        config = self._config(ctx)
        agent = config.get("agent_instance")
        agent_info = agent.get_info() if agent and hasattr(agent, "get_info") else {}
        return {
            "agent": agent_info,
            "mode": {
                "mode": "agent",
                "agent_type": config.get("agent_type", "basic"),
                "streaming": bool(config.get("streaming", True)),
                "session_id": ctx.session_id,
            },
        }

    def reload_config(self) -> Dict[str, Any]:
        success = reload_llm_config()
        if success:
            try:
                from src.agents.basicagents.factories.registry import get_global_registry

                registry = get_global_registry()
                registry.clear_cache()
            except Exception:
                pass
            return {"type": "success", "message": "Agent configuration reloaded.", "payload": {}}
        return {"type": "error", "message": "Failed to reload agent configuration.", "payload": {}}

    async def list_catalog(self) -> Dict[str, Any]:
        catalog_service = get_catalog_service("agent.basic")
        catalog = await catalog_service.get_catalog()
        if isinstance(catalog, dict) and "error" in catalog:
            return {
                "type": "error",
                "message": catalog.get("error", "Failed to load basic agent catalog."),
                "payload": {"kind": "agent_catalog", "catalog": catalog},
            }
        return {
            "type": "success",
            "message": "",
            "payload": {"kind": "agent_catalog", "catalog": catalog},
        }

