# 工具API参考与实施步骤

## 1. 工具API快速参考

### 1.1 虚拟文件系统工具

#### ls / list_files

**功能：** 列出虚拟文件系统中的所有文件

**签名：**
```python
def ls(
    runtime: ToolRuntime[None, FilesystemState],
    path: str | None = None
) -> list[str]
```

**参数：**
- `path`（可选）：目录前缀过滤

**返回：** 文件路径列表

**示例：**
```python
# 列出所有文件
ls()  # ["/workspace/file1.txt", "/memories/notes.md", ...]

# 列出指定目录
ls(path="/workspace")  # ["/workspace/file1.txt", "/workspace/file2.py"]
```

---

#### read_file

**功能：** 读取虚拟文件内容

**签名：**
```python
def read_file(
    file_path: str,
    runtime: ToolRuntime[None, FilesystemState],
    offset: int = 0,
    limit: int = 2000
) -> str
```

**参数：**
- `file_path`：文件路径（绝对路径，以 `/` 开头）
- `offset`：起始行号（从 0 开始）
- `limit`：读取行数

**返回：** 带行号的文件内容

**示例：**
```python
# 读取整个文件
read_file("/workspace/code.py")

# 分页读取
read_file("/workspace/large.txt", offset=0, limit=100)    # 前100行
read_file("/workspace/large.txt", offset=100, limit=100)  # 第101-200行
```

---

#### write_file

**功能：** 创建新的虚拟文件

**签名：**
```python
def write_file(
    file_path: str,
    content: str,
    runtime: ToolRuntime[None, FilesystemState]
) -> Command | str
```

**参数：**
- `file_path`：文件路径
- `content`：文件内容

**返回：** 成功消息或错误提示

**示例：**
```python
# 创建普通文件
write_file("/workspace/notes.txt", "Hello World")

# 创建长期记忆文件
write_file("/memories/preferences.json", '{"theme": "dark"}')
```

---

#### edit_file

**功能：** 编辑已有虚拟文件

**签名：**
```python
def edit_file(
    file_path: str,
    old_string: str,
    new_string: str,
    runtime: ToolRuntime[None, FilesystemState],
    replace_all: bool = False
) -> Command | str
```

**参数：**
- `file_path`：文件路径
- `old_string`：要替换的字符串
- `new_string`：替换为的字符串
- `replace_all`：是否替换所有匹配

**返回：** 成功消息或错误提示

**示例：**
```python
# 单次替换
edit_file("/workspace/code.py", "old_name", "new_name")

# 全部替换
edit_file("/workspace/config.yaml", "localhost", "production.com", replace_all=True)
```

---

### 1.2 真实文件系统工具

#### list_real_files

**功能：** 列出指定目录下的真实文件

**签名：**
```python
def list_real_files(
    directory_path: str | None = None,
    recursive: bool = False,
    include_hidden: bool = False
) -> list[str]
```

**参数：**
- `directory_path`：目录路径（默认为项目根目录）
- `recursive`：是否递归列出子目录
- `include_hidden`：是否包含隐藏文件

**返回：** 文件路径列表

**示例：**
```python
# 列出项目根目录文件
list_real_files()

# 递归列出src目录所有文件
list_real_files("./src", recursive=True)
```

---

#### read_real_file

**功能：** 读取真实文件内容

**签名：**
```python
def read_real_file(
    file_path: str,
    offset: int = 0,
    limit: int = 2000,
    encoding: str = "utf-8"
) -> str
```

**参数：**
- `file_path`：文件路径
- `offset`：起始行号（从 0 开始）
- `limit`：读取行数
- `encoding`：文件编码

**返回：** 带行号的文件内容

**示例：**
```python
# 读取整个文件
read_real_file("./src/main.py")

# 分页读取大文件
read_real_file("./logs/app.log", offset=0, limit=100)

# 指定编码
read_real_file("./data.csv", encoding="gbk")
```

---

#### glob_real_files

**功能：** 按通配符模式搜索真实文件

**签名：**
```python
def glob_real_files(
    pattern: str,
    base_path: str | None = None,
    recursive: bool = True
) -> list[str]
```

**参数：**
- `pattern`：Glob 模式
- `base_path`：搜索基础路径（默认为项目根目录）
- `recursive`：是否递归搜索

**返回：** 匹配的文件路径列表

**Glob 模式语法：**
- `*`：匹配任意字符（不跨目录）
- `**`：递归匹配目录
- `?`：匹配单个字符
- `[abc]`：匹配字符集合

**示例：**
```python
# 查找所有Python文件
glob_real_files("**/*.py")

# 查找src目录下的测试文件
glob_real_files("**/test_*.py", base_path="./src")

# 查找特定扩展名
glob_real_files("**/*.{json,yaml,yml}")
```

---

#### grep_real_files

**功能：** 在真实文件内容中搜索文本模式

**签名：**
```python
def grep_real_files(
    pattern: str,
    file_pattern: str | None = None,
    base_path: str | None = None,
    case_sensitive: bool = True,
    context_lines: int = 0,
    max_results: int = 100
) -> str
```

**参数：**
- `pattern`：正则表达式模式
- `file_pattern`：文件过滤模式（可选）
- `base_path`：搜索基础路径（可选）
- `case_sensitive`：是否区分大小写
- `context_lines`：上下文行数
- `max_results`：最大结果数

**返回：** 格式化的搜索结果

**示例：**
```python
# 搜索函数定义
grep_real_files(r"def \w+\(", file_pattern="**/*.py")

# 不区分大小写搜索
grep_real_files("TODO", case_sensitive=False)

# 显示上下文
grep_real_files("class.*Agent", context_lines=2)
```

---

## 2. 最小可用版本实施步骤

### 2.1 第一阶段：配置与基础架构

**目标：** 创建配置文件和目录结构

#### 步骤 1：创建配置目录

```bash
mkdir -p config/agents/deep/middleware/filesystem
```

#### 步骤 2：创建虚拟文件系统配置

创建 `config/agents/deep/middleware/filesystem/virtual_filesystem.json`：

```json
{
  "enabled": true,
  "long_term_memory": false,
  "tool_token_limit_before_evict": 20000
}
```

#### 步骤 3：创建真实文件系统配置

创建 `config/agents/deep/middleware/filesystem/real_filesystem.json`：

```json
{
  "enabled": true,
  "project_root": "${AUTO_DETECT}",
  "security": {
    "allowed_paths": ["${PROJECT_ROOT}"],
    "excluded_paths": [
      "${PROJECT_ROOT}/.git",
      "${PROJECT_ROOT}/.env",
      "${PROJECT_ROOT}/.venv",
      "${PROJECT_ROOT}/node_modules"
    ],
    "allowed_extensions": [
      ".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml"
    ],
    "max_file_size": 10485760
  }
}
```

---

### 2.2 第二阶段：真实文件系统最小实现

**目标：** 实现 `list_real_files` 和 `read_real_file` 工具

#### 步骤 1：创建模块结构

```bash
mkdir -p src/components/deepagents/runtime_middlewares/real_filesystem
touch src/components/deepagents/runtime_middlewares/real_filesystem/__init__.py
touch src/components/deepagents/runtime_middlewares/real_filesystem/middleware.py
touch src/components/deepagents/runtime_middlewares/real_filesystem/tools.py
touch src/components/deepagents/runtime_middlewares/real_filesystem/config.py
touch src/components/deepagents/runtime_middlewares/real_filesystem/security.py
```

#### 步骤 2：实现配置加载（config.py）

**核心功能：**
- 加载 JSON 配置文件
- 解析 `project_root`（自动检测或环境变量）
- 环境变量替换

**关键逻辑：**
```python
def detect_project_root() -> Path:
    """自动检测项目根目录"""
    markers = [".git", "pyproject.toml", "package.json"]
    current = Path.cwd()
    while current != current.parent:
        if any((current / marker).exists() for marker in markers):
            return current
        current = current.parent
    return Path.cwd()
```

#### 步骤 3：实现安全检查（security.py）

**核心功能：**
- 路径规范化
- 白名单检查
- 黑名单检查
- 文件扩展名检查
- 文件大小检查

**关键逻辑：**
```python
def validate_path(path: Path, config: SecurityConfig) -> None:
    """验证路径是否安全"""
    resolved = path.resolve()

    # 白名单检查
    if not any(resolved.is_relative_to(allowed) for allowed in config.allowed_paths):
        raise SecurityError("Path not in allowed directories")

    # 黑名单检查
    if any(resolved.is_relative_to(excluded) for excluded in config.excluded_paths):
        raise SecurityError("Path is excluded")

    # 扩展名检查
    if config.allowed_extensions and resolved.suffix not in config.allowed_extensions:
        raise SecurityError("File type not allowed")
```

#### 步骤 4：实现 list_real_files 工具（tools.py）

**实现要点：**
- 使用 `pathlib.Path.iterdir()` 列出目录
- 递归时使用 `Path.rglob()`
- 过滤隐藏文件
- 调用安全检查

**伪代码：**
```python
@tool
def list_real_files(directory_path: str | None = None, recursive: bool = False) -> list[str]:
    base = Path(directory_path) if directory_path else project_root
    validate_path(base, config)

    if recursive:
        files = base.rglob("*")
    else:
        files = base.iterdir()

    # 过滤和安全检查
    result = []
    for file in files:
        if file.is_file() and not is_hidden(file):
            try:
                validate_path(file, config)
                result.append(str(file))
            except SecurityError:
                continue

    return result
```

#### 步骤 5：实现 read_real_file 工具（tools.py）

**实现要点：**
- 路径安全检查
- 文件大小检查
- 编码处理（默认 UTF-8，失败时尝试检测）
- 分页读取（offset + limit）
- 行号格式化

**伪代码：**
```python
@tool
def read_real_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    path = Path(file_path).resolve()
    validate_path(path, config)

    # 文件大小检查
    if path.stat().st_size > config.max_file_size:
        raise ValueError(f"File too large: {path.stat().st_size} bytes")

    # 读取文件
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        # 尝试其他编码或返回错误
        raise ValueError("Cannot decode file with UTF-8")

    # 分页和格式化
    start = offset
    end = min(start + limit, len(lines))
    selected_lines = lines[start:end]

    return format_with_line_numbers(selected_lines, start_line=start+1)
```

#### 步骤 6：实现中间件（middleware.py）

**核心功能：**
- 加载配置
- 注册工具
- 添加 System Prompt

**关键逻辑：**
```python
class RealFilesystemMiddleware(AgentMiddleware):
    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.tools = [list_real_files, read_real_file]

    def wrap_model_call(self, request, handler):
        request.system_prompt += "\n\n" + REAL_FILESYSTEM_SYSTEM_PROMPT
        return handler(request)
```

---

### 2.3 第三阶段：集成与测试

#### 步骤 1：在 Agent 配置中启用中间件

修改 Agent 配置（如 `config/agents/deep/agent_config.json`）：

```json
{
  "middlewares": [
    {
      "type": "real_filesystem",
      "config_path": "config/agents/deep/middleware/filesystem/real_filesystem.json"
    }
  ]
}
```

#### 步骤 2：编写单元测试

创建 `tests/test_real_filesystem.py`：

**测试要点：**
- 配置加载
- 项目根目录检测
- 路径安全检查
- list_real_files 功能
- read_real_file 功能
- 错误处理

#### 步骤 3：编写集成测试

创建 `tests/integration/test_real_filesystem_agent.py`：

**测试场景：**
- Agent 使用 list_real_files 列出项目文件
- Agent 使用 read_real_file 读取源码
- Agent 处理访问被拒绝的文件
- Agent 处理文件不存在的情况

#### 步骤 4：手动测试

**测试命令：**
```bash
# 启动Agent并请求列出文件
python main.py --prompt "列出项目中的所有Python文件"

# 请求读取特定文件
python main.py --prompt "读取src/main.py文件的内容"

# 测试安全限制
python main.py --prompt "读取.env文件"  # 应该被拒绝
```

---

### 2.4 第四阶段：文档与交付

#### 步骤 1：更新 README

在项目 README 中添加：
- 真实文件系统功能说明
- 配置示例
- 安全注意事项

#### 步骤 2：编写快速开始指南

创建 `docs/quickstart-real-filesystem.md`，包含：
- 5分钟快速配置
- 常见使用场景
- 故障排查

#### 步骤 3：提交测试报告

包括：
- 单元测试覆盖率
- 集成测试结果
- 手动测试截图
- 已知问题列表

---

## 3. 后续扩展计划

### 3.1 第二版：添加搜索工具

**新增工具：**
- `glob_real_files`：Glob 模式搜索
- `grep_real_files`：内容搜索

**实施要点：**
- 使用 `pathlib.Path.glob()` 实现 Glob
- 使用 Python `re` 模块实现 Grep
- 结果数量限制
- 性能优化（大文件跳过、早停）

---

### 3.2 第三版：性能优化

**优化方向：**
- 路径解析缓存
- 并发文件读取
- 目录列表缓存
- 二进制文件检测优化

---

### 3.3 第四版：高级功能

**可能的新功能：**
- 文件监控（检测变化）
- 权限回调机制
- 审计日志
- 远程文件系统支持（HTTP、GitHub）

---

## 4. 常见问题

### Q1：为什么不直接使用虚拟文件系统读取真实文件？

**答：** 虚拟文件系统完全隔离，无法访问宿主机。真实文件系统提供受控的只读访问。

---

### Q2：Grep 为什么不集成 ripgrep？

**答：** 第一版使用纯 Python 实现，降低依赖。性能不足时可在后续版本集成 ripgrep。

---

### Q3：如何限制 Agent 只读取特定目录？

**答：** 在 `security.allowed_paths` 中只配置需要的目录，使用最小权限原则。

---

### Q4：大文件如何处理？

**答：** 使用 `offset` 和 `limit` 参数分页读取，避免一次性加载整个文件。

---

### Q5：如何调试路径访问被拒绝的问题？

**答：**
1. 检查 `project_root` 是否正确解析
2. 查看 `allowed_paths` 是否包含目标路径
3. 确认文件不在 `excluded_paths` 中
4. 验证文件扩展名在 `allowed_extensions` 中

---

## 5. 实施检查清单

### 配置阶段
- [ ] 创建配置目录结构
- [ ] 创建虚拟文件系统配置文件
- [ ] 创建真实文件系统配置文件
- [ ] 验证配置文件格式正确

### 开发阶段
- [ ] 实现配置加载模块
- [ ] 实现项目根目录自动检测
- [ ] 实现路径安全检查
- [ ] 实现 list_real_files 工具
- [ ] 实现 read_real_file 工具
- [ ] 实现中间件类

### 测试阶段
- [ ] 编写单元测试（覆盖率 > 80%）
- [ ] 编写集成测试
- [ ] 手动测试基本功能
- [ ] 手动测试安全限制
- [ ] 性能测试（大文件、大目录）

### 文档阶段
- [ ] 更新 README
- [ ] 编写快速开始指南
- [ ] 编写API文档
- [ ] 记录已知问题

### 交付阶段
- [ ] 代码审查
- [ ] 提交测试报告
- [ ] 用户验收测试
- [ ] 部署生产环境
