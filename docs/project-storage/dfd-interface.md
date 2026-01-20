# 数据流与接口说明

> 版本: 1.0
> 日期: 2025-01-20
> 状态: 设计阶段

## 1. 概述

本文档描述项目存储重构后的数据流和模块接口设计。

---

## 2. 数据流图 (DFD)

### 2.1 Level 0: 系统上下文图

```
                              ┌─────────────────┐
                              │     用户        │
                              └────────┬────────┘
                                       │
                         iris 命令 / 对话输入
                                       │
                                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                          iris-code 系统                          │
│                                                                  │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────────┐   │
│  │  CLI     │───▶│  Core Engine │───▶│  Storage Layer       │   │
│  │  Layer   │    │  (LLM/Agent) │    │  (.iris/ + ~/.iris/) │   │
│  └──────────┘    └──────────────┘    └──────────────────────┘   │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │     外部服务 (LLM APIs)          │
                    └──────────────────────────────────┘
```

### 2.2 Level 1: 主要数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              iris-code 系统                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐                                                                │
│  │ 用户    │                                                                │
│  └────┬────┘                                                                │
│       │ 1. iris 命令                                                        │
│       ▼                                                                     │
│  ┌─────────────────┐                                                        │
│  │ 1.0 CLI 入口    │                                                        │
│  │ (main.py)       │                                                        │
│  └────────┬────────┘                                                        │
│           │ 2. 当前工作目录                                                  │
│           ▼                                                                 │
│  ┌─────────────────┐      3. 项目路径      ┌─────────────────┐              │
│  │ 2.0 项目检测    │─────────────────────▶│ D1 项目文件系统  │              │
│  │ (ProjectContext)│◀─────────────────────│ (检测标记文件)   │              │
│  └────────┬────────┘      项目根路径       └─────────────────┘              │
│           │                                                                 │
│           │ 4. ProjectContext                                               │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 3.0 元数据管理  │                                                        │
│  │ (MetadataManager)│                                                       │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           │ 5. 读取/更新项目记录                                             │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ D2 元数据存储   │                                                        │
│  │ (~/.iris/       │                                                        │
│  │  metadata.json) │                                                        │
│  └─────────────────┘                                                        │
│           │                                                                 │
│           │ 6. 项目上下文 + 最后会话信息                                     │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 4.0 会话管理    │                                                        │
│  │ (SessionManager)│                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           │ 7. 存储路径                                                     │
│           ▼                                                                 │
│  ┌─────────────────┐      8. 读写会话      ┌─────────────────┐              │
│  │ 5.0 会话存储    │─────────────────────▶│ D3 会话文件      │              │
│  │ (SessionStorage)│◀─────────────────────│ (<project>/.iris/│              │
│  └────────┬────────┘      会话数据         │  sessions/)      │              │
│           │                                └─────────────────┘              │
│           │ 9. 历史消息                                                     │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ 6.0 对话引擎    │                                                        │
│  │ (LLM/Agent)     │                                                        │
│  └────────┬────────┘                                                        │
│           │                                                                 │
│           │ 10. API 请求                                                    │
│           ▼                                                                 │
│  ┌─────────────────┐                                                        │
│  │ D4 外部 LLM API │                                                        │
│  │ (Zhipu/OpenAI)  │                                                        │
│  └─────────────────┘                                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Level 2: 详细数据流

#### 2.3.1 项目初始化流程

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           项目初始化数据流                                  │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│    用户                                                                    │
│      │                                                                     │
│      │ cd /path/to/project && iris                                         │
│      ▼                                                                     │
│  ┌──────────┐                                                              │
│  │ CLI 入口 │                                                              │
│  └────┬─────┘                                                              │
│       │                                                                    │
│       │ Path.cwd()                                                         │
│       ▼                                                                    │
│  ┌───────────────────┐                                                     │
│  │ ProjectContext.   │                                                     │
│  │ from_cwd()        │                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ 向上遍历目录                                                   │
│            ▼                                                               │
│  ┌───────────────────┐     检查 .git, pyproject.toml 等                    │
│  │ detect_project_   │─────────────────────────────────▶ 文件系统          │
│  │ root()            │◀───────────────────────────────── 返回项目根路径    │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ project_root                                                  │
│            ▼                                                               │
│  ┌───────────────────┐                                                     │
│  │ generate_project_ │                                                     │
│  │ id()              │                                                     │
│  │ → name_hash8      │                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ ProjectContext 对象                                           │
│            ▼                                                               │
│  ┌───────────────────┐                                                     │
│  │ ensure_structure()│                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ mkdir -p .iris/sessions/{llm,basicagent,deepagent}            │
│            ▼                                                               │
│       .iris/ 目录已创建                                                    │
│            │                                                               │
│            │ 更新元数据                                                    │
│            ▼                                                               │
│  ┌───────────────────┐     读取/写入      ┌─────────────────────┐         │
│  │ MetadataManager.  │───────────────────▶│ ~/.iris/metadata.json│         │
│  │ update_project()  │◀───────────────────│                     │         │
│  └───────────────────┘                    └─────────────────────┘         │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 2.3.2 会话恢复流程

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           会话恢复数据流                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌───────────────────┐                                                     │
│  │ SessionManager.   │                                                     │
│  │ prompt_for_       │                                                     │
│  │ session_choice()  │                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ 1. 获取存储路径                                                │
│            ▼                                                               │
│  ┌───────────────────┐                                                     │
│  │ ProjectContext.   │                                                     │
│  │ get_storage_dir() │                                                     │
│  │ → .iris/sessions/ │                                                     │
│  │   {mode}/         │                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ 2. 读取会话索引                                                │
│            ▼                                                               │
│  ┌───────────────────┐     读取           ┌─────────────────────┐         │
│  │ SessionStorage.   │───────────────────▶│ sessions_index.json │         │
│  │ list_sessions()   │◀───────────────────│                     │         │
│  └─────────┬─────────┘     会话列表       └─────────────────────┘         │
│            │                                                               │
│            │ 3. 检查元数据中的最后会话                                      │
│            ▼                                                               │
│  ┌───────────────────┐     读取           ┌─────────────────────┐         │
│  │ MetadataManager.  │───────────────────▶│ ~/.iris/metadata.json│         │
│  │ get_project()     │◀───────────────────│ → last_session      │         │
│  └─────────┬─────────┘                    └─────────────────────┘         │
│            │                                                               │
│            │ 4. 提示用户选择                                                │
│            ▼                                                               │
│       用户选择恢复/新建                                                    │
│            │                                                               │
│            │ 5. 加载会话消息                                                │
│            ▼                                                               │
│  ┌───────────────────┐     读取           ┌─────────────────────┐         │
│  │ SessionStorage.   │───────────────────▶│ user_*.json         │         │
│  │ load_session()    │◀───────────────────│                     │         │
│  └───────────────────┘     消息列表       └─────────────────────┘         │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 2.3.3 对话保存流程

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           对话保存数据流                                    │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│  ┌───────────────────┐                                                     │
│  │ 对话引擎返回响应  │                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ HumanMessage + AIMessage                                      │
│            ▼                                                               │
│  ┌───────────────────┐                                                     │
│  │ Checkpointer.     │                                                     │
│  │ persist_from_     │                                                     │
│  │ runtime()         │                                                     │
│  └─────────┬─────────┘                                                     │
│            │                                                               │
│            │ 1. 过滤消息（只保留 Human/AI）                                  │
│            │ 2. 去重                                                       │
│            │ 3. 裁剪（超过限制时）                                          │
│            ▼                                                               │
│  ┌───────────────────┐     写入           ┌─────────────────────┐         │
│  │ SessionStorage.   │───────────────────▶│ user_*.json         │         │
│  │ save_session()    │                    │ sessions_index.json │         │
│  └─────────┬─────────┘                    └─────────────────────┘         │
│            │                                                               │
│            │ 4. 更新元数据                                                  │
│            ▼                                                               │
│  ┌───────────────────┐     写入           ┌─────────────────────┐         │
│  │ MetadataManager.  │───────────────────▶│ ~/.iris/metadata.json│         │
│  │ update_project()  │                    │ → last_session      │         │
│  └───────────────────┘                    └─────────────────────┘         │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. 接口定义

### 3.1 ProjectContext 接口

```python
class ProjectContext:
    """项目上下文接口"""

    # 属性
    project_path: Path          # 项目根目录绝对路径
    project_id: str             # 项目唯一标识
    project_name: str           # 项目目录名
    is_iris_source: bool        # 是否是 iris-code 源码项目

    # 类方法
    @classmethod
    def from_cwd(cls) -> "ProjectContext":
        """从当前工作目录创建上下文"""
        ...

    @classmethod
    def from_path(cls, path: Path) -> "ProjectContext":
        """从指定路径创建上下文"""
        ...

    # 实例属性
    @property
    def iris_dir(self) -> Path:
        """项目 .iris 目录路径"""
        ...

    @property
    def config_file(self) -> Path:
        """项目配置文件路径"""
        ...

    @property
    def agent_md_file(self) -> Path:
        """项目 Agent 指令文件路径"""
        ...

    # 实例方法
    def get_storage_dir(self, mode: str) -> Path:
        """
        获取特定模式的会话存储目录

        Args:
            mode: "llm" | "basic" | "deep"

        Returns:
            存储目录路径
        """
        ...

    def ensure_structure(self) -> None:
        """确保 .iris 目录结构存在"""
        ...

    def get_storage_dirs_dict(self) -> dict[str, str]:
        """
        获取兼容 SessionManager 的存储目录字典

        Returns:
            {"llm": "...", "basic": "...", "deep": "..."}
        """
        ...
```

### 3.2 MetadataManager 接口

```python
class MetadataManager:
    """全局元数据管理器接口"""

    def __init__(self, metadata_file: Optional[Path] = None):
        """
        初始化元数据管理器

        Args:
            metadata_file: 元数据文件路径，默认 ~/.iris/metadata.json
        """
        ...

    def get_project(self, project_path: Path) -> Optional[ProjectMetadata]:
        """
        获取项目元数据

        Args:
            project_path: 项目根目录路径

        Returns:
            项目元数据，不存在返回 None
        """
        ...

    def update_project(
        self,
        project_path: Path,
        project_id: str,
        project_name: str,
        mode: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> None:
        """
        更新或创建项目元数据

        Args:
            project_path: 项目根目录路径
            project_id: 项目唯一标识
            project_name: 项目名称
            mode: 最后使用的模式 ("llm"|"basic"|"deep")
            session_id: 最后的会话 ID
        """
        ...

    def list_recent_projects(self, limit: int = 10) -> List[ProjectMetadata]:
        """
        列出最近使用的项目

        Args:
            limit: 返回数量限制

        Returns:
            按最后使用时间倒序排列的项目列表
        """
        ...

    def remove_project(self, project_path: Path) -> bool:
        """
        移除项目记录

        Args:
            project_path: 项目根目录路径

        Returns:
            是否成功移除
        """
        ...
```

### 3.3 SessionManager 接口（修改后）

```python
class SessionManager:
    """会话管理器接口（修改后）"""

    def __init__(
        self,
        *,
        mode: str = "basic",
        project_context: Optional[ProjectContext] = None,
        storage_dirs: Optional[Dict[str, str]] = None  # 向后兼容
    ):
        """
        初始化会话管理器

        Args:
            mode: 初始模式 ("llm"|"basic"|"deep")
            project_context: 项目上下文（优先使用）
            storage_dirs: 存储目录映射（向后兼容）
        """
        ...

    # 其余接口保持不变
```

### 3.4 Checkpointer 接口（修改后）

```python
class BasicAgentCheckpointer:
    """Basic Agent 检查点保存器接口（修改后）"""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        project_context: Optional[ProjectContext] = None,
        max_messages: int = 50
    ):
        """
        初始化检查点保存器

        Args:
            storage_dir: 存储目录路径（向后兼容）
            project_context: 项目上下文（优先使用）
            max_messages: 最大消息数量
        """
        ...

    # 其余接口保持不变


class DeepAgentCheckpointer:
    """Deep Agent 检查点保存器接口（修改后）"""

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        project_context: Optional[ProjectContext] = None,
        runtime_checkpointer: Optional[MemorySaver] = None,
        max_messages: int = 100
    ):
        """
        初始化检查点保存器

        Args:
            storage_dir: 存储目录路径（向后兼容）
            project_context: 项目上下文（优先使用）
            runtime_checkpointer: 运行时检查点保存器
            max_messages: 最大消息数量
        """
        ...

    # 其余接口保持不变
```

---

## 4. 数据结构

### 4.1 ProjectMetadata

```python
@dataclass
class LastSessionInfo:
    """最后会话信息"""
    mode: str           # "llm" | "basic" | "deep"
    session_id: str     # 会话 ID


@dataclass
class ProjectMetadata:
    """项目元数据"""
    path: str                               # 项目绝对路径
    id: str                                 # 项目唯一标识
    name: str                               # 项目目录名
    last_session: Optional[LastSessionInfo] # 最后会话信息
    last_used: str                          # 最后使用时间 (ISO 8601)
    created_at: str                         # 创建时间 (ISO 8601)
```

### 4.2 metadata.json 文件格式

```json
{
  "version": "1.0",
  "projects": [
    {
      "path": "/home/user/my-project",
      "id": "my-project_a1b2c3d4",
      "name": "my-project",
      "last_session": {
        "mode": "deep",
        "session_id": "user_20250120_153045_a1b2c3d4"
      },
      "last_used": "2025-01-20T15:30:45.123456",
      "created_at": "2025-01-15T10:00:00.000000"
    },
    {
      "path": "D:\\Projects\\Langchain\\Muti-AI-Agent",
      "id": "Muti-AI-Agent_e5f6g7h8",
      "name": "Muti-AI-Agent",
      "last_session": {
        "mode": "basic",
        "session_id": "user_20250120_143022_b2c3d4e5"
      },
      "last_used": "2025-01-20T14:30:22.654321",
      "created_at": "2025-01-10T09:00:00.000000"
    }
  ]
}
```

### 4.3 会话文件格式（保持不变）

```json
{
  "session_id": "user_20250120_153045_a1b2c3d4",
  "messages": [
    {
      "type": "HumanMessage",
      "content": "你好",
      "timestamp": "2025-01-20T15:30:45.123456"
    },
    {
      "type": "AIMessage",
      "content": "你好！有什么可以帮助你的吗？",
      "timestamp": "2025-01-20T15:30:46.234567"
    }
  ],
  "message_count": 2,
  "created_at": "2025-01-20T15:30:45.000000",
  "updated_at": "2025-01-20T15:30:46.234567",
  "metadata": {}
}
```

---

## 5. 错误处理

### 5.1 项目检测失败

```python
# 当无法检测到项目根目录时
try:
    project_root = detect_project_root(path)
except Exception as e:
    logger.warning(f"Project detection failed: {e}")
    # 降级：使用当前目录作为项目根
    project_root = path.resolve()
```

### 5.2 元数据读写失败

```python
# 元数据读取失败时返回空结构
def _load(self) -> Dict[str, Any]:
    try:
        with open(self.metadata_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to load metadata: {e}")
        return {"version": self.VERSION, "projects": []}

# 元数据写入失败时记录日志但不中断
def _save(self) -> None:
    try:
        with open(self.metadata_file, "w") as f:
            json.dump(self._data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save metadata: {e}")
        # 不抛出异常，避免影响主流程
```

### 5.3 目录创建失败

```python
def ensure_structure(self) -> None:
    try:
        for mode in ["llm", "basicagent", "deepagent"]:
            (self.iris_dir / "sessions" / mode).mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        logger.error(f"Permission denied creating .iris directory: {e}")
        raise RuntimeError(f"Cannot create .iris directory: {e}")
    except OSError as e:
        logger.error(f"Failed to create .iris directory: {e}")
        raise RuntimeError(f"Cannot create .iris directory: {e}")
```

---

## 6. 性能考虑

### 6.1 项目检测优化

```python
# 缓存项目检测结果（单次运行内）
_project_root_cache: Dict[Path, Optional[Path]] = {}

def detect_project_root(start_path: Path) -> Optional[Path]:
    resolved = start_path.resolve()
    if resolved in _project_root_cache:
        return _project_root_cache[resolved]

    result = _detect_project_root_impl(resolved)
    _project_root_cache[resolved] = result
    return result
```

### 6.2 元数据延迟加载

```python
class MetadataManager:
    def __init__(self, metadata_file: Path):
        self.metadata_file = metadata_file
        self._data: Optional[Dict] = None  # 延迟加载

    @property
    def data(self) -> Dict:
        if self._data is None:
            self._data = self._load()
        return self._data
```

### 6.3 目录存在性检查优化

```python
def ensure_structure(self) -> None:
    # 只在目录不存在时创建
    for mode in ["llm", "basicagent", "deepagent"]:
        session_dir = self.iris_dir / "sessions" / mode
        if not session_dir.exists():
            session_dir.mkdir(parents=True, exist_ok=True)
```

---

## 7. 安全考虑

### 7.1 路径验证

```python
def _validate_project_path(path: Path) -> Path:
    """验证并规范化项目路径"""
    resolved = path.resolve()

    # 防止目录穿越
    if ".." in str(resolved):
        raise ValueError("Path traversal not allowed")

    # 确保是目录
    if resolved.exists() and not resolved.is_dir():
        raise ValueError("Path must be a directory")

    return resolved
```

### 7.2 元数据文件权限

```python
def _save(self) -> None:
    # 确保元数据目录权限正确（仅用户可读写）
    self.metadata_file.parent.mkdir(parents=True, exist_ok=True)

    with open(self.metadata_file, "w", encoding="utf-8") as f:
        json.dump(self._data, f, indent=2, ensure_ascii=False)

    # 设置文件权限（Unix 系统）
    if hasattr(os, 'chmod'):
        os.chmod(self.metadata_file, 0o600)
```

### 7.3 项目 ID 清理

```python
def _generate_project_id(project_path: Path) -> str:
    # 清理目录名，只保留安全字符
    dir_name = project_path.name
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', dir_name)

    # 限制长度
    if len(safe_name) > 50:
        safe_name = safe_name[:50]

    path_hash = hashlib.md5(str(project_path.resolve()).encode()).hexdigest()[:8]
    return f"{safe_name}_{path_hash}"
```
