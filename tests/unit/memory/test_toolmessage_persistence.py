from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from src.components.shared.memory.basic_agent_checkpointer import BasicAgentCheckpointer
from src.components.shared.memory.deep_agent_checkpointer import DeepAgentCheckpointer
from src.components.shared.memory.session_manager import SessionManager
from src.components.shared.storage.message_filter import MessageFilter
from src.components.shared.storage.session_storage import (
    MAX_TOOL_CONTENT_LENGTH,
    SessionStorage,
)


def test_session_storage_persists_tool_calls_and_tool_messages(tmp_path: Path) -> None:
    storage = SessionStorage(str(tmp_path))
    session_id = "user_tool_ctx"
    messages = [
        HumanMessage(content="List files"),
        AIMessage(
            content="",
            tool_calls=[{"name": "shell", "args": {"command": "dir"}, "id": "call-1"}],
        ),
        ToolMessage(content="a.txt\nb.txt", tool_call_id="call-1", name="shell", status="success"),
        AIMessage(content="Found two files."),
    ]

    assert storage.save_session(session_id, messages)

    loaded = storage.load_session(session_id)
    assert loaded is not None
    assert [type(msg).__name__ for msg in loaded] == [
        "HumanMessage",
        "AIMessage",
        "ToolMessage",
        "AIMessage",
    ]
    assert loaded[1].tool_calls[0]["id"] == "call-1"
    assert loaded[1].tool_calls[0]["name"] == "shell"
    assert getattr(loaded[2], "tool_call_id", "") == "call-1"
    assert getattr(loaded[2], "name", "") == "shell"
    assert getattr(loaded[2], "status", None) == "success"


def test_session_storage_truncates_tool_content_and_tracks_turns(tmp_path: Path) -> None:
    storage = SessionStorage(str(tmp_path))
    session_id = "user_tool_truncate"
    long_output = "X" * (MAX_TOOL_CONTENT_LENGTH + 200)
    messages = [
        HumanMessage(content="Run command"),
        AIMessage(content="", tool_calls=[{"name": "shell", "args": {"command": "echo"}, "id": "call-1"}]),
        ToolMessage(content=long_output, tool_call_id="call-1", name="shell"),
        AIMessage(content="Done"),
        HumanMessage(content="Next question"),
        AIMessage(content="Answer"),
    ]

    assert storage.save_session(session_id, messages)

    session_file = tmp_path / f"{session_id}.json"
    raw = json.loads(session_file.read_text(encoding="utf-8"))

    assert raw["message_count"] == 6
    assert raw["turn_count"] == 2
    assert raw["tool_message_count"] == 1
    assert raw["metadata"] == {}
    tool_entry = next(msg for msg in raw["messages"] if msg["type"] == "ToolMessage")
    assert tool_entry["tool_content_meta"]["truncated"] is True
    assert tool_entry["tool_content_meta"]["original_length"] == len(long_output)
    assert len(tool_entry["content"]) > MAX_TOOL_CONTENT_LENGTH
    assert len(tool_entry["content"]) < len(long_output)

    info = storage.get_session_info(session_id)
    assert info is not None
    assert info["turn_count"] == 2
    assert info["tool_message_count"] == 1


def test_message_filter_keeps_tool_messages_and_filters_system_notifications() -> None:
    message_filter = MessageFilter()
    history = [
        SystemMessage(content="[internal notice]"),
        HumanMessage(content="real question"),
        AIMessage(content="", tool_calls=[{"name": "shell", "args": {}, "id": "c1"}]),
        ToolMessage(content="ok", tool_call_id="c1", name="shell"),
        AIMessage(content="final answer"),
        HumanMessage(content="/clear"),
        AIMessage(content="session cleared"),
    ]

    filtered = message_filter.filter_message_history(history)

    assert all(not isinstance(msg, SystemMessage) for msg in filtered)
    assert any(isinstance(msg, ToolMessage) for msg in filtered)
    assert all(not (isinstance(msg, HumanMessage) and msg.content == "/clear") for msg in filtered)
    assert all(not (isinstance(msg, AIMessage) and msg.content == "session cleared") for msg in filtered)


def test_basic_checkpointer_dedup_preserves_distinct_tool_calls_and_ai_tool_requests(tmp_path: Path) -> None:
    checkpointer = BasicAgentCheckpointer(str(tmp_path), max_messages=50)

    ai1 = AIMessage(content="", tool_calls=[{"name": "shell", "args": {"command": "dir"}, "id": "a1"}])
    ai2 = AIMessage(content="", tool_calls=[{"name": "shell", "args": {"command": "dir"}, "id": "a2"}])
    tool1 = ToolMessage(content="OK", tool_call_id="a1", name="shell")
    tool2 = ToolMessage(content="OK", tool_call_id="a2", name="shell")

    deduped = checkpointer._deduplicate_messages([ai1, ai2, tool1, tool2])

    assert len(deduped) == 4


def test_atomic_trim_keeps_latest_ai_tool_group_together_in_basic_checkpointer(tmp_path: Path) -> None:
    checkpointer = BasicAgentCheckpointer(str(tmp_path), max_messages=2)
    messages = [
        HumanMessage(content="old"),
        AIMessage(content="old answer"),
        HumanMessage(content="run"),
        AIMessage(content="", tool_calls=[{"name": "shell", "args": {"command": "dir"}, "id": "c1"}]),
        ToolMessage(content="files", tool_call_id="c1", name="shell"),
    ]

    trimmed = checkpointer._trim_messages(messages)

    assert len(trimmed) == 2
    assert isinstance(trimmed[0], AIMessage)
    assert isinstance(trimmed[1], ToolMessage)
    assert trimmed[0].tool_calls[0]["id"] == "c1"
    assert getattr(trimmed[1], "tool_call_id", "") == "c1"


def test_deep_checkpointer_enhance_runtime_input_uses_turns_not_messages(tmp_path: Path) -> None:
    checkpointer = DeepAgentCheckpointer(str(tmp_path), max_messages=100)
    session_id = "user_deep_turns"
    stored = [
        HumanMessage(content="Q1"),
        AIMessage(content="A1"),
        HumanMessage(content="Q2"),
        AIMessage(content="", tool_calls=[{"name": "shell", "args": {"command": "dir"}, "id": "c2"}]),
        ToolMessage(content="files", tool_call_id="c2", name="shell"),
        AIMessage(content="A2"),
        HumanMessage(content="Q3"),
        AIMessage(content="A3"),
    ]
    assert checkpointer.storage.save_session(session_id, stored)

    runtime_input = checkpointer.enhance_runtime_input(session_id, "Q4", max_history=2)
    messages = runtime_input["messages"]

    assert [m.content for m in messages if isinstance(m, HumanMessage)] == ["Q2", "Q3", "Q4"]
    assert any(isinstance(m, ToolMessage) and getattr(m, "tool_call_id", "") == "c2" for m in messages)


def test_deep_checkpointer_persist_from_runtime_does_not_load_existing_session(tmp_path: Path) -> None:
    checkpointer = DeepAgentCheckpointer(str(tmp_path), max_messages=100)

    def fail_load(*_args, **_kwargs):
        raise AssertionError("persist_from_runtime should not load existing session")

    checkpointer.storage.load_session = fail_load  # type: ignore[method-assign]

    success = checkpointer.persist_from_runtime(
        "user_no_read",
        runtime_checkpointer=None,
        runtime_config=None,
        agent_state={"messages": [HumanMessage(content="Q"), AIMessage(content="A")]},
    )

    assert success is True


def test_session_manager_summary_prefers_turn_count(tmp_path: Path) -> None:
    storage_dirs = {
        "llm": str(tmp_path / "llm"),
        "basic": str(tmp_path / "basic"),
        "deep": str(tmp_path / "deep"),
    }
    manager = SessionManager(mode="deep", storage_dirs=storage_dirs)
    session_id = manager.create_new_session()
    manager.current_session_id = session_id

    manager.storage.save_session(
        session_id,
        [
            HumanMessage(content="Q1"),
            AIMessage(content="A1"),
            HumanMessage(content="Q2"),
            AIMessage(content="", tool_calls=[{"name": "shell", "args": {}, "id": "c1"}]),
            ToolMessage(content="ok", tool_call_id="c1", name="shell"),
            AIMessage(content="A2"),
        ],
    )

    summary = manager.get_current_session_summary()
    assert summary.startswith("Turns: 2")
    assert "messages: 6" in summary
