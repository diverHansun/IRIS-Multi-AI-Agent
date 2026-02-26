import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agents.basicagents.adapters.openai_agent_adapter import OpenAIAgentAdapter
from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.instances.base_agent import BaseAgent


def _build_agent_config(*, memory_enabled: bool) -> AgentConfig:
    return AgentConfig(
        provider="dummy",
        model="dummy-model",
        llm_params={"temperature": 0.2},
        agent_params={
            "max_iterations": 5,
            "max_execution_time": 60,
            "memory_enabled": memory_enabled,
            "agent_type": "react",
        },
        provider_specific={},
    )


class _DummyAgent(BaseAgent):
    def __init__(
        self,
        *,
        graph: Any,
        memory_enabled: bool = True,
        checkpointer: Any = None,
    ) -> None:
        super().__init__(
            provider="dummy",
            model="dummy-model",
            llm=MagicMock(name="llm"),
            graph=graph,
            tools=[],
            checkpointer=checkpointer,
            config=_build_agent_config(memory_enabled=memory_enabled),
        )

    def _get_provider_name(self) -> str:
        return "dummy"


class AgentGraphBasicsTest(unittest.TestCase):
    def test_parse_graph_output_extracts_intermediate_steps(self) -> None:
        agent = _DummyAgent(graph=AsyncMock(), memory_enabled=False, checkpointer=None)

        messages = [
            HumanMessage(content="question"),
            AIMessage(
                content="thinking",
                tool_calls=[{"id": "call-1", "name": "calculator", "args": {"value": 21}}],
            ),
            ToolMessage(content="42", tool_call_id="call-1", name="calculator"),
            AIMessage(content="The result is 42."),
        ]

        parsed = agent._parse_graph_output({"messages": messages})

        self.assertEqual(parsed["output"], "The result is 42.")
        self.assertEqual(parsed["tool_calls"], 1)
        self.assertEqual(parsed["tool_names"], ["calculator"])
        action, observation = parsed["intermediate_steps"][0]
        self.assertEqual(action.tool, "calculator")
        self.assertEqual(observation, "42")

    def test_build_graph_config_merges_checkpointer(self) -> None:
        agent = _DummyAgent(graph=AsyncMock(), memory_enabled=True, checkpointer=object())
        extra_config = {"configurable": {"foo": "bar"}, "metadata": {"scope": "test"}}

        merged = agent._build_graph_config("session-1", extra_config)

        self.assertIsNotNone(merged)
        assert merged is not None  # type narrowing
        self.assertEqual(merged["configurable"]["thread_id"], "session-1")
        self.assertEqual(merged["configurable"]["checkpoint_ns"], "")
        self.assertEqual(merged["configurable"]["foo"], "bar")
        self.assertEqual(merged["metadata"], {"scope": "test"})

    def test_invoke_returns_legacy_structure(self) -> None:
        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Hello there!"),
        ]

        graph = AsyncMock()
        graph.ainvoke = AsyncMock(return_value={"messages": messages})

        agent = _DummyAgent(graph=graph, memory_enabled=True, checkpointer=object())
        result = asyncio.run(agent.invoke("Hi", session_id="thread-1"))

        self.assertTrue(result["success"])
        self.assertEqual(result["output"], "Hello there!")
        self.assertEqual(result["tool_calls"], 0)
        self.assertTrue(result["memory_enabled"])
        self.assertEqual(result["session_id"], "thread-1")

        graph.ainvoke.assert_awaited_once()
        args, kwargs = graph.ainvoke.await_args
        self.assertEqual(args[0]["messages"][0].content, "Hi")
        self.assertEqual(kwargs["config"]["configurable"]["thread_id"], "thread-1")

    def test_openai_adapter_uses_checkpointer(self) -> None:
        config = AgentConfig(
            provider="openai",
            model="stub-model",
            llm_params={
                "model": "stub-model",
                "api_key": "test-key",
                "streaming": False,
            },
            agent_params={
                "max_iterations": 5,
                "max_execution_time": 60,
                "memory_enabled": True,
                "agent_type": "react",
            },
            provider_specific={"system_prompt": "custom prompt"},
        )
        adapter = OpenAIAgentAdapter(config=config)
        fake_checkpointer = object()

        with patch(
            "src.agents.basicagents.adapters.openai_agent_adapter.create_agent",
            return_value="graph",
        ) as mock_create:
            graph = adapter.create_graph(
                llm="llm-instance",
                tools=["tool-a"],
                checkpointer=fake_checkpointer,
            )

        self.assertEqual(graph, "graph")
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["model"], "llm-instance")
        self.assertEqual(kwargs["tools"], ["tool-a"])
        self.assertIs(kwargs["checkpointer"], fake_checkpointer)
        self.assertEqual(kwargs["system_prompt"], "custom prompt")


if __name__ == "__main__":
    unittest.main()
