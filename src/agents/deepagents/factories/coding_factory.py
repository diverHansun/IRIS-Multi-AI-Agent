"""Factory for coding-focused DeepAgents."""

from __future__ import annotations

from src.agents.deepagents.factories.base import BaseDeepAgentFactory
from src.agents.deepagents.instances.coding_agent import CodingAgent


class CodingFactory(BaseDeepAgentFactory):
    """Create coding DeepAgent instances."""

    function_type = "coding"
    agent_cls = CodingAgent

    def __init__(self) -> None:
        super().__init__(description="Coding-oriented DeepAgent with tooling support.")
