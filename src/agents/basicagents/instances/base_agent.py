"""Base agent abstraction built on LangChain 1.0 agent graphs."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.agents import AgentAction
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from src.components.shared.memory.checkpointer import (
    BaseAgentCheckpointer,
    create_default_checkpointer,
)
from src.components.shared.memory.global_memory import GlobalMemoryManager
from src.components.shared.tools.unified_manager import UnifiedToolManager

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Template base class for all agents."""

    def __init__(
        self,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        llm_adapter: Optional[Any] = None,
        agent_adapter: Optional[Any] = None,
        memory_config: Optional[Dict[str, Any]] = None,
        global_memory_manager: Optional[GlobalMemoryManager] = None,
        **kwargs: Any,
    ) -> None:
        self.model = model
        self.provider = provider
        self.llm_adapter = llm_adapter
        self.agent_adapter = agent_adapter
        self._use_adapters = bool(llm_adapter or agent_adapter)

        if agent_adapter:
            agent_params = agent_adapter.get_agent_params(**kwargs)
            self.temperature = agent_params.get("temperature", 0.1)
            self.verbose = agent_params.get("verbose", False)
            self.max_iterations = agent_params.get("max_iterations", 8)
            self.enable_memory = agent_params.get("memory_enabled", True)
            self.max_execution_time = agent_params.get("max_execution_time")
            logger.info(
                "BaseAgent initialised using adapter: provider=%s model=%s max_iterations=%s",
                provider,
                model,
                self.max_iterations,
            )
        else:
            self.temperature = 0.1
            self.verbose = False
            self.max_iterations = 8
            self.enable_memory = True
            self.max_execution_time = None
            logger.info(
                "BaseAgent initialised with defaults: model=%s max_iterations=%s",
                model,
                self.max_iterations,
            )

        self.global_memory_manager = global_memory_manager
        self.memory_config = memory_config or {}
        self.kwargs = kwargs

        self.llm: Optional[Any] = None
        self.tools: List[Any] = []
        self.agent_graph: Optional[Any] = None
        self.is_initialized = False

        self.chat_memory: Optional[GlobalMemoryManager] = None
        self.checkpointer: Optional[BaseAgentCheckpointer] = None

        if self.enable_memory:
            self._init_memory(self.memory_config)

    async def initialize(self) -> None:
        """Initialise the agent by creating the LLM, loading tools, and building the agent graph."""
        if self.is_initialized:
            return

        try:
            logger.info("Initialising %s...", self.__class__.__name__)
            await self._create_llm_with_adapter()
            await self._load_tools()
            self._build_agent_graph_with_adapter()
            self.is_initialized = True
            logger.info(
                "%s initialised: model=%s tools=%d",
                self.__class__.__name__,
                self.model,
                len(self.tools),
            )
        except Exception as exc:
            logger.error("Agent initialisation failed: %s", exc, exc_info=True)
            raise

    async def _create_llm_with_adapter(self) -> None:
        """Create the LLM using the configured adapter."""
        llm_params = self.llm_adapter.get_llm_params(**self.kwargs) if self.llm_adapter else {}
        if hasattr(self, "_create_llm_instance"):
            self.llm = await self._create_llm_instance(llm_params)
        else:
            await self._create_llm()
        logger.info("LLM created: model=%s params=%s", self.model, llm_params)

    async def _create_llm(self) -> None:
        """Fallback LLM creation hook for subclasses."""
        logger.warning(
            "_create_llm is not implemented for %s; provide llm_adapter or override this method",
            self.__class__.__name__,
        )

    def _build_agent_graph_with_adapter(self) -> None:
        """Create the CompiledStateGraph using the agent adapter."""
        if not self.agent_adapter:
            raise ValueError("Agent adapter is required for building the agent graph")

        self.agent_graph = self.agent_adapter.create_agent_graph(
            llm=self.llm,
            tools=self.tools,
            checkpointer=self.checkpointer if self.enable_memory else None,
        )

        logger.info("Agent graph created for provider=%s model=%s", self.provider, self.model)

    async def _load_tools(self) -> None:
        """Load all registered tools via the unified tool manager."""
        logger.info("Loading tools using UnifiedToolManager...")
        tool_manager = UnifiedToolManager(auto_register_defaults=True)
        await tool_manager.initialize_all()
        self.tools = tool_manager.get_all_tools()

        status = tool_manager.get_status()
        for provider_name, provider_status in status.get("providers", {}).items():
            logger.debug("%s: %s tools", provider_name, provider_status.get("tool_count", 0))

        logger.info("Loaded %d tools", len(self.tools))

    def _init_memory(self, config: Dict[str, Any]) -> None:
        """Initialise memory manager and checkpointer."""
        try:
            if self.global_memory_manager:
                self.chat_memory = self.global_memory_manager
                logger.info("Using global memory manager")
            else:
                self.chat_memory = GlobalMemoryManager(
                    storage_dir=config.get("storage_path", "data/sessions"),
                    max_messages=config.get("max_messages", 50),
                )
                logger.info("Using local memory manager")

            self.checkpointer = create_default_checkpointer()
        except Exception as exc:
            logger.error("Memory manager initialisation failed: %s", exc)
            self.enable_memory = False
            self.checkpointer = None

    def _prepare_graph_input(self, query: str) -> Dict[str, Sequence[BaseMessage]]:
        """Convert textual query into the message-based input required by the graph."""
        return {"messages": [HumanMessage(content=query)]}

    def _build_graph_config(
        self,
        session_id: str,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Construct the run configuration for graph execution."""
        base_config: Optional[Dict[str, Any]] = None
        if self.enable_memory and self.checkpointer:
            base_config = self.checkpointer.build_config(session_id)

        if extra_config is None:
            return base_config

        if base_config is None:
            return extra_config

        merged = dict(extra_config)
        base_configurable = dict(base_config.get("configurable", {}))
        extra_configurable = dict(extra_config.get("configurable", {}))
        merged["configurable"] = {**base_configurable, **extra_configurable}
        return merged

    def _parse_graph_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert the graph output into the legacy executor response structure."""
        messages: Sequence[BaseMessage] = result.get("messages", [])  # type: ignore[assignment]
        output = self._extract_final_output(messages)
        intermediate_steps = self._extract_intermediate_steps(messages)
        tool_names = self._extract_tool_names(intermediate_steps)

        return {
            "output": output,
            "intermediate_steps": intermediate_steps,
            "tool_calls": len(intermediate_steps),
            "tool_names": tool_names,
        }

    def _extract_final_output(self, messages: Sequence[BaseMessage]) -> str:
        """Extract the latest AI response from the message list."""
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return self._normalize_message_content(message.content)
        return ""

    def _extract_intermediate_steps(
        self,
        messages: Sequence[BaseMessage],
    ) -> List[Any]:
        """Reconstruct intermediate steps from AI and tool messages."""
        tool_messages: Dict[str, ToolMessage] = {}
        for message in messages:
            if isinstance(message, ToolMessage) and message.tool_call_id:
                tool_messages[message.tool_call_id] = message

        steps: List[Any] = []

        for message in messages:
            if isinstance(message, AIMessage):
                tool_calls = getattr(message, "tool_calls", None)
                if not tool_calls:
                    continue

                for tool_call in tool_calls:
                    action = AgentAction(
                        tool=tool_call.get("name", ""),
                        tool_input=tool_call.get("args", {}),
                        log=str(tool_call.get("id", "")),
                    )
                    observation = ""
                    tool_call_id = tool_call.get("id")
                    if tool_call_id and tool_call_id in tool_messages:
                        observation = self._normalize_message_content(
                            tool_messages[tool_call_id].content
                        )
                    steps.append((action, observation))

        return steps

    def _extract_tool_names(self, intermediate_steps: List[Any]) -> List[str]:
        """Collect tool names from intermediate steps."""
        names: List[str] = []
        for step in intermediate_steps:
            if isinstance(step, tuple) and step and isinstance(step[0], AgentAction):
                names.append(step[0].tool)
        return names

    def _normalize_message_content(self, content: Any) -> str:
        """Normalise message content into a plain string."""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    parts.append(str(item.get("text") or item.get("content") or item))
                else:
                    parts.append(str(item))
            return " ".join(part for part in parts if part)
        return str(content)

    def _record_conversation(self, session_id: str, query: str, output: str) -> None:
        """Store the conversation turn in the configured memory managers."""
        if not self.enable_memory or not self.chat_memory:
            return

        add_conversation = getattr(self.chat_memory, "add_conversation", None)
        if callable(add_conversation):
            try:
                add_conversation(session_id, query, output, current_llm_info=None)
            except Exception as exc:
                logger.warning("Failed to record conversation: %s", exc)

        save_session = getattr(self.chat_memory, "save_session", None)
        if callable(save_session):
            try:
                save_session(session_id)
            except Exception as exc:
                logger.warning("Failed to save session: %s", exc)

    async def _execute_query(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute the agent graph and adapt the output to the legacy contract."""
        if not self.agent_graph:
            raise RuntimeError("Agent graph is not initialised; call initialize() first")

        try:
            graph_input = self._prepare_graph_input(query)
            extra_config = kwargs.pop("config", None)
            run_config = self._build_graph_config(session_id, extra_config)

            if run_config:
                result = await self.agent_graph.ainvoke(graph_input, config=run_config)
            else:
                result = await self.agent_graph.ainvoke(graph_input)

            parsed = self._parse_graph_output(result)
            parsed.update(
                {
                    "success": True,
                    "session_id": session_id if self.enable_memory else None,
                    "memory_enabled": self.enable_memory,
                }
            )

            self._record_conversation(session_id, query, parsed["output"])

            return parsed
        except Exception as exc:
            logger.error("Query execution failed: %s", exc, exc_info=True)
            return {
                "output": f"Query execution failed: {exc}",
                "intermediate_steps": [],
                "success": False,
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id if self.enable_memory else None,
                "memory_enabled": self.enable_memory,
            }

    def _extract_tool_names_from_steps(self, intermediate_steps: List[Any]) -> List[str]:
        """Deprecated helper kept for backward compatibility."""
        return self._extract_tool_names(intermediate_steps)

    async def invoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Asynchronously invoke the agent."""
        if not self.is_initialized:
            await self.initialize()
        return await self._execute_query(query, session_id=session_id, **kwargs)

    async def ainvoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Compatibility alias for frameworks expecting ainvoke."""
        return await self.invoke(query, session_id=session_id, **kwargs)

    async def execute(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Alias for invoke retained for compatibility."""
        return await self.invoke(query, session_id=session_id, **kwargs)

    def invoke_sync(self, query: str, session_id: str = "default") -> Dict[str, Any]:
        """Synchronously invoke the agent."""
        try:
            loop = asyncio.get_running_loop()
            task = asyncio.create_task(self.invoke(query, session_id))
            return asyncio.run_coroutine_threadsafe(task, loop).result()
        except RuntimeError:
            return asyncio.run(self.invoke(query, session_id))

    def get_agent_info(self) -> Dict[str, Any]:
        """Return metadata about the agent."""
        from src.llm.managers import get_llm_info

        provider_name = self._get_provider_name()
        try:
            model_info = get_llm_info(provider_name, self.model)
        except Exception as exc:
            logger.warning("Failed to fetch model info: %s", exc)
            model_info = {}

        temperature = self.temperature
        if self.llm and hasattr(self.llm, "temperature"):
            temperature = getattr(self.llm, "temperature")

        info = {
            "provider": provider_name,
            "model": self.model,
            "temperature": temperature,
            "max_iterations": self.max_iterations,
            "max_execution_time": self.max_execution_time,
            "initialized": self.is_initialized,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory,
            "use_adapters": self._use_adapters,
            **model_info,
        }

        if self.enable_memory and self.chat_memory:
            stats = getattr(self.chat_memory, "get_memory_stats", None)
            if callable(stats):
                info["memory_info"] = stats()

        return info

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the provider identifier (e.g. 'openai')."""
        raise NotImplementedError

    def get_info(self) -> Dict[str, Any]:
        """Compatibility alias for get_agent_info."""
        return self.get_agent_info()

    def get_llm(self) -> Optional[Any]:
        """Return the underlying LLM instance."""
        return self.llm

    def list_tools(self) -> List[str]:
        """Return the names of registered tools."""
        return [tool.name for tool in self.tools] if self.tools else []

    def get_memory_stats(self) -> Optional[Dict[str, Any]]:
        """Retrieve memory statistics if available."""
        if self.enable_memory and self.chat_memory:
            stats = getattr(self.chat_memory, "get_memory_stats", None)
            if callable(stats):
                return stats()
        return None

    def clear_memory(self, session_id: str = "default") -> bool:
        """Clear session memory."""
        if self.enable_memory and self.chat_memory:
            clear_session = getattr(self.chat_memory, "clear_session", None)
            if callable(clear_session):
                return clear_session(session_id)
        return False

    def save_memory(self, session_id: str = "default") -> bool:
        """Persist session memory."""
        if self.enable_memory and self.chat_memory:
            save_session = getattr(self.chat_memory, "save_session", None)
            if callable(save_session):
                return save_session(session_id)
        return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List available memory sessions."""
        if self.enable_memory and self.chat_memory:
            list_sessions_fn = getattr(self.chat_memory, "list_sessions", None)
            if callable(list_sessions_fn):
                return list_sessions_fn()
        return []

    def delete_session(self, session_id: str) -> bool:
        """Delete a memory session."""
        if self.enable_memory and self.chat_memory:
            delete_fn = getattr(self.chat_memory, "delete_session", None)
            if callable(delete_fn):
                return delete_fn(session_id)
        return False

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve information about a specific memory session."""
        if self.enable_memory and self.chat_memory:
            info_fn = getattr(self.chat_memory, "get_session_info", None)
            if callable(info_fn):
                return info_fn(session_id)
        return None
