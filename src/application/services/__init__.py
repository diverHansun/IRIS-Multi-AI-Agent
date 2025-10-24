"""Service router for engine-specific business logic."""

from __future__ import annotations

from src.application.services.base import BaseEngineService


def get_current_service(ctx) -> BaseEngineService:
    engine = getattr(ctx, "current_engine", None)
    if engine == "llm":
        from src.application.services.llm import LLMService

        return LLMService()
    if engine == "agent":
        agent_type = ctx.get_engine_config("agent").get("agent_type", "basic").lower()
        if agent_type in {"basic", ""}:
            from src.application.services.agent.basic import BasicAgentService

            return BasicAgentService()
        if agent_type == "deep":
            from src.application.services.agent.deep import DeepAgentService

            return DeepAgentService()
        raise ValueError(f"Unknown agent type '{agent_type}'")
    if engine == "agentflow":
        from src.application.services.agentflow import AgentFlowService

        return AgentFlowService()
    if engine == "dify":
        from src.application.services.dify.service import DifyService

        return DifyService()
    raise ValueError(f"Unknown engine '{engine}'")
