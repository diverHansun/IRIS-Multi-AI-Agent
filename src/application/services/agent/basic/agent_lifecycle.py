"""
Agent lifecycle helpers for the basic-mode agent service.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from src.agents.basicagents.managers import agent_manager

from src.application.services.agent.basic.streaming import register_llm


def _agent_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("agent")


async def _instantiate_agent(ctx, provider: str | None, model: str | None) -> Any:
    # If no provider specified, use first available provider
    if not provider:
        available_agents = agent_manager.get_available_agents()
        if available_agents:
            provider = available_agents[0]["provider"]
        else:
            raise RuntimeError("No basic agent providers available")

    agent = await agent_manager.create_agent(
        provider=provider,
        model=model,
        global_memory_manager=ctx.global_memory,
    )

    if hasattr(agent, "verbose"):
        agent.verbose = True
    if hasattr(agent, "temperature"):
        agent.temperature = 0.1

    return agent


def _update_config(config: Dict[str, Any], provider: str | None, model: str | None, agent: Any) -> Dict[str, Any]:
    info = agent.get_info() if hasattr(agent, "get_info") else {}
    config["provider"] = info.get("provider", provider)
    config["model"] = info.get("model", model)
    config["agent_instance"] = agent

    if hasattr(agent, "get_llm"):
        llm = agent.get_llm()
        register_llm(config["provider"], llm)

    return info


async def create_default_agent(ctx, target: str = "basic") -> Tuple[Any, Dict[str, Any]]:
    """
    Create the default agent for the supplied target mode.
    """
    config = _agent_config(ctx)
    config["agent_type"] = target

    provider = config.get("provider")
    model = config.get("model")
    agent = await _instantiate_agent(ctx, provider, model)
    info = _update_config(config, provider, model, agent)
    return agent, info


async def switch_agent(ctx, *, provider: str, model: str | None, target: str = "basic") -> Tuple[Any, Dict[str, Any]]:
    """
    Switch the active agent to a new provider/model pair.
    """
    config = _agent_config(ctx)
    config["agent_type"] = target

    agent = await _instantiate_agent(ctx, provider, model)
    info = _update_config(config, provider, model, agent)
    return agent, info
