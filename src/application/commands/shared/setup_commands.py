"""CLI commands for configuration wizard and health check."""

from __future__ import annotations

import asyncio

from src.application.commands.base import BaseCommand, CommandResult


async def _run_setup(ctx, args: str) -> CommandResult:
    """Delegate to SetupWizard based on parsed flags."""
    from src.core.config.setup.wizard import SetupWizard

    parts = args.strip().split()
    if not parts:
        wizard = SetupWizard(console=ctx.console)
        success = await asyncio.to_thread(wizard.run_all)
        return (
            CommandResult.success("Setup completed.")
            if success
            else CommandResult.error("Setup failed or was interrupted.")
        )

    flag = parts[0]
    sub_target = parts[1] if len(parts) > 1 else None

    target_map = {
        "--llm":   ("llm",   None),
        "--agent": ("agent", sub_target),
        "--tools": ("tools", sub_target),
        "--dify":  ("dify",  None),
    }
    if flag not in target_map:
        return CommandResult.error(
            f"Unknown flag '{flag}'. Valid: --llm, --agent [basic|deep], --tools [sdk|mcp], --dify"
        )
    if flag == "--agent" and sub_target not in (None, "basic", "deep"):
        return CommandResult.error(
            f"Invalid --agent target '{sub_target}'. Valid: basic, deep"
        )
    if flag == "--tools" and sub_target not in (None, "sdk", "mcp"):
        return CommandResult.error(
            f"Invalid --tools target '{sub_target}'. Valid: sdk, mcp"
        )

    target, sub = target_map[flag]
    wizard = SetupWizard(console=ctx.console)
    success = await asyncio.to_thread(wizard.run_specific, target, sub)
    label = f"{target}" + (f" ({sub})" if sub else "")
    return (
        CommandResult.success(f"Setup [{label}] completed.")
        if success
        else CommandResult.error(f"Setup [{label}] failed or was interrupted.")
    )


async def _run_doctor(ctx) -> CommandResult:
    """Run a full configuration health check and print the report."""
    from src.core.config.setup.validator import ConfigValidator

    validator = ConfigValidator(console=ctx.console)
    results = validator.check_all()
    validator.print_report(results)

    failed = [r for r in results if r.status == "fail"]
    if failed:
        return CommandResult.error(
            f"{len(failed)} issue(s) found. Run /setup to fix."
        )
    return CommandResult.success("All configuration checks passed.")


class SetupCommand(BaseCommand):
    """Interactive wizard for configuring LLM providers, agents, tools, and Dify."""

    name = "setup"
    help_text = "Run configuration wizard (LLM, agents, tools, dify)"
    aliases = ()
    engine_scope = ("all",)

    async def execute(self, ctx, args: str) -> CommandResult:
        return await _run_setup(ctx, args)


class DoctorCommand(BaseCommand):
    """Check that all required configuration values are present and valid."""

    name = "doctor"
    help_text = "Check configuration health (LLM keys, agents, tools, dify)"
    aliases = ("check",)
    engine_scope = ("all",)

    async def execute(self, ctx, args: str) -> CommandResult:
        return await _run_doctor(ctx)
