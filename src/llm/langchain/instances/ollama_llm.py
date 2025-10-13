"""
Ollama LLM wrapper.

Provides a thin layer over ChatOllama. All arguments must be preprocessed by
upstream adapters and managers before constructing this class.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

import aiohttp
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class OllamaLLM:
    """Lightweight wrapper for Ollama chat models."""

    def __init__(
        self,
        model: str,
        base_url: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        num_ctx: Optional[int] = None,
        timeout: Optional[int] = None,
        keep_alive: Optional[str] = None,
        disable_thinking_mode: Optional[bool] = None,
        **extra_params: Any,
    ):
        if not model:
            raise ValueError("Ollama model name is required")
        if not base_url:
            raise ValueError("Ollama base_url is required")

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.num_ctx = num_ctx
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.disable_thinking_mode = disable_thinking_mode
        self.extra_params = extra_params
        self._llm: Optional[BaseChatModel] = None

    async def health_check(self) -> bool:
        """
        Verify whether the Ollama service is reachable and the model is present.

        Returns:
            True when the service responds with a valid model list.
        """
        url = f"{self.base_url}/api/tags"
        timeout = aiohttp.ClientTimeout(total=min(self.timeout or 10, 30))

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        logger.warning("Ollama health check failed with status %s", response.status)
                        return False

                    payload = await response.json()
                    available = {item.get("name") for item in payload.get("models", []) if item.get("name")}

                    if self.model == "auto":
                        return bool(available)
                    return self.model in available
        except asyncio.TimeoutError:
            logger.warning("Ollama health check timed out for %s", url)
            return False
        except Exception as exc:
            logger.debug("Ollama health check error: %s", exc)
            return False

    def _build_params(self) -> Dict[str, Any]:
        """Assemble keyword arguments for ChatOllama."""
        params: Dict[str, Any] = {
            "model": self.model,
            "base_url": self.base_url,
        }

        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k
        if self.num_ctx is not None:
            params["num_ctx"] = self.num_ctx
        if self.timeout is not None:
            params["timeout"] = self.timeout
        if self.keep_alive is not None:
            params["keep_alive"] = self.keep_alive
        if self.disable_thinking_mode is not None:
            params["disable_thinking"] = self.disable_thinking_mode

        params.update(self.extra_params)
        return params

    def create_llm(self) -> BaseChatModel:
        """Instantiate and return ChatOllama."""
        llm_params = self._build_params()
        logger.debug("Initialising ChatOllama with params: %s", llm_params)
        self._llm = ChatOllama(**llm_params)
        return self._llm

    def get_llm(self) -> Optional[BaseChatModel]:
        """Return the cached ChatOllama instance if it has been created."""
        return self._llm
