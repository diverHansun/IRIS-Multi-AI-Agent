"""Client helpers for interacting with the Dify REST API."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


class DifyClientError(Exception):
    """Raised when communication with the Dify API fails."""


class DifyClient:
    """Async HTTP client that wraps the Dify REST endpoints used by the CLI."""

    def __init__(self, api_key: str, base_url: str, timeout: int = 30) -> None:
        """
        Initialise the client.

        Args:
            api_key: Dify API key that authorises requests.
            base_url: Base URL of the Dify deployment.
            timeout: Default timeout (seconds) used for HTTP operations.
        """

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # Streaming requests tend to run longer than ordinary calls.
        self.streaming_timeout = timeout * 4
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> "DifyClient":
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        return self

    async def __aexit__(self, exc_type, exc, exc_tb) -> None:
        await self.close()

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def _raise_for_status(
        self, response: aiohttp.ClientResponse, *, context: str
    ) -> None:
        if 200 <= response.status < 300:
            return

        body = await response.text()
        try:
            payload = json.loads(body)
            message = payload.get("message", body)
            code = payload.get("code", "unknown")
            raise DifyClientError(f"{context} [{code}]: {message}")
        except json.JSONDecodeError:
            raise DifyClientError(f"{context}: HTTP {response.status}, {body}")

    async def chat_message(
        self,
        query: str,
        user_id: str,
        streaming: bool = True,
        conversation_id: Optional[str] = None,
        inputs: Optional[Dict[str, Any]] = None,
        files: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a chat message and yield events from the API.
        """

        session = await self._get_session()
        payload: Dict[str, Any] = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "streaming" if streaming else "blocking",
            "user": user_id,
        }

        if conversation_id:
            payload["conversation_id"] = conversation_id
        if files:
            payload["files"] = files

        timeout = aiohttp.ClientTimeout(total=self.streaming_timeout if streaming else self.timeout)

        async with session.post(
            f"{self.base_url}/chat-messages",
            json=payload,
            headers=self.headers,
            timeout=timeout,
        ) as response:
            await self._raise_for_status(response, context="Chat request failed")

            if not streaming:
                data = await response.json()
                yield data
                return

            buffer = b""
            async for chunk in response.content.iter_chunked(1024):
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if not line.startswith(b"data: "):
                        continue

                    payload = line[6:]
                    if payload == b"[DONE]":
                        return

                    try:
                        event = json.loads(payload.decode("utf-8"))
                    except json.JSONDecodeError:
                        logger.warning("Failed to decode streaming payload: %s", payload)
                        continue

                    logger.debug("Streaming event: %s", event)
                    yield event

    async def upload_file(
        self,
        file_path: str,
        user_id: str,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Dify's file endpoint.
        """

        if not os.path.exists(file_path):
            raise DifyClientError(f"文件不存在: {file_path}")

        session = await self._get_session()
        url = f"{self.base_url}/files/upload"
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        content_type = self._guess_mime_type(filename)

        async def _progress_hook(transferred: int) -> None:
            if progress_callback:
                percentage = int(transferred * 100 / max(file_size, 1))
                progress_callback(min(percentage, 100))

        form = aiohttp.FormData()
        form.add_field("user", user_id)

        with open(file_path, "rb") as file_obj:
            reader = _StreamingReader(file_obj, _progress_hook)
            form.add_field(
                "file",
                reader,
                filename=filename,
                content_type=content_type,
            )

            async with session.post(
                url,
                headers={"Authorization": self.headers["Authorization"]},
                data=form,
                timeout=aiohttp.ClientTimeout(total=self.streaming_timeout),
            ) as response:
                await self._raise_for_status(response, context="Upload failed")
                return await response.json()

    async def close(self) -> None:
        """
        Close the underlying HTTP session.
        """
        if self._session and not self._session.closed:
            await self._session.close()
            await asyncio.sleep(0.05)
        self._session = None

    @staticmethod
    def _guess_mime_type(filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".pdf": "application/pdf",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".csv": "text/csv",
            ".json": "application/json",
        }.get(ext, "application/octet-stream")


class _StreamingReader:
    """
    Wrapper that reports upload progress while aiohttp reads chunks from disk.
    """

    def __init__(self, stream, callback) -> None:
        self._stream = stream
        self._callback = callback
        self._transferred = 0

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        self._transferred += len(chunk)
        if chunk and self._callback:
            try:
                self._callback(self._transferred)
            except Exception as exc:  # pragma: no cover - best effort
                logger.debug("Progress callback failed: %s", exc)
        return chunk

    def __getattr__(self, item: str) -> Any:
        return getattr(self._stream, item)

