"""Deep agent service coordinating multi-agent operations."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.application.services.base import BaseEngineService
from src.application.services.agent.deep.agent_lifecycle import create_default_deep_agent, switch_deep_agent
from src.application.services.agent.deep.conversation import handle_deep_agent_query
from src.core.providers import deepagents_provider_registry


class DeepAgentService(BaseEngineService):
    """Service responsible for deep agent mode lifecycle."""

    @staticmethod
    def _config(ctx) -> Dict[str, Any]:
        return ctx.get_engine_config("agent")

    @staticmethod
    def _available_providers() -> List[str]:
        return deepagents_provider_registry.get_available_providers()

    async def initialize(self, ctx) -> Dict[str, Any]:
        providers = self._available_providers()
        if not providers:
            return {
                "type": "error",
                "message": "No deep agent providers available. Please configure API keys.",
                "payload": {"providers": providers},
            }

        config = self._config(ctx)
        config["agent_type"] = "deep"
        config.setdefault("function_type", "research")
        config.setdefault("middleware", {})
        agent = config.get("agent_instance")

        if agent is None:
            agent, info = await create_default_deep_agent(ctx, target="deep")
        else:
            info = agent.get_info() if hasattr(agent, "get_info") else {}

        config["agent_instance"] = agent
        config["provider"] = info.get("provider") or config.get("provider")
        config["model"] = info.get("model") or config.get("model")
        if info_middleware := info.get("middleware"):
            config["middleware"] = info_middleware

        return {
            "type": "success",
            "message": "Deep agent engine initialized.",
            "payload": {
                "agent": info,
                "mode": {
                    "mode": "agent",
                    "agent_type": "deep",
                    "streaming": False,
                    "middleware": info.get("middleware"),
                    "function_type": config.get("function_type"),
                    "session_id": ctx.session_id,
                },
            },
        }

    async def handle_query(self, ctx, query: str) -> str:
        return await handle_deep_agent_query(ctx, query)

    async def switch_model(self, ctx, provider: str, model: Optional[str] = None) -> Dict[str, Any]:
        config = self._config(ctx)
        if not provider:
            provider = config.get("provider")
        providers = self._available_providers()
        if not provider:
            return {
                "type": "error",
                "message": "Provider must be specified for deep agent.",
                "payload": {"available_providers": providers},
            }
        if provider.lower() not in providers:
            return {
                "type": "error",
                "message": f"Unsupported deep agent provider: {provider}",
                "payload": {"available_providers": providers},
            }

        function_type = config.get("function_type", "research")
        model = model or config.get("model")

        agent, info = await switch_deep_agent(
            ctx,
            provider=provider,
            model=model,
            target="deep",
            function_type=function_type,
        )
        config["agent_instance"] = agent

        return {
            "type": "success",
            "message": f"Switched to {info.get('provider')} / {info.get('model')}",
            "payload": {
                "agent": info,
                "mode": {
                    "mode": "agent",
                    "agent_type": "deep",
                    "streaming": False,
                    "middleware": info.get("middleware"),
                    "function_type": config.get("function_type"),
                    "session_id": ctx.session_id,
                },
            },
        }

    def get_info(self, ctx) -> Dict[str, Any]:
        config = self._config(ctx)
        agent = config.get("agent_instance")

        if agent and hasattr(agent, "get_info"):
            # Agent is initialized, return full info
            agent_info = agent.get_info()
        else:
            # Agent not yet initialized, return config-based metadata
            agent_info = {
                "provider": config.get("provider", "unknown"),
                "model": config.get("model", "unknown"),
                "function_type": config.get("function_type", "research"),
                "tool_count": 0,
                "tools": [],
                "status": "not_initialized",
                "message": "Agent will be initialized on first query",
            }

        return {
            "agent": agent_info,
            "mode": {
                "mode": "agent",
                "agent_type": "deep",
                "streaming": False,
                "middleware": agent_info.get("middleware"),
                "function_type": config.get("function_type"),
                "session_id": ctx.session_id,
            },
        }

    def reload_config(self) -> Dict[str, Any]:
        try:
            deepagents_provider_registry.reload()
            return {"type": "success", "message": "Deep agent configuration reloaded.", "payload": {}}
        except Exception as exc:  # pylint: disable=broad-except
            return {"type": "error", "message": f"Failed to reload deep agent configuration: {exc}", "payload": {}}
