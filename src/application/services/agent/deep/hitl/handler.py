"""Human-in-the-loop interrupt handling utilities."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from rich.markup import escape
from rich.panel import Panel
from langgraph.types import Interrupt

from .file_ops import build_approval_preview as build_file_preview, render_diff_block
from .preview import build_approval_preview as build_shell_preview
from .session_manager import SessionHITLManager


Decision = Dict[str, Any]
InterruptPayload = Dict[str, Any]


class HITLDecisionError(RuntimeError):
    """Raised when no valid decision can be produced for an interrupt."""


async def handle_hitl_interrupt(
    ctx,
    interrupts: Sequence[Interrupt],
    hitl_manager: SessionHITLManager,
    hitl_config: Optional[Dict[str, Any]] = None,
    shell_workspace: str | None = None,
) -> List[InterruptPayload]:
    """
    Prompt the user to approve or reject pending tool executions.

    Returns a list of resume payloads matching the order of interrupts.
    """

    responses: List[InterruptPayload] = []

    for interrupt in interrupts:
        payload = _coerce_interrupt_payload(interrupt.value)
        if payload is None:
            raise HITLDecisionError("Interrupt payload is missing required fields.")

        action_requests = payload.get("action_requests", [])
        review_configs = payload.get("review_configs", [])
        if not action_requests:
            raise HITLDecisionError("Interrupt payload does not include action requests.")

        decisions: List[Decision] = []
        for index, request in enumerate(action_requests):
            config = review_configs[index] if index < len(review_configs) else None
            decision = await _resolve_decision(
                ctx,
                request,
                config,
                hitl_manager,
                shell_workspace=shell_workspace,
            )
            decisions.append(decision)

        responses.append({"decisions": decisions})

    return responses


def _coerce_interrupt_payload(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    return None


async def _resolve_decision(
    ctx,
    request: Dict[str, Any],
    config: Optional[Dict[str, Any]],
    hitl_manager: SessionHITLManager,
    shell_workspace: str | None = None,
) -> Decision:
    tool_name = str(request.get("name", "unknown"))
    args = request.get("args", {})
    description = request.get("description") or "Tool execution requires approval."

    allowed_decisions = _normalize_allowed_decisions(config)
    warning = hitl_manager.get_tool_warning(tool_name)
    safe_tool_name = escape(tool_name)

    if "approve" in allowed_decisions and hitl_manager.is_auto_approved(tool_name):
        ctx.console.print(f"[dim]Auto-approved '{safe_tool_name}' (session preference).[/]")
        return {"type": "approve"}

    can_auto = hitl_manager.can_auto_approve(tool_name) and "approve" in allowed_decisions
    is_dangerous = hitl_manager.is_dangerous(tool_name)
    safe_args = escape(_format_args(args))
    header_lines = [
        "======================================================================",
        "TOOL EXECUTION REQUIRES APPROVAL",
        "======================================================================",
        f"  Tool: {safe_tool_name}",
        f"  Arguments:\n{safe_args}",
    ]

    if warning:
        header_lines.append(f"  Warning: {escape(warning)}")

    header_lines.extend(
        [
            "",
            "  Description:",
            f"    {escape(description)}",
        ]
    )

    # Try file_ops preview first (for write_real_file, edit_real_file)
    # Fall back to shell preview (for shell)
    preview = build_file_preview(tool_name, args) or build_shell_preview(
        tool_name,
        args,
        shell_workspace=shell_workspace,
    )
    if preview:
        header_lines.append("")
        header_lines.append(f"  Preview: {escape(preview.title)}")
        for detail in preview.details:
            header_lines.append(f"    {escape(detail)}")
        if preview.error:
            header_lines.append(f"    Error: {escape(preview.error)}")

    ctx.console.print("\n".join(header_lines))
    if preview and preview.diff and not preview.error:
        ctx.console.print()
        render_diff_block(preview.diff, preview.diff_title or "Diff Preview", ctx.console)

    ctx.console.print()

    options = _build_options(allowed_decisions, can_auto, is_dangerous)

    # Display all options in a single panel with visual styling
    options_panel = Panel(
        "\n".join(options["labels"]),
        title="[bold]Please Choose[/]",
        border_style="cyan",
        padding=(0, 1),
    )
    ctx.console.print(options_panel)

    # Require explicit input (no default value)
    while True:
        choice = await asyncio.to_thread(
            ctx.console.input,
            f"\n[bold]Your choice[/] [{', '.join(sorted(options['valid']))}]: ",
        )
        choice = choice.strip()
        if not choice:
            ctx.console.print("[yellow]Please enter a choice. No default value is provided.[/]")
            continue
        if choice not in options["valid"]:
            ctx.console.print("[red]Invalid selection. Please choose a valid option.[/]")
            continue
        break

    if choice == "1":
        ctx.console.print(f"[green]Approved '{safe_tool_name}'.[/]")
        return {"type": "approve"}

    if choice == "2":
        hitl_manager.register_auto_approval(tool_name)
        ctx.console.print(
            f"[green]Approved '{safe_tool_name}' and remembered this preference.[/]"
        )
        return {"type": "approve"}

    if choice == "3":
        message = await asyncio.to_thread(
            ctx.console.input,
            "Optional message to the agent (leave blank to skip): ",
        )
        if message.strip():
            ctx.console.print("[yellow]Tool call rejected with user message.[/]")
            return {"type": "reject", "message": message.strip()}
        ctx.console.print("[yellow]Tool call rejected.[/]")
        return {"type": "reject"}

    # Option 4: provide instructions (reject with guidance)
    instructions = await asyncio.to_thread(
        ctx.console.input,
        "Describe how the agent should proceed instead: ",
    )
    ctx.console.print("[yellow]Instructions relayed to the agent.[/]")
    return {
        "type": "reject",
        "message": instructions.strip() or "User rejected the tool call without instructions.",
    }


def _normalize_allowed_decisions(config: Optional[Dict[str, Any]]) -> Iterable[str]:
    if not config:
        return ("approve", "reject")
    allowed = config.get("allowed_decisions")
    if isinstance(allowed, Sequence):
        return tuple(str(decision) for decision in allowed)
    return ("approve", "reject")


def _format_args(args: Any) -> str:
    try:
        return json.dumps(args, indent=2, ensure_ascii=False)
    except TypeError:
        return repr(args)


def _build_options(
    allowed_decisions: Iterable[str],
    can_auto: bool,
    is_dangerous: bool,
) -> Dict[str, Any]:
    """
    Build option labels with visual styling.

    Returns a dictionary with:
        - labels: List of all option strings
        - valid: Set of valid choice numbers
    """
    allowed = set(decision.lower() for decision in allowed_decisions)

    labels: List[str] = []
    valid_choices: List[str] = []

    # Build approval options with icons and colors
    if "approve" in allowed:
        labels.append("[green][1] \u2713 Yes[/] - Approve this operation")
        valid_choices.append("1")

        if can_auto and not is_dangerous:
            labels.append(
                "[yellow][2] \u26a1 Yes and don't ask again[/] - Auto-approve in this session"
            )
            valid_choices.append("2")
        else:
            # Provide specific reason for unavailability
            if is_dangerous:
                reason = "Tool is security-sensitive"
            else:
                reason = "Tool settings disabled auto-approval"
            labels.append(f"[dim][2] (Unavailable - {reason})[/]")

    # Build rejection options with icons and colors
    if "reject" in allowed:
        labels.append("[red][3] \u2717 No[/] - Reject this operation")
        labels.append("[cyan][4] \u270f Tell the agent what to do instead[/]")
        valid_choices.extend(["3", "4"])
    else:
        labels.append("[dim][3] (Reject not allowed for this request)[/]")
        labels.append("[dim][4] (Reject with guidance not allowed)[/]")

    return {
        "labels": labels,
        "valid": set(valid_choices),
    }
