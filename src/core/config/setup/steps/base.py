"""
Base classes for setup steps.

Defines SetupStep abstract base, StepResult, CheckResult, and SetupContext.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Set

if TYPE_CHECKING:
    from rich.console import Console
    from src.core.config.setup.writer import EnvWriter


@dataclass
class StepResult:
    """Result of a setup step execution."""

    success: bool = False
    skipped: bool = False
    error: str = ""
    configured_items: List[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Result of a single health check item."""

    name: str
    status: str  # "pass", "fail", "warn"
    message: str
    category: str  # "llm", "agent", "tools", "dify"


@dataclass
class SetupContext:
    """Shared context passed between setup steps."""

    share_dir: Path
    env_writer: "EnvWriter"
    configured_providers: Set[str]
    console: "Console"
    version: str


class SetupStep(ABC):
    """Abstract base class for all setup steps."""

    name: str
    title: str
    skippable: bool

    @abstractmethod
    def run(self, context: SetupContext, sub_target: Optional[str] = None) -> StepResult:
        """Execute the configuration step interactively."""

    @abstractmethod
    def check(self, context: SetupContext) -> List[CheckResult]:
        """Health check for this step (used by iris doctor)."""
