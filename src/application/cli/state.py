"""
Application state object used by the refactored CLI.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from rich.console import Console

from src.config import settings


def _resolve_default_langchain_provider() -> str:
    provider = (settings.default_llm_provider or "zhipu").strip().lower()
    return provider or "zhipu"


def _resolve_default_langchain_model(provider: str) -> str:
    if settings.default_llm_model:
        return settings.default_llm_model.strip()
    if provider == "zhipu":
        return "glm-4.5-flash"
    if provider == "openai":
        return "gpt-4o-mini"
    return "auto"


_DEFAULT_LANGCHAIN_PROVIDER = _resolve_default_langchain_provider()
_DEFAULT_LANGCHAIN_MODEL = _resolve_default_langchain_model(_DEFAULT_LANGCHAIN_PROVIDER)
_DEFAULT_LANGCHAIN_MODE = "agent" if _DEFAULT_LANGCHAIN_PROVIDER == "zhipu" else "llm"


DEFAULT_ENGINE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "langchain": {
        "provider": _DEFAULT_LANGCHAIN_PROVIDER,
        "model": _DEFAULT_LANGCHAIN_MODEL,
        "mode": _DEFAULT_LANGCHAIN_MODE,
        "streaming": True,
        "agent": None,
    },
    "langgraph": {
        "graph_name": None,
        "provider": None,
        "model": None,
        "graph_instance": None,
    },
    "dify": {
        "conversation_id": None,
        "files": [],
        "control": None,
        "initialized": False,
    },
}


@dataclass(slots=True)
class AppState:
    """
    Global state shared across the CLI, command handlers, and services.

    The structure follows the design documented in the refactor plan where
    each engine keeps dedicated configuration while sharing common
    components such as memory and session management.
    """

    console: Console = field(default_factory=Console)
    current_engine: str = "langchain"
    engine_configs: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: deepcopy(DEFAULT_ENGINE_CONFIGS)
    )

    # Shared components
    global_memory: Any = None
    session_manager: Any = None
    session_id: Optional[str] = None
    streaming_manager: Any = None

    # Optional tool managers
    mcp_manager: Any = None

    def get_engine_config(self, engine: str | None = None) -> Dict[str, Any]:
        """
        Retrieve the configuration dictionary for a given engine.
        """
        key = engine or self.current_engine
        if key not in self.engine_configs:
            raise ValueError(f"Unknown engine '{key}'")
        return self.engine_configs[key]

    def set_engine_config(self, engine: str, key: str, value: Any) -> None:
        """
        Update a single configuration value for an engine.
        """
        config = self.get_engine_config(engine)
        config[key] = value

    def reset_engine(self, engine: str) -> None:
        """
        Reset the configuration for a specific engine back to its defaults.
        """
        if engine not in DEFAULT_ENGINE_CONFIGS:
            raise ValueError(f"Unknown engine '{engine}'")
        self.engine_configs[engine] = deepcopy(DEFAULT_ENGINE_CONFIGS[engine])
