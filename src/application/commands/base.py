"""
Command system abstractions used by the refactored CLI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence


@dataclass(slots=True)
class CommandResult:
    """
    Normalized command execution result.
    """

    type: str
    message: str = ""
    payload: Dict[str, Any] | None = None

    @classmethod
    def success(cls, message: str = "", payload: Dict[str, Any] | None = None) -> "CommandResult":
        return cls(type="success", message=message, payload=payload)

    @classmethod
    def error(cls, message: str, payload: Dict[str, Any] | None = None) -> "CommandResult":
        return cls(type="error", message=message, payload=payload)

    @classmethod
    def info(cls, message: str, payload: Dict[str, Any] | None = None) -> "CommandResult":
        return cls(type="info", message=message, payload=payload)

    @classmethod
    def exit(cls, message: str = "Exiting.") -> "CommandResult":
        return cls(type="exit", message=message, payload=None)


class CommandContextProtocol(ABC):
    """
    Protocol describing the minimal attributes required from the CLI state.
    """

    current_engine: str


class BaseCommand(ABC):
    """
    Base class for all commands.
    """

    name: str
    help_text: str = ""
    aliases: Sequence[str] = ()
    engine_scope: Sequence[str] = ("all",)

    def __init__(self) -> None:
        if not getattr(self, "name", None):
            raise ValueError("Command must define a name attribute.")

    def is_available(self, engine: str) -> bool:
        """
        Check whether the command can be executed under the given engine.
        """
        if "all" in self.engine_scope:
            return True
        return engine in self.engine_scope

    def get_all_names(self) -> Iterable[str]:
        """
        Return the command name and aliases for registry usage.
        """
        yield self.name
        yield from self.aliases

    @abstractmethod
    async def execute(self, ctx: CommandContextProtocol, args: str) -> CommandResult:
        """
        Execute the command.
        """
