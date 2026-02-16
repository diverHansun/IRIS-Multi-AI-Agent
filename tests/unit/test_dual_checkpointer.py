"""Unit tests for dual checkpointer architecture in Deep Agent."""

import pytest

pytest.skip("UnifiedCheckpointer removed after memory refactor", allow_module_level=True)

import asyncio
from unittest.mock import AsyncMock, MagicMock

from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from src.agents.deepagents.instances.base_deep_agent import BaseDeepAgent
from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer


class TestDualCheckpointerArchitecture:
    """Test dual checkpointer implementation in BaseDeepAgent."""

    def _build_adapter(self):
        adapter = MagicMock(spec=BaseDeepAgentAdapter)
        adapter.function_type = "test"
        adapter.provider = "test_provider"
        adapter.model = "test_model"
        adapter.get_capabilities.return_value = {}
        return adapter

    def test_agent_initializes_with_dual_checkpointers(self):
        adapter = self._build_adapter()
        storage_checkpointer = MagicMock(spec=UnifiedCheckpointer)

        agent = BaseDeepAgent(
            adapter=adapter,
            global_memory_manager=storage_checkpointer,
        )

        assert hasattr(agent, "runtime_checkpointer")
        assert isinstance(agent.runtime_checkpointer, MemorySaver)
        assert agent.storage_checkpointer is storage_checkpointer

    def test_runtime_checkpointer_is_memory_saver(self):
        adapter = self._build_adapter()
        agent = BaseDeepAgent(adapter=adapter)
        assert isinstance(agent.runtime_checkpointer, MemorySaver)

    def test_storage_checkpointer_points_to_global_memory(self):
        adapter = self._build_adapter()
        mock_storage = MagicMock()
        agent = BaseDeepAgent(
            adapter=adapter,
            global_memory_manager=mock_storage,
        )
        assert agent.storage_checkpointer is mock_storage

    def test_runtime_config_includes_checkpoint_namespace(self):
        adapter = self._build_adapter()
        adapter.function_type = "Research"
        adapter.provider = "MyProvider"

        agent = BaseDeepAgent(adapter=adapter)

        runtime_config = agent.create_runtime_config("session-123")
        configurable = runtime_config["configurable"]

        assert configurable["thread_id"] == "session-123"
        assert configurable["checkpoint_ns"] == "deep_agent::myprovider::research"

    def test_invoke_uses_memory_sync_for_history(self):
        adapter = self._build_adapter()
        mock_memory_sync = MagicMock()

        def load_side_effect(session_ctx, *_args):
            session_ctx.update_checkpoint_id("load-ckpt")
            return session_ctx.build_runtime_config({
                "configurable": {
                    "thread_id": session_ctx.session_id,
                    "checkpoint_ns": session_ctx.checkpoint_namespace(),
                }
            })

        def persist_side_effect(session_ctx, *_args):
            session_ctx.update_checkpoint_id("persist-ckpt")

        mock_memory_sync.load_into_runtime.side_effect = load_side_effect
        mock_memory_sync.persist_from_runtime.side_effect = persist_side_effect

        agent = BaseDeepAgent(
            adapter=adapter,
            memory_sync=mock_memory_sync,
        )
        agent.runtime = MagicMock()
        agent.runtime.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content="done")]
        })

        async def _run():
            await agent.invoke("hello", session_id="session-x")

        asyncio.run(_run())

        assert mock_memory_sync.load_into_runtime.called
        assert mock_memory_sync.persist_from_runtime.called
        assert agent._session_checkpoints["session-x"] == "persist-ckpt"

    def test_enhance_runtime_input_merges_history(self):
        adapter = self._build_adapter()
        fake_memory = MagicMock()
        history = MagicMock()
        history.messages = [HumanMessage(content="past")]
        fake_memory.get_session_history.return_value = history

        agent = BaseDeepAgent(adapter=adapter, global_memory_manager=fake_memory)
        payload = {"messages": [HumanMessage(content="new")]}

        merged = agent.enhance_runtime_input("session", payload)

        assert len(merged["messages"]) == 2
        assert merged["messages"][0].content == "past"
    def test_invoke_skips_memory_sync_when_unavailable(self):
        adapter = self._build_adapter()
        agent = BaseDeepAgent(adapter=adapter)
        agent.runtime = MagicMock()
        agent.runtime.ainvoke = AsyncMock(return_value={"messages": []})

        async def _run():
            return await agent.invoke("ping", session_id="alpha")

        result = asyncio.run(_run())

        assert result["success"] is True
        assert agent._session_checkpoints == {}

    def test_unified_checkpointer_filters_tool_messages(self):
        checkpointer = UnifiedCheckpointer(storage_dir="data/test_sessions")

        config = {"configurable": {"thread_id": "filter_test"}}
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
        metadata = {"step": 1}

        checkpointer.put(config, checkpoint, metadata, {})
        retrieved = checkpointer.get_tuple(config)

        assert retrieved is not None
        messages = retrieved.checkpoint["channel_values"]["messages"]
        assert len(messages) == 2
        assert isinstance(messages[0], HumanMessage)
        assert isinstance(messages[1], AIMessage)

        checkpointer.delete_session("filter_test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

import pytest

pytest.skip("UnifiedCheckpointer removed after memory refactor", allow_module_level=True)
