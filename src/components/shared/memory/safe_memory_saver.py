"""Fault-tolerant MemorySaver wrapper.

LangGraph's ``MemorySaver`` serialises channel values via msgpack in both
``put()`` and ``put_writes()``.  Internal routing channels
(``__pregel_tasks``) carry ``Send`` objects whose ``arg`` may contain
values that are not msgpack-serialisable (coroutines, custom runtime
objects, etc.).  When ``durability`` is set to the default (not
``"exit"``), these methods are called on **every** graph step, exposing
this serialisation gap.

``SafeMemorySaver`` catches the resulting ``TypeError`` and retries with
the problematic channel filtered out, so the checkpoint still records all
serialisable state (messages, channel values) while the graph execution
continues uninterrupted.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
)
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger(__name__)

# Channel name used by LangGraph for internal routing (Send objects).
_TASKS_CHANNEL = "__pregel_tasks"


class SafeMemorySaver(MemorySaver):
    """MemorySaver subclass that tolerates non-serialisable channel data.

    Behaviour
    ---------
    Both ``put`` and ``put_writes`` first attempt a full write.  On
    ``TypeError`` (msgpack serialisation failure) they retry with the
    ``__pregel_tasks`` channel stripped out.  If the retry also fails the
    error is logged and silently swallowed so the graph execution is not
    interrupted.

    All other ``MemorySaver`` methods (``get_tuple``, ``list``, etc.)
    are inherited unchanged.
    """

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        try:
            return super().put(config, checkpoint, metadata, new_versions)
        except TypeError:
            # Remove the TASKS channel from both channel_values and versions
            safe_versions = {
                k: v for k, v in new_versions.items() if k != _TASKS_CHANNEL
            }
            channel_values = checkpoint.get("channel_values", {})
            if isinstance(channel_values, dict) and _TASKS_CHANNEL in channel_values:
                safe_checkpoint = dict(checkpoint)
                safe_values = {
                    k: v for k, v in channel_values.items() if k != _TASKS_CHANNEL
                }
                safe_checkpoint["channel_values"] = safe_values
            else:
                safe_checkpoint = checkpoint

            try:
                result = super().put(config, safe_checkpoint, metadata, safe_versions)
                logger.debug(
                    "put: retried without TASKS channel "
                    "(%d/%d versions saved).",
                    len(safe_versions),
                    len(new_versions),
                )
                return result
            except Exception:
                logger.warning(
                    "put: retry without TASKS channel also failed; "
                    "returning config as-is.",
                    exc_info=True,
                )
                # Return a valid config so the graph can continue
                return {
                    "configurable": {
                        "thread_id": config["configurable"]["thread_id"],
                        "checkpoint_ns": config["configurable"].get(
                            "checkpoint_ns", ""
                        ),
                        "checkpoint_id": checkpoint.get("id", ""),
                    }
                }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        try:
            super().put_writes(config, writes, task_id, task_path)
        except TypeError:
            # Fallback: remove the TASKS channel that contains Send objects
            safe_writes = [
                (channel, value)
                for channel, value in writes
                if channel != _TASKS_CHANNEL
            ]
            if not safe_writes:
                logger.debug(
                    "put_writes: all writes were non-serialisable TASKS "
                    "channel entries; skipping checkpoint write."
                )
                return
            try:
                super().put_writes(config, safe_writes, task_id, task_path)
                logger.debug(
                    "put_writes: retried without TASKS channel "
                    "(%d/%d writes saved).",
                    len(safe_writes),
                    len(writes),
                )
            except Exception:
                logger.warning(
                    "put_writes: retry without TASKS channel also failed; "
                    "skipping checkpoint write.",
                    exc_info=True,
                )
