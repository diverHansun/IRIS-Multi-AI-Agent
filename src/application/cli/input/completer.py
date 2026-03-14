"""
Engine-aware Tab completion for CLI commands.

Data sources:
  - Command names and help_text: COMMAND_REGISTRY (single source of truth at runtime).
    This module does NOT depend on gui/render.py command tables, which are display-only
    and could diverge from the registry.
  - Argument option values: _ARG_VALUES table defined in this module.
  - Available command set per engine: _ENGINE_COMMANDS, filtered at call time from ctx.

Completion behavior:
  /        + Tab  -> all available commands for the current engine
  /mo      + Tab  -> /mode, /model  (prefix filter)
  /mode    + Tab  -> basic, deep    (argument value completion)
  /mode b  + Tab  -> basic

complete_while_typing=False ensures the completer is only triggered by Tab,
leaving free-text AI queries completely undisturbed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from prompt_toolkit.completion import CompleteEvent, Completer, Completion
from prompt_toolkit.document import Document

if TYPE_CHECKING:
    from src.application.cli.state import AppState


# Argument option values per command (first positional level only).
# Key: command name without the leading slash.
_ARG_VALUES: dict[str, list[str]] = {
    "switch":          ["llm", "agent", "agentflow", "dify"],
    "mode":            ["basic", "deep"],
    "stream":          ["on", "off", "enable", "disable"],
    "use":             ["research", "coding", "analysis"],
    "mcp":             ["status", "status -v", "tools", "tools --json", "reload"],
    "connector":       ["status", "status -v", "tools", "tools --json", "reload"],
    "skills":          ["list", "create", "info", "reload"],
    "deep":            ["status", "config reload", "filesystem status", "filesystem reload"],
    "files":           ["clear", "remove"],
    "tools":           ["--list"],
    "sessions":        ["all"],
}

# Commands available in every engine.
_GLOBAL: frozenset[str] = frozenset({"switch", "help", "info", "exit", "quit"})

# Commands shared across llm, agent, and agentflow engines.
_SESSION_SHARED: frozenset[str] = frozenset(
    {"new", "clear", "sessions", "restore", "delete_session", "cleanup"}
)

# Engine -> full set of available command names.
_ENGINE_COMMANDS: dict[str, frozenset[str]] = {
    "llm": _GLOBAL | _SESSION_SHARED | frozenset(
        {"model", "llms", "reload", "stream"}
    ),
    "agent": _GLOBAL | _SESSION_SHARED | frozenset(
        {"mode", "model", "use", "deep", "tools", "mcp", "connector", "skills"}
    ),
    "agentflow": _GLOBAL | _SESSION_SHARED | frozenset(
        {"graph", "graph-model", "nodes", "visualize"}
    ),
    "dify": _GLOBAL | frozenset({"upload", "files", "reset", "reconnect"}),
}


def _load_command_meta() -> dict[str, str]:
    """Load command name -> help_text mapping from COMMAND_REGISTRY.

    Returns an empty dict on import failure so that completion still works
    without descriptive metadata.
    """
    try:
        from src.application.commands import COMMAND_REGISTRY
        return {
            name: cmds[0].help_text
            for name, cmds in COMMAND_REGISTRY.items()
            if cmds
        }
    except Exception:
        return {}


class CommandCompleter(Completer):
    """Tab completer that filters available commands by the current engine.

    Each completion item includes a display_meta string sourced from
    COMMAND_REGISTRY.help_text, shown inline in the completion menu.
    """

    def __init__(self, ctx: "AppState") -> None:
        self._ctx = ctx
        self._meta: dict[str, str] = _load_command_meta()

    def get_completions(
        self,
        document: Document,
        complete_event: CompleteEvent,
    ) -> Iterable[Completion]:
        text = document.text_before_cursor.lstrip()

        if not text.startswith("/"):
            return

        body = text[1:]
        parts = body.split(" ", 1)
        cmd_fragment = parts[0]
        has_space = len(parts) > 1

        available = _ENGINE_COMMANDS.get(self._ctx.current_engine, _GLOBAL)

        if not has_space:
            # Case 1: command name is incomplete — complete the name.
            for cmd_name in sorted(available):
                if cmd_name.startswith(cmd_fragment):
                    yield Completion(
                        text=cmd_name[len(cmd_fragment):],
                        start_position=0,
                        display=f"/{cmd_name}",
                        display_meta=self._meta.get(cmd_name, ""),
                    )
        else:
            # Case 2: command name is complete — complete the argument value.
            if cmd_fragment not in available:
                return
            arg_fragment = parts[1]
            for value in _ARG_VALUES.get(cmd_fragment, []):
                if value.startswith(arg_fragment):
                    yield Completion(
                        text=value[len(arg_fragment):],
                        start_position=0,
                        display=value,
                    )
