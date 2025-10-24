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
    ) -> None:
        self.adapter = adapter
        self.runtime = runtime
        self.metadata = metadata or {}
        self.system_prompt: Optional[str] = self.metadata.get("system_prompt")

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
            result = await self.runtime.ainvoke({"messages": messages})
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Deep agent invocation failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "output": f"Deep agent execution failed: {exc}",
                "messages": [],
                "tool_calls": 0,
                "tool_names": [],
                "session_id": session_id,
            }

        output_message = self._extract_output_message(result)
        output_text = ""
        tool_calls = 0
        tool_names: List[str] = []
        if isinstance(output_message, AIMessage):
            output_text = self._message_content_to_text(output_message.content)
            tool_calls = len(output_message.tool_calls or [])
            tool_names = [
                tool_call.get("name")
                for tool_call in (output_message.tool_calls or [])
                if isinstance(tool_call, dict) and tool_call.get("name")
            ]
        elif output_message is not None:
            output_text = self._message_content_to_text(getattr(output_message, "content", output_message))

        return {
            "success": True,
            "output": output_text,
            "messages": result.get("messages", []),
            "tool_calls": tool_calls,
            "tool_names": tool_names,
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

    @staticmethod
    def _message_content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(BaseDeepAgent._message_content_to_text(item) for item in content)
        return str(content)
