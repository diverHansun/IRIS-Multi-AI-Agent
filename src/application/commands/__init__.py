"""Command registry and dispatcher."""

from __future__ import annotations

from typing import Dict, List

from src.application.commands.base import BaseCommand, CommandResult

# Registry now stores a list of commands per name to support engine-scoped commands
COMMAND_REGISTRY: Dict[str, List[BaseCommand]] = {}


async def dispatch(name: str, ctx, args: str) -> CommandResult:
    commands = COMMAND_REGISTRY.get(name)
    if not commands:
        return CommandResult.error(f"Unknown command '{name}'")

    # Find the first command that is available for the current engine
    for command in commands:
        if command.is_available(ctx.current_engine):
            return await command.execute(ctx, args)

    return CommandResult.error(f"Command '{name}' is not available in current engine.")


def register_command(command: BaseCommand) -> None:
    """Register a command. Multiple commands can share the same name if they have different engine_scopes."""
    for cmd_name in command.get_all_names():
        if cmd_name not in COMMAND_REGISTRY:
            COMMAND_REGISTRY[cmd_name] = []
        COMMAND_REGISTRY[cmd_name].append(command)


def register_default_commands() -> None:
    from src.application.commands.agent.model_commands import ModelCommand
    from src.application.commands.agent.mode_commands import ModeCommand
    from src.application.commands.agent.deep import DeepCommand, UseCommand
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
    from src.application.commands.shared.skills_commands import SkillsCommand
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
        ModelCommand(),
        ModeCommand(),
        UseCommand(),
        DeepCommand(),
        LLMModelCommand(),
        LLMsCommand(),
        ReloadCommand(),
        LLMStreamCommand(),
        MCPCommand(),
        ConnectorCommand(),
        SkillsCommand(),
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
