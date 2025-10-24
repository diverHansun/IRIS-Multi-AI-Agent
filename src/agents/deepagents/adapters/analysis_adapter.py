"""Analysis DeepAgent adapter."""

from __future__ import annotations

from .base import BaseDeepAgentAdapter


class AnalysisAdapter(BaseDeepAgentAdapter):
    """Adapter for analysis-focused deep agents."""

    function_type = "analysis"
