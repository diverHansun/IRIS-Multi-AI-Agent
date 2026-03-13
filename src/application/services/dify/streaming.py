"""
Streaming helpers for processing Dify API responses and rendering output.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from rich.console import Console
from rich.status import Status

from src.application.cli.theme import COLORS

logger = logging.getLogger(__name__)


class DifyStreaming:
    """Handle streaming responses and status output for Dify."""

    def __init__(self, console: Console, renderer: Any | None = None):
        """
        Initialise the streaming helper.

        Args:
            console: Rich console instance used for rendering.
        """
        self.console = console
        self.renderer = renderer
        self._current_message_id = None
        self._current_conversation_id = None

        # Performance control parameters
        self.buffer_size = 200
        self.delay_ms = 20
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

        status: Status | None = None
        try:
            if show_typing:
                if self.renderer is not None:
                    self.renderer.start_spinner()
                else:
                    status = Status("Thinking...", console=self.console, spinner="dots")
                    status.start()

            first_content_received = False
            content_buffer = []
            display_buffer = []

            chunk_count = 0
            max_chunks = 10000
            buffer_size = getattr(self, "buffer_size", 200)

            self._start_time = None
            self._chunk_count = 0
            self._total_chars = 0

            async for raw_data in stream_generator:
                chunk_count += 1

                if chunk_count > max_chunks:
                    logger.warning("Stream chunk count exceeded limit: %s", max_chunks)
                    self._display_warning(
                        f"\nWarning: Response exceeded limit ({self.max_content_length} chars), truncated"
                    )
                    break

                parsed_data = self.parse_stream_data(raw_data)
                if not parsed_data:
                    continue

                data_type = parsed_data["type"]

                if data_type in {"message", "agent_message"}:
                    if not first_content_received and show_typing:
                        self._stop_status(status)
                        first_content_received = True

                    content = parsed_data.get("content", "")
                    if content:
                        self._update_statistics(content)
                        content_buffer.append(content)
                        display_buffer.append(content)

                        total_content_length = sum(len(c) for c in content_buffer)
                        if total_content_length > self.max_content_length:
                            logger.warning("Response too long: %s chars", total_content_length)
                            self._display_warning(
                                f"\nWarning: Response exceeded limit ({self.max_content_length} chars), truncated"
                            )
                            break

                        await self._apply_rate_limit()

                        if len(display_buffer) >= buffer_size or "\n" in content:
                            buffered_content = "".join(display_buffer)
                            self._display_chunk(buffered_content)
                            display_buffer.clear()
                            if self.delay_ms > 0:
                                await asyncio.sleep(self.delay_ms / 1000.0)

                    if parsed_data.get("message_id"):
                        message_id = parsed_data["message_id"]
                    if parsed_data.get("conversation_id"):
                        conversation_id = parsed_data["conversation_id"]
                    continue

                if data_type == "agent_thought":
                    if not first_content_received and show_typing:
                        self._stop_status(status)
                        first_content_received = True

                    tool = parsed_data.get("tool", "")
                    if tool:
                        self._display_agent_thought(
                            int(parsed_data.get("position", 0) or 0),
                            tool,
                        )
                    continue

                if data_type == "message_end":
                    if not first_content_received and show_typing:
                        self._stop_status(status)
                        first_content_received = True

                    final_content = parsed_data.get("content", "")
                    if final_content and final_content not in "".join(content_buffer):
                        self._display_final_text(final_content)

                    if parsed_data.get("message_id"):
                        message_id = parsed_data["message_id"]
                    if parsed_data.get("conversation_id"):
                        conversation_id = parsed_data["conversation_id"]

                    metadata = parsed_data.get("metadata", {})
                    if metadata:
                        self._pending_metadata.update(metadata)
                    break

                if data_type in {"ping", "ignored"}:
                    continue

                if data_type == "error":
                    self._stop_status(status)
                    error_msg = parsed_data.get("error")
                    detail_msg = parsed_data.get("message")
                    if not error_msg:
                        error_msg = detail_msg or "Unknown error"
                    elif detail_msg and detail_msg != error_msg:
                        error_msg = f"{error_msg}: {detail_msg}"

                    logger.error("Dify error event: %s", parsed_data)
                    self._display_error(f"\nError: {error_msg}")
                    return None

                if data_type == "file":
                    if not first_content_received and show_typing:
                        self._stop_status(status)
                        first_content_received = True
                    self._display_file(parsed_data.get("filename", "Unknown file"))

            if show_typing and not first_content_received:
                self._stop_status(status)

            if display_buffer:
                self._display_chunk("".join(display_buffer))

            if content_buffer:
                self._display_stream_complete(self._get_performance_stats(), len(content_buffer))

            self._current_message_id = message_id
            self._current_conversation_id = conversation_id
            return conversation_id

        except Exception as e:
            self._stop_status(status)
            error_type = type(e).__name__
            error_msg = str(e)

            self._display_error(f"\nStreaming error ({error_type}): {error_msg}")
            if "ConnectionError" in error_type or "TimeoutError" in error_type:
                self._display_warning("Suggestion: Check network connection or Dify service status")
            elif "JSONDecodeError" in error_type:
                self._display_warning("Suggestion: Dify API response format error, check configuration")
            elif "KeyError" in error_type:
                self._display_warning("Suggestion: Dify API response field missing, may be version incompatible")
            else:
                self._display_warning("Suggestion: Check Dify configuration and network connection")

            logger.error(f"Streaming error: {error_type} - {error_msg}", exc_info=True)
            return None

        finally:
            # Display metadata after stream completes
            if self._pending_metadata:
                self._display_final_metadata(self._pending_metadata)
                self._pending_metadata.clear()

    def _stop_status(self, status: Status | None) -> None:
        if self.renderer is not None:
            self.renderer.stop_spinner()
            return
        if status is not None:
            try:
                status.stop()
            except Exception:
                pass

    def _display_chunk(self, text: str) -> None:
        if not text:
            return
        if self.renderer is not None:
            stream_chunk = getattr(self.renderer, "stream_chunk", None)
            if callable(stream_chunk):
                stream_chunk(text)
                return
        self.console.print(text, end="", style=COLORS["text_primary"])

    def _display_final_text(self, text: str) -> None:
        if not text:
            return
        if self.renderer is not None:
            self.renderer.emit_assistant_text(text)
            return
        self.console.print(text, style="bright_white")

    def _display_agent_thought(self, position: int, tool: str) -> None:
        if self.renderer is not None:
            from src.application.cli.renderers import TranscriptEvent

            self.renderer.emit(
                TranscriptEvent(
                    kind="agent_thought",
                    payload={"position": position, "tool": tool},
                )
            )
            return
        self.console.print(f"\n[Agent Step {position}] {tool} ✓", style=COLORS["info"])

    def _display_file(self, filename: str) -> None:
        if self.renderer is not None:
            from src.application.cli.renderers import TranscriptEvent

            self.renderer.emit(TranscriptEvent(kind="file", text=filename))
            return
        self.console.print(f"\nFile: {filename}", style=COLORS["info"])

    def _display_stream_complete(self, stats: Dict[str, Any], fragment_count: int) -> None:
        if self.renderer is not None:
            finish_stream = getattr(self.renderer, "finish_stream", None)
            if callable(finish_stream):
                finish_stream(stats)
                return
        self.console.print()
        if stats:
            try:
                self.console.print(
                    f"Response complete | "
                    f"{stats['elapsed_time']:.2f}s | "
                    f"{stats['total_chars']} chars | "
                    f"{stats['chars_per_second']:.1f} chars/s | "
                    f"{stats['total_chunks']} chunks",
                    style=COLORS["text_dim"],
                )
            except Exception as stats_e:
                logger.debug(f"Failed to display performance stats: {stats_e}")
                self.console.print(
                    f"Response complete ({fragment_count} fragments)",
                    style=COLORS["text_dim"],
                )
        else:
            self.console.print(
                f"Response complete ({fragment_count} fragments)",
                style=COLORS["text_dim"],
            )

    def _display_warning(self, text: str) -> None:
        if self.renderer is not None:
            self.renderer.emit_warning(text)
            return
        self.console.print(text, style=COLORS["warning"])

    def _display_error(self, text: str) -> None:
        if self.renderer is not None:
            self.renderer.emit_error(text)
            return
        self.console.print(text, style=COLORS["error"])

    def _display_info(self, text: str) -> None:
        if self.renderer is not None:
            self.renderer.emit_info(text)
            return
        self.console.print(text, style=COLORS["text_dim"])

    def _display_metadata(self, metadata: Dict[str, Any]):
        """
        Display metadata information (deprecated, use _display_final_metadata).

        Args:
            metadata: Metadata dictionary
        """
        if "usage" in metadata:
            usage = metadata["usage"]
            self._display_info(f"\nToken usage: {usage}")

        if "retriever_resources" in metadata:
            resources = metadata["retriever_resources"]
            if resources:
                self._display_info(f"\nReferenced resources: {len(resources)} items")

    def _display_final_metadata(self, metadata: Dict[str, Any]):
        """
        Display token usage and statistics at conversation end.

        Args:
            metadata: Metadata dictionary from message_end event
        """
        if self.renderer is not None:
            from src.application.cli.renderers import TranscriptEvent

            self.renderer.emit(TranscriptEvent(kind="metadata", payload=metadata))
            return

        if "usage" in metadata:
            usage = metadata["usage"]
            self.console.print(f"\nToken usage: {usage}", style=COLORS["text_dim"])

        if "retriever_resources" in metadata:
            resources = metadata["retriever_resources"]
            if resources:
                self.console.print(
                    f"\nReferenced resources: {len(resources)} items",
                    style=COLORS["text_dim"],
                )

    async def display_simple_message(self, message: str, style: str = COLORS["text_primary"]):
        """
        Display simple message.

        Args:
            message: Message content
            style: Message style
        """
        if style == COLORS["error"]:
            self._display_error(message)
        elif style == COLORS["warning"]:
            self._display_warning(message)
        elif style in {COLORS["text_dim"], COLORS["info"], COLORS["success"]}:
            self._display_info(message)
        elif self.renderer is not None:
            self.renderer.emit_assistant_text(message)
        else:
            self.console.print(message, style=style)

    async def display_error(self, error: str):
        """
        Display error message.

        Args:
            error: Error message
        """
        self._display_error(f"Error: {error}")

    async def display_success(self, message: str):
        """
        Display success message.

        Args:
            message: Success message
        """
        self._display_info(message)

    async def display_info(self, message: str):
        """
        Display information message.

        Args:
            message: Information content
        """
        self._display_info(message)

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
