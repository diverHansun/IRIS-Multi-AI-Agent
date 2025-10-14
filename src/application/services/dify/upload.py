"""Utilities for selecting and uploading files to the Dify platform."""

from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from rich.console import Console
from rich.progress import (
    BarColumn,
    FileSizeColumn,
    Progress,
    TaskID,
    TimeRemainingColumn,
)
from tkinter import filedialog

from .client import DifyClient, DifyClientError

import logging

logger = logging.getLogger(__name__)


class DifyUploader:
    """
    High level helper that validates files and streams them to the Dify API.

    Console messages intentionally remain in Chinese so that end users keep
    the original experience.
    """

    def __init__(self, client: DifyClient, console: Console, config: Dict[str, Any]) -> None:
        self.client = client
        self.console = console
        self.config = config
        self.supported_types = {ext.lower() for ext in config.get("supported_file_types", [])}
        self.max_file_size = int(config.get("max_file_size", 10 * 1024 * 1024))  # default 10 MB

    # --------------------------------------------------------------------- #
    # Validation helpers
    # --------------------------------------------------------------------- #
    def validate_file(self, file_path: str) -> Dict[str, Any]:
        """
        Check whether the file satisfies configured constraints.
        """

        if not os.path.exists(file_path):
            return {"valid": False, "error": f"文件不存在: {file_path}"}

        if not os.path.isfile(file_path):
            return {"valid": False, "error": f"不是有效的文件: {file_path}"}

        extension = Path(file_path).suffix.lower()
        if self.supported_types and extension not in self.supported_types:
            supported = ", ".join(sorted(self.supported_types))
            return {"valid": False, "error": f"不支持的文件类型: {extension}\n支持的类型: {supported}"}

        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            size_mb = file_size / (1024 * 1024)
            limit_mb = self.max_file_size / (1024 * 1024)
            return {"valid": False, "error": f"文件过大: {size_mb:.1f}MB > {limit_mb:.1f}MB"}

        return {"valid": True, "size": file_size, "extension": extension}

    # --------------------------------------------------------------------- #
    # File selection helpers
    # --------------------------------------------------------------------- #
    def select_file(self) -> Optional[str]:
        """
        Open a native dialog to select a single file.
        """
        try:
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", 1)

            wildcard = " ".join(f"*{ext}" for ext in sorted(self.supported_types)) or "*.*"
            filetypes = [
                ("所有支持的文件", wildcard),
                ("文档", "*.txt *.md *.markdown *.pdf *.html *.xlsx *.xls *.docx *.csv *.xml *.epub"),
                ("图片", "*.jpg *.jpeg *.png *.gif *.webp *.svg"),
                ("全部文件", "*.*"),
            ]

            file_path = filedialog.askopenfilename(
                title="选择要上传的文件", filetypes=filetypes, initialdir=os.getcwd()
            )
            root.destroy()
            return file_path or None
        except Exception as exc:  # pragma: no cover - GUI failure is non-critical
            logger.error("文件选择对话框失败: %s", exc)
            self.console.print(f"[red]文件选择失败: {exc}[/red]")
            return None

    def select_files(self) -> Optional[List[str]]:
        """
        Open a native dialog to select multiple files.
        """
        try:
            root = tk.Tk()
            root.withdraw()
            root.wm_attributes("-topmost", 1)

            wildcard = " ".join(f"*{ext}" for ext in sorted(self.supported_types)) or "*.*"
            filetypes = [
                ("所有支持的文件", wildcard),
                ("文档", "*.txt *.md *.markdown *.pdf *.html *.xlsx *.xls *.docx *.csv *.xml *.epub"),
                ("图片", "*.jpg *.jpeg *.png *.gif *.webp *.svg"),
                ("全部文件", "*.*"),
            ]

            file_paths = filedialog.askopenfilenames(
                title="选择要上传的文件", filetypes=filetypes, initialdir=os.getcwd()
            )
            root.destroy()
            return list(file_paths) if file_paths else None
        except Exception as exc:  # pragma: no cover
            logger.error("文件选择对话框失败: %s", exc)
            self.console.print(f"[red]文件选择失败: {exc}[/red]")
            return None

    # --------------------------------------------------------------------- #
    # Upload helpers
    # --------------------------------------------------------------------- #
    async def upload_file(self, file_path: str, user_id: str) -> Dict[str, Any]:
        """
        Upload a single file and return the Dify response.
        """

        filename = os.path.basename(file_path)
        progress = Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            FileSizeColumn(),
            TimeRemainingColumn(),
            transient=True,
            console=self.console,
        )

        async with progress:
            task_id = progress.add_task(f"上传 {filename}", total=100)

            def _on_progress(percent: int) -> None:
                progress.update(task_id, completed=percent)

            try:
                response = await self.client.upload_file(
                    file_path=file_path,
                    user_id=user_id,
                    progress_callback=_on_progress,
                )
                return {
                    "success": True,
                    "file_id": response.get("id"),
                    "filename": response.get("name", filename),
                    "type": response.get("type"),
                    "raw_response": response,
                }
            except DifyClientError as exc:
                logger.error("Upload failed: %s", exc)
                return {"success": False, "error": str(exc)}

    async def upload_multiple_files(self, file_paths: List[str], user_id: str) -> Dict[str, Any]:
        """
        Upload multiple files sequentially and aggregate the results.
        """

        success: List[Dict[str, Any]] = []
        failed: List[Dict[str, Any]] = []

        for file_path in file_paths:
            result = await self.upload_file(file_path, user_id)
            if result["success"]:
                success.append({"file_path": file_path, "result": result})
            else:
                failed.append({"file_path": file_path, "error": result["error"]})

        return {"success": success, "failed": failed}


# ------------------------------------------------------------------------- #
# Public command helper
# ------------------------------------------------------------------------- #
async def handle_upload_command(
    ctx,
    query: str,
    client: DifyClient,
    console: Console,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Parse the upload command, validate chosen files, and forward them to Dify.
    """

    uploader = DifyUploader(client=client, console=console, config=config)
    tokens = shlex.split(query)

    if not tokens:
        console.print("[dim]正在打开文件选择对话框（支持多选）...[/dim]")
        selected = uploader.select_files()
        if not selected:
            console.print("[yellow]已取消上传[/yellow]")
            return {"type": "cancel"}
        file_paths = selected
    else:
        file_paths: List[str] = []
        for token in tokens:
            path = token
            if not os.path.isabs(path):
                path = os.path.abspath(path)
            file_paths.append(path)

    if len(file_paths) == 1:
        file_path = file_paths[0]
        validation = uploader.validate_file(file_path)
        if not validation["valid"]:
            console.print(f"[red]{validation['error']}[/red]")
            return {"type": "error", "message": validation["error"]}

        filename = os.path.basename(file_path)
        size_mb = validation["size"] / (1024 * 1024)
        console.print(f"[dim]准备上传: {filename} ({size_mb:.1f}MB)[/dim]")

        user_id = getattr(ctx, "session_id", "default_user")
        result = await uploader.upload_file(file_path, user_id)

        if not result["success"]:
            console.print(f"[red]上传失败: {result['error']}[/red]")
            return {"type": "error", "message": result["error"]}

        console.print(f"[green]上传成功: {result['filename']}[/green]")
        console.print(f"[dim]文件ID: {result['file_id']}[/dim]")
        if result.get("type") == "image":
            console.print("[dim]提示: 图片将在下一次对话中被引用。[/dim]")
        else:
            console.print("[dim]提示: 文档将在下一次对话中被引用。[/dim]")

        result_payload = {
            "type": "success",
            "file_id": result["file_id"],
            "filename": result["filename"],
            "file_type": result.get("type"),
            "file_info": result.get("raw_response", {}),
            "uploaded_files": [result],
        }
        return result_payload

    # Multiple file uploads
    console.print(f"[blue]准备批量上传 {len(file_paths)} 个文件...[/blue]")

    valid_files: List[str] = []
    invalid_files: List[Dict[str, str]] = []
    for file_path in file_paths:
        validation = uploader.validate_file(file_path)
        if validation["valid"]:
            valid_files.append(file_path)
        else:
            invalid_files.append({"path": file_path, "error": validation["error"]})

    if invalid_files:
        console.print(f"[yellow]提示: 有 {len(invalid_files)} 个文件未通过验证，将被忽略。[/yellow]")
        for item in invalid_files:
            console.print(f"  [dim]{os.path.basename(item['path'])}: {item['error']}[/dim]")

    if not valid_files:
        console.print("[red]全部文件均未通过验证，已取消上传。[/red]")
        return {"type": "error", "message": "所有文件均未通过验证"}

    console.print(f"[dim]开始上传 {len(valid_files)} 个有效文件...[/dim]")
    user_id = getattr(ctx, "session_id", "default_user")
    batch_result = await uploader.upload_multiple_files(valid_files, user_id)

    success_count = len(batch_result["success"])
    failed_count = len(batch_result["failed"])

    if success_count:
        console.print(f"[green]成功上传 {success_count} 个文件[/green]")
        for item in batch_result["success"]:
            info = item["result"]
            console.print(f"  [dim]• {info['filename']} (ID: {info['file_id']})[/dim]")

    if failed_count:
        console.print(f"[red]{failed_count} 个文件上传失败[/red]")
        for item in batch_result["failed"]:
            console.print(f"  [dim]• {os.path.basename(item['file_path'])}: {item['error']}[/dim]")

    if success_count == 0:
        return {
            "type": "error",
            "message": "批量文件上传失败",
            "failed_count": failed_count,
            "batch_result": batch_result,
        }

    return {
        "type": "success",
        "uploaded_files": [item["result"] for item in batch_result["success"]],
        "success_count": success_count,
        "failed_count": failed_count,
        "batch_result": batch_result,
    }


__all__ = ["DifyUploader", "handle_upload_command"]

