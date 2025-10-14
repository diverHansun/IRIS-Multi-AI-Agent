"""
Dify file management commands such as /upload and /files.
"""

from __future__ import annotations

from ..base import BaseCommand, CommandResult


class DifyUploadCommand(BaseCommand):
    name = "upload"
    engine_scope = ("dify",)
    help_text = "Upload files to the Dify workspace."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("Dify file upload will be implemented during migration.")


class DifyFilesCommand(BaseCommand):
    name = "files"
    engine_scope = ("dify",)
    help_text = "List uploaded files for Dify."

    async def execute(self, ctx, args: str) -> CommandResult:
        return CommandResult.info("Dify file listing will be implemented during migration.")


__all__ = ["DifyUploadCommand", "DifyFilesCommand"]
