"""Adapter implementations for DeepAgents."""

from .analysis_adapter import AnalysisAdapter
from .coding_adapter import CodingAdapter
from .research_adapter import ResearchAdapter
from .base import BaseDeepAgentAdapter

__all__ = [
    "AnalysisAdapter",
    "CodingAdapter",
    "ResearchAdapter",
    "BaseDeepAgentAdapter",
]
