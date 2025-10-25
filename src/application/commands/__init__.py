"""Command registry and dispatcher."""

from __future__ import annotations

from typing import Dict

from src.application.commands.base import BaseCommand, CommandResult

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
    from src.application.commands.agent.basic import ModelCommand as BasicModelCommand
    from src.application.commands.agent.mode_commands import ModeCommand
    from src.application.commands.agent.deep import DeepCommand, ModelCommand as DeepModelCommand, UseCommand
    from src.application.commands.agentflow.graph_commands import GraphCommand
    from src.application.commands.agentflow.model_commands import AgentFlowModelCommand
    from src.application.commands.agentflow.node_commands import NodesCommand, VisualizeCommand
    from src.application.commands.dify.file_commands import DifyFilesCommand, DifyUploadCommand
    from src.application.commands.dify.session_commands import DifyReconnectCommand, DifyResetCommand
    from src.application.commands.engine_commands import SwitchEngineCommand
    from src.application.commands.llm.llm_commands import LLMsCommand, ReloadCommand
    from src.application.commands.llm.stream_commands import StreamCommand as LLMStreamCommand
    from src.application.commands.llm.model_commands import LLMModelCommand
    from src.application.commands.shared.session_commands import (
        CleanupSessionsCommand,
        ClearSessionCommand,
        DeleteSessionCommand,
        ListSessionsCommand,
        NewSessionCommand,
        RestoreSessionCommand,
    )
    from src.application.commands.shared.mcp_connector_commands import ConnectorCommand, MCPCommand
    from src.application.commands.shared.system_commands import ExitCommand, HelpCommand, InfoCommand
    from src.application.commands.shared.tools_commands import ToolsCommand

    commands: list[BaseCommand] = [
        SwitchEngineCommand(),
        HelpCommand(),
        InfoCommand(),
        ExitCommand(),
        ToolsCommand(),
        NewSessionCommand(),
        ClearSessionCommand(),
        ListSessionsCommand(),
        RestoreSessionCommand(),
        DeleteSessionCommand(),
        CleanupSessionsCommand(),
        BasicModelCommand(),
        DeepModelCommand(),
        ModeCommand(),
        UseCommand(),
        DeepCommand(),
        LLMModelCommand(),
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
