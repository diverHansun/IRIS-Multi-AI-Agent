"""Deep agent conversation helpers."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from rich.markup import escape

import asyncio

from langgraph.errors import GraphRecursionError
from langgraph.types import Command, Interrupt

from .event_handler import DeepAgentEventHandler
from ..hitl.handler import handle_hitl_interrupt, HITLDecisionError
from ..hitl.session_manager import SessionHITLManager
from ..hitl.file_ops import FileOpTracker

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


def _ensure_checkpoint_namespace(agent: Any, runtime_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarantee LangGraph runtime configs include checkpoint namespace metadata.
    """
    configurable = runtime_config.setdefault("configurable", {})
    checkpoint_ns = configurable.get("checkpoint_ns")
    if checkpoint_ns:
        return runtime_config

    namespace = getattr(agent, "checkpoint_namespace", None)
    if namespace is None and hasattr(agent, "get_checkpoint_namespace"):
        try:
            namespace = agent.get_checkpoint_namespace()
        except Exception:  # pylint: disable=broad-except
            namespace = None
    configurable["checkpoint_ns"] = namespace or "deep_agent::default"
    return runtime_config


def _sync_history_to_runtime(agent: Any, runtime_config: Dict[str, Any]) -> None:
    """
    Synchronize conversation history from storage checkpointer to runtime checkpointer.

    This enables the runtime to have access to previous conversation context
    while using MemorySaver for HITL support.

    Args:
        agent: Agent instance with dual checkpointers
        runtime_config: Runtime configuration containing thread_id
    """
    if not hasattr(agent, "storage_checkpointer") or agent.storage_checkpointer is None:
        return

    runtime_config = _ensure_checkpoint_namespace(agent, runtime_config)

    try:
        # Load checkpoint from storage (UnifiedCheckpointer)
        checkpoint_tuple = agent.storage_checkpointer.get_tuple(runtime_config)

        if checkpoint_tuple:
            # Ensure checkpoint has required metadata for LangGraph
            checkpoint_ns = runtime_config.get("configurable", {}).get("checkpoint_ns", "")
            metadata_with_ns = dict(checkpoint_tuple.metadata or {})
            metadata_with_ns.setdefault("checkpoint_ns", checkpoint_ns)

            # Restore to runtime checkpointer (MemorySaver)
            agent.runtime_checkpointer.put(
                runtime_config,
                checkpoint_tuple.checkpoint,
                metadata_with_ns,
                checkpoint_tuple.checkpoint.get("channel_versions", {})
            )
            logger.debug(
                "Loaded conversation history to runtime checkpointer for thread_id=%s",
                runtime_config.get("configurable", {}).get("thread_id")
            )
    except Exception as exc:
        logger.warning("Failed to sync history to runtime checkpointer: %s", exc)


def _flatten_checkpoint_messages(entries: Any) -> List[Any]:
    """Extract BaseMessage instances from nested checkpoint structures."""

    from langchain_core.messages import BaseMessage

    flattened: List[Any] = []
    stack: List[Any] = [entries]

    while stack:
        item = stack.pop()

        if isinstance(item, BaseMessage):
            flattened.append(item)
            continue

        if item is None:
            continue

        if asyncio.iscoroutine(item):
            # Skip coroutines entirely
            continue

        if isinstance(item, dict):
            item_type = item.get("type")
            value = item.get("value")

            if item_type == "message" and isinstance(value, BaseMessage):
                flattened.append(value)
                continue

            # Some LangGraph write operations wrap the message in the "value" field
            if value is not None:
                stack.append(value)

            # Also traverse other dict values (lists, tuples, etc.)
            for dict_value in item.values():
                if dict_value is value:
                    continue
                stack.append(dict_value)
            continue

        if isinstance(item, (list, tuple)):
            stack.extend(reversed(item))
            continue

        if isinstance(item, set):
            stack.extend(item)
            continue

    return flattened


def _sync_runtime_to_storage(agent: Any, runtime_config: Dict[str, Any]) -> None:
    """
    Synchronize final state from runtime checkpointer to storage checkpointer.

    After streaming completes, save the filtered conversation
    (HumanMessage/AIMessage only) to long-term storage.

    Args:
        agent: Agent instance with dual checkpointers
        runtime_config: Runtime configuration containing thread_id
    """
    if not hasattr(agent, "storage_checkpointer") or agent.storage_checkpointer is None:
        return

    runtime_config = _ensure_checkpoint_namespace(agent, runtime_config)

    try:
        # Get final checkpoint from runtime (MemorySaver)
        final_checkpoint = agent.runtime_checkpointer.get_tuple(runtime_config)

        if final_checkpoint:
            # Clean checkpoint before passing to storage
            # Filter out LangGraph internal structures (coroutines, write operations)
            # that may exist in messages during HITL operations
            from langchain_core.messages import BaseMessage

            checkpoint_copy = final_checkpoint.checkpoint.copy()
            channel_values = dict(checkpoint_copy.get("channel_values", {}))
            messages = channel_values.get("messages", [])

            filtered_messages = _flatten_checkpoint_messages(messages)
            channel_values["messages"] = filtered_messages
            checkpoint_copy["channel_values"] = channel_values

            logger.debug(
                "Filtered checkpoint messages: %d -> %d (removed %d non-message objects)",
                len(messages), len(filtered_messages), len(messages) - len(filtered_messages)
            )

            # Save to storage (UnifiedCheckpointer automatically filters)
            # Pass channel_versions as new_versions parameter
            agent.storage_checkpointer.put(
                runtime_config,
                checkpoint_copy,
                final_checkpoint.metadata,
                checkpoint_copy.get("channel_versions", {})
            )
            logger.debug(
                "Saved conversation history to storage checkpointer for thread_id=%s",
                runtime_config.get("configurable", {}).get("thread_id")
            )
    except Exception as exc:
        logger.warning("Failed to sync runtime to storage checkpointer: %s", exc)


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
    hitl_config = metadata.get("hitl_config", {})
    hitl_manager = _ensure_hitl_manager(ctx, hitl_config)

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
    runtime_input = agent.create_runtime_input(query)
    runtime_config = agent.create_runtime_config(session_id)
    max_execution_time = safety_opts.get("max_execution_time")
    deadline = time.perf_counter() + max_execution_time if isinstance(max_execution_time, (int, float)) else None

    # Session lifecycle: Load history from storage to runtime checkpointer
    # Following SOLID SRP: Conversation handler manages session synchronization
    _sync_history_to_runtime(agent, runtime_config)

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

    # Session lifecycle: Save filtered messages from runtime to storage checkpointer
    # This persists the conversation while keeping storage lean
    _sync_runtime_to_storage(agent, runtime_config)

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
