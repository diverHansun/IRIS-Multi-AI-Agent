"""
ConfigValidator -- Health check for all configuration items.

Used by /iris doctor to check configuration health status.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.rule import Rule

from src.core.config.setup.steps.base import CheckResult, SetupContext
from src.core.config.setup.steps.llm import LLMSetupStep
from src.core.config.setup.steps.agent import AgentSetupStep
from src.core.config.setup.steps.tools import ToolsSetupStep
from src.core.config.setup.steps.dify import DifySetupStep
from src.core.config.setup.writer import EnvWriter

logger = logging.getLogger(__name__)

# Core-layer color constants (no dependency on application layer)
_COLORS: Dict = {
    "success": "green",
    "warning": "yellow",
    "error": "red",
    "text_dim": "dim",
}


def _get_colors() -> Dict:
    return _COLORS


class ConfigValidator:
    """Configuration health checker."""

    def __init__(
        self,
        share_dir: Optional[Path] = None,
        console: Optional[Console] = None,
    ):
        self._share_dir = share_dir or Path.home() / ".iris"
        self._console = console or Console()

    def check_all(self) -> List[CheckResult]:
        """Run all health checks."""
        context = self._build_context()
        results: List[CheckResult] = []

        for step in self._get_all_steps():
            results.extend(step.check(context))

        return results

    def check_category(self, category: str) -> List[CheckResult]:
        """Run health checks for a specific category."""
        context = self._build_context()
        step = self._resolve_step(category)
        if step is None:
            return []
        return step.check(context)

    def print_report(self, results: List[CheckResult]) -> None:
        """Print formatted health check report."""
        colors = _get_colors()
        console = self._console

        console.print()
        console.print("IRIS Configuration Health Check", style="bold")
        console.print(Rule(style=colors.get("text_dim", "dim")))

        # Group by category
        categories: Dict[str, List[CheckResult]] = {}
        for r in results:
            categories.setdefault(r.category, []).append(r)

        # Category display names
        cat_names = {
            "llm": "LLM",
            "agent": "Agent",
            "tools": "Tools",
            "dify": "Dify",
        }

        icon_map = {"pass": "[*]", "fail": "[x]", "warn": "[!]"}
        style_map = {
            "pass": colors.get("success", "green"),
            "fail": colors.get("error", "red"),
            "warn": colors.get("warning", "yellow"),
        }

        for cat_key in ["llm", "agent", "tools", "dify"]:
            cat_results = categories.get(cat_key, [])
            if not cat_results:
                continue

            console.print(f"\n{cat_names.get(cat_key, cat_key)}:", style="bold")
            for r in cat_results:
                icon = icon_map.get(r.status, "[ ]")
                style = style_map.get(r.status, "")
                console.print(f"  {icon} {r.message}", style=style)

        # Summary
        pass_count = sum(1 for r in results if r.status == "pass")
        fail_count = sum(1 for r in results if r.status == "fail")
        warn_count = sum(1 for r in results if r.status == "warn")

        console.print()
        console.print(Rule(style=colors.get("text_dim", "dim")))
        console.print(
            f"Summary: {pass_count} passed, {fail_count} failed, {warn_count} warnings",
            style="bold",
        )

        if fail_count > 0:
            console.print(
                "\nRun /iris setup to fix configuration issues.",
                style=colors.get("warning", "yellow"),
            )

    def _build_context(self) -> SetupContext:
        env_writer = EnvWriter(self._share_dir / ".env")
        pre_configured = set(env_writer.get_configured_providers())

        try:
            from src.core.config.setup.wizard import get_package_version
            version = get_package_version()
        except Exception:
            version = "0.0.0"

        return SetupContext(
            share_dir=self._share_dir,
            env_writer=env_writer,
            configured_providers=pre_configured,
            console=self._console,
            version=version,
        )

    def _get_all_steps(self) -> list:
        return [
            LLMSetupStep(),
            AgentSetupStep(),
            ToolsSetupStep(),
            DifySetupStep(),
        ]

    @staticmethod
    def _resolve_step(category: str):
        step_map = {
            "llm": LLMSetupStep,
            "agent": AgentSetupStep,
            "tools": ToolsSetupStep,
            "dify": DifySetupStep,
        }
        cls = step_map.get(category)
        return cls() if cls else None
