"""Runtime builder utilities for DeepAgents."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, TodoListMiddleware
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain.chat_models import init_chat_model
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer

from .runtime_middlewares import (
    CompiledSubAgent,
    FilesystemMiddleware,
    PatchToolCallsMiddleware,
    SubAgent,
    SubAgentMiddleware,
)


def create_deep_agent_runtime(
    *,
    model: str | BaseChatModel | None,
    system_prompt: str | None,
    tools: Sequence[BaseTool | Any] | None = None,
    model_settings: Dict[str, Any] | None = None,
    middleware_config: Dict[str, Any] | None = None,
    subagents: List[SubAgent | CompiledSubAgent] | None = None,
    extra_middleware: Sequence[AgentMiddleware] | None = None,
    use_long_term_memory: bool = False,
    interrupt_on: Dict[str, bool | InterruptOnConfig] | None = None,
    checkpointer: Checkpointer | None = None,
    store: BaseStore | None = None,
    cache: BaseCache | None = None,
    name: str | None = None,
    debug: bool = False,
) -> CompiledStateGraph:
    """Create a configured deep agent runtime graph."""

    if isinstance(model, str) and model_settings:
        model = init_chat_model(model, **model_settings)

    middleware_config = middleware_config or {}
    filesystem_cfg = middleware_config.get("filesystem", {})
    subagents_cfg = middleware_config.get("subagents", {})

    filesystem_middleware = FilesystemMiddleware(
        long_term_memory=use_long_term_memory or filesystem_cfg.get("long_term_memory", False),
        tool_token_limit_before_evict=filesystem_cfg.get("tool_token_limit_before_evict"),
    )

    default_subagent_middleware: List[AgentMiddleware] = [
        TodoListMiddleware(),
        FilesystemMiddleware(
            long_term_memory=use_long_term_memory or filesystem_cfg.get("long_term_memory", False),
            tool_token_limit_before_evict=filesystem_cfg.get("tool_token_limit_before_evict"),
        ),
        SummarizationMiddleware(
            model=model,
            max_tokens_before_summary=170000,
            messages_to_keep=6,
        ),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
        PatchToolCallsMiddleware(),
    ]

    subagent_middleware = SubAgentMiddleware(
        default_model=model,
        default_tools=tools or [],
        subagents=subagents or [],
        default_middleware=default_subagent_middleware,
        default_interrupt_on=interrupt_on,
        general_purpose_agent=True,
        task_description=subagents_cfg.get("task_description"),
    )

    deepagent_middleware: List[AgentMiddleware] = [
        TodoListMiddleware(),
        filesystem_middleware,
        subagent_middleware,
        SummarizationMiddleware(
            model=model,
            max_tokens_before_summary=170000,
            messages_to_keep=6,
        ),
        AnthropicPromptCachingMiddleware(unsupported_model_behavior="ignore"),
        PatchToolCallsMiddleware(),
    ]

    if interrupt_on is not None:
        deepagent_middleware.append(HumanInTheLoopMiddleware(interrupt_on=interrupt_on))

    if extra_middleware:
        deepagent_middleware.extend(extra_middleware)

    agent_graph = create_agent(
        model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=deepagent_middleware,
        checkpointer=checkpointer,
        store=store,
        cache=cache,
        debug=debug,
        name=name,
    )

    return agent_graph.with_config({"recursion_limit": 1000})
