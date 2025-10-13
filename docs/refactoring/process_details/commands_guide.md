# 命令层重构指南

## 模块概述

命令层负责处理所有用户命令，采用 Command Pattern 设计模式：
- 命令解析和参数验证
- 按引擎分包管理
- 统一的命令注册和路由机制

**核心原则**：每个命令独立、按引擎隔离、可插拔注册

## 目录结构

```
application/commands/
├── __init__.py          # 命令注册表和路由
├── base.py              # BaseCommand 抽象基类
├── parser.py            # 命令解析工具
├── engine_commands.py   # /switch <engine> (全局)
│
├── shared/              # 共享命令（跨引擎）
│   ├── __init__.py
│   ├── system_commands.py    # help, info, exit
│   └── session_commands.py   # new, clear, restore, delete
│
├── langchain/           # LangChain 专属命令
│   ├── __init__.py
│   ├── model_commands.py     # /model <provider> <model>
│   ├── mode_commands.py      # /mode llm|agent, /stream on|off
│   ├── llm_commands.py       # /llms, /reload
│   └── tool_commands.py      # /mcp, /connector
│
├── langgraph/           # LangGraph 专属命令（预留）
│   ├── __init__.py
│   ├── graph_commands.py     # /graph <name>
│   ├── node_commands.py      # /nodes, /visualize
│   └── model_commands.py     # /model <provider> <model>
│
└── dify/                # Dify 专属命令
    ├── __init__.py
    ├── file_commands.py      # /upload, /files
    └── session_commands.py   # /reset, /reconnect
```

## 关键模块说明

### 1. parser.py - 命令解析工具

**职责**：
- 解析用户输入
- 区分命令和对话
- 提取命令名和参数

**关键接口**：

```python
def parse_command(query: str) -> tuple[str, str]:
    """解析命令和参数
    
    Args:
        query: 用户输入（如 "/switch langchain"）
    
    Returns:
        (command, args): ("/switch", "langchain")
    """

def is_command(query: str) -> bool:
    """判断是否为命令
    
    Returns:
        True if starts with '/'
    """

def extract_command_name(command: str) -> str:
    """提取命令名（去除 / 前缀）
    
    Args:
        command: "/switch"
    
    Returns:
        "switch"
    """
```

**迁移映射**：
- `components/process/cli.py` L48-98 → `commands/parser.py`
  - 直接迁移函数，无修改

### 2. base.py - BaseCommand 抽象基类

**职责**：
- 定义命令标准接口
- 提供命令元数据

**关键接口**：

```python
class CommandResult:
    """命令执行结果"""
    type: str        # success | error | info | list
    message: str
    payload: dict

class BaseCommand(ABC):
    """命令抽象基类"""
    
    name: str                    # 命令名
    aliases: List[str] = []      # 别名
    help_text: str               # 帮助信息
    engine_scope: List[str]      # 可用引擎 ["langchain"] 或 ["all"]
    
    @abstractmethod
    async def execute(self, ctx, args: str) -> CommandResult:
        """执行命令"""
        pass
    
    def is_available(self, current_engine: str) -> bool:
        """判断命令在当前引擎是否可用"""
        if "all" in self.engine_scope:
            return True
        return current_engine in self.engine_scope
    
    def validate_args(self, args: str) -> bool:
        """验证参数（可选重写）"""
        return True
```

**迁移映射**：
- 新增模块，定义统一接口

### 3. __init__.py - 命令注册表和路由

**职责**：
- 注册所有命令
- 提供统一的命令分发

**关键接口**：

```python
# 命令注册表
COMMAND_REGISTRY = {
    # 全局命令
    "switch": SwitchEngineCommand(),
    "help": HelpCommand(),
    "info": InfoCommand(),
    "exit": ExitCommand(),
    "quit": ExitCommand(),
    
    # 共享命令
    "new": NewSessionCommand(),
    "clear": ClearSessionCommand(),
    "sessions": ListSessionsCommand(),
    "restore": RestoreSessionCommand(),
    "delete_session": DeleteSessionCommand(),
    "cleanup": CleanupSessionsCommand(),
    
    # LangChain 命令
    "model": {
        "langchain": LangChainModelCommand(),
        "langgraph": LangGraphModelCommand(),
    },
    "mode": ModeCommand(),         # engine_scope=["langchain"]
    "stream": StreamCommand(),     # engine_scope=["langchain"]
    "llms": LLMsCommand(),         # engine_scope=["langchain"]
    "reload": ReloadCommand(),     # engine_scope=["langchain"]
    "mcp": MCPCommand(),           # engine_scope=["langchain", "langgraph"]
    "connector": ConnectorCommand(), 
    
    # LangGraph 命令（预留）
    "graph": GraphCommand(),
    "nodes": NodesCommand(),
    
    # Dify 命令
    "upload": DifyUploadCommand(),
    "files": DifyFilesCommand(),
    "reset": DifyResetCommand(),
    "reconnect": DifyReconnectCommand(),
}

async def dispatch(command_name: str, ctx, args: str) -> CommandResult:
    """命令分发
    
    Args:
        command_name: 命令名（不含 /）
        ctx: 应用上下文
        args: 参数字符串
    
    Returns:
        CommandResult
    """
    cmd = COMMAND_REGISTRY.get(command_name)
    
    if not cmd:
        return CommandResult(
            type="error",
            message=f"Unknown command: {command_name}",
            payload={}
        )
    
    # 处理多引擎命令（如 /model）
    if isinstance(cmd, dict):
        cmd = cmd.get(ctx.current_engine)
        if not cmd:
            return CommandResult(
                type="error",
                message=f"Command '{command_name}' not available in {ctx.current_engine} engine",
                payload={}
            )
    
    # 检查命令可用性
    if not cmd.is_available(ctx.current_engine):
        return CommandResult(
            type="error",
            message=f"Command '{command_name}' not available in {ctx.current_engine} engine",
            payload={}
        )
    
    # 执行命令
    return await cmd.execute(ctx, args)
```

**迁移映射**：
- `components/process/cli.py` L294-737 (命令路由) → `commands/__init__.py`
  - 重构：if-elif 硬编码 → 注册表 + 分发函数

### 4. shared/system_commands.py - 系统命令

**职责**：
- 处理全局系统命令

**示例实现**：

```python
class HelpCommand(BaseCommand):
    name = "help"
    engine_scope = ["all"]
    help_text = "显示帮助信息"
    
    async def execute(self, ctx, args):
        from ...cli.gui.render import render_help
        render_help(ctx.console, dify_mode=(ctx.current_engine == "dify"))
        return CommandResult(type="success", message="", payload={})

class InfoCommand(BaseCommand):
    name = "info"
    engine_scope = ["all"]
    help_text = "显示系统信息"
    
    async def execute(self, ctx, args):
        # 根据当前引擎获取信息
        if ctx.current_engine == "dify":
            info = await ctx.engine_configs["dify"]["control"].get_detailed_info()
            from ...cli.gui.render import render_dify_info
            render_dify_info(ctx.console, info, ctx.session_id)
        else:
            # LangChain/LangGraph
            from ...services import get_current_service
            service = get_current_service(ctx)
            info = service.get_info(ctx)
            from ...cli.gui.render import render_info
            render_info(ctx.console, info)
        
        return CommandResult(type="success", message="", payload={})
```

**迁移映射**：
- `components/process/cli.py` L325-342 (help/info 命令) → `shared/system_commands.py`

### 5. shared/session_commands.py - 会话命令

**示例实现**：

```python
class NewSessionCommand(BaseCommand):
    name = "new"
    engine_scope = ["all"]
    help_text = "创建新会话"
    
    async def execute(self, ctx, args):
        old_id = ctx.session_id
        ctx.session_id = ctx.session_manager.create_new_session()
        return CommandResult(
            type="success",
            message=f"New session created: {ctx.session_id}",
            payload={"old_session_id": old_id, "new_session_id": ctx.session_id}
        )
```

**迁移映射**：
- `components/process/session_control.py` → `shared/session_commands.py`
  - 重构：函数 → Command 类
  - `new_session()` → `NewSessionCommand`
  - `clear_session()` → `ClearSessionCommand`
  - `list_sessions()` → `ListSessionsCommand`
  - `restore_session()` → `RestoreSessionCommand`
  - `delete_session()` → `DeleteSessionCommand`
  - `cleanup_sessions()` → `CleanupSessionsCommand`

### 6. langchain/model_commands.py - LangChain 模型命令

**示例实现**：

```python
class LangChainModelCommand(BaseCommand):
    name = "model"
    engine_scope = ["langchain"]
    help_text = "切换 LangChain 模型"
    
    async def execute(self, ctx, args):
        parts = args.split()
        if len(parts) < 1:
            return CommandResult(
                type="error",
                message="Usage: /model <provider> [model]",
                payload={}
            )
        
        provider = parts[0]
        model = parts[1] if len(parts) > 1 else None
        
        # 调用 service 执行切换
        from ...services.langchain import LangChainService
        service = LangChainService()
        result = await service.switch_model(ctx, provider, model)
        
        return result
```

**迁移映射**：
- `components/process/control.py` L10-70 (`switch_llm`) → `langchain/model_commands.py`
  - 重构：函数 → Command 类
  - 调用 `LangChainService.switch_model()`

### 7. langchain/tool_commands.py - 工具管理命令

**示例实现**：

```python
class MCPCommand(BaseCommand):
    name = "mcp"
    engine_scope = ["langchain", "langgraph"]
    help_text = "MCP 工具管理"
    
    async def execute(self, ctx, args):
        parts = args.split()
        if not parts:
            return CommandResult(
                type="error",
                message="Usage: /mcp status|tools|reload",
                payload={}
            )
        
        subcommand = parts[0].lower()
        
        if subcommand == "status":
            # 调用 mcp_control
            from ....components.process import mcp_control
            verbose = "-v" in parts or "--verbose" in parts
            result = await mcp_control.mcp_status(verbose=verbose)
            # 渲染结果
            from ...cli.gui.render import render_mcp_status
            render_mcp_status(ctx.console, result["payload"], verbose)
            
        # ... 其他子命令
```

**迁移映射**：
- `components/process/cli.py` L354-395 (MCP 命令) → `langchain/tool_commands.py`
- `components/process/cli.py` L398-436 (Connector 命令) → `langchain/tool_commands.py`
- 保留 `mcp_control.py` 和 `connector_control.py` 作为底层实现

## 使用示例

### CLI 中使用命令分发

```python
# application/cli/main.py

from ..commands import dispatch
from ..commands.parser import is_command, parse_command, extract_command_name

async def run():
    # ...
    query = await asyncio.to_thread(ctx.console.input, prompt)
    
    if is_command(query):
        command, args = parse_command(query)
        command_name = extract_command_name(command)
        
        # 分发命令
        result = await dispatch(command_name, ctx, args)
        
        # 处理结果
        if result.type == "error":
            ctx.console.print(f"[red]{result.message}[/]")
        elif result.type == "success" and result.message:
            ctx.console.print(f"[green]{result.message}[/]")
```

### 添加新命令

```python
# 1. 定义命令类
class MyNewCommand(BaseCommand):
    name = "mynew"
    engine_scope = ["langchain"]
    help_text = "My new command"
    
    async def execute(self, ctx, args):
        # 实现逻辑
        return CommandResult(type="success", message="Done", payload={})

# 2. 注册到 COMMAND_REGISTRY
COMMAND_REGISTRY["mynew"] = MyNewCommand()
```

## 风险点

### 1. 命令冲突

**风险**：不同引擎可能有同名命令

**应对**：
- 使用 `engine_scope` 限制命令可用范围
- 多引擎命令使用 dict 分别注册

### 2. 参数解析

**风险**：参数解析逻辑分散在各命令中，不统一

**应对**：
- 在 `BaseCommand` 提供通用解析方法
- 复杂参数使用 `argparse` 或 `click`

### 3. 循环导入

**风险**：命令导入 service，service 可能导入命令

**应对**：
- 命令只导入 service（单向依赖）
- 必要时使用动态导入

## 迁移检查清单

- [ ] 创建 `parser.py`，迁移命令解析函数
- [ ] 创建 `base.py`，定义 BaseCommand 接口
- [ ] 创建 `__init__.py`，实现命令注册表和分发
- [ ] 迁移系统命令到 `shared/system_commands.py`
- [ ] 迁移会话命令到 `shared/session_commands.py`
- [ ] 迁移 LangChain 命令到 `langchain/`
- [ ] 创建 Dify 命令到 `dify/`
- [ ] 预留 LangGraph 命令结构
- [ ] 测试命令注册和分发机制
- [ ] 测试各引擎命令隔离

