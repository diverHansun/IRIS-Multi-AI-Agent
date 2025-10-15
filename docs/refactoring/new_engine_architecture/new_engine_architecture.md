# Multi-AI-Agent 架构重构方案：引擎模式化

> **版本**：v3.0.0
> 
> **创建时间**：2025-10-15
> 
> **作者**：diverHansun

---

## 一、重构目标

将项目从基于"技术栈"的命名方式转换为基于"引擎模式"的架构组织，使得：
1. 目录结构反映实际的使用模式，而非底层技术栈
2. 为四种引擎模式提供清晰的边界和职责划分
3. 统一核心抽象层，避免不必要的技术栈分离
4. 为后续引入 DeepAgents 和 AgentFlow 奠定基础

---

## 二、四引擎架构定义

### 2.1 引擎总览

| 引擎名称 | 切换命令 | 内部模式 | 核心特征 | 技术栈 |
|---------|---------|---------|---------|--------|
| **LLM** | `/switch llm` | - | 纯 LLM 对话，无工具调用 | LangChain LLM |
| **Agent** | `/switch agent` | `/mode basic`<br>`/mode deep` | 单一智能体，支持工具调用 | LangChain + 部分 LangGraph |
| **AgentFlow** | `/switch agentflow` | - | 多智能体工作流编排 | LangGraph StateGraph |
| **Dify** | `/switch dify` | - | 外部 Dify 引擎集成 | Dify API |

### 2.2 引擎详解

#### LLM 引擎
- **定位**：最基础的 LLM 对话引擎
- **能力**：纯文本生成，支持流式输出，支持历史对话（记忆）
- **限制**：不支持工具调用、不支持多轮规划
- **应用场景**：简单对话、文本生成、摘要提取
- **代码层**：`src/llm/`

#### Agent 引擎（两种模式）
- **定位**：单一智能体引擎
- **能力**：LLM + 工具调用 + ReAct 循环
- **模式划分**：
  - **Basic 模式**：基于 LangChain 的基础智能体
    - 使用较简单的模型（如 glm-4-flash）
    - 适合常规工具调用任务
  - **Deep 模式**：基于 LangChain + 部分 LangGraph 的高级智能体
    - 使用更强的模型（如 glm-4-plus）
    - 具备更强的思考能力
    - 可能包含 RAG、TODO 清单等高级功能（未来）
    - 本质仍是单一 agent，不涉及多智能体编排
- **模式切换**：在 agent 引擎内使用 `/mode basic` 和 `/mode deep` 切换
- **代码层**：`src/agents/basicagents/` + `src/agents/deepagents/`
- **应用场景**：需要工具调用的任务、自主决策、信息检索

#### AgentFlow 引擎
- **定位**：多智能体协作编排引擎
- **能力**：使用 LangGraph StateGraph 编排多个 Agent
- **特点**：
  - 可以调用 BasicAgents 作为节点
  - 可以调用 DeepAgents 作为节点
  - 支持复杂的工作流、条件分支、状态管理
- **代码层**：使用 `src/components/graph/` 编排各类 agents
- **应用场景**：复杂的多步任务、需要多个专业 Agent 协作的场景

#### Dify 引擎
- **定位**：外部 Dify 平台集成
- **能力**：通过 Dify API 访问预构建的工作流
- **应用场景**：使用 Dify 平台已有的工作流

---

## 三、用户命令体验

### 3.1 引擎切换命令

```bash
# 启动时默认进入 agent 引擎（basic 模式）
$ python main.py
> 当前引擎: agent (basic)

# 切换到其他引擎
> /switch llm
✓ 已切换到 LLM 引擎

> /switch agent
✓ 已切换到 Agent 引擎 (basic 模式)

> /switch agentflow
✓ 已切换到 AgentFlow 引擎

> /switch dify
✓ 已切换到 Dify 引擎
```

### 3.2 Agent 引擎模式切换

```bash
# 在 agent 引擎内切换模式
> /switch agent
✓ 已切换到 Agent 引擎 (basic 模式)

> /mode deep
✓ 已切换到 deep 模式

> /mode basic
✓ 已切换到 basic 模式
```

---

## 四、AppState 状态管理

### 4.1 引擎配置结构

```python
DEFAULT_ENGINE_CONFIGS = {
    "llm": {
        "provider": "zhipu",
        "model": "glm-4-flash",
        "streaming": True,
    },
    "agent": {
        "agent_type": "basic",      # "basic" | "deep"
        "provider": "zhipu",
        "model": "glm-4-flash",     # 根据 agent_type 使用不同模型
        "streaming": True,
        "agent_instance": None,
    },
    "agentflow": {
        "graph_name": None,
        "provider": None,
        "model": None,
        "graph_instance": None,
    },
    "dify": {
        "conversation_id": None,
        "files": [],
        "control": None,
        "initialized": False,
    },
}
```

### 4.2 状态管理说明

- **current_engine**：当前激活的引擎（llm / agent / agentflow / dify）
- **agent.agent_type**：Agent 引擎的当前模式（basic / deep）
- **共享组件**：session、memory 在所有引擎间共享，不区分引擎

---

## 五、目录结构对照

### 5.1 src/ 核心层重构

#### agents 模块

```diff
src/agents/
- ├── langchain/              # 旧：基于技术栈命名
+ ├── basicagents/            # 新：基础智能体（Agent 引擎 basic 模式）
  │   ├── adapters/
  │   ├── factories/
  │   ├── instances/
  │   └── managers/
+ └── deepagents/             # 新：高级智能体（Agent 引擎 deep 模式，未来）
+     └── ...
```

**说明**：
- `basicagents`：Agent 引擎 basic 模式的实现（全部使用 LangChain）
- `deepagents`：Agent 引擎 deep 模式的实现（LangChain + 部分 LangGraph，但仍是单一 agent）
- 两者通过 `/mode` 命令在 Agent 引擎内切换

#### components 模块

```diff
src/components/
- ├── langchain/              # 旧：基于技术栈命名
+ ├── basicagents/            # 新：BasicAgents 专用组件
  │   ├── parsers/
  │   │   └── json_react_output_parser.py
  │   └── prompts/
  │       ├── registry.py
  │       └── tooling.py
+ ├── deepagents/             # 新：DeepAgents 专用组件（预留）
+ │   └── .gitkeep
+ ├── graph/                  # 新：Graph 相关组件（通用）
+ │   ├── core_nodes/         # 基础节点（Tool、RAG、Memory、Router）
+ │   │   ├── tool_node.py
+ │   │   ├── rag_node.py
+ │   │   ├── memory_node.py
+ │   │   ├── router_node.py
+ │   │   ├── control_node.py
+ │   │   └── checkpoint_node.py
+ │   ├── graph_builder.py    # Graph 构建器
+ │   └── state_manager.py    # 状态管理
  └── shared/                 # 保持：共享组件
      ├── memory/
      ├── session/
      └── tools/
```

**说明**：
- `basicagents`：BasicAgents 使用的组件（prompts、parsers）
- `deepagents`：DeepAgents 专用组件（目前预留，未来可能有特殊组件）
- `graph`：Graph 相关组件，可被 DeepAgents 和 AgentFlow 共同使用
- `shared`：所有引擎共享的组件（tools、memory、session）

#### llm 模块

```diff
src/llm/
- ├── langchain/              # ❌ 旧：多余的 langchain 层级
- │   ├── adapters/
- │   ├── instances/
- │   ├── managers/
- │   └── utils/
+ ├── adapters/               # ✅ 新：直接提升到 llm/ 下
+ │   ├── base.py
+ │   ├── ollama_adapter.py
+ │   ├── openai_adapter.py
+ │   └── zhipu_adapter.py
+ ├── instances/              # ✅ 新：直接提升到 llm/ 下
+ │   ├── ollama_llm.py
+ │   ├── openai_llm.py
+ │   └── zhipu_llm.py
+ ├── managers/               # ✅ 新：直接提升到 llm/ 下
+ │   └── llm_manager.py
+ └── utils/                  # ✅ 新：直接提升到 llm/ 下
+     └── streaming.py
```

**说明**：
- 去除 `langchain` 这一层，因为 LLM 层只有一种实现方式
- 直接将 adapters、instances、managers、utils 提升到 `src/llm/` 下

#### core 模块

```diff
src/core/
- ├── langchain/              # 旧：多余的 langchain 层级
- │   └── providers/
+ └── providers/              # 新：统一的 Provider 层
      ├── provider_registry.py
      └── utils/
          └── ollama.py
```

**说明**：
- 去除 `langchain` 这一层分类
- 统一所有 LLM Provider 的抽象接口
- `provider_registry.py` 从配置文件读取 provider 信息，供 catalog 使用

---

### 5.2 application/ 应用层重构

#### engine_adapters 模块

```diff
application/engine_adapters/
- ├── langchain_adapter.py    # 旧：基于技术栈
- ├── langgraph_adapter.py    # 旧：基于技术栈
+ ├── llm_adapter.py          # 新：LLM 引擎适配器
+ ├── agent_adapter.py        # 新：Agent 引擎适配器（统一处理 basic 和 deep）
+ ├── agentflow_adapter.py    # 新：AgentFlow 引擎适配器
  └── dify_adapter.py         # 保持：Dify 引擎适配器
```

**agent_adapter.py 的工作机制**：
```python
class AgentAdapter:
    def execute(self, app_state, user_input):
        agent_config = app_state.get_engine_config("agent")
        agent_type = agent_config.get("agent_type", "basic")  # 读取模式
        
        if agent_type == "basic":
            from application.services.agent.basic import BasicAgentService
            service = BasicAgentService()
        elif agent_type == "deep":
            from application.services.agent.deep import DeepAgentService
            service = DeepAgentService()
        
        return service.execute(user_input, agent_config)
```

**说明**：
- 4 个 adapter 对应 4 个引擎
- `agent_adapter` 根据 `agent_type` 字段分发到 basic 或 deep 服务
- adapter 负责引擎分流，是引擎切换的关键模块

#### commands 模块

```diff
application/commands/
- ├── langchain/              # 旧：基于技术栈
- │   ├── llm_commands.py
- │   ├── mode_commands.py
- │   ├── model_commands.py
- │   └── tool_commands.py
- └── langgraph/              # 旧：基于技术栈
-     ├── graph_commands.py
-     ├── model_commands.py
-     └── node_commands.py
+ ├── llm/                    # 新：LLM 引擎命令（可选）
+ ├── agent/                  # 新：Agent 引擎命令
+ │   ├── mode_commands.py    # /mode basic / /mode deep
+ │   ├── model_commands.py
+ │   └── tool_commands.py
+ ├── agentflow/              # 新：AgentFlow 引擎命令
+ │   ├── graph_commands.py
+ │   ├── model_commands.py
+ │   └── node_commands.py
  ├── dify/                   # 保持：Dify 引擎命令
  └── shared/                 # 保持：共享命令
      ├── session_commands.py
      └── system_commands.py
```

**命令系统更新**：
```diff
# 旧命令（废弃）
- /mode agent                 # 切换到 agent 模式
- /mode llm                   # 切换到 llm 模式

# 新命令
+ /switch llm                 # 切换到 LLM 引擎
+ /switch agent               # 切换到 Agent 引擎（默认 basic 模式）
+ /switch agentflow           # 切换到 AgentFlow 引擎
+ /switch dify                # 切换到 Dify 引擎

# Agent 引擎内模式切换
+ /mode basic                 # 切换到 basic 模式
+ /mode deep                  # 切换到 deep 模式
```

#### services 模块

```diff
application/services/
- ├── langchain/              # 旧：基于技术栈
- │   ├── service.py
- │   ├── agent_lifecycle.py
- │   ├── conversation.py
- │   └── streaming.py
- └── langgraph/              # 旧：基于技术栈
-     ├── service.py
-     ├── graph_executor.py
-     └── workflow_manager.py
+ ├── llm/                    # 新：LLM 引擎服务
+ │   ├── service.py
+ │   ├── streaming.py
+ │   └── conversation.py     # 历史对话管理
+ ├── agent/                  # 新：Agent 引擎服务
+ │   ├── basic/              # BasicAgent 服务
+ │   │   ├── service.py
+ │   │   ├── agent_lifecycle.py
+ │   │   ├── conversation.py
+ │   │   └── streaming.py
+ │   └── deep/               # DeepAgent 服务（未来）
+ │       └── ...
+ ├── agentflow/              # 新：AgentFlow 引擎服务
+ │   ├── service.py
+ │   ├── graph_executor.py
+ │   └── workflow_manager.py
  ├── dify/                   # 保持：Dify 引擎服务
  └── shared/                 # 保持：共享服务
```

**说明**：
- 新增 `services/llm/`：处理纯 LLM 对话，包含历史管理
- `services/agent/basic/`：BasicAgent 服务（调用 `src/agents/basicagents/`）
- `services/agent/deep/`：DeepAgent 服务（调用 `src/agents/deepagents/`，未来）
- `services/agentflow/`：编排多个 Agent，使用 `src/components/graph/`
- services 层面限制 llm 引擎不能访问 tools

#### catalog 模块

```diff
application/services/catalog/
- ├── langchain/              # 旧：基于技术栈
- │   └── catalog.py
- └── langgraph/              # 旧：基于技术栈
-     └── catalog.py
+ ├── llm/                    # 新：LLM catalog（可选）
+ │   └── catalog.py
+ ├── agent/                  # 新：Agent catalog
+ │   ├── basic/              # BasicAgent catalog
+ │   │   └── catalog.py
+ │   └── deep/               # DeepAgent catalog（未来）
+ │       └── catalog.py
+ ├── agentflow/              # 新：AgentFlow catalog
+ │   └── catalog.py
  └── dify/                   # 保持：Dify catalog
      └── catalog.py
```

**catalog 数据流**：
```
src/core/providers/provider_registry.py（提供所有 provider + model）
    ↓
BasicAgentCatalog（筛选适合 basic 模式的模型）
    → 返回：zhipu/glm-4-flash, openai/gpt-4o-mini
    
DeepAgentCatalog（筛选适合 deep 模式的强模型）
    → 返回：zhipu/glm-4-plus, openai/gpt-4o
```

**说明**：
- `catalog/agent/basic/`：返回可用的 provider + model 组合（适合 basicagent）
- `catalog/agent/deep/`：返回可用的 provider + model 组合（适合 deepagent，强模型）
- `catalog/agentflow/`：返回可用的工作流图
- catalog 基于 `provider_registry.py` 筛选数据

---

## 六、导入路径迁移指南

### 1. src/agents 相关导入

```python
# 旧导入
from src.agents.basicagents import agent_manager
from src.agents.basicagents.instances import BaseAgent, ZhipuAgent
from src.agents.basicagents.factories import agent_factory

# 新导入
from src.agents.basicagents import agent_manager
from src.agents.basicagents.instances import BaseAgent, ZhipuAgent
from src.agents.basicagents.factories import agent_factory
```

### 2. src/components 相关导入

```python
# 旧导入
from src.components.basicagents.parsers import JsonReactOutputParser
from src.components.basicagents.prompts import registry

# 新导入
from src.components.basicagents.parsers import JsonReactOutputParser
from src.components.basicagents.prompts import registry
```

### 3. src/llm 相关导入

```python
# 旧导入
from src.llm.managers import llm_manager
from src.llm.adapters import ZhipuAdapter
from src.llm.instances import OllamaLLM

# 新导入
from src.llm.managers import llm_manager
from src.llm.adapters import ZhipuAdapter
from src.llm.instances import OllamaLLM
```

### 4. src/core 相关导入

```python
# 旧导入
from src.core.providers import provider_registry
from src.core.providers.utils import list_ollama_models

# 新导入
from src.core.providers import provider_registry
from src.core.providers.utils import list_ollama_models
```

### 5. application/engine_adapters 相关导入

```python
# 旧导入
from application.engine_adapters.langchain_adapter import LangChainAdapter
from application.engine_adapters.langgraph_adapter import LangGraphAdapter

# 新导入
from application.engine_adapters.agent_adapter import AgentAdapter
from application.engine_adapters.agentflow_adapter import AgentFlowAdapter
```

### 6. application/services 相关导入

```python
# 旧导入
from application.services.langchain import LangChainService
from application.services.langgraph import LangGraphService

# 新导入
from application.services.agent import AgentService
from application.services.agentflow import AgentFlowService
```

### 7. application/commands 相关导入

```python
# 旧导入
from application.commands.langchain import mode_commands
from application.commands.langgraph import graph_commands

# 新导入
from application.commands.agent import model_commands
from application.commands.agentflow import graph_commands
```

---

## 七、受影响文件统计

### src/ 层

| 模块 | 受影响文件数 | 主要变更 |
|------|-------------|---------|
| `src/agents/langchain` → `basicagents` | 所有文件 | 目录重命名 + 导入路径更新 |
| `src/components/langchain` → `basicagents` | 所有文件 | 目录重命名 + 导入路径更新 |
| `src/llm/langchain` → `llm` | 所有文件 | 目录提升 + 导入路径更新 |
| `src/core/langchain/providers` → `providers` | 所有文件 | 目录提升 + 导入路径更新 |

**导入更新文件清单**：
- agents 模块导入：7 个文件
- components 模块导入：1 个文件
- llm 模块导入：9 个文件
- core 模块导入：14 个文件

### application/ 层

| 模块 | 受影响文件数 | 主要变更 |
|------|-------------|---------|
| `engine_adapters/` | 2 个文件 | 文件重命名 + 类重命名 |
| `commands/langchain` → `agent` | 4 个文件 | 目录重命名（删除 mode_commands.py） |
| `commands/langgraph` → `agentflow` | 3 个文件 | 目录重命名 |
| `services/langchain` → `agent` | 4 个文件 | 目录重命名 + 导入更新 |
| `services/langgraph` → `agentflow` | 3 个文件 | 目录重命名 + 导入更新 |
| `services/catalog/langchain` → `catalog/agent/basicagents` | 1 个文件 | 目录重组 |
| `services/catalog/langgraph` → `catalog/agentflow` | 1 个文件 | 目录重命名 |

**新建**：
- `application/services/llm/` 目录及相关服务文件
- `application/engine_adapters/llm_adapter.py`

---

## 八、实施步骤

### Phase 1: src/ 核心层重构（优先级：高）

#### Step 1.1: 重命名 agents 模块
```bash
# 重命名目录
src/agents/langchain/ → src/agents/basicagents/

# 更新导入路径（7个文件）
- src/application/services/langchain/service.py
- src/application/services/catalog/langchain/catalog.py
- src/application/services/langchain/agent_lifecycle.py
- src/agents/langchain/factories/ollama_factory.py
- src/agents/langchain/managers/agent_manager.py
- src/agents/langchain/factories/openai_factory.py
- src/agents/langchain/factories/zhipu_factory.py
```

#### Step 1.2: 重命名 components 模块
```bash
# 重命名目录
src/components/langchain/ → src/components/basicagents/

# 更新导入路径（1个文件）
- src/agents/langchain/adapters/zhipu_agent_adapter.py
```

#### Step 1.3: 重构 llm 模块
```bash
# 提升目录层级
src/llm/langchain/adapters/   → src/llm/adapters/
src/llm/langchain/instances/  → src/llm/instances/
src/llm/langchain/managers/   → src/llm/managers/
src/llm/langchain/utils/      → src/llm/utils/

# 删除空目录
src/llm/langchain/

# 更新导入路径（9个文件）
- src/application/services/langchain/service.py
- src/application/services/langchain/streaming.py
- src/agents/langchain/instances/base_agent.py
- src/agents/langchain/instances/ollama_agent.py
- src/agents/langchain/instances/openai_agent.py
- src/agents/langchain/instances/zhipu_agent.py
- src/agents/langchain/instances/zhipu_fcall_agent.py
- src/agents/langchain/managers/agent_manager.py
- src/llm/langchain/managers/llm_manager.py
```

#### Step 1.4: 重构 core 模块
```bash
# 提升目录层级
src/core/langchain/providers/ → src/core/providers/

# 删除空目录
src/core/langchain/

# 更新导入路径（14个文件）
- src/application/services/catalog/langchain/catalog.py
- src/llm/langchain/adapters/base.py
- src/llm/langchain/__init__.py
- src/llm/langchain/utils/streaming.py
- src/agents/langchain/factories/ollama_factory.py
- src/llm/langchain/adapters/ollama_adapter.py
- src/llm/langchain/adapters/openai_adapter.py
- src/llm/langchain/adapters/zhipu_adapter.py
- src/agents/langchain/managers/agent_manager.py
- src/agents/langchain/adapters/ollama_agent_adapter.py
- src/agents/langchain/adapters/openai_agent_adapter.py
- src/agents/langchain/adapters/zhipu_agent_adapter.py
- src/agents/langchain/adapters/base.py
- src/llm/langchain/managers/llm_manager.py
```

#### Step 1.5: 更新模块文档
```bash
# 更新各模块的 __init__.py 文档字符串
- src/agents/basicagents/__init__.py
- src/components/basicagents/__init__.py
- src/llm/__init__.py
- src/core/providers/__init__.py
```

---

### Phase 2: application/ 应用层重构（优先级：高）

#### Step 2.1: 重命名 engine_adapters
```bash
# 重命名文件
application/engine_adapters/langchain_adapter.py → agent_adapter.py
application/engine_adapters/langgraph_adapter.py → agentflow_adapter.py

# 新建文件
application/engine_adapters/llm_adapter.py

# 更新类名
LangChainAdapter → AgentAdapter
LangGraphAdapter → AgentFlowAdapter

# 更新引用这些 adapter 的文件
- application/engine_commands.py (或主入口文件)
```

#### Step 2.2: 重命名 commands 模块
```bash
# 重命名目录
application/commands/langchain/ → application/commands/agent/
application/commands/langgraph/ → application/commands/agentflow/

# 新建目录（如需要）
application/commands/llm/

# 修改 mode_commands.py
# 将 /mode agent 和 /mode llm 改为 /mode basic 和 /mode deep

# 更新命令注册文件
- application/commands/__init__.py
- application/commands/parser.py
```

#### Step 2.3: 重命名 services 模块
```bash
# 重构目录结构
application/services/langchain/ → application/services/agent/basic/
application/services/langgraph/ → application/services/agentflow/

# 新建目录
application/services/llm/
application/services/llm/service.py
application/services/llm/streaming.py
application/services/llm/conversation.py

application/services/agent/deep/  (预留未来使用)

# 更新服务注册文件
- application/services/__init__.py
```

#### Step 2.4: 重组 catalog 模块
```bash
# 重组目录结构
application/services/catalog/langchain/ → application/services/catalog/agent/basic/
application/services/catalog/langgraph/ → application/services/catalog/agentflow/

# 新建目录
application/services/catalog/llm/ (可选)
application/services/catalog/agent/deep/ (预留)

# 更新 catalog 相关导入
- application/services/catalog/__init__.py
```

#### Step 2.5: 更新 AppState
```bash
# 修改 src/application/cli/state.py

# 旧配置
DEFAULT_ENGINE_CONFIGS = {
    "langchain": {...},
    "langgraph": {...},
    "dify": {...},
}

# 新配置
DEFAULT_ENGINE_CONFIGS = {
    "llm": {...},
    "agent": {"agent_type": "basic", ...},
    "agentflow": {...},
    "dify": {...},
}
```

---

### Phase 3: 文档更新（优先级：中）

#### Step 3.1: 重命名架构指南
```bash
# 重命名文件
docs/langgraph-architecture/langgraph_guide.md → docs/langgraph-architecture/agentflow_guide.md
```

#### Step 3.2: 更新架构指南内容
```markdown
# 更新内容要点
- 强调四种引擎模式（LLM、Agent、AgentFlow、Dify）
- 更新所有目录路径引用
- 更新所有导入示例
- 添加 BasicAgents 和 DeepAgents 的区别说明
- 添加 AgentFlow 如何编排 BasicAgents 和 DeepAgents 的说明
```

#### Step 3.3: 创建迁移指南
```bash
# 新建文件
docs/refactoring/migration_guide_v3.md

# 内容
- 旧版本到新版本的迁移步骤
- 常见问题和解决方案
- 破坏性变更清单
```

---

### Phase 4: 测试和验证（优先级：高）

#### Step 4.1: 导入测试
```bash
# 验证所有模块可以正常导入
python -c "from src.agents.basicagents import agent_manager"
python -c "from src.components.basicagents.parsers import JsonReactOutputParser"
python -c "from src.llm.managers import llm_manager"
python -c "from src.core.providers import provider_registry"
```

#### Step 4.2: 功能测试
```bash
# 运行现有测试套件
pytest tests/

# 测试四种引擎切换
/switch llm
/switch agent
/switch agentflow
/switch dify
```

#### Step 4.3: 集成测试
```bash
# 测试完整的工作流
- LLM 引擎对话测试
- Agent 引擎工具调用测试
- AgentFlow 多智能体协作测试
- Dify 集成测试
```

---

## 九、迁移检查清单

### 9.1 目录重命名
- [ ] `src/agents/langchain` → `src/agents/basicagents`
- [ ] `src/components/langchain` → `src/components/basicagents`
- [ ] 新建 `src/components/deepagents/` (预留)
- [ ] 新建 `src/components/graph/` (graph 组件)
- [ ] `src/llm/langchain/*` → `src/llm/*` (提升)
- [ ] `src/core/langchain/providers` → `src/core/providers` (提升)
- [ ] `application/engine_adapters/langchain_adapter.py` → `agent_adapter.py`
- [ ] `application/engine_adapters/langgraph_adapter.py` → `agentflow_adapter.py`
- [ ] `application/commands/langchain` → `application/commands/agent`
- [ ] `application/commands/langgraph` → `application/commands/agentflow`
- [ ] `application/services/langchain` → `application/services/agent`
- [ ] `application/services/langgraph` → `application/services/agentflow`
- [ ] `application/services/catalog/langchain` → `application/services/catalog/agent/basicagents`
- [ ] `application/services/catalog/langgraph` → `application/services/catalog/agentflow`

### 9.2 新建目录/文件
- [ ] `src/components/deepagents/` (预留)
- [ ] `src/components/graph/` (graph 组件目录)
- [ ] `application/services/llm/`
- [ ] `application/services/llm/service.py`
- [ ] `application/services/llm/streaming.py`
- [ ] `application/services/llm/conversation.py`
- [ ] `application/services/agent/basic/` (重组)
- [ ] `application/services/agent/deep/` (预留)
- [ ] `application/services/catalog/agent/basic/`
- [ ] `application/services/catalog/agent/deep/` (预留)
- [ ] `application/engine_adapters/llm_adapter.py`
- [ ] `application/commands/llm/` (可选)

### 9.3 导入路径更新
- [ ] src/agents 相关导入 (7个文件)
- [ ] src/components 相关导入 (1个文件)
- [ ] src/llm 相关导入 (9个文件)
- [ ] src/core 相关导入 (14个文件)
- [ ] application/engine_adapters 相关导入
- [ ] application/services 相关导入
- [ ] application/commands 相关导入

### 9.4 类名和变量重命名
- [ ] `LangChainAdapter` → `AgentAdapter`
- [ ] `LangGraphAdapter` → `AgentFlowAdapter`
- [ ] `LangChainService` → `BasicAgentService`
- [ ] `LangGraphService` → `AgentFlowService`
- [ ] `LangChainCatalogService` → `BasicAgentCatalogService`
- [ ] `LangGraphCatalogService` → `AgentFlowCatalogService`

### 9.5 AppState 更新
- [ ] 修改 `DEFAULT_ENGINE_CONFIGS`：langchain → agent, langgraph → agentflow
- [ ] 新增 llm 引擎配置
- [ ] agent 引擎配置增加 `agent_type` 字段

### 9.6 命令系统更新
- [ ] 修改 `/mode` 命令：`/mode agent` 和 `/mode llm` → `/mode basic` 和 `/mode deep`
- [ ] 实现 `/switch llm` 命令
- [ ] 实现 `/switch agent` 命令（默认 basic 模式）
- [ ] 实现 `/switch agentflow` 命令
- [ ] `/switch dify` 命令保持不变
- [ ] 更新命令帮助文档

### 9.7 文档更新
- [ ] 重命名 `langgraph_guide.md` → `agentflow_guide.md`
- [ ] 更新架构指南内容
- [ ] 本文档 `new_engine_architecture.md` 已完成
- [ ] 更新 README.md
- [ ] 更新相关教程文档

### 9.8 测试和验证
- [ ] 所有模块导入测试通过
- [ ] 单元测试通过
- [ ] 集成测试通过
- [ ] 四种引擎切换功能正常
- [ ] 工具调用功能正常
- [ ] 工作流编排功能正常

---

## 十、本轮实施范围和细节说明

### 10.1 Deep Agent 实施范围

**本轮重构（Phase 1-4）**：
- 只创建目录结构和占位符，不实现具体功能
- `/mode deep` 命令暂时降级到 basic 模式

**具体实施**：

#### 目录结构
```
src/agents/deepagents/
├── __init__.py          # 空实现，包含文档注释
└── README.md            # 说明预留目的和未来计划

application/services/agent/deep/
├── __init__.py          # 空实现
└── README.md            # 说明未来实现计划

application/services/catalog/agent/deep/
├── __init__.py          # 空实现
└── README.md            # 说明未来的 catalog 规划
```

#### AgentAdapter 实现
```python
class AgentAdapter:
    def execute(self, app_state, user_input):
        agent_config = app_state.get_engine_config("agent")
        agent_type = agent_config.get("agent_type", "basic")
        
        if agent_type == "basic":
            from application.services.agent.basic import BasicAgentService
            service = BasicAgentService()
        elif agent_type == "deep":
            # 本轮暂时降级到 basic
            from application.services.agent.basic import BasicAgentService
            service = BasicAgentService()
            app_state.console.print("[yellow]Deep mode is under development, using basic mode[/]")
        
        return service.execute(user_input, agent_config)
```

#### /mode deep 行为
- 执行时显示提示："Deep mode is under development, using basic mode"
- 实际使用 BasicAgentService
- `agent_type` 字段正常更新为 "deep"（为未来做准备）

**未来实施（Phase 5+）**：
- 实现 DeepAgents 的核心功能（RAG、TODO 清单、思考链等）
- 实现 DeepAgentService
- 完善 DeepAgent Catalog

### 10.2 components/graph/ 实施范围

**本轮重构（Phase 1-4）**：
- 全新设计，只创建接口定义和文档，不实现具体功能
- 为 DeepAgents 和 AgentFlow 预留统一的 Graph 组件基础

**具体实施**：

#### 目录结构
```
src/components/graph/
├── __init__.py              # 空实现，导出接口
├── README.md                # 说明 Graph 组件的设计目标
├── core_nodes/
│   ├── __init__.py
│   └── README.md            # 列出计划实现的节点类型
├── graph_builder.py         # 接口定义（空实现）
└── state_manager.py         # 接口定义（空实现）
```

#### README.md 内容要点
```markdown
# Graph Components

本目录包含 LangGraph 相关的通用组件，供 DeepAgents 和 AgentFlow 共同使用。

## 设计目标
- 提供统一的节点接口（Tool、RAG、Memory、Router 等）
- 提供 Graph 构建器，简化 StateGraph 创建
- 提供状态管理器，统一状态流转逻辑

## 计划实现的节点类型
- tool_node.py: 工具调用节点
- rag_node.py: RAG 检索节点
- memory_node.py: 记忆管理节点
- router_node.py: 条件路由节点
- control_node.py: 控制流节点（暂停、终止等）
- checkpoint_node.py: 状态快照节点

## 状态：预留
本组件目前为预留状态，将在 Phase 5+ 基于 LangGraph 官方库实现。
```

**未来实施（Phase 5+）**：
- 基于 LangGraph 官方库实现各类节点
- 实现 GraphBuilder
- 实现 StateManager
- 供 DeepAgents 和 AgentFlow 使用

### 10.3 services/llm/ 实施范围

**本轮重构（Phase 1-4）**：
- 实现完整的 LLM 引擎服务
- 复用 conversation.py 逻辑，但移除 agent 依赖
- 完全禁止工具调用

**具体实施**：

#### 目录结构
```
application/services/llm/
├── __init__.py
├── service.py           # LLM 引擎服务主类
├── conversation.py      # 会话管理（改造自 langchain/conversation.py）
└── streaming.py         # 流式输出（改造自 langchain/streaming.py）
```

#### LLMService 实现要点
```python
class LLMService(BaseEngineService):
    """纯 LLM 对话服务，不支持工具调用"""
    
    async def initialize(self, ctx):
        # 直接初始化 LLM，不需要 agent
        from src.llm.managers import LLMManager
        config = ctx.get_engine_config("llm")
        provider = config.get("provider")
        model = config.get("model")
        
        # 创建 LLM 实例
        llm_instance = LLMManager.create_llm(provider, model)
        config["llm_instance"] = llm_instance
        
        return {"type": "success", "message": f"LLM initialized: {provider}/{model}"}
    
    async def handle_query(self, ctx, query: str):
        # 直接使用 llm_instance，不通过 agent
        config = ctx.get_engine_config("llm")
        llm = config.get("llm_instance")
        
        # 获取历史对话
        history = ctx.global_memory.get_session_history(ctx.session_id)
        
        # 构建提示词（包含历史）
        prompt = self._build_prompt(query, history)
        
        # 调用 LLM（流式或非流式）
        if config.get("streaming"):
            response = await self._stream_response(llm, prompt)
        else:
            response = await llm.ainvoke(prompt)
        
        return response
```

#### conversation.py 改造要点
- 移除 `agent.get_llm()` 调用
- 直接使用 `config["llm_instance"]`
- 保留历史对话管理逻辑
- 保留提示词构建逻辑

#### 工具调用限制
- 在 service 层面确保不传递任何 tools 参数
- LLM 初始化时不绑定工具
- 如果用户尝试使用工具相关命令，返回错误提示

### 10.4 实例管理策略

**生命周期管理**：

| 字段 | 初始化时机 | 缓存策略 | 清空时机 |
|------|-----------|---------|---------|
| `llm.llm_instance` | 懒加载 | 长驻缓存 | 切换 provider/model 时 |
| `agent.agent_instance` | 懒加载 | 长驻缓存 | 切换 provider/model 或 agent_type 时 |
| `agentflow.graph_instance` | 懒加载 | 长驻缓存 | 切换 graph_name 时 |

**实现逻辑**：

```python
# src/application/cli/state.py 增加辅助方法

class AppState:
    def clear_engine_instance(self, engine: str, keys: list[str] = None):
        """清空引擎实例缓存"""
        config = self.get_engine_config(engine)
        if keys is None:
            # 清空所有可能的实例字段
            keys = ["llm_instance", "agent_instance", "graph_instance"]
        
        for key in keys:
            if key in config:
                config[key] = None
    
    def get_or_create_instance(self, engine: str, instance_key: str, creator_func):
        """获取或创建实例（懒加载模式）"""
        config = self.get_engine_config(engine)
        instance = config.get(instance_key)
        
        if instance is None:
            instance = creator_func(config)
            config[instance_key] = instance
        
        return instance
```

**引擎切换时的行为**：
- 切换引擎（`/switch`）：保留所有引擎的实例缓存
- 切换模型（`/model`）：清空当前引擎的实例，强制重建
- 切换 agent 模式（`/mode`）：清空 agent_instance

**优势**：
- 实例缓存提高性能
- 切换引擎不丢失状态，可快速切回
- 切换关键配置时强制重建，保证一致性

### 10.5 Catalog 划分策略

**本轮重构（Phase 1-4）**：
- 只实现 `catalog/agent/basic/`
- 复用原有的 `catalog/langchain/catalog.py` 逻辑
- 不实现 `catalog/agent/deep/`（预留）
- 不实现 `catalog/llm/`（可选，可直接使用 provider_registry）

**具体实施**：

#### catalog/agent/basic/catalog.py
```python
class BasicAgentCatalogService(BaseCatalogService):
    """
    BasicAgent 的 catalog 服务，管理可用的 provider + model 组合。
    
    本轮复用原 LangChainCatalogService 的逻辑。
    """
    
    async def get_catalog(self) -> dict:
        # 从 agent_manager 获取可用的 agents
        from src.agents.basicagents.managers import agent_manager
        available_agents = agent_manager.get_available_agents()
        
        # 构建 catalog 数据结构（同原逻辑）
        ...
        
        return catalog
    
    def validate_model(self, provider: str, model: str | None) -> dict:
        # 验证模型是否可用（同原逻辑）
        ...
```

#### catalog/agent/deep/ (预留)
```
application/services/catalog/agent/deep/
├── __init__.py          # 空实现
└── README.md            # 说明未来的筛选标准
```

**README.md 内容**：
```markdown
# DeepAgent Catalog

## 筛选标准（计划）
DeepAgent 使用更强大的模型，筛选标准：
- context 窗口 >= 32K
- 支持复杂推理（如 o1 系列）
- 推理性能较强

## 计划支持的模型
- zhipu: glm-4-plus, glm-4-long
- openai: gpt-4o, gpt-4-turbo, o1-preview
- ollama: qwen2.5:14b, qwen2.5:32b

## 状态：预留
本 catalog 将在 DeepAgent 功能实现时一并完成。
```

#### catalog/llm/ (可选)
暂不实现，直接使用 `provider_registry` 提供的数据即可。

---

## 十一、注意事项

### 11.1 破坏性变更

此次重构包含以下破坏性变更：
- 所有 `src.agents.basicagents` 的导入路径失效
- 所有 `src.components.basicagents` 的导入路径失效
- 所有 `src.llm` 的导入路径失效
- 所有 `src.core` 的导入路径失效
- `/mode agent` 和 `/mode llm` 命令语义变更为 `/mode basic` 和 `/mode deep`
- 新增 `/switch` 系列命令用于引擎切换
- Adapter 类名变更
- Service 目录结构重组

### 11.2 向后兼容

**本次重构不考虑向后兼容**，理由：
- 项目处于快速迭代阶段
- 旧的 session 文件不需要迁移
- 代码库规模可控，可以一次性完成重构
- 清晰的架构比向后兼容更重要

### 11.3 分阶段实施

建议按照以下顺序进行：
1. **Phase 1**：先完成 src/ 核心层的重构（最底层）
2. **Phase 2**：再完成 application/ 应用层的重构（依赖核心层）
3. **Phase 3**：更新文档
4. **Phase 4**：全面测试
5. **Phase 5+**：实现 DeepAgents、Graph 组件等预留功能

每个 Phase 完成后进行充分测试，确保没有问题再进行下一阶段。

### 11.4 测试策略

- **tests/ 目录暂不处理**：旧的单元测试文件暂时保留，不进行更新
- 重构完成后，架构稳定后再重新编写测试
- 手动功能测试为主，确保四种引擎切换正常
- 重点测试：
  - LLM 引擎的纯对话功能
  - Agent 引擎的 basic 模式
  - `/mode deep` 的降级行为
  - 引擎切换和实例缓存

### 11.5 回滚方案

在开始重构前：
- 创建专门的分支 `feature/engine-architecture-refactor`
- 确保主分支代码可以正常运行
- 使用 git 进行版本控制，可随时回滚

---

## 十二、预期效果

重构完成后，项目架构将具有以下特点：

### 12.1 清晰的引擎边界

- LLM、Agent、AgentFlow、Dify 四种引擎职责明确
- 每种引擎有独立的 adapter、commands、services
- Agent 引擎内部通过 `/mode` 命令切换 basic 和 deep 模式
- 本轮实现 LLM 和 Agent(basic)，为 Agent(deep) 和 AgentFlow 预留扩展空间

### 12.2 统一的核心抽象

- `src/core/providers` 统一管理所有 LLM Provider
- 不再按技术栈分离核心接口
- catalog 基于 provider_registry 筛选，而不是重复管理
- 实例管理统一：懒加载 + 缓存策略

### 12.3 灵活的扩展性

- 未来可以轻松添加 DeepAgents（已预留目录和接口）
- AgentFlow 可以自由编排 BasicAgents 和 DeepAgents
- 可以添加新的引擎模式而不影响现有代码
- components/graph/ 组件可被 DeepAgents 和 AgentFlow 共同使用
- 预留功能不影响主线开发，可按需实现

### 12.4 更好的可维护性

- 目录结构反映实际的使用模式（引擎模式），而非底层技术栈
- 开发者更容易理解代码组织：4 个引擎，2 种 agent 模式
- 降低新人上手难度：清晰的引擎切换命令和目录结构
- 职责边界明确：LLM 纯对话、Agent 工具调用、AgentFlow 编排

### 12.5 用户体验提升

- 引擎切换更直观：`/switch llm`, `/switch agent`, `/switch agentflow`
- Agent 模式切换更明确：`/mode basic`, `/mode deep`（本轮 deep 降级到 basic）
- Session 和 memory 在所有引擎间共享，切换无缝
- 实例缓存提升性能，切换引擎快速恢复

---

## 十三、参考文档

- [LangChain 官方文档](https://python.langchain.com/docs/)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [AgentFlow 架构指南](../langgraph-architecture/agentflow_guide.md)（待更新）
- [原架构文档](../langchain-architecture/architecture.md)
- [快速参考手册](quick_reference.md)

---

## 十四、版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v3.0.0 | 2025-10-15 | 初始版本：引擎模式化架构重构方案 |

---

**文档结束**

