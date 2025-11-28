# LLM Interrupt Mechanism Implementation

## Objective

Implement keyboard interrupt handling for LLM streaming mode that allows users to interrupt ongoing streaming responses while preserving the already-streamed content.

**Behavior**:
- Ctrl+C during streaming: Stop streaming, preserve partial response
- Display the already-streamed content
- User can immediately issue new query after interrupt

## Reference Implementation

### Official DeepAgents Pattern

While the official DeepAgents CLI doesn't have a dedicated LLM-only mode, we can reference the streaming interrupt handling pattern:

**Primary Reference**:
- `deepagents/libs/deepagents-cli/deepagents_cli/execution.py:630-650`

**Pattern**:
```python
except KeyboardInterrupt:
    if spinner_active:
        status.stop()
    console.print("\n[yellow]Interrupted by user[/yellow]")
    return
```

## Current Project Status

**Files to Modify**:
- `src/llm/utils/streaming.py:453-558` (StreamingManager.stream_chat method)

**Current Implementation**:
```python
async def stream_chat(
    self,
    provider: str,
    prompt: str,
    display_title: str = "AI Response",
    show_display: bool = True
) -> Dict[str, Any]:
    # ... initialization ...

    try:
        # Execute streaming generation
        async for chunk in streaming_llm.stream_generate(prompt):
            full_response += chunk
            chunk_count += 1

            if display:
                display.update(chunk)

            await asyncio.sleep(settings.streaming_delay_ms / 1000.0)

    except Exception as e:
        error_msg = f"Streaming chat failed: {str(e)}"
        logger.error(error_msg)
        full_response = error_msg
        # ... error handling ...

    finally:
        if display:
            display.stop()
        # ... final display and metrics ...
```

**Issue**: Generic exception handling catches KeyboardInterrupt, doesn't preserve partial response properly

## Implementation Plan

### Step 1: Add Dedicated KeyboardInterrupt Handler

**File**: `src/llm/utils/streaming.py`

Modify the `stream_chat` method (lines 453-558):

```python
async def stream_chat(
    self,
    provider: str,
    prompt: str,
    display_title: str = "AI Response",
    show_display: bool = True
) -> Dict[str, Any]:
    """
    Execute streaming chat.

    Args:
        provider: LLM provider
        prompt: Input prompt
        display_title: Display title
        show_display: Whether to show streaming UI

    Returns:
        Dictionary with response text and performance metrics
    """
    if provider not in self.streaming_llms:
        raise ValueError(f"Unregistered streaming LLM provider: {provider}")

    streaming_llm = self.streaming_llms[provider]
    full_response = ""
    start_time = time.time()
    chunk_count = 0
    interrupted = False

    # Initialize display
    display = None
    if show_display:
        display = StreamingDisplay(display_title)
        display.start()

    try:
        # Execute streaming generation
        async for chunk in streaming_llm.stream_generate(prompt):
            full_response += chunk
            chunk_count += 1

            # Update display
            if display:
                display.update(chunk)

            # Small delay for better visual effect
            await asyncio.sleep(settings.streaming_delay_ms / 1000.0)

    except KeyboardInterrupt:
        from src.application.cli.theme import COLORS, PANEL_DEFAULTS

        # User interrupted streaming - preserve partial response
        interrupted = True
        logger.info(f"Streaming interrupted by user after {len(full_response)} characters")

        if display:
            display.stop()

        console.print(
            "\nResponse interrupted by user",
            style=COLORS["warning"]
        )

        # Display partial response if any content was received
        if full_response:
            try:
                console.print(
                    Panel(
                        full_response,
                        title=f"[bold]{display_title} (Interrupted)[/bold]",
                        border_style=COLORS["warning"],
                        **PANEL_DEFAULTS,
                    )
                )
            except UnicodeEncodeError:
                print(f"\n=== {display_title} (Interrupted) ===")
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
            "success": True,  # Partial success
            "interrupted": True,
        }

    except Exception as e:
        error_msg = f"Streaming chat failed: {str(e)}"
        logger.error(error_msg)
        full_response = error_msg

        # Handle Unicode encoding errors
        if "gbk" in str(e) and "can't encode" in str(e):
            logger.warning("Detected Unicode encoding issue, not a network 502 error")
            full_response = "Response successful, but encountered encoding issues during display"

    finally:
        # Stop display
        if display and not interrupted:
            display.stop()

            # Calculate performance metrics
            elapsed = time.time() - start_time
            chars_per_second = len(full_response) / elapsed if elapsed > 0 else 0

            # Display final result and performance metrics
            if not interrupted:
                try:
                    console.print(
                        Panel(
                            full_response,
                            title=f"[bold]{display_title} (Complete)[/bold]",
                            border_style=COLORS["success"],
                            **PANEL_DEFAULTS,
                        )
                    )
                except UnicodeEncodeError:
                    print(f"\n=== {display_title} (Complete) ===")
                    try:
                        safe_response = full_response.encode('gbk', errors='replace').decode('gbk')
                        print(safe_response)
                    except:
                        print("[Response contains special characters, cannot display completely]")
                    print("=" * 50)

                if chunk_count > 0:
                    try:
                        console.print(
                            f"Performance: {elapsed:.2f}s | "
                            f"{len(full_response)} characters | "
                            f"{chars_per_second:.1f} chars/sec | "
                            f"{chunk_count} chunks",
                            style=COLORS["text_dim"],
                        )
                    except UnicodeEncodeError:
                        print(f"Performance: {elapsed:.2f}s | {len(full_response)} characters | {chars_per_second:.1f} chars/sec | {chunk_count} chunks")

    return {
        "response": full_response,
        "elapsed_time": time.time() - start_time,
        "chunk_count": chunk_count,
        "characters": len(full_response),
        "success": not full_response.startswith("Streaming chat failed"),
        "interrupted": False,
    }
```

### Step 2: Update Streaming Provider Classes

**File**: `src/llm/utils/streaming.py`

Ensure provider-specific generators don't catch KeyboardInterrupt:

**ZhipuStreamingLLM** (lines 209-236):
```python
async def stream_generate(
    self,
    prompt: str,
    on_token: Optional[Callable[[str], None]] = None
) -> AsyncGenerator[str, None]:
    """Zhipu AI streaming generation"""
    try:
        callback_handler = StreamingCallbackHandler(on_token)

        async for chunk in self.llm.astream(
            [HumanMessage(content=prompt)],
            config={"callbacks": [callback_handler]}
        ):
            if hasattr(chunk, 'content') and chunk.content:
                yield chunk.content
    except KeyboardInterrupt:
        # Allow interrupt to propagate up
        raise
    except Exception as e:
        logger.error(f"Zhipu AI streaming generation failed: {e}")
        yield f"Streaming generation error: {str(e)}"
```

**Apply same pattern to**:
- `OpenAIStreamingLLM.stream_generate` (lines 238-265)
- `OllamaStreamingLLM.stream_generate` (lines 267-388)

### Step 3: Update High-Level API

**File**: `src/llm/utils/streaming.py`

Ensure `stream_llm_response` preserves interrupt behavior:

```python
@for_llm_only
async def stream_llm_response(
    provider: str,
    prompt: str,
    llm: Optional[BaseChatModel] = None,
    display_title: str = "AI Response",
    show_display: bool = True
) -> str:
    """
    Convenience function for streaming LLM response.

    IMPORTANT: This function is for LLM direct chat only.
    DO NOT use this for Agent tool calling - use agent.ainvoke() instead.
    """
    # Dynamic registration if LLM provided
    if llm and provider not in streaming_manager.get_supported_providers():
        streaming_manager.register_llm(provider, llm)

    try:
        result = await streaming_manager.stream_chat(
            provider=provider,
            prompt=prompt,
            display_title=display_title,
            show_display=show_display
        )
        return result["response"]
    except KeyboardInterrupt:
        # Interrupt already handled in stream_chat, just propagate
        logger.info("LLM streaming interrupted, propagating to main loop")
        raise
```

## Behavior Flow

```
User presses Ctrl+C during LLM streaming
    |
    v
KeyboardInterrupt raised in streaming generator
    |
    v
Caught in stream_chat method
    |
    +-- Stop display (if active)
    +-- Print interrupt message
    +-- Display partial response (if any)
    +-- Calculate partial metrics
    +-- Return result with interrupted=True
    |
    v
Return to main CLI loop
    |
    v
Double-Ctrl+C logic handles exit confirmation
```

## Partial Response Handling

**Key Design Points**:

1. **Preserve accumulated content**:
   - `full_response` accumulates all chunks before interrupt
   - This content is displayed even if incomplete

2. **Visual indication**:
   - Panel title shows "(Interrupted)" instead of "(Complete)"
   - Border color changes to yellow (warning)
   - Separate message indicates interruption

3. **Metrics calculation**:
   - Performance metrics based on partial content
   - `interrupted` flag in result dictionary
   - `success=True` for partial results (user requested stop, not error)

## Memory Persistence

**LLM mode characteristics**:
- Uses `MemorySyncAdapter` for conversation history
- Interrupted responses should be saved if user wants to continue context
- Future enhancement: Add user prompt "Save partial response? (y/n)"

**Current behavior**:
- Partial responses are NOT saved to history
- Each LLM query is independent
- User can see partial response on screen for reference

**Future enhancement** (optional):
```python
if interrupted and full_response:
    # Ask user if they want to save partial response
    save_partial = console.input("Save partial response to history? (y/n): ")
    if save_partial.lower() == 'y':
        # Save to memory
        pass
```

## Testing Scenarios

1. **Interrupt early**: Verify minimal content displayed correctly
2. **Interrupt mid-stream**: Verify partial content preserved
3. **Interrupt near end**: Verify most content captured
4. **No content received**: Verify graceful handling
5. **Unicode content**: Verify encoding fallback works
6. **Rapid interrupts**: Verify no resource leaks

## Dependencies

**LangChain**:
- `BaseChatModel.astream()` - Raises KeyboardInterrupt on Ctrl+C
- Async generator interrupt propagation

**Rich Library**:
- `Live.stop()` - Cleanly stops live display
- `Panel` - Display partial content with custom styling

**Project Components**:
- `StreamingDisplay` - Manages live streaming UI
- `COLORS` and `PANEL_DEFAULTS` - Consistent styling
- Main loop double-Ctrl+C handler - Exit confirmation

## Notes

- LLM interrupt handling is simpler than Agent modes (no state management)
- Partial responses provide value even when interrupted
- The main loop's double-Ctrl+C mechanism still handles exit confirmation
- Future enhancement could add user choice to save partial responses
- This design balances simplicity with useful partial result preservation
