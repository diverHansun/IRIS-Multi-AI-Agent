from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from src.components.shared.memory.basic_agent_checkpointer import BasicAgentCheckpointer
from src.components.shared.memory.llm_memory import LLMMemory
from src.components.shared.memory.session_manager import SessionManager


def _checkpoint_payload(messages):
    return {
        "v": 1,
        "id": "ckp_test",
        "ts": "2025-01-01T00:00:00Z",
        "channel_values": {"messages": messages},
        "channel_versions": {"messages": len(messages)},
        "versions_seen": {},
        "updated_channels": ["messages"],
    }


def test_basic_checkpointer_merges_history(tmp_path: Path):
    storage_dir = tmp_path / "basic"
    checkpointer = BasicAgentCheckpointer(str(storage_dir), max_messages=10)
    session_id = "user_test_basic"

    existing = [HumanMessage(content="Q1"), AIMessage(content="A1"), HumanMessage(content="Q2"), AIMessage(content="A2")]
    checkpointer.storage.save_session(session_id, existing)

    new_messages = [HumanMessage(content="Q3"), AIMessage(content="A3")]
    checkpoint = _checkpoint_payload(new_messages)
    config = {"configurable": {"thread_id": session_id, "checkpoint_ns": ""}}

    checkpointer.put(config, checkpoint, {}, {"messages": len(new_messages)})

    saved = checkpointer.storage.load_session(session_id)
    assert saved is not None
    assert len(saved) == 6
    assert saved[0].content == "Q1" and saved[-1].content == "A3"


def test_basic_checkpointer_get_tuple_returns_trimmed_checkpoint(tmp_path: Path):
    storage_dir = tmp_path / "basic_tuple"
    checkpointer = BasicAgentCheckpointer(str(storage_dir), max_messages=3)
    session_id = "user_test_tuple"

    messages = [
        HumanMessage(content="Q1"),
        AIMessage(content="A1"),
        HumanMessage(content="Q2"),
        AIMessage(content="A2"),
    ]
    checkpointer.storage.save_session(session_id, messages)

    config = {"configurable": {"thread_id": session_id, "checkpoint_ns": ""}}
    tpl = checkpointer.get_tuple(config)

    assert tpl is not None
    assert tpl.checkpoint["channel_values"]["messages"][-1].content == "A2"
    assert len(tpl.checkpoint["channel_values"]["messages"]) == 3  # trimmed to max_messages
    assert tpl.metadata.get("session_id") == session_id


def test_llm_memory_add_and_trim(tmp_path: Path):
    storage_dir = tmp_path / "llm"
    llm_memory = LLMMemory(str(storage_dir), max_messages=3)
    session_id = "user_llm_test"

    llm_memory.add_conversation(session_id, "u1", "a1")
    llm_memory.add_conversation(session_id, "u2", "a2")

    history = llm_memory.get_history(session_id, max_messages=10)
    assert len(history) == 3  # trimmed to max_messages (last 3 messages kept)
    assert history[-1].content == "a2"


def test_session_manager_cross_mode_isolation(tmp_path: Path):
    base_dir = tmp_path / "sessions"
    storage_dirs = {
        "llm": str(base_dir / "llm"),
        "basic": str(base_dir / "basic"),
        "deep": str(base_dir / "deep"),
    }
    mgr = SessionManager(mode="basic", storage_dirs=storage_dirs)

    basic_session = mgr.create_new_session()
    assert mgr.session_exists(basic_session)

    mgr.mode = "llm"
    llm_session = mgr.create_new_session()
    assert mgr.session_exists(llm_session)
    assert not mgr.session_exists(basic_session)  # current mode is llm

    grouped = mgr.list_all_sessions()
    assert len(grouped["basic"]) == 1
    assert len(grouped["llm"]) == 1
    assert len(grouped["deep"]) == 0
