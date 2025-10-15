# 架构重构快速参考手册

> **版本**：v3.0.0
> 
> **创建时间**：2025-10-15
> 
> **用途**：快速查找重构前后的路径、导入、命令对照

---

## 重要说明：本轮实施范围

### 本轮实现（Phase 1-4）

**完全实现**：
- LLM 引擎（纯对话，无工具）
- Agent 引擎的 basic 模式（工具调用）
- 所有目录重命名和路径迁移
- 引擎切换命令 `/switch`
- 实例管理和缓存

**预留但不实现**：
- Agent 引擎的 deep 模式（`/mode deep` 降级到 basic）
- DeepAgents 目录（只创建空目录和 README）
- components/graph/ 组件（只创建接口定义）
- catalog/agent/deep/（只创建空目录和 README）
- AgentFlow 引擎（保持占位符）

详细说明请参考 [new_engine_architecture.md 第十章](new_engine_architecture.md#十本轮实施范围和细节说明)

---

## 一、目录路径对照表

### 1.1 src/ 核心层

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| `src/agents/langchain/` | `src/agents/basicagents/` | Agent 引擎 basic 模式实现 |
| - | `src/agents/deepagents/` | Agent 引擎 deep 模式实现（新增） |
| `src/components/langchain/` | `src/components/basicagents/` | BasicAgents 组件 |
| - | `src/components/deepagents/` | DeepAgents 组件（新增，预留） |
| - | `src/components/graph/` | Graph 组件（新增） |
| `src/llm/langchain/adapters/` | `src/llm/adapters/` | LLM 适配器（提升） |
| `src/llm/langchain/instances/` | `src/llm/instances/` | LLM 实例（提升） |
| `src/llm/langchain/managers/` | `src/llm/managers/` | LLM 管理器（提升） |
| `src/llm/langchain/utils/` | `src/llm/utils/` | LLM 工具（提升） |
| `src/core/langchain/providers/` | `src/core/providers/` | Provider 注册（提升） |

### 1.2 application/ 应用层

| 旧路径 | 新路径 | 说明 |
|--------|--------|------|
| `application/engine_adapters/langchain_adapter.py` | `application/engine_adapters/agent_adapter.py` | Agent 引擎适配器 |
| `application/engine_adapters/langgraph_adapter.py` | `application/engine_adapters/agentflow_adapter.py` | AgentFlow 引擎适配器 |
| - | `application/engine_adapters/llm_adapter.py` | LLM 引擎适配器（新增） |
| `application/commands/langchain/` | `application/commands/agent/` | Agent 引擎命令 |
| `application/commands/langgraph/` | `application/commands/agentflow/` | AgentFlow 引擎命令 |
| - | `application/commands/llm/` | LLM 引擎命令（新增，可选） |
| `application/services/langchain/` | `application/services/agent/basic/` | BasicAgent 服务 |
| - | `application/services/agent/deep/` | DeepAgent 服务（新增，预留） |
| `application/services/langgraph/` | `application/services/agentflow/` | AgentFlow 服务 |
| - | `application/services/llm/` | LLM 服务（新增） |
| `application/services/catalog/langchain/` | `application/services/catalog/agent/basic/` | BasicAgent 目录 |
| - | `application/services/catalog/agent/deep/` | DeepAgent 目录（新增，预留） |
| `application/services/catalog/langgraph/` | `application/services/catalog/agentflow/` | AgentFlow 目录 |
| - | `application/services/catalog/llm/` | LLM 目录（新增，可选） |

---

## 二、导入语句对照表

### 2.1 agents 模块导入

```python
# 旧导入
from src.agents.basicagents import agent_manager
from src.agents.basicagents import AgentManager
from src.agents.basicagents.instances import BaseAgent, ZhipuAgent, OpenAIAgent, OllamaAgent
from src.agents.basicagents.instances import ZhipuFCallAgent
from src.agents.basicagents.factories import agent_factory, BaseAgentFactory
from src.agents.basicagents.factories import ZhipuAgentFactory, OpenAIAgentFactory, OllamaAgentFactory
from src.agents.basicagents.factories import FactoryRegistry, get_global_registry
from src.agents.basicagents.managers import agent_manager, AgentManager

# 新导入
from src.agents.basicagents import agent_manager
from src.agents.basicagents import AgentManager
from src.agents.basicagents.instances import BaseAgent, ZhipuAgent, OpenAIAgent, OllamaAgent
from src.agents.basicagents.instances import ZhipuFCallAgent
from src.agents.basicagents.factories import agent_factory, BaseAgentFactory
from src.agents.basicagents.factories import ZhipuAgentFactory, OpenAIAgentFactory, OllamaAgentFactory
from src.agents.basicagents.factories import FactoryRegistry, get_global_registry
from src.agents.basicagents.managers import agent_manager, AgentManager
```

### 2.2 components 模块导入

```python
# 旧导入
from src.components.basicagents.parsers import JsonReactOutputParser
from src.components.basicagents.prompts import registry
from src.components.basicagents.prompts import tooling

# 新导入
from src.components.basicagents.parsers import JsonReactOutputParser
from src.components.basicagents.prompts import registry
from src.components.basicagents.prompts import tooling
```

### 2.3 llm 模块导入

```python
# 旧导入
from src.llm import ZhipuAILLM, OpenAILLM, OllamaLLM
from src.llm import LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter
from src.llm import LLMManager, LLMProvider, get_llm_info
from src.llm.instances import ZhipuAILLM, OpenAILLM, OllamaLLM
from src.llm.adapters import LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter
from src.llm.managers import LLMManager, LLMProvider, get_llm_info
from src.llm.managers import reload_llm_config
from src.llm.utils import StreamingLLM, stream_llm_response

# 新导入
from src.llm import ZhipuAILLM, OpenAILLM, OllamaLLM
from src.llm import LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter
from src.llm import LLMManager, LLMProvider, get_llm_info
from src.llm.instances import ZhipuAILLM, OpenAILLM, OllamaLLM
from src.llm.adapters import LLMAdapter, ZhipuAdapter, OpenAIAdapter, OllamaAdapter
from src.llm.managers import LLMManager, LLMProvider, get_llm_info
from src.llm.managers import reload_llm_config
from src.llm.utils import StreamingLLM, stream_llm_response
```

### 2.4 core 模块导入

```python
# 旧导入
from src.core import providers
from src.core.providers import provider_registry
from src.core.providers.utils import OllamaClient, list_ollama_models

# 新导入
from src.core import providers
from src.core.providers import provider_registry
from src.core.providers.utils import OllamaClient, list_ollama_models
```

### 2.5 application/engine_adapters 导入

```python
# 旧导入
from application.engine_adapters.langchain_adapter import LangChainAdapter
from application.engine_adapters.langgraph_adapter import LangGraphAdapter
from ..engine_adapters.langchain_adapter import LangChainAdapter
from ..engine_adapters.langgraph_adapter import LangGraphAdapter

# 新导入
from application.engine_adapters.agent_adapter import AgentAdapter
from application.engine_adapters.agentflow_adapter import AgentFlowAdapter
from application.engine_adapters.llm_adapter import LLMAdapter
from ..engine_adapters.agent_adapter import AgentAdapter
from ..engine_adapters.agentflow_adapter import AgentFlowAdapter
from ..engine_adapters.llm_adapter import LLMAdapter
```

### 2.6 application/services 导入

```python
# 旧导入
from application.services.langchain import LangChainService
from application.services.langgraph import LangGraphService
from ..services.langchain import LangChainService
from ..services.langgraph import LangGraphService
from ...services.langchain import LangChainService

# 新导入
from application.services.agent.basic import BasicAgentService
from application.services.agentflow import AgentFlowService
from application.services.llm import LLMService
from ..services.agent.basic import BasicAgentService
from ..services.agentflow import AgentFlowService
from ..services.llm import LLMService
from ...services.agent.basic import BasicAgentService
```

### 2.7 application/commands 导入

```python
# 旧导入
from application.commands.langchain import mode_commands, model_commands, tool_commands
from application.commands.langgraph import graph_commands, node_commands
from ..commands.langchain import mode_commands
from ...commands.langchain import ModeCommand

# 新导入
from application.commands.agent import mode_commands, model_commands, tool_commands
from application.commands.agentflow import graph_commands, node_commands
from ..commands.agent import mode_commands
from ...commands.agent import ModeCommand
```

### 2.8 catalog 导入

```python
# 旧导入
from application.services.catalog.langchain import LangChainCatalogService
from application.services.catalog.langgraph import LangGraphCatalogService

# 新导入
from application.services.catalog.agent.basic import BasicAgentCatalogService
from application.services.catalog.agentflow import AgentFlowCatalogService
from application.services.catalog.llm import LLMCatalogService
```

---

## 三、类名和变量重命名对照

### 3.1 Adapter 类

| 旧类名 | 新类名 | 文件 |
|--------|--------|------|
| `LangChainAdapter` | `AgentAdapter` | `application/engine_adapters/agent_adapter.py` |
| `LangGraphAdapter` | `AgentFlowAdapter` | `application/engine_adapters/agentflow_adapter.py` |

### 3.2 Service 类

| 旧类名 | 新类名 | 文件 |
|--------|--------|------|
| `LangChainService` | `BasicAgentService` | `application/services/agent/basic/service.py` |
| `LangGraphService` | `AgentFlowService` | `application/services/agentflow/service.py` |

### 3.3 Catalog 类

| 旧类名 | 新类名 | 文件 |
|--------|--------|------|
| `LangChainCatalogService` | `BasicAgentCatalogService` | `application/services/catalog/agent/basic/catalog.py` |
| `LangGraphCatalogService` | `AgentFlowCatalogService` | `application/services/catalog/agentflow/catalog.py` |

---

## 四、命令系统对照

### 4.1 引擎切换命令

| 旧命令 | 新命令 | 说明 |
|--------|--------|------|
| - | `/switch llm` | 切换到 LLM 引擎 |
| - | `/switch agent` | 切换到 Agent 引擎（默认 basic 模式） |
| - | `/switch agentflow` | 切换到 AgentFlow 引擎 |
| - | `/switch dify` | 切换到 Dify 引擎（保持不变） |

### 4.2 模式切换命令（仅在 Agent 引擎内）

| 旧命令 | 新命令 | 说明 |
|--------|--------|------|
| `/mode agent` | `/mode basic` | 切换到 basic 模式 |
| `/mode llm` | `/mode deep` | 切换到 deep 模式 |

### 4.3 命令作用域

| 命令文件 | 旧 engine_scope | 新 engine_scope |
|----------|----------------|----------------|
| `mode_commands.py` | `("langchain",)` | `("agent",)` |
| `model_commands.py` | `("langchain",)` | `("agent",)` |
| `tool_commands.py` | `("langchain",)` | `("agent",)` |
| `graph_commands.py` | `("langgraph",)` | `("agentflow",)` |

---

## 五、配置文件变更对照

### 5.1 AppState 引擎配置

#### src/application/cli/state.py

**旧配置**：
```python
DEFAULT_ENGINE_CONFIGS = {
    "langchain": {
        "provider": "zhipu",
        "model": "glm-4.5-flash",
        "mode": "agent",  # "agent" | "llm"
        "streaming": True,
        "agent": None,
    },
    "langgraph": {
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

**新配置**：
```python
DEFAULT_ENGINE_CONFIGS = {
    "llm": {
        "provider": "zhipu",
        "model": "glm-4-flash",
        "streaming": True,
    },
    "agent": {
        "agent_type": "basic",  # "basic" | "deep"
        "provider": "zhipu",
        "model": "glm-4-flash",
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

### 5.2 引擎名称变更

| 旧引擎名 | 新引擎名 | 说明 |
|---------|---------|------|
| `langchain` | `agent` | Agent 引擎（包含 basic 和 deep） |
| - | `llm` | LLM 引擎（新增） |
| `langgraph` | `agentflow` | AgentFlow 引擎 |
| `dify` | `dify` | 保持不变 |

---

## 六、文件名变更对照

### 6.1 Adapter 文件

| 旧文件名 | 新文件名 |
|---------|---------|
| `application/engine_adapters/langchain_adapter.py` | `application/engine_adapters/agent_adapter.py` |
| `application/engine_adapters/langgraph_adapter.py` | `application/engine_adapters/agentflow_adapter.py` |

### 6.2 文档文件

| 旧文件名 | 新文件名 |
|---------|---------|
| `docs/langgraph-architecture/langgraph_guide.md` | `docs/langgraph-architecture/agentflow_guide.md` |

---

## 七、常见导入模式替换

### 7.1 使用 sed 批量替换（Linux/Mac）

```bash
# agents 模块
find src -name "*.py" -exec sed -i 's/from src\.agents\.langchain/from src.agents.basicagents/g' {} \;
find src -name "*.py" -exec sed -i 's/import src\.agents\.langchain/import src.agents.basicagents/g' {} \;

# components 模块
find src -name "*.py" -exec sed -i 's/from src\.components\.langchain/from src.components.basicagents/g' {} \;

# llm 模块
find src -name "*.py" -exec sed -i 's/from src\.llm\.langchain\./from src.llm./g' {} \;
find src -name "*.py" -exec sed -i 's/from src\.llm\.langchain import/from src.llm import/g' {} \;

# core 模块
find src -name "*.py" -exec sed -i 's/from src\.core\.langchain\.providers/from src.core.providers/g' {} \;
find src -name "*.py" -exec sed -i 's/from src\.core\.langchain import providers/from src.core import providers/g' {} \;

# application services
find src -name "*.py" -exec sed -i 's/from application\.services\.langchain/from application.services.agent.basic/g' {} \;
find src -name "*.py" -exec sed -i 's/from \.\.services\.langchain/from ..services.agent.basic/g' {} \;
find src -name "*.py" -exec sed -i 's/from \.\.\.services\.langchain/from ...services.agent.basic/g' {} \;
```

### 7.2 使用 PowerShell 批量替换（Windows）

```powershell
# agents 模块
Get-ChildItem -Path "src" -Filter "*.py" -Recurse | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.agents\.langchain', 'from src.agents.basicagents' | Set-Content $_.FullName
}

# components 模块
Get-ChildItem -Path "src" -Filter "*.py" -Recurse | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.components\.langchain', 'from src.components.basicagents' | Set-Content $_.FullName
}

# llm 模块
Get-ChildItem -Path "src" -Filter "*.py" -Recurse | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.llm\.langchain\.', 'from src.llm.' | Set-Content $_.FullName
}

# core 模块
Get-ChildItem -Path "src" -Filter "*.py" -Recurse | ForEach-Object {
    (Get-Content $_.FullName) -replace 'from src\.core\.langchain\.providers', 'from src.core.providers' | Set-Content $_.FullName
}
```

---

## 八、验证检查清单

### 8.1 导入验证

执行以下命令验证导入是否正确：

```bash
# 验证 agents 模块
python -c "from src.agents.basicagents import agent_manager; print('OK')"

# 验证 components 模块
python -c "from src.components.basicagents.parsers import JsonReactOutputParser; print('OK')"

# 验证 llm 模块
python -c "from src.llm.managers import LLMManager; print('OK')"

# 验证 core 模块
python -c "from src.core.providers import provider_registry; print('OK')"

# 验证 adapters
python -c "from application.engine_adapters.agent_adapter import AgentAdapter; print('OK')"
```

### 8.2 目录验证

检查以下目录是否存在：

```bash
# src/ 核心层
ls -la src/agents/basicagents/
ls -la src/components/basicagents/
ls -la src/components/graph/
ls -la src/llm/adapters/
ls -la src/core/providers/

# application/ 应用层
ls -la application/engine_adapters/agent_adapter.py
ls -la application/engine_adapters/agentflow_adapter.py
ls -la application/engine_adapters/llm_adapter.py
ls -la application/services/agent/basic/
ls -la application/services/agentflow/
ls -la application/services/llm/
```

---

## 九、受影响文件快速索引

### 9.1 需要更新导入的文件（按模块分类）

#### agents 模块相关（7个文件）

```
src/application/services/langchain/service.py
src/application/services/catalog/langchain/catalog.py
src/application/services/langchain/agent_lifecycle.py
src/agents/langchain/factories/ollama_factory.py
src/agents/langchain/managers/agent_manager.py
src/agents/langchain/factories/openai_factory.py
src/agents/langchain/factories/zhipu_factory.py
```

#### components 模块相关（1个文件）

```
src/agents/langchain/adapters/zhipu_agent_adapter.py
```

#### llm 模块相关（9个文件）

```
src/application/services/langchain/service.py
src/application/services/langchain/streaming.py
src/agents/langchain/instances/base_agent.py
src/agents/langchain/instances/ollama_agent.py
src/agents/langchain/instances/openai_agent.py
src/agents/langchain/instances/zhipu_agent.py
src/agents/langchain/instances/zhipu_fcall_agent.py
src/agents/langchain/managers/agent_manager.py
src/llm/langchain/managers/llm_manager.py
```

#### core 模块相关（14个文件）

```
src/application/services/catalog/langchain/catalog.py
src/llm/langchain/adapters/base.py
src/llm/langchain/__init__.py
src/llm/langchain/utils/streaming.py
src/agents/langchain/factories/ollama_factory.py
src/llm/langchain/adapters/ollama_adapter.py
src/llm/langchain/adapters/openai_adapter.py
src/llm/langchain/adapters/zhipu_adapter.py
src/agents/langchain/managers/agent_manager.py
src/agents/langchain/adapters/ollama_agent_adapter.py
src/agents/langchain/adapters/openai_agent_adapter.py
src/agents/langchain/adapters/zhipu_agent_adapter.py
src/agents/langchain/adapters/base.py
src/llm/langchain/managers/llm_manager.py
```

---

## 十、注意事项

### 10.1 路径替换优先级

执行替换时应该按照以下优先级，避免出现错误：

1. **第一步**：重命名目录结构
2. **第二步**：更新导入路径（从最具体到最通用）
   - 先替换 `src.llm.managers` → `src.llm.managers`
   - 再替换 `src.llm` → `src.llm`
3. **第三步**：更新类名和变量名
4. **第四步**：更新配置文件

### 10.2 常见错误

1. **顺序错误**：如果先替换 `src.llm` → `src.llm`，会把 `src.llm.managers` 错误替换为 `src.llm.managers.managers`
2. **相对导入**：注意相对导入（`..` 和 `...`）的层级关系变化
3. **循环导入**：重命名后可能出现新的循环导入，需要调整导入顺序

### 10.3 建议工具

- **IDE 重构功能**：使用 PyCharm 或 VSCode 的"重命名"功能可以自动更新引用
- **git grep**：使用 `git grep` 而不是普通 `grep`，避免搜索到 `.pyc` 文件
- **分批提交**：每完成一个模块的重构就提交一次，方便回滚

---

## 十一、预留功能说明

### 11.1 DeepAgent 相关（本轮不实现）

**预留目录**：
```
src/agents/deepagents/              # 只有 __init__.py 和 README.md
application/services/agent/deep/    # 只有 __init__.py 和 README.md
application/services/catalog/agent/deep/  # 只有 __init__.py 和 README.md
```

**临时行为**：
- `/mode deep` 执行时降级到 basic 模式
- 显示提示："Deep mode is under development, using basic mode"
- `agent_type` 字段正常更新（为未来做准备）

**未来实现**：Phase 5+

### 11.2 Graph 组件相关（本轮不实现）

**预留目录**：
```
src/components/graph/
├── __init__.py
├── README.md
├── core_nodes/
│   ├── __init__.py
│   └── README.md
├── graph_builder.py (空)
└── state_manager.py (空)
```

**说明**：
- 只创建接口定义，不实现具体功能
- README.md 说明设计目标和计划实现的节点类型

**未来实现**：Phase 5+，基于 LangGraph 官方库

### 11.3 AgentFlow 引擎（本轮不实现）

**现状**：
- `application/services/agentflow/` 保持占位符
- 只有基本的服务框架，没有实际功能

**未来实现**：Phase 5+，依赖 components/graph/ 的实现

### 11.4 LLM Catalog（本轮可选）

**说明**：
- `application/services/catalog/llm/` 可以不实现
- 直接使用 `provider_registry` 提供的数据即可
- 如需实现，可以简单封装 provider_registry

---

**文档结束**

