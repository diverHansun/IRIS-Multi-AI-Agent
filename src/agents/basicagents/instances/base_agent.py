"""
Refactored BaseAgent class.

Pure executor that receives fully initialized components.
No initialization logic, no hardcoded values - configuration driven only.

Design Principles:
- KISS: Simple and straightforward message parsing
- SRP: Each method has a single, well-defined responsibility
- DRY: Reusable extraction methods for common patterns
- YAGNI: Only implement features that are currently needed
"""

import logging
import time
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
from src.components.shared.memory.session_context import SessionContext

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
            - intermediate_steps: List of tool calls (backward compatibility)
            - tool_calls: Number of tool calls
            - tool_names: List of tool names used
            - reasoning_steps: List of reasoning steps for detailed display
            - execution_time: Execution time in seconds
            - should_show_details: Whether to show detailed steps
            - success: Whether execution succeeded
            - session_id: Session ID (if memory enabled)
            - memory_enabled: Whether memory is enabled
            - error: Error message (if failed)

        Raises:
            AgentExecutionError: If execution fails
        """
        if not self.graph:
            raise AgentExecutionError("Agent graph is not available")

        start_time = time.time()

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

            # Calculate execution time
            execution_time = time.time() - start_time

            # Parse and format result
            parsed = self._parse_graph_output(result)

            # Determine if detailed steps should be shown
            should_show_details = self._should_show_details(parsed, execution_time)

            # Add metadata
            parsed.update({
                "success": True,
                "execution_time": execution_time,
                "should_show_details": should_show_details,
                "session_id": session_id if self.enable_memory else None,
                "memory_enabled": self.enable_memory,
            })

            return parsed

        except Exception as exc:
            execution_time = time.time() - start_time
            logger.error(f"Query execution failed: {exc}", exc_info=True)

            # Return error result with metadata
            return {
                "success": False,
                "error": str(exc),
                "output": "",
                "tool_calls": 0,
                "tool_names": [],
                "reasoning_steps": [],
                "intermediate_steps": [],
                "execution_time": execution_time,
                "should_show_details": False,
                "session_id": session_id if self.enable_memory else None,
                "memory_enabled": self.enable_memory,
            }

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

        session_ctx = self._create_session_context(session_id)
        return session_ctx.build_runtime_config(extra_config)

    def _parse_graph_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse graph output into standardized format.

        Follows SRP principle: orchestrates extraction methods without
        implementing extraction logic itself.

        Args:
            result: Raw graph execution result

        Returns:
            Parsed result dictionary with all required fields
        """
        messages: List[BaseMessage] = result.get("messages", [])

        # Extract final answer
        output = self._extract_final_output(messages)

        # Extract tool statistics
        tool_stats = self._extract_tool_stats(messages)

        # Extract reasoning steps for detailed display
        reasoning_steps = self._extract_reasoning_steps(messages)

        # Extract intermediate steps for backward compatibility
        intermediate_steps = self._extract_intermediate_steps(messages)

        logger.debug(
            f"Parsed output: {len(messages)} messages, "
            f"{tool_stats['tool_calls']} tool calls, "
            f"{len(reasoning_steps)} reasoning steps"
        )

        return {
            "output": output,
            "tool_calls": tool_stats["tool_calls"],
            "tool_names": tool_stats["tool_names"],
            "reasoning_steps": reasoning_steps,
            "intermediate_steps": intermediate_steps,
        }

    def _extract_final_output(self, messages: List[BaseMessage]) -> str:
        """
        Extract final AI response from messages.

        Implements proper ReAct pattern detection to skip intermediate steps
        and extract only the final answer.

        Detection rules:
        1. Skip messages with tool_calls (intermediate tool invocation)
        2. Skip ReAct intermediate steps (has 'action' but no 'final_answer')
        3. Skip thinking-only steps (has 'thought' but no 'final_answer')
        4. Extract final_answer from dict or return plain text

        Args:
            messages: List of messages from graph execution

        Returns:
            Final output string (cleaned and normalized)
        """
        for message in reversed(messages):
            if not isinstance(message, AIMessage):
                continue

            # Skip intermediate tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                continue

            content = message.content

            # Handle string that looks like JSON
            if isinstance(content, str) and content.strip().startswith("{"):
                try:
                    import json
                    parsed_content = json.loads(content)
                    if isinstance(parsed_content, dict):
                        # Check if this is a ReAct intermediate step
                        if "action" in parsed_content and "final_answer" not in parsed_content:
                            continue
                        if "thought" in parsed_content and "final_answer" not in parsed_content:
                            continue
                        # Extract final answer if present
                        if "final_answer" in parsed_content:
                            return self._normalize_message_content(parsed_content["final_answer"])
                except json.JSONDecodeError:
                    # Fall through to handle as plain text
                    pass

            # Handle dictionary content (ReAct format)
            if isinstance(content, dict):
                # Skip ReAct intermediate steps
                if "action" in content and "final_answer" not in content:
                    continue
                if "thought" in content and "final_answer" not in content:
                    continue

                # Extract final answer
                if "final_answer" in content:
                    return self._normalize_message_content(content["final_answer"])

                # Fallback: normalize entire dict
                return self._normalize_message_content(content)

            # Handle plain text or list content
            return self._normalize_message_content(content)

        logger.warning("No final output found in messages")
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

    def _extract_tool_stats(self, messages: List[BaseMessage]) -> Dict[str, Any]:
        """
        Extract tool call statistics from messages.

        Follows DRY principle: reuses intermediate_steps extraction logic.

        Args:
            messages: List of messages from graph execution

        Returns:
            Dictionary with tool_calls count and tool_names list
        """
        tool_calls = 0
        tool_names_set = set()

        for message in messages:
            if isinstance(message, AIMessage):
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls += len(message.tool_calls)
                    for tool_call in message.tool_calls:
                        tool_name = tool_call.get("name", "unknown")
                        tool_names_set.add(tool_name)

        return {
            "tool_calls": tool_calls,
            "tool_names": sorted(list(tool_names_set)),
        }

    def _extract_reasoning_steps(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """
        Extract reasoning steps for detailed display.

        Captures tool invocations and their timing (if available).
        Follows KISS principle: simple structure for display formatting.

        Format (simple version):
        [
            {"step": 1, "description": "Tool: web_search"},
            {"step": 2, "description": "Tool: read_file"},
        ]

        Args:
            messages: List of messages from graph execution

        Returns:
            List of reasoning step dictionaries
        """
        steps = []
        step_number = 0

        for message in messages:
            if isinstance(message, AIMessage):
                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        step_number += 1
                        tool_name = tool_call.get("name", "unknown")

                        # Format: simple tool name only (no parameters for BasicAgent)
                        steps.append({
                            "step": step_number,
                            "description": f"Tool: {tool_name}",
                        })

        return steps

    def _should_show_details(self, parsed: Dict[str, Any], execution_time: float) -> bool:
        """
        Determine if detailed steps should be displayed.

        Implements hybrid mode (intelligent switching) based on:
        - Tool call count > 2
        - Reasoning steps > 3
        - Execution time > 30 seconds

        Follows YAGNI principle: simple heuristics without over-engineering.

        Args:
            parsed: Parsed output dictionary
            execution_time: Execution time in seconds

        Returns:
            True if detailed steps should be shown, False otherwise
        """
        tool_calls = parsed.get("tool_calls", 0)
        reasoning_steps = len(parsed.get("reasoning_steps", []))

        should_show = (
            tool_calls > 2 or
            reasoning_steps > 3 or
            execution_time > 30.0
        )

        logger.debug(
            f"Display mode decision: tool_calls={tool_calls}, "
            f"reasoning_steps={reasoning_steps}, execution_time={execution_time:.1f}s "
            f"-> show_details={should_show}"
        )

        return should_show

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
            
        if isinstance(content, dict):
            # Handle dict content: check for common keys like final_answer, output, text, content
            # Priority order: final_answer > output > answer > text > content
            if "final_answer" in content:
                # Recursively normalize in case it's also a dict/list
                return self._normalize_message_content(content["final_answer"])
            if "output" in content:
                return self._normalize_message_content(content["output"])
            if "answer" in content:
                return self._normalize_message_content(content["answer"])
            if "text" in content:
                return self._normalize_message_content(content["text"])
            if "content" in content:
                return self._normalize_message_content(content["content"])
            
            # If dict doesn't have recognized keys, log warning and convert to string
            logger.warning(f"Unknown dict format in message content: {list(content.keys())}")
            return str(content)
            
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    # Try to extract meaningful text from dict items
                    text = (item.get("text") or 
                           item.get("content") or 
                           item.get("final_answer") or
                           str(item))
                    parts.append(text)
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

    def _create_session_context(self, session_id: str) -> SessionContext:
        return SessionContext(
            session_id=session_id,
            agent_type="basic",
            provider=self.provider,
            function_type=self.config.agent_params.get("agent_type", "default"),
        )

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
