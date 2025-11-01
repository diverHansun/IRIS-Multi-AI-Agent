"""Real filesystem middleware for DeepAgents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.runtime import Runtime

from .config import RealFilesystemOptions, build_real_filesystem_options
from .tools import RealFilesystemToolFactory

REAL_FILESYSTEM_PROMPT = """You can inspect the host project using real filesystem tools.

Key rules:
- Access is strictly read-only; never attempt to modify host files.
- Only paths within the configured allowlist and allowed extensions are reachable.
- Hidden files remain hidden unless explicitly requested.
- Prefer listing files before reading, and use pagination for large files.

Available tools:
- list_real_files(directory_path=None, recursive=False, include_hidden=False)
- read_real_file(file_path, offset=0, limit=2000, encoding="utf-8")"""


class RealFilesystemMiddleware(AgentMiddleware):
    """Expose read-only access to the host filesystem under strict safety controls."""

    def __init__(
        self,
        *,
        config: Dict[str, Any] | None = None,
        tool_descriptions: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__()
        self.options: RealFilesystemOptions = build_real_filesystem_options(config or {})
        factory = RealFilesystemToolFactory(self.options)
        if tool_descriptions:
            descriptions = list(tool_descriptions)
            builders = [factory.build_list_tool, factory.build_read_tool]
            tools: List[Any] = []
            for builder, override in zip(builders, descriptions, strict=False):
                tools.append(builder(override))
            for builder in builders[len(descriptions) :]:
                tools.append(builder())
            self.tools = tools
        else:
            self.tools = factory.build_all()
        self.system_prompt = REAL_FILESYSTEM_PROMPT

    # ------------------------------------------------------------------ AgentMiddleware overrides
    def get_tools(self) -> List[Any]:
        return list(self.tools)

    def before_agent(
        self,
        state,
        runtime: Runtime[Any],
    ) -> Dict[str, Any] | None:
        project_root = self.options.project_root
        if not project_root.exists():
            raise ValueError(f"Real filesystem project root does not exist: {project_root}")
        if not project_root.is_dir():
            raise ValueError(f"Real filesystem project root is not a directory: {project_root}")
        return None

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ) -> ModelResponse:
        if self.system_prompt:
            if request.system_prompt:
                request.system_prompt = f"{request.system_prompt}\n\n{self.system_prompt}"
            else:
                request.system_prompt = self.system_prompt
        return handler(request)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler,
    ):
        if self.system_prompt:
            if request.system_prompt:
                request.system_prompt = f"{request.system_prompt}\n\n{self.system_prompt}"
            else:
                request.system_prompt = self.system_prompt
        return await handler(request)

    def describe(self) -> Dict[str, Any]:
        """Return a JSON-serialisable snapshot of the middleware configuration."""
        description = self.options.describe()
        description.update(
            {
                "enabled": True,
                "tools": [tool.name for tool in self.tools if hasattr(tool, "name")],
            }
        )
        return description
