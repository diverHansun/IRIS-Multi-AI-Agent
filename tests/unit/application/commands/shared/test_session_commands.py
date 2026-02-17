from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from src.application.commands.shared.session_commands import (
    CleanupSessionsCommand,
    ClearSessionCommand,
    DeleteSessionCommand,
    ListSessionsCommand,
    NewSessionCommand,
    RestoreSessionCommand,
)


class _StorageStub:
    def __init__(self, *, delete_ok: bool = True) -> None:
        self.delete_ok = delete_ok
        self.deleted: list[str] = []

    def delete_session(self, session_id: str) -> bool:
        self.deleted.append(session_id)
        return self.delete_ok


class _SessionManagerStub:
    def __init__(self) -> None:
        self.mode = "llm"
        self.storage = _StorageStub()
        self.created = 0
        self.clear_ok = True
        self.default_sessions = [{"session_id": "s1"}]
        self.grouped_sessions = {"llm": [{"session_id": "s1"}], "basic": [], "deep": []}
        self.exists_current = {"s1": True}
        self.exists_by_mode = {"llm": set(), "basic": set(), "deep": set()}
        self.info = {"session_id": "s1", "message_count": 3}

    def create_new_session(self) -> str:
        self.created += 1
        return f"new-{self.created}"

    def clear_current_session(self) -> bool:
        return self.clear_ok

    def list_sessions(self):
        return list(self.default_sessions)

    def list_all_sessions(self):
        return dict(self.grouped_sessions)

    def session_exists(self, session_id: str, mode: str | None = None) -> bool:
        if mode is None:
            return self.exists_current.get(session_id, False)
        return session_id in self.exists_by_mode.get(mode, set())

    def get_session_info(self, session_id: str):
        return dict(self.info)

    def cleanup_orphaned_sessions(self):
        return {"orphaned_index_entries": 1, "orphaned_files": 2}


class _Ctx:
    def __init__(self, session_manager=None) -> None:
        self.current_engine = "llm"
        self.session_id = "s1"
        self.console = MagicMock()
        self.session_manager = session_manager


def test_new_session_requires_session_manager():
    command = NewSessionCommand()
    ctx = _Ctx(session_manager=None)

    result = asyncio.run(command.execute(ctx, ""))

    assert result.type == "error"
    assert "Session manager is not initialized." == result.message


def test_new_session_updates_context_and_payload():
    command = NewSessionCommand()
    manager = _SessionManagerStub()
    ctx = _Ctx(session_manager=manager)

    result = asyncio.run(command.execute(ctx, ""))

    assert result.type == "success"
    assert result.payload == {"old_session_id": "s1", "new_session_id": "new-1"}
    assert ctx.session_id == "new-1"


def test_clear_session_success_and_failure():
    command = ClearSessionCommand()
    manager = _SessionManagerStub()
    ctx = _Ctx(session_manager=manager)

    ok = asyncio.run(command.execute(ctx, ""))
    assert ok.type == "success"

    manager.clear_ok = False
    fail = asyncio.run(command.execute(ctx, ""))
    assert fail.type == "error"
    assert "Failed to clear session memory." in fail.message


def test_list_sessions_default_and_all_mode():
    command = ListSessionsCommand()
    manager = _SessionManagerStub()
    ctx = _Ctx(session_manager=manager)

    default_result = asyncio.run(command.execute(ctx, ""))
    assert default_result.type == "render"
    assert default_result.payload["kind"] == "sessions"
    assert default_result.payload["current_session_id"] == "s1"

    all_result = asyncio.run(command.execute(ctx, "all"))
    assert all_result.type == "render"
    assert all_result.payload["kind"] == "sessions_grouped"
    assert all_result.payload["current_mode"] == "llm"


def test_restore_session_validation_and_cross_mode_hint():
    command = RestoreSessionCommand()
    manager = _SessionManagerStub()
    ctx = _Ctx(session_manager=manager)

    missing = asyncio.run(command.execute(ctx, ""))
    assert missing.type == "error"
    assert "Usage: /restore <session_id>" in missing.message

    manager.exists_current["target"] = False
    manager.exists_by_mode["basic"].add("target")
    cross_mode = asyncio.run(command.execute(ctx, "target"))
    assert cross_mode.type == "error"
    assert "exists in mode 'basic'" in cross_mode.message
    assert "Switch to basic mode first." in cross_mode.message


def test_restore_session_success_in_current_mode():
    command = RestoreSessionCommand()
    manager = _SessionManagerStub()
    manager.exists_current["target"] = True
    manager.info = {"session_id": "target", "message_count": 8}
    ctx = _Ctx(session_manager=manager)

    result = asyncio.run(command.execute(ctx, "target"))

    assert result.type == "success"
    assert ctx.session_id == "target"
    assert result.payload["session_id"] == "target"
    assert result.payload["session_info"]["message_count"] == 8


def test_delete_session_flow_for_current_and_non_current():
    command = DeleteSessionCommand()
    manager = _SessionManagerStub()
    ctx = _Ctx(session_manager=manager)

    missing = asyncio.run(command.execute(ctx, ""))
    assert missing.type == "error"
    assert "Usage: /delete_session <session_id>" in missing.message

    manager.exists_current["missing"] = False
    not_found = asyncio.run(command.execute(ctx, "missing"))
    assert not_found.type == "error"
    assert "Session does not exist: missing" in not_found.message

    # Delete non-current session
    manager.exists_current["other"] = True
    non_current = asyncio.run(command.execute(ctx, "other"))
    assert non_current.type == "success"
    assert non_current.payload == {"deleted_session_id": "other"}

    # Delete current session triggers new session creation
    manager.exists_current["s1"] = True
    current = asyncio.run(command.execute(ctx, "s1"))
    assert current.type == "success"
    assert current.payload["deleted_session_id"] == "s1"
    assert current.payload["new_session_id"] == "new-1"
    assert ctx.session_id == "new-1"


def test_delete_session_reports_storage_failure():
    command = DeleteSessionCommand()
    manager = _SessionManagerStub()
    manager.storage = _StorageStub(delete_ok=False)
    manager.exists_current["s1"] = True
    ctx = _Ctx(session_manager=manager)

    result = asyncio.run(command.execute(ctx, "s1"))

    assert result.type == "error"
    assert "Failed to delete session: s1" in result.message


def test_cleanup_sessions_returns_stats_payload():
    command = CleanupSessionsCommand()
    manager = _SessionManagerStub()
    ctx = _Ctx(session_manager=manager)

    result = asyncio.run(command.execute(ctx, ""))

    assert result.type == "success"
    assert result.payload == {"orphaned_index_entries": 1, "orphaned_files": 2}
