"""
Provider Base Class

Provider abstract base class, defines unified Provider interface.
This is a shared module used by both LLM and Agent modules.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseProvider(ABC):
    """
    Provider abstract base class

    Responsibilities:
    - Define unified Provider interface
    - Encapsulate Provider-specific creation logic
    - Manage Provider configuration
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Provider

        Args:
            config: Provider configuration from providers.json
        """
        self.config = config
        self.name = config.get("name")
        self.default_model = config.get("default_model")
        self.api_key_env = config.get("api_key_env")
        self.models = config.get("models", {})
        self.mode_defaults = config.get("mode_defaults", {})

        logger.debug(f"Provider initialized: {self.name}")

    @abstractmethod
    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """
        Create LLM instance (must be implemented by subclass)

        Args:
            model: Model name
            api_key: API key
            **kwargs: Additional parameters

        Returns:
            LLM instance
        """
        pass

    @abstractmethod
    def validate_api_key(self, api_key: str) -> bool:
        """
        Validate API key format (must be implemented by subclass)

        Args:
            api_key: API key

        Returns:
            Whether valid
        """
        pass

    def get_supported_models(self) -> Dict[str, Any]:
        """
        Get supported model list

        Returns:
            Model configuration dictionary
        """
        return self.models

    def get_default_model(self) -> str:
        """Get default model"""
        return self.default_model

    def get_model_config(self, model: str) -> Optional[Dict[str, Any]]:
        """
        Get model configuration

        Args:
            model: Model name

        Returns:
            Model configuration, None if not exists
        """
        return self.models.get(model)

    def validate_model(self, model: str) -> bool:
        """
        Validate if model is supported

        Args:
            model: Model name

        Returns:
            Whether supported
        """
        return model in self.models

    def get_mode_defaults(self, mode: str) -> Dict[str, Any]:
        """
        Get mode default parameters

        Args:
            mode: Mode name ("llm" or "agent")

        Returns:
            Mode default parameters
        """
        return self.mode_defaults.get(mode, {})

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, default_model={self.default_model})"
