from __future__ import annotations

import json
from typing import Any, Iterable, Dict, List


def _call_schema_api(maybe_model: Any) -> Dict[str, Any] | None:
    """Try various schema APIs on Pydantic v2/v1 classes or instances.
    Returns a dict if successful, else None.
    """
    if maybe_model is None:
        return None
    # Try v2 class/instance
    fn = getattr(maybe_model, "model_json_schema", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            pass
    # Try v1 class/instance
    fn = getattr(maybe_model, "schema", None)
    if callable(fn):
        try:
            return fn()
        except Exception:
            pass
    return None


def _extract_tool_schema(tool: Any) -> Dict[str, Any]:
    """
    Try to extract a full JSON Schema for a LangChain tool.
    Priority:
      1) Pydantic v2: tool.args_schema.model_json_schema()
      2) Pydantic v1: tool.args_schema.schema()
      3) Fallback: {"type":"object","properties":{"input":{"type":"string"}},"required":["input"]}
    """
    # args_schema (Pydantic) path
    args_schema = getattr(tool, "args_schema", None)
    schema = _call_schema_api(args_schema)
    if schema is not None:
        return schema

    # Some LangChain tools expose input_schema; attempt to use it if present
    input_schema = getattr(tool, "input_schema", None)
    if input_schema is not None:
        # If a dict already, return directly; else try schema APIs
        if isinstance(input_schema, dict):
            return input_schema
        schema = _call_schema_api(input_schema)
        if schema is not None:
            return schema

    # Fallback minimal schema
    return {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        },
        "required": ["input"],
        "additionalProperties": False,
    }


def serialize_tools(tools: Iterable[Any]) -> str:
    """
    Serialize a sequence of LangChain tools into a compact JSON array string
    with entries: {name, description, schema}.

    - name: English identifier
    - description: Short description
    - schema: JSON Schema dict for action_input
    """
    items: List[Dict[str, Any]] = []
    for tool in tools:
        name = getattr(tool, "name", None) or getattr(tool, "__name__", "tool")
        description = getattr(tool, "description", None) or getattr(tool, "desc", "")
        try:
            schema = _extract_tool_schema(tool)
        except Exception:
            # Extreme fallback to avoid non-serializable content bubbling up
            schema = {
                "type": "object",
                "properties": {"input": {"type": "string"}},
                "required": ["input"],
                "additionalProperties": False,
            }
        items.append({
            "name": str(name),
            "description": str(description) if description is not None else "",
            "schema": schema,
        })

    # We return pretty JSON but without code fences; caller injects it directly into the template
    # Ensure JSON serializable; if any non-serializable sneaks in, coerce via default=str
    try:
        return json.dumps(items, ensure_ascii=False, indent=2)
    except TypeError:
        return json.dumps(items, ensure_ascii=False, indent=2, default=str)

