# DeepAgent Interrupt Mechanism Implementation

## Objective

Implement a keyboard interrupt mechanism for DeepAgent mode that allows users to gracefully interrupt ongoing LLM/Agent conversations without terminating the CLI application.

**Behavior**:
- First Ctrl+C: Interrupt current conversation, preserve previous messages, continue CLI loop
- Second Ctrl+C (within 3 seconds): Exit the application

## Reference Implementation

### Official DeepAgents CLI

**Primary References**:
- `deepagents/libs/deepagents-cli/deepagents_cli/execution.py:630-673`
- `deepagents/libs/deepagents-cli/deepagents_cli/input.py:185-221`
- `deepagents/libs/deepagents-cli/deepagents_cli/config.py:337-350`
- `deepagents/libs/deepagents-cli/deepagents_cli/main.py:229-268`

**Key Implementation Points**:

1. **Session State Management** (`config.py:337-350`)
```python
class SessionState:
    def __init__(self, auto_approve: bool = False, no_splash: bool = False):
        self.auto_approve = auto_approve
        self.no_splash = no_splash
        self.exit_hint_until: float | None = None
        self.exit_hint_handle = None
        self.thread_id = str(uuid.uuid4())
```

2. **Double Ctrl+C Handler** (`input.py:185-221`)
```python
@kb.add("c-c")
def _(event) -> None:
    """Require double Ctrl+C within a short window to exit."""
    app = event.app
    now = time.monotonic()

    if session_state.exit_hint_until is not None and now < session_state.exit_hint_until:
        # Second press - exit
        handle = session_state.exit_hint_handle
        if handle:
            handle.cancel()
            session_state.exit_hint_handle = None
        session_state.exit_hint_until = None
        app.invalidate()
        app.exit(exception=KeyboardInterrupt())
        return

    # First press - set hint window
    session_state.exit_hint_until = now + EXIT_CONFIRM_WINDOW  # 3.0 seconds
    session_state.exit_hint_handle = loop.call_later(EXIT_CONFIRM_WINDOW, clear_hint)
    app.invalidate()
```

3. **Agent State Update** (`execution.py:630-673`)
```python
except KeyboardInterrupt:
    if spinner_active:
        status.stop()
    console.print("\n[yellow]Interrupted by user[/yellow]")
    console.print("Updating agent state...", style="dim")

    try:
        await agent.aupdate_state(
            config=config,
            values={
                "messages": [
                    HumanMessage(content="[User interrupted the previous request with Ctrl+C]")
                ]
            },
        )
        console.print("Ready for next command.\n", style="dim")
    except Exception as e:
        console.print(f"[red]Warning: Failed to update agent state: {e}[/red]\n")

    return
```

4. **Main Loop Handler** (`main.py:229-268`)
```python
while True:
    try:
        user_input = await session.prompt_async()
        if session_state.exit_hint_handle:
            session_state.exit_hint_handle.cancel()
            session_state.exit_hint_handle = None
        session_state.exit_hint_until = None
        # ... process input
    except KeyboardInterrupt:
        console.print("\nGoodbye!", style=COLORS["primary"])
        break
```

## Current Project Status

**Files to Modify**:
- `src/application/cli/state.py` - Add interrupt state fields
- `src/application/cli/main.py:108-111` - Implement double Ctrl+C logic
- `src/application/services/agent/deep/streaming/conversation.py:340-342` - Add agent state update

**Current Issues**:
1. `main.py:108-111`: Direct exit on first Ctrl+C without state preservation
2. `conversation.py:340-342`: No agent state notification on interrupt
3. Missing session state fields for interrupt tracking

## Implementation Plan

### Step 1: Update AppState Class

**File**: `src/application/cli/state.py`

Add interrupt tracking fields:
```python
class AppState:
    # Existing fields...

    # Interrupt handling
    exit_hint_until: Optional[float] = None
    exit_hint_handle: Optional[asyncio.TimerHandle] = None
```

### Step 2: Implement Double Ctrl+C in Main Loop

**File**: `src/application/cli/main.py`

Replace lines 108-111:
```python
except KeyboardInterrupt:
    import time
    now = time.monotonic()

    if ctx.exit_hint_until and now < ctx.exit_hint_until:
        # Second press within window - exit
        if ctx.exit_hint_handle:
            ctx.exit_hint_handle.cancel()
            ctx.exit_hint_handle = None
        ctx.exit_hint_until = None
        ctx.console.print("\nGoodbye!", style=COLORS["info"])
        break
    else:
        # First press - set hint window
        EXIT_CONFIRM_WINDOW = 3.0
        ctx.exit_hint_until = now + EXIT_CONFIRM_WINDOW

        # Cancel old timer if exists
        if ctx.exit_hint_handle:
            ctx.exit_hint_handle.cancel()

        # Schedule hint clearing
        loop = asyncio.get_running_loop()
        def clear_hint():
            if ctx.exit_hint_until and time.monotonic() >= ctx.exit_hint_until:
                ctx.exit_hint_until = None
                ctx.exit_hint_handle = None

        ctx.exit_hint_handle = loop.call_later(EXIT_CONFIRM_WINDOW, clear_hint)

        ctx.console.print(
            "\nInterrupted. Press Ctrl+C again within 3s to exit.",
            style=COLORS["warning"]
        )
        continue  # Continue CLI loop
```

### Step 3: Update DeepAgent Conversation Handler

**File**: `src/application/services/agent/deep/streaming/conversation.py`

Replace lines 340-342:
```python
except KeyboardInterrupt:
    from src.application.cli.theme import COLORS

    ctx.console.print(
        "\nExecution interrupted by user.",
        style=COLORS["warning"]
    )

    # Persist conversation state before interrupt (exclude interrupted message)
    await _persist_conversation_state(
        ctx, session_ctx, runtime_checkpointer,
        runtime_config, agent_memory_sync,
        reason="user_interrupt"
    )

    # Notify agent about interruption using SystemMessage
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
        logger.error(f"Failed to update agent state: {update_exc}")
        ctx.console.print(
            "Warning: Could not notify agent",
            style=COLORS["warning"]
        )

    return ""
```

### Step 4: Clear Hint State After User Input

**File**: `src/application/cli/main.py`

After line 93 (after getting user input):
```python
query = await asyncio.to_thread(ctx.console.input, prompt)

# Clear exit hint state when user provides new input
if ctx.exit_hint_handle:
    ctx.exit_hint_handle.cancel()
    ctx.exit_hint_handle = None
ctx.exit_hint_until = None

if not query.strip():
    continue
```

## State Preservation Strategy

**What to preserve**:
- All messages before the interrupted query
- Agent's partial reasoning (already in checkpoint)

**What NOT to preserve**:
- The interrupted user query (not sent to storage)
- Incomplete agent responses (LangGraph handles via checkpoint)

**Persistence Flow**:
1. User presses Ctrl+C during agent execution
2. `KeyboardInterrupt` caught in `conversation.py`
3. Call `_persist_conversation_state` with reason="user_interrupt"
4. Filter messages using `agent_memory_sync.filter_messages_for_storage`
5. Save to storage via `agent_memory_sync.storage.save_session`
6. Update agent runtime state with SystemMessage notification
7. Return to CLI loop

## Testing Scenarios

1. **Interrupt during tool execution**: Verify checkpoint saves tool call state
2. **Interrupt during streaming**: Verify partial response not saved
3. **Double Ctrl+C timing**: Verify 3-second window works correctly
4. **State recovery**: Verify next query has correct conversation history
5. **Multiple interrupts**: Verify repeated interrupts don't corrupt state

## Dependencies

**LangGraph**:
- `agent.runtime.aupdate_state()` - Update runtime state without triggering execution
- Runtime checkpointer (MemorySaver) - Manages in-memory conversation state
- SystemMessage injection - Notifies agent without persisting to storage

**Project Components**:
- `MemorySyncAdapter.filter_messages_for_storage` - Filters out system messages
- `persist_conversation_state` - Unified persistence helper
- `AppState` - CLI session state management

## Notes

- SystemMessage is used for agent notification because it won't be persisted to long-term storage
- The interrupted message preservation is handled by LangGraph's checkpoint mechanism
- Timer cleanup prevents memory leaks from repeated interrupts
- The 3-second window provides good UX without being too restrictive
