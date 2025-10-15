"""
Dify engine service that implements the BaseEngineService contract.

The implementation adapts the legacy Dify control logic into a runtime
object managed by the service. The runtime handles configuration loading,
client lifecycle, streaming output, and file management.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

from src.application.services.base import BaseEngineService
from src.application.services.dify.client import DifyClient, DifyClientError
from src.application.services.dify.streaming import DifyStreaming
from src.application.services.dify.upload import handle_upload_command

logger = logging.getLogger(__name__)


class _DifyRuntime:
    """
    Runtime wrapper that encapsulates the legacy Dify control behaviour.
    """

    def __init__(self, console: Console, config_path: str = "config/dify/config.json") -> None:
        self.console = console
        self.config_path = config_path
        self.config_data: Optional[Dict[str, Any]] = None
        self.client: Optional[DifyClient] = None
        self.streaming: Optional[DifyStreaming] = None
        self.conversation_id: Optional[str] = None
        self.uploaded_files: List[Dict[str, Any]] = []
        self.initialized: bool = False

    async def initialize(self, force_reinit: bool = False) -> Dict[str, Any]:
        """
        Initialise the Dify client and streaming helpers.
        """
        if self.initialized and not force_reinit:
            return {"type": "success", "message": "Dify client already initialised."}

        if self.initialized and force_reinit:
            await self.cleanup()

        try:
            self.config_data = self._load_config()
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            return {"type": "error", "message": f"Configuration error: {exc}"}

        if not self._validate_config(self.config_data):
            return {"type": "error", "message": "Invalid Dify configuration."}

        self.client = DifyClient(
            api_key=self.config_data["api_key"],
            base_url=self.config_data["base_url"],
            timeout=self.config_data.get("timeout", 30),
        )

        self.streaming = DifyStreaming(self.console)
        self.streaming.buffer_size = self.config_data.get("streaming_buffer_size", 200)
        self.streaming.delay_ms = self.config_data.get("streaming_delay_ms", 20)
        self.streaming.display_refresh_rate = self.config_data.get("streaming_display_refresh_rate", 15)
        self.streaming.max_content_length = self.config_data.get("max_content_length", 1_000_000)
        self.streaming.max_chunks_per_second = self.config_data.get("max_chunks_per_second", 50)

        try:
            await self._test_connection()
        except DifyClientError as exc:
            logger.error("Dify connection test failed: %s", exc)
            return {"type": "error", "message": f"Connection test failed: {exc}"}

        self.initialized = True
        return {"type": "success", "message": "Dify client initialised successfully."}

    def _load_config(self) -> Dict[str, Any]:
        config_file = Path(self.config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Missing configuration file: {self.config_path}")

        raw_content = config_file.read_text(encoding="utf-8")
        substituted = self._substitute_env_vars(raw_content)
        return json.loads(substituted)

    def _substitute_env_vars(self, content: str) -> str:
        """
        Replace ${VAR} or ${VAR:-default} placeholders inside the config.
        """

        def _replace(match: re.Match[str]) -> str:
            expression = match.group(1)
            if ":-" in expression:
                var_name, default = expression.split(":-", 1)
                return os.getenv(var_name, default)
            value = os.getenv(expression)
            if value is None:
                raise ValueError(f"Environment variable '{expression}' is not set.")
            return value

        return re.sub(r"\$\{([^}]+)\}", _replace, content)

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        required = ("api_key", "base_url")
        for field in required:
            if not config.get(field):
                self.console.print(f"[red]Config validation failed: missing '{field}'.[/]")
                return False

        api_key = config["api_key"]
        if not (api_key.startswith("app-") or api_key.startswith("sk-")):
            self.console.print("[red]Invalid API key format. Should start with 'app-' or 'sk-'.[/]")
            return False

        return True

    async def _test_connection(self) -> None:
        """
        Send a lightweight request to ensure the client credentials work.
        """
        if self.client is None:
            raise DifyClientError("Client not initialised.")

        async for _ in self.client.chat_message(
            query="health_check",
            user_id="system_probe",
            streaming=False,
        ):
            break

    async def handle_query(self, query: str, user_id: str) -> Dict[str, Any]:
        if not self.initialized or self.client is None or self.streaming is None:
            return {"type": "error", "message": "Dify client is not initialised."}

        files_payload = None
        if self.uploaded_files:
            files_payload = [{k: v for k, v in item.items() if not k.startswith("_")} for item in self.uploaded_files]
            logger.debug("Sending files payload: %s", files_payload)

        try:
            stream = self.client.chat_message(
                query=query,
                user_id=user_id,
                streaming=True,
                conversation_id=self.conversation_id,
                files=files_payload,
            )

            if self.uploaded_files:
                self.console.print(f"[dim]Using {len(self.uploaded_files)} queued file(s); queue cleared.[/]")
                self.uploaded_files.clear()

            new_conversation_id = await self.streaming.display_stream(stream)
            if new_conversation_id:
                self.conversation_id = new_conversation_id

            return {"type": "success", "message": ""}
        except DifyClientError as exc:
            await self.streaming.display_error(str(exc))
            return {"type": "error", "message": str(exc)}
        except Exception as exc:
            logger.exception("Dify query processing failed: %s", exc)
            await self.streaming.display_error(f"Query processing failed: {exc}")
            return {"type": "error", "message": f"Query processing failed: {exc}"}

    async def handle_upload(self, ctx, args: str) -> Dict[str, Any]:
        if not self.initialized or self.client is None or self.config_data is None:
            return {"type": "error", "message": "Dify client is not initialised."}

        result = await handle_upload_command(
            ctx=ctx,
            query=args,
            client=self.client,
            console=self.console,
            config=self.config_data,
        )

        if result.get("type") == "success" and "uploaded_files" in result:
            uploaded_files = result["uploaded_files"]
            for file_result in uploaded_files:
                raw_response = file_result.get("raw_response", {})
                file_extension = raw_response.get("extension", "").lower()
                if file_extension and not file_extension.startswith("."):
                    file_extension = f".{file_extension}"

                raw_type = file_result.get("type")
                if raw_type in (None, "", "file"):
                    file_type = "image" if file_extension in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"} else "document"
                else:
                    file_type = raw_type

                self.uploaded_files.append(
                    {
                        "type": file_type,
                        "transfer_method": "local_file",
                        "upload_file_id": raw_response.get("id") or file_result.get("file_id"),
                        "_filename": file_result.get("filename", "unknown"),
                        "_size": file_result.get("size", 0),
                    }
                )

            count = len(uploaded_files)
            if count == 1:
                name = uploaded_files[0].get("filename", "unknown")
                self.console.print(f"[dim]Queued file: {name}. It will be used in the next conversation.[/]")
            else:
                self.console.print(f"[dim]Queued {count} files. They will be used in the next conversation.[/]")

            self.console.print(f"[blue]Pending files: {len(self.uploaded_files)}[/]")

        return result

    async def list_files(self) -> None:
        if not self.uploaded_files:
            self.console.print("[dim]No files are queued for the next conversation.[/]")
            return

        total_size = 0
        self.console.print(f"[blue]{len(self.uploaded_files)} queued file(s):[/]")
        for index, info in enumerate(self.uploaded_files, start=1):
            size = info.get("_size", 0)
            total_size += size
            size_str = self._format_size(size)
            file_type = info.get("type", "unknown")
            filename = info.get("_filename", "unknown")
            file_id = info.get("upload_file_id", "unknown")
            type_color = "cyan" if file_type == "image" else "yellow"
            self.console.print(f"  [{index}] [{type_color}]{file_type:<8}[/{type_color}] {filename} ({size_str})")
            self.console.print(f"      [dim]ID: {file_id}[/]")

        self.console.print(f"[dim]Total size: {self._format_size(total_size)}[/]")
        self.console.print("[dim]Files are consumed on the next conversation automatically.[/]")

    async def remove_file(self, index: int) -> Dict[str, Any]:
        if not self.uploaded_files:
            self.console.print("[yellow]No files to remove.[/]")
            return {"removed": 0, "failed": 0}

        if index < 1 or index > len(self.uploaded_files):
            self.console.print(f"[red]Invalid index {index}. Valid range: 1-{len(self.uploaded_files)}.[/]")
            return {"removed": 0, "failed": 1}

        removed = self.uploaded_files.pop(index - 1)
        filename = removed.get("_filename", "unknown")
        self.console.print(f"[green]Removed file: {filename}[/]")
        self.console.print(f"[dim]{len(self.uploaded_files)} file(s) remain queued.[/]")
        return {"removed": 1, "failed": 0}

    async def remove_files_by_indices(self, indices: List[int]) -> Dict[str, Any]:
        if not self.uploaded_files:
            self.console.print("[yellow]No files to remove.[/]")
            return {"removed": 0, "failed": 0}

        removed = 0
        failed = 0
        for index in sorted(set(indices), reverse=True):
            if 1 <= index <= len(self.uploaded_files):
                file_info = self.uploaded_files.pop(index - 1)
                self.console.print(f"[green]Removed: {file_info.get('_filename', 'unknown')}[/]")
                removed += 1
            else:
                self.console.print(f"[yellow]Skipped invalid index: {index}[/]")
                failed += 1

        self.console.print(f"[dim]Removed {removed} file(s); {len(self.uploaded_files)} remain queued.[/]")
        return {"removed": removed, "failed": failed}

    async def clear_files(self) -> None:
        if not self.uploaded_files:
            self.console.print("[dim]File queue is already empty.[/]")
            return

        count = len(self.uploaded_files)
        self.uploaded_files.clear()
        self.console.print(f"[yellow]Cleared {count} queued file(s).[/]")

    async def reset_conversation(self) -> None:
        self.conversation_id = None
        self.uploaded_files.clear()
        if self.streaming:
            await self.streaming.display_info("Conversation reset. File queue cleared.")

    async def get_detailed_info(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "queued_files": len(self.uploaded_files),
            "initialized": self.initialized,
        }

    async def cleanup(self) -> None:
        try:
            if self.client is not None:
                await self.client.close()
        except Exception as exc:  # pragma: no cover
            logger.warning("Error closing Dify client: %s", exc)
        finally:
            self.client = None
            self.streaming = None
            self.config_data = None
            self.uploaded_files.clear()
            self.conversation_id = None
            self.initialized = False

    @staticmethod
    def _format_size(size: int) -> str:
        if size > 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}MB"
        if size > 1024:
            return f"{size / 1024:.1f}KB"
        return f"{size}B"


class DifyService(BaseEngineService):
    """
    Service facade for the Dify runtime.
    """

    def _get_runtime(self, ctx) -> _DifyRuntime:
        config = ctx.get_engine_config("dify")
        runtime = config.get("runtime")
        if runtime is None:
            runtime = _DifyRuntime(ctx.console)
            config["runtime"] = runtime
        return runtime

    async def initialize(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        result = await runtime.initialize()
        if result["type"] == "error":
            return result

        return {
            "type": "success",
            "message": result.get("message", ""),
            "payload": {
                "agent": {
                    "provider": "dify",
                    "model": "cloud",
                    "conversation_id": runtime.conversation_id,
                    "files_count": len(runtime.uploaded_files),
                },
                "mode": {
                    "mode": "cloud",
                    "streaming": True,
                    "session_id": ctx.session_id,
                },
            },
        }

    async def handle_query(self, ctx, query: str) -> str:
        runtime = self._get_runtime(ctx)
        if not runtime.initialized:
            init_result = await runtime.initialize()
            if init_result["type"] == "error":
                ctx.console.print(f"[red]{init_result['message']}[/]")
                return ""
        result = await runtime.handle_query(query, user_id=ctx.session_id or "default_user")
        if result["type"] == "error":
            ctx.console.print(f"[red]{result['message']}[/]")
        return ""

    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        return {
            "type": "error",
            "message": "Dify relies on its managed cloud model and cannot switch providers.",
            "payload": {},
        }

    def get_info(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        return {
            "agent": {
                "provider": "dify",
                "model": "cloud",
                "conversation_id": runtime.conversation_id,
                "files_count": len(runtime.uploaded_files),
            },
            "mode": {
                "mode": "cloud",
                "streaming": True,
                "session_id": ctx.session_id,
            },
        }

    async def upload_from_command(self, ctx, args: str) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        if not runtime.initialized:
            init_result = await runtime.initialize()
            if init_result["type"] == "error":
                return init_result
        return await runtime.handle_upload(ctx, args)

    async def list_files(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        await runtime.list_files()
        return {"type": "success", "message": ""}

    async def clear_files(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        await runtime.clear_files()
        return {"type": "success", "message": "Cleared queued files."}

    async def remove_files(self, ctx, indices: List[int]) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        result = await runtime.remove_files_by_indices(indices)
        return {
            "type": "success",
            "message": f"Removed {result['removed']} file(s).",
            "payload": result,
        }

    async def reset(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        await runtime.reset_conversation()
        return {"type": "success", "message": "Conversation reset."}

    async def reconnect(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        init_result = await runtime.initialize(force_reinit=True)
        return init_result

    async def get_detailed_info(self, ctx) -> Dict[str, Any]:
        runtime = self._get_runtime(ctx)
        return await runtime.get_detailed_info()

    async def cleanup(self, ctx) -> None:
        runtime = self._get_runtime(ctx)
        await runtime.cleanup()
