"""Research DeepAgent adapter."""

from __future__ import annotations

from .base import BaseDeepAgentAdapter


class ResearchAdapter(BaseDeepAgentAdapter):
    """Adapter for research-focused deep agents."""

    function_type = "research"
