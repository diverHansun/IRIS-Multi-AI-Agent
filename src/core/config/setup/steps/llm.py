"""
LLM Provider Configuration Step.

Guides user through selecting LLM providers and entering API keys.
At least one LLM provider must be configured (not skippable).
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
from src.core.config.setup.widgets import Option, SelectOne, text_input

logger = logging.getLogger(__name__)

# Provider definitions for the LLM step
_PROVIDERS = [
    {
        "key": "zhipu",
        "name": "Zhipu AI",
        "description": "Zhipu GLM (recommended)",
        "api_key_env": "ZHIPU_API_KEY",
        "default_model": "glm-4.5-flash",
        "has_base_url": False,
    },
    {
        "key": "openai",
        "name": "OpenAI",
        "description": "OpenAI GPT (supports custom base_url)",
        "api_key_env": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
        "has_base_url": True,
        "base_url_env": "OPENAI_BASE_URL",
    },
    {
        "key": "tongyi",
        "name": "Tongyi Qwen",
        "description": "Tongyi Qwen (Alibaba Cloud)",
        "api_key_env": "TONGYI_API_KEY",
        "default_model": "qwen3-max",
        "has_base_url": False,
    },
    {
        "key": "ollama",
        "name": "Ollama",
        "description": "Local models (no API key needed)",
        "api_key_env": None,
        "default_model": "auto",
        "has_base_url": False,
    },
]


class LLMSetupStep(SetupStep):
    """LLM provider selection and API key configuration."""

    name = "llm"
    title = "LLM Provider Configuration"
    skippable = False

    def run(self, context: SetupContext, sub_target: Optional[str] = None) -> StepResult:
        """Run the LLM setup step interactively."""
        console = context.console
        configured_items: List[str] = []

        # Show current status table
        self._print_status_table(context)

        # Provider selection with back-navigation support
        last_selected_key: Optional[str] = "zhipu"
        while True:
            options = self._build_provider_options(context)
            selector = SelectOne(
                title="Select default LLM provider:",
                options=options,
                default=last_selected_key,
            )
            selected = selector.run()

            if selected is None:
                return StepResult(success=False, error="No provider selected")

            last_selected_key = selected.key
            provider_info = self._get_provider_info(selected.key)

            if provider_info["api_key_env"] is None:
                # No key needed (e.g., ollama) — proceed immediately
                break

            result = self._configure_provider_key(context, provider_info, configured_items)
            if result is None:
                # Esc pressed — go back to provider selector
                continue
            break

        default_provider = selected.key
        provider_info = self._get_provider_info(default_provider)

        # Configure the selected provider
        key_configured = provider_info["api_key_env"] is None
        if provider_info["api_key_env"]:
            # Already configured above — check if it was saved
            key_configured = context.env_writer.has_key(provider_info["api_key_env"])

        # Write default provider/model
        context.env_writer.write_key("DEFAULT_LLM_PROVIDER", default_provider)
        context.env_writer.write_key("DEFAULT_LLM_MODEL", provider_info["default_model"])
        configured_items.append(f"DEFAULT_LLM_PROVIDER={default_provider}")
        if key_configured:
            context.configured_providers.add(default_provider)

        if default_provider == "ollama":
            context.configured_providers.add("ollama")

        # Ask to configure additional providers
        while True:
            answer = Prompt.ask(
                "  Configure another provider?",
                choices=["y", "N"],
                default="N",
                console=console,
            )
            if answer.upper() != "Y":
                break

            remaining = [
                p for p in _PROVIDERS
                if p["key"] != default_provider
                and p["key"] not in context.configured_providers
                and p["api_key_env"] is not None
            ]
            if not remaining:
                console.print("  All providers are already configured.", style="dim")
                break

            extra_options = [
                Option(
                    key=p["key"],
                    label=p["key"],
                    description=p["description"],
                    status="not configured",
                )
                for p in remaining
            ]
            extra_sel = SelectOne(title="Select provider:", options=extra_options)
            extra = extra_sel.run()
            if extra is None:
                break

            extra_info = self._get_provider_info(extra.key)
            self._configure_provider_key(context, extra_info, configured_items)
            context.configured_providers.add(extra.key)

        # Validation: at least one provider configured
        if not context.configured_providers:
            return StepResult(
                success=False,
                error="At least one LLM provider must be configured.",
            )

        return StepResult(success=True, configured_items=configured_items)

    def check(self, context: SetupContext) -> List[CheckResult]:
        """Health check for LLM configuration."""
        results: List[CheckResult] = []

        for p in _PROVIDERS:
            env_var = p["api_key_env"]
            if env_var is None:
                results.append(CheckResult(
                    name=p["key"],
                    status="pass",
                    message=f"{p['name']}: available (no key needed)",
                    category="llm",
                ))
                continue

            value = os.getenv(env_var, "")
            if value and not value.startswith("your_"):
                results.append(CheckResult(
                    name=env_var,
                    status="pass",
                    message=f"{env_var} configured",
                    category="llm",
                ))
            else:
                results.append(CheckResult(
                    name=env_var,
                    status="warn",
                    message=f"{env_var} not configured",
                    category="llm",
                ))

        # Check default provider
        default_provider = os.getenv("DEFAULT_LLM_PROVIDER", "")
        if default_provider:
            p_info = self._get_provider_info(default_provider)
            if p_info:
                env_var = p_info.get("api_key_env")
                if env_var is None or (os.getenv(env_var, "") and not os.getenv(env_var, "").startswith("your_")):
                    results.append(CheckResult(
                        name="DEFAULT_LLM_PROVIDER",
                        status="pass",
                        message=f"DEFAULT_LLM_PROVIDER = {default_provider} (key available)",
                        category="llm",
                    ))
                else:
                    results.append(CheckResult(
                        name="DEFAULT_LLM_PROVIDER",
                        status="fail",
                        message=f"DEFAULT_LLM_PROVIDER = {default_provider}, but {env_var} not configured",
                        category="llm",
                    ))

        return results

    def _print_status_table(self, context: SetupContext) -> None:
        """Print provider status table using Rich."""
        table = Table(show_header=True, header_style="bold")
        table.add_column("Provider", style="bold")
        table.add_column("Description")
        table.add_column("Status", justify="right")

        for p in _PROVIDERS:
            status = self._get_provider_status(p, context)
            style = "green" if status in ("configured", "available") else "dim"
            table.add_row(p["key"], p["description"], f"[{style}]{status}[/{style}]")

        context.console.print(table)

    def _build_provider_options(self, context: SetupContext) -> List[Option]:
        """Build Option list for SelectOne."""
        return [
            Option(
                key=p["key"],
                label=p["key"],
                description=p["description"],
                status=self._get_provider_status(p, context),
            )
            for p in _PROVIDERS
        ]

    def _get_provider_status(self, provider: dict, context: SetupContext) -> str:
        """Return human-readable status for a provider."""
        if provider["api_key_env"] is None:
            return "available"
        if provider["key"] in context.configured_providers:
            return "configured"
        value = os.getenv(provider["api_key_env"], "")
        if value and not value.startswith("your_"):
            return "configured"
        return "not configured"

    def _configure_provider_key(
        self,
        context: SetupContext,
        provider_info: dict,
        configured_items: List[str],
    ) -> Optional[bool]:
        """Ask user for API key and optionally base_url.

        Returns True if configured/confirmed, None if Esc pressed (go back).
        Pre-fills existing values as defaults so the user can confirm with Enter.
        For providers with has_base_url, base_url is prompted first.
        """
        console = context.console
        env_var = provider_info["api_key_env"]

        if provider_info.get("has_base_url"):
            base_url_env = provider_info.get("base_url_env", "")
            default_url = "https://api.openai.com/v1"
            existing_url = os.getenv(base_url_env, "") or default_url
            base_url = text_input(base_url_env, default=existing_url)
            if base_url is None:
                return None  # Esc pressed — go back
            base_url = base_url.strip() or default_url
            context.env_writer.write_key(base_url_env, base_url)
            configured_items.append(f"{base_url_env}={base_url}")

        existing_key = os.getenv(env_var, "")
        default_key = existing_key if existing_key and not existing_key.startswith("your_") else ""
        key = text_input(env_var, default=default_key)
        if key is None:
            return None  # Esc pressed — go back
        if not key or key.startswith("your_"):
            console.print("  [-] Skipped (empty input)", style="dim")
            return None

        context.env_writer.write_key(env_var, key)
        configured_items.append(env_var)
        console.print("  [*] API key saved", style="green")
        return True

    @staticmethod
    def _get_provider_info(key: str) -> Optional[dict]:
        """Look up provider info by key."""
        for p in _PROVIDERS:
            if p["key"] == key:
                return p
        return None
