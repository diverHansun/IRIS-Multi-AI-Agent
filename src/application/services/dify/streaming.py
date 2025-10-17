"""
Streaming helpers for processing Dify API responses and rendering output.
"""

import json
import asyncio
import time
from typing import Dict, Any, Optional, AsyncGenerator
from rich.console import Console
from rich.text import Text
from rich.status import Status
from rich.panel import Panel
import logging

logger = logging.getLogger(__name__)


class DifyStreaming:
    """Handle streaming responses and status output for Dify."""

    def __init__(self, console: Console):
        """
        Initialise the streaming helper.

        Args:
            console: Rich console instance used for rendering.
        """
        self.console = console
        self._current_message_id = None
        self._current_conversation_id = None

        # Performance control parameters
        self.buffer_size = 200
        self.delay_ms = 20
        self.display_refresh_rate = 15
        self.max_content_length = 1_000_000
        self.max_chunks_per_second = 50

        # Streaming statistics
        self._start_time = None
        self._chunk_count = 0
        self._total_chars = 0
        self._last_chunk_time = 0

        # Pending metadata for delayed display
        self._pending_metadata: Dict[str, Any] = {}

    async def _apply_rate_limit(self) -> None:
        """Apply a simple rate limit to avoid excessive updates."""
        current_time = time.time()

        # Calculate the current throughput
        if self._start_time and current_time > self._start_time:
            elapsed = current_time - self._start_time
            chunks_per_second = self._chunk_count / elapsed

            # If throughput is too high, add a short delay
            if chunks_per_second > self.max_chunks_per_second:
                delay = max(0, self.delay_ms / 1000.0)
                await asyncio.sleep(delay)

        # Update the timestamp for the most recent chunk
        self._last_chunk_time = current_time

    def _update_statistics(self, content: str) -> None:
        """Update basic performance statistics."""
        self._chunk_count += 1
        self._total_chars += len(content)

        if self._start_time is None:
            self._start_time = time.time()

    def _get_performance_stats(self) -> Dict[str, Any]:
        """Return performance statistics for summary output."""
        if not self._start_time:
            return {}

        elapsed = time.time() - self._start_time
        chars_per_second = self._total_chars / elapsed if elapsed > 0 else 0
        chunks_per_second = self._chunk_count / elapsed if elapsed > 0 else 0

        return {
            "elapsed_time": elapsed,
            "total_chunks": self._chunk_count,
            "total_chars": self._total_chars,
            "chars_per_second": chars_per_second,
            "chunks_per_second": chunks_per_second,
        }

    def parse_stream_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse streaming data from Dify API.

        Args:
            data: Raw streaming data

        Returns:
            Parsed data dict, or None if invalid
        """
        try:
            event = data.get("event")

            if event == "message":
                # Message event: append assistant content
                return {
                    "type": "message",
                    "content": data.get("answer", ""),
                    "message_id": data.get("message_id"),
                    "conversation_id": data.get("conversation_id"),
                }

            elif event == "agent_message":
                # Agent message event (Agent mode)
                return {
                    "type": "agent_message",
                    "content": data.get("answer", ""),
                    "message_id": data.get("message_id"),
                    "conversation_id": data.get("conversation_id"),
                }

            elif event == "agent_thought":
                # Agent thinking event (Agent mode)
                return {
                    "type": "agent_thought",
                    "id": data.get("id"),
                    "position": data.get("position", 0),
                    "thought": data.get("thought", ""),
                    "observation": data.get("observation", ""),
                    "tool": data.get("tool", ""),
                    "tool_input": data.get("tool_input", ""),
                    "message_files": data.get("message_files", []),
                    "conversation_id": data.get("conversation_id"),
                }

            elif event == "message_end":
                # Message end event: contains metadata
                return {
                    "type": "message_end",
                    "content": data.get("answer", ""),
                    "message_id": data.get("message_id"),
                    "conversation_id": data.get("conversation_id"),
                    "metadata": data.get("metadata", {}),
                }

            elif event == "error":
                # Error event
                return {
                    "type": "error",
                    "error": data.get("error", "Unknown error"),
                    "message": data.get("message", ""),
                }

            elif event == "message_file":
                # File event
                return {
                    "type": "file",
                    "file_id": data.get("file_id"),
                    "filename": data.get("filename"),
                    "url": data.get("url"),
                }

            elif event == "ping":
                # Ping event (keepalive)
                return {"type": "ping"}

            elif event in [
                "workflow_started",
                "workflow_finished",
                "node_started",
                "node_finished",
                "tts_message",
                "tts_message_end",
                "message_replace",
                "text_chunk",
                "text_replace",
            ]:
                # Workflow and advanced events - silently ignore (not needed for basic display)
                return {"type": "ignored", "event": event}

            else:
                # Truly unknown event - log for debugging
                logger.debug(
                    f"Unknown event type: {event}",
                    extra={"event": event, "data_preview": str(data)[:200]},
                )
                return {"type": "ignored", "event": event}

        except Exception as e:
            logger.warning(f"Failed to parse stream data: {e}, data: {data}")
            return None

    async def display_stream(
        self,
        stream_generator: AsyncGenerator[Dict[str, Any], None],
        show_typing: bool = True,
    ) -> Optional[str]:
        """
        Display streaming output from Dify API.

        Args:
            stream_generator: Async generator of streaming data
            show_typing: Whether to show typing indicator

        Returns:
            Final conversation ID for subsequent requests
        """
        content_buffer = []
        conversation_id = None
        message_id = None

        # Reset pending metadata
        self._pending_metadata.clear()

        try:
            # Show the waiting status indicator
            if show_typing:
                status = Status("Thinking...", console=self.console, spinner="dots")
                status.start()

            first_content_received = False
            content_buffer = []
            display_buffer = []  # Display buffer to reduce output frequency

            chunk_count = 0
            max_chunks = 10000  # Max chunks to prevent infinite loops
            buffer_size = getattr(
                self, "buffer_size", 200
            )  # Buffer size from config, default 200

            # Update statistics
            self._start_time = None
            self._chunk_count = 0
            self._total_chars = 0

            async for raw_data in stream_generator:
                chunk_count += 1

                # Prevent unbounded buffer growth by limiting chunks
                if chunk_count > max_chunks:
                    logger.warning(f"Stream chunk count exceeded limit: {max_chunks}")
                    self.console.print(
                        f"\n[yellow]Warning: Response too long, truncated[/yellow]"
                    )
                    break

                parsed_data = self.parse_stream_data(raw_data)

                if not parsed_data:
                    continue

                data_type = parsed_data["type"]

                if data_type == "message" or data_type == "agent_message":
                    # Handle assistant replies
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True

                    content = parsed_data.get("content", "")
                    if content:
                        # Update statistics for this chunk
                        self._update_statistics(content)

                        content_buffer.append(content)
                        display_buffer.append(content)

                        # Truncate overly long responses to avoid flooding
                        total_content_length = sum(len(c) for c in content_buffer)
                        if total_content_length > self.max_content_length:
                            logger.warning(
                                f"Response too long: {total_content_length} chars"
                            )
                            self.console.print(
                                f"\n[yellow]Warning: Response exceeded limit ({self.max_content_length} chars), truncated[/yellow]"
                            )
                            break

                        # Handle metadata events
                        await self._apply_rate_limit()

                        # Accumulate content and flush when necessary
                        if len(display_buffer) >= buffer_size or "\n" in content:
                            # Render assistant output
                            buffered_content = "".join(display_buffer)
                            self.console.print(
                                buffered_content, end="", style="bright_white"
                            )
                            display_buffer.clear()

                            # Add a tiny delay for a smoother visual
                            if self.delay_ms > 0:
                                await asyncio.sleep(self.delay_ms / 1000.0)

                    # Update conversation identifier
                    if parsed_data.get("message_id"):
                        message_id = parsed_data["message_id"]
                    if parsed_data.get("conversation_id"):
                        conversation_id = parsed_data["conversation_id"]

                elif data_type == "agent_thought":
                    # Handle agent thinking (minimal display)
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True

                    position = parsed_data.get("position", 0)
                    tool = parsed_data.get("tool", "")

                    if tool:
                        # Minimal agent display: [Agent Step N] tool_name ✓
                        self.console.print(
                            f"\n[yellow][Agent Step {position}] {tool} ✓[/yellow]"
                        )

                elif data_type == "message_end":
                    # Handle message end
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True

                    # Ensure buffered content is displayed
                    final_content = parsed_data.get("content", "")
                    if final_content and final_content not in "".join(content_buffer):
                        self.console.print(final_content, style="bright_white")

                    # Update last message identifier
                    if parsed_data.get("message_id"):
                        message_id = parsed_data["message_id"]
                    if parsed_data.get("conversation_id"):
                        conversation_id = parsed_data["conversation_id"]

                    # Store metadata for later display (not now!)
                    metadata = parsed_data.get("metadata", {})
                    if metadata:
                        self._pending_metadata.update(metadata)

                    break

                elif data_type == "ping":
                    # Ignore ping events (keepalive)
                    continue

                elif data_type == "ignored":
                    # Silently ignore workflow and advanced events
                    continue

                elif data_type == "error":
                    if show_typing:
                        status.stop()

                    error_msg = parsed_data.get("error")
                    detail_msg = parsed_data.get("message")
                    if not error_msg:
                        error_msg = detail_msg or "Unknown error"
                    elif detail_msg and detail_msg != error_msg:
                        error_msg = f"{error_msg}: {detail_msg}"

                    logger.error("Dify error event: %s", parsed_data)
                    self.console.print(f"\n[red]Error: {error_msg}[/red]")
                    return None

                elif data_type == "file":
                    # Display information about uploaded files
                    if not first_content_received and show_typing:
                        status.stop()
                        first_content_received = True

                    filename = parsed_data.get("filename", "Unknown file")
                    self.console.print(f"\n[blue]File: {filename}[/blue]")

            # Ensure the status indicator stops cleanly
            if show_typing and not first_content_received:
                status.stop()

            # Flush any remaining buffered content
            if display_buffer:
                buffered_content = "".join(display_buffer)
                self.console.print(buffered_content, end="", style="bright_white")

            # Persist buffered content for summary statistics
            if content_buffer:
                self.console.print()

                # Display statistics similar to streaming LLM diagnostics
                stats = self._get_performance_stats()
                if stats:
                    try:
                        self.console.print(
                            f"[dim]Response complete | "
                            f"{stats['elapsed_time']:.2f}s | "
                            f"{stats['total_chars']} chars | "
                            f"{stats['chars_per_second']:.1f} chars/s | "
                            f"{stats['total_chunks']} chunks[/dim]"
                        )
                    except Exception as stats_e:
                        logger.debug(f"Failed to display performance stats: {stats_e}")
                        self.console.print(
                            f"[dim]Response complete ({len(content_buffer)} fragments)[/dim]"
                        )
                else:
                    self.console.print(
                        f"[dim]Response complete ({len(content_buffer)} fragments)[/dim]"
                    )

            # Persist current conversation information
            self._current_message_id = message_id
            self._current_conversation_id = conversation_id

            return conversation_id

        except Exception as e:
            if show_typing:
                try:
                    status.stop()
                except:
                    pass

            # Provide detailed diagnostic information
            error_type = type(e).__name__
            error_msg = str(e)

            self.console.print(
                f"\n[red]Streaming error ({error_type}): {error_msg}[/red]"
            )

            # Suggest potential remediation steps
            if "ConnectionError" in error_type or "TimeoutError" in error_type:
                self.console.print(
                    "[yellow]Suggestion: Check network connection or Dify service status[/yellow]"
                )
            elif "JSONDecodeError" in error_type:
                self.console.print(
                    "[yellow]Suggestion: Dify API response format error, check configuration[/yellow]"
                )
            elif "KeyError" in error_type:
                self.console.print(
                    "[yellow]Suggestion: Dify API response field missing, may be version incompatible[/yellow]"
                )
            else:
                self.console.print(
                    "[yellow]Suggestion: Check Dify configuration and network connection[/yellow]"
                )

            logger.error(f"Streaming error: {error_type} - {error_msg}", exc_info=True)
            return None

        finally:
            # Display metadata after stream completes
            if self._pending_metadata:
                self._display_final_metadata(self._pending_metadata)
                self._pending_metadata.clear()

    def _display_metadata(self, metadata: Dict[str, Any]):
        """
        Display metadata information (deprecated, use _display_final_metadata).

        Args:
            metadata: Metadata dictionary
        """
        if "usage" in metadata:
            usage = metadata["usage"]
            self.console.print(f"\n[dim]Token usage: {usage}[/dim]")

        if "retriever_resources" in metadata:
            resources = metadata["retriever_resources"]
            if resources:
                self.console.print(
                    f"\n[dim]Referenced resources: {len(resources)} items[/dim]"
                )

    def _display_final_metadata(self, metadata: Dict[str, Any]):
        """
        Display token usage and statistics at conversation end.

        Args:
            metadata: Metadata dictionary from message_end event
        """
        # Keep current display format
        if "usage" in metadata:
            usage = metadata["usage"]
            self.console.print(f"\n[dim]Token usage: {usage}[/dim]")

        if "retriever_resources" in metadata:
            resources = metadata["retriever_resources"]
            if resources:
                self.console.print(
                    f"\n[dim]Referenced resources: {len(resources)} items[/dim]"
                )

    async def display_simple_message(self, message: str, style: str = "bright_white"):
        """
        Display simple message.

        Args:
            message: Message content
            style: Message style
        """
        self.console.print(message, style=style)

    async def display_error(self, error: str):
        """
        Display error message.

        Args:
            error: Error message
        """
        self.console.print(f"[red]Error: {error}[/red]")

    async def display_success(self, message: str):
        """
        Display success message.

        Args:
            message: Success message
        """
        self.console.print(f"[green]{message}[/green]")

    async def display_info(self, message: str):
        """
        Display information message.

        Args:
            message: Information content
        """
        self.console.print(f"[blue]{message}[/blue]")

    def get_current_conversation_id(self) -> Optional[str]:
        """
        Get current conversation ID.

        Returns:
            Current conversation ID, or None if not available
        """
        return self._current_conversation_id

    def get_current_message_id(self) -> Optional[str]:
        """
        Get current message ID.

        Returns:
            Current message ID, or None if not available
        """
        return self._current_message_id
