from typing import Any, Dict, List, Optional
import re

from langchain_core.tools import BaseTool


def _safe_set_tool_name(tool: BaseTool, new_name: str) -> None:
    try:
        tool.name = new_name  # most BaseTool instances allow attribute mutation
    except Exception:
        # If immutable, ignore renaming
        pass


def apply_naming_and_filter(
    tools: List[BaseTool],
    namespace_strategy: str = "prefix",
    default_prefix: str = "mcp:",
    rename_prefix: Optional[str] = None,
    include_tools: Optional[List[str]] = None,
    exclude_tools: Optional[List[str]] = None,
) -> List[BaseTool]:
    include_set = set(include_tools or [])
    exclude_set = set(exclude_tools or [])

    result: List[BaseTool] = []

    for t in tools:
        name = t.name
        # filter by include/exclude if configured
        if include_set and name not in include_set:
            continue
        if exclude_set and name in exclude_set:
            continue

        # naming (prefix)
        if namespace_strategy == "prefix":
            prefix = rename_prefix or default_prefix
            if prefix and not name.startswith(prefix):
                _safe_set_tool_name(t, f"{prefix}{name}")
        # sanitize to satisfy providers like OpenAI function name rules
        # Allowed: letters, digits, underscore, hyphen (^[a-zA-Z0-9_-]+$)
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", t.name)
        if sanitized != t.name:
            _safe_set_tool_name(t, sanitized)
        result.append(t)

    return result


def schema_summary(tool: BaseTool) -> Dict[str, Any]:
    """Return a concise schema summary for CLI -v view."""
    # Prefer pydantic v2 API if available
    try:
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            return {"name": tool.name, "params": []}

        schema = None
        if hasattr(args_schema, "model_json_schema"):
            schema = args_schema.model_json_schema()
        elif hasattr(args_schema, "schema"):
            schema = args_schema.schema()
        else:
            return {"name": tool.name, "params": []}

        props = schema.get("properties", {})
        required = set(schema.get("required", []) or [])
        params = []
        for key, meta in props.items():
            t = meta.get("type") or meta.get("anyOf") or meta.get("allOf")
            params.append({
                "name": key,
                "required": key in required,
                "type": t if isinstance(t, str) else "union" if t else "unknown",
            })
        return {"name": tool.name, "params": params}
    except Exception:
        return {"name": tool.name, "params": []}
