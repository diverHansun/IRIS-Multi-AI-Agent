"""Base DeepAgent instance abstraction."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from src.agents.deepagents.adapters.base import BaseDeepAgentAdapter
from src.components.shared.memory.deep_agent_checkpointer import DeepAgentCheckpointer

logger = logging.getLogger(__name__)


class BaseDeepAgent:
    """
    Common functionality shared by DeepAgent instances.

    Implements dual checkpointer architecture:
    - MemorySaver for runtime state restoration (HITL support)
    - SessionStorage (via MemorySyncAdapter) for long-term conversation persistence

    This design follows SOLID principles:
    - SRP: Separates runtime execution state from persistent storage
    - OCP: Allows different checkpointer implementations without modifying agent logic
    """

    def __init__(
        self,
        *,
        adapter: BaseDeepAgentAdapter,
        runtime: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        deep_checkpointer: Optional[DeepAgentCheckpointer] = None,
    ) -> None:
        self.adapter = adapter
        self.runtime = runtime
        self.metadata = metadata or {}
        self.system_prompt: Optional[str] = self.metadata.get("system_prompt")
        self.deep_checkpointer = deep_checkpointer or DeepAgentCheckpointer()
        self.enable_memory = True
        self.checkpoint_namespace = self._compute_checkpoint_namespace()
        self._session_checkpoints: Dict[str, Optional[str]] = {}

        # Runtime checkpointer for HITL interrupt/resume support
        # Uses MemorySaver to preserve complete execution state including ToolMessage and __interrupt__
        self.runtime_checkpointer = getattr(self.deep_checkpointer, "runtime_checkpointer", None)
        if self.runtime_checkpointer is None:
            # Fallback to DeepAgentCheckpointer's internal MemorySaver
            self.runtime_checkpointer = DeepAgentCheckpointer().runtime_checkpointer

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
        base_config = self._build_runtime_config(session_id)
        payload = self.enhance_runtime_input(session_id, payload)
        config = base_config

        logger.debug("Before runtime.ainvoke for session_id=%s", session_id)
        logger.debug("Config: %s", config)
        if hasattr(self.runtime_checkpointer, 'storage'):
            thread_id = config.get("configurable", {}).get("thread_id")
            checkpoint_ns = config.get("configurable", {}).get("checkpoint_ns", "")
            if thread_id and thread_id in self.runtime_checkpointer.storage:
                if checkpoint_ns in self.runtime_checkpointer.storage[thread_id]:
                    existing_keys = list(self.runtime_checkpointer.storage[thread_id][checkpoint_ns].keys())
                    logger.debug("MemorySaver has %d checkpoints", len(existing_keys))
                    logger.debug("Checkpoint IDs: %s", existing_keys)
                    logger.debug("ID types: %s", [type(k).__name__ for k in existing_keys])
                else:
                    logger.debug("No checkpoints for checkpoint_ns='%s'", checkpoint_ns)
            else:
                logger.debug("No checkpoints for thread_id=%s", thread_id)

        try:
            logger.debug("Calling runtime.ainvoke()...")
            result = await self.runtime.ainvoke(payload, config=config)
            logger.debug("runtime.ainvoke() succeeded")
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Deep agent invocation failed: %s", exc, exc_info=True)
            return self._build_error_response(exc, session_id)

        self._persist_runtime_history(session_id, config, result)
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

        return {
            "success": True,
            "output": output_text,
            "messages": messages,
            "tool_calls": tool_calls,
            "tool_names": tool_names,
            "subagent_calls": subagent_calls,
            "session_id": session_id,
        }

    def _compute_checkpoint_namespace(self) -> str:
        """Generate a deterministic namespace for LangGraph checkpoints."""
        provider = getattr(self.adapter, "provider", "unknown") or "unknown"
        function_type = getattr(self.adapter, "function_type", None) or "default"
        provider_key = self._sanitize_namespace_component(str(provider))
        function_key = self._sanitize_namespace_component(str(function_type))
        return f"deep_agent::{provider_key}::{function_key}"

    @staticmethod
    def _sanitize_namespace_component(value: str) -> str:
        """Keep checkpoint namespace components filesystem friendly."""
        lowered = value.lower().strip()
        if not lowered:
            return "default"
        return "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in lowered)

    def get_checkpoint_namespace(self) -> str:
        """Public accessor so orchestrators can ensure configs include namespace."""
        return self.checkpoint_namespace

    def _build_runtime_input(self, query: str) -> Dict[str, Any]:
        return {"messages": [HumanMessage(content=query)]}

    def _build_runtime_config(self, session_id: str) -> Dict[str, Any]:
        """
        Build runtime configuration for LangGraph execution.

        Note: checkpoint_ns is set to empty string for LangGraph MemorySaver compatibility.
        All modes share history using session_id (thread_id) only for cross-provider persistence.
        """
        return {
            "configurable": {
                "thread_id": session_id,
                "checkpoint_ns": "",  # Required by MemorySaver, use empty string for shared history
            }
        }

    def _fetch_conversation_history(self, session_id: str) -> List[BaseMessage]:
        """Retrieve existing conversation history for a session."""
        if not self.enable_memory or not self.deep_checkpointer:
            return []
        try:
            messages = self.deep_checkpointer.storage.load_session(session_id) or []
            if isinstance(messages, list):
                return list(messages)
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Failed to fetch conversation history for session %s: %s", session_id, exc)
        return []

    def enhance_runtime_input(self, session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Merge stored conversation history into runtime input payload."""
        if not self.deep_checkpointer:
            return payload
        try:
            # Leverage DeepAgentCheckpointer history injection (includes max_history trimming)
            return self.deep_checkpointer.enhance_runtime_input(
                session_id,
                payload["messages"][-1].content if isinstance(payload.get("messages", [None])[-1], HumanMessage) else "",
                max_history=10,
            )
        except Exception:
            # Fallback to simple merge on failure
            if not isinstance(payload, dict):
                return payload
            pending_messages = payload.get("messages")
            if not isinstance(pending_messages, list):
                return payload
            history = self._fetch_conversation_history(session_id)
            if not history:
                return payload
            merged_payload = dict(payload)
            merged_payload["messages"] = history + pending_messages
            return merged_payload

    def _persist_runtime_history(
        self,
        session_id: str,
        runtime_config: Dict[str, Any],
        agent_state: Optional[Dict[str, Any]],
    ) -> None:
        if not self.enable_memory:
            return

        try:
            self.deep_checkpointer.persist_from_runtime(
                session_id,
                self.runtime_checkpointer,
                runtime_config,
                agent_state,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Failed to persist runtime history for session %s: %s", session_id, exc)

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
        """
        DEPRECATED: This method is no longer used and will be removed in a future version.

        Memory persistence is now handled exclusively by MemorySyncAdapter.persist_from_runtime()
        to avoid duplicate writes and maintain single responsibility principle (SRP).

        The conversation history is automatically persisted through:
        - conversation.py: persist_from_runtime() after streaming completes
        - memory_sync.py: MemorySyncAdapter syncs runtime to storage checkpointer

        This method is kept for backward compatibility only.
        """
        logger.warning(
            "_record_conversation() is deprecated and will be removed. "
            "Use MemorySyncAdapter.persist_from_runtime() instead."
        )

    @staticmethod
    def _message_content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "\n".join(BaseDeepAgent._message_content_to_text(item) for item in content)
        return str(content)
