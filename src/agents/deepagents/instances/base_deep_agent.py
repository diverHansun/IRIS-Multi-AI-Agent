"""Base DeepAgent instance abstraction."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

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

        payload = self._build_runtime_input(query)
        config = self._build_runtime_config(session_id)

        try:
            result = await self.runtime.ainvoke(payload, config=config)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Deep agent invocation failed: %s", exc, exc_info=True)
            return self._build_error_response(exc, session_id)

        return self._prepare_success_result(query, session_id, result)

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

    def prepare_stream_result(
        self,
        query: str,
        session_id: str,
        agent_state: Dict[str, Any],
        *,
        tool_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Normalise the final streamed state into the legacy response format."""
        messages = agent_state.get("messages", [])
        output_text, tool_calls, tool_names, subagent_calls = self._analyse_messages(messages)

        if tool_stats:
            tool_calls = tool_stats.get("tool_calls", tool_calls)
            tool_names = tool_stats.get("tool_names", tool_names)
            subagent_calls = tool_stats.get("subagent_calls", subagent_calls)

        if self.enable_memory and self.global_memory_manager and output_text:
            self._record_conversation(session_id, query, output_text)

        return {
            "success": True,
            "output": output_text,
            "messages": messages,
            "tool_calls": tool_calls,
            "tool_names": tool_names,
            "subagent_calls": subagent_calls,
            "session_id": session_id,
        }

    def _build_runtime_input(self, query: str) -> Dict[str, Any]:
        return {"messages": [HumanMessage(content=query)]}

    def _build_runtime_config(self, session_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": session_id}}

    def create_runtime_input(self, query: str) -> Dict[str, Any]:
        """Public helper used by streaming orchestrators to build runtime input."""
        return self._build_runtime_input(query)

    def create_runtime_config(self, session_id: str) -> Dict[str, Any]:
        """Public helper used by streaming orchestrators to build runtime config."""
        return self._build_runtime_config(session_id)

    def _prepare_success_result(
        self,
        query: str,
        session_id: str,
        runtime_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        messages = runtime_result.get("messages", [])
        output_text, tool_calls, tool_names, subagent_calls = self._analyse_messages(messages)

        if self.enable_memory and self.global_memory_manager and output_text:
            self._record_conversation(session_id, query, output_text)

        return {
            "success": True,
            "output": output_text,
            "messages": messages,
            "tool_calls": tool_calls,
            "tool_names": tool_names,
            "subagent_calls": subagent_calls,
            "session_id": session_id,
        }

    @staticmethod
    def _build_error_response(exc: Exception, session_id: str) -> Dict[str, Any]:
        return {
            "success": False,
            "output": f"Deep agent execution failed: {exc}",
            "messages": [],
            "tool_calls": 0,
            "tool_names": [],
            "subagent_calls": [],
            "session_id": session_id,
        }

    def _analyse_messages(
        self,
        messages: List[BaseMessage],
    ) -> Tuple[str, int, List[str], List[Dict[str, Any]]]:
        output_message = self._extract_output_message(messages)
        output_text = self._message_to_text(output_message)
        tool_calls, tool_names, subagent_calls = self._collect_tool_metadata(messages)
        return output_text, tool_calls, tool_names, subagent_calls

    def _collect_tool_metadata(
        self,
        messages: List[BaseMessage],
    ) -> Tuple[int, List[str], List[Dict[str, Any]]]:
        tool_calls = 0
        tool_names: List[str] = []
        subagent_calls: List[Dict[str, Any]] = []
        tool_results: Dict[str, Dict[str, Any]] = {}

        for message in messages:
            if isinstance(message, ToolMessage) and message.tool_call_id and message.name == "task":
                tool_results[message.tool_call_id] = {
                    "content": message.content,
                    "status": getattr(message, "status", "success"),
                }

        for message in messages:
            if isinstance(message, AIMessage) and message.tool_calls:
                message_tool_calls = message.tool_calls or []
                tool_calls += len(message_tool_calls)
                for call in message_tool_calls:
                    if not isinstance(call, dict):
                        continue
                    name = call.get("name")
                    if name:
                        if name not in tool_names:
                            tool_names.append(name)
                        if name == "task":
                            subagent_calls.append(self._build_subagent_call(call, tool_results))

        return tool_calls, tool_names, [call for call in subagent_calls if call]

    @staticmethod
    def _build_subagent_call(
        call: Dict[str, Any],
        tool_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        args = call.get("args", {}) if isinstance(call, dict) else {}
        tool_call_id = call.get("id", "")
        task_desc = args.get("description", "")
        result_info = tool_results.get(tool_call_id, {})
        result_content = result_info.get("content", "")
        result_status = result_info.get("status", "unknown")

        return {
            "subagent_type": args.get("subagent_type", "unknown"),
            "description": task_desc[:100] + "..." if len(task_desc) > 100 else task_desc,
            "call_id": tool_call_id,
            "result": result_content[:150] + "..." if len(result_content) > 150 else result_content,
            "status": result_status,
        }

    @staticmethod
    def _extract_output_message(messages: List[BaseMessage]) -> Optional[BaseMessage]:
        if not messages:
            return None
        return messages[-1]

    @staticmethod
    def _message_to_text(message: Optional[BaseMessage]) -> str:
        if message is None:
            return ""
        if isinstance(message, AIMessage):
            return BaseDeepAgent._message_content_to_text(message.content)
        return BaseDeepAgent._message_content_to_text(getattr(message, "content", ""))

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
