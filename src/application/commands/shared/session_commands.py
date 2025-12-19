"""
Session management commands shared by LLM, Agent, and AgentFlow engines.
"""

from __future__ import annotations
from src.application.commands.base import BaseCommand, CommandResult


class NewSessionCommand(BaseCommand):
    name = "new"
    engine_scope = ("llm", "agent", "agentflow")
    help_text = "Create a new session."

    async def execute(self, ctx, args: str) -> CommandResult:
        if ctx.session_manager is None:
            return CommandResult.error("Session manager is not initialized.")
        old_session_id = ctx.session_id
        ctx.session_id = ctx.session_manager.create_new_session()
        return CommandResult.success(
            f"New session created: {ctx.session_id}",
            payload={"old_session_id": old_session_id, "new_session_id": ctx.session_id},
        )


class ClearSessionCommand(BaseCommand):
    name = "clear"
    engine_scope = ("llm", "agent", "agentflow")
    help_text = "Clear the current session memory."

    async def execute(self, ctx, args: str) -> CommandResult:
        if ctx.session_manager is None:
            return CommandResult.error("Session manager is not initialized.")
        if ctx.session_manager.clear_current_session():
            return CommandResult.success("Current session memory cleared.")
        return CommandResult.error("Failed to clear session memory.")


class ListSessionsCommand(BaseCommand):
    name = "sessions"
    engine_scope = ("llm", "agent", "agentflow")
    help_text = "List available sessions."

    async def execute(self, ctx, args: str) -> CommandResult:
        if ctx.session_manager is None:
            return CommandResult.error("Session manager is not initialized.")

        arg = args.strip().lower()
        show_all = arg == "all"

        if show_all and hasattr(ctx.session_manager, "list_all_sessions"):
            sessions_grouped = ctx.session_manager.list_all_sessions()
            return CommandResult(
                type="render",
                payload={
                    "kind": "sessions_grouped",
                    "sessions": sessions_grouped,
                    "current_session_id": ctx.session_id,
                    "current_mode": ctx.session_manager.mode,
                },
            )

        sessions = ctx.session_manager.list_sessions()
        return CommandResult(
            type="render",
            payload={
                "kind": "sessions",
                "sessions": sessions,
                "current_session_id": ctx.session_id,
            },
        )


class RestoreSessionCommand(BaseCommand):
    name = "restore"
    engine_scope = ("llm", "agent", "agentflow")
    help_text = "Restore a specific session by ID."

    async def execute(self, ctx, args: str) -> CommandResult:
        target = args.strip()
        if not target:
            return CommandResult.error("Usage: /restore <session_id>")
        if ctx.session_manager is None:
            return CommandResult.error("Session system is not initialized.")

        # Prefer current mode; if not found, check other modes and guide user
        if ctx.session_manager.session_exists(target):
            ctx.session_id = target
            session_info = ctx.session_manager.get_session_info(target)
            return CommandResult.success(
                f"Switched to session: {target}",
                payload={"session_id": target, "session_info": session_info},
            )

        for mode in ("llm", "basic", "deep"):
            if ctx.session_manager.session_exists(target, mode=mode):
                return CommandResult.error(
                    f"Session '{target}' exists in mode '{mode}', not current mode '{ctx.session_manager.mode}'. "
                    f"Switch to {mode} mode first."
                )

        return CommandResult.error(f"Session does not exist: {target}")


class DeleteSessionCommand(BaseCommand):
    name = "delete_session"
    engine_scope = ("llm", "agent", "agentflow")
    help_text = "Delete a session by ID."

    async def execute(self, ctx, args: str) -> CommandResult:
        target = args.strip()
        if not target:
            return CommandResult.error("Usage: /delete_session <session_id>")
        if ctx.session_manager is None:
            return CommandResult.error("Session system is not initialized.")
        if not ctx.session_manager.session_exists(target):
            return CommandResult.error(f"Session does not exist: {target}")

        storage = ctx.session_manager.storage
        if storage.delete_session(target):
            payload = {"deleted_session_id": target}
            message = f"Session deleted: {target}"
            if target == ctx.session_id:
                ctx.session_id = ctx.session_manager.create_new_session()
                message += f". New session created: {ctx.session_id}"
                payload["new_session_id"] = ctx.session_id
            return CommandResult.success(message, payload=payload)
        return CommandResult.error(f"Failed to delete session: {target}")


class CleanupSessionsCommand(BaseCommand):
    name = "cleanup"
    engine_scope = ("llm", "agent", "agentflow")
    help_text = "Clean up orphaned sessions."

    async def execute(self, ctx, args: str) -> CommandResult:
        if ctx.session_manager is None:
            return CommandResult.error("Session manager is not initialized.")
        cleanup_stats = ctx.session_manager.cleanup_orphaned_sessions()
        return CommandResult.success("Session cleanup completed.", payload=cleanup_stats)


__all__ = [
    "NewSessionCommand",
    "ClearSessionCommand",
    "ListSessionsCommand",
    "RestoreSessionCommand",
    "DeleteSessionCommand",
    "CleanupSessionsCommand",
]
