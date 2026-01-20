# 修改点与功能清单

> 版本: 1.0
> 日期: 2025-01-20
> 状态: 设计阶段

## 1. 概述

本文档详细列出实现项目存储重构所需的所有修改点和新增功能，按模块和职责分工组织。

---

## 2. 新增模块

### 2.1 项目管理模块 (`src/core/project/`)

| 文件 | 类/函数 | 职责 | 优先级 |
|------|--------|------|--------|
| `__init__.py` | - | 模块导出 | P0 |
| `context.py` | `ProjectContext` | 项目上下文管理 | P0 |
| `detector.py` | `detect_project_root()` | 项目根目录检测 | P0 |
| `detector.py` | `generate_project_id()` | 项目 ID 生成 | P0 |
| `metadata.py` | `ProjectMetadata` | 项目元数据模型 | P0 |
| `metadata.py` | `MetadataManager` | 全局元数据管理 | P0 |
| `paths.py` | `resolve_storage_path()` | 存储路径解析 | P1 |
| `share.py` | `IrisShareDir` | `~/.iris/` 目录管理 | P0 |

#### 2.1.1 context.py 详细设计

```python
# src/core/project/context.py

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .detector import detect_project_root, is_iris_source_project
from .share import IrisShareDir


@dataclass
class ProjectContext:
    """项目上下文，统一管理项目相关路径和配置"""

    project_path: Path
    project_id: str
    project_name: str
    is_iris_source: bool = False

    @classmethod
    def from_cwd(cls) -> "ProjectContext":
        """从当前工作目录创建上下文"""
        return cls.from_path(Path.cwd())

    @classmethod
    def from_path(cls, path: Path) -> "ProjectContext":
        """从指定路径创建上下文"""
        project_root = detect_project_root(path)
        if project_root is None:
            # 未检测到项目，使用当前目录作为项目根
            project_root = path.resolve()

        project_name = project_root.name
        project_id = cls._generate_project_id(project_root)
        is_iris = is_iris_source_project(project_root)

        return cls(
            project_path=project_root,
            project_id=project_id,
            project_name=project_name,
            is_iris_source=is_iris,
        )

    @staticmethod
    def _generate_project_id(project_path: Path) -> str:
        """生成项目唯一标识: {safe_dir_name}_{hash[:8]}"""
        path_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:8]
        dir_name = project_path.name
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dir_name)
        return f"{safe_name}_{path_hash}"

    @property
    def iris_dir(self) -> Path:
        """项目 .iris 目录路径"""
        return self.project_path / ".iris"

    @property
    def config_file(self) -> Path:
        """项目配置文件路径"""
        return self.iris_dir / "config.json"

    @property
    def agent_md_file(self) -> Path:
        """项目 Agent 指令文件路径"""
        return self.iris_dir / "agent.md"

    def get_storage_dir(self, mode: str) -> Path:
        """
        获取特定模式的会话存储目录

        Args:
            mode: 存储模式 ("llm", "basic", "deep")

        Returns:
            存储目录路径
        """
        mode_dir_map = {
            "llm": "llm",
            "basic": "basicagent",
            "deep": "deepagent",
        }
        dir_name = mode_dir_map.get(mode, mode)
        return self.iris_dir / "sessions" / dir_name

    def ensure_structure(self) -> None:
        """确保 .iris 目录结构存在（自动创建）"""
        for mode in ["llm", "basicagent", "deepagent"]:
            (self.iris_dir / "sessions" / mode).mkdir(parents=True, exist_ok=True)

    def get_storage_dirs_dict(self) -> dict[str, str]:
        """获取兼容 SessionManager 的存储目录字典"""
        return {
            "llm": str(self.get_storage_dir("llm")),
            "basic": str(self.get_storage_dir("basic")),
            "deep": str(self.get_storage_dir("deep")),
        }
```

#### 2.1.2 detector.py 详细设计

```python
# src/core/project/detector.py

from pathlib import Path
from typing import Optional, Tuple

# 项目标记文件（按优先级排序）
PROJECT_MARKERS: Tuple[str, ...] = (
    ".iris",          # iris 项目标记（最高优先级）
    ".git",           # Git 仓库
    "pyproject.toml", # Python 项目
    "package.json",   # Node.js 项目
    "Cargo.toml",     # Rust 项目
    "go.mod",         # Go 项目
    "pom.xml",        # Maven 项目
    "build.gradle",   # Gradle 项目
)

# iris-code 源码项目标记
IRIS_SOURCE_MARKERS: Tuple[str, ...] = (
    "src/core/project",
    "src/application/cli",
    "src/components/shared/memory",
)


def detect_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """
    从指定路径向上遍历，检测项目根目录

    Args:
        start_path: 起始搜索路径，默认为当前工作目录

    Returns:
        项目根目录路径，未找到则返回 None
    """
    current = Path(start_path or Path.cwd()).resolve()

    # 向上遍历目录树
    for parent in [current, *list(current.parents)]:
        for marker in PROJECT_MARKERS:
            marker_path = parent / marker
            if marker_path.exists():
                return parent

    return None


def is_iris_source_project(project_root: Path) -> bool:
    """
    检测是否为 iris-code 源码项目

    Args:
        project_root: 项目根目录

    Returns:
        是否为 iris-code 源码项目
    """
    for marker in IRIS_SOURCE_MARKERS:
        if (project_root / marker).exists():
            return True
    return False
```

#### 2.1.3 metadata.py 详细设计

```python
# src/core/project/metadata.py

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .share import IrisShareDir

logger = logging.getLogger(__name__)


@dataclass
class LastSessionInfo:
    """最后会话信息"""
    mode: str           # "llm" | "basic" | "deep"
    session_id: str


@dataclass
class ProjectMetadata:
    """单个项目的元数据"""
    path: str
    id: str
    name: str
    last_session: Optional[LastSessionInfo] = None
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        if self.last_session:
            data["last_session"] = asdict(self.last_session)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectMetadata":
        """从字典创建"""
        last_session = None
        if data.get("last_session"):
            last_session = LastSessionInfo(**data["last_session"])
        return cls(
            path=data["path"],
            id=data["id"],
            name=data["name"],
            last_session=last_session,
            last_used=data.get("last_used", datetime.now().isoformat()),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


class MetadataManager:
    """全局元数据管理器"""

    VERSION = "1.0"

    def __init__(self, metadata_file: Optional[Path] = None):
        self.metadata_file = metadata_file or IrisShareDir.get_metadata_file()
        self._data: Dict[str, Any] = self._load()

    def _load(self) -> Dict[str, Any]:
        """加载元数据文件"""
        if not self.metadata_file.exists():
            return {"version": self.VERSION, "projects": []}

        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load metadata: {e}")
            return {"version": self.VERSION, "projects": []}

    def _save(self) -> None:
        """保存元数据文件"""
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def get_project(self, project_path: Path) -> Optional[ProjectMetadata]:
        """获取项目元数据"""
        path_str = str(project_path.resolve())
        for proj in self._data.get("projects", []):
            if proj.get("path") == path_str:
                return ProjectMetadata.from_dict(proj)
        return None

    def update_project(
        self,
        project_path: Path,
        project_id: str,
        project_name: str,
        mode: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """更新或创建项目元数据"""
        path_str = str(project_path.resolve())
        now = datetime.now().isoformat()

        # 查找现有项目
        projects = self._data.get("projects", [])
        existing_idx = None
        for idx, proj in enumerate(projects):
            if proj.get("path") == path_str:
                existing_idx = idx
                break

        # 构建新元数据
        if existing_idx is not None:
            meta = ProjectMetadata.from_dict(projects[existing_idx])
            meta.last_used = now
            if mode and session_id:
                meta.last_session = LastSessionInfo(mode=mode, session_id=session_id)
            projects[existing_idx] = meta.to_dict()
        else:
            last_session = None
            if mode and session_id:
                last_session = LastSessionInfo(mode=mode, session_id=session_id)
            meta = ProjectMetadata(
                path=path_str,
                id=project_id,
                name=project_name,
                last_session=last_session,
                last_used=now,
                created_at=now,
            )
            projects.append(meta.to_dict())

        self._data["projects"] = projects
        self._save()

    def list_recent_projects(self, limit: int = 10) -> List[ProjectMetadata]:
        """列出最近使用的项目"""
        projects = [
            ProjectMetadata.from_dict(p)
            for p in self._data.get("projects", [])
        ]
        projects.sort(key=lambda x: x.last_used, reverse=True)
        return projects[:limit]

    def remove_project(self, project_path: Path) -> bool:
        """移除项目记录"""
        path_str = str(project_path.resolve())
        projects = self._data.get("projects", [])
        original_len = len(projects)
        self._data["projects"] = [p for p in projects if p.get("path") != path_str]
        if len(self._data["projects"]) < original_len:
            self._save()
            return True
        return False
```

#### 2.1.4 share.py 详细设计

```python
# src/core/project/share.py

from pathlib import Path


class IrisShareDir:
    """~/.iris/ 共享目录管理"""

    _SHARE_DIR_NAME = ".iris"

    @classmethod
    def get_share_dir(cls) -> Path:
        """
        获取共享目录路径，不存在则创建

        Returns:
            ~/.iris/ 目录路径
        """
        share_dir = Path.home() / cls._SHARE_DIR_NAME
        share_dir.mkdir(parents=True, exist_ok=True)
        return share_dir

    @classmethod
    def get_metadata_file(cls) -> Path:
        """获取元数据文件路径"""
        return cls.get_share_dir() / "metadata.json"

    @classmethod
    def get_global_config_file(cls) -> Path:
        """获取全局配置文件路径"""
        return cls.get_share_dir() / "config.json"

    @classmethod
    def get_global_agent_md_file(cls) -> Path:
        """获取全局 Agent 指令文件路径"""
        return cls.get_share_dir() / "agent.md"
```

---

## 3. 需要修改的现有模块

### 3.1 会话管理模块

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `src/components/shared/memory/session_manager.py` | 接受 `ProjectContext` 参数，动态计算存储路径 | P0 |
| `src/components/shared/memory/basic_agent_checkpointer.py` | 移除硬编码路径，接受动态存储路径 | P0 |
| `src/components/shared/memory/deep_agent_checkpointer.py` | 移除硬编码路径，接受动态存储路径 | P0 |
| `src/components/shared/memory/llm_memory.py` | 移除硬编码路径，接受动态存储路径 | P0 |
| `src/components/shared/storage/session_storage.py` | 无需修改（路径已通过构造函数传入） | - |

#### 3.1.1 SessionManager 修改

**修改前**:
```python
class SessionManager:
    def __init__(
        self,
        *,
        mode: str = "basic",
        storage_dirs: Optional[Dict[str, str]] = None,
    ):
        self.storage_dirs = storage_dirs or {
            "llm": "data/llm/sessions",
            "basic": "data/basicagent/sessions",
            "deep": "data/deepagent/sessions",
        }
```

**修改后**:
```python
from src.core.project import ProjectContext

class SessionManager:
    def __init__(
        self,
        *,
        mode: str = "basic",
        project_context: Optional[ProjectContext] = None,
        storage_dirs: Optional[Dict[str, str]] = None,  # 保留用于向后兼容
    ):
        # 优先使用 project_context
        if project_context:
            self.project_context = project_context
            self.storage_dirs = project_context.get_storage_dirs_dict()
        elif storage_dirs:
            self.project_context = None
            self.storage_dirs = storage_dirs
        else:
            # 默认行为：从当前目录创建上下文
            self.project_context = ProjectContext.from_cwd()
            self.storage_dirs = self.project_context.get_storage_dirs_dict()
```

#### 3.1.2 BasicAgentCheckpointer 修改

**修改前**:
```python
class BasicAgentCheckpointer(BaseCheckpointSaver[int]):
    def __init__(self, storage_dir: str = "data/basicagent/sessions", max_messages: int = 50):
        self.storage = SessionStorage(storage_dir)
```

**修改后**:
```python
class BasicAgentCheckpointer(BaseCheckpointSaver[int]):
    def __init__(
        self,
        storage_dir: Optional[str] = None,
        project_context: Optional[ProjectContext] = None,
        max_messages: int = 50
    ):
        # 优先使用 project_context
        if storage_dir:
            resolved_dir = storage_dir
        elif project_context:
            resolved_dir = str(project_context.get_storage_dir("basic"))
        else:
            # 默认行为：从当前目录创建上下文
            ctx = ProjectContext.from_cwd()
            resolved_dir = str(ctx.get_storage_dir("basic"))

        self.storage = SessionStorage(resolved_dir)
```

#### 3.1.3 DeepAgentCheckpointer 修改

同 BasicAgentCheckpointer，将 `"data/deepagent/sessions"` 替换为动态路径。

#### 3.1.4 LLMMemory 修改

同上，将硬编码路径替换为动态路径。

### 3.2 应用状态模块

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `src/application/cli/state.py` | 新增 `project_context` 字段 | P0 |

**修改**:
```python
@dataclass(slots=True)
class AppState:
    # ... 现有字段 ...

    # 新增项目上下文
    project_context: Optional[ProjectContext] = None
```

### 3.3 CLI 入口模块

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `src/application/cli/main.py` | 初始化时创建 ProjectContext，注入到各组件 | P0 |
| `main.py` | 可能需要调整入口逻辑 | P1 |

**初始化流程修改**:
```python
# src/application/cli/main.py

from src.core.project import ProjectContext, MetadataManager

async def initialize_app() -> AppState:
    # 1. 创建项目上下文
    project_context = ProjectContext.from_cwd()

    # 2. 确保目录结构存在
    project_context.ensure_structure()

    # 3. 更新全局元数据
    metadata_manager = MetadataManager()
    metadata_manager.update_project(
        project_path=project_context.project_path,
        project_id=project_context.project_id,
        project_name=project_context.project_name,
    )

    # 4. 创建 AppState
    state = AppState(
        console=Console(),
        project_context=project_context,
    )

    # 5. 初始化 SessionManager（注入项目上下文）
    state.session_manager = SessionManager(
        mode="basic",
        project_context=project_context,
    )

    # 6. 初始化 Checkpointers（注入项目上下文）
    state.basic_checkpointer = BasicAgentCheckpointer(
        project_context=project_context
    )
    state.deep_checkpointer = DeepAgentCheckpointer(
        project_context=project_context
    )

    # ... 其余初始化逻辑 ...

    return state
```

### 3.4 pyproject.toml 配置

| 文件 | 修改内容 | 优先级 |
|------|---------|--------|
| `pyproject.toml` | 添加 CLI entry point | P0 |

**添加**:
```toml
[project.scripts]
iris = "src.application.cli.main:main"
```

---

## 4. 迁移工具

### 4.1 迁移脚本

| 文件 | 功能 | 优先级 |
|------|------|--------|
| `scripts/migrate_sessions.py` | 将 `data/` 会话迁移到 `.iris/` | P0 |

**迁移脚本设计**:
```python
# scripts/migrate_sessions.py

"""
会话数据迁移脚本

将旧版 data/ 目录中的会话迁移到新版 .iris/ 目录
"""

import shutil
from pathlib import Path
from src.core.project import ProjectContext


def migrate_sessions(project_path: Path, dry_run: bool = True) -> dict:
    """
    迁移会话数据

    Args:
        project_path: 项目根目录
        dry_run: 是否为试运行（不实际移动文件）

    Returns:
        迁移统计信息
    """
    ctx = ProjectContext.from_path(project_path)
    old_data_dir = project_path / "data"
    stats = {"moved": 0, "skipped": 0, "errors": []}

    mode_mapping = {
        "llm": "llm",
        "basicagent": "basicagent",
        "deepagent": "deepagent",
    }

    for old_mode, new_mode in mode_mapping.items():
        old_session_dir = old_data_dir / old_mode / "sessions"
        new_session_dir = ctx.get_storage_dir(new_mode.replace("agent", ""))

        if not old_session_dir.exists():
            continue

        # 确保目标目录存在
        if not dry_run:
            new_session_dir.mkdir(parents=True, exist_ok=True)

        # 迁移文件
        for file_path in old_session_dir.glob("*.json"):
            target_path = new_session_dir / file_path.name

            if target_path.exists():
                stats["skipped"] += 1
                continue

            try:
                if not dry_run:
                    shutil.copy2(file_path, target_path)
                stats["moved"] += 1
                print(f"{'[DRY RUN] ' if dry_run else ''}Migrated: {file_path} -> {target_path}")
            except Exception as e:
                stats["errors"].append(str(e))

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate session data to .iris/")
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project path")
    parser.add_argument("--execute", action="store_true", help="Actually move files (default is dry run)")

    args = parser.parse_args()
    stats = migrate_sessions(args.project, dry_run=not args.execute)

    print(f"\nMigration {'completed' if args.execute else 'preview'}:")
    print(f"  Moved: {stats['moved']}")
    print(f"  Skipped: {stats['skipped']}")
    if stats["errors"]:
        print(f"  Errors: {len(stats['errors'])}")
        for err in stats["errors"]:
            print(f"    - {err}")
```

---

## 5. 任务清单

### 5.1 Phase 1: 核心基础设施 (P0)

- [ ] 创建 `src/core/project/` 模块目录
- [ ] 实现 `share.py` - IrisShareDir
- [ ] 实现 `detector.py` - 项目检测
- [ ] 实现 `context.py` - ProjectContext
- [ ] 实现 `metadata.py` - MetadataManager
- [ ] 编写单元测试

### 5.2 Phase 2: 存储模块改造 (P0)

- [ ] 修改 `SessionManager` - 支持 ProjectContext
- [ ] 修改 `BasicAgentCheckpointer` - 移除硬编码路径
- [ ] 修改 `DeepAgentCheckpointer` - 移除硬编码路径
- [ ] 修改 `LLMMemory` - 移除硬编码路径
- [ ] 编写集成测试

### 5.3 Phase 3: CLI 集成 (P0)

- [ ] 修改 `AppState` - 添加 project_context 字段
- [ ] 修改 CLI 初始化流程 - 注入 ProjectContext
- [ ] 配置 pyproject.toml entry point
- [ ] 测试全局 `iris` 命令

### 5.4 Phase 4: 迁移工具 (P0)

- [ ] 实现迁移脚本 `scripts/migrate_sessions.py`
- [ ] 测试迁移流程
- [ ] 编写迁移文档

### 5.5 Phase 5: 文档和清理 (P1)

- [ ] 更新 README.md
- [ ] 清理旧代码中的注释
- [ ] 添加 `.iris/` 到 `.gitignore` 建议

---

## 6. 依赖关系图

```
┌─────────────────────────────────────────────────────────────┐
│                     Phase 1: 核心基础                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ share.py │  │detector.py│  │context.py│  │metadata.py│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
│       └─────────────┴──────┬──────┴─────────────┘          │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Phase 2: 存储改造                       │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  │
│  │ SessionManager │  │BasicCheckpointer│  │DeepCheckpointer│
│  └────────┬───────┘  └────────┬───────┘  └──────┬───────┘  │
│           │                   │                  │          │
│           └───────────────────┴──────────────────┘          │
│                            │                                │
└────────────────────────────┼────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Phase 3: CLI 集成                       │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────┐      │
│  │ AppState │  │ CLI main.py  │  │ pyproject.toml   │      │
│  └──────────┘  └──────────────┘  └──────────────────┘      │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Phase 4: 迁移工具                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              migrate_sessions.py                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 7. 验收标准

### 7.1 功能验收

- [ ] 在新项目目录下运行 `iris`，自动创建 `.iris/` 目录
- [ ] 会话数据正确存储在 `<project>/.iris/sessions/<mode>/`
- [ ] 切换项目后，会话数据正确隔离
- [ ] `~/.iris/metadata.json` 正确记录项目信息
- [ ] 迁移脚本能正确迁移旧数据

### 7.2 兼容性验收

- [ ] 现有代码在不传入 ProjectContext 时仍能正常工作
- [ ] 现有测试全部通过
- [ ] 迁移后的会话数据可正常读取

### 7.3 性能验收

- [ ] 项目检测时间 < 100ms
- [ ] 元数据读写时间 < 50ms
