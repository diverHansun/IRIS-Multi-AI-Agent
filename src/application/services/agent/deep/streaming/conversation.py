"""Deep agent conversation helpers."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.markup import escape

from langgraph.errors import GraphRecursionError
from langgraph.types import Command, Interrupt

from src.components.deepagents.runtime_middlewares.timeout import ExecutionTimeoutError
from .event_handler import DeepAgentEventHandler
from ..hitl.handler import handle_hitl_interrupt, HITLDecisionError
from ..hitl.session_manager import SessionHITLManager
from ..hitl.file_ops import FileOpTracker
from src.components.shared.memory import DeepAgentCheckpointer
from src.application.cli.theme import COLORS

logger = logging.getLogger(__name__)


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


def _is_shell_security_policy_enabled(metadata: Optional[Dict[str, Any]]) -> bool:
    middleware_cfg = (metadata or {}).get("middleware", {})
    if not isinstance(middleware_cfg, dict):
        return False
    shell_cfg = middleware_cfg.get("shell", {})
    if not isinstance(shell_cfg, dict):
        return False
    security_cfg = shell_cfg.get("security_policy", {})
    return isinstance(security_cfg, dict) and bool(security_cfg.get("enabled", False))


def _resolve_shell_workspace_for_preview(metadata: Optional[Dict[str, Any]]) -> Optional[str]:
    middleware_cfg = (metadata or {}).get("middleware", {})
    if not isinstance(middleware_cfg, dict):
        return None
    shell_cfg = middleware_cfg.get("shell", {})
    if not isinstance(shell_cfg, dict):
        return None
    resolved_workspace = shell_cfg.get("resolved_workspace_root")
    if resolved_workspace not in (None, ""):
        return str(resolved_workspace)
    workspace = shell_cfg.get("workspace_root")
    if workspace in (None, "", "auto", "."):
        return None
    return str(workspace)


def _build_effective_hitl_config(
    metadata: Optional[Dict[str, Any]],
    hitl_config: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply runtime HITL adjustments based on active shell middleware configuration."""
    if not isinstance(hitl_config, dict):
        return {}

    effective = dict(hitl_config)
    tools_cfg = hitl_config.get("tools", {})
    effective_tools: Dict[str, Any] = {}
    if isinstance(tools_cfg, dict):
        for key, value in tools_cfg.items():
            effective_tools[str(key)] = dict(value) if isinstance(value, dict) else value

    dangerous_tools = list(hitl_config.get("dangerous_tools", []) or [])

    if _is_shell_security_policy_enabled(metadata):
        dangerous_tools = [tool for tool in dangerous_tools if str(tool) != "shell"]
        shell_settings = effective_tools.get("shell")
        if not isinstance(shell_settings, dict):
            shell_settings = {}
        else:
            shell_settings = dict(shell_settings)
        shell_settings["allow_auto_approve"] = True
        effective_tools["shell"] = shell_settings

    effective["dangerous_tools"] = dangerous_tools
    effective["tools"] = effective_tools
    return effective


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
    """
    Route query to deep agent instance using streaming execution.

    Implements dual checkpointer session lifecycle:
    1. Load conversation history from storage_checkpointer to runtime_checkpointer
    2. Execute with runtime_checkpointer (supports HITL)
    3. Save filtered messages back to storage_checkpointer
    """
    config = _get_agent_config(ctx)
    agent: Any = config.get("agent_instance")
    if agent is None:
        raise RuntimeError("Deep agent is not initialized.")

    metadata = getattr(agent, "metadata", {}) or {}
    streaming_opts = _resolve_streaming_options(metadata)
    safety_opts = _resolve_safety(metadata)
    raw_hitl_config = metadata.get("hitl_config", {})
    hitl_config = _build_effective_hitl_config(metadata, raw_hitl_config)
    hitl_manager = _ensure_hitl_manager(ctx, hitl_config)
    shell_workspace_for_preview = _resolve_shell_workspace_for_preview(metadata)

    # Create file operation tracker for this query
    file_tracker = FileOpTracker()

    # Pass file_tracker to event_handler for result display
    event_handler = DeepAgentEventHandler(
        ctx.console,
        file_tracker=file_tracker,
        **streaming_opts
    )

    # Pass file_tracker to hitl_manager for approval preview
    hitl_manager._file_tracker = file_tracker

    session_id = ctx.session_id or "default"
    runtime_config = agent.create_runtime_config(session_id)
    max_execution_time = safety_opts.get("max_execution_time")
    deadline = time.perf_counter() + max_execution_time if isinstance(max_execution_time, (int, float)) else None

    runtime_checkpointer = getattr(agent, "runtime_checkpointer", None)
    project_context = getattr(ctx, "project_context", None)
    metadata_manager = getattr(ctx, "metadata_manager", None)
    deep_checkpointer: DeepAgentCheckpointer = (
        getattr(agent, "deep_checkpointer", None)
        or getattr(ctx, "deep_checkpointer", None)
        or DeepAgentCheckpointer(
            project_context=project_context,
            metadata_manager=metadata_manager,
        )
    )
    setattr(agent, "deep_checkpointer", deep_checkpointer)
    setattr(ctx, "deep_checkpointer", deep_checkpointer)

    # Check if MemorySaver already has checkpoint for this session
    # MemorySaver is in-memory, so it only has checkpoints from current program run
    has_checkpoint = False
    if runtime_checkpointer:
        try:
            checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config)
            has_checkpoint = checkpoint_tuple is not None
            if has_checkpoint:
                # Get message count from checkpoint
                checkpoint_messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
                logger.debug(f"MemorySaver has checkpoint with {len(checkpoint_messages)} messages")
            else:
                logger.debug("MemorySaver has no checkpoint for this session yet")
        except Exception as exc:
            logger.warning(f"Failed to check checkpoint existence: {exc}")

    # Only inject history from storage if MemorySaver doesn't have checkpoint yet
    if not has_checkpoint:
        logger.info("First query in this session: loading history from storage into input")
        runtime_input = deep_checkpointer.enhance_runtime_input(
            session_id,
            query,
            max_history=10,
        )
    else:
        logger.info("Continuing session: MemorySaver will provide history automatically")
        runtime_input = agent.create_runtime_input(query)

    ctx.console.print("[dim]Deep agent reasoning...[/]")

    pending_input: Any = runtime_input
    timed_out = False
    final_state: Optional[Dict[str, Any]] = None

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
            except (KeyboardInterrupt, asyncio.CancelledError):
                # User interrupted streaming - re-raise to trigger outer exception handler
                logger.info("Deep agent streaming interrupted by user")
                raise
            except GraphRecursionError as exc:
                ctx.console.print(f"[bold red]Recursion limit exceeded:[/] {escape(str(exc))}")
                return ""
            except TimeoutError as exc:
                # Step timeout - persist state and notify agent
                logger.warning(f"Step timeout occurred in Deep Agent: {exc}")

                ctx.console.print(
                    f"[yellow]TIMEOUT: The agent took longer than expected for this step.[/]"
                )

                checkpoint_tuple = runtime_checkpointer.get_tuple(runtime_config) if runtime_checkpointer else None
                if not checkpoint_tuple:
                    logger.warning("No checkpoint found - persisting current state via DeepAgentCheckpointer")
                deep_checkpointer.persist_from_runtime(
                    session_id,
                    runtime_checkpointer,
                    runtime_config,
                    None,
                )

                # Notify agent using SystemMessage (won't be persisted)
                ctx.console.print(f"[dim]Informing agent about timeout...[/]")
                try:
                    from langchain_core.messages import SystemMessage
                    await agent.runtime.aupdate_state(
                        runtime_config,
                        values={
                            "messages": [
                                SystemMessage(
                                    content="SYSTEM NOTIFICATION: The previous operation timed out. "
                                    "Your work has been saved. You can continue or ask for clarification."
                                )
                            ]
                        },
                    )
                    ctx.console.print(f"[dim]Agent notified. You can continue the conversation.[/]")
                    logger.info("Agent notified about step timeout via SystemMessage")
                except Exception as update_exc:
                    logger.error(f"Failed to update agent state: {update_exc}")
                    ctx.console.print(f"[yellow]Warning: Could not notify agent[/]")

                return "[Timeout occurred - please retry or rephrase your request]"

            except ExecutionTimeoutError as exc:
                # Max execution time exceeded (方案B: middleware raises exception)
                logger.warning(f"Max execution time exceeded: {exc}")

                ctx.console.print(
                    f"[yellow]EXECUTION TIMEOUT: Agent exceeded maximum execution time "
                    f"({exc.elapsed_time:.1f}s / {exc.max_execution_time:.1f}s)[/]"
                )

                deep_checkpointer.persist_from_runtime(
                    session_id,
                    runtime_checkpointer,
                    runtime_config,
                    None,
                )

                # Notify agent using SystemMessage
                ctx.console.print(f"[dim]Informing agent about execution timeout...[/]")
                try:
                    from langchain_core.messages import SystemMessage
                    await agent.runtime.aupdate_state(
                        runtime_config,
                        values={
                            "messages": [
                                SystemMessage(
                                    content=f"SYSTEM NOTIFICATION: Maximum execution time exceeded "
                                    f"({exc.max_execution_time:.0f}s). Conversation state saved. "
                                    f"Please continue with a simpler task or ask for help."
                                )
                            ]
                        },
                    )
                    ctx.console.print(f"[dim]Agent notified. Conversation saved.[/]")
                    logger.info("Agent notified about max_execution_time via SystemMessage")
                except Exception as update_exc:
                    logger.error(f"Failed to update agent state: {update_exc}")
                    ctx.console.print(f"[yellow]Warning: Could not notify agent[/]")

                return "[Execution time limit exceeded - conversation saved]"
            except Exception as exc:
                logger.error(f"Unexpected error in agent streaming: {exc}", exc_info=True)
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
                        shell_workspace=shell_workspace_for_preview,
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
    except (KeyboardInterrupt, asyncio.CancelledError):
        ctx.console.print(
            "\nExecution interrupted by user.",
            style=COLORS["warning"],
        )

        try:
            # NOTE: Do NOT use event_handler.last_agent_state here!
            # Extract full state from runtime_checkpointer instead.
            deep_checkpointer.persist_from_runtime(
                session_id,
                runtime_checkpointer,
                runtime_config,
                agent_state=None,  # Force using runtime_checkpointer
            )
        except Exception as exc:
            logger.warning("Failed to persist conversation on interrupt: %s", exc)

        ctx.console.print("Updating agent state...", style=COLORS["text_dim"])
        try:
            from langchain_core.messages import SystemMessage

            await agent.runtime.aupdate_state(
                runtime_config,
                values={
                    "messages": [
                        SystemMessage(
                            content="[User interrupted the previous request with Ctrl+C]"
                        )
                    ]
                },
            )
            ctx.console.print("Ready for next command.", style=COLORS["text_dim"])
            logger.info("Agent notified about user interrupt via SystemMessage")
        except Exception as update_exc:
            logger.error("Failed to update agent state: %s", update_exc)
            ctx.console.print(
                "Warning: Could not notify agent",
                style=COLORS["warning"],
            )

        return ""

    if timed_out:
        ctx.console.print("[bold red]Deep agent execution timed out.[/]")
        return ""

    # Normal completion - persist
    # NOTE: Do NOT use event_handler.last_agent_state here!
    # It only contains the last update chunk, which may miss HumanMessages.
    # Instead, let persist_from_runtime() extract the full state from runtime_checkpointer.
    deep_checkpointer.persist_from_runtime(
        session_id,
        runtime_checkpointer,
        runtime_config,
        agent_state=None,  # Force using runtime_checkpointer
    )
    logger.info("[CONVERSATION] Persistence completed for session %s", session_id)

    # Get final state for result preparation (event_handler state is OK for this purpose)
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
