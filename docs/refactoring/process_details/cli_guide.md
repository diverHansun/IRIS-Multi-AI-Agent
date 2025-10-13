# CLI 层重构指南

## 模块概述

CLI 层是应用的入口和交互界面，负责：
- 主循环控制和输入输出
- 应用状态管理
- UI 渲染和用户交互

**核心原则**：只做 IO 和交互，不包含业务逻辑

## 目录结构

```
application/cli/
├── __init__.py
├── main.py          # 主循环（精简后的 cli.py）
├── state.py         # AppState 定义
└── gui/             # UI 层
    ├── __init__.py
    ├── render.py    # 渲染函数（原 gui.py）
    ├── interact.py  # 交互辅助（新增）
    ├── formatter.py # 数据格式化（新增）
    └── logo.py      # Logo 显示（从 ui/logo 迁移）
```

## 关键模块说明

### 1. main.py - 主循环

**职责**：
- 应用启动和初始化
- 主循环：输入 → 解析 → 路由 → 输出
- 生命周期管理（启动/关闭/清理）

**关键接口**：

```python
async def run():
    """主循环入口"""
    # 初始化
    ctx = AppState()
    
    # 主循环
    while True:
        query = await asyncio.to_thread(ctx.console.input, prompt)
        
        if is_command(query):
            # 命令路由
            from ..commands import dispatch
            result = await dispatch(command_name, ctx, args)
        else:
            # 对话路由
            from ..engine_adapters import get_adapter
            adapter = get_adapter(ctx.current_engine)
            result = await adapter.handle_query(ctx, query)
```

**迁移映射**：
- `components/process/cli.py` → `cli/main.py`
  - 保留：主循环结构、输入输出
  - 移除：命令处理逻辑（→ commands/）、对话处理逻辑（→ services/）

### 2. state.py - 应用状态

**职责**：
- 定义应用全局状态
- 管理引擎配置

**关键接口**：

```python
class AppState:
    """应用全局状态"""
    
    def __init__(self):
        self.console = Console()
        
        # 当前执行引擎
        self.current_engine: str = "langchain"  # langchain | langgraph | dify
        
        # 每个引擎的独立配置
        self.engine_configs = {
            "langchain": {
                "provider": "zhipu",
                "model": "glm-4-plus",
                "mode": "llm",
                "streaming": True,
                "agent": None,
            },
            "langgraph": {
                "graph_name": "deep_agent",
                "provider": "openai",
                "model": "gpt-4o",
                "graph_instance": None,
            },
            "dify": {
                "conversation_id": None,
                "files": [],
                "control": None,
            }
        }
        
        # 共享组件
        self.global_memory = None
        self.session_manager = None
        self.session_id = None
```

**迁移映射**：
- `components/process/cli.py` L32-45 (AppState) → `cli/state.py`
  - 重构：`llm_mode/dify_mode` → `current_engine`
  - 重构：分散的配置 → `engine_configs` 统一管理

### 3. gui/render.py - 渲染层

**职责**：
- 接收格式化后的数据
- 使用 Rich 进行渲染

**关键接口**：

```python
def render_welcome(console):
    """渲染欢迎信息"""
    
def render_info(console, engine_info, mode_info):
    """渲染系统信息"""
    
def render_sessions(console, formatted_sessions):
    """渲染会话列表"""
    
def render_llms_catalog(console, catalog):
    """渲染 LLM 目录"""
```

**迁移映射**：
- `components/process/gui.py` → `cli/gui/render.py`
  - 保留：所有 `render_*()` 函数
  - 移除：数据格式化逻辑（→ formatter.py）

### 4. gui/formatter.py - 数据格式化

**职责**：
- 将业务数据转换为显示格式

**关键接口**：

```python
def format_agent_info(agent) -> dict:
    """格式化 Agent 信息用于显示"""
    info = agent.get_info()
    return {
        "provider_display": f"{info['provider'].upper()}",
        "model_display": f"{info['model']}",
        "features": ", ".join(info.get('model_features', [])),
    }

def format_file_size(bytes: int) -> str:
    """格式化文件大小：1024 → "1KB" """
    if bytes > 1024 * 1024:
        return f"{bytes / (1024 * 1024):.1f}MB"
    elif bytes > 1024:
        return f"{bytes / 1024:.1f}KB"
    return f"{bytes}B"

def format_session_list(sessions: List[dict], current_id: str) -> List[dict]:
    """格式化会话列表"""
    # 添加当前标记、格式化时间等
```

**迁移映射**：
- `components/process/gui.py` 中的格式化逻辑 → `cli/gui/formatter.py`
  - 抽取：数据处理、格式转换逻辑

### 5. gui/interact.py - 交互辅助

**职责**：
- 处理用户输入、确认、选择等交互

**关键接口**：

```python
def prompt_confirm(console, message: str, default: bool = False) -> bool:
    """确认提示：确定要删除会话？[y/N]"""
    
def prompt_select(console, options: List[str], title: str = "") -> str:
    """选择提示：从列表中选择一项"""
    
def parse_indices(input_str: str) -> List[int]:
    """解析索引列表："1 3 5" → [1, 3, 5]"""
```

**迁移映射**：
- 新增模块，抽取 `cli.py` 中的交互逻辑
  - 会话选择逻辑
  - 文件索引解析逻辑

### 6. gui/logo.py - Logo 显示

**职责**：
- 显示启动 Logo 和欢迎信息

**关键接口**：

```python
def display_logo():
    """显示 IRIS Logo"""
    
def display_logo_intro():
    """显示 Logo 介绍"""
```

**迁移映射**：
- `src/ui/logo/logo.py` → `cli/gui/logo.py`
  - 直接迁移，无修改

## 使用示例

### 主循环使用

```python
# application/cli/main.py

from .state import AppState
from .gui.render import render_welcome
from .gui.logo import display_logo

async def run():
    # 显示 Logo
    display_logo()
    
    # 创建状态
    ctx = AppState()
    
    # 渲染欢迎信息
    render_welcome(ctx.console)
    
    # 主循环
    while True:
        prompt = f"[bold cyan]{ctx.current_engine}[/] > "
        query = await asyncio.to_thread(ctx.console.input, prompt)
        # ...
```

### 渲染使用

```python
# 使用 formatter + render

from .gui.formatter import format_agent_info
from .gui.render import render_info

# 1. 格式化数据
formatted_info = format_agent_info(ctx.agent)

# 2. 渲染
render_info(ctx.console, formatted_info, mode_info)
```

## 风险点

### 1. 主循环复杂度

**风险**：主循环仍然包含较多判断逻辑

**应对**：
- 命令判断 → `commands/parser.py`
- 引擎路由 → `engine_adapters/`
- 保持主循环简洁

### 2. 状态管理

**风险**：`engine_configs` 结构变化可能影响多处代码

**应对**：
- 提供 getter/setter 方法封装访问
- 使用类型提示明确结构

### 3. 循环导入

**风险**：`cli/main.py` 导入 `commands/` 和 `engine_adapters/`，可能形成循环

**应对**：
- 使用动态导入（在函数内部 import）
- 保持单向依赖：cli → commands/adapters

## 迁移检查清单

- [ ] 将 `cli.py` 主循环精简，移除业务逻辑
- [ ] 创建 `state.py`，重构 AppState 结构
- [ ] 将 `gui.py` 拆分为 `render.py` + `formatter.py` + `interact.py`
- [ ] 迁移 `ui/logo/logo.py` 到 `cli/gui/logo.py`
- [ ] 更新所有导入路径
- [ ] 测试主循环和 UI 渲染功能

