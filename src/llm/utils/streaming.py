"""
Streaming Utility Module

Provides unified interface and management for LLM streaming output.
Supports streaming from Zhipu AI, OpenAI, and Ollama.

IMPORTANT: This module is designed for direct LLM chat only.
Agents should NOT use streaming as they need complete responses for tool calling.

Usage:
    # For LLM direct chat (CLI mode)
    result = await stream_llm_response(provider="zhipu", prompt="Hello", llm=llm_instance)

    # For Agent (use non-streaming methods instead)
    result = await agent.ainvoke(query)  # Correct
"""

import asyncio
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional, Callable
from abc import ABC, abstractmethod
from functools import wraps
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.callbacks import AsyncCallbackHandler
from src.core.providers.utils import OllamaClient
from src.application.cli.theme import COLORS, PANEL_DEFAULTS

# Import runtime settings.
try:
    from src.core.config import settings
except ImportError:
    # Provide a minimal fallback when this module runs standalone.
    class Settings:
        streaming_display_refresh_rate = 10
        streaming_delay_ms = 50
    settings = Settings()

logger = logging.getLogger(__name__)
console = Console()


# ========== Decorator for LLM-only functions ==========

def for_llm_only(func):
    """
    Decorator to mark functions that should only be used with LLMs, not Agents.

    This is a documentation decorator - it doesn't enforce restrictions,
    but serves as a clear signal to developers.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    # Add marker attribute
    wrapper.__llm_only__ = True
    return wrapper


# ========== Streaming Callback Handler ==========

class StreamingCallbackHandler(AsyncCallbackHandler):
    """Collect tokens from LangChain streaming callbacks."""
    
    def __init__(self, on_token: Optional[Callable[[str], None]] = None):
        """
        Initialise the streaming callback handler.

        Args:
            on_token: Optional callback invoked for each new token.
        """
        self.on_token = on_token
        self.tokens = []
        self.current_text = ""
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Handle a newly streamed token."""
        try:
            self.tokens.append(token)
            self.current_text += token
            
            if self.on_token:
                self.on_token(token)
        except Exception as e:
            logger.error("Streaming callback handler failed: %s", e)
    
    def get_full_text(self) -> str:
        """Return the accumulated text."""
        return self.current_text
    
    def clear(self):
        """Reset the accumulated token buffer."""
        self.tokens.clear()
        self.current_text = ""

class StreamingDisplay:
    """Manage a standalone Rich live display for streamed content."""
    
    def __init__(self, title: str = "AI Response"):
        """
        Initialise the live streaming display.

        Args:
            title: Title used for the output panel.
        """
        self.title = title
        self.content = ""
        self.live = None
        self.console = Console()
    
    def start(self):
        """Start the live display."""
        try:
            self.live = Live(
                self._create_panel(),
                console=self.console,
                refresh_per_second=settings.streaming_display_refresh_rate,
                transient=False
            )
            self.live.start()
        except Exception as e:
            logger.error("Failed to start streaming display: %s", e)
    
    def update(self, new_content: str):
        """Append new content to the live display."""
        try:
            self.content += new_content
            if self.live:
                self.live.update(self._create_panel())
        except Exception as e:
            logger.error("Failed to update streaming display: %s", e)
    
    def stop(self):
        """Stop the live display."""
        try:
            if self.live:
                self.live.stop()
                self.live = None
        except Exception as e:
            logger.error("Failed to stop streaming display: %s", e)
    
    def _create_panel(self) -> Panel:
        """Create the current Rich panel payload."""
        # Add a cursor glyph to make the stream feel active.
        display_content = self.content + "▊"

        return Panel(
            Text(display_content, style=COLORS["agent"]),
            title=f"[bold]{self.title}[/bold]",
            border_style=COLORS["info"],
            **PANEL_DEFAULTS,
        )
    
    def get_content(self) -> str:
        """Return the current buffered content."""
        return self.content

class StreamingLLM(ABC):
    """
    Abstract base class for streaming LLM providers.

    This class defines the interface for all streaming LLM implementations.
    Each provider (Zhipu, OpenAI, Ollama, etc.) should implement this interface.

    Design Pattern: Strategy Pattern - allows easy addition of new providers.

    For adding new providers:
        1. Subclass StreamingLLM
        2. Implement stream_generate method
        3. Register in StreamingManager
    """

    def __init__(self, llm: BaseChatModel):
        """
        Initialize streaming LLM provider.

        Args:
            llm: LangChain ChatModel instance
        """
        self.llm = llm

    @abstractmethod
    async def stream_generate(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream generate text from LLM.

        Args:
            prompt: Input prompt text
            on_token: Optional callback function called for each token

        Yields:
            Text chunks from the LLM stream

        Raises:
            Exception: If streaming fails
        """
        pass

class ZhipuStreamingLLM(StreamingLLM):
    """
    Zhipu AI streaming LLM implementation.

    Supports streaming for GLM-4, GLM-4-Plus, and other Zhipu models.
    """

    async def stream_generate(
        self,
        prompt: str,
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from a Zhipu model."""
        try:
            # Create a callback handler for token-level bookkeeping.
            callback_handler = StreamingCallbackHandler(on_token)

            # Consume the model via LangChain's streaming interface.
            async for chunk in self.llm.astream(
                [HumanMessage(content=prompt)],
                config={"callbacks": [callback_handler]}
            ):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Allow cooperative cancellation without wrapping the exception.
            return
        except Exception as e:
            logger.error("Zhipu streaming generation failed: %s", e)
            yield f"Streaming generation error: {str(e)}"

class OpenAIStreamingLLM(StreamingLLM):
    """
    OpenAI streaming LLM implementation.

    Supports streaming for GPT-4, GPT-3.5, and other OpenAI models.
    """

    async def stream_generate(
        self, 
        prompt: str, 
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from an OpenAI-compatible model."""
        try:
            # Create a callback handler for token-level bookkeeping.
            callback_handler = StreamingCallbackHandler(on_token)
            
            # Consume the model via LangChain's streaming interface.
            async for chunk in self.llm.astream(
                [HumanMessage(content=prompt)],
                config={"callbacks": [callback_handler]}
            ):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Allow cooperative cancellation without wrapping the exception.
            return
        except Exception as e:
            logger.error("OpenAI streaming generation failed: %s", e)
            yield f"Streaming generation error: {str(e)}"

class OllamaStreamingLLM(StreamingLLM):
    """
    Ollama streaming LLM implementation.

    Supports streaming for local Ollama models.
    Includes HTTP fallback for 502 errors and concurrent request handling.
    """

    async def stream_generate(
        self, 
        prompt: str, 
        on_token: Optional[Callable[[str], None]] = None
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama with HTTP fallback support."""
        try:
            # Emit detailed diagnostics for local model debugging.
            logger.info("[DEBUG] OllamaStreamingLLM starting stream generation")
            logger.info("[DEBUG] Prompt length: %s characters", len(prompt))
            logger.info("[DEBUG] Prompt preview: %s...", prompt[:200])
            logger.info("[DEBUG] LLM type: %s", type(self.llm))
            
            # Create a callback handler for token-level bookkeeping.
            callback_handler = StreamingCallbackHandler(on_token)
            
            # Start normal streaming first. Additional fallbacks live below.
            logger.info("[DEBUG] Starting self.llm.astream()")
            chunk_count = 0
            
            try:
                async for chunk in self.llm.astream(
                    [HumanMessage(content=prompt)],
                    config={"callbacks": [callback_handler]}
                ):
                    if hasattr(chunk, 'content') and chunk.content:
                        chunk_count += 1
                        logger.debug("[DEBUG] Received chunk #%s: %s...", chunk_count, chunk.content[:50])
                        yield chunk.content
                
                logger.info("[DEBUG] Stream generation completed with %s chunks", chunk_count)
                
            except (KeyboardInterrupt, asyncio.CancelledError):
                # Allow cooperative cancellation without wrapping the exception.
                return
            except Exception as astream_e:
                logger.error("[DEBUG] astream call failed: %s: %s", type(astream_e).__name__, astream_e)
                
                # Fall back to raw HTTP when the LangChain transport returns 502.
                if hasattr(astream_e, 'status_code') and astream_e.status_code == 502:
                    logger.error("[DEBUG] Received 502, enabling HTTP fallback")
                    logger.error("[DEBUG]   LangChain exception: %s: %s", type(astream_e).__name__, astream_e)
                    
                    # Use a direct HTTP client as the first recovery path.
                    try:
                        base_url = getattr(self.llm, 'base_url', 'http://localhost:11434')
                        model = getattr(self.llm, 'model', 'unknown')
                        temperature = getattr(self.llm, 'temperature', 0.1)

                        logger.error("[DEBUG] Using HTTP fallback: %s, model: %s", base_url, model)

                        http_client = OllamaClient(base_url=base_url, timeout=300)
                        
                        chunk_count = 0
                        async for chunk in http_client.stream_chat(model, prompt, temperature):
                            chunk_count += 1
                            logger.debug(f"[DEBUG] HTTP fallback chunk #{chunk_count}: {chunk[:30]}...")
                            yield chunk
                        
                        logger.info("[DEBUG] HTTP fallback succeeded with %s chunks", chunk_count)
                        return
                        
                    except Exception as http_e:
                        logger.error("[DEBUG] HTTP fallback also failed: %s", http_e)
                        # Continue to the generic fallback path below.
                
                # Recover from async generator re-entry with a non-streaming invoke.
                if "asynchronous generator is already running" in str(astream_e):
                    logger.warning("[DEBUG] Detected async generator re-entry, trying ainvoke fallback")
                    
                    # Use ainvoke and chunk the final text to mimic streaming.
                    try:
                        result = await self.llm.ainvoke([HumanMessage(content=prompt)])
                        if hasattr(result, 'content') and result.content:
                            # Split the full result into coarse chunks for compatibility.
                            content = result.content
                            chunk_size = max(1, len(content) // 10)
                            for i in range(0, len(content), chunk_size):
                                chunk = content[i:i+chunk_size]
                                logger.debug(f"[DEBUG] Fallback chunk: {chunk[:30]}...")
                                yield chunk
                            return
                        else:
                            yield "Fallback response completed"
                            return
                    except Exception as fallback_e:
                        logger.error("[DEBUG] Fallback also failed: %s", fallback_e)
                
                raise astream_e

        except (KeyboardInterrupt, asyncio.CancelledError):
            # Allow cooperative cancellation without wrapping the exception.
            return
        except Exception as e:
            logger.error("[DEBUG] Ollama streaming generation failed: %s: %s", type(e).__name__, e)
            if hasattr(e, 'status_code'):
                logger.error("[DEBUG] Status code: %s", e.status_code)
            if hasattr(e, 'response'):
                logger.error("[DEBUG] Response body: %s", e.response)
            if hasattr(e, 'request'):
                logger.error("[DEBUG] Request metadata: %s", e.request)
            
            # Log additional diagnostic details for local debugging.
            logger.error("[DEBUG] Exception attributes: %s", dir(e))
            logger.error("[DEBUG] LLM configuration check:")
            logger.error("[DEBUG]   model: %s", getattr(self.llm, "model", "Unknown"))
            logger.error("[DEBUG]   base_url: %s", getattr(self.llm, "base_url", "Unknown"))
            logger.error("[DEBUG]   timeout: %s", getattr(self.llm, "timeout", "Unknown"))
            
            # Probe the raw Ollama endpoint to separate transport issues from UI issues.
            logger.error("[DEBUG] Probing the Ollama endpoint directly...")
            try:
                import requests
                base_url = getattr(self.llm, 'base_url', 'http://localhost:11434')
                response = requests.get(f"{base_url}/api/tags", timeout=10)
                logger.error("[DEBUG] Direct connection status: %s", response.status_code)
            except Exception as conn_e:
                logger.error("[DEBUG] Direct connection failed: %s", conn_e)
            
            yield f"Streaming generation error: {str(e)}"

class StreamingManager:
    """
    Streaming output manager.

    Manages registration and dispatching of streaming LLM providers.
    Supports multiple providers and easy extension for new LLMs.

    Design Pattern: Registry Pattern - centralizes provider management.

    Usage:
        manager = StreamingManager()
        manager.register_llm("zhipu", llm_instance)
        result = await manager.stream_chat("zhipu", "Hello")

    For adding new providers:
        1. Create a new StreamingLLM subclass
        2. Add provider mapping in _PROVIDER_MAP
        3. Register and use immediately
    """

    # Provider class mapping. Add new providers here.
    _PROVIDER_MAP = {
        "zhipu": ZhipuStreamingLLM,
        "openai": OpenAIStreamingLLM,
        "ollama": OllamaStreamingLLM,
        # Add new providers here:
        # "claude": ClaudeStreamingLLM,
        # "gemini": GeminiStreamingLLM,
    }

    def __init__(self):
        """Initialize streaming manager"""
        self.streaming_llms: Dict[str, StreamingLLM] = {}

    def register_llm(self, provider: str, llm: BaseChatModel) -> None:
        """
        Register streaming LLM provider.

        Args:
            provider: Provider name (zhipu, openai, ollama, etc.)
            llm: LangChain ChatModel instance

        Raises:
            ValueError: If provider is not supported
        """
        provider_key = provider.lower()

        if provider_key not in self._PROVIDER_MAP:
            supported = ", ".join(self._PROVIDER_MAP.keys())
            logger.warning(
                f"Unsupported streaming provider: {provider}. "
                f"Supported: {supported}"
            )
            raise ValueError(f"Unsupported provider: {provider}")

        try:
            provider_class = self._PROVIDER_MAP[provider_key]
            self.streaming_llms[provider_key] = provider_class(llm)
            logger.info(f"Registered streaming LLM: {provider_key}")
        except Exception as e:
            logger.error(f"Failed to register streaming LLM {provider}: {e}")
            raise
    
    async def stream_chat(
        self,
        provider: str,
        prompt: str,
        display_title: str = "AI Response",
        show_display: bool = True,
        renderer: Any | None = None,
    ) -> Dict[str, Any]:
        """
        Execute a streaming chat request.

        Args:
            provider: Registered LLM provider name.
            prompt: Prompt text sent to the model.
            display_title: Display title used by the fallback live UI.
            show_display: Whether terminal output should be rendered.

        Returns:
            A dictionary with the full response and performance metadata.
        """
        if provider not in self.streaming_llms:
            raise ValueError(f"Unregistered streaming LLM provider: {provider}")
        
        streaming_llm = self.streaming_llms[provider]
        full_response = ""
        start_time = time.time()
        chunk_count = 0
        interrupted = False
        
        # Initialise the optional display surface.
        display = None
        use_renderer = show_display and renderer is not None
        if use_renderer:
            start_spinner = getattr(renderer, "start_spinner", None)
            if callable(start_spinner):
                start_spinner()
        elif show_display:
            display = StreamingDisplay(display_title)
            display.start()
        
        try:
            # Stream the response from the selected provider.
            async for chunk in streaming_llm.stream_generate(prompt):
                full_response += chunk
                chunk_count += 1

                # Push each chunk into the active presentation surface.
                if use_renderer:
                    stream_chunk = getattr(renderer, "stream_chunk", None)
                    if callable(stream_chunk):
                        stream_chunk(chunk)
                elif display:
                    display.update(chunk)

                # Keep a small pacing delay for smoother terminal rendering.
                await asyncio.sleep(settings.streaming_delay_ms / 1000.0)
        except (KeyboardInterrupt, asyncio.CancelledError):
            interrupted = True
            logger.info("Streaming interrupted by user after %s characters", len(full_response))

            if use_renderer:
                stop_spinner = getattr(renderer, "stop_spinner", None)
                if callable(stop_spinner):
                    stop_spinner()
                emit_warning = getattr(renderer, "emit_warning", None)
                if callable(emit_warning):
                    emit_warning("\nResponse interrupted by user")
            else:
                if display:
                    display.stop()
                console.print(
                    "\nResponse interrupted by user",
                    style=COLORS["warning"],
                )

            if full_response:
                if not use_renderer:
                    try:
                        console.print(
                            Panel(
                                full_response,
                                title=f"[bold]{display_title} (Interrupted)[/bold]",
                                border_style=COLORS["warning"],
                                **PANEL_DEFAULTS,
                            )
                        )
                    except UnicodeEncodeError as e:
                        logger.warning("Unicode encoding error while displaying interrupted response: %s", e)
                        print(f"\n=== {display_title} (Interrupted) ===")
                        try:
                            safe_response = full_response.encode('gbk', errors='replace').decode('gbk')
                            print(safe_response)
                        except Exception as fallback_e:
                            logger.warning("Failed to encode response with GBK fallback: %s", fallback_e)
                            print("[Response contains special characters, cannot display completely]")
                        print("=" * 50)
            else:
                if use_renderer:
                    emit_info = getattr(renderer, "emit_info", None)
                    if callable(emit_info):
                        emit_info("No content received before interruption")
                else:
                    console.print(
                        "No content received before interruption",
                        style=COLORS["text_dim"],
                    )

            return {
                "response": full_response,
                "elapsed_time": time.time() - start_time,
                "chunk_count": chunk_count,
                "characters": len(full_response),
                "success": True,
                "interrupted": True,
            }
        except Exception as e:
            error_msg = f"Streaming chat failed: {str(e)}"
            logger.error(error_msg)
            full_response = error_msg
            
            # Do not misclassify local encoding failures as transport errors.
            if "gbk" in str(e) and "can't encode" in str(e):
                logger.warning("[DEBUG] Detected a Unicode encoding issue, not a transport 502")
                full_response = "The response succeeded, but rendering hit an encoding issue."
            
        finally:
            # Finalise the active display surface.
            if not interrupted:
                elapsed = time.time() - start_time
                chars_per_second = len(full_response) / elapsed if elapsed > 0 else 0

                if use_renderer:
                    finish_stream = getattr(renderer, "finish_stream", None)
                    if callable(finish_stream):
                        finish_stream()
                    else:
                        stop_spinner = getattr(renderer, "stop_spinner", None)
                        if callable(stop_spinner):
                            stop_spinner()
                elif display:
                    display.stop()
                    
                    # Render the final response and performance summary safely.
                    try:
                        console.print(
                            Panel(
                                full_response,
                                title=f"[bold]{display_title} (Complete)[/bold]",
                                border_style=COLORS["success"],
                                **PANEL_DEFAULTS,
                            )
                        )
                    except UnicodeEncodeError as e:
                        logger.warning("Unicode encoding error while displaying final response: %s", e)
                        # Fall back to a plain text dump if Rich cannot encode the response.
                        print(f"\n=== {display_title} (Complete) ===")
                        # Apply a conservative encoding fallback before printing.
                        try:
                            safe_response = full_response.encode('gbk', errors='replace').decode('gbk')
                            print(safe_response)
                        except Exception as fallback_e:
                            logger.warning("Failed to encode final response with GBK fallback: %s", fallback_e)
                            print("[The response contains special characters and could not be fully displayed]")
                        print("=" * 50)
                    
                    if chunk_count > 0:
                        try:
                            console.print(
                                f"Performance: {elapsed:.2f}s | "
                                f"{len(full_response)} chars | "
                                f"{chars_per_second:.1f} chars/s | "
                                f"{chunk_count} chunks",
                                style=COLORS["text_dim"],
                            )
                        except UnicodeEncodeError as e:
                            # Fallback to a plain text performance summary.
                            logger.warning("Unicode encoding error while displaying performance metrics: %s", e)
                            print(f"Performance: {elapsed:.2f}s | {len(full_response)} chars | {chars_per_second:.1f} chars/s | {chunk_count} chunks")
        
        return {
            "response": full_response,
            "elapsed_time": time.time() - start_time,
            "chunk_count": chunk_count,
            "characters": len(full_response),
            "success": not full_response.startswith("Streaming chat failed"),
            "interrupted": False,
        }
    
    def get_supported_providers(self) -> list:
        """Return the list of registered streaming providers."""
        return list(self.streaming_llms.keys())

# Shared streaming manager instance.
streaming_manager = StreamingManager()

# ========== Convenience Functions ==========

@for_llm_only
async def stream_llm_response(
    provider: str,
    prompt: str,
    llm: Optional[BaseChatModel] = None,
    display_title: str = "AI Response",
    show_display: bool = True,
    renderer: Any | None = None,
) -> str:
    """
    Convenience function for streaming LLM response.

    IMPORTANT: This function is for LLM direct chat only.
    DO NOT use this for Agent tool calling - use agent.ainvoke() instead.

    Args:
        provider: LLM provider name (zhipu, openai, ollama)
        prompt: Input prompt text
        llm: Optional LangChain ChatModel instance (for dynamic registration)
        display_title: Display panel title
        show_display: Whether to show streaming UI

    Returns:
        Complete response text from LLM

    Raises:
        ValueError: If provider is not supported

    Example:
        # For LLM chat (correct usage)
        response = await stream_llm_response("zhipu", "Hello", llm=my_llm)

        # For Agent (wrong - use this instead)
        response = await agent.ainvoke("Hello")
    """
    # Dynamic registration if LLM provided
    if llm and provider not in streaming_manager.get_supported_providers():
        streaming_manager.register_llm(provider, llm)

    try:
        result = await streaming_manager.stream_chat(
            provider=provider,
            prompt=prompt,
            display_title=display_title,
            show_display=show_display,
            renderer=renderer,
        )
    except KeyboardInterrupt:
        logger.info("LLM streaming interrupted, propagating to caller")
        raise

    return result["response"]

async def demo_streaming():
    """Run a small standalone streaming demo."""
    console.print("[bold]Streaming demo[/bold]", style=COLORS["info"])
    
    # Simulate a streamed answer character by character.
    demo_text = (
        "This is a streaming output demo. Characters appear gradually to mimic "
        "a live model response and make the interaction feel more immediate."
    )
    
    display = StreamingDisplay("Demo")
    display.start()
    
    try:
        for char in demo_text:
            display.update(char)
            await asyncio.sleep(settings.streaming_delay_ms / 1000.0)
            
    finally:
        display.stop()
        console.print("[bold]Demo complete[/bold]", style=COLORS["success"])

if __name__ == "__main__":
    # Run the standalone demo when executed directly.
    asyncio.run(demo_streaming())
