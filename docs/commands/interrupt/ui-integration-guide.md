# UI Integration Guide for Interrupt Mechanism

## Overview

This document specifies how interrupt-related messages should be displayed using the project's standardized CLI theme system located in `src/application/cli/`.

## UI Theme System

### Core Components

**Files**:
- `src/application/cli/theme.py` - Color schemes, symbols, panel defaults
- `src/application/cli/gui/render.py` - Rendering helpers with Panel and Table
- `src/application/cli/gui/interact.py` - User interaction helpers

### Theme Standards

**No Emoji Policy**: The project explicitly avoids emoji. Use ASCII/Unicode symbols from `theme.py`.

**Color Palette** (`COLORS`):
```python
{
    "primary": "#A8E650",     # Main brand color
    "secondary": "#50B4FF",   # Secondary accent
    "success": "#34d399",     # Success states
    "warning": "#fbbf24",     # Warnings
    "error": "#ef4444",       # Errors
    "info": "#3b82f6",        # Informational
    "text_primary": "#ffffff",# Primary text
    "text_dim": "#6b7280",    # Dimmed text
    "user": "#ffffff",        # User messages
    "agent": "#A8E650",       # Agent responses
    "tool": "#fbbf24",        # Tool indicators
}
```

**Status Symbols** (`STATUS_SYMBOLS`):
```python
{
    "completed": "[OK]",
    "in_progress": "[..]",
    "pending": "[ ]",
    "failed": "[X]",
}
```

**Panel Defaults** (`PANEL_DEFAULTS`):
```python
{
    "box": box.ROUNDED,
    "padding": (0, 1),
}
```

## Interrupt Message Guidelines

### DeepAgent Mode

**First Ctrl+C (Interrupt Conversation)**:
```python
# Immediate feedback
ctx.console.print(
    "\nExecution interrupted by user.",
    style=COLORS["warning"]
)

# State update notification
ctx.console.print(
    "Updating agent state...",
    style=COLORS["text_dim"]
)

# Completion confirmation
ctx.console.print(
    "Ready for next command.",
    style=COLORS["text_dim"]
)
```

**Second Ctrl+C (Exit Application)**:
```python
ctx.console.print(
    "\nGoodbye!",
    style=COLORS["info"]
)
```

**Double Ctrl+C Hint**:
```python
ctx.console.print(
    "\nInterrupted. Press Ctrl+C again within 3s to exit.",
    style=COLORS["warning"]
)
```

### BasicAgent Mode

**Interrupt During Execution**:
```python
ctx.console.print(
    "\nAgent execution interrupted by user.",
    style=COLORS["warning"]
)
```

### LLM Mode

**Interrupt During Streaming**:
```python
console.print(
    "\nResponse interrupted by user",
    style=COLORS["warning"]
)
```

**Partial Response Display**:
```python
from rich.panel import Panel
from src.application.cli.theme import PANEL_DEFAULTS, COLORS

console.print(
    Panel(
        partial_response,
        title="[bold]AI Response (Interrupted)[/bold]",
        border_style=COLORS["warning"],
        **PANEL_DEFAULTS,
    )
)
```

**No Content Received**:
```python
console.print(
    "No content received before interruption",
    style=COLORS["text_dim"]
)
```

## Implementation Examples

### Example 1: DeepAgent Interrupt Handler

**File**: `src/application/services/agent/deep/streaming/conversation.py`

```python
from src.application.cli.theme import COLORS

except KeyboardInterrupt:
    ctx.console.print(
        "\nExecution interrupted by user.",
        style=COLORS["warning"]
    )

    # Persist state
    await _persist_conversation_state(
        ctx, session_ctx, runtime_checkpointer,
        runtime_config, agent_memory_sync,
        reason="user_interrupt"
    )

    # Notify agent
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

### Example 2: Main Loop Double Ctrl+C Handler

**File**: `src/application/cli/main.py`

```python
from src.application.cli.theme import COLORS
import time

except KeyboardInterrupt:
    now = time.monotonic()

    if ctx.exit_hint_until and now < ctx.exit_hint_until:
        # Second press - exit
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
        continue
```

### Example 3: LLM Streaming Interrupt

**File**: `src/llm/utils/streaming.py`

```python
from rich.panel import Panel
from src.application.cli.theme import COLORS, PANEL_DEFAULTS

except KeyboardInterrupt:
    interrupted = True
    logger.info(f"Streaming interrupted by user after {len(full_response)} characters")

    if display:
        display.stop()

    console.print(
        "\nResponse interrupted by user",
        style=COLORS["warning"]
    )

    # Display partial response if available
    if full_response:
        try:
            console.print(
                Panel(
                    full_response,
                    title="[bold]AI Response (Interrupted)[/bold]",
                    border_style=COLORS["warning"],
                    **PANEL_DEFAULTS,
                )
            )
        except UnicodeEncodeError:
            # Fallback for encoding issues
            print(f"\n=== AI Response (Interrupted) ===")
            try:
                safe_response = full_response.encode('gbk', errors='replace').decode('gbk')
                print(safe_response)
            except:
                print("[Response contains special characters, cannot display completely]")
            print("=" * 50)
    else:
        console.print(
            "No content received before interruption",
            style=COLORS["text_dim"]
        )

    # Return partial result
    return {
        "response": full_response,
        "elapsed_time": time.time() - start_time,
        "chunk_count": chunk_count,
        "characters": len(full_response),
        "success": True,
        "interrupted": True,
    }
```

## Message Style Guide

### Interrupt Notifications

**Pattern**: Direct, concise, user-facing
```python
# Good
ctx.console.print("\nExecution interrupted by user.", style=COLORS["warning"])

# Avoid
ctx.console.print("\n[yellow]Interrupted by user[/yellow]")  # Don't hardcode colors
```

### State Updates

**Pattern**: Dimmed, progress indication
```python
# Good
ctx.console.print("Updating agent state...", style=COLORS["text_dim"])
ctx.console.print("Ready for next command.", style=COLORS["text_dim"])

# Avoid
ctx.console.print("[dim]Agent notified. You can continue the conversation.[/]")  # Too verbose
```

### Warnings

**Pattern**: Clear indication of non-critical issues
```python
# Good
ctx.console.print("Warning: Could not notify agent", style=COLORS["warning"])

# Avoid
ctx.console.print("[yellow]Warning: Failed to update agent state[/]")  # Don't use Rich markup directly
```

### Exit Messages

**Pattern**: Simple, friendly
```python
# Good
ctx.console.print("\nGoodbye!", style=COLORS["info"])

# Avoid
ctx.console.print("\n\n[yellow]Interrupted[/yellow]")  # Not user-friendly
```

## Panel Usage

**When to use Panels**:
- Displaying structured information (help, status, configuration)
- Showing partial LLM responses
- Presenting multi-line formatted content

**When NOT to use Panels**:
- Simple one-line notifications
- Progress indicators
- Interrupt feedback (use direct console.print instead)

**Example**:
```python
# Good - Panel for structured content
console.print(
    Panel(
        partial_response,
        title="[bold]AI Response (Interrupted)[/bold]",
        border_style=COLORS["warning"],
        **PANEL_DEFAULTS,
    )
)

# Bad - Panel for simple message
console.print(
    Panel("Interrupted by user", border_style="yellow")  # Overkill
)
```

## Best Practices

1. **Always import COLORS from theme**:
   ```python
   from src.application.cli.theme import COLORS
   ```

2. **Use semantic color names**:
   ```python
   # Good
   style=COLORS["warning"]
   style=COLORS["text_dim"]

   # Avoid
   style="yellow"
   style="#fbbf24"
   ```

3. **Preserve newlines for readability**:
   ```python
   # Good
   ctx.console.print("\nInterrupted. Press Ctrl+C again within 3s to exit.", style=COLORS["warning"])

   # Avoid
   ctx.console.print("Interrupted. Press Ctrl+C again within 3s to exit.", style=COLORS["warning"])
   ```

4. **Use Rich markup sparingly**:
   ```python
   # Good
   ctx.console.print("Ready for next command.", style=COLORS["text_dim"])

   # Avoid
   ctx.console.print("[dim]Ready for next command.[/]")
   ```

5. **Consistent message terminology**:
   - "Interrupted" not "Cancelled"
   - "Ready for next command" not "You can continue"
   - "Updating agent state" not "Saving state"

## Integration Checklist

Before implementing interrupt messages:

- [ ] Import COLORS from `src.application.cli.theme`
- [ ] Use semantic color names (warning, text_dim, info, error)
- [ ] Apply PANEL_DEFAULTS for any Panel usage
- [ ] Avoid emoji and Rich markup in favor of theme symbols
- [ ] Keep messages concise and user-facing
- [ ] Use dimmed style for progress/technical details
- [ ] Test with project's console theme
- [ ] Verify color consistency across different terminal types

## Reference Files

**Required Reading**:
- `src/application/cli/theme.py` - Complete theme system
- `src/application/cli/gui/render.py` - Panel and Table rendering examples
- `src/application/cli/main.py` - Existing console usage patterns

**Example Usage**:
- Look at how `print_help()` and `render_info()` use Panels
- See how error messages use `COLORS["error"]`
- Study how warnings use `COLORS["warning"]`
