"""
Tools Configuration Step.

Covers SDK tools (Tavily, DuckDuckGo, Zhipu Search/Crawl, AMap)
and MCP tools (Notion, Context7, AMap Maps, Firecrawl, Chrome DevTools).
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional

from rich.prompt import Prompt
from rich.table import Table

from src.core.config.setup.steps.base import (
    CheckResult,
    SetupContext,
    SetupStep,
    StepResult,
)

logger = logging.getLogger(__name__)

# SDK tools configuration
_SDK_TOOLS = [
    {"name": "Tavily Search", "key_env": "TAVILY_API_KEY", "description": "Web search API"},
    {"name": "DuckDuckGo", "key_env": None, "description": "Free web search"},
    {"name": "Zhipu Search", "key_env": "ZHIPU_API_KEY", "description": "Zhipu search (reuses LLM key)"},
    {"name": "Zhipu Crawl", "key_env": "ZHIPU_API_KEY", "description": "Zhipu crawling (reuses LLM key)"},
    {"name": "AMap Services", "key_env": "AMAP_API_KEY", "description": "Map search and routing"},
]

# MCP tools configuration
_MCP_TOOLS = [
    {"name": "Notion", "key_env": "NOTION_TOKEN", "description": "Notion page/database"},
    {"name": "Context7", "key_env": "CONTEXT7_API_KEY", "description": "Context7 MCP service"},
    {"name": "AMap Maps", "key_env": "AMAP_MAPS_API_KEY", "description": "AMap maps MCP"},
    {"name": "Firecrawl", "key_env": "FIRECRAWL_API_KEY", "description": "Web crawling via Firecrawl"},
    {"name": "Chrome DevTools", "key_env": None, "description": "Browser automation"},
]


class ToolsSetupStep(SetupStep):
    """SDK + MCP tools API key configuration."""

    name = "tools"
    title = "Tools Configuration"
    skippable = True

    def run(self, context: SetupContext, sub_target: Optional[str] = None) -> StepResult:
        """Run tools setup. sub_target: None=both, 'sdk', 'mcp'."""
        console = context.console
        configured_items: List[str] = []

        if sub_target is None or sub_target == "sdk":
            console.print("\n  --- SDK Tools ---")
            self._show_tools_table(context, _SDK_TOOLS)
            self._configure_tools(context, _SDK_TOOLS, configured_items)

        if sub_target is None or sub_target == "mcp":
            console.print("\n  --- MCP Tools ---")
            self._show_tools_table(context, _MCP_TOOLS)
            self._configure_tools(context, _MCP_TOOLS, configured_items)

        return StepResult(success=True, configured_items=configured_items)

    def check(self, context: SetupContext) -> List[CheckResult]:
        """Health check for tools configuration."""
        results: List[CheckResult] = []

        for tool in _SDK_TOOLS:
            results.append(self._check_tool(tool, "tools"))

        for tool in _MCP_TOOLS:
            results.append(self._check_tool(tool, "tools"))

        return results

    def _show_tools_table(self, context: SetupContext, tools: list) -> None:
        """Show tools status table."""
        table = Table(show_header=True, header_style="bold")
        table.add_column("Tool", style="bold")
        table.add_column("Required Key")
        table.add_column("Status", justify="right")

        for tool in tools:
            key_env = tool["key_env"]
            if key_env is None:
                key_display = "(no key needed)"
                status = "available"
                style = "green"
            elif _has_key(key_env):
                key_display = key_env
                status = "configured"
                style = "green"
            else:
                key_display = key_env
                status = "not configured"
                style = "dim"

            table.add_row(tool["name"], key_display, f"[{style}]{status}[/{style}]")

        context.console.print(table)

    def _configure_tools(
        self,
        context: SetupContext,
        tools: list,
        configured_items: List[str],
    ) -> None:
        """Ask user to configure unconfigured tools."""
        console = context.console

        for tool in tools:
            key_env = tool["key_env"]
            if key_env is None:
                continue  # no key needed
            if _has_key(key_env):
                continue  # already configured

            answer = Prompt.ask(
                f"  Configure {key_env}?",
                choices=["y", "skip"],
                default="skip",
                console=console,
            )
            if answer == "y":
                key = Prompt.ask(f"  {key_env}", password=True, console=console)
                if key and not key.startswith("your_"):
                    context.env_writer.write_key(key_env, key)
                    configured_items.append(key_env)
                    console.print(f"  [*] {key_env} saved", style="green")
                else:
                    console.print(f"  [-] Skipped (empty or placeholder)", style="dim")

    @staticmethod
    def _check_tool(tool: dict, category: str) -> CheckResult:
        """Check a single tool's key status."""
        key_env = tool["key_env"]
        if key_env is None:
            return CheckResult(
                name=tool["name"],
                status="pass",
                message=f'{tool["name"]}: available (no key needed)',
                category=category,
            )
        if _has_key(key_env):
            return CheckResult(
                name=key_env,
                status="pass",
                message=f'{tool["name"]}: {key_env} configured',
                category=category,
            )
        return CheckResult(
            name=key_env,
            status="warn",
            message=f'{tool["name"]}: {key_env} not configured',
            category=category,
        )


def _has_key(env_var: str) -> bool:
    """Check if an env var has a valid (non-placeholder) value."""
    value = os.getenv(env_var, "")
    return bool(value) and not value.startswith("your_")
