"""
Agent Configuration Step.

Covers Basic mode (confirmation display) and Deep mode (mainagents/subagents config check).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.prompt import Prompt
from rich.table import Table

from src.core.config.setup.steps.base import (
    CheckResult,
    SetupContext,
    SetupStep,
    StepResult,
)
from src.core.config.setup.widgets import text_input

logger = logging.getLogger(__name__)


class AgentSetupStep(SetupStep):
    """Agent configuration step (basic + deep modes)."""

    name = "agent"
    title = "Agent Configuration"
    skippable = True

    def run(self, context: SetupContext, sub_target: Optional[str] = None) -> StepResult:
        """Run agent setup. sub_target: None=both, 'basic', 'deep'."""
        console = context.console
        configured_items: List[str] = []

        if sub_target is None or sub_target == "basic":
            self._run_basic(context)

        if sub_target == "deep":
            self._run_deep(context, configured_items)
        elif sub_target is None:
            answer = Prompt.ask(
                "  Configure deep agent mode?",
                choices=["y", "N"],
                default="N",
                console=console,
            )
            if answer.upper() == "Y":
                self._run_deep(context, configured_items)
            else:
                console.print("  [-] Deep mode skipped", style="dim")

        return StepResult(success=True, configured_items=configured_items)

    def check(self, context: SetupContext) -> List[CheckResult]:
        """Health check for agent configuration."""
        results: List[CheckResult] = []

        # Basic agent check
        default_provider = os.getenv("DEFAULT_LLM_PROVIDER", "zhipu")
        default_model = os.getenv("DEFAULT_LLM_MODEL", "glm-4.7-flash")
        provider_key = _provider_env_key(default_provider)

        if provider_key is None or _has_key(provider_key):
            results.append(CheckResult(
                name="basic_agent",
                status="pass",
                message=f"Basic agent: {default_provider} / {default_model} (key available)",
                category="agent",
            ))
        else:
            results.append(CheckResult(
                name="basic_agent",
                status="fail",
                message=f"Basic agent: {default_provider} / {default_model} ({provider_key} not configured)",
                category="agent",
            ))

        # Deep agent checks
        mainagents = self._load_deep_config(context.share_dir, "mainagents.json")
        if mainagents:
            for provider_name, config in mainagents.items():
                api_config = config.get("api_config", {})
                key_env = api_config.get("api_key_env", "")
                if _has_key(key_env):
                    results.append(CheckResult(
                        name=f"deep_main_{provider_name}",
                        status="pass",
                        message=f"Main agent: {provider_name} configured",
                        category="agent",
                    ))
                else:
                    results.append(CheckResult(
                        name=f"deep_main_{provider_name}",
                        status="warn",
                        message=f"Main agent: {provider_name} not configured (fallback available)",
                        category="agent",
                    ))

        subagents = self._load_deep_config(context.share_dir, "subagents.json")
        if subagents:
            for role_name, config in subagents.items():
                providers = config.get("providers", {})
                llm_config = config.get("llm_config", {})

                if providers:
                    # New multi-provider format
                    has_any = False
                    for pname, pconf in providers.items():
                        key_env = pconf.get("api_config", {}).get("api_key_env", "")
                        if _has_key(key_env):
                            has_any = True
                            break
                    if has_any:
                        results.append(CheckResult(
                            name=f"deep_sub_{role_name}",
                            status="pass",
                            message=f'Sub-agent "{role_name}": configured',
                            category="agent",
                        ))
                    else:
                        results.append(CheckResult(
                            name=f"deep_sub_{role_name}",
                            status="warn",
                            message=f'Sub-agent "{role_name}": no provider configured',
                            category="agent",
                        ))
                elif llm_config:
                    # Old single-provider format
                    key_env = llm_config.get("api_config", {}).get("api_key_env", "")
                    provider_name = llm_config.get("provider", "unknown")
                    if _has_key(key_env):
                        results.append(CheckResult(
                            name=f"deep_sub_{role_name}",
                            status="pass",
                            message=f'Sub-agent "{role_name}": {provider_name} configured',
                            category="agent",
                        ))
                    else:
                        results.append(CheckResult(
                            name=f"deep_sub_{role_name}",
                            status="warn",
                            message=f'Sub-agent "{role_name}": {key_env} not configured',
                            category="agent",
                        ))

        return results

    def _run_basic(self, context: SetupContext) -> None:
        """Display basic agent configuration (informational only)."""
        console = context.console
        default_provider = os.getenv("DEFAULT_LLM_PROVIDER", "")
        if not default_provider and context.configured_providers:
            default_provider = next(iter(context.configured_providers))

        default_model = os.getenv("DEFAULT_LLM_MODEL", "")

        console.print()
        console.print("  Agent Configuration - Basic Mode", style="bold")
        console.print(f"  Basic agent will use: {default_provider} / {default_model}")
        console.print("  (derived from LLM configuration)")
        console.print()

    def _run_deep(self, context: SetupContext, configured_items: List[str]) -> None:
        """Interactive deep agent configuration."""
        console = context.console

        # Show mainagents status
        console.print()
        console.print("  Agent Configuration - Deep Mode", style="bold")

        mainagents = self._load_deep_config(context.share_dir, "mainagents.json")
        if mainagents:
            console.print("\n  Main agent providers (mainagents.json):")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Provider", style="bold")
            table.add_column("Model")
            table.add_column("API Key Status", justify="right")

            for provider_name, config in mainagents.items():
                api_config = config.get("api_config", {})
                key_env = api_config.get("api_key_env", "")
                default_model = config.get("default_model", "")
                models = config.get("models", {})
                model_name = default_model or (next(iter(models)) if models else "")
                status = "configured" if _has_key(key_env) else "not configured"
                style = "green" if status == "configured" else "dim"
                table.add_row(provider_name, model_name, f"[{style}]{status}[/{style}]")

            console.print(table)

        # Show subagents status
        subagents = self._load_deep_config(context.share_dir, "subagents.json")
        if subagents:
            console.print("\n  Sub-agents (subagents.json):")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Role", style="bold")
            table.add_column("Provider")
            table.add_column("Model")
            table.add_column("Status", justify="right")

            missing_keys: List[Dict[str, str]] = []

            for role_name, config in subagents.items():
                provider_name, model_name, key_env = self._resolve_subagent_info(config)
                status = "configured" if _has_key(key_env) else "not configured"
                style = "green" if status == "configured" else "dim"
                table.add_row(role_name, provider_name, model_name, f"[{style}]{status}[/{style}]")

                if not _has_key(key_env):
                    missing_keys.append({"role": role_name, "key_env": key_env, "provider": provider_name})

            console.print(table)

            for m in missing_keys:
                console.print(
                    f'  [!] Sub-agent "{m["role"]}" requires {m["key_env"]} (not configured).',
                    style="yellow",
                )

            if missing_keys:
                answer = Prompt.ask(
                    "  Configure missing API keys?",
                    choices=["y", "N"],
                    default="N",
                    console=console,
                )
                if answer.upper() == "Y":
                    seen_keys: set = set()
                    for m in missing_keys:
                        key_env = m["key_env"]
                        if key_env in seen_keys:
                            continue
                        seen_keys.add(key_env)
                        key = text_input(key_env)
                        if key and not key.startswith("your_"):
                            context.env_writer.write_key(key_env, key)
                            configured_items.append(key_env)
                            console.print(f"  [*] {key_env} saved", style="green")
                        elif key is None:
                            console.print(f"  [-] {key_env} skipped", style="dim")

    def _load_deep_config(self, share_dir: Path, filename: str) -> Optional[Dict[str, Any]]:
        """Load deep agent config JSON from ~/.iris/agents/deep/."""
        path = share_dir / "agents" / "deep" / filename
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load %s: %s", path, exc)
            return None

    @staticmethod
    def _resolve_subagent_info(config: dict) -> tuple:
        """Extract provider name, model, api_key_env from subagent config.

        Supports both old (llm_config) and new (providers) format.
        """
        # New format: providers dict
        providers = config.get("providers", {})
        if providers:
            first_provider = next(iter(providers))
            pconf = providers[first_provider]
            return (
                first_provider,
                pconf.get("model", ""),
                pconf.get("api_config", {}).get("api_key_env", ""),
            )

        # Old format: llm_config
        llm_config = config.get("llm_config", {})
        return (
            llm_config.get("provider", "unknown"),
            llm_config.get("model", ""),
            llm_config.get("api_config", {}).get("api_key_env", ""),
        )


def _provider_env_key(provider: str) -> Optional[str]:
    """Map provider name to API key env var."""
    mapping = {
        "zhipu": "ZHIPU_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "tongyi": "TONGYI_API_KEY",
        "ollama": None,
    }
    return mapping.get(provider)


def _has_key(env_var: str) -> bool:
    """Check if an env var has a valid (non-placeholder) value."""
    if not env_var:
        return True  # no key needed
    value = os.getenv(env_var, "")
    return bool(value) and not value.startswith("your_")
