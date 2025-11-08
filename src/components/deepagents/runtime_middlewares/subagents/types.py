"""Data structures for subagent specifications.

This module defines the core data types used to describe subagents
in the DeepAgents middleware system.

Following SOLID principles:
- SRP: This module only defines data structures, no business logic
- OCP: New subagent types can be added through configuration without code changes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Sequence, Optional


@dataclass(slots=True)
class SubAgent:
    """Lightweight specification describing a subagent to the orchestrator.

    This dataclass represents the complete configuration for a subagent,
    including its identity, capabilities, and runtime constraints.

    Attributes:
        name: Unique identifier for the subagent
        description: Human-readable description of the subagent's purpose
        system_prompt: System prompt defining the subagent's behavior
        tools: List of tool names or instances available to the subagent
        model: LLM model instance or identifier for the subagent
        metadata: Additional metadata for the subagent
        recursion_limit: Maximum recursion depth allowed
        step_timeout: Timeout in seconds for a single step
        max_execution_time: Maximum total execution time in seconds
        middleware: List of middleware instances to apply
        checkpointer: Checkpointer instance for state management
        display_config: Configuration for display and logging
    """

    name: str
    description: str
    system_prompt: str
    tools: Sequence[Any] = field(default_factory=list)
    model: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    recursion_limit: Optional[int] = None
    step_timeout: Optional[float] = None
    max_execution_time: Optional[float] = None
    middleware: Sequence[Any] = field(default_factory=list)
    checkpointer: Optional[Any] = None
    display_config: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CompiledSubAgent:
    """Placeholder for a fully compiled and ready-to-use subagent runnable.

    This dataclass wraps a pre-compiled subagent runnable, allowing it to be
    used directly without additional compilation steps.

    Attributes:
        name: Unique identifier for the subagent
        description: Human-readable description of the subagent's purpose
        runnable: The compiled runnable instance
    """

    name: str
    description: str
    runnable: Any
