"""Simple unit tests for dual checkpointer architecture without pytest dependency."""

import pytest

pytest.skip("UnifiedCheckpointer removed after memory refactor", allow_module_level=True)

import asyncio
from pathlib import Path
from unittest.mock import MagicMock
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.agents.deepagents.instances.base_deep_agent import BaseDeepAgent
from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer


class DummyRuntime:
    async def ainvoke(self, payload, config):  # pragma: no cover - helper
        return {"messages": [AIMessage(content="dummy"), HumanMessage(content="ack")]}  # type: ignore[list-item]


def _build_adapter():
    adapter = MagicMock(spec=BaseDeepAgentAdapter)
    adapter.function_type = "test"
    adapter.provider = "test_provider"
    adapter.model = "test_model"
    adapter.get_capabilities.return_value = {}
    return adapter


def test_agent_initializes_with_dual_checkpointers():
    print("Test: Agent initializes with dual checkpointers...")
    adapter = _build_adapter()
    storage_checkpointer = MagicMock(spec=UnifiedCheckpointer)

    agent = BaseDeepAgent(adapter=adapter, global_memory_manager=storage_checkpointer)

    assert isinstance(agent.runtime_checkpointer, MemorySaver)
    assert agent.storage_checkpointer is storage_checkpointer
    print("[OK] Agent initializes with dual checkpointers")


def test_runtime_checkpointer_is_memory_saver():
    print("Test: Runtime checkpointer is MemorySaver...")
    adapter = _build_adapter()

    agent = BaseDeepAgent(adapter=adapter)

    assert isinstance(agent.runtime_checkpointer, MemorySaver)
    print("[OK] Runtime checkpointer is MemorySaver")


def test_invoke_uses_memory_sync():
    print("Test: invoke integrates with MemorySyncAdapter...")
    adapter = _build_adapter()
    memory_sync = MagicMock()

    def load_side_effect(session_ctx, *_):
        session_ctx.update_checkpoint_id("ckpt-load")
        return session_ctx.build_runtime_config({
            "configurable": {"thread_id": session_ctx.session_id, "checkpoint_ns": session_ctx.checkpoint_namespace()},
        })

    def persist_side_effect(session_ctx, *_):
        session_ctx.update_checkpoint_id("ckpt-save")

    memory_sync.load_into_runtime.side_effect = load_side_effect
    memory_sync.persist_from_runtime.side_effect = persist_side_effect

    agent = BaseDeepAgent(adapter=adapter, memory_sync=memory_sync)
    agent.runtime = DummyRuntime()

    asyncio.run(agent.invoke("hello", session_id="demo"))

    assert agent._session_checkpoints.get("demo") == "ckpt-save"
    assert memory_sync.load_into_runtime.called
    assert memory_sync.persist_from_runtime.called
    print("[OK] invoke integrates with MemorySyncAdapter")


def test_unified_checkpointer_filters_tool_messages():
    print("Test: UnifiedCheckpointer filters ToolMessages...")
    checkpointer = UnifiedCheckpointer(storage_dir="data/test_sessions_simple")

    config = {"configurable": {"thread_id": "filter_test_simple"}}
    checkpoint = {
        "v": 1,
        "id": "test_id",
        "ts": "2024-01-01",
        "channel_values": {
            "messages": [
                HumanMessage(content="Question"),
                AIMessage(content="Answer"),
                ToolMessage(content="Tool result", tool_call_id="tool_1", name="tool"),
            ]
        },
        "channel_versions": {"messages": 3},
        "versions_seen": {},
        "updated_channels": ["messages"],
    }

    checkpointer.put(config, checkpoint, {"step": 1}, {})
    retrieved = checkpointer.get_tuple(config)
    assert retrieved is not None
    messages = retrieved.checkpoint["channel_values"]["messages"]
    assert len(messages) == 2

    checkpointer.delete_session("filter_test_simple")
    print("[OK] UnifiedCheckpointer filters ToolMessages")


def run_all_tests():
    print("=" * 60)
    print("Running Dual Checkpointer Architecture Tests (simple)")
    print("=" * 60)

    tests = [
        test_agent_initializes_with_dual_checkpointers,
        test_runtime_checkpointer_is_memory_saver,
        test_invoke_uses_memory_sync,
        test_unified_checkpointer_filters_tool_messages,
    ]

    passed = 0
    failed = 0

    for test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as exc:  # pragma: no cover - manual harness
            failed += 1
            print(f"[FAIL] {test_func.__name__}: {exc}")

    print("=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    raise SystemExit(0 if success else 1)
import pytest

pytest.skip("UnifiedCheckpointer removed after memory refactor", allow_module_level=True)
