from pathlib import Path

from langchain_core.messages import HumanMessage, AIMessage

from src.core.project import ProjectContext
from src.components.shared.memory import SessionManager
from src.components.shared.storage.session_storage import SessionStorage


class TestSessionStorageIntegration:
    def test_save_and_load_session(self, tmp_path: Path):
        project_dir = tmp_path / "storage-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        storage = SessionStorage(str(ctx.get_storage_dir("llm")))

        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
        storage.save_session("test_session", messages)

        loaded = storage.load_session("test_session")

        assert loaded is not None
        assert len(loaded) == 2
        assert loaded[0].content == "Hello"
        assert loaded[1].content == "Hi there!"

    def test_session_persistence_across_managers(self, tmp_path: Path):
        project_dir = tmp_path / "persist-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        manager1 = SessionManager(mode="llm", project_context=ctx)
        session_id = manager1.create_new_session()

        storage1 = manager1.storage
        storage1.save_session(session_id, [HumanMessage(content="Test")])

        manager2 = SessionManager(mode="llm", project_context=ctx)
        assert manager2.session_exists(session_id)

        messages = manager2.storage.load_session(session_id)
        assert messages is not None
        assert len(messages) == 1
        assert messages[0].content == "Test"
