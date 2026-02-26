from __future__ import annotations

from typing import Any, Dict

import src.components.deepagents.runtime as runtime_module


class _DummySubAgentMiddleware:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def get_task_tool(self):
        return None


class _DummyGraph:
    def with_config(self, config: Dict[str, Any]):
        self.config = config
        return self


def test_runtime_inserts_skills_middleware_after_todolist(monkeypatch):
    captured: Dict[str, Any] = {}

    def fake_create_agent(model, **kwargs):  # noqa: ANN001
        captured["model"] = model
        captured["middleware"] = kwargs["middleware"]
        return _DummyGraph()

    monkeypatch.setattr(runtime_module, "SubAgentMiddleware", _DummySubAgentMiddleware)
    monkeypatch.setattr(runtime_module, "create_agent", fake_create_agent)

    skills_middleware = object()

    runtime_module.create_deep_agent_runtime(
        model="openai:gpt-4o-mini",
        system_prompt="system",
        tools=[],
        filesystem_middlewares=[],
        shell_middleware=None,
        skills_middleware=skills_middleware,
    )

    middleware = captured["middleware"]
    assert middleware[1].__class__.__name__ == "TodoListMiddleware"
    assert middleware[2] is skills_middleware

