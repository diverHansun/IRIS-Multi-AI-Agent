"""
Setup and Doctor commands.

Thin shell over core-layer SetupWizard and ConfigValidator.
"""

from __future__ import annotations

import asyncio

from src.application.commands.base import BaseCommand, CommandResult


class SetupCommand(BaseCommand):
    """Run configuration wizard (LLM, agents, tools, dify)."""

    name = "setup"
    help_text = "Run configuration wizard (LLM, agents, tools, dify)"
    aliases = ()
    engine_scope = ("all",)

    async def execute(self, ctx, args: str) -> CommandResult:
        """Parse args and delegate to SetupWizard."""
        from src.core.config.setup.wizard import SetupWizard

        parts = args.strip().split()

        if not parts:
            wizard = SetupWizard(console=ctx.console)
            success = await asyncio.to_thread(wizard.run_all)
            return (
                CommandResult.success("Setup completed.")
                if success
                else CommandResult.error("Setup failed.")
            )

        flag = parts[0]
        sub_target = parts[1] if len(parts) > 1 else None

        target_map = {
            "--llm": ("llm", None),
            "--agent": ("agent", sub_target),
            "--tools": ("tools", sub_target),
            "--dify": ("dify", None),
        }

        if flag not in target_map:
            return CommandResult.error(
                f"Unknown setup target: {flag}. "
                f"Valid options: --llm, --agent, --tools, --dify"
            )

        if flag == "--agent" and sub_target not in (None, "basic", "deep"):
            return CommandResult.error(
                f"Unknown setup sub-target for --agent: {sub_target}. "
                f"Valid options: basic, deep"
            )
        if flag == "--tools" and sub_target not in (None, "sdk", "mcp"):
            return CommandResult.error(
                f"Unknown setup sub-target for --tools: {sub_target}. "
                f"Valid options: sdk, mcp"
            )

        target, sub = target_map[flag]
        wizard = SetupWizard(console=ctx.console)
        success = await asyncio.to_thread(wizard.run_specific, target, sub)
        return (
            CommandResult.success(f"Setup ({target}) completed.")
            if success
            else CommandResult.error(f"Setup ({target}) failed.")
        )


class DoctorCommand(BaseCommand):
    """Check configuration health status."""

    name = "doctor"
    help_text = "Check configuration health status"
    aliases = ("check",)
    engine_scope = ("all",)

    async def execute(self, ctx, args: str) -> CommandResult:
        """Run configuration health check."""
        from src.core.config.setup.validator import ConfigValidator

        validator = ConfigValidator(console=ctx.console)
        parts = args.strip().split()

        valid_categories = {"llm", "agent", "tools", "dify"}

        if not parts:
            results = validator.check_all()
        else:
            category = parts[0].lstrip("-")
            if category not in valid_categories:
                return CommandResult.error(
                    f"Unknown category '{category}'. "
                    f"Valid options: {', '.join(sorted(valid_categories))}"
                )
            results = validator.check_category(category)

        validator.print_report(results)

        failed = [r for r in results if r.status == "fail"]
        if failed:
            return CommandResult.error(
                f"{len(failed)} configuration issue(s) found. "
                "Run /iris setup to fix."
            )
        return CommandResult.success("All configuration checks passed.")
