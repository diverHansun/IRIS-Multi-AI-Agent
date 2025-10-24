"""Base factory classes for DeepAgents."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, Type

from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter
from src.agents.deepagents.instances.base_deep_agent import BaseDeepAgent
from src.agents.deepagents.managers.subagent_manager import SubAgentManager
from src.components.deepagents.runtime import create_deep_agent_runtime
from src.components.deepagents.runtime_middlewares import SubAgent
from src.components.shared.tools.unified_manager import UnifiedToolManager

logger = logging.getLogger(__name__)


class BaseDeepAgentFactory(ABC):
    """Abstract factory for building deep agent instances."""

    function_type: str
    agent_cls: Type[BaseDeepAgent] = BaseDeepAgent

    def __init__(self, *, description: str = "") -> None:
        self.description = description

    async def create_agent(
        self,
        *,
        provider: str,
        model: str,
        adapter: BaseDeepAgentAdapter,
        subagent_manager: SubAgentManager,
        provider_config: Dict[str, Any],
        middleware_config: Dict[str, Any],
        **user_params: Any,
    ) -> BaseDeepAgent:
        """Create the deep agent."""
        resolved_middleware = self._resolve_middleware_config(provider_config, middleware_config)

        available_subagents = subagent_manager.get_available_subagents()
        system_prompt = adapter.get_system_prompt(
            subagents=available_subagents.keys(),
            tools=user_params.get("tools"),
            task_description=user_params.get("task_description"),
            user_context=user_params.get("user_context"),
        )

        subagent_specs, subagent_metadata = self._build_subagent_specs(
            adapter=adapter,
            subagent_manager=subagent_manager,
            middleware_config=resolved_middleware,
        )

        tools = user_params.get("tools")
        tool_manager = None
        if not tools:
            tool_manager = UnifiedToolManager(auto_register_defaults=True)
            await tool_manager.initialize_all()
            tools = tool_manager.get_all_tools()
        tool_names = [getattr(tool, "name", repr(tool)) for tool in tools] if tools else []

        model_settings = adapter.get_model_parameters()
        if adapter.base_url:
            model_settings["base_url"] = adapter.base_url

        runtime = create_deep_agent_runtime(
            model=adapter.get_model_identifier(),
            system_prompt=system_prompt,
            tools=tools,
            model_settings=model_settings,
            middleware_config=resolved_middleware,
            subagents=subagent_specs,
            use_long_term_memory=resolved_middleware.get("filesystem", {}).get("long_term_memory", False),
            interrupt_on=user_params.get("interrupt_on"),
            checkpointer=user_params.get("checkpointer"),
            store=user_params.get("store"),
            cache=user_params.get("cache"),
            name=user_params.get("name"),
            debug=user_params.get("debug", False),
        )

        metadata = {
            "system_prompt": system_prompt,
            "middleware": resolved_middleware,
            "subagents": subagent_metadata,
            "provider_config": provider_config,
            "model_identifier": adapter.get_model_identifier(),
            "tools": tool_names,
            "tool_count": len(tool_names),
        }
        metadata.update(adapter.build_metadata())

        agent = self.agent_cls(adapter=adapter, metadata=metadata)
        agent.set_runtime(runtime)
        return agent

    def _resolve_middleware_config(
        self,
        provider_config: Dict[str, Any],
        global_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        provider_middleware = provider_config.get("middleware", {})
        resolved = {}
        for key in ("filesystem", "subagents", "patch_tool_calls"):
            value = provider_middleware.get(key)
            if isinstance(value, dict):
                resolved[key] = value
            elif isinstance(value, str) and value != "default":
                resolved[key] = global_config.get(value, {})
            else:
                resolved[key] = global_config.get(key, {})
        return resolved

    def _build_subagent_specs(
        self,
        *,
        adapter: BaseDeepAgentAdapter,
        subagent_manager: SubAgentManager,
        middleware_config: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        specs: List[SubAgent] = []
        metadata: List[Dict[str, Any]] = []
        configured_subagents = middleware_config.get("subagents", {}).get("subagents", {})

        for subagent_type in subagent_manager.get_available_subagents().keys():
            try:
                config = subagent_manager.get_subagent_config(subagent_type)
                model_identifier = adapter.get_model_identifier_for(config["provider"], config["model"])
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to resolve subagent configuration for %s: %s", subagent_type, exc)
                continue

            prompt = adapter.get_subagent_prompt(subagent_type)
            tools = configured_subagents.get(subagent_type, {}).get("tools", [])
            description = configured_subagents.get(subagent_type, {}).get(
                "description",
                f"{subagent_type} specialist",
            )
            subagent_spec = SubAgent(
                name=subagent_type,
                description=description,
                system_prompt=prompt,
                tools=tools,
                model=model_identifier,
                metadata={
                    "provider": config["provider"],
                    "model_config": config,
                },
            )
            specs.append(subagent_spec)
            metadata.append(
                {
                    "name": subagent_type,
                    "model": model_identifier,
                    "tools": tools,
                    "description": subagent_spec["description"],
                }
            )
        return specs, metadata

    def describe(self) -> Dict[str, Any]:
        """Return metadata describing the factory."""
        return {
            "function_type": self.function_type,
            "description": self.description,
        }
