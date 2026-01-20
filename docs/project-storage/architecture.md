# 项目存储架构重构设计文档

> 版本: 1.0
> 日期: 2025-01-20
> 状态: 设计阶段

## 1. 概述

本文档描述 iris-code 项目存储架构的重构设计，目标是实现：
1. **项目隔离存储** - 每个项目的会话数据存储在项目本地 `.iris/` 目录
2. **全局 CLI 唤醒** - 在任意项目目录下输入 `iris` 即可启动
3. **项目上下文感知** - 自动识别当前项目并加载对应配置和会话

---

## 2. 现有架构分析

### 2.1 当前存储结构

```
Muti-AI-Agent/
├── data/
│   ├── llm/sessions/
│   │   ├── user_20250120_153045_a1b2c3d4.json
│   │   └── sessions_index.json
│   ├── basicagent/sessions/
│   │   ├── user_*.json
│   │   └── sessions_index.json
│   └── deepagent/sessions/
│       ├── user_*.json
│       └── sessions_index.json
└── config/
    └── (配置文件)
```

### 2.2 现有问题

| 问题 | 描述 | 影响 |
|------|------|------|
| **无项目隔离** | 所有项目的会话混在同一个 `data/` 目录 | 无法区分不同项目的上下文 |
| **路径硬编码** | 存储路径在多个模块中硬编码 | 难以支持动态项目路径 |
| **单一运行位置** | 只能在本项目目录下运行 | 无法作为通用工具使用 |
| **缺乏项目感知** | 没有项目检测和上下文管理机制 | 无法加载项目级配置 |

### 2.3 硬编码路径位置

| 模块 | 文件 | 硬编码路径 |
|------|------|-----------|
| `SessionStorage` | `src/components/shared/storage/session_storage.py:26` | `data/sessions` |
| `SessionManager` | `src/components/shared/memory/session_manager.py:34-37` | `data/{mode}/sessions` |
| `BasicAgentCheckpointer` | `src/components/shared/memory/basic_agent_checkpointer.py:25` | `data/basicagent/sessions` |
| `DeepAgentCheckpointer` | `src/components/shared/memory/deep_agent_checkpointer.py:28` | `data/deepagent/sessions` |
| `LLMMemory` | `src/components/shared/memory/llm_memory.py` | `data/llm/sessions` |

---

## 3. 新架构设计

### 3.1 设计原则

1. **项目本地存储** - 会话数据存储在项目 `.iris/` 目录，跟随项目移动
2. **配置优先级** - 环境变量 > 项目配置 > 用户配置 > 默认值
3. **向后兼容** - 提供迁移工具，支持旧数据迁移
4. **单一职责** - 新增 `ProjectContext` 统一管理项目上下文
5. **开闭原则** - 存储路径通过依赖注入，便于扩展

### 3.2 新存储结构

#### 3.2.1 项目级存储 (`<project>/.iris/`)

```
<project_root>/
├── .iris/                           # 项目配置和会话存储
│   ├── config.json                  # 项目级配置（可选）
│   ├── agent.md                     # 项目级 Agent 指令（可选）
│   ├── sessions/
│   │   ├── llm/
│   │   │   ├── user_*.json         # 会话文件
│   │   │   └── sessions_index.json  # 索引文件
│   │   ├── basicagent/
│   │   │   ├── user_*.json
│   │   │   └── sessions_index.json
│   │   └── deepagent/
│   │       ├── user_*.json
│   │       └── sessions_index.json
│   └── skills/                      # 项目级自定义技能（未来扩展）
│
└── (项目其他文件...)
```

#### 3.2.2 用户级存储 (`~/.iris/`)

```
~/.iris/
├── config.json                      # 用户全局配置
├── metadata.json                    # 项目元数据索引
└── agent.md                         # 用户级 Agent 指令（可选）
```

#### 3.2.3 元数据文件结构 (`~/.iris/metadata.json`)

```json
{
  "version": "1.0",
  "projects": [
    {
      "path": "/path/to/project",
      "id": "my-project_a1b2c3d4",
      "name": "my-project",
      "last_session": {
        "mode": "deep",
        "session_id": "user_20250120_153045_a1b2c3d4"
      },
      "last_used": "2025-01-20T15:30:45.000000",
      "created_at": "2025-01-15T10:00:00.000000"
    }
  ]
}
```

### 3.3 项目识别规则

#### 3.3.1 项目根目录检测

通过以下标记文件识别项目根目录（向上遍历）：

```python
PROJECT_MARKERS = (
    ".git",           # Git 仓库
    "pyproject.toml", # Python 项目
    "package.json",   # Node.js 项目
    "Cargo.toml",     # Rust 项目
    "go.mod",         # Go 项目
    ".iris",          # iris 项目标记
)
```

#### 3.3.2 项目 ID 生成规则

```python
def generate_project_id(project_path: Path) -> str:
    """
    生成项目唯一标识: {safe_dir_name}_{hash[:8]}

    示例:
    - /home/user/my-project → "my-project_a1b2c3d4"
    - D:\Projects\Muti-AI-Agent → "Muti-AI-Agent_e5f6g7h8"
    """
    import hashlib
    import re

    path_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:8]
    dir_name = project_path.name
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dir_name)
    return f"{safe_name}_{path_hash}"
```

### 3.4 配置优先级

```
┌─────────────────────────────────────────┐
│ 1. 环境变量 (.env)                      │  最高优先级
├─────────────────────────────────────────┤
│ 2. 项目配置 (<project>/.iris/config.json)│
├─────────────────────────────────────────┤
│ 3. 用户配置 (~/.iris/config.json)       │
├─────────────────────────────────────────┤
│ 4. 代码默认值                           │  最低优先级
└─────────────────────────────────────────┘
```

### 3.5 文件操作权限控制

当 iris 在某个项目中运行时，文件操作权限遵循配置驱动原则：

**默认配置（严格模式）**:
```json
{
  "filesystem": {
    "allowed_paths": ["${PROJECT_ROOT}"],
    "excluded_paths": [
      "${PROJECT_ROOT}/.git",
      "${PROJECT_ROOT}/.env",
      "${PROJECT_ROOT}/.iris/sessions"
    ]
  }
}
```

**可选配置（扩展权限）**:
```json
{
  "filesystem": {
    "allowed_paths": [
      "${PROJECT_ROOT}",
      "${HOME}/shared-libs"
    ],
    "allow_iris_source": false
  }
}
```

---

## 4. 新模块设计

### 4.1 模块结构

```
src/core/project/
├── __init__.py
├── context.py          # ProjectContext - 核心上下文类
├── detector.py         # 项目检测和识别
├── metadata.py         # 全局元数据管理
├── paths.py            # 路径解析和标准化
└── share.py            # ~/.iris/ 共享目录管理
```

### 4.2 核心类设计

#### 4.2.1 ProjectContext

```python
@dataclass
class ProjectContext:
    """项目上下文，统一管理项目相关路径和配置"""

    project_path: Path              # 项目根目录绝对路径
    project_id: str                 # 项目唯一标识 (dir_name_hash)
    project_name: str               # 项目目录名
    is_iris_source: bool            # 是否是 iris-code 源码项目

    @classmethod
    def from_cwd(cls) -> "ProjectContext":
        """从当前工作目录创建上下文"""
        ...

    @classmethod
    def from_path(cls, path: Path) -> "ProjectContext":
        """从指定路径创建上下文"""
        ...

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
        """获取特定模式的会话存储目录"""
        return self.iris_dir / "sessions" / mode

    def ensure_structure(self) -> None:
        """确保 .iris 目录结构存在（自动创建）"""
        for mode in ["llm", "basicagent", "deepagent"]:
            (self.iris_dir / "sessions" / mode).mkdir(parents=True, exist_ok=True)
```

#### 4.2.2 ProjectMetadata

```python
@dataclass
class ProjectMetadata:
    """单个项目的元数据"""
    path: str
    id: str
    name: str
    last_session: Optional[LastSessionInfo]
    last_used: str
    created_at: str

@dataclass
class LastSessionInfo:
    """最后会话信息"""
    mode: str           # "llm" | "basic" | "deep"
    session_id: str

class MetadataManager:
    """全局元数据管理器"""

    def __init__(self, metadata_file: Path = None):
        self.metadata_file = metadata_file or Path.home() / ".iris" / "metadata.json"

    def get_project(self, project_path: Path) -> Optional[ProjectMetadata]:
        """获取项目元数据"""
        ...

    def update_project(self, context: ProjectContext, mode: str, session_id: str) -> None:
        """更新项目的最后会话信息"""
        ...

    def list_recent_projects(self, limit: int = 10) -> List[ProjectMetadata]:
        """列出最近使用的项目"""
        ...
```

#### 4.2.3 IrisShareDir

```python
class IrisShareDir:
    """~/.iris/ 共享目录管理"""

    @staticmethod
    def get_share_dir() -> Path:
        """获取共享目录路径，不存在则创建"""
        share_dir = Path.home() / ".iris"
        share_dir.mkdir(parents=True, exist_ok=True)
        return share_dir

    @staticmethod
    def get_metadata_file() -> Path:
        """获取元数据文件路径"""
        return IrisShareDir.get_share_dir() / "metadata.json"

    @staticmethod
    def get_global_config_file() -> Path:
        """获取全局配置文件路径"""
        return IrisShareDir.get_share_dir() / "config.json"
```

---

## 5. 与现有模块的集成

### 5.1 SessionManager 改造

**改造前**:
```python
class SessionManager:
    def __init__(self, *, mode: str = "basic", storage_dirs: Optional[Dict[str, str]] = None):
        self.storage_dirs = storage_dirs or {
            "llm": "data/llm/sessions",
            "basic": "data/basicagent/sessions",
            "deep": "data/deepagent/sessions",
        }
```

**改造后**:
```python
class SessionManager:
    def __init__(
        self,
        *,
        mode: str = "basic",
        project_context: Optional[ProjectContext] = None
    ):
        self.project_context = project_context or ProjectContext.from_cwd()
        self.storage_dirs = {
            "llm": str(self.project_context.get_storage_dir("llm")),
            "basic": str(self.project_context.get_storage_dir("basicagent")),
            "deep": str(self.project_context.get_storage_dir("deepagent")),
        }
```

### 5.2 AppState 改造

**新增字段**:
```python
@dataclass(slots=True)
class AppState:
    # ... 现有字段 ...

    # 新增项目上下文
    project_context: Optional[ProjectContext] = None
```

### 5.3 CLI 初始化流程改造

```python
# src/application/cli/main.py

async def main():
    # 1. 检测并创建项目上下文
    project_context = ProjectContext.from_cwd()
    project_context.ensure_structure()  # 自动创建 .iris/ 目录

    # 2. 更新全局元数据
    metadata_manager = MetadataManager()
    metadata_manager.touch_project(project_context)

    # 3. 初始化 AppState（注入项目上下文）
    state = AppState(project_context=project_context)

    # 4. 初始化 SessionManager（使用项目上下文的存储路径）
    state.session_manager = SessionManager(
        mode="basic",
        project_context=project_context
    )

    # ... 其余初始化逻辑 ...
```

---

## 6. CLI 全局入口设计

### 6.1 pyproject.toml 配置

```toml
[project.scripts]
iris = "src.application.cli.main:main"
```

### 6.2 安装方式

```bash
# 开发模式安装（代码修改立即生效）
cd /path/to/Muti-AI-Agent
pip install -e .

# 验证安装
iris --help
```

### 6.3 使用方式

```bash
# 在任意项目目录下运行
cd /path/to/my-project
iris

# 首次运行会自动创建 .iris/ 目录
# 会话数据存储在 /path/to/my-project/.iris/sessions/
```

---

## 7. 架构对比图

### 7.1 改造前

```
┌─────────────────────────────────────────────────────────────┐
│                     Muti-AI-Agent/                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   CLI       │───▶│ SessionMgr │───▶│   Storage   │     │
│  │   main.py   │    │ (硬编码路径)│    │ data/...    │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                                              │              │
│                     ┌────────────────────────┘              │
│                     ▼                                       │
│         data/llm/sessions/                                  │
│         data/basicagent/sessions/                           │
│         data/deepagent/sessions/                            │
│         (所有项目混在一起)                                   │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 改造后

```
┌─────────────────────────────────────────────────────────────┐
│                        ~/.iris/                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  metadata.json (项目索引)                            │   │
│  │  config.json (全局配置)                              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 记录项目信息
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Project A/.iris/                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   iris      │───▶│ ProjectCtx  │───▶│ SessionMgr  │     │
│  │   (全局)    │    │ (动态路径)  │    │ (注入路径)  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│                              │                              │
│                              ▼                              │
│              .iris/sessions/llm/                            │
│              .iris/sessions/basicagent/                     │
│              .iris/sessions/deepagent/                      │
│              (项目独立存储)                                  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Project B/.iris/                        │
│              (另一个项目的独立存储)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. 风险和缓解措施

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 现有会话数据丢失 | 用户历史记录消失 | 提供迁移工具，自动迁移 `data/` 到 `.iris/` |
| `.iris/` 被误删除 | 项目会话丢失 | 可添加到 `.gitignore`；元数据在 `~/.iris/` 有备份 |
| 项目路径变更 | 元数据失效 | 通过项目 ID 关联，支持重新检测 |
| 多用户共享项目 | 会话冲突 | `.iris/` 建议加入 `.gitignore`，每个用户独立会话 |

---

## 9. 参考设计

| 项目 | 存储位置 | 特点 |
|------|---------|------|
| **kimi-cli** | `~/.kimi/sessions/<hash>/` | 全局存储，路径哈希隔离 |
| **deepagents-cli** | `<project>/.deepagents/` | 项目本地存储 |
| **Claude Code** | `<project>/.claude/` | 项目本地配置 |
| **iris-code (新)** | `<project>/.iris/` | 项目本地存储 + 全局元数据 |

---

## 10. 下一步

1. 阅读 [goal-duty.md](./goal-duty.md) 了解具体修改点
2. 阅读 [dfd-interface.md](./dfd-interface.md) 了解数据流和接口
3. 阅读 [migration.md](./migration.md) 了解迁移方案
4. 阅读 [tests.md](./tests.md) 了解测试计划
