import asyncio
import queue

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Interrupt

from src.application.services.agent.deep.streaming.event_handler import DeepAgentEventHandler
from src.application.services.agent.deep.hitl.handler import handle_hitl_interrupt
from src.application.services.agent.deep.hitl.session_manager import SessionHITLManager


class DummyConsole:
    def __init__(self, inputs=None):
        self.outputs = []
        self._inputs = queue.Queue()
        for item in inputs or []:
            self._inputs.put(item)

    def print(self, message="", *args, **kwargs):
        self.outputs.append(str(message))

    def input(self, prompt):
        self.outputs.append(prompt)
        try:
            return self._inputs.get_nowait()
        except queue.Empty:
            return ""


@pytest.mark.asyncio
async def test_handle_hitl_interrupt_auto_approval_choice():
    console = DummyConsole(inputs=["2"])
    ctx = type("Ctx", (), {"console": console})
    manager = SessionHITLManager()
    manager.update_configuration(dangerous_tools=[], tool_settings={})

    interrupt = Interrupt(
        value={
            "action_requests": [{"name": "write_file", "args": {"path": "demo.txt"}}],
            "review_configs": [{"allowed_decisions": ["approve", "reject"]}],
        }
    )

    responses = await handle_hitl_interrupt(ctx, (interrupt,), manager, None)
    assert responses == [{"decisions": [{"type": "approve"}]}]
    assert manager.is_auto_approved("write_file")


@pytest.mark.asyncio
async def test_handle_hitl_interrupt_auto_skip_when_preapproved():
    console = DummyConsole()
    ctx = type("Ctx", (), {"console": console})
    manager = SessionHITLManager()
    manager.update_configuration(dangerous_tools=[], tool_settings={})
    manager.register_auto_approval("read_file")

    interrupt = Interrupt(
        value={
            "action_requests": [{"name": "read_file", "args": {"path": "demo.txt"}}],
            "review_configs": [{"allowed_decisions": ["approve", "reject"]}],
        }
    )

    responses = await handle_hitl_interrupt(ctx, (interrupt,), manager, None)
    assert responses == [{"decisions": [{"type": "approve"}]}]
    # No additional input should be requested.
    assert not console._inputs.qsize()


def test_event_handler_tracks_messages_and_interrupts():
    console = DummyConsole()
    handler = DeepAgentEventHandler(console)

    event = {"agent": {"messages": [AIMessage(content="Hello world")]}}
    result = handler.handle_event(event)
    assert result.final_state is not None
    assert handler.tool_stats["tool_calls"] == 0

    interrupt = Interrupt(value={"action_requests": []})
    interrupt_event = {"__interrupt__": (interrupt,)}
    result = handler.handle_event(interrupt_event)
    assert result.interrupts == (interrupt,)

    handler.render_summary()
    assert handler.last_agent_state is not None
