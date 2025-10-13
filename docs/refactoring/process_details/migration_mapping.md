# 迁移映射表

## 概述

本文档提供详细的代码迁移映射，帮助实施时快速定位原代码位置和目标位置。

## 文件级迁移映射

### 从 components/process/ 迁移

| 原文件 | 目标文件 | 迁移类型 | 说明 |
|--------|---------|---------|------|
| `cli.py` | `cli/main.py` | 重构 | 精简主循环，移除业务逻辑 |
| `cli.py` | `cli/state.py` | 抽取 | AppState 定义 |
| `cli.py` | `commands/parser.py` | 抽取 | 命令解析函数 |
| `gui.py` | `cli/gui/render.py` | 拆分 | 渲染函数 |
| `gui.py` | `cli/gui/formatter.py` | 抽取 | 数据格式化逻辑 |
| `gui.py` | `cli/gui/interact.py` | 抽取 | 交互逻辑 |
| `control.py` | `services/langchain/service.py` | 重构 | 部分逻辑重构为服务 |
| `control.py` | `commands/langchain/model_commands.py` | 重构 | switch_llm 重构为命令 |
| `session_control.py` | `commands/shared/session_commands.py` | 重构 | 函数重构为 Command 类 |
| `mcp_control.py` | `commands/langchain/tool_commands.py` | 集成 | MCP 命令处理器 |
| `connector_control.py` | `commands/langchain/tool_commands.py` | 集成 | Connector 命令处理器 |
| `registry.py` | `services/catalog/langchain/catalog.py` | 重构 | 重命名为 catalog，调整依赖 |
| `validation.py` | 保留位置 | 保留 | 输入验证模块 |

### 从 components/dify/ 迁移

| 原文件 | 目标文件 | 迁移类型 | 说明 |
|--------|---------|---------|------|
| `control.py` | `services/dify/service.py` | 重构 | DifyControl → DifyService |
| `client.py` | `services/dify/client.py` | 直接迁移 | 无修改 |
| `streaming.py` | `services/dify/streaming.py` | 直接迁移 | 无修改 |
| `upload.py` | `services/dify/upload.py` | 直接迁移 | 无修改 |

### 从 ui/logo/ 迁移

| 原文件 | 目标文件 | 迁移类型 | 说明 |
|--------|---------|---------|------|
| `logo.py` | `cli/gui/logo.py` | 直接迁移 | 整合到 GUI 层 |

## 代码级迁移映射

### cli.py 详细映射

| 原代码位置 | 目标位置 | 说明 |
|-----------|---------|------|
| **L32-45: AppState 类** | `cli/state.py` | 重构状态结构 |
| └─ `llm_mode`, `dify_mode` | → `current_engine` | 统一为引擎标识 |
| └─ `agent`, `dify_control` | → `engine_configs` | 归入引擎配置 |
| **L48-70: parse_command()** | `commands/parser.py` | 直接迁移 |
| **L73-83: is_command()** | `commands/parser.py` | 直接迁移 |
| **L86-98: extract_command_name()** | `commands/parser.py` | 直接迁移 |
| **L101-159: run() 初始化部分** | `cli/main.py` | 保留，调整引用 |
| └─ L131-143: 创建 Agent | → `services/langchain/agent_lifecycle.py` | 抽取为函数 |
| └─ L150-159: 注册流式 LLM | → `services/langchain/streaming.py` | 统一注册 |
| **L172-291: 主循环对话处理** | 拆分到多处 | |
| └─ L198-234: LLM 流式对话 | → `services/langchain/conversation.py:handle_llm_query(streaming=True)` | 抽取为函数 |
| └─ L239-260: LLM 非流式对话 | → `services/langchain/conversation.py:handle_llm_query(streaming=False)` | 抽取为函数 |
| └─ L266-283: Agent 对话 | → `services/langchain/conversation.py:handle_agent_query()` | 抽取为函数 |
| └─ L192-195: Dify 对话 | → `services/dify/service.py:handle_query()` | 重构为服务方法 |
| **L294-737: 命令处理** | `commands/` 各模块 | 重构为 Command Pattern |
| └─ L297-323: exit/quit | → `commands/shared/system_commands.py:ExitCommand` | |
| └─ L325-327: help | → `commands/shared/system_commands.py:HelpCommand` | |
| └─ L329-342: info | → `commands/shared/system_commands.py:InfoCommand` | |
| └─ L344-351: llms | → `commands/langchain/llm_commands.py:LLMsCommand` | |
| └─ L354-395: mcp | → `commands/langchain/tool_commands.py:MCPCommand` | |
| └─ L398-436: connector | → `commands/langchain/tool_commands.py:ConnectorCommand` | |
| └─ L439-494: switch | → `commands/engine_commands.py:SwitchEngineCommand` | |
| └─ L498-501: upload | → `commands/dify/file_commands.py:DifyUploadCommand` | |
| └─ L509-561: files | → `commands/dify/file_commands.py:DifyFilesCommand` | |
| └─ L581-592: clear | → `commands/shared/session_commands.py:ClearSessionCommand` | |
| └─ L594-604: new | → `commands/shared/session_commands.py:NewSessionCommand` | |
| └─ L606-620: delete_session | → `commands/shared/session_commands.py:DeleteSessionCommand` | |
| └─ L622-633: cleanup | → `commands/shared/session_commands.py:CleanupSessionsCommand` | |
| └─ L635-644: sessions | → `commands/shared/session_commands.py:ListSessionsCommand` | |
| └─ L646-662: restore | → `commands/shared/session_commands.py:RestoreSessionCommand` | |
| └─ L665-673: reload | → `commands/langchain/llm_commands.py:ReloadCommand` | |
| └─ L676-702: mode | → `commands/langchain/mode_commands.py:ModeCommand` | |
| └─ L705-732: stream | → `commands/langchain/mode_commands.py:StreamCommand` | |

### control.py 详细映射

| 原代码位置 | 目标位置 | 说明 |
|-----------|---------|------|
| **L10-70: switch_llm()** | `commands/langchain/model_commands.py` | 重构为 Command |
| └─ L24-29: 创建 Agent | → `services/langchain/agent_lifecycle.py:switch_agent()` | |
| └─ L42-54: 注册流式 LLM | → `services/langchain/streaming.py:register_streaming_llm()` | |
| **L73-101: set_mode()** | `commands/langchain/mode_commands.py:ModeCommand` | 重构为 Command |
| **L104-137: set_stream()** | `commands/langchain/mode_commands.py:StreamCommand` | 重构为 Command |
| **L140-158: get_info()** | `services/langchain/service.py:get_info()` | 重构为服务方法 |
| **L161-196: reload_config()** | `commands/langchain/llm_commands.py:ReloadCommand` | 重构为 Command |

### session_control.py 详细映射

| 原代码位置 | 目标位置 | 说明 |
|-----------|---------|------|
| **L7-20: clear_session()** | `commands/shared/session_commands.py:ClearSessionCommand` | 函数 → Command 类 |
| **L23-34: new_session()** | `commands/shared/session_commands.py:NewSessionCommand` | 函数 → Command 类 |
| **L37-47: list_sessions()** | `commands/shared/session_commands.py:ListSessionsCommand` | 函数 → Command 类 |
| **L50-77: restore_session()** | `commands/shared/session_commands.py:RestoreSessionCommand` | 函数 → Command 类 |
| **L80-116: delete_session()** | `commands/shared/session_commands.py:DeleteSessionCommand` | 函数 → Command 类 |
| **L119-127: cleanup_sessions()** | `commands/shared/session_commands.py:CleanupSessionsCommand` | 函数 → Command 类 |

### gui.py 详细映射

| 原代码位置 | 目标位置 | 说明 |
|-----------|---------|------|
| **L9-53: print_welcome()** | `cli/gui/render.py:render_welcome()` | 直接迁移 |
| **L56-157: print_help()** | `cli/gui/render.py:render_help()` | 直接迁移 |
| **L160-202: render_llms()** | `cli/gui/render.py:render_llms_catalog()` | 直接迁移 |
| **L205-238: render_info()** | `cli/gui/render.py:render_info()` | 直接迁移 |
| **L241-277: render_dify_info()** | `cli/gui/render.py:render_dify_info()` | 直接迁移 |
| **L280-295: render_sessions()** | `cli/gui/render.py:render_sessions()` | 拆分：格式化 → formatter.py |
| **L298-313: render_mcp_status()** | `cli/gui/render.py:render_mcp_status()` | 直接迁移 |
| **L316-332: render_mcp_tools()** | `cli/gui/render.py:render_mcp_tools()` | 直接迁移 |
| **L335-347: render_connector_status()** | `cli/gui/render.py:render_connector_status()` | 直接迁移 |
| **L350-365: render_connector_tools()** | `cli/gui/render.py:render_connector_tools()` | 直接迁移 |
| **格式化逻辑** | `cli/gui/formatter.py` | 新增模块 |
| **交互逻辑** | `cli/gui/interact.py` | 新增模块 |

### registry.py 详细映射

| 原代码位置 | 目标位置 | 说明 |
|-----------|---------|------|
| **L10-70: get_catalog()** | `services/catalog/langchain/catalog.py:get_catalog()` | 重构，依赖 provider_registry |
| └─ Ollama 动态查询 | 保留增强 | 继续支持 |
| **L73-94: validate()** | `services/catalog/langchain/catalog.py:validate_model()` | 重构，调用 provider_registry |
| **L97-102: resolve_default()** | 整合到 `get_model_info()` | 简化 |

### dify/control.py 详细映射

| 原代码位置 | 目标位置 | 说明 |
|-----------|---------|------|
| **L22-40: DifyControl.__init__()** | `services/dify/service.py:DifyService.__init__()` | 重构为服务 |
| **L127-199: initialize()** | `services/dify/service.py:initialize()` | 实现 BaseEngineService |
| **L220-290: handle_query()** | `services/dify/service.py:handle_query()` | 实现 BaseEngineService |
| **L371-401: get_detailed_info()** | `services/dify/service.py:get_info()` | 实现 BaseEngineService |
| **L518-541: cleanup()** | `services/dify/service.py:cleanup()` | 资源清理 |
| **L544-575: init_dify_client()** | `services/dify/service.py:initialize()` | 整合到初始化 |

## 新增模块

### 基础抽象层

| 模块 | 说明 |
|------|------|
| `commands/base.py` | BaseCommand 抽象基类 |
| `commands/parser.py` | 命令解析工具 |
| `commands/__init__.py` | 命令注册表和分发 |
| `services/base.py` | BaseEngineService 抽象基类 |
| `services/__init__.py` | 服务路由器 |
| `engine_adapters/__init__.py` | 适配器路由 |
| `cli/state.py` | AppState 定义 |

### 引擎适配器

| 模块 | 说明 |
|------|------|
| `engine_adapters/langchain_adapter.py` | LangChain 适配器 |
| `engine_adapters/langgraph_adapter.py` | LangGraph 适配器（预留） |
| `engine_adapters/dify_adapter.py` | Dify 适配器 |

### LangChain 服务

| 模块 | 说明 |
|------|------|
| `services/langchain/service.py` | 主服务 |
| `services/langchain/conversation.py` | 对话处理 |
| `services/langchain/streaming.py` | 流式服务 |
| `services/langchain/agent_lifecycle.py` | Agent 生命周期 |

### GUI 层拆分

| 模块 | 说明 |
|------|------|
| `cli/gui/formatter.py` | 数据格式化 |
| `cli/gui/interact.py` | 交互辅助 |

### 目录服务

| 模块 | 说明 |
|------|------|
| `services/catalog/__init__.py` | 统一接口 |
| `services/catalog/langchain/catalog.py` | LangChain 目录 |
| `services/catalog/langgraph/catalog.py` | LangGraph 目录（预留） |
| `services/catalog/dify/catalog.py` | Dify 目录（暂不实现） |

## 删除文件清单

迁移完成后需要删除的文件：

```
src/components/process/
├── cli.py                    # → 拆分到多处
├── control.py                # → 拆分到多处
├── session_control.py        # → commands/shared/session_commands.py
├── mcp_control.py            # 保留（被 commands 调用）
├── connector_control.py      # 保留（被 commands 调用）
├── gui.py                    # → cli/gui/render.py + formatter.py
├── registry.py               # → services/catalog/langchain/catalog.py
└── validation.py             # 保留原位置

src/components/dify/
├── control.py                # → services/dify/service.py
├── client.py                 # → services/dify/client.py
├── streaming.py              # → services/dify/streaming.py
└── upload.py                 # → services/dify/upload.py

src/ui/logo/
└── logo.py                   # → cli/gui/logo.py
```

## 导入路径更新清单

### 需要全局替换的导入

```python
# AppState
from src.components.process.cli import AppState
→ from src.application.cli.state import AppState

# GUI 渲染
from src.components.process.gui import render_info, render_sessions
→ from src.application.cli.gui.render import render_info, render_sessions

# Logo
from src.ui.logo.logo import display_logo
→ from src.application.cli.gui.logo import display_logo

# Dify 控制
from src.components.dify.control import DifyControl, init_dify_client
→ from src.application.services.dify.service import DifyService

# 命令解析
from src.components.process.cli import parse_command, is_command
→ from src.application.commands.parser import parse_command, is_command

# Registry
from src.components.process.registry import get_catalog
→ from src.application.services.catalog import get_engine_catalog

# Session 控制
from src.components.process.session_control import new_session, clear_session
→ 不再直接导入，通过 Command 调用

# Control
from src.components.process.control import switch_llm
→ 不再直接导入，通过 Command 调用
```

### 保持不变的导入

```python
# 这些模块保持原位置
from src.components.shared.memory import GlobalMemoryManager
from src.components.shared.tools.mcp import GlobalMCPManager
from src.components.process.mcp_control import mcp_status
from src.components.process.connector_control import connector_status
from src.agents.langchain.managers import agent_manager
from src.llm.langchain.utils import stream_llm_response
from src.core.langchain.providers import provider_registry
```

## 迁移验证清单

迁移完成后，验证以下功能：

- [ ] CLI 主循环正常启动
- [ ] 命令解析和分发正常
- [ ] LangChain 引擎：
  - [ ] LLM 模式对话（流式/非流式）
  - [ ] Agent 模式对话
  - [ ] 模型切换 `/model`
  - [ ] 模式切换 `/mode`
  - [ ] 目录查询 `/llms`
  - [ ] 配置重载 `/reload`
- [ ] Dify 引擎：
  - [ ] 初始化和连接
  - [ ] 对话功能
  - [ ] 文件上传 `/upload`
  - [ ] 文件管理 `/files`
- [ ] 会话管理：
  - [ ] `/new`, `/clear`, `/restore`
  - [ ] `/sessions`, `/delete_session`
- [ ] 引擎切换 `/switch`
- [ ] UI 渲染正常
- [ ] 无导入错误
- [ ] 无循环依赖

