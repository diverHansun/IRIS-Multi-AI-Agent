"""Unit tests for SafeMemorySaver.

Verifies that the fault-tolerant wrapper correctly handles
non-serialisable Send objects in put_writes while preserving
all other checkpoint functionality.
"""

from __future__ import annotations

from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Send

from src.components.shared.memory.safe_memory_saver import SafeMemorySaver


# -- helpers ----------------------------------------------------------------

_TASKS_CHANNEL = "__pregel_tasks"


def _make_config(thread_id: str = "t1", checkpoint_id: str = "cp1") -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
            "checkpoint_id": checkpoint_id,
        }
    }


class _Unserializable:
    """Object that cannot be msgpack-serialised."""

    pass


# -- tests ------------------------------------------------------------------


def test_normal_writes_pass_through() -> None:
    """Regular serialisable writes should work exactly like MemorySaver."""
    saver = SafeMemorySaver()
    config = _make_config()

    # First, create a checkpoint so put_writes has something to attach to
    checkpoint = {
        "v": 1,
        "id": "cp1",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {"messages": [HumanMessage(content="hi")]},
        "channel_versions": {"messages": 1},
        "versions_seen": {},
    }
    saver.put(config, checkpoint, {}, {})

    # Now put_writes with normal serialisable data
    writes = [("messages", HumanMessage(content="hello"))]
    saver.put_writes(config, writes, task_id="task-1")

    # Verify the write was stored
    assert ("t1", "", "cp1") in saver.writes
    stored = saver.writes[("t1", "", "cp1")]
    assert len(stored) > 0


def test_send_with_unserializable_arg_degrades_gracefully() -> None:
    """Send objects with non-serialisable args should not crash put_writes.

    This reproduces the exact error:
      TypeError: Type is not msgpack serializable: Send
    """
    saver = SafeMemorySaver()
    config = _make_config()

    checkpoint = {
        "v": 1,
        "id": "cp1",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    saver.put(config, checkpoint, {}, {})

    # Mix of serialisable writes and a problematic TASKS/Send write
    problematic_send = Send("some_node", _Unserializable())
    writes = [
        ("messages", AIMessage(content="thinking...")),
        (_TASKS_CHANNEL, problematic_send),
    ]

    # Should NOT raise — SafeMemorySaver catches and retries
    saver.put_writes(config, writes, task_id="task-2")

    # The messages write should still be saved
    stored = saver.writes[("t1", "", "cp1")]
    assert len(stored) >= 1


def test_all_writes_are_tasks_skipped_silently() -> None:
    """When ALL writes are non-serialisable TASKS, just skip — no crash."""
    saver = SafeMemorySaver()
    config = _make_config()

    checkpoint = {
        "v": 1,
        "id": "cp1",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    saver.put(config, checkpoint, {}, {})

    writes = [
        (_TASKS_CHANNEL, Send("node_a", _Unserializable())),
        (_TASKS_CHANNEL, Send("node_b", _Unserializable())),
    ]

    # Should NOT raise
    saver.put_writes(config, writes, task_id="task-3")


def test_serialisable_send_works_normally() -> None:
    """Send objects with simple serialisable args should pass through fine."""
    saver = SafeMemorySaver()
    config = _make_config()

    checkpoint = {
        "v": 1,
        "id": "cp1",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    saver.put(config, checkpoint, {}, {})

    # A Send with a plain dict arg should serialise fine
    writes = [
        (_TASKS_CHANNEL, Send("agent", {"messages": []})),
    ]

    saver.put_writes(config, writes, task_id="task-4")

    stored = saver.writes[("t1", "", "cp1")]
    assert len(stored) >= 1


def test_get_tuple_and_put_inherited_from_memory_saver() -> None:
    """Core checkpoint methods should work identically to MemorySaver."""
    saver = SafeMemorySaver()
    config = _make_config(thread_id="t2", checkpoint_id="cp-inherited")

    messages = [HumanMessage(content="hello"), AIMessage(content="hi there")]
    checkpoint = {
        "v": 1,
        "id": "cp-inherited",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {"messages": messages},
        "channel_versions": {"messages": 2},
        "versions_seen": {},
    }

    returned_config = saver.put(config, checkpoint, {"source": "test"}, {})
    assert returned_config is not None

    result = saver.get_tuple(config)
    assert result is not None
    assert result.checkpoint["id"] == "cp-inherited"
    # MemorySaver stores channel_values in its own internal structure;
    # verify the checkpoint was round-tripped successfully
    assert result.config["configurable"]["thread_id"] == "t2"


def test_fallback_retry_also_fails_is_swallowed() -> None:
    """If even the filtered retry fails, log warning but don't crash."""
    saver = SafeMemorySaver()
    config = _make_config()

    checkpoint = {
        "v": 1,
        "id": "cp1",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }
    saver.put(config, checkpoint, {}, {})

    # Patch super().put_writes to always raise TypeError
    with patch.object(
        SafeMemorySaver.__bases__[0],
        "put_writes",
        side_effect=TypeError("always fails"),
    ):
        # Should NOT raise even when both attempts fail
        saver.put_writes(
            config,
            [("messages", HumanMessage(content="x"))],
            task_id="task-x",
        )


def test_put_with_unserializable_tasks_channel_degrades() -> None:
    """put() should survive when channel_values contains non-serialisable TASKS data.

    This reproduces the second crash path:
      MemorySaver.put() -> serde.dumps_typed(values[k]) -> TypeError
    """
    saver = SafeMemorySaver()
    config = _make_config(thread_id="t-put", checkpoint_id="cp-put")

    # Checkpoint whose channel_values include a TASKS channel with Send
    checkpoint = {
        "v": 1,
        "id": "cp-put",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {
            "messages": [HumanMessage(content="hello")],
            _TASKS_CHANNEL: (Send("tool_node", _Unserializable()),),
        },
        "channel_versions": {"messages": 1},
        "versions_seen": {},
    }
    # new_versions includes the TASKS channel
    new_versions = {"messages": 1, _TASKS_CHANNEL: 1}

    # Should NOT raise
    result = saver.put(config, checkpoint, {}, new_versions)
    assert result is not None
    assert result["configurable"]["thread_id"] == "t-put"

    # Messages should still be accessible
    tup = saver.get_tuple(config)
    assert tup is not None


def test_put_without_tasks_channel_works_normally() -> None:
    """put() with only serialisable channels should work identically to MemorySaver."""
    saver = SafeMemorySaver()
    config = _make_config(thread_id="t-ok", checkpoint_id="cp-ok")

    checkpoint = {
        "v": 1,
        "id": "cp-ok",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {
            "messages": [HumanMessage(content="hello"), AIMessage(content="hi")],
        },
        "channel_versions": {"messages": 2},
        "versions_seen": {},
    }

    result = saver.put(config, checkpoint, {}, {"messages": 2})
    assert result is not None
    assert result["configurable"]["checkpoint_id"] == "cp-ok"


def test_put_fallback_also_fails_returns_config() -> None:
    """If put() fails even after filtering, return a valid config without crashing."""
    saver = SafeMemorySaver()
    config = _make_config(thread_id="t-fail", checkpoint_id="cp-fail")

    checkpoint = {
        "v": 1,
        "id": "cp-fail",
        "ts": "2025-01-01T00:00:00",
        "channel_values": {},
        "channel_versions": {},
        "versions_seen": {},
    }

    with patch.object(
        SafeMemorySaver.__bases__[0],
        "put",
        side_effect=TypeError("always fails"),
    ):
        result = saver.put(config, checkpoint, {}, {})
        assert result is not None
        assert result["configurable"]["thread_id"] == "t-fail"
        assert result["configurable"]["checkpoint_id"] == "cp-fail"


def test_deep_agent_checkpointer_uses_safe_memory_saver() -> None:
    """DeepAgentCheckpointer should default to SafeMemorySaver, not MemorySaver."""
    import tempfile

    from src.components.shared.memory.deep_agent_checkpointer import (
        DeepAgentCheckpointer,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        checkpointer = DeepAgentCheckpointer(storage_dir=tmpdir)
        assert isinstance(checkpointer.runtime_checkpointer, SafeMemorySaver)
