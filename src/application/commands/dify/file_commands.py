"""
Dify file management commands such as /upload and /files.
"""

from __future__ import annotations

from typing import List

from ...services.dify import DifyService
from ..base import BaseCommand, CommandResult


class DifyUploadCommand(BaseCommand):
    name = "upload"
    engine_scope = ("dify",)
    help_text = "Upload files to the Dify workspace."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = DifyService()
        result = await service.upload_from_command(ctx, args)
        if result["type"] == "error":
            return CommandResult.error(result.get("message", "Upload failed."), payload=result.get("payload"))
        message = result.get("message", "Files uploaded successfully.")
        return CommandResult.success(message, payload=result.get("payload"))


class DifyFilesCommand(BaseCommand):
    name = "files"
    engine_scope = ("dify",)
    help_text = "List or manage queued files for Dify."

    async def execute(self, ctx, args: str) -> CommandResult:
        service = DifyService()
        tokens = args.strip().split()

        if not tokens:
            await service.list_files(ctx)
            return CommandResult.success("")

        action = tokens[0].lower()

        if action == "clear":
            result = await service.clear_files(ctx)
            return CommandResult(type=result["type"], message=result.get("message", ""), payload=result.get("payload"))

        if action == "remove":
            if len(tokens) < 2:
                return CommandResult.error("Usage: /files remove <index ...>")
            try:
                indices: List[int] = [int(token) for token in tokens[1:]]
            except ValueError:
                return CommandResult.error("File indices must be integers.")
            result = await service.remove_files(ctx, indices)
            return CommandResult(
                type=result["type"],
                message=result.get("message", ""),
                payload=result.get("payload"),
            )

        return CommandResult.error("Usage: /files [clear|remove <index ...>]")


__all__ = ["DifyUploadCommand", "DifyFilesCommand"]
