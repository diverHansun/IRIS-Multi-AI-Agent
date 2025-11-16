"""Real filesystem middleware for DeepAgents."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langgraph.runtime import Runtime

from .config import RealFilesystemOptions, build_real_filesystem_options
from .tools import RealFilesystemToolFactory

REAL_FILESYSTEM_PROMPT = """You can access and modify the host project files using real filesystem tools.

Key rules:
- **Read operations**: Unrestricted. Use list, read, glob, grep freely to explore the codebase.
- **Write/Edit operations**: Automatic approval workflow. System will pause, show diff preview, and wait for user confirmation.
- Only paths within the configured allowlist and allowed extensions are accessible.
- Use pagination (offset/limit) when reading large files to avoid context overflow.

Available tools:
- list_real_files(directory_path, recursive, include_hidden)
- read_real_file(file_path, offset, limit, encoding)
- glob_real_files(pattern, base_path, recursive, include_hidden)
- grep_real_files(pattern, file_pattern, base_path, case_sensitive, context_lines, max_results, include_hidden)
- write_real_file(file_path, content, encoding) [Triggers approval]
- edit_real_file(file_path, old_string, new_string, encoding, replace_all) [Triggers approval]"""


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
        builders = [
            factory.build_list_tool,
            factory.build_read_tool,
            factory.build_write_tool,
            factory.build_edit_tool,
            factory.build_glob_tool,
            factory.build_grep_tool,
        ]
        if tool_descriptions:
            descriptions = list(tool_descriptions)
            tools: List[Any] = []
            for builder, override in zip(builders, descriptions, strict=False):
                tools.append(builder(override))
            for builder in builders[len(descriptions) :]:
                tools.append(builder())
            self.tools = tools
        else:
            self.tools = [builder() for builder in builders]
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
