"""Lifecycle helpers for deep agent service."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from src.agents.deepagents.managers import deep_agent_manager
from src.core.providers import deepagents_provider_registry


def _agent_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("agent")


def _default_provider_and_model() -> Tuple[str, str]:
    providers = deepagents_provider_registry.list_providers()
    if not providers:
        raise RuntimeError("No deep agent providers configured.")
    provider_name, provider_config = next(iter(providers.items()))
    models = provider_config.get("models", {})
    if not models:
        raise RuntimeError(f"No models configured for provider {provider_name}.")
    model_name = next(iter(models.keys()))
    return provider_name, model_name


async def _instantiate_agent(
    ctx,
    provider: str | None,
    model: str | None,
    function_type: str,
) -> Tuple[Any, str, str]:
    """
    Instantiate deep agent with isolated memory system.

    Deep mode creates its own GlobalMemoryManager and MemorySyncAdapter
    with agent_mode="deep" to ensure storage isolation from basic/llm modes.
    """
    from src.components.shared.memory import GlobalMemoryManager, MemorySyncAdapter

    providers = deepagents_provider_registry.list_providers()

    resolved_provider = (provider or "").lower()
    if resolved_provider not in providers:
        resolved_provider, resolved_model = _default_provider_and_model()
    else:
        model_map = providers[resolved_provider].get("models", {})
        if not model_map:
            raise RuntimeError(f"No models configured for provider {resolved_provider}.")
        if not model or model not in model_map:
            resolved_model = next(iter(model_map.keys()))
        else:
            resolved_model = model

    # Create isolated memory system for deep mode
    deep_global_memory = GlobalMemoryManager(agent_mode="deep", max_messages=50)
    deep_memory_sync = MemorySyncAdapter(deep_global_memory, agent_mode="deep")

    agent = await deep_agent_manager.create_deep_agent(
        provider=resolved_provider,
        model=resolved_model,
        global_memory_manager=deep_global_memory,
        memory_sync=deep_memory_sync,
        function_type=function_type,
    )

    # Attach memory_sync to agent for conversation handling
    setattr(agent, "memory_sync", deep_memory_sync)

    return agent, resolved_provider, resolved_model


def _update_config(
    config: Dict[str, Any],
    provider: str,
    model: str,
    function_type: str,
    agent: Any,
) -> Dict[str, Any]:
    info = agent.get_info() if hasattr(agent, "get_info") else {}
    config["provider"] = provider
    config["model"] = model
    config["function_type"] = function_type
    config["agent_instance"] = agent
    return info


async def create_default_deep_agent(ctx, target: str = "deep") -> Tuple[Any, Dict[str, Any]]:
    config = _agent_config(ctx)
    config["agent_type"] = target
    function_type = config.get("function_type", "research")
    config["function_type"] = function_type

    provider = config.get("provider")
    model = config.get("model")
    agent, resolved_provider, resolved_model = await _instantiate_agent(ctx, provider, model, function_type)
    info = _update_config(config, resolved_provider, resolved_model, function_type, agent)
    return agent, info


async def switch_deep_agent(
    ctx,
    *,
    provider: str,
    model: Optional[str],
    target: str = "deep",
    function_type: Optional[str] = None,
) -> Tuple[Any, Dict[str, Any]]:
    config = _agent_config(ctx)
    config["agent_type"] = target
    function_type = function_type or config.get("function_type", "research")
    config["function_type"] = function_type

    agent, resolved_provider, resolved_model = await _instantiate_agent(ctx, provider, model, function_type)
    info = _update_config(config, resolved_provider, resolved_model, function_type, agent)
    return agent, info
