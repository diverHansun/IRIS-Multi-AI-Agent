"""Runtime builder utilities for DeepAgents."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware, InterruptOnConfig, TodoListMiddleware
from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain.agents.middleware.types import AgentMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import Checkpointer

from .runtime_middlewares import (
    JsonArgsParserMiddleware,
    PatchToolCallsMiddleware,
    ExecutionTimeoutMiddleware,
)
from .runtime_middlewares.subagents import (
    SubAgent,
    CompiledSubAgent,
    SubAgentMiddleware,
)
from .runtime_middlewares.virtual_filesystem import VirtualFilesystemMiddleware


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
    recursion_limit: int | None = None,
    step_timeout: float | None = None,
    stream_mode: str | None = None,
    max_execution_time: float | None = None,
    filesystem_middleware: Any | None = None,
    filesystem_middlewares: Sequence[Any] | None = None,
    shell_middleware: Any | None = None,
    skills_middleware: Any | None = None,
) -> CompiledStateGraph:
    """Create a configured deep agent runtime graph."""

    if isinstance(model, str) and model_settings:
        model = init_chat_model(model, **model_settings)

    middleware_config = middleware_config or {}
    filesystem_cfg = middleware_config.get("filesystem", {}) or {}
    subagents_cfg = middleware_config.get("subagents", {})

    # Coerce provided filesystem middlewares into a list while supporting legacy parameter.
    provided_filesystem_middlewares: List[AgentMiddleware] = []
    if filesystem_middlewares:
        provided_filesystem_middlewares.extend(filesystem_middlewares)
    elif filesystem_middleware is not None:
        provided_filesystem_middlewares.append(filesystem_middleware)
    else:
        # Backwards compatibility: create virtual filesystem middleware if enabled.
        virtual_cfg = filesystem_cfg.get("virtual") if isinstance(filesystem_cfg, dict) else None
        if virtual_cfg is None and isinstance(filesystem_cfg, dict):
            virtual_cfg = filesystem_cfg
        if isinstance(virtual_cfg, dict) and virtual_cfg.get("enabled", True):
            from .runtime_middlewares.virtual_filesystem import VirtualFilesystemMiddleware

            provided_filesystem_middlewares.append(
                VirtualFilesystemMiddleware(
                    long_term_memory=use_long_term_memory or virtual_cfg.get("long_term_memory", False),
                    tool_token_limit_before_evict=virtual_cfg.get("tool_token_limit_before_evict"),
                )
            )

    # Build subagent middleware list (SOLID: SRP - conditional middleware inclusion)
    default_subagent_middleware: List[AgentMiddleware] = [
        JsonArgsParserMiddleware(enable_logging=True),
        TodoListMiddleware(),
    ]
    
    # Add filesystem middleware for subagents if enabled
    default_subagent_middleware.extend(provided_filesystem_middlewares)
    
    default_subagent_middleware.extend([
        SummarizationMiddleware(
            model=model,
            max_tokens_before_summary=170000,
            messages_to_keep=6,
        ),
        PatchToolCallsMiddleware(),
    ])

    subagent_middleware = SubAgentMiddleware(
        default_model=model,
        default_tools=tools or [],
        subagents=subagents or [],
        default_middleware=default_subagent_middleware,
        default_interrupt_on=interrupt_on,
        general_purpose_agent=True,
        task_description=subagents_cfg.get("task_description"),
    )

    # Get task tool from SubAgentMiddleware and add to tools list
    task_tool = subagent_middleware.get_task_tool()
    if task_tool:
        tools = list(tools) if tools else []
        tools.append(task_tool)

    # Build main agent middleware list (SOLID: SRP - conditional middleware inclusion)
    deepagent_middleware: List[AgentMiddleware] = [
        JsonArgsParserMiddleware(enable_logging=True),
        TodoListMiddleware(),
    ]

    # Add skills middleware if provided (after TodoList, before filesystem)
    if skills_middleware is not None:
        deepagent_middleware.append(skills_middleware)

    # Add filesystem middleware if enabled
    deepagent_middleware.extend(provided_filesystem_middlewares)

    # Add shell middleware if provided (injected by factory)
    if shell_middleware is not None:
        deepagent_middleware.append(shell_middleware)

    # Add subagent middleware
    deepagent_middleware.append(subagent_middleware)
    deepagent_middleware.extend([
        SummarizationMiddleware(
            model=model,
            max_tokens_before_summary=170000,
            messages_to_keep=6,
        ),
        PatchToolCallsMiddleware(),
    ])

    # Add execution timeout middleware if max_execution_time is specified
    if max_execution_time is not None and max_execution_time > 0:
        deepagent_middleware.insert(0, ExecutionTimeoutMiddleware(max_execution_time=max_execution_time))

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

    if step_timeout:
        agent_graph.step_timeout = step_timeout
    if stream_mode:
        agent_graph.stream_mode = stream_mode

    limit = recursion_limit or 1000
    return agent_graph.with_config({"recursion_limit": limit})
