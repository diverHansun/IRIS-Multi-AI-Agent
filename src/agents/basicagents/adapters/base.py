"""
Refactored AgentAdapter base class.

Core assembler responsible for creating fully initialized Agent instances.
Adapter directly connects configuration to instance creation, eliminating Factory layer.

Following SOLID principles:
- SRP: Manages agent assembly workflow
- OCP: Extendable via provider-specific subclasses
- DIP: Depends on AgentConfig abstraction
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.exceptions import (
    LLMCreationError,
    ToolLoadingError,
    GraphCreationError,
    AgentCreationError,
)
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class AgentAdapter(ABC):
    """
    Base class for agent adapters.

    Adapter is the core assembler that creates fully initialized Agent instances.
    It orchestrates the creation of all components (LLM, tools, checkpointer, graph)
    and assembles them into a ready-to-use Agent.

    Responsibilities:
    1. Create LLM instance (provider-specific)
    2. Load tools (common across providers)
    3. Create checkpointer (common across providers)
    4. Create agent graph (provider-specific)
    5. Instantiate agent with all components (provider-specific)

    The adapter receives AgentConfig with all resolved parameters and uses it
    to create components without any hardcoded values.
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize agent adapter with resolved configuration.

        Args:
            config: Fully resolved AgentConfig instance
        """
        self.config = config
        self.provider = config.provider
        self.model = config.model

        logger.debug(
            f"AgentAdapter initialized: {self.provider}/{self.model}"
        )

    async def create_agent(self):
        """
        Create fully initialized agent instance.

        This is the main entry point for agent creation. It orchestrates
        all creation steps and returns a ready-to-use agent.

        Returns:
            Fully initialized Agent instance

        Raises:
            LLMCreationError: If LLM creation fails
            ToolLoadingError: If tool loading fails
            GraphCreationError: If graph creation fails
            AgentCreationError: If agent instantiation fails
        """
        try:
            # Step 1: Create LLM (provider-specific)
            logger.info(f"Creating LLM for {self.provider}/{self.model}")
            llm = self.create_llm()

            # Step 2: Load tools (common)
            logger.info("Loading tools")
            tools = await self.load_tools()

            # Step 3: Create checkpointer (common)
            logger.info("Creating checkpointer")
            checkpointer = self.create_checkpointer()

            # Step 4: Create graph (provider-specific)
            logger.info("Creating agent graph")
            graph = self.create_graph(llm, tools, checkpointer)

            # Step 5: Instantiate agent (provider-specific)
            logger.info("Instantiating agent")
            agent = self._instantiate_agent(llm, graph, tools, checkpointer)

            logger.info(
                f"Agent created successfully: {agent.__class__.__name__} "
                f"({self.provider}/{self.model})"
            )

            return agent

        except (LLMCreationError, ToolLoadingError, GraphCreationError) as e:
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            # Wrap unexpected exceptions
            raise AgentCreationError(
                f"Unexpected error during agent creation for {self.provider}/{self.model}: {e}"
            ) from e

    @abstractmethod
    def create_llm(self) -> BaseChatModel:
        """
        Create LLM instance.

        Provider-specific implementation. Uses self.config.llm_params for configuration.

        Returns:
            Initialized chat model instance

        Raises:
            LLMCreationError: If LLM creation fails
        """
        pass

    async def load_tools(self) -> List[BaseTool]:
        """
        Load tools using UnifiedToolManager.

        Common implementation across all providers.

        Returns:
            List of initialized tools

        Raises:
            ToolLoadingError: If tool loading fails
        """
        try:
            from src.components.shared.tools.unified_manager import UnifiedToolManager

            tool_manager = UnifiedToolManager(auto_register_defaults=True)
            await tool_manager.initialize_all()
            tools = tool_manager.get_all_tools()

            logger.info(f"Loaded {len(tools)} tools")
            return tools

        except Exception as e:
            raise ToolLoadingError(f"Failed to load tools: {e}") from e

    def create_checkpointer(self) -> Optional[UnifiedCheckpointer]:
        """
        Create checkpointer if memory is enabled.

        Common implementation across all providers.
        Uses self.config.agent_params for configuration.

        Returns:
            UnifiedCheckpointer instance if memory enabled, None otherwise
        """
        if not self.config.agent_params.get("memory_enabled", True):
            logger.info("Memory disabled, skipping checkpointer creation")
            return None

        # Create unified checkpointer with independent GlobalMemoryManager
        checkpointer = UnifiedCheckpointer(
            storage_dir="data/sessions",
            max_messages=50,
        )

        logger.info("Checkpointer created")
        return checkpointer

    @abstractmethod
    def create_graph(
        self,
        llm: BaseChatModel,
        tools: List[BaseTool],
        checkpointer: Optional[UnifiedCheckpointer],
    ) -> CompiledStateGraph:
        """
        Create agent graph.

        Provider-specific implementation. Uses self.config for configuration
        including system_prompt, agent_type, etc.

        Args:
            llm: Initialized chat model
            tools: List of tools
            checkpointer: Checkpointer instance or None

        Returns:
            Compiled state graph

        Raises:
            GraphCreationError: If graph creation fails
        """
        pass

    @abstractmethod
    def _instantiate_agent(
        self,
        llm: BaseChatModel,
        graph: CompiledStateGraph,
        tools: List[BaseTool],
        checkpointer: Optional[UnifiedCheckpointer],
    ):
        """
        Instantiate agent with all components.

        Provider-specific implementation. Returns the appropriate Agent subclass
        (e.g., ZhipuAgent, ZhipuFCallAgent, OpenAIAgent).

        Args:
            llm: Initialized chat model
            graph: Compiled state graph
            tools: List of tools
            checkpointer: Checkpointer instance or None

        Returns:
            Fully initialized Agent instance
        """
        pass

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"{self.__class__.__name__}(provider={self.provider}, model={self.model})"
