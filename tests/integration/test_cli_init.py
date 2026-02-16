from pathlib import Path

from src.core.project import ProjectContext, MetadataManager
from src.components.shared.memory import SessionManager


class TestCLIInitialization:
    def test_full_initialization_flow(self, tmp_path: Path):
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        metadata_file = tmp_path / ".iris" / "metadata.json"

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        assert (project_dir / ".iris" / "sessions" / "llm").exists()
        assert (project_dir / ".iris" / "sessions" / "basicagent").exists()
        assert (project_dir / ".iris" / "sessions" / "deepagent").exists()

        manager = MetadataManager(metadata_file)
        manager.update_project(
            project_path=ctx.project_path,
            project_id=ctx.project_id,
            project_name=ctx.project_name,
        )

        meta = manager.get_project(project_dir)
        assert meta is not None
        assert meta.name == "test-project"

    def test_session_manager_with_project_context(self, tmp_path: Path):
        project_dir = tmp_path / "session-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        session_manager = SessionManager(mode="basic", project_context=ctx)

        assert "basicagent" in session_manager.storage_dirs["basic"]
        assert str(project_dir) in session_manager.storage_dirs["basic"]

    def test_multiple_projects_isolation(self, tmp_path: Path):
        project_a = tmp_path / "project-a"
        project_b = tmp_path / "project-b"

        for p in (project_a, project_b):
            p.mkdir()
            (p / ".git").mkdir()

        ctx_a = ProjectContext.from_path(project_a)
        ctx_b = ProjectContext.from_path(project_b)

        ctx_a.ensure_structure()
        ctx_b.ensure_structure()

        assert ctx_a.get_storage_dir("llm") != ctx_b.get_storage_dir("llm")
        assert "project-a" in str(ctx_a.get_storage_dir("llm"))
        assert "project-b" in str(ctx_b.get_storage_dir("llm"))
