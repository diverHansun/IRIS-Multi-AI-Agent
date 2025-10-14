"""
LangGraph workflow management helpers (placeholders).
"""

from __future__ import annotations


class WorkflowManager:
    """
    Placeholder manager responsible for tracking LangGraph workflows.
    """

    def __init__(self) -> None:
        self._workflows: dict[str, dict] = {}

    def list_workflows(self) -> list[str]:
        return list(self._workflows.keys())

    def get_workflow(self, name: str) -> dict | None:
        return self._workflows.get(name)

