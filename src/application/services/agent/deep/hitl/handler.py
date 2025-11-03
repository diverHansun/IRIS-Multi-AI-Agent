"""Human-in-the-loop interrupt handling utilities."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from rich.markup import escape
from langgraph.types import Interrupt

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
    prompt_lines = [
        "======================================================================",
        "TOOL EXECUTION REQUIRES APPROVAL",
        "======================================================================",
        f"  Tool: {safe_tool_name}",
        f"  Arguments:\n{safe_args}",
    ]

    if warning:
        prompt_lines.append(f"  Warning: {escape(warning)}")

    prompt_lines.extend(
        [
            "",
            "  Description:",
            f"    {escape(description)}",
            "",
            "Please choose:",
        ]
    )

    options = _build_options(allowed_decisions, can_auto, is_dangerous)
    for option_line in options["labels"]:
        prompt_lines.append(option_line)

    default_choice = "1" if "1" in options["valid"] else next(iter(options["valid"]))

    while True:
        ctx.console.print("\n".join(prompt_lines))
        choice = await asyncio.to_thread(
            ctx.console.input,
            f"Your choice [{', '.join(sorted(options['valid']))}] (default: {default_choice}): ",
        )
        choice = choice.strip() or default_choice
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
    allowed = set(decision.lower() for decision in allowed_decisions)

    labels: List[str] = []
    valid_choices: List[str] = []

    if "approve" in allowed:
        labels.append("  [1] Yes - Approve this operation")
        valid_choices.append("1")
        if can_auto and not is_dangerous:
            labels.append("  [2] Yes and don't ask again - Auto-approve in this session")
            valid_choices.append("2")
        else:
            labels.append("  [2] (Unavailable for this tool)")

    if "reject" in allowed:
        labels.append("  [3] No - Reject this operation")
        labels.append("  [4] Tell the agent what to do instead")
        valid_choices.extend(["3", "4"])
    else:
        labels.append("  [3] (Reject not allowed for this request)")
        labels.append("  [4] (Reject with guidance not allowed)")

    return {"labels": labels, "valid": set(valid_choices)}
