"""
Base service abstraction for engine-specific business logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseEngineService(ABC):
    """
    Abstract base class for engine services.
    """

    @abstractmethod
    async def initialize(self, ctx) -> Dict[str, Any]:
        """
        Prepare the service for use. Must return a structured result.
        """

    @abstractmethod
    async def handle_query(self, ctx, query: str) -> str:
        """
        Handle a conversation query and return a textual response.
        """

    @abstractmethod
    async def switch_model(self, ctx, provider: str, model: str | None = None) -> Dict[str, Any]:
        """
        Switch the active model for the engine where relevant.
        """

    @abstractmethod
    def get_info(self, ctx) -> Dict[str, Any]:
        """
        Return descriptive information about the engine state.
        """

    def supports_command(self, command_name: str) -> bool:
        """
        Override in subclasses to declare command compatibility.
        """
        return False

