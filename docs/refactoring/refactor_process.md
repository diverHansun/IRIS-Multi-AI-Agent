# Process 架构重构与未来扩展文档

## 文档概述

编写一份全面的架构文档，详细说明：

1. 当前 `src/components/process/` 的架构现状与问题
2. 基于 `src/application/` 的新架构设计
3. 支持 LangChain/LangGraph/Dify 三大引擎的扩展方案
4. 具体的迁移实施路径

## 文档结构

### 第一部分：当前架构分析

- **目录结构回顾**
  - 列出 `src/components/process/` 当前所有文件
  - 标注各文件职责（cli.py 762行的主循环、gui.py 渲染等）

- **职责混乱问题**
  - cli.py 过载：交互、业务逻辑、副作用（流式注册）混合
  - gui.py 职责过轻：只做渲染，缺少交互层
  - 缺少服务层：对话处理直接写在 cli 主循环
  - 命令路由硬编码：300+ 行 if-elif

- **引擎耦合问题**
  - LangChain/Dify 模式混在同一流程
  - 未来引入 LangGraph 难以扩展
  - 缺少统一的引擎适配层

### 第二部分：新架构设计 (src/application/)

#### 2.1 整体分层

```
src/application/
├── cli/                # CLI 入口层（纯交互）
├── commands/           # 命令处理层（按引擎分包）
│   ├── shared/        # 共享命令（跨引擎）
│   ├── langchain/     # LangChain 专属命令
│   ├── langgraph/     # LangGraph 专属命令
│   └── dify/          # Dify 专属命令
├── services/           # 业务服务层（按引擎分包，包含实现）
│   ├── langchain/     # LangChain 引擎服务 + 实现
│   ├── langgraph/     # LangGraph 引擎服务 + 实现（预留）
│   └── dify/          # Dify 引擎服务 + 实现
└── engine_adapters/    # 引擎适配层（分流网关）
```

#### 2.2 核心设计要点

**AppState 重构**

- 引入 `current_engine` 字段（langchain/langgraph/dify）
- 每个引擎独立配置：`engine_configs = {}`
- 共享组件：memory、session_manager

**Engine Adapters 作为引擎网关**

- `engine_adapters/langchain_adapter.py` - 处理 LangChain Agent/LLM 调用
- `engine_adapters/langgraph_adapter.py` - 处理 LangGraph 工作流执行（预留）
- `engine_adapters/dify_adapter.py` - 适配 Dify 服务层的实现

**Services 按引擎拆分（包含具体实现）**

- `services/base.py` - BaseEngineService 抽象类
- `services/langchain/` - LangChain 引擎服务 + 实现
  - service.py - 主服务
  - conversation.py - 对话处理
  - streaming.py - 流式管理
  - agent_lifecycle.py - Agent 生命周期
- `services/langgraph/` - LangGraph 引擎服务 + 实现（预留）
  - service.py - 主服务
  - graph_executor.py - Graph 执行器
  - workflow_manager.py - 工作流管理
- `services/dify/` - Dify 引擎服务 + 实现
  - service.py - 主服务（原 control.py 重构）
  - client.py - API 客户端
  - streaming.py - 流式处理
  - upload.py - 文件上传

**Commands 命令注册机制（按引擎分包）**

- `base.py` - BaseCommand 基类
- `engine_commands.py` - /switch langchain|langgraph|dify（全局命令）
- `shared/` - 共享命令（跨引擎可用）
  - `system_commands.py` - /help, /info, /exit
  - `session_commands.py` - /new, /clear, /restore, /delete_session
- `langchain/` - LangChain 专属命令
  - `model_commands.py` - /model <provider> <model>
  - `mode_commands.py` - /mode llm|agent, /stream on|off
  - `llm_commands.py` - /llms, /reload
  - `tool_commands.py` - /mcp, /connector
- `langgraph/` - LangGraph 专属命令（预留）
  - `graph_commands.py` - /graph <name>
  - `node_commands.py` - /nodes, /visualize
  - `model_commands.py` - /model <provider> <model>
- `dify/` - Dify 专属命令
  - `file_commands.py` - /upload, /files
  - `session_commands.py` - /reset, /reconnect

#### 2.3 命令层级设计

```
层级 1: /switch <engine>     # 切换执行引擎
层级 2: /model <provider>     # 在引擎内切换模型
层级 3: /mode llm|agent       # 引擎特定配置
```

示例：

```bash
/switch langchain              # 切到 LangChain 引擎
/model openai gpt-4o          # 在 LangChain 内切换模型
/mode agent                    # LangChain 特定：切到 agent 模式

/switch langgraph              # 切到 LangGraph 引擎  
/graph deep_agent             # LangGraph 特定：切换工作流
/model zhipu glm-4-plus       # 切换 Graph 使用的 LLM
```

### 第三部分：组件定位说明

#### 3.1 保持在 components/ 的模块

- `src/components/shared/` - 共享组件（保留）
  - memory/ - 全局内存管理
  - session/ - 会话存储
  - tools/ - 工具系统（MCP, Connector, SDK）

- `src/components/langchain/` - LangChain 特定组件（保留）
  - parsers/ - 输出解析器
  - prompts/ - 提示词模板

#### 3.2 迁移到 application/ 的模块

**从 `src/components/process/` 迁移：**

- cli.py → `application/cli/main.py`
- gui.py → `application/cli/gui/render.py`
- control.py → `application/services/langchain/service.py`（部分逻辑）
- session_control.py → `application/commands/shared/session_commands.py`
- mcp_control.py → `application/commands/langchain/tool_commands.py`
- connector_control.py → `application/commands/langchain/tool_commands.py`
- registry.py → 保留或迁移到 `application/services/`

**从 `src/ui/logo/` 迁移：**

- logo.py → `application/cli/gui/logo.py`（整合到 GUI 层）

**从 `src/components/dify/` 迁移到 `application/services/dify/`：**

- client.py → `services/dify/client.py`
- control.py → `services/dify/service.py`（重构为主服务）
- streaming.py → `services/dify/streaming.py`
- upload.py → `services/dify/upload.py`

**迁移原因**：
- Dify 与 LangChain/LangGraph 本质相同，都是执行引擎服务
- 三个引擎服务应在同一层级，结构对称
- 便于 `engine_adapters/` 统一调用

### 第四部分：执行流程对比

#### 4.1 当前流程（混乱）

```
User Input → cli.py
  → if LLM mode: 
      直接 agent.get_llm() + 构建历史 + 流式输出 + 保存记忆
  → if Agent mode:
      直接 agent.ainvoke()
  → if Dify:
      调用 dify_control.xxx()
```

#### 4.2 重构后流程（清晰）

```
User Input → cli/main.py
  → 是命令？
     ├─ Yes → CommandRegistry.dispatch()
     │         → 根据 current_engine 路由到对应命令处理器
     │           ├─ shared commands (全局可用)
     │           ├─ langchain commands (仅 langchain 引擎)
     │           ├─ langgraph commands (仅 langgraph 引擎)
     │           └─ dify commands (仅 dify 引擎)
     │         → Command.execute() → Service 层处理
     │
     └─ No → 根据 current_engine 分流
              ├─ langchain → LangChainAdapter → services/langchain/
              ├─ langgraph → LangGraphAdapter → services/langgraph/
              └─ dify → DifyAdapter → services/dify/
```

### 第五部分：LangGraph 集成预留

#### 5.1 LangGraph 服务结构（预留）

```
services/langgraph/
├── service.py           # LangGraphService 主服务
├── graph_executor.py    # Graph 执行器
├── graph_builder.py     # Graph 构建器
└── workflow_manager.py  # 工作流管理
```

#### 5.2 与 agents/langgraph/ 的关系

- `agents/langgraph/` - Graph 定义和节点实现
  - deepagents/ - DeepAgent 图定义
  - subagents/ - 子 Agent 图
- `application/services/langgraph/` - Graph 调度和执行控制
  - 负责选择和运行 Graph
  - 状态管理和流式输出

### 第六部分：迁移实施路径

#### 阶段 1：目录结构准备

1. 创建 `src/application/` 目录结构
2. 创建 `commands/`、`services/`、`adapters/`、`cli/` 子目录

#### 阶段 2：基础抽象层

1. 实现 `services/base.py` - BaseEngineService
2. 实现 `commands/base.py` - BaseCommand
3. 实现 `cli/state.py` - AppState 重构

#### 阶段 3：LangChain 引擎迁移

1. 实现 `services/langchain/` 服务
2. 实现 `adapters/langchain_adapter.py`
3. 迁移 LangChain 相关命令

#### 阶段 4：Dify 引擎迁移

1. 迁移 `components/dify/` → `services/dify/`
2. 重构 `control.py` → `service.py`（实现 BaseEngineService）
3. 实现 `engine_adapters/dify_adapter.py`
4. 实现 `commands/dify/` 命令处理器

#### 阶段 5：CLI 主循环重构

1. 重写 `cli/main.py`（精简后的主循环）
2. 实现命令注册与路由
3. GUI 层拆分（render/interact/formatter）

#### 阶段 6：测试与清理

1. 测试三种引擎切换
2. 删除旧目录：
   - `components/process/`
   - `components/dify/`
   - `ui/logo/`（整合到 `application/cli/gui/`）
3. 更新所有导入路径
4. 更新 README 和使用文档

### 第七部分：关键收益总结

1. **职责清晰**：CLI（交互）→ Commands（处理）→ Engine Adapters（适配）→ Services（实现）
2. **结构对称**：三个引擎（LangChain/LangGraph/Dify）在 services/ 层地位平等
3. **易扩展**：新增引擎只需实现 BaseEngineService + 对应的 adapter 和 commands
4. **命令分离**：每个引擎的命令独立管理，互不干扰
5. **LangGraph 就绪**：预留完整的目录结构和接口
6. **维护友好**：每层职责单一，按引擎分包，代码清晰

### 第八部分：完整架构总览

#### 8.1 最终目录结构

```
src/
├── application/                           #  应用控制层
│   ├── __init__.py
│   │
│   ├── cli/                              # CLI 应用入口
│   │   ├── __init__.py
│   │   ├── main.py                       # 主循环（精简后的 cli.py）
│   │   ├── state.py                      # AppState 定义
│   │   └── gui/                          # UI 层
│   │       ├── __init__.py
│   │       ├── render.py                 # 渲染函数（原 gui.py）
│   │       ├── interact.py               # 交互辅助（新增）
│   │       ├── formatter.py              # 数据格式化（新增）
│   │       └── logo.py                   # Logo 显示（从 ui/logo 迁移）
│   │
│   ├── commands/                          # 命令处理层（按引擎分包）
│   │   ├── __init__.py                   # 命令注册表和路由
│   │   ├── base.py                       # BaseCommand 抽象基类
│   │   ├── engine_commands.py            # /switch <engine> (全局)
│   │   │
│   │   ├── shared/                       # 共享命令（跨引擎）
│   │   │   ├── __init__.py
│   │   │   ├── system_commands.py        # help, info, exit
│   │   │   └── session_commands.py       # new, clear, restore, delete
│   │   │
│   │   ├── langchain/                    # LangChain 专属命令
│   │   │   ├── __init__.py
│   │   │   ├── model_commands.py         # /model <provider> <model>
│   │   │   ├── mode_commands.py          # /mode llm|agent, /stream on|off
│   │   │   ├── llm_commands.py           # /llms, /reload
│   │   │   └── tool_commands.py          # /mcp, /connector
│   │   │
│   │   ├── langgraph/                    # LangGraph 专属命令（预留）
│   │   │   ├── __init__.py
│   │   │   ├── graph_commands.py         # /graph <name>
│   │   │   ├── node_commands.py          # /nodes, /visualize
│   │   │   └── model_commands.py         # /model <provider> <model>
│   │   │
│   │   └── dify/                         # Dify 专属命令
│   │       ├── __init__.py
│   │       ├── file_commands.py          # /upload, /files
│   │       └── session_commands.py       # /reset, /reconnect
│   │
│   ├── services/                          # 业务服务层（按引擎分包）
│   │   ├── __init__.py                   # 引擎服务路由器
│   │   ├── base.py                       # BaseEngineService 抽象类
│   │   │
│   │   ├── langchain/                    # LangChain 引擎服务
│   │   │   ├── __init__.py
│   │   │   ├── service.py                # 主服务（实现 BaseEngineService）
│   │   │   ├── conversation.py           # 对话处理（LLM/Agent 模式）
│   │   │   ├── streaming.py              # 流式输出管理
│   │   │   └── agent_lifecycle.py        # Agent 创建/切换/销毁
│   │   │
│   │   ├── langgraph/                    # LangGraph 引擎服务（预留）
│   │   │   ├── __init__.py
│   │   │   ├── service.py                # 主服务
│   │   │   ├── graph_executor.py         # Graph 执行器
│   │   │   ├── graph_builder.py          # Graph 构建器
│   │   │   └── workflow_manager.py       # 工作流管理
│   │   │
│   │   └── dify/                         # Dify 引擎服务（从 components 迁移）
│   │       ├── __init__.py
│   │       ├── service.py                # 主服务（原 control.py 重构）
│   │       ├── client.py                 # Dify API 客户端
│   │       ├── streaming.py              # 流式处理
│   │       └── upload.py                 # 文件上传
│   │
│   └── engine_adapters/                   # 引擎适配层（分流网关）
│       ├── __init__.py
│       ├── base.py                       # BaseEngineAdapter（可选）
│       ├── langchain_adapter.py          # LangChain 适配器
│       ├── langgraph_adapter.py          # LangGraph 适配器（预留）
│       └── dify_adapter.py               # Dify 适配器
│
├── components/                            # 业务组件层
│   ├── shared/                           # 共享组件（保留）
│   │   ├── memory/                       # 全局内存管理
│   │   ├── session/                      # 会话存储
│   │   └── tools/                        # 工具系统
│   │       ├── mcp/                      # MCP 工具
│   │       ├── connector/                # Connector 工具
│   │       └── sdk/                      # SDK 工具
│   │
│   └── langchain/                        # LangChain 组件（保留）
│       ├── parsers/                      # 输出解析器
│       └── prompts/                      # 提示词模板
│
├── agents/                                # Agent 实现层
│   └── langchain/                        # LangChain Agent 实现
│       ├── adapters/
│       ├── factories/
│       ├── instances/
│       └── managers/
│
├── llm/                                   # LLM 实例层
│   └── langchain/
│       ├── adapters/
│       ├── instances/
│       └── managers/
│
├── core/                                  # 核心基础设施
│   └── langchain/
│       └── providers/
│
└── config/                                # 配置管理
    ├── env_loader.py
    ├── llm_loader.py
    └── settings.py
```

#### 8.2 各层职责矩阵

| 层级 | 目录 | 核心职责 | 关键原则 |
|------|------|----------|----------|
| **应用入口层** | `application/cli/` | 用户交互、输入输出、主循环控制 | 只做 IO，不含业务逻辑 |
| **命令处理层** | `application/commands/` | 命令解析、参数验证、命令执行 | 按引擎分包，每个命令独立 |
| **服务编排层** | `application/services/` | 业务流程编排、引擎服务实现 | 每个引擎独立服务包 |
| **引擎适配层** | `application/engine_adapters/` | 统一接口、引擎分流、调用转换 | 三大引擎的统一网关 |
| **组件实现层** | `components/` | 可复用的功能模块 | 与引擎无关的共享组件 |
| **Agent 层** | `agents/` | Agent 实例和工厂 | Agent 定义和创建 |
| **LLM 层** | `llm/` | LLM 实例和管理 | 模型封装和调用 |

#### 8.3 数据流向图

```
┌─────────────────────────────────────────────────────────────┐
│                        User Input                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
           ┌──────────────────────────────┐
           │   application/cli/main.py    │
           │    (主循环 & 输入解析)        │
           └──────────────┬───────────────┘
                          │
                  是命令？ / 是对话？
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
        ▼ 命令                              ▼ 对话
┌───────────────────┐            ┌──────────────────────┐
│ commands/         │            │ 根据 current_engine   │
│ - 根据引擎路由     │            │ 选择 engine_adapter  │
│ - 命令执行        │            └──────────┬───────────┘
└────────┬──────────┘                       │
         │                          ┌───────┴────────┐
         │                          │                │
         ▼                          ▼                ▼
┌─────────────────┐         ┌─────────────┐  ┌─────────────┐
│ services/       │         │ langchain   │  │ langgraph   │
│ - langchain     │◄────────│ _adapter    │  │ _adapter    │
│ - langgraph     │         └─────────────┘  └─────────────┘
│ - dify          │                │
└─────────┬───────┘         ┌─────────────┐
          │                 │ dify        │
          │                 │ _adapter    │
          │                 └──────┬──────┘
          │                        │
          ▼                        ▼
┌──────────────────────────────────────────┐
│        services/<engine>/service.py      │
│        - 引擎特定的业务逻辑               │
│        - 调用底层 agents/llm/components  │
└──────────────────────────────────────────┘
```

#### 8.4 引擎服务对比

| 特性 | LangChain 引擎 | LangGraph 引擎 | Dify 引擎 |
|------|---------------|---------------|-----------|
| **服务位置** | `services/langchain/` | `services/langgraph/` | `services/dify/` |
| **适配器** | `langchain_adapter.py` | `langgraph_adapter.py` | `dify_adapter.py` |
| **命令包** | `commands/langchain/` | `commands/langgraph/` | `commands/dify/` |
| **模型切换** | ✅ `/model <provider>` | ✅ `/model <provider>` | ❌ 云端固定 |
| **模式切换** | ✅ LLM/Agent 模式 | ❌ 固定 Graph 模式 | ❌ 固定云端模式 |
| **特有命令** | /mode, /stream, /mcp | /graph, /nodes | /upload, /files |
| **底层依赖** | `agents/langchain/` | `agents/langgraph/` | HTTP API |

#### 8.5 命令可用性矩阵

| 命令 | LangChain | LangGraph | Dify | 说明 |
|------|-----------|-----------|------|------|
| `/switch <engine>` | ✅ | ✅ | ✅ | 全局命令 |
| `/help` | ✅ | ✅ | ✅ | 全局命令 |
| `/info` | ✅ | ✅ | ✅ | 全局命令 |
| `/new` | ✅ | ✅ | ✅ | 共享会话命令 |
| `/clear` | ✅ | ✅ | ✅ | 共享会话命令 |
| `/model` | ✅ | ✅ | ❌ | 引擎特定 |
| `/mode` | ✅ | ❌ | ❌ | 仅 LangChain |
| `/stream` | ✅ | ❌ | ❌ | 仅 LangChain |
| `/llms` | ✅ | ❌ | ❌ | 仅 LangChain |
| `/mcp` | ✅ | ✅ | ❌ | 工具管理 |
| `/graph` | ❌ | ✅ | ❌ | 仅 LangGraph |
| `/nodes` | ❌ | ✅ | ❌ | 仅 LangGraph |
| `/upload` | ❌ | ❌ | ✅ | 仅 Dify |
| `/files` | ❌ | ❌ | ✅ | 仅 Dify |
| `/reset` | ❌ | ❌ | ✅ | 仅 Dify |

#### 8.6 AppState 结构设计

```python
class AppState:
    """应用全局状态"""
    
    def __init__(self):
        self.console = Console()
        
        #  核心：当前执行引擎
        self.current_engine: str = "langchain"  # langchain | langgraph | dify
        
        #  每个引擎的独立配置
        self.engine_configs = {
            "langchain": {
                "provider": "zhipu",
                "model": "glm-4-plus",
                "mode": "llm",          # llm | agent
                "streaming": True,
                "agent": None,          # Agent 实例
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
                "control": None,        # DifyControl 实例
            }
        }
        
        # 共享组件
        self.global_memory = None           # GlobalMemoryManager
        self.session_manager = None         # SessionManager
        self.session_id = None              # 当前会话 ID
```

## 文档输出位置

`docs/refactoring/process_architecture_refactoring.md`

## 文档风格

- 使用清晰的标题层级
- 包含代码示例和目录树
- 使用表格对比当前/未来架构
- 标注关键模块的职责边界
- 提供完整的数据流向图和架构总览