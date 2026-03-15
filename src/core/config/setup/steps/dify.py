"""
Dify Engine Configuration Step.

Configures DIFY_API_KEY and DIFY_BASE_URL for the Dify engine.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from rich.prompt import Prompt

from src.core.config.setup.steps.base import (
    CheckResult,
    SetupContext,
    SetupStep,
    StepResult,
)

logger = logging.getLogger(__name__)

_DEFAULT_DIFY_BASE_URL = "https://api.dify.ai/v1"


class DifySetupStep(SetupStep):
    """Dify engine API key and base URL configuration."""

    name = "dify"
    title = "Dify Engine Configuration"
    skippable = True

    def run(self, context: SetupContext, sub_target: Optional[str] = None) -> StepResult:
        """Run Dify setup step."""
        console = context.console
        configured_items: List[str] = []

        console.print("  Dify engine requires an API key from your Dify instance.")

        answer = Prompt.ask(
            "  Configure Dify?",
            choices=["y", "skip"],
            default="skip",
            console=console,
        )

        if answer != "y":
            return StepResult(success=True, skipped=True)

        # API key
        key = Prompt.ask("  DIFY_API_KEY", password=True, console=console)
        if key and not key.startswith("your_"):
            context.env_writer.write_key("DIFY_API_KEY", key)
            configured_items.append("DIFY_API_KEY")
        else:
            console.print("  [-] Skipped (empty or placeholder)", style="dim")
            return StepResult(success=True, skipped=True)

        # Base URL
        base_url = Prompt.ask(
            f"  DIFY_BASE_URL",
            default=_DEFAULT_DIFY_BASE_URL,
            console=console,
        )
        context.env_writer.write_key("DIFY_BASE_URL", base_url)
        configured_items.append(f"DIFY_BASE_URL={base_url}")

        console.print("  [*] Dify configuration saved", style="green")
        return StepResult(success=True, configured_items=configured_items)

    def check(self, context: SetupContext) -> List[CheckResult]:
        """Health check for Dify configuration."""
        results: List[CheckResult] = []

        dify_key = os.getenv("DIFY_API_KEY", "")
        if dify_key and not dify_key.startswith("your_"):
            results.append(CheckResult(
                name="DIFY_API_KEY",
                status="pass",
                message="DIFY_API_KEY is configured",
                category="dify",
            ))

            dify_url = os.getenv("DIFY_BASE_URL", "")
            if dify_url:
                results.append(CheckResult(
                    name="DIFY_BASE_URL",
                    status="pass",
                    message=f"DIFY_BASE_URL = {dify_url}",
                    category="dify",
                ))
        else:
            results.append(CheckResult(
                name="DIFY_API_KEY",
                status="warn",
                message="DIFY_API_KEY not configured (Dify engine unavailable, can be skipped)",
                category="dify",
            ))

        return results
