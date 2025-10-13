"""
OpenAI LLM wrapper.

Provides a minimal wrapper around ChatOpenAI that accepts fully prepared parameters.
"""

import logging
from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)


class OpenAILLM:
    """Lightweight OpenAI chat model wrapper."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        streaming: bool = False,
        callback_manager: Optional[Any] = None,
        **extra_params: Any,
    ):
        if not api_key:
            raise ValueError("OpenAI api_key is required")

        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.streaming = streaming
        self.callback_manager = callback_manager
        self.extra_params = extra_params
        self._llm: Optional[BaseChatModel] = None

    def create_llm(self) -> BaseChatModel:
        """Instantiate and return ChatOpenAI."""
        llm_params: Dict[str, Any] = {
            "model": self.model,
            "openai_api_key": self.api_key,
            "streaming": self.streaming,
        }

        if self.base_url:
            llm_params["base_url"] = self.base_url
        if self.temperature is not None:
            llm_params["temperature"] = self.temperature
        if self.max_tokens is not None:
            llm_params["max_tokens"] = self.max_tokens
        if self.callback_manager is not None:
            llm_params["callback_manager"] = self.callback_manager

        llm_params.update(self.extra_params)

        logger.debug("Initialising ChatOpenAI with params: %s", llm_params.keys())
        self._llm = ChatOpenAI(**llm_params)
        return self._llm

    def get_llm(self) -> Optional[BaseChatModel]:
        """Return the cached LLM instance if already created."""
        return self._llm
