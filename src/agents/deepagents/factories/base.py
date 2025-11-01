"""Base factory classes for DeepAgents."""

from __future__ import annotations

import logging
from abc import ABC
from typing import Any, Dict, List, Optional, Tuple, Type

from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter
from src.agents.deepagents.instances.base_deep_agent import BaseDeepAgent
from src.agents.deepagents.managers.subagent_manager import SubAgentManager
from src.components.deepagents.runtime import create_deep_agent_runtime
from src.components.deepagents.runtime_middlewares import SubAgent
from src.components.shared.tools.unified_manager import UnifiedToolManager
from src.components.shared.memory.checkpointer import create_default_checkpointer

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
        middleware_config: Dict[str, Any],
        global_memory_manager: Optional[Any] = None,
        **user_params: Any,
    ) -> BaseDeepAgent:
        """Create the deep agent."""
        resolved_middleware = self._resolve_middleware_config(adapter, middleware_config)

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

        # Inject virtual filesystem tools if enabled (SOLID: SRP - Factory manages tool composition)
        tools, filesystem_middlewares = self._inject_filesystem_tools(tools, resolved_middleware)
        tool_names = [tool.name if hasattr(tool, 'name') else tool.__name__ for tool in tools] if tools else []

        # Get LLM parameters from adapter
        model_settings = adapter.get_llm_params()

        # Initialize checkpointer for memory persistence if not provided
        checkpointer = user_params.get("checkpointer")
        if checkpointer is None and global_memory_manager is not None:
            checkpointer_wrapper = create_default_checkpointer()
            checkpointer = checkpointer_wrapper.checkpointer
            logger.info("Created default checkpointer for deep agent with global memory")

        # Get runtime and safety config from adapter
        runtime_config = adapter.get_runtime_config()
        safety_config = adapter.get_safety_config()

        hitl_config = safety_config.get("hitl_config", {}) or {}
        interrupt_on = user_params.get("interrupt_on") or self._build_interrupt_config(hitl_config)
        recursion_limit = runtime_config.get("recursion_limit", 1000)
        step_timeout = runtime_config.get("step_timeout")
        stream_mode = runtime_config.get("stream_mode", "updates")
        max_execution_time = safety_config.get("max_execution_time")

        filesystem_config = resolved_middleware.get("filesystem", {})
        virtual_config = filesystem_config.get("virtual")
        if not isinstance(virtual_config, dict):
            virtual_config = filesystem_config if isinstance(filesystem_config, dict) else {}
        use_long_term_memory = bool(virtual_config.get("long_term_memory", False))

        runtime = create_deep_agent_runtime(
            model=adapter.get_model_identifier(),
            system_prompt=system_prompt,
            tools=tools,
            model_settings=model_settings,
            middleware_config=resolved_middleware,
            subagents=subagent_specs,
            use_long_term_memory=use_long_term_memory,
            interrupt_on=interrupt_on,
            checkpointer=checkpointer,
            store=user_params.get("store"),
            cache=user_params.get("cache"),
            name=user_params.get("name"),
            debug=user_params.get("debug", False),
            recursion_limit=recursion_limit,
            step_timeout=step_timeout,
            stream_mode=stream_mode,
            max_execution_time=max_execution_time,
            filesystem_middlewares=filesystem_middlewares,  # DRY: reuse instances from tool injection
        )

        # Get display config from adapter
        display_config = adapter.get_display_config()
        metadata_config = adapter.get_metadata()

        streaming_preferences = {
            "stream_mode": stream_mode,
            "streaming_enabled": display_config.get("streaming_enabled", True),
            "show_reasoning_steps": display_config.get("show_reasoning_steps", True),
            "show_tool_calls": display_config.get("show_tool_calls", True),
            "show_tool_results": display_config.get("show_tool_results", True),
            "show_subagent_delegations": display_config.get("show_subagent_delegations", True),
            "show_elapsed_time": display_config.get("show_elapsed_time", True),
        }
        safety_limits = {
            "max_execution_time": safety_config.get("max_execution_time"),
            "max_recursion_limit": recursion_limit,
            "max_input_tokens": metadata_config.get("max_input_tokens"),
            "max_output_tokens": metadata_config.get("max_output_tokens"),
        }

        metadata = {
            "system_prompt": system_prompt,
            "middleware": resolved_middleware,
            "subagents": subagent_metadata,
            "model_identifier": adapter.get_model_identifier(),
            "tools": tool_names,
            "tool_count": len(tool_names),
            "streaming": streaming_preferences,
            "safety": safety_limits,
            "hitl_config": hitl_config,
            "runtime_config": runtime_config,
            "display_config": display_config,
        }
        metadata.update(adapter.build_metadata())

        agent = self.agent_cls(
            adapter=adapter,
            metadata=metadata,
            global_memory_manager=global_memory_manager,
        )
        agent.set_runtime(runtime)
        return agent

    def _resolve_middleware_config(
        self,
        adapter: BaseDeepAgentAdapter,
        global_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve middleware configuration.

        Args:
            adapter: Adapter providing middleware config
            global_config: Global middleware configuration

        Returns:
            Resolved middleware configuration
        """
        provider_middleware = adapter.get_middleware_config()
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
    ) -> Tuple[List[SubAgent], List[Dict[str, Any]]]:
        """
        Build SubAgent specifications for SubAgentMiddleware.

        This method creates subagent specs using the new SubAgentsProviderRegistry
        which provides clean, categorized parameters.

        Args:
            adapter: Deep agent adapter for provider info
            subagent_manager: Manager with SubAgentsProviderRegistry
            middleware_config: Middleware configuration

        Returns:
            Tuple of (subagent_specs, subagent_metadata)
        """
        specs: List[SubAgent] = []
        metadata: List[Dict[str, Any]] = []

        for subagent_type in subagent_manager.get_available_subagents().keys():
            try:
                # Get complete categorized configuration from new registry
                config = subagent_manager.get_subagent_config(subagent_type)

                llm_config = config["llm_config"]
                provider = llm_config["provider"]
                model = llm_config["model"]

                # Get model identifier for init_chat_model
                model_identifier = adapter.get_model_identifier_for(provider, model)

                # Create LLM instance using ONLY clean LLM parameters
                from langchain.chat_models import init_chat_model

                # Use the clean parameter extraction method from registry
                llm_params = subagent_manager.subagents_registry.get_llm_params_only(
                    subagent_type
                )

                logger.debug(
                    f"Creating subagent '{subagent_type}' LLM with params: {list(llm_params.keys())}"
                )

                # Create LLM instance
                subagent_llm = init_chat_model(model_identifier, **llm_params)

            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "Failed to resolve subagent configuration for %s: %s",
                    subagent_type,
                    exc,
                    exc_info=True,
                )
                continue

            # Get system prompt and description from config
            system_prompt = config["system_prompt"]
            description = config["description"]

            # Get runtime limits from config
            runtime_limits = config["runtime_limits"]
            recursion_limit = runtime_limits.get("recursion_limit")
            step_timeout = runtime_limits.get("step_timeout")
            max_execution_time = runtime_limits.get("max_execution_time")

            # Get agent_config, display_config, and metadata from config
            agent_config = config["agent_config"]
            display_config = config["display_config"]
            metadata_cfg = config["metadata"]

            # Validate and extract parameters with type checking
            tools = agent_config.get("tools", [])
            if tools and not isinstance(tools, list):
                logger.warning(
                    f"SubAgent '{subagent_type}' tools config invalid, using empty list"
                )
                tools = []

            middleware_cfg = agent_config.get("middleware", [])
            if middleware_cfg and not isinstance(middleware_cfg, list):
                logger.warning(
                    f"SubAgent '{subagent_type}' middleware config invalid, using empty list"
                )
                middleware_cfg = []

            checkpointer = agent_config.get("checkpointer", False)

            logger.debug(
                f"Creating SubAgent '{subagent_type}' with recursion_limit={recursion_limit}, "
                f"step_timeout={step_timeout}, max_execution_time={max_execution_time}, "
                f"tools={tools}, middleware={middleware_cfg}, checkpointer={checkpointer}"
            )

            # Build SubAgent spec with all configuration parameters
            subagent_spec = SubAgent(
                name=config["name"],
                description=description,
                system_prompt=system_prompt,
                tools=tools,  # Use validated configured tools
                model=subagent_llm,  # Pass LLM instance
                recursion_limit=recursion_limit,
                step_timeout=step_timeout,  # Pass step_timeout (single step timeout)
                max_execution_time=max_execution_time,  # Pass max_execution_time (total execution timeout)
                middleware=middleware_cfg,  # Pass validated middleware config
                checkpointer=checkpointer,  # Pass checkpointer config
                display_config=display_config,  # Pass display_config
                metadata=metadata_cfg,  # Pass metadata from config
            )
            specs.append(subagent_spec)

            # Build metadata for tracking and display
            metadata.append(
                {
                    "name": config["name"],
                    "model": model_identifier,
                    "tools": tools,  # Record validated configured tools
                    "description": description,
                    "safety": {
                        "max_execution_time": runtime_limits.get("max_execution_time"),
                        "max_recursion_limit": runtime_limits.get("recursion_limit"),
                        "streaming_enabled": display_config.get("streaming_enabled"),
                    },
                    "middleware": middleware_cfg,  # Record validated configured middleware
                    "checkpointer": checkpointer,  # Record checkpointer config
                }
            )

        logger.info(f"Built {len(specs)} subagent specifications")
        return specs, metadata

    @staticmethod
    def _build_interrupt_config(hitl_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not hitl_config:
            return None
        interrupt_on: Dict[str, Any] = {}
        dangerous_tools = hitl_config.get("dangerous_tools", [])
        for tool in dangerous_tools:
            interrupt_on[tool] = {"allowed_decisions": ["approve", "reject"]}

        for tool, settings in (hitl_config.get("tools") or {}).items():
            allow_auto = settings.get("allow_auto_approve", True)
            if allow_auto is False or tool in interrupt_on:
                interrupt_on.setdefault(tool, {"allowed_decisions": ["approve", "reject"]})
            description = settings.get("warning_message")
            if description:
                interrupt_on.setdefault(tool, {"allowed_decisions": ["approve", "reject"]})
                interrupt_on[tool]["description"] = description

        return interrupt_on or None


    def _inject_filesystem_tools(self, tools, middleware_config):
        """Inject enabled filesystem toolsets and return instantiated middlewares."""
        fs_config = middleware_config.get("filesystem", {})

        virtual_config = fs_config.get("virtual")
        real_config = fs_config.get("real")

        # Backwards compatibility: treat plain dict as virtual configuration
        if virtual_config is None and real_config is None and isinstance(fs_config, dict):
            virtual_config = fs_config

        middlewares: List[Any] = []
        updated_tools = list(tools) if tools else []

        if isinstance(virtual_config, dict) and virtual_config.get("enabled", True):
            try:
                from src.components.deepagents.runtime_middlewares.virtual_filesystem import (
                    VirtualFilesystemMiddleware,
                )

                virtual_middleware = VirtualFilesystemMiddleware(
                    long_term_memory=virtual_config.get("long_term_memory", False),
                    tool_token_limit_before_evict=virtual_config.get("tool_token_limit_before_evict"),
                )
                vs_tools = virtual_middleware.get_tools()
                if vs_tools:
                    updated_tools.extend(vs_tools)
                    logger.info("Injected %d virtual filesystem tools", len(vs_tools))
                middlewares.append(virtual_middleware)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to inject virtual filesystem tools: %s", exc, exc_info=True)

        if isinstance(real_config, dict) and real_config.get("enabled", False):
            try:
                from src.components.deepagents.runtime_middlewares.real_filesystem import (
                    RealFilesystemMiddleware,
                )

                real_middleware = RealFilesystemMiddleware(config=real_config)
                rs_tools = real_middleware.get_tools()
                if rs_tools:
                    updated_tools.extend(rs_tools)
                    logger.info("Injected %d real filesystem tools", len(rs_tools))
                middlewares.append(real_middleware)
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Failed to inject real filesystem tools: %s", exc, exc_info=True)

        return updated_tools or tools, middlewares

    def describe(self) -> Dict[str, Any]:
        """Return metadata describing the factory."""
        return {
            "function_type": self.function_type,
            "description": self.description,
        }
