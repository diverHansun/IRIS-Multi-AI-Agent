"""Factory for research-focused DeepAgents."""

from __future__ import annotations

from src.agents.deepagents.factories.base import BaseDeepAgentFactory
from src.agents.deepagents.instances.research_agent import ResearchAgent


class ResearchFactory(BaseDeepAgentFactory):
    """Create research DeepAgent instances."""

    function_type = "research"
    agent_cls = ResearchAgent

    def __init__(self) -> None:
        super().__init__(description="Research-focused multi-agent coordination.")
