"""
Refactored BaseAgent class.

Pure executor that receives fully initialized components.
No initialization logic, no hardcoded values - configuration driven only.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.agents import AgentAction
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from src.agents.basicagents.config import AgentConfig
from src.agents.basicagents.exceptions import AgentExecutionError
from src.components.shared.memory.unified_checkpointer import UnifiedCheckpointer

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Base class for all agents.

    Pure executor that receives fully initialized components from Adapter.
    All dependencies are injected via constructor - no lazy initialization.

    Responsibilities:
    - Execute queries using the provided graph
    - Parse and format results
    - Provide agent information

    No responsibilities:
    - Configuration management (handled by AgentConfig)
    - Component creation (handled by Adapter)
    - Initialization logic (everything ready on construction)
    """

    def __init__(
        self,
        provider: str,
        model: str,
        llm: BaseChatModel,
        graph: CompiledStateGraph,
        tools: List[BaseTool],
        checkpointer: Optional[UnifiedCheckpointer],
        config: AgentConfig,
    ):
        """
        Initialize agent with fully initialized components.

        All parameters are required (except checkpointer which can be None).
        Agent is ready to use immediately after construction.

        Args:
            provider: Provider name (e.g., 'zhipu', 'openai')
            model: Model name (e.g., 'glm-4.5', 'gpt-4o')
            llm: Initialized chat model instance
            graph: Compiled state graph (ready to execute)
            tools: List of initialized tools
            checkpointer: Unified checkpointer (None if memory disabled)
            config: Agent configuration object
        """
        self.provider = provider
        self.model = model
        self.llm = llm
        self.graph = graph
        self.tools = tools
        self.checkpointer = checkpointer
        self.config = config

        # Extract commonly used parameters from config (for convenience)
        self.temperature = config.llm_params.get("temperature")
        self.max_iterations = config.agent_params["max_iterations"]
        self.max_execution_time = config.agent_params.get("max_execution_time")
        self.enable_memory = config.agent_params["memory_enabled"]

        logger.info(
            f"{self.__class__.__name__} initialized: {provider}/{model} "
            f"(temp={self.temperature}, max_iter={self.max_iterations}, "
            f"memory={self.enable_memory})"
        )

    async def invoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute agent query.

        Args:
            query: User query string
            session_id: Session identifier for memory (default: "default")
            **kwargs: Additional parameters

        Returns:
            Dictionary with execution results:
            - output: Final agent response
            - intermediate_steps: List of tool calls
            - tool_calls: Number of tool calls
            - tool_names: List of tool names used
            - success: Whether execution succeeded
            - session_id: Session ID (if memory enabled)
            - memory_enabled: Whether memory is enabled

        Raises:
            AgentExecutionError: If execution fails
        """
        if not self.graph:
            raise AgentExecutionError("Agent graph is not available")

        try:
            # Prepare graph input
            graph_input = self._prepare_graph_input(query)

            # Prepare run configuration
            run_config = self._build_graph_config(session_id)

            # Execute graph
            if run_config:
                result = await self.graph.ainvoke(graph_input, config=run_config)
            else:
                result = await self.graph.ainvoke(graph_input)

            # Parse and format result
            parsed = self._parse_graph_output(result)
            parsed.update({
                "success": True,
                "session_id": session_id if self.enable_memory else None,
                "memory_enabled": self.enable_memory,
            })

            return parsed

        except Exception as exc:
            logger.error(f"Query execution failed: {exc}", exc_info=True)
            raise AgentExecutionError(f"Query execution failed: {exc}") from exc

    async def ainvoke(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Async invoke alias.

        Compatible with frameworks expecting ainvoke method.

        Args:
            query: User query string
            session_id: Session identifier
            **kwargs: Additional parameters

        Returns:
            Execution results dictionary
        """
        return await self.invoke(query, session_id=session_id, **kwargs)

    async def execute(
        self,
        query: str,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute alias for backward compatibility.

        Args:
            query: User query string
            session_id: Session identifier
            **kwargs: Additional parameters

        Returns:
            Execution results dictionary
        """
        return await self.invoke(query, session_id=session_id, **kwargs)

    def _prepare_graph_input(self, query: str) -> Dict[str, List[BaseMessage]]:
        """
        Convert query string to graph input format.

        Args:
            query: User query string

        Returns:
            Dictionary with messages list
        """
        return {"messages": [HumanMessage(content=query)]}

    def _build_graph_config(
        self,
        session_id: str,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Build graph run configuration.

        Includes checkpointer configuration if memory is enabled.

        Args:
            session_id: Session identifier
            extra_config: Additional configuration to merge

        Returns:
            Run configuration dictionary or None
        """
        if not self.enable_memory or not self.checkpointer:
            return extra_config

        # Build base config with thread_id for checkpointer
        base_config = {"configurable": {"thread_id": session_id}}

        if extra_config is None:
            return base_config

        # Merge configurations
        merged = dict(extra_config)
        base_configurable = base_config.get("configurable", {})
        extra_configurable = extra_config.get("configurable", {})
        merged["configurable"] = {**base_configurable, **extra_configurable}

        return merged

    def _parse_graph_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse graph output into standardized format.

        Args:
            result: Raw graph execution result

        Returns:
            Parsed result dictionary
        """
        messages: List[BaseMessage] = result.get("messages", [])
        output = self._extract_final_output(messages)
        intermediate_steps = self._extract_intermediate_steps(messages)
        tool_names = self._extract_tool_names(intermediate_steps)

        return {
            "output": output,
            "intermediate_steps": intermediate_steps,
            "tool_calls": len(intermediate_steps),
            "tool_names": tool_names,
        }

    def _extract_final_output(self, messages: List[BaseMessage]) -> str:
        """
        Extract final AI response from messages.

        Args:
            messages: List of messages from graph

        Returns:
            Final output string
        """
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                return self._normalize_message_content(message.content)
        return ""

    def _extract_intermediate_steps(
        self,
        messages: List[BaseMessage],
    ) -> List[Any]:
        """
        Extract intermediate tool call steps.

        Args:
            messages: List of messages from graph

        Returns:
            List of (AgentAction, observation) tuples
        """
        # Map tool_call_id to ToolMessage
        tool_messages: Dict[str, ToolMessage] = {}
        for message in messages:
            if isinstance(message, ToolMessage) and message.tool_call_id:
                tool_messages[message.tool_call_id] = message

        steps: List[Any] = []

        # Extract tool calls from AIMessages
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
        """
        Extract unique tool names from intermediate steps.

        Args:
            intermediate_steps: List of intermediate steps

        Returns:
            List of unique tool names
        """
        names: List[str] = []
        for step in intermediate_steps:
            if isinstance(step, tuple) and step and isinstance(step[0], AgentAction):
                tool_name = step[0].tool
                if tool_name not in names:
                    names.append(tool_name)
        return names

    def _normalize_message_content(self, content: Any) -> str:
        """
        Normalize message content to plain string.

        Args:
            content: Message content (string, list, or dict)

        Returns:
            Normalized string
        """
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

    def get_agent_info(self) -> Dict[str, Any]:
        """
        Get agent information.

        Returns:
            Dictionary with agent metadata
        """
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "max_iterations": self.max_iterations,
            "max_execution_time": self.max_execution_time,
            "tool_count": len(self.tools),
            "tools": [tool.name for tool in self.tools] if self.tools else [],
            "memory_enabled": self.enable_memory,
            "agent_type": self.config.agent_params.get("agent_type", "react"),
        }

    def get_info(self) -> Dict[str, Any]:
        """
        Alias for get_agent_info for backward compatibility.

        Returns:
            Agent information dictionary
        """
        return self.get_agent_info()

    def get_llm(self) -> Optional[BaseChatModel]:
        """
        Get underlying LLM instance.

        Returns:
            LLM instance
        """
        return self.llm

    def list_tools(self) -> List[str]:
        """
        List tool names.

        Returns:
            List of tool names
        """
        return [tool.name for tool in self.tools] if self.tools else []

    @abstractmethod
    def _get_provider_name(self) -> str:
        """
        Get provider identifier.

        Must be implemented by subclasses.

        Returns:
            Provider name string
        """
        pass
