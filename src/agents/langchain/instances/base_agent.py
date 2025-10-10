"""
Base Agent Abstract Class

Defines the template method pattern for all agents.
Extracts common initialization, execution, and memory management logic.
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

from langchain_core.runnables.history import RunnableWithMessageHistory

from ....components.shared.tools.unified_manager import UnifiedToolManager
from ....components.shared.memory.global_memory import GlobalMemoryManager

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base Agent class implementing template method pattern.

    All agent implementations should inherit from this class and implement
    the abstract methods: _create_llm() and _build_agent().

    The common initialization flow, execution logic, and memory management
    are handled by the base class.
    """

    def __init__(
        self,
        model: str,
        temperature: float = 0.1,
        verbose: bool = False,
        max_iterations: int = 8,
        enable_memory: bool = True,
        memory_config: Optional[Dict[str, Any]] = None,
        global_memory_manager = None,
        **kwargs
    ):
        """
        Initialize base agent.

        Args:
            model: Model name
            temperature: Temperature parameter
            verbose: Enable verbose logging
            max_iterations: Maximum iterations for agent execution
            enable_memory: Enable memory management
            memory_config: Memory configuration parameters
            global_memory_manager: Global memory manager instance
            **kwargs: Additional parameters
        """
        self.model = model
        self.temperature = temperature
        self.verbose = verbose
        self.max_iterations = max_iterations
        self.enable_memory = enable_memory
        self.global_memory_manager = global_memory_manager
        self.kwargs = kwargs

        # Core components
        self.llm = None
        self.tools = []
        self.agent_executor = None
        self.is_initialized = False

        # Memory management
        self.chat_memory = None
        self.agent_with_memory = None

        if enable_memory:
            self._init_memory(memory_config or {})

    async def initialize(self):
        """
        Template method for agent initialization.

        This method defines the initialization flow:
        1. Create LLM (implemented by subclass)
        2. Load tools (common logic)
        3. Build agent (implemented by subclass)
        4. Setup memory (common logic)
        """
        if self.is_initialized:
            return

        try:
            logger.info(f"Initializing {self.__class__.__name__}...")

            # Step 1: Create LLM (subclass implementation)
            await self._create_llm()

            # Step 2: Load tools (common logic)
            await self._load_tools()

            # Step 3: Build agent (subclass implementation)
            self._build_agent()

            # Step 4: Setup memory (common logic)
            if self.enable_memory and self.chat_memory:
                self._build_agent_with_memory()

            self.is_initialized = True
            logger.info(
                f"{self.__class__.__name__} initialized - "
                f"Model: {self.model}, Tools: {len(self.tools)}"
            )

        except Exception as e:
            logger.error(f"Agent initialization failed: {e}")
            raise

    @abstractmethod
    async def _create_llm(self):
        """
        Create LLM instance (must be implemented by subclass).

        Subclasses should create self.llm in this method.
        """
        pass

    @abstractmethod
    def _build_agent(self):
        """
        Build agent executor (must be implemented by subclass).

        Subclasses should create self.agent_executor in this method.
        """
        pass

    async def _load_tools(self):
        """
        Load all tools using UnifiedToolManager (common logic for all agents).

        Uses the strategy pattern to load tools from all registered providers:
        1. SDK Tool Provider
        2. MCP Tool Provider
        3. Connector Tool Provider
        """
        logger.info("Loading tools using UnifiedToolManager...")

        # Create and initialize tool manager
        tool_manager = UnifiedToolManager(auto_register_defaults=True)
        await tool_manager.initialize_all()

        # Get all tools
        self.tools = tool_manager.get_all_tools()

        logger.info(f"Total tools loaded: {len(self.tools)}")

        # Log tool counts by provider
        status = tool_manager.get_status()
        for provider_name, provider_status in status["providers"].items():
            logger.debug(
                f"  {provider_name}: {provider_status['tool_count']} tools"
            )

    def _init_memory(self, config: Dict[str, Any]) -> None:
        """
        Initialize memory manager (common logic).

        Args:
            config: Memory configuration parameters
        """
        try:
            if self.global_memory_manager:
                self.chat_memory = self.global_memory_manager
                logger.info("Using global memory manager")
            else:
                self.chat_memory = GlobalMemoryManager(
                    storage_dir=config.get("storage_path", "data/sessions"),
                    max_messages=config.get("max_messages", 50)
                )
                logger.info("Using local memory manager")
        except Exception as e:
            logger.error(f"Memory manager initialization failed: {e}")
            self.enable_memory = False

    def _build_agent_with_memory(self):
        """
        Build agent with memory support (common logic).

        Wraps agent_executor with RunnableWithMessageHistory.
        """
        try:
            if not self.agent_executor:
                raise ValueError("Base agent must be initialized first")

            if self.global_memory_manager:
                self.agent_with_memory = self.global_memory_manager.create_runnable_with_memory(
                    self.agent_executor,
                    input_key="input",
                    history_key="chat_history"
                )
            else:
                self.agent_with_memory = self.chat_memory.create_runnable_with_memory(
                    self.agent_executor
                )

            logger.info("Agent with memory created")

        except Exception as e:
            logger.error(f"Agent with memory creation failed: {e}")
            self.enable_memory = False
            raise

    async def _execute_query(
        self,
        query: str,
        session_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute query (common logic for all agents).

        Args:
            query: User query
            session_id: Session ID for memory management
            **kwargs: Additional parameters

        Returns:
            Execution result with output, tool calls, and metadata
        """
        try:
            # Use agent with memory if enabled
            if self.enable_memory and self.agent_with_memory:
                result = await self.agent_with_memory.ainvoke(
                    {"input": query},
                    config={"configurable": {"session_id": session_id}}
                )

                # Save session
                if self.chat_memory:
                    self.chat_memory.save_session(session_id)

                # Extract tool names
                tool_names = self._extract_tool_names(result.get("intermediate_steps", []))

                return {
                    "output": result["output"],
                    "intermediate_steps": result.get("intermediate_steps", []),
                    "success": True,
                    "tool_calls": len(result.get("intermediate_steps", [])),
                    "tool_names": tool_names,
                    "session_id": session_id,
                    "memory_enabled": True
                }
            else:
                # Use agent without memory
                result = await self.agent_executor.ainvoke({"input": query})

                # Extract tool names
                tool_names = self._extract_tool_names(result.get("intermediate_steps", []))

                return {
                    "output": result["output"],
                    "intermediate_steps": result.get("intermediate_steps", []),
                    "success": True,
                    "tool_calls": len(result.get("intermediate_steps", [])),
                    "tool_names": tool_names,
                    "session_id": None,
                    "memory_enabled": False
                }

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                "output": f"Query execution failed: {str(e)}",
                "intermediate_steps": [],
                "success": False,
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id,
                "memory_enabled": self.enable_memory
            }

    def _extract_tool_names(self, intermediate_steps: List) -> List[str]:
        """
        Extract tool names from intermediate steps.

        Args:
            intermediate_steps: List of (AgentAction, observation) tuples

        Returns:
            List of tool names
        """
        tool_names = []
        for step in intermediate_steps:
            if hasattr(step, '__len__') and len(step) >= 1:
                agent_action = step[0]
                if hasattr(agent_action, 'tool'):
                    tool_names.append(agent_action.tool)
        return tool_names

    async def invoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Async invoke agent (main interface).

        Args:
            query: User query
            session_id: Session ID for memory management
            **kwargs: Additional parameters

        Returns:
            Execution result
        """
        if not self.is_initialized:
            await self.initialize()

        return await self._execute_query(query, session_id, **kwargs)

    async def ainvoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Async invoke agent (LangChain standard interface).

        Args:
            query: User query
            session_id: Session ID for memory management
            **kwargs: Additional parameters

        Returns:
            Execution result
        """
        return await self.invoke(query, session_id, **kwargs)

    def invoke_sync(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """
        Sync invoke agent (compatibility interface).

        Args:
            query: User query
            session_id: Session ID for memory management

        Returns:
            Execution result
        """
        try:
            loop = asyncio.get_running_loop()
            task = asyncio.create_task(self.invoke(query, session_id))
            return asyncio.run_coroutine_threadsafe(task, loop).result()
        except RuntimeError:
            return asyncio.run(self.invoke(query, session_id))

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get agent information.

        Returns:
            Agent metadata including model, tools, and memory status
        """
        from ...llm.langchain.llm_manager import get_llm_info

        # Get model info
        provider = self._get_provider_name()
        try:
            model_info = get_llm_info(provider, self.model)
        except Exception as e:
            logger.warning(f"Failed to get model info: {e}")
            model_info = {}

        # Get actual temperature
        actual_temperature = self.temperature
        if hasattr(self, 'llm') and self.llm and hasattr(self.llm, 'temperature'):
            actual_temperature = self.llm.temperature

        info = {
            "provider": provider,
            "model": self.model,
            "temperature": actual_temperature,
            "max_iterations": self.max_iterations,
            "initialized": self.is_initialized,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory,
            **model_info
        }

        # Add memory info
        if self.enable_memory and self.chat_memory:
            info["memory_info"] = self.chat_memory.get_memory_stats()

        return info

    @abstractmethod
    def _get_provider_name(self) -> str:
        """
        Get provider name (must be implemented by subclass).

        Returns:
            Provider name (e.g., "zhipu", "openai", "ollama")
        """
        pass

    def get_info(self) -> Dict[str, Any]:
        """Get agent info (compatibility interface)."""
        return self.get_agent_info()

    def get_llm(self):
        """Get underlying LLM instance."""
        return self.llm

    def list_tools(self) -> List[str]:
        """List tool names."""
        return [tool.name for tool in self.tools]

    # Memory management methods

    def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """Get memory statistics."""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.get_memory_stats()
        return None

    def clear_memory(self, session_id: str = "default") -> bool:
        """Clear session memory."""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.clear_session(session_id)
        return False

    def save_memory(self, session_id: str = "default") -> bool:
        """Manually save memory."""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.save_session(session_id)
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions."""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.list_sessions()
        return []

    def delete_session(self, session_id: str) -> bool:
        """Delete session."""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.delete_session(session_id)
        return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session detailed information."""
        if self.enable_memory and self.chat_memory:
            return self.chat_memory.get_session_info(session_id)
        return None
