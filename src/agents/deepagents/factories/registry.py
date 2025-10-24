"""Factory registry for DeepAgents."""

from __future__ import annotations

from typing import Dict, Optional, Type

from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter
from src.agents.deepagents.factories.base import BaseDeepAgentFactory


class DeepAgentFactoryRegistry:
    """Registry managing deep agent factories and adapters."""

    def __init__(self) -> None:
        self._factories: Dict[str, BaseDeepAgentFactory] = {}
        self._adapter_classes: Dict[str, Type[BaseDeepAgentAdapter]] = {}
        self._register_defaults()

    def register_factory(
        self,
        factory: BaseDeepAgentFactory,
        *,
        adapter_class: Type[BaseDeepAgentAdapter],
    ) -> None:
        """Register a factory and its adapter class."""
        function_type = factory.function_type
        self._factories[function_type] = factory
        self._adapter_classes[function_type] = adapter_class

    def get_factory(self, function_type: str) -> Optional[BaseDeepAgentFactory]:
        """Retrieve factory for a function type."""
        return self._factories.get(function_type)

    def get_adapter_class(self, function_type: str) -> Optional[Type[BaseDeepAgentAdapter]]:
        """Retrieve adapter class for a function type."""
        return self._adapter_classes.get(function_type)

    def describe_factories(self) -> Dict[str, Dict[str, str]]:
        """Return descriptions for registered factories."""
        return {key: factory.describe() for key, factory in self._factories.items()}

    def _register_defaults(self) -> None:
        """Register built-in factories."""
        from src.agents.deepagents.adapters import AnalysisAdapter, CodingAdapter, ResearchAdapter
        from src.agents.deepagents.factories.analysis_factory import AnalysisFactory
        from src.agents.deepagents.factories.coding_factory import CodingFactory
        from src.agents.deepagents.factories.research_factory import ResearchFactory

        self.register_factory(
            ResearchFactory(),
            adapter_class=ResearchAdapter,
        )
        self.register_factory(
            CodingFactory(),
            adapter_class=CodingAdapter,
        )
        self.register_factory(
            AnalysisFactory(),
            adapter_class=AnalysisAdapter,
        )
