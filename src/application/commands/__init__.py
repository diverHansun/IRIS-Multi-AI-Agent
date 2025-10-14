"""
Command registry and dispatcher.
"""

from __future__ import annotations

from typing import Dict

from .base import BaseCommand, CommandResult

COMMAND_REGISTRY: Dict[str, BaseCommand] = {}


async def dispatch(name: str, ctx, args: str) -> CommandResult:
    """
    Dispatch a command by name. The registry will be populated during the
    migration steps.
    """
    command = COMMAND_REGISTRY.get(name)
    if command is None:
        return CommandResult.error(f"Unknown command '{name}'")
    if not command.is_available(ctx.current_engine):
        return CommandResult.error(f"Command '{name}' is not available in current engine.")
    return await command.execute(ctx, args)


def register_command(command: BaseCommand) -> None:
    """
    Register a command instance into the registry.
    """
    for cmd_name in command.get_all_names():
        COMMAND_REGISTRY[cmd_name] = command


def register_default_commands() -> None:
    """
    Populate the registry with the default command set.
    """
    from .engine_commands import SwitchEngineCommand
    from .shared.session_commands import (
        CleanupSessionsCommand,
        ClearSessionCommand,
        DeleteSessionCommand,
        ListSessionsCommand,
        NewSessionCommand,
        RestoreSessionCommand,
    )
    from .shared.system_commands import ExitCommand, HelpCommand, InfoCommand
    from .langchain.llm_commands import LLMsCommand, ReloadCommand
    from .langchain.mode_commands import ModeCommand, StreamCommand
    from .langchain.model_commands import ModelCommand
    from .langchain.tool_commands import ConnectorCommand, MCPCommand
    from .langgraph.graph_commands import GraphCommand
    from .langgraph.model_commands import LangGraphModelCommand
    from .langgraph.node_commands import NodesCommand, VisualizeCommand
    from .dify.file_commands import DifyFilesCommand, DifyUploadCommand
    from .dify.session_commands import DifyReconnectCommand, DifyResetCommand

    commands: list[BaseCommand] = [
        SwitchEngineCommand(),
        HelpCommand(),
        InfoCommand(),
        ExitCommand(),
        NewSessionCommand(),
        ClearSessionCommand(),
        ListSessionsCommand(),
        RestoreSessionCommand(),
        DeleteSessionCommand(),
        CleanupSessionsCommand(),
        ModelCommand(),
        ModeCommand(),
        StreamCommand(),
        LLMsCommand(),
        ReloadCommand(),
        MCPCommand(),
        ConnectorCommand(),
        GraphCommand(),
        NodesCommand(),
        VisualizeCommand(),
        LangGraphModelCommand(),
        DifyUploadCommand(),
        DifyFilesCommand(),
        DifyResetCommand(),
        DifyReconnectCommand(),
    ]

    for command in commands:
        register_command(command)


# Populate registry on import
register_default_commands()
