"""
Muti-AI-Agent - multi-LLM agent showcase project.
"""

__version__ = "3.0.0"
__author__ = "diverHansun"

def build_zhipu_agent(*args, **kwargs):
    """Lazily import and delegate to the Zhipu agent factory."""
    try:
        from .agents.basicagents.instances.zhipu_agent import (  # type: ignore
            build_zhipu_agent as _build_zhipu_agent,
        )
        return _build_zhipu_agent(*args, **kwargs)
    except ImportError as exc:  # pragma: no cover - defensive lazy import guard
        raise ImportError(f"Unable to import build_zhipu_agent: {exc}") from exc


def build_simple_zhipu_chat(*args, **kwargs):
    """Lazily import and delegate to the simple Zhipu chat helper."""
    try:
        from .agents.basicagents.instances.zhipu_agent import (  # type: ignore
            build_simple_zhipu_chat as _build_simple_zhipu_chat,
        )
        return _build_simple_zhipu_chat(*args, **kwargs)
    except ImportError as exc:  # pragma: no cover - defensive lazy import guard
        raise ImportError(f"Unable to import build_simple_zhipu_chat: {exc}") from exc


def get_json_react_parser():
    """Lazily import and return the JSONReActSingleInputOutputParser."""
    from .components.basicagents.parsers.json_react_output_parser import (  # type: ignore
        JSONReActSingleInputOutputParser,
    )

    return JSONReActSingleInputOutputParser


__all__ = [
    "build_zhipu_agent",
    "build_simple_zhipu_chat",
    "get_json_react_parser",
]
