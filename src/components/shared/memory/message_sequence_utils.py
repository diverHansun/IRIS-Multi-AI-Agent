from __future__ import annotations

from typing import Iterable, List, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def split_into_atomic_groups(messages: Sequence[BaseMessage]) -> List[List[BaseMessage]]:
    """Split messages into trim-safe groups preserving AI(tool_calls)+ToolMessage pairs."""
    groups: List[List[BaseMessage]] = []
    current_group: List[BaseMessage] = []
    pending_tool_call_ids: set[str] = set()

    def flush_current() -> None:
        nonlocal current_group, pending_tool_call_ids
        if current_group:
            groups.append(current_group)
            current_group = []
        pending_tool_call_ids = set()

    for msg in messages:
        if isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            tool_call_ids = {
                str(call.get("id"))
                for call in tool_calls
                if isinstance(call, dict) and call.get("id")
            }
            if tool_calls:
                flush_current()
                current_group = [msg]
                pending_tool_call_ids = set(tool_call_ids)
                # Malformed tool_calls with no ids: keep AIMessage as standalone group.
                if not pending_tool_call_ids:
                    flush_current()
                continue

            flush_current()
            groups.append([msg])
            continue

        if isinstance(msg, ToolMessage):
            tool_call_id = str(getattr(msg, "tool_call_id", "") or "")
            if current_group and pending_tool_call_ids and tool_call_id in pending_tool_call_ids:
                current_group.append(msg)
                pending_tool_call_ids.discard(tool_call_id)
                if not pending_tool_call_ids:
                    flush_current()
                continue

            # Orphan or unexpected ToolMessage remains a standalone group.
            flush_current()
            groups.append([msg])
            continue

        if isinstance(msg, HumanMessage):
            flush_current()
            groups.append([msg])
            continue

        flush_current()
        groups.append([msg])

    flush_current()
    return groups


def trim_messages_by_atomic_groups(
    messages: Sequence[BaseMessage],
    max_messages: int | None,
) -> List[BaseMessage]:
    """Trim from the front while avoiding splitting atomic AI/tool groups."""
    if not max_messages or max_messages <= 0:
        return list(messages)
    if len(messages) <= max_messages:
        return list(messages)

    groups = split_into_atomic_groups(messages)
    if not groups:
        return []

    selected: List[List[BaseMessage]] = []
    total = 0
    for group in reversed(groups):
        group_len = len(group)
        if selected and (total + group_len) > max_messages:
            break
        selected.append(group)
        total += group_len

    result: List[BaseMessage] = []
    for group in reversed(selected):
        result.extend(group)
    return result


def extract_recent_turns(messages: Sequence[BaseMessage], max_turns: int) -> List[BaseMessage]:
    """Return the most recent N turns, where turns are bounded by HumanMessage starts."""
    if max_turns <= 0:
        return []

    human_indices = [idx for idx, msg in enumerate(messages) if isinstance(msg, HumanMessage)]
    if not human_indices:
        return list(messages)

    start_index = human_indices[-max_turns] if len(human_indices) >= max_turns else human_indices[0]
    return list(messages[start_index:])


def dedup_identity_key(message: BaseMessage) -> tuple:
    """Stable dedup key that preserves ToolMessage and AI tool_call semantics."""
    if isinstance(message, ToolMessage):
        tool_call_id = str(getattr(message, "tool_call_id", "") or "")
        if tool_call_id:
            return ("ToolMessage", tool_call_id)
        return ("ToolMessage", _safe_content(message))

    if isinstance(message, AIMessage):
        tool_calls = getattr(message, "tool_calls", None) or []
        tool_call_ids = tuple(
            str(call.get("id") or "")
            for call in tool_calls
            if isinstance(call, dict)
        )
        return ("AIMessage", _safe_content(message), tool_call_ids)

    return (type(message).__name__, _safe_content(message))


def are_consecutive_duplicates(prev: BaseMessage, curr: BaseMessage) -> bool:
    """Conservative duplicate check for consecutive-message dedupe."""
    return dedup_identity_key(prev) == dedup_identity_key(curr)


def _safe_content(message: BaseMessage) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    return str(content)

