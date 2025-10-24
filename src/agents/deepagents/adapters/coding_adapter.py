"""Coding DeepAgent adapter."""

from __future__ import annotations

from .base import BaseDeepAgentAdapter


class CodingAdapter(BaseDeepAgentAdapter):
    """Adapter for coding-focused deep agents."""

    function_type = "coding"
