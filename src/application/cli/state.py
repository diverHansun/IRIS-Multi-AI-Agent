"""Application state object used by the refactored CLI."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from rich.console import Console

from src.config import settings
from src.core.project import ProjectContext, MetadataManager


def _resolve_default_provider() -> str:
    provider = (settings.default_llm_provider or "zhipu").strip().lower()
    return provider or "zhipu"


def _resolve_default_model(provider: str) -> str:
    if settings.default_llm_model:
        return settings.default_llm_model.strip()
    if provider == "zhipu":
        return "glm-4.5-flash"
    if provider == "openai":
        return "gpt-4o-mini"
    return "auto"


_DEFAULT_PROVIDER = _resolve_default_provider()
_DEFAULT_MODEL = _resolve_default_model(_DEFAULT_PROVIDER)


DEFAULT_ENGINE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "llm": {
        "provider": _DEFAULT_PROVIDER,
        "model": _DEFAULT_MODEL,
        "streaming": True,
        "llm_instance": None,
    },
    "agent": {
        "agent_type": "basic",
        "provider": _DEFAULT_PROVIDER,
        "model": _DEFAULT_MODEL,
        "streaming": True,
        "agent_instance": None,
    },
    "agentflow": {
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


from asyncio import TimerHandle


@dataclass(slots=True)
class AppState:
    """Global state shared across the CLI, command handlers, and services."""

    console: Console = field(default_factory=Console)
    current_engine: str = "agent"
    engine_configs: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: deepcopy(DEFAULT_ENGINE_CONFIGS)
    )

    # Legacy fields (will be removed after migration)
    global_memory: Any = None
    memory_sync: Any = None

    # New memory components
    session_manager: Any = None
    llm_memory: Any = None
    basic_checkpointer: Any = None
    deep_checkpointer: Any = None
    session_id: Optional[str] = None
    streaming_manager: Any = None
    mcp_manager: Any = None
    hitl_manager: Any = None

    # Session restoration for mode switching
    _basic_session_id: Optional[str] = None

    # Project context
    project_context: Optional[ProjectContext] = None
    metadata_manager: Optional[MetadataManager] = None

    # Interrupt handling
    exit_hint_until: Optional[float] = None
    exit_hint_handle: Optional[TimerHandle] = None

    def get_engine_config(self, engine: str | None = None) -> Dict[str, Any]:
        key = engine or self.current_engine
        if key not in self.engine_configs:
            raise ValueError(f"Unknown engine '{key}'")
        return self.engine_configs[key]

    def set_engine_config(self, engine: str, key: str, value: Any) -> None:
        config = self.get_engine_config(engine)
        config[key] = value

    def reset_engine(self, engine: str) -> None:
        if engine not in DEFAULT_ENGINE_CONFIGS:
            raise ValueError(f"Unknown engine '{engine}'")
        self.engine_configs[engine] = deepcopy(DEFAULT_ENGINE_CONFIGS[engine])
