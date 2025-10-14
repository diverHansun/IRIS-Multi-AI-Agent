"""
LangChain engine service implementation placeholder.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.agents.langchain.managers import agent_manager
from src.llm.langchain.managers import reload_llm_config

from ..base import BaseEngineService
from ..catalog import get_catalog_service
from .agent_lifecycle import create_default_agent, switch_agent
from .conversation import handle_agent_query, handle_llm_query
from .streaming import register_llm


class LangChainService(BaseEngineService):
    """
    Service coordinating LangChain-specific operations.
    """

    @staticmethod
    def _config(ctx) -> Dict[str, Any]:
        return ctx.get_engine_config("langchain")

    @staticmethod
    def _available_providers() -> List[str]:
        return [p["provider"] for p in agent_manager.get_available_agents()]

    async def initialize(self, ctx) -> Dict[str, Any]:
        providers = self._available_providers()
        if not providers:
            return {
                "type": "error",
                "message": "No LLM providers available. Please configure API keys.",
                "payload": {"providers": providers},
            }

        config = self._config(ctx)
        agent = config.get("agent")
        if agent is None:
            agent, info = await create_default_agent(ctx)
        else:
            info = agent.get_info() if hasattr(agent, "get_info") else {}
            if hasattr(agent, "get_llm"):
                register_llm(info.get("provider"), agent.get_llm())

        return {
            "type": "success",
            "message": "LangChain engine initialized.",
            "payload": {
                "agent": info,
                "mode": {
                    "mode": config.get("mode", "llm"),
                    "streaming": config.get("streaming", True),
                    "session_id": ctx.session_id,
                },
            },
        }

    async def handle_query(self, ctx, query: str) -> str:
        config = self._config(ctx)
        mode = config.get("mode", "llm")
        streaming_enabled = bool(config.get("streaming", True))

        if mode == "agent":
            return await handle_agent_query(ctx, query)

        return await handle_llm_query(ctx, query, streaming=streaming_enabled)

    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        providers = self._available_providers()
        if provider not in providers:
            return {
                "type": "error",
                "message": f"Unsupported LLM provider: {provider}",
                "payload": {"available_providers": providers},
            }

        _, info = await switch_agent(ctx, provider=provider, model=model)
        config = self._config(ctx)

        return {
            "type": "success",
            "message": f"Switched to {info.get('provider')} / {info.get('model')}",
            "payload": {
                "agent": info,
                "mode": {
                    "mode": config.get("mode", "llm"),
                    "streaming": config.get("streaming", True),
                    "session_id": ctx.session_id,
                },
            },
        }

    def get_info(self, ctx) -> Dict[str, Any]:
        config = self._config(ctx)
        agent = config.get("agent")
        agent_info = agent.get_info() if agent and hasattr(agent, "get_info") else {}
        mode_info = {
            "mode": config.get("mode", "llm"),
            "streaming": config.get("streaming", True),
            "session_id": ctx.session_id,
        }
        return {"agent": agent_info, "mode": mode_info}

    def reload_config(self) -> Dict[str, Any]:
        success = reload_llm_config()
        if success:
            try:
                from src.agents.langchain.factories.registry import get_global_registry

                registry = get_global_registry()
                registry.clear_cache()
            except Exception:
                pass
            return {"type": "success", "message": "LLM configuration reloaded.", "payload": {}}
        return {"type": "error", "message": "Failed to reload LLM configuration.", "payload": {}}

    def set_mode(self, ctx, mode: str) -> Dict[str, Any]:
        config = self._config(ctx)
        normalized = mode.lower()
        if normalized in {"llm", "stream"}:
            config["mode"] = "llm"
            config["streaming"] = True
            return {
                "type": "success",
                "message": "Switched to LLM mode (streaming output).",
                "payload": {"mode": config["mode"], "streaming": config["streaming"]},
            }
        if normalized in {"agent", "tool"}:
            config["mode"] = "agent"
            return {
                "type": "success",
                "message": "Switched to Agent mode (tool calling).",
                "payload": {"mode": config["mode"], "streaming": config["streaming"]},
            }
        return {"type": "error", "message": "Invalid mode, use 'llm' or 'agent'."}

    def set_stream(self, ctx, action: str) -> Dict[str, Any]:
        config = self._config(ctx)
        if config.get("mode", "llm") != "llm":
            return {
                "type": "error",
                "message": "Streaming output is only available in LLM mode.",
            }

        normalized = action.lower()
        if normalized in {"on", "enable"}:
            config["streaming"] = True
            return {
                "type": "success",
                "message": "Streaming output enabled.",
                "payload": {"streaming": True},
            }
        if normalized in {"off", "disable"}:
            config["streaming"] = False
            return {
                "type": "success",
                "message": "Streaming output disabled.",
                "payload": {"streaming": False},
            }
        return {"type": "error", "message": "Invalid action, use 'on' or 'off'."}

    async def list_catalog(self) -> Dict[str, Any]:
        catalog_service = get_catalog_service("langchain")
        catalog = await catalog_service.get_catalog()
        if isinstance(catalog, dict) and "error" in catalog:
            return {
                "type": "error",
                "message": catalog.get("error", "Failed to load catalog."),
                "payload": {"kind": "llm_catalog", "catalog": catalog},
            }
        return {
            "type": "success",
            "message": "",
            "payload": {"kind": "llm_catalog", "catalog": catalog},
        }
