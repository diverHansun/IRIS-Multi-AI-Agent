# BasicAgent Interrupt Mechanism Implementation

## Objective

Implement keyboard interrupt handling for BasicAgent mode that allows users to interrupt ongoing agent execution without terminating the CLI. BasicAgent does not require state persistence on interrupt.

**Behavior**:
- Ctrl+C during execution: Stop current agent call, return to CLI loop
- No conversation state persistence needed (stateless design)
- User can immediately issue new query after interrupt

## Reference Implementation

### Official DeepAgents CLI

**Primary Reference**:
- `deepagents/libs/deepagents-cli/deepagents_cli/execution.py:630-650`

**Key Pattern**:
```python
except asyncio.CancelledError:
    if spinner_active:
        status.stop()
    console.print("\n[yellow]Interrupted by user[/yellow]")
    console.print("Updating agent state...", style="dim")

    try:
        await agent.aupdate_state(
            config=config,
            values={
                "messages": [
                    HumanMessage(content="[The previous request was cancelled by the system]")
                ]
            },
        )
        console.print("Ready for next command.\n", style="dim")
    except Exception as e:
        console.print(f"[red]Warning: Failed to update agent state: {e}[/red]\n")

    return
```

**Difference for BasicAgent**:
BasicAgent uses standard LangChain AgentExecutor without LangGraph's runtime state management, so `aupdate_state` is not applicable. Instead, we simply catch the interrupt and return.

## Current Project Status

**File to Modify**:
- `src/application/services/agent/basic/conversation.py:19-65`

**Current Implementation**:
```python
async def handle_agent_query(ctx, query: str) -> str:
    config = _get_agent_config(ctx)
    agent = config.get("agent_instance")
    if agent is None:
        raise RuntimeError("Agent engine is not initialized.")

    with ctx.console.status("[dim]Agent reasoning...[/]"):
        result = await agent.ainvoke(query, session_id=ctx.session_id)

    # ... rest of the function
```

**Issue**: No interrupt handling - KeyboardInterrupt would propagate to main loop and cause exit

## Implementation Plan

### Step 1: Add KeyboardInterrupt Handler

**File**: `src/application/services/agent/basic/conversation.py`

Wrap execution in try-except block:

```python
async def handle_agent_query(ctx, query: str) -> str:
    """
    Handle an agent-oriented query where tool usage is permitted.
    """
    config = _get_agent_config(ctx)
    agent = config.get("agent_instance")
    if agent is None:
        raise RuntimeError("Agent engine is not initialized.")

    try:
        with ctx.console.status("[dim]Agent reasoning...[/]"):
            result = await agent.ainvoke(query, session_id=ctx.session_id)

        # Persist conversation to storage if memory sync is available
        if hasattr(ctx, 'memory_sync') and ctx.memory_sync:
            try:
                session_ctx = SessionContext(
                    session_id=ctx.session_id,
                    agent_type=config.get("agent_type", "basic"),
                    provider=config.get("provider", "unknown"),
                    function_type="agent",
                )
                ctx.memory_sync.persist_from_runtime(
                    session_ctx,
                    agent.checkpointer if hasattr(agent, 'checkpointer') else None,
                    None,
                    result,
                )
                logger.debug(f"Persisted Basic mode conversation for session {ctx.session_id}")
            except Exception as e:
                logger.warning(f"Failed to persist Basic mode conversation: {e}")

        if result.get("success"):
            answer = result.get("output", "No response generated.")
            ctx.console.print(f"[bold blue]BasicAgent >[/] {answer}")
            tool_calls = result.get("tool_calls", 0)
            if tool_calls:
                tool_names = result.get("tool_names") or []
                if tool_names:
                    ctx.console.print(f"[dim]Used {len(tool_names)} tools ({tool_calls} calls): {', '.join(tool_names)}[/]")
                else:
                    ctx.console.print(f"[dim]Used {tool_calls} tool calls[/]")
            return answer

        error_message = result.get("error", "Unknown error")
        ctx.console.print(f"[bold red]Agent Error: {error_message}[/]")
        return ""

    except KeyboardInterrupt:
        from src.application.cli.theme import COLORS

        # User interrupted agent execution
        ctx.console.print(
            "\nAgent execution interrupted by user.",
            style=COLORS["warning"]
        )
        logger.info("BasicAgent execution interrupted by user via Ctrl+C")
        return ""
    except asyncio.CancelledError:
        from src.application.cli.theme import COLORS

        # Async cancellation (e.g., from asyncio.timeout)
        ctx.console.print(
            "\nAgent execution cancelled.",
            style=COLORS["warning"]
        )
        logger.info("BasicAgent execution cancelled")
        return ""
```

### Step 2: Verify Main Loop Integration

**File**: `src/application/cli/main.py`

Ensure conversation handler catches interrupt:

```python
async def _handle_conversation(ctx: AppState, query: str) -> None:
    adapter = get_adapter(ctx.current_engine)
    try:
        await adapter.handle_query(ctx, query)  # This calls handle_agent_query
    except ExecutionTimeoutError as exc:
        # Handle execution timeout
        # ... existing timeout handling
    except KeyboardInterrupt:
        # Propagate to main loop for double-Ctrl+C handling
        raise
    except Exception as exc:
        ctx.console.print(f"[bold]Conversation error:[/bold] {exc}", style=COLORS["error"])
```

**Critical**: We must NOT catch KeyboardInterrupt here - let it propagate to the main loop's double-Ctrl+C handler.

## Behavior Flow

```
User presses Ctrl+C during BasicAgent execution
    |
    v
KeyboardInterrupt raised in agent.ainvoke()
    |
    v
Caught in handle_agent_query (conversation.py)
    |
    +-- Stop status display
    +-- Print interrupt message
    +-- Log interrupt event
    +-- Return empty string
    |
    v
Return to main CLI loop
    |
    v
Double-Ctrl+C logic handles exit confirmation
```

## Design Rationale

### Why No State Persistence?

**BasicAgent characteristics**:
1. Uses LangChain AgentExecutor (not LangGraph runtime)
2. Designed for simpler, stateless interactions
3. No checkpoint-based state management
4. Memory is handled by MemorySyncAdapter after completion

**Implications**:
- Interrupted queries are simply discarded
- No partial tool results saved
- User can immediately retry or rephrase
- Clean separation from DeepAgent's stateful design

### Why No Agent State Update?

Unlike DeepAgent's `agent.runtime.aupdate_state()`:
- BasicAgent doesn't have runtime state management
- AgentExecutor completes or fails atomically
- No intermediate state to preserve
- Next invocation starts fresh with loaded history

## Testing Scenarios

1. **Interrupt during tool execution**: Verify clean exit without errors
2. **Interrupt before tool execution**: Verify no partial state saved
3. **Rapid interrupts**: Verify no exception accumulation
4. **Memory persistence**: Verify interrupted query not saved to history
5. **Resume after interrupt**: Verify next query works normally

## Dependencies

**LangChain**:
- `AgentExecutor.ainvoke()` - Raises KeyboardInterrupt on Ctrl+C
- Standard Python async interrupt handling

**Project Components**:
- `AppState` - CLI context for console output
- `MemorySyncAdapter` - Handles successful conversation persistence only
- Main loop double-Ctrl+C handler - Manages exit confirmation

## Notes

- BasicAgent interrupt handling is simpler than DeepAgent (no state update needed)
- The main loop's double-Ctrl+C mechanism handles exit confirmation
- Memory persistence only happens on successful completion
- Interrupted executions leave no trace in conversation history
- This design maintains BasicAgent's simplicity while providing good UX
