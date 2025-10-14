"""
Formatting helpers used by the CLI GUI before rendering.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, List, Mapping, MutableMapping


def format_session_list(raw_sessions: Iterable[Mapping[str, str]], current_id: str | None) -> List[MutableMapping[str, str]]:
    """
    Convert raw session metadata into a list suitable for rendering.
    """
    formatted: List[MutableMapping[str, str]] = []
    for session in raw_sessions:
        item = dict(session)
        if item.get("id") == current_id:
            item["active"] = "yes"
        timestamp = item.get("created_at")
        if timestamp:
            try:
                created_at = datetime.fromisoformat(timestamp)
                item["created_at_display"] = created_at.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                item["created_at_display"] = timestamp
        formatted.append(item)
    return formatted


def format_model_info(info: Mapping[str, str]) -> Mapping[str, str]:
    """
    Normalize provider/model names for display.
    """
    return {
        "provider": info.get("provider", "").upper(),
        "model": info.get("model", ""),
    }

