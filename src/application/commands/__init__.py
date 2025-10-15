"""Command registry and dispatcher."""

from __future__ import annotations

from typing import Dict

from .base import BaseCommand, CommandResult

COMMAND_REGISTRY: Dict[str, BaseCommand] = {}


async def dispatch(name: str, ctx, args: str) -> CommandResult:
    command = COMMAND_REGISTRY.get(name)
    if command is None:
        return CommandResult.error(f"Unknown command '{name}'")
    if not command.is_available(ctx.current_engine):
        return CommandResult.error(f"Command '{name}' is not available in current engine.")
    return await command.execute(ctx, args)


def register_command(command: BaseCommand) -> None:
    for cmd_name in command.get_all_names():
        COMMAND_REGISTRY[cmd_name] = command


def register_default_commands() -> None:
    from .agent.mode_commands import ModeCommand
    from .agent.model_commands import ModelCommand
    from .agent.tool_commands import ConnectorCommand, MCPCommand
    from .agentflow.graph_commands import GraphCommand
    from .agentflow.model_commands import AgentFlowModelCommand
    from .agentflow.node_commands import NodesCommand, VisualizeCommand
    from .dify.file_commands import DifyFilesCommand, DifyUploadCommand
    from .dify.session_commands import DifyReconnectCommand, DifyResetCommand
    from .engine_commands import SwitchEngineCommand
    from .llm.llm_commands import LLMsCommand, ReloadCommand
    from .llm.stream_commands import StreamCommand as LLMStreamCommand
    from .shared.session_commands import (
        CleanupSessionsCommand,
        ClearSessionCommand,
        DeleteSessionCommand,
        ListSessionsCommand,
        NewSessionCommand,
        RestoreSessionCommand,
    )
    from .shared.system_commands import ExitCommand, HelpCommand, InfoCommand

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
        LLMsCommand(),
        ReloadCommand(),
        LLMStreamCommand(),
        MCPCommand(),
        ConnectorCommand(),
        GraphCommand(),
        NodesCommand(),
        VisualizeCommand(),
        AgentFlowModelCommand(),
        DifyUploadCommand(),
        DifyFilesCommand(),
        DifyResetCommand(),
        DifyReconnectCommand(),
    ]

    for command in commands:
        register_command(command)


register_default_commands()
