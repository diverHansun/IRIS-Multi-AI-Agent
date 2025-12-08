from typing import Any, Dict, List, Optional
import logging
import re

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


def _safe_set_tool_name(tool: BaseTool, new_name: str) -> None:
    try:
        tool.name = new_name  # most BaseTool instances allow attribute mutation
    except Exception as exc:
        logger.warning("Unable to set tool name to '%s': %s", new_name, exc)


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

    logger.debug(
        "Applying naming/filter to %d tools (include=%s, exclude=%s, strategy=%s)",
        len(tools),
        include_tools,
        exclude_tools,
        namespace_strategy,
    )

    for t in tools:
        name = getattr(t, "name", "<unknown>")
        try:
            if include_set and name not in include_set:
                logger.debug("Skipping tool not in include list: %s", name)
                continue
            if exclude_set and name in exclude_set:
                logger.debug("Skipping tool in exclude list: %s", name)
                continue

            if namespace_strategy == "prefix":
                prefix = rename_prefix or default_prefix
                if prefix and not name.startswith(prefix):
                    _safe_set_tool_name(t, f"{prefix}{name}")

            sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", t.name)
            if sanitized != t.name:
                logger.debug("Sanitizing tool name '%s' -> '%s'", t.name, sanitized)
                _safe_set_tool_name(t, sanitized)

            result.append(t)
        except Exception as exc:
            logger.warning("Failed to process tool '%s': %s", name, exc, exc_info=True)

    logger.debug("Naming/filter applied. Tools remaining: %d", len(result))
    return result


def schema_summary(tool: BaseTool) -> Dict[str, Any]:
    """Return a concise schema summary for CLI -v view."""
    try:
        args_schema = getattr(tool, "args_schema", None)
        if args_schema is None:
            logger.debug("Tool %s has no args_schema", getattr(tool, "name", "<unknown>"))
            return {"name": tool.name, "params": []}

        schema = None
        if hasattr(args_schema, "model_json_schema"):
            schema = args_schema.model_json_schema()
        elif hasattr(args_schema, "schema"):
            schema = args_schema.schema()
        else:
            logger.debug("Tool %s args_schema missing schema methods", getattr(tool, "name", "<unknown>"))
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
    except Exception as exc:
        logger.warning("Failed to summarize schema for tool %s: %s", getattr(tool, "name", "<unknown>"), exc)
        return {"name": tool.name, "params": []}
