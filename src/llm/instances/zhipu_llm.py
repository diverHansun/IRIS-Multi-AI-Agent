"""
Zhipu AI LLM wrapper.

Provides a thin layer over ChatZhipuAI that simply forwards prepared parameters.
"""

import logging
from typing import Any, Dict, Optional

from langchain_community.chat_models import ChatZhipuAI
from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


class ZhipuAILLM:
    """Lightweight wrapper for ChatZhipuAI."""

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        streaming: bool = False,
        thinking_mode: bool = False,
        callback_manager: Optional[Any] = None,
        **extra_params: Any,
    ):
        if not api_key:
            raise ValueError("ZhipuAI api_key is required")

        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming
        self.thinking_mode = thinking_mode
        self.callback_manager = callback_manager
        self.extra_params = extra_params
        self._llm: Optional[BaseChatModel] = None

    def create_llm(self) -> BaseChatModel:
        """Instantiate and return the LangChain chat model."""
        client_params: Dict[str, Any] = {
            "model": self.model,
            "zhipuai_api_key": self.api_key,
            "streaming": self.streaming,
        }

        if self.temperature is not None:
            client_params["temperature"] = self.temperature
        if self.max_tokens is not None:
            client_params["max_tokens"] = self.max_tokens
        if self.callback_manager is not None:
            client_params["callback_manager"] = self.callback_manager

        # Convert thinking_mode flag into SDK parameters when enabled.
        if self.thinking_mode:
            self.extra_params.setdefault("thinking", True)

        client_params.update(self.extra_params)

        logger.debug("Initialising ChatZhipuAI with params: %s", client_params.keys())
        self._llm = ChatZhipuAI(**client_params)
        return self._llm

    def get_llm(self) -> Optional[BaseChatModel]:
        """Return the cached LLM instance if already created."""
        return self._llm
