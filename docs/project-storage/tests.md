# 测试计划

> 版本: 1.0
> 日期: 2025-01-20
> 状态: 设计阶段

## 1. 概述

本文档描述项目存储重构的测试计划，包括单元测试、集成测试和端到端测试。

---

## 2. 测试范围

### 2.1 新增模块测试

| 模块 | 测试文件 | 优先级 |
|------|---------|--------|
| `src/core/project/detector.py` | `tests/unit/core/project/test_detector.py` | P0 |
| `src/core/project/context.py` | `tests/unit/core/project/test_context.py` | P0 |
| `src/core/project/metadata.py` | `tests/unit/core/project/test_metadata.py` | P0 |
| `src/core/project/share.py` | `tests/unit/core/project/test_share.py` | P0 |

### 2.2 修改模块测试

| 模块 | 测试文件 | 优先级 |
|------|---------|--------|
| `SessionManager` | `tests/unit/memory/test_session_manager.py` | P0 |
| `BasicAgentCheckpointer` | `tests/unit/memory/test_basic_agent_checkpointer.py` | P0 |
| `DeepAgentCheckpointer` | `tests/unit/memory/test_deep_agent_checkpointer.py` | P0 |

### 2.3 集成测试

| 场景 | 测试文件 | 优先级 |
|------|---------|--------|
| CLI 初始化流程 | `tests/integration/test_cli_init.py` | P0 |
| 会话存储到 `.iris/` | `tests/integration/test_session_storage.py` | P0 |
| 项目切换 | `tests/integration/test_project_switch.py` | P1 |

---

## 3. 单元测试

### 3.1 test_detector.py

```python
# tests/unit/core/project/test_detector.py

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.core.project.detector import (
    detect_project_root,
    is_iris_source_project,
    PROJECT_MARKERS,
)


class TestDetectProjectRoot:
    """项目根目录检测测试"""

    def test_detect_git_project(self, tmp_path: Path):
        """测试检测 Git 项目"""
        # 创建 .git 目录
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "src" / "app"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir)
        assert result == tmp_path

    def test_detect_python_project(self, tmp_path: Path):
        """测试检测 Python 项目"""
        (tmp_path / "pyproject.toml").touch()
        subdir = tmp_path / "src"
        subdir.mkdir()

        result = detect_project_root(subdir)
        assert result == tmp_path

    def test_detect_iris_marker(self, tmp_path: Path):
        """测试检测 .iris 标记"""
        (tmp_path / ".iris").mkdir()
        subdir = tmp_path / "app"
        subdir.mkdir()

        result = detect_project_root(subdir)
        assert result == tmp_path

    def test_no_project_marker(self, tmp_path: Path):
        """测试无项目标记时返回 None"""
        subdir = tmp_path / "random" / "dir"
        subdir.mkdir(parents=True)

        result = detect_project_root(subdir)
        assert result is None

    def test_detect_from_cwd(self, tmp_path: Path):
        """测试从当前工作目录检测"""
        (tmp_path / ".git").mkdir()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = detect_project_root()
            assert result == tmp_path

    def test_marker_priority(self, tmp_path: Path):
        """测试标记优先级（.iris 优先于 .git）"""
        # 在不同层级创建标记
        (tmp_path / ".iris").mkdir()
        inner_dir = tmp_path / "inner"
        inner_dir.mkdir()
        (inner_dir / ".git").mkdir()

        # 从 inner 目录检测应该先找到 .git
        result = detect_project_root(inner_dir)
        assert result == inner_dir


class TestIsIrisSourceProject:
    """iris-code 源码项目检测测试"""

    def test_is_iris_source(self, tmp_path: Path):
        """测试识别 iris-code 源码项目"""
        (tmp_path / "src" / "core" / "project").mkdir(parents=True)
        (tmp_path / "src" / "application" / "cli").mkdir(parents=True)

        assert is_iris_source_project(tmp_path) is True

    def test_not_iris_source(self, tmp_path: Path):
        """测试非 iris-code 项目"""
        (tmp_path / "src" / "app").mkdir(parents=True)

        assert is_iris_source_project(tmp_path) is False
```

### 3.2 test_context.py

```python
# tests/unit/core/project/test_context.py

import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.project.context import ProjectContext


class TestProjectContext:
    """ProjectContext 测试"""

    def test_from_path_with_git(self, tmp_path: Path):
        """测试从 Git 项目创建上下文"""
        (tmp_path / ".git").mkdir()

        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.project_path == tmp_path
        assert ctx.project_name == tmp_path.name
        assert ctx.is_iris_source is False
        assert tmp_path.name in ctx.project_id
        assert len(ctx.project_id.split("_")[-1]) == 8  # hash 部分

    def test_from_cwd(self, tmp_path: Path):
        """测试从当前目录创建上下文"""
        (tmp_path / ".git").mkdir()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            ctx = ProjectContext.from_cwd()
            assert ctx.project_path == tmp_path

    def test_iris_dir_property(self, tmp_path: Path):
        """测试 iris_dir 属性"""
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.iris_dir == tmp_path / ".iris"

    def test_config_file_property(self, tmp_path: Path):
        """测试 config_file 属性"""
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.config_file == tmp_path / ".iris" / "config.json"

    def test_get_storage_dir(self, tmp_path: Path):
        """测试 get_storage_dir 方法"""
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        assert ctx.get_storage_dir("llm") == tmp_path / ".iris" / "sessions" / "llm"
        assert ctx.get_storage_dir("basic") == tmp_path / ".iris" / "sessions" / "basicagent"
        assert ctx.get_storage_dir("deep") == tmp_path / ".iris" / "sessions" / "deepagent"

    def test_ensure_structure(self, tmp_path: Path):
        """测试 ensure_structure 方法"""
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        ctx.ensure_structure()

        assert (tmp_path / ".iris" / "sessions" / "llm").exists()
        assert (tmp_path / ".iris" / "sessions" / "basicagent").exists()
        assert (tmp_path / ".iris" / "sessions" / "deepagent").exists()

    def test_get_storage_dirs_dict(self, tmp_path: Path):
        """测试 get_storage_dirs_dict 方法"""
        (tmp_path / ".git").mkdir()
        ctx = ProjectContext.from_path(tmp_path)

        dirs = ctx.get_storage_dirs_dict()

        assert "llm" in dirs
        assert "basic" in dirs
        assert "deep" in dirs

    def test_project_id_generation(self, tmp_path: Path):
        """测试项目 ID 生成"""
        project_dir = tmp_path / "my-test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)

        # ID 格式: {safe_name}_{hash8}
        assert ctx.project_id.startswith("my-test-project_")
        assert len(ctx.project_id.split("_")[-1]) == 8

    def test_project_id_with_special_chars(self, tmp_path: Path):
        """测试包含特殊字符的目录名"""
        project_dir = tmp_path / "my project @2024!"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)

        # 特殊字符应被替换为下划线
        assert "@" not in ctx.project_id
        assert "!" not in ctx.project_id
        assert " " not in ctx.project_id

    def test_fallback_to_current_dir(self, tmp_path: Path):
        """测试无项目标记时使用当前目录"""
        ctx = ProjectContext.from_path(tmp_path)

        # 应该使用 tmp_path 作为项目根
        assert ctx.project_path == tmp_path.resolve()
```

### 3.3 test_metadata.py

```python
# tests/unit/core/project/test_metadata.py

import pytest
import json
from pathlib import Path
from datetime import datetime

from src.core.project.metadata import (
    ProjectMetadata,
    LastSessionInfo,
    MetadataManager,
)


class TestProjectMetadata:
    """ProjectMetadata 数据类测试"""

    def test_to_dict(self):
        """测试转换为字典"""
        meta = ProjectMetadata(
            path="/test/path",
            id="test_12345678",
            name="test",
            last_session=LastSessionInfo(mode="deep", session_id="session_1"),
        )

        data = meta.to_dict()

        assert data["path"] == "/test/path"
        assert data["id"] == "test_12345678"
        assert data["last_session"]["mode"] == "deep"

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "path": "/test/path",
            "id": "test_12345678",
            "name": "test",
            "last_session": {"mode": "llm", "session_id": "s1"},
            "last_used": "2025-01-20T10:00:00",
            "created_at": "2025-01-15T09:00:00",
        }

        meta = ProjectMetadata.from_dict(data)

        assert meta.path == "/test/path"
        assert meta.last_session.mode == "llm"

    def test_from_dict_without_last_session(self):
        """测试没有 last_session 时从字典创建"""
        data = {
            "path": "/test/path",
            "id": "test_12345678",
            "name": "test",
        }

        meta = ProjectMetadata.from_dict(data)

        assert meta.last_session is None


class TestMetadataManager:
    """MetadataManager 测试"""

    def test_init_creates_empty_structure(self, tmp_path: Path):
        """测试初始化创建空结构"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        assert manager._data["version"] == "1.0"
        assert manager._data["projects"] == []

    def test_load_existing_file(self, tmp_path: Path):
        """测试加载现有文件"""
        metadata_file = tmp_path / "metadata.json"
        existing_data = {
            "version": "1.0",
            "projects": [
                {"path": "/test", "id": "test_1", "name": "test"}
            ]
        }
        metadata_file.write_text(json.dumps(existing_data))

        manager = MetadataManager(metadata_file)

        assert len(manager._data["projects"]) == 1

    def test_get_project_exists(self, tmp_path: Path):
        """测试获取存在的项目"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        # 先添加项目
        project_path = tmp_path / "my-project"
        manager.update_project(project_path, "my-project_abc", "my-project")

        # 获取项目
        meta = manager.get_project(project_path)

        assert meta is not None
        assert meta.name == "my-project"

    def test_get_project_not_exists(self, tmp_path: Path):
        """测试获取不存在的项目"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        meta = manager.get_project(tmp_path / "nonexistent")

        assert meta is None

    def test_update_project_new(self, tmp_path: Path):
        """测试添加新项目"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "new-project"
        manager.update_project(
            project_path,
            "new-project_abc",
            "new-project",
            mode="basic",
            session_id="session_1"
        )

        meta = manager.get_project(project_path)
        assert meta is not None
        assert meta.last_session.mode == "basic"
        assert meta.last_session.session_id == "session_1"

    def test_update_project_existing(self, tmp_path: Path):
        """测试更新现有项目"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "project"

        # 第一次添加
        manager.update_project(project_path, "project_abc", "project", mode="llm", session_id="s1")

        # 第二次更新
        manager.update_project(project_path, "project_abc", "project", mode="deep", session_id="s2")

        meta = manager.get_project(project_path)
        assert meta.last_session.mode == "deep"
        assert meta.last_session.session_id == "s2"

    def test_list_recent_projects(self, tmp_path: Path):
        """测试列出最近项目"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        # 添加多个项目
        for i in range(5):
            project_path = tmp_path / f"project-{i}"
            manager.update_project(project_path, f"project-{i}_abc", f"project-{i}")

        projects = manager.list_recent_projects(limit=3)

        assert len(projects) == 3

    def test_remove_project(self, tmp_path: Path):
        """测试移除项目"""
        metadata_file = tmp_path / "metadata.json"
        manager = MetadataManager(metadata_file)

        project_path = tmp_path / "to-remove"
        manager.update_project(project_path, "to-remove_abc", "to-remove")

        result = manager.remove_project(project_path)

        assert result is True
        assert manager.get_project(project_path) is None

    def test_save_and_reload(self, tmp_path: Path):
        """测试保存后重新加载"""
        metadata_file = tmp_path / "metadata.json"

        # 第一个 manager 添加数据
        manager1 = MetadataManager(metadata_file)
        project_path = tmp_path / "persistent"
        manager1.update_project(project_path, "persistent_abc", "persistent")

        # 第二个 manager 加载数据
        manager2 = MetadataManager(metadata_file)
        meta = manager2.get_project(project_path)

        assert meta is not None
        assert meta.name == "persistent"
```

### 3.4 test_share.py

```python
# tests/unit/core/project/test_share.py

import pytest
from pathlib import Path
from unittest.mock import patch

from src.core.project.share import IrisShareDir


class TestIrisShareDir:
    """IrisShareDir 测试"""

    def test_get_share_dir_creates_directory(self, tmp_path: Path):
        """测试获取共享目录时自动创建"""
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            share_dir = IrisShareDir.get_share_dir()

            assert share_dir.exists()
            assert share_dir == home_dir / ".iris"

    def test_get_metadata_file(self, tmp_path: Path):
        """测试获取元数据文件路径"""
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            metadata_file = IrisShareDir.get_metadata_file()

            assert metadata_file == home_dir / ".iris" / "metadata.json"

    def test_get_global_config_file(self, tmp_path: Path):
        """测试获取全局配置文件路径"""
        home_dir = tmp_path / "home"
        home_dir.mkdir()

        with patch("pathlib.Path.home", return_value=home_dir):
            config_file = IrisShareDir.get_global_config_file()

            assert config_file == home_dir / ".iris" / "config.json"
```

---

## 4. 集成测试

### 4.1 test_cli_init.py

```python
# tests/integration/test_cli_init.py

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.core.project import ProjectContext, MetadataManager
from src.components.shared.memory.session_manager import SessionManager


class TestCLIInitialization:
    """CLI 初始化流程集成测试"""

    def test_full_initialization_flow(self, tmp_path: Path):
        """测试完整初始化流程"""
        # 创建模拟项目
        project_dir = tmp_path / "test-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # 模拟元数据文件
        metadata_file = tmp_path / ".iris" / "metadata.json"

        # 1. 创建项目上下文
        ctx = ProjectContext.from_path(project_dir)

        # 2. 确保目录结构
        ctx.ensure_structure()

        # 3. 验证目录创建
        assert (project_dir / ".iris" / "sessions" / "llm").exists()
        assert (project_dir / ".iris" / "sessions" / "basicagent").exists()
        assert (project_dir / ".iris" / "sessions" / "deepagent").exists()

        # 4. 更新元数据
        manager = MetadataManager(metadata_file)
        manager.update_project(
            project_path=ctx.project_path,
            project_id=ctx.project_id,
            project_name=ctx.project_name,
        )

        # 5. 验证元数据
        meta = manager.get_project(project_dir)
        assert meta is not None
        assert meta.name == "test-project"

    def test_session_manager_with_project_context(self, tmp_path: Path):
        """测试 SessionManager 与 ProjectContext 集成"""
        project_dir = tmp_path / "session-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        # 创建 SessionManager
        session_manager = SessionManager(mode="basic", project_context=ctx)

        # 验证存储路径
        assert "basicagent" in session_manager.storage_dirs["basic"]
        assert str(project_dir) in session_manager.storage_dirs["basic"]

    def test_multiple_projects_isolation(self, tmp_path: Path):
        """测试多个项目的隔离"""
        # 创建两个项目
        project_a = tmp_path / "project-a"
        project_b = tmp_path / "project-b"

        for p in [project_a, project_b]:
            p.mkdir()
            (p / ".git").mkdir()

        ctx_a = ProjectContext.from_path(project_a)
        ctx_b = ProjectContext.from_path(project_b)

        ctx_a.ensure_structure()
        ctx_b.ensure_structure()

        # 验证会话目录隔离
        assert ctx_a.get_storage_dir("llm") != ctx_b.get_storage_dir("llm")
        assert "project-a" in str(ctx_a.get_storage_dir("llm"))
        assert "project-b" in str(ctx_b.get_storage_dir("llm"))
```

### 4.2 test_session_storage.py

```python
# tests/integration/test_session_storage.py

import pytest
from pathlib import Path

from src.core.project import ProjectContext
from src.components.shared.memory.session_manager import SessionManager
from src.components.shared.storage.session_storage import SessionStorage
from langchain_core.messages import HumanMessage, AIMessage


class TestSessionStorageIntegration:
    """会话存储集成测试"""

    def test_save_and_load_session(self, tmp_path: Path):
        """测试保存和加载会话"""
        project_dir = tmp_path / "storage-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        # 创建 SessionStorage
        storage = SessionStorage(str(ctx.get_storage_dir("llm")))

        # 保存会话
        messages = [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!"),
        ]
        storage.save_session("test_session", messages)

        # 加载会话
        loaded = storage.load_session("test_session")

        assert len(loaded) == 2
        assert loaded[0].content == "Hello"
        assert loaded[1].content == "Hi there!"

    def test_session_persistence_across_managers(self, tmp_path: Path):
        """测试跨 SessionManager 实例的会话持久化"""
        project_dir = tmp_path / "persist-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        # 第一个 manager 创建会话
        manager1 = SessionManager(mode="llm", project_context=ctx)
        session_id = manager1.create_new_session()

        # 保存一些消息
        storage1 = manager1.storage
        storage1.save_session(session_id, [HumanMessage(content="Test")])

        # 第二个 manager 加载会话
        manager2 = SessionManager(mode="llm", project_context=ctx)
        assert manager2.session_exists(session_id)

        # 验证数据
        messages = manager2.storage.load_session(session_id)
        assert len(messages) == 1
        assert messages[0].content == "Test"
```

---

## 5. 端到端测试

### 5.1 E2E 测试场景

```python
# tests/e2e/test_project_workflow.py

import pytest
import subprocess
import json
from pathlib import Path


class TestProjectWorkflow:
    """项目工作流端到端测试"""

    @pytest.mark.e2e
    def test_first_run_creates_iris_dir(self, tmp_path: Path):
        """测试首次运行创建 .iris 目录"""
        project_dir = tmp_path / "e2e-project"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # 运行 iris（模拟）
        # 实际测试中可能需要启动 subprocess
        from src.core.project import ProjectContext

        ctx = ProjectContext.from_path(project_dir)
        ctx.ensure_structure()

        assert (project_dir / ".iris").exists()
        assert (project_dir / ".iris" / "sessions").exists()

    @pytest.mark.e2e
    def test_session_survives_restart(self, tmp_path: Path):
        """测试会话在重启后保留"""
        project_dir = tmp_path / "restart-test"
        project_dir.mkdir()
        (project_dir / ".git").mkdir()

        # 第一次 "运行"
        from src.core.project import ProjectContext, MetadataManager
        from src.components.shared.memory.session_manager import SessionManager
        from langchain_core.messages import HumanMessage, AIMessage

        ctx1 = ProjectContext.from_path(project_dir)
        ctx1.ensure_structure()

        manager1 = SessionManager(mode="deep", project_context=ctx1)
        session_id = manager1.create_new_session()
        manager1.storage.save_session(session_id, [
            HumanMessage(content="Remember this"),
            AIMessage(content="I will remember"),
        ])

        # 更新元数据
        metadata_file = tmp_path / "home" / ".iris" / "metadata.json"
        metadata_file.parent.mkdir(parents=True, exist_ok=True)
        mm = MetadataManager(metadata_file)
        mm.update_project(
            ctx1.project_path,
            ctx1.project_id,
            ctx1.project_name,
            mode="deep",
            session_id=session_id
        )

        # 第二次 "运行"（模拟重启）
        ctx2 = ProjectContext.from_path(project_dir)
        manager2 = SessionManager(mode="deep", project_context=ctx2)

        # 从元数据获取最后会话
        mm2 = MetadataManager(metadata_file)
        meta = mm2.get_project(project_dir)

        assert meta is not None
        assert meta.last_session is not None
        assert meta.last_session.session_id == session_id

        # 加载会话
        messages = manager2.storage.load_session(meta.last_session.session_id)
        assert len(messages) == 2
        assert "Remember this" in messages[0].content
```

---

## 6. 测试数据和 Fixtures

### 6.1 conftest.py

```python
# tests/conftest.py

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """创建临时项目目录"""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    (project_dir / ".git").mkdir()
    return project_dir


@pytest.fixture
def temp_home(tmp_path: Path) -> Path:
    """创建临时 home 目录"""
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    return home_dir


@pytest.fixture
def mock_project_context(temp_project: Path):
    """创建模拟的 ProjectContext"""
    from src.core.project import ProjectContext

    ctx = ProjectContext.from_path(temp_project)
    ctx.ensure_structure()
    return ctx


@pytest.fixture
def mock_metadata_manager(temp_home: Path):
    """创建模拟的 MetadataManager"""
    from src.core.project.metadata import MetadataManager

    metadata_file = temp_home / ".iris" / "metadata.json"
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    return MetadataManager(metadata_file)
```

---

## 7. 测试覆盖率目标

| 模块 | 目标覆盖率 |
|------|-----------|
| `src/core/project/detector.py` | >= 90% |
| `src/core/project/context.py` | >= 90% |
| `src/core/project/metadata.py` | >= 85% |
| `src/core/project/share.py` | >= 90% |
| `SessionManager` (修改部分) | >= 80% |
| `Checkpointers` (修改部分) | >= 80% |

---

## 8. 测试执行命令

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行特定模块测试
pytest tests/unit/core/project/ -v

# 运行集成测试
pytest tests/integration/ -v

# 运行 E2E 测试
pytest tests/e2e/ -v -m e2e

# 生成覆盖率报告
pytest tests/ --cov=src/core/project --cov-report=html

# 运行所有测试
pytest tests/ -v
```

---

## 9. CI/CD 集成

```yaml
# .github/workflows/test.yml (示例)

name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e .
          pip install pytest pytest-cov pytest-asyncio

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src/core/project

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```
