# DeepAgent Interrupt Issue Analysis

## Error Trace

```
Traceback (most recent call last):
  File "conversation.py", line 198, in handle_deep_agent_query
    async for event in agent.runtime.astream(
  File "langgraph/pregel/main.py", line 2956, in astream
    async for _ in runner.atick(
  File "langgraph/pregel/_runner.py", line 377, in atick
    done, inflight = await asyncio.wait(
  File "asyncio/tasks.py", line 428, in wait
    return await _wait(fs, timeout, return_when, loop)
  File "asyncio/tasks.py", line 535, in _wait
    await waiter
asyncio.exceptions.CancelledError

During handling of the above exception, another exception occurred:
KeyboardInterrupt
```

## Problem Analysis

### Issue 1: Missing CancelledError Handler

**Location**: `src/application/services/agent/deep/streaming/conversation.py:197-340`

The code only catches `KeyboardInterrupt` at line 341, but NOT `asyncio.CancelledError`.

**Current Code Structure**:
```python
try:
    while True:
        try:
            async for event in agent.runtime.astream(...):
                # Process events
        except GraphRecursionError as exc:
            # Handle recursion
        except TimeoutError as exc:
            # Handle timeout
        except ExecutionTimeoutError as exc:
            # Handle execution timeout
        except Exception as exc:
            # Handle generic exceptions

        # HITL interrupt handling
        if captured_interrupts:
            # Process interrupts
        else:
            break

except KeyboardInterrupt:  # ❌ Only catches KeyboardInterrupt
    # Handle interrupt
```

**What Happens**:
1. User presses Ctrl+C
2. LangGraph's `astream()` is running in `asyncio.wait()`
3. asyncio converts Ctrl+C to `CancelledError` (not `KeyboardInterrupt`)
4. `CancelledError` bubbles up through LangGraph stack
5. No handler catches it in the inner `try` block
6. `CancelledError` propagates to outer `try` block
7. Outer block only has `except KeyboardInterrupt`, misses `CancelledError`
8. Exception continues to propagate, causing crash

### Issue 2: LangGraph Async Stream Cleanup

**LangGraph Behavior**:
- `agent.runtime.astream()` is an async generator from LangGraph
- When interrupted, it's in the middle of `asyncio.wait()`
- The generator needs proper cleanup to avoid "already running" errors

**Call Stack**:
```
agent.runtime.astream()  [LangGraph async generator]
    ↓
runner.atick()  [LangGraph internal]
    ↓
asyncio.wait()  [Waiting for tasks]
    ↓
Ctrl+C → CancelledError raised here
```

### Issue 3: Exception Type Mismatch

**In Async Context**:
- `KeyboardInterrupt` → Only raised in main thread / synchronous code
- `asyncio.CancelledError` → Raised in async code when interrupted

**DeepAgent is Async**:
- `handle_deep_agent_query` is async function
- `agent.runtime.astream()` is async generator
- Therefore, we get `CancelledError`, not `KeyboardInterrupt`

## Why LLM/BasicAgent Work But DeepAgent Doesn't

### LLM Mode
```python
# LLM streaming (simplified)
async for chunk in streaming_llm.stream_generate(prompt):
    # Simple async iteration
    await asyncio.sleep(0.05)
```
- Simple async loop
- We added `except (KeyboardInterrupt, asyncio.CancelledError)` ✅
- Works correctly

### BasicAgent Mode
```python
# BasicAgent (simplified)
with ctx.console.status("Agent reasoning..."):
    result = await agent.ainvoke(query)
```
- Single async call, not streaming
- Completes quickly or gets cancelled
- Handler added: `except (KeyboardInterrupt, asyncio.CancelledError)` ✅
- Works correctly

### DeepAgent Mode
```python
# DeepAgent (current - BROKEN)
async for event in agent.runtime.astream(...):
    # LangGraph complex async streaming
    # Multiple nested async operations
    # HITL interrupts, middleware, checkpointing
```
- Complex LangGraph async streaming
- Only catches `KeyboardInterrupt` ❌
- Missing `asyncio.CancelledError` handler ❌
- Crashes on Ctrl+C

## Solution Requirements

### 1. Catch Both Exception Types

**Outer try-except** (line 341):
```python
# Current (WRONG)
except KeyboardInterrupt:
    # Handle interrupt

# Required (CORRECT)
except (KeyboardInterrupt, asyncio.CancelledError):
    # Handle interrupt
```

### 2. Inner Exception Handling

The inner `try` block (line 197) also needs to handle cancellation:

```python
try:
    async for event in agent.runtime.astream(...):
        # Process events
except (KeyboardInterrupt, asyncio.CancelledError):
    # Break out of streaming loop
    break
except GraphRecursionError as exc:
    # Existing handlers...
```

### 3. Proper State Cleanup

When interrupted:
1. Stop the LangGraph stream gracefully
2. Persist conversation state (excluding interrupted message)
3. Notify agent runtime with SystemMessage
4. Return control to main loop for double Ctrl+C handling

## Comparison with Official DeepAgents

### Official Pattern (deepagents-cli/execution.py:630-650)

```python
try:
    async for chunk in agent.astream(...):
        # Process chunks

except asyncio.CancelledError:  # ✅ Catches CancelledError
    if spinner_active:
        status.stop()
    console.print("\n[yellow]Interrupted by user[/yellow]")

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

except KeyboardInterrupt:  # ✅ Also catches KeyboardInterrupt
    # Same handling as CancelledError
    return
```

**Key Differences**:
1. Official catches BOTH `CancelledError` and `KeyboardInterrupt` ✅
2. Official handles them separately but identically
3. Official uses `return` to exit cleanly

### Our Current Implementation

```python
except KeyboardInterrupt:  # ❌ Only catches KeyboardInterrupt
    ctx.console.print("\nExecution interrupted by user.", style=COLORS["warning"])

    try:
        await _persist_conversation_state(...)
        # ... state update logic
    except Exception as update_exc:
        logger.error(f"Failed to update agent state: {update_exc}")

    return ""
```

**Problems**:
1. Missing `asyncio.CancelledError` handler ❌
2. Only catches `KeyboardInterrupt` which doesn't happen in async context ❌

## Current Implementation Problem

### What Actually Happens (Lines 214-217)

Current code:
```python
except (KeyboardInterrupt, asyncio.CancelledError):
    logger.info("Deep agent streaming interrupted by user")
    break  # ← PROBLEM: Only exits inner while, not triggering outer except
```

Execution flow:
```
while True (outer):              [Line 193]
    try:
        async for event in astream():  [Line 198]
            # Process events
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("...")
        break  # ← Exits inner while loop, not raising exception

    # After break, continues here:
    if timed_out:                [Line 316]
        break

    if captured_interrupts:      [Line 320]
        # Process HITL
    else:
        break                    [Line 344]

# Inner while loop exits normally - outer except never triggered!
except (KeyboardInterrupt, asyncio.CancelledError):  [Line 345]
    # This block is NEVER reached when inner except catches and breaks
    # ❌ Missing interrupt handling!
```

### Why The Outer Exception Handler Never Executes

1. User presses Ctrl+C during `agent.runtime.astream()`
2. `asyncio.CancelledError` is raised and caught at line 214
3. `break` statement exits the inner `while True` loop
4. Control continues to line 316 (checks `if timed_out:`)
5. Control continues to line 320 (checks `if captured_interrupts:`)
6. Since no actual interrupts were captured, goes to line 344 (`else: break`)
7. The outer `while True` loop exits normally
8. No exception is raised, so outer `except (KeyboardInterrupt, asyncio.CancelledError)` at line 345 is NEVER triggered
9. Code continues to line 388 and beyond
10. Since `event_handler.last_agent_state` is None, displays error: "Deep agent failed to produce a response."

### Why `break` Doesn't Work Here

The difference between exception flow:

**Option 1: Using `break` (WRONG)**
```
Inner except catches exception
  |
  v
break statement
  |
  v
Inner while loop exits normally
  |
  v
Outer except NEVER triggered
  |
  v
Function continues to line 388
```

**Option 2: Using `raise` (CORRECT)**
```
Inner except catches exception
  |
  v
raise statement
  |
  v
Exception propagates to outer try
  |
  v
Outer except CATCHES IT
  |
  v
Proper cleanup and return ""
```

## Recommended Fix

### Location 1: Inner Try Block (Line 214)

Change `break` to `raise`:

```python
except (KeyboardInterrupt, asyncio.CancelledError):
    # User interrupted - re-raise to trigger outer exception handler
    logger.info("Deep agent streaming interrupted by user")
    raise  # ✅ CORRECT: Propagate to outer except block
```

This allows the exception to propagate to the outer `try` block which has the proper cleanup code.

### Why This Works

When `raise` is used:
1. Exception is re-raised from inner except
2. Exception propagates through the while loop
3. Outer `except (KeyboardInterrupt, asyncio.CancelledError)` at line 345 catches it
4. Proper cleanup executes:
   - Display interrupt message
   - Persist conversation state
   - Notify agent runtime
   - Return "" to main loop

### Location 2: Outer Try Block (Line 345)

The outer exception handler (already exists) will now be triggered:

```python
except (KeyboardInterrupt, asyncio.CancelledError):  # Already in place
    ctx.console.print(
        "\nExecution interrupted by user.",
        style=COLORS["warning"],
    )

    try:
        await _persist_conversation_state(
            ctx,
            session_ctx,
            runtime_checkpointer,
            runtime_config,
            agent_memory_sync,
            reason="user_interrupt",
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
```

This block already has all the proper cleanup code. We just need to make sure it gets triggered by using `raise` instead of `break` in the inner handler.
```

## Testing Plan

After applying the fix (changing `break` to `raise` at line 217):

1. **Interrupt during model call**:
   Expected output:
   ```
   DEEP[S] > who are you?
   Deep agent reasoning...
   [Ctrl+C pressed]

   Execution interrupted by user.
   Updating agent state...
   Ready for next command.
   [Ready for next prompt]
   ```

2. **Interrupt during tool execution**:
   Expected output:
   ```
   DEEP[S] > read file
   Deep agent reasoning...
   [Tool execution interrupted with Ctrl+C]

   Execution interrupted by user.
   Updating agent state...
   Ready for next command.
   [Checkpoint preserved, ready for next prompt]
   ```

3. **Double Ctrl+C exit**:
   Expected output:
   ```
   DEEP[S] > query
   [Ctrl+C first time]
   Interrupted. Press Ctrl+C again within 3s to exit.

   [Ctrl+C second time within 3s]
   Goodbye!
   [Application exits cleanly]
   ```

## Summary

### Root Cause

The initial fix (adding `except (KeyboardInterrupt, asyncio.CancelledError):` at line 214) was incomplete:

1. Inner handler catches the exception with `break`
2. `break` only exits the inner while loop normally
3. Outer exception handler at line 345 is never triggered
4. No cleanup code executes
5. Function continues past line 388
6. Displays error: "Deep agent failed to produce a response."

### The Real Solution

Change line 217 from `break` to `raise`:

```python
except (KeyboardInterrupt, asyncio.CancelledError):
    logger.info("Deep agent streaming interrupted by user")
    raise  # <- Re-raise the exception
```

This allows the exception to propagate to the outer `try` block which contains all the proper cleanup logic:
- Display interrupt message
- Persist conversation state
- Notify agent runtime
- Return "" to continue CLI loop

### Why This Is The Correct Approach

1. Inner handler logs the interrupt and re-raises
2. Exception propagates through while loop
3. Outer `except` block at line 345 catches it
4. Proper cleanup executes (already implemented)
5. Function returns "" to main loop
6. CLI loop continues normally

This matches the official deepagents-cli pattern where exceptions trigger outer handlers with comprehensive cleanup code.
