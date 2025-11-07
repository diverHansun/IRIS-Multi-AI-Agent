"""Deep agent conversation helpers."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from rich.markup import escape

from langgraph.errors import GraphRecursionError
from langgraph.types import Command, Interrupt

from .event_handler import DeepAgentEventHandler
from ..hitl.handler import handle_hitl_interrupt, HITLDecisionError
from ..hitl.session_manager import SessionHITLManager
from ..hitl.file_ops import FileOpTracker


def _get_agent_config(ctx) -> Dict[str, Any]:
    return ctx.get_engine_config("agent")


def _ensure_hitl_manager(ctx, hitl_config: Optional[Dict[str, Any]]) -> SessionHITLManager:
    manager: Optional[SessionHITLManager] = getattr(ctx, "hitl_manager", None)
    if manager is None:
        manager = SessionHITLManager()
        ctx.hitl_manager = manager

    dangerous_tools = (hitl_config or {}).get("dangerous_tools", [])
    tool_settings = (hitl_config or {}).get("tools", {})
    manager.update_configuration(dangerous_tools=dangerous_tools, tool_settings=tool_settings)
    return manager


def _resolve_streaming_options(metadata: Dict[str, Any]) -> Dict[str, Any]:
    streaming = metadata.get("streaming", {}) if metadata else {}
    return {
        "show_reasoning_steps": streaming.get("show_reasoning_steps", True),
        "show_tool_calls": streaming.get("show_tool_calls", True),
        "show_tool_results": streaming.get("show_tool_results", True),
        "show_subagent_delegations": streaming.get("show_subagent_delegations", True),
        "show_elapsed_time": streaming.get("show_elapsed_time", True),
    }


def _resolve_safety(metadata: Dict[str, Any]) -> Dict[str, Any]:
    safety = metadata.get("safety", {}) if metadata else {}
    return {
        "max_execution_time": safety.get("max_execution_time"),
        "max_recursion_limit": safety.get("max_recursion_limit"),
    }


async def handle_deep_agent_query(ctx, query: str) -> str:
    """Route query to deep agent instance using streaming execution."""
    config = _get_agent_config(ctx)
    agent: Any = config.get("agent_instance")
    if agent is None:
        raise RuntimeError("Deep agent is not initialized.")

    metadata = getattr(agent, "metadata", {}) or {}
    streaming_opts = _resolve_streaming_options(metadata)
    safety_opts = _resolve_safety(metadata)
    hitl_config = metadata.get("hitl_config", {})
    hitl_manager = _ensure_hitl_manager(ctx, hitl_config)

    # Create file operation tracker for this query
    file_tracker = FileOpTracker(console=ctx.console)

    # Pass file_tracker to event_handler for result display
    event_handler = DeepAgentEventHandler(
        ctx.console,
        file_tracker=file_tracker,
        **streaming_opts
    )

    # Pass file_tracker to hitl_manager for approval preview
    hitl_manager._file_tracker = file_tracker

    session_id = ctx.session_id or "default"
    runtime_input = agent.create_runtime_input(query)
    runtime_config = agent.create_runtime_config(session_id)
    max_execution_time = safety_opts.get("max_execution_time")
    deadline = time.perf_counter() + max_execution_time if isinstance(max_execution_time, (int, float)) else None

    ctx.console.print("[dim]Deep agent reasoning...[/]")

    pending_input: Any = runtime_input
    timed_out = False

    try:
        while True:
            # Variables to capture interrupt state during streaming
            captured_interrupts: Optional[Tuple[Interrupt, ...]] = None

            try:
                async for event in agent.runtime.astream(
                    pending_input,
                    config=runtime_config,
                    stream_mode=["messages", "updates"],
                    subgraphs=True,
                    durability="exit",
                ):
                    result = event_handler.handle_event(event)

                    # Capture interrupts but don't process them yet
                    if result.interrupts:
                        captured_interrupts = result.interrupts

                    if deadline is not None and time.perf_counter() > deadline:
                        timed_out = True
                        break
            except GraphRecursionError as exc:
                ctx.console.print(f"[bold red]Recursion limit exceeded:[/] {escape(str(exc))}")
                return ""
            except Exception as exc:
                ctx.console.print(f"[bold red]Unexpected error in agent streaming:[/] {escape(str(exc))}")
                return ""

            if timed_out:
                break

            # Process HITL interrupts after streaming completes
            if captured_interrupts:
                try:
                    resume_payloads = await handle_hitl_interrupt(
                        ctx,
                        captured_interrupts,
                        hitl_manager,
                        hitl_config,
                    )
                    resume_data: Any
                    if len(resume_payloads) == 1:
                        resume_data = resume_payloads[0]
                    else:
                        resume_data = resume_payloads

                    pending_input = Command(resume=resume_data)
                    # Continue while loop to resume
                except HITLDecisionError as exc:
                    ctx.console.print(f"[bold red]HITL approval failed:[/] {escape(str(exc))}")
                    return ""
                except Exception as exc:
                    ctx.console.print(f"[bold red]Unexpected error during HITL processing:[/] {escape(str(exc))}")
                    return ""
            else:
                # No interrupts - normal completion
                break
    except KeyboardInterrupt:
        ctx.console.print("\n[yellow]Execution interrupted by user.[/]")
        return ""

    if timed_out:
        ctx.console.print("[bold red]Deep agent execution timed out.[/]")
        return ""

    final_state = event_handler.last_agent_state
    if not final_state:
        ctx.console.print("[bold red]Deep agent failed to produce a response.[/]")
        return ""

    result = agent.prepare_stream_result(
        query,
        session_id,
        final_state,
        tool_stats=event_handler.tool_stats,
    )

    if not result.get("success"):
        ctx.console.print(
            f"[bold red]Deep Agent Error:[/] {escape(result.get('output', 'Unknown error.'))}"
        )
        return ""

    answer = result.get("output", "No response generated.")
    ctx.console.print(f"[bold blue]DeepAgent >[/] {escape(answer)}")

    tool_calls = result.get("tool_calls", 0)
    tool_names = result.get("tool_names") or []
    if tool_calls:
        if tool_names:
            joined_names = ", ".join(tool_names)
            ctx.console.print(
                f"[dim]Used {len(tool_names)} tools ({tool_calls} calls): {escape(joined_names)}[/]"
            )
        else:
            ctx.console.print(f"[dim]Used {tool_calls} tool calls[/]")

    subagent_calls = result.get("subagent_calls", [])
    if subagent_calls:
        ctx.console.print(f"\n[bold cyan]SubAgent Delegations ({len(subagent_calls)} total)[/]")
        for idx, call in enumerate(subagent_calls, 1):
            subagent_type = call.get("subagent_type", "unknown")
            description = call.get("description", "")
            call_id = call.get("call_id", "")
            status = call.get("status", "unknown")
            ctx.console.print(
                f"[bold cyan][{idx}] {escape(subagent_type)}[/] ({escape(status)})"
            )
            if description:
                ctx.console.print(f"[dim]  Task:[/] {escape(description)}")
            if call_id:
                ctx.console.print(f"[dim]  ID:[/] {escape(call_id)}")

    event_handler.render_summary()
    return answer
