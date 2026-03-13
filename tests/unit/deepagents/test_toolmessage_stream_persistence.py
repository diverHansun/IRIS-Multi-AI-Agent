from __future__ import annotations

from types import SimpleNamespace
from typing import Any, AsyncIterator

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from src.application.services.agent.deep.streaming.conversation import handle_deep_agent_query
from src.application.services.agent.deep.streaming.event_handler import DeepAgentEventHandler


class _ConsoleStub:
    def __init__(self) -> None:
        self.outputs: list[str] = []

    def print(self, message: Any = "", *args: Any, **kwargs: Any) -> None:  # noqa: ARG002
        self.outputs.append(str(message))


def test_event_handler_marks_step_completed_when_updates_end_with_tool_message() -> None:
    handler = DeepAgentEventHandler(_ConsoleStub(), show_reasoning_steps=False)
    tool_msg = ToolMessage(content="ok", tool_call_id="c1", name="shell")

    result = handler.handle_event((("tools",), "updates", {"tools": {"messages": [tool_msg]}}))
    assert result.step_completed is True

    result = handler.handle_event((("agent",), "updates", {"agent": {"messages": [AIMessage(content="done")]}}))
    assert result.step_completed is False


class _RuntimeCheckpointerStub:
    def __init__(self) -> None:
        self.calls = 0

    def get_tuple(self, _config: dict) -> Any:
        self.calls += 1
        if self.calls == 1:
            return None  # first "has_checkpoint" probe
        checkpoint_id = f"ckpt-{self.calls}"
        return SimpleNamespace(
            config={"configurable": {"checkpoint_id": checkpoint_id}},
            checkpoint={"id": checkpoint_id, "channel_values": {"messages": []}},
        )


class _DeepCheckpointerStub:
    def __init__(self) -> None:
        self.persist_calls = 0

    def enhance_runtime_input(self, session_id: str, query: str, max_history: int = 10) -> dict:
        return {"messages": [HumanMessage(content=query)]}

    def persist_from_runtime(self, *args: Any, **kwargs: Any) -> bool:  # noqa: ARG002
        self.persist_calls += 1
        return True


class _RuntimeStub:
    def __init__(self, events: list[Any] | None = None) -> None:
        self.astream_kwargs: dict[str, Any] | None = None
        self.events = events or [
            (("tools",), "updates", {"tools": {"messages": [ToolMessage(content="files", tool_call_id="c1", name="shell")]}}),
            (("agent",), "updates", {"agent": {"messages": [AIMessage(content="All done")]}}),
        ]

    async def astream(self, pending_input: Any, **kwargs: Any) -> AsyncIterator[Any]:  # noqa: ARG002
        self.astream_kwargs = dict(kwargs)
        for event in self.events:
            yield event


class _AgentStub:
    def __init__(
        self,
        *,
        runtime: _RuntimeStub | None = None,
        output: str = "All done",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.metadata = metadata or {
            "hitl_config": {},
            "streaming": {
                "show_reasoning_steps": False,
                "show_elapsed_time": True,
            },
        }
        self.runtime = runtime or _RuntimeStub()
        self.runtime_checkpointer = _RuntimeCheckpointerStub()
        self.deep_checkpointer = _DeepCheckpointerStub()
        self.output = output

    def create_runtime_config(self, session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id, "checkpoint_ns": ""}}

    def create_runtime_input(self, query: str) -> dict:
        return {"messages": [HumanMessage(content=query)]}

    def prepare_stream_result(self, query: str, session_id: str, final_state: dict, *, tool_stats: dict | None = None) -> dict:  # noqa: ARG002
        return {
            "success": True,
            "output": self.output,
            "messages": final_state.get("messages", []),
            "tool_calls": (tool_stats or {}).get("tool_calls", 0),
            "tool_names": (tool_stats or {}).get("tool_names", []),
            "subagent_calls": [],
            "session_id": session_id,
        }


class _CtxStub:
    def __init__(self, agent: _AgentStub) -> None:
        self.console = _ConsoleStub()
        self.session_id = "user_stream_test"
        self.project_context = None
        self.metadata_manager = None
        self._engine = {"agent_instance": agent}
        self.hitl_manager = None

    def get_engine_config(self, name: str) -> dict:  # noqa: ARG002
        return self._engine


@pytest.mark.asyncio
async def test_handle_deep_agent_query_persists_per_step_and_uses_async_durability() -> None:
    agent = _AgentStub()
    ctx = _CtxStub(agent)

    answer = await handle_deep_agent_query(ctx, "list files")

    assert answer == "All done"
    assert agent.runtime.astream_kwargs is not None
    assert "durability" not in agent.runtime.astream_kwargs
    # one per-step persist + one final persist
    assert agent.deep_checkpointer.persist_calls >= 2


@pytest.mark.asyncio
async def test_handle_deep_agent_query_skips_duplicate_final_output_when_streamed() -> None:
    runtime = _RuntimeStub(
        events=[
            (
                ("agent",),
                "messages",
                (
                    AIMessageChunk(content="All done", chunk_position="last"),
                    {},
                ),
            ),
            (("agent",), "updates", {"agent": {"messages": [AIMessage(content="All done")]}}),
        ]
    )
    agent = _AgentStub(runtime=runtime, output="All done")
    ctx = _CtxStub(agent)

    answer = await handle_deep_agent_query(ctx, "stream final")

    assert answer == "All done"
    deepagent_lines = [line for line in ctx.console.outputs if "DeepAgent >" in line]
    assert len(deepagent_lines) == 1
    assert "All done" in deepagent_lines[0]


@pytest.mark.asyncio
async def test_handle_deep_agent_query_falls_back_when_only_intermediate_text_streamed() -> None:
    runtime = _RuntimeStub(
        events=[
            (
                ("agent",),
                "messages",
                (
                    AIMessageChunk(content="Let me search first"),
                    {},
                ),
            ),
            (
                ("agent",),
                "messages",
                (
                    AIMessageChunk(
                        content="",
                        tool_call_chunks=[
                            {
                                "name": "web_search",
                                "args": '{"query":"demo"}',
                                "id": "call-1",
                                "index": 0,
                                "type": "tool_call_chunk",
                            }
                        ],
                    ),
                    {},
                ),
            ),
            (("agent",), "updates", {"agent": {"messages": [AIMessage(content="All done")]}}),
        ]
    )
    agent = _AgentStub(runtime=runtime, output="All done")
    ctx = _CtxStub(agent)

    answer = await handle_deep_agent_query(ctx, "stream intermediate only")

    assert answer == "All done"
    deepagent_lines = [line for line in ctx.console.outputs if "DeepAgent >" in line]
    assert len(deepagent_lines) == 2
    assert any("Let me search first" in line for line in deepagent_lines)
    assert any("All done" in line for line in deepagent_lines)


@pytest.mark.asyncio
async def test_handle_deep_agent_query_shows_elapsed_footer_when_enabled() -> None:
    agent = _AgentStub()
    ctx = _CtxStub(agent)

    answer = await handle_deep_agent_query(ctx, "show elapsed")

    assert answer == "All done"
    assert not any("Deep agent reasoning..." in line for line in ctx.console.outputs)
    elapsed_lines = [line for line in ctx.console.outputs if line.startswith("Elapsed: ")]
    assert len(elapsed_lines) == 1


@pytest.mark.asyncio
async def test_handle_deep_agent_query_hides_elapsed_footer_when_disabled() -> None:
    agent = _AgentStub(
        metadata={
            "hitl_config": {},
            "streaming": {
                "show_reasoning_steps": False,
                "show_elapsed_time": False,
            },
        }
    )
    ctx = _CtxStub(agent)

    answer = await handle_deep_agent_query(ctx, "hide elapsed")

    assert answer == "All done"
    assert not any(line.startswith("Elapsed: ") for line in ctx.console.outputs)


@pytest.mark.asyncio
async def test_handle_deep_agent_query_uses_compact_summary_instead_of_verbose_tail() -> None:
    runtime = _RuntimeStub(
        events=[
            (
                ("agent",),
                "updates",
                {
                    "agent": {
                        "messages": [
                            AIMessage(
                                content="",
                                tool_calls=[
                                    {
                                        "name": "task",
                                        "args": {
                                            "subagent_type": "coding",
                                            "description": "Create a plugin example",
                                        },
                                        "id": "call-1",
                                    }
                                ],
                            )
                        ]
                    }
                },
            ),
            (
                ("agent",),
                "messages",
                (
                    ToolMessage(
                        content="Plugin example completed",
                        tool_call_id="call-1",
                        name="task",
                        status="success",
                    ),
                    {},
                ),
            ),
            (("agent",), "updates", {"agent": {"messages": [AIMessage(content="All done")]}}),
        ]
    )
    agent = _AgentStub(runtime=runtime)
    ctx = _CtxStub(agent)

    answer = await handle_deep_agent_query(ctx, "compact summary")

    assert answer == "All done"
    assert any("Summary:" in line for line in ctx.console.outputs)
    assert any("Tool calls: 1" in line for line in ctx.console.outputs)
    assert any("[1] coding (completed) - Create a plugin example" in line for line in ctx.console.outputs)
    assert not any("Used " in line for line in ctx.console.outputs)
    assert not any("SubAgent Delegations" in line for line in ctx.console.outputs)
    assert not any("(unknown)" in line for line in ctx.console.outputs)
