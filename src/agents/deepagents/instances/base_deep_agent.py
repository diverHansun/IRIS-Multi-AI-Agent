"""Base DeepAgent instance abstraction."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter

logger = logging.getLogger(__name__)


class BaseDeepAgent:
    """Common functionality shared by DeepAgent instances."""

    def __init__(
        self,
        *,
        adapter: BaseDeepAgentAdapter,
        runtime: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        global_memory_manager: Optional[Any] = None,
    ) -> None:
        self.adapter = adapter
        self.runtime = runtime
        self.metadata = metadata or {}
        self.system_prompt: Optional[str] = self.metadata.get("system_prompt")
        self.global_memory_manager = global_memory_manager
        self.enable_memory = global_memory_manager is not None

    @property
    def function_type(self) -> str:
        """Return the function type of the agent."""
        return self.adapter.function_type

    def get_info(self) -> Dict[str, Any]:
        """Return descriptive information about the agent."""
        info = {
            "provider": self.adapter.provider,
            "model": self.adapter.model,
            "function_type": self.function_type,
            "system_prompt": self.system_prompt,
        }
        info.update(self.metadata)
        info.update(self.adapter.get_capabilities())
        return info

    async def invoke(
        self,
        query: str,
        *,
        session_id: str = "default",
        **_: Any,
    ) -> Dict[str, Any]:
        """Invoke the underlying agent runtime and normalise the response."""
        if self.runtime is None:
            raise RuntimeError("Deep agent runtime has not been initialized")

        messages = [HumanMessage(content=query)]

        try:
            # Build config with session_id for memory persistence
            config = {"configurable": {"thread_id": session_id}} if self.enable_memory else None

            if config:
                result = await self.runtime.ainvoke({"messages": messages}, config=config)
            else:
                result = await self.runtime.ainvoke({"messages": messages})
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Deep agent invocation failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "output": f"Deep agent execution failed: {exc}",
                "messages": [],
                "tool_calls": 0,
                "tool_names": [],
                "subagent_calls": [],
                "session_id": session_id,
            }

        output_message = self._extract_output_message(result)
        output_text = ""

        # Extract tool calls and names from ALL messages, not just the last one
        tool_calls = 0
        tool_names: List[str] = []
        subagent_calls: List[Dict[str, str]] = []  # Track subagent delegations
        messages = result.get("messages", [])
        for message in messages:
            if isinstance(message, AIMessage) and hasattr(message, "tool_calls"):
                message_tool_calls = message.tool_calls or []
                tool_calls += len(message_tool_calls)
                for tool_call in message_tool_calls:
                    if isinstance(tool_call, dict):
                        name = tool_call.get("name")
                        if name and name not in tool_names:
                            tool_names.append(name)

                        # Check if this is a task tool (subagent delegation)
                        if name == "task":
                            args = tool_call.get("args", {})
                            subagent_type = args.get("subagent_type", "unknown")
                            task_desc = args.get("description", "")
                            subagent_calls.append({
                                "subagent_type": subagent_type,
                                "description": task_desc[:100] + "..." if len(task_desc) > 100 else task_desc
                            })

        # Extract output text
        if isinstance(output_message, AIMessage):
            output_text = self._message_content_to_text(output_message.content)
        elif output_message is not None:
            output_text = self._message_content_to_text(getattr(output_message, "content", output_message))

        # Record conversation in global memory if available
        if self.enable_memory and self.global_memory_manager and output_text:
            self._record_conversation(session_id, query, output_text)

        return {
            "success": True,
            "output": output_text,
            "messages": result.get("messages", []),
            "tool_calls": tool_calls,
            "tool_names": tool_names,
            "subagent_calls": subagent_calls,  # Include subagent delegation info
            "session_id": session_id,
        }

    async def ainvoke(
        self,
        query: str,
        *,
        session_id: str = "default",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Compatibility alias mirroring BaseAgent interface."""
        return await self.invoke(query, session_id=session_id, **kwargs)

    def set_runtime(self, runtime: Any) -> None:
        """Set the runtime used by this agent."""
        self.runtime = runtime

    def _extract_output_message(self, runtime_result: Dict[str, Any]) -> Optional[BaseMessage]:
        messages = runtime_result.get("messages", [])
        if not messages:
            return None
        return messages[-1]

    def _record_conversation(self, session_id: str, query: str, output: str) -> None:
        """Store the conversation turn in the global memory manager."""
        if not self.enable_memory or not self.global_memory_manager:
            return

        add_conversation = getattr(self.global_memory_manager, "add_conversation", None)
        if callable(add_conversation):
            try:
                add_conversation(session_id, query, output, current_llm_info=None)
            except Exception as exc:
                logger.warning("Failed to record conversation: %s", exc)

        save_session = getattr(self.global_memory_manager, "save_session", None)
        if callable(save_session):
            try:
                save_session(session_id)
            except Exception as exc:
                logger.warning("Failed to save session: %s", exc)

    @staticmethod
    def _message_content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(BaseDeepAgent._message_content_to_text(item) for item in content)
        return str(content)
