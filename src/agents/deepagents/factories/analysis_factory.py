"""Factory for analysis-focused DeepAgents."""

from __future__ import annotations

from src.agents.deepagents.factories.base import BaseDeepAgentFactory
from src.agents.deepagents.instances.analysis_agent import AnalysisAgent


class AnalysisFactory(BaseDeepAgentFactory):
    """Create analytical DeepAgent instances."""

    function_type = "analysis"
    agent_cls = AnalysisAgent

    def __init__(self) -> None:
        super().__init__(description="Analysis-oriented DeepAgent focused on insights.")
