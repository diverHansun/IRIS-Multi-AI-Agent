# LLM+Agent架构重构文档 v3.0

## 概览

本次重构的核心目标是实现**模块内聚**和**职责分离**，将LLM和Agent的管理、适配逻辑分别放在各自的模块内，消除硬编码，实现完全的配置驱动。

## 架构原则

1. **模块内聚**: 每个模块(llm/agent)有自己的managers和adapters
2. **职责分离**: LLM Adapter只处理LLM参数，Agent Adapter只处理Agent参数
3. **配置驱动**: 所有参数从`config/llms/providers.json`读取，优先级: mode_defaults → mode_overrides → user_params
4. **消除硬编码**: Agent不再硬编码默认值，全部从配置或Adapter获取

## 新增文件结构

```
src/
├── llm/langchain/
│   ├── managers/
│   │   ├── llm_manager.py              # 简化为API入口
│   │   └── provider_registry.py        # [新增] Provider注册表
│   │
│   ├── providers/
│   │   ├── base.py                     # [新增] Provider基类
│   │   ├── zhipu/provider.py           # [待实现]
│   │   ├── openai/provider.py          # [待实现]
│   │   └── ollama/provider.py          # [待实现]
│   │
│   └── adapters/                       # [重构] 只处理LLM参数
│       ├── base.py                     # 重构: 只保留LLM参数逻辑
│       ├── zhipu_adapter.py            # 重构: 移除Agent参数
│       └── ...
│
└── agents/langchain/
    ├── managers/                        # [新增] Agent管理器
    │   ├── __init__.py
    │   └── agent_manager.py            # [新增] Agent创建协调器
    │
    ├── adapters/                        # [新增] Agent参数适配器
    │   ├── __init__.py
    │   ├── base.py                      # [新增] AgentAdapter基类
    │   ├── zhipu_agent_adapter.py       # [新增]
    │   ├── openai_agent_adapter.py      # [新增]
    │   └── ollama_agent_adapter.py      # [新增]
    │
    └── instances/                       # [待重构] Agent实例
        ├── base_agent.py                # 移除硬编码，使用Adapter
        ├── zhipu_agent.py               # 适配新架构
        └── ...
```

## 核心组件说明

### 1. Agent Manager (新增)
- **位置**: `agents/langchain/managers/agent_manager.py`
- **职责**: Agent创建的统一入口，协调LLM和Agent的创建
- **API**:
  ```python
  agent_manager.create_agent(
      provider="zhipu",
      model="glm-4.5",
      verbose=True  # 用户参数
  )
  ```

### 2. Agent Adapter (新增)
- **位置**: `agents/langchain/adapters/`
- **职责**: 只处理Agent参数
- **处理的参数**:
  - `max_iterations`: 最大迭代次数
  - `max_execution_time`: 最大执行时间
  - `memory_enabled`: 是否启用记忆
  - `verbose`: 是否详细输出
  - `temperature`: Agent温度参数(与LLM温度可以不同)

### 3. LLM Adapter (重构)
- **位置**: `llm/langchain/adapters/`
- **职责**: 只处理LLM参数
- **处理的参数**:
  - `temperature`: LLM温度参数
  - `streaming`: 是否流式输出
  - `max_tokens`: 最大输出token数
  - `thinking_mode`: 思考模式(智谱AI特有)

### 4. Provider Registry (新增)
- **位置**: `llm/langchain/managers/provider_registry.py`
- **职责**: Provider配置管理
- **功能**:
  - 从`providers.json`加载配置
  - 提供配置查询接口
  - 支持动态重载

## 参数流转示例

### providers.json配置
```json
{
  "ZHIPU": {
    "mode_defaults": {
      "llm": {
        "temperature": 0.1,
        "streaming": true
      },
      "agent": {
        "temperature": 0.1,
        "max_iterations": 8,
        "max_execution_time": 300
      }
    },
    "models": {
      "glm-4.5": {
        "mode_overrides": {
          "llm": {
            "thinking_mode": true,
            "temperature": 0.5
          },
          "agent": {
            "max_iterations": 15,
            "max_execution_time": 180
          }
        }
      }
    }
  }
}
```

### 参数应用流程
```python
# 用户代码
agent = agent_manager.create_agent(
    provider="zhipu",
    model="glm-4.5",
    verbose=True
)

# ===== 内部流转 =====

# 1. LLM Adapter获取LLM参数
llm_params = llm_adapter.get_llm_params()
# 结果: {
#   "temperature": 0.5,        # mode_overrides.llm
#   "streaming": true,         # mode_defaults.llm
#   "thinking_mode": true      # mode_overrides.llm
# }

# 2. Agent Adapter获取Agent参数
agent_params = agent_adapter.get_agent_params(verbose=True)
# 结果: {
#   "temperature": 0.1,          # mode_defaults.agent
#   "max_iterations": 15,        # mode_overrides.agent ✅ 使用配置的15
#   "max_execution_time": 180,   # mode_overrides.agent ✅
#   "verbose": True              # user_params (优先级最高)
# }

# 3. BaseAgent应用参数（不再硬编码）
self.max_iterations = 15          # ✅ 从配置获取
self.max_execution_time = 180     # ✅ 从配置获取
self.verbose = True               # ✅ 用户参数优先

# 4. AgentExecutor创建
AgentExecutor(
    agent=agent,
    tools=tools,
    max_iterations=15,            # ✅ 正确应用配置
    max_execution_time=180,       # ✅ 正确应用配置
    verbose=True
)
```

## 解决的问题

### 问题1: Adapter混杂LLM和Agent参数
**旧架构**: LLM Adapter同时处理`temperature`和`max_iterations`
**新架构**:
- LLM Adapter只处理`temperature`, `streaming`, `max_tokens`
- Agent Adapter只处理`max_iterations`, `max_execution_time`

### 问题2: 配置未应用
**旧架构**: BaseAgent硬编码`max_iterations=8`，忽略配置的`15`
**新架构**: BaseAgent通过AgentAdapter获取配置，优先使用配置值

### 问题3: Agent和llm_manager职责混乱
**旧架构**: Agent的manager放在llm模块下
**新架构**: Agent模块有自己的managers和adapters

## ✅ 完成工作清单

1. ✅ 创建Agent Manager
2. ✅ 创建Agent Adapter基类和实现
3. ✅ 创建Provider基类和Registry
4. ✅ 重构LLM Adapter(只保留LLM参数)
5. ✅ 重构BaseAgent(移除硬编码)
6. ✅ 重构各Provider的Agent实例
7. ✅ **简化LLMManager (503行→329行, -34%)**
8. ✅ **创建Provider实现**
   - `zhipu/provider.py` - ZhipuProvider
   - `openai/provider.py` - OpenAIProvider
   - `ollama/provider.py` - OllamaProvider
9. ✅ **增强ProviderRegistry** (新增 `get_provider_instance()` 工厂方法)
10. ✅ **测试配置参数应用 (6/6测试通过)**
    - ✅ 获取可用Provider列表
    - ✅ 获取模型信息
    - ✅ 验证模型
    - ✅ ProviderRegistry正确工作
    - ✅ Provider实现正确
    - ✅ 向后兼容性
11. ✅ 更新文档

## 使用示例

### 创建Agent (新方式)
```python
from src.agents.langchain.managers import agent_manager

# 使用配置的默认参数
agent = agent_manager.create_agent(
    provider="zhipu",
    model="glm-4.5"
)
# max_iterations = 15 (从配置读取)

# 覆盖配置参数
agent = agent_manager.create_agent(
    provider="zhipu",
    model="glm-4.5",
    max_iterations=20,  # 用户参数优先
    verbose=True
)
# max_iterations = 20 (用户参数)
```

### 创建LLM (兼容旧方式)
```python
from src.llm.langchain.managers import create_llm

llm = create_llm(
    provider="zhipu",
    model="glm-4.5"
)
# temperature = 0.5 (从mode_overrides.llm读取)
```

## 架构优势

| 方面 | 优势 |
|-----|-----|
| **模块内聚** | 每个模块有自己的managers和adapters |
| **职责清晰** | LLM/Agent参数完全分离 |
| **配置驱动** | 无硬编码，全部从配置获取 |
| **易于扩展** | 新增Provider只需实现2个Adapter |
| **向后兼容** | 保留llm_manager,现有代码无需修改 |
| **可测试性** | 每个组件独立，易于单元测试 |

## 迁移指南

### 现有代码无需修改
```python
# 这些代码继续工作
from src.llm.langchain.managers import create_llm
llm = create_llm("zhipu", "glm-4.5")
```

### 推荐使用新方式创建Agent
```python
# 旧方式 (仍然支持)
from src.agents.langchain.instances import ZhipuAgent
agent = ZhipuAgent(model="glm-4.5", max_iterations=8)  # 硬编码

# 新方式 (推荐)
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5")  # 从配置读取
```

## 总结

本次重构实现了真正的**模块内聚**和**配置驱动**，解决了Adapter职责混杂和Agent硬编码的问题。配置文件中的`agent.max_iterations=15`将正确应用到Agent实例，不再被硬编码的`8`覆盖。

### 重构成果

#### 代码优化
- **LLM Manager**: 503行 → 329行 (**-34%**)
- **删除冗余**: 移除 `FALLBACK_LLMS` 硬编码配置 (91行)
- **删除重复**: 移除 `_convert_json_config`, `_merge_mode_defaults`, `_get_provider_models` (75行)
- **职责委托**: 配置管理→ProviderRegistry, LLM创建→Provider实现

#### 新增文件
```
src/llm/langchain/providers/
├── zhipu/provider.py       # ZhipuProvider (96行)
├── openai/provider.py      # OpenAIProvider (109行)
└── ollama/provider.py      # OllamaProvider (123行)
```

#### Provider Registry增强
- 新增 `get_provider_instance()` 工厂方法
- 支持动态创建Provider实例
- 统一Provider接口

#### 测试结果
```
✅ 测试1: 获取可用Provider列表 - 通过
✅ 测试2: 获取模型信息 - 通过 (验证max_iterations=15)
✅ 测试3: 验证模型 - 通过
✅ 测试4: ProviderRegistry正确工作 - 通过
✅ 测试5: Provider实现正确 - 通过
✅ 测试6: 向后兼容性 - 通过

测试覆盖率: 6/6 (100%)
```

#### 架构改进
| 改进点 | 前 | 后 |
|--------|-----|-----|
| LLM Manager行数 | 503行 | 329行 (-34%) |
| 配置加载 | 自己实现 | 委托ProviderRegistry |
| LLM创建 | 硬编码if/else | 委托Provider实现 |
| API密钥验证 | 无统一接口 | Provider.validate_api_key() |
| 扩展新Provider | 修改多处代码 | 实现1个Provider类 |
| 向后兼容 | N/A | 100%兼容旧API |

### 最佳实践

#### 创建LLM (推荐方式)
```python
from src.llm.langchain.managers import create_llm

# 自动使用配置的参数
llm = create_llm("zhipu", "glm-4.5")
# thinking_mode=True (从config读取)
```

#### 创建Agent (推荐方式)
```python
from src.agents.langchain.managers import agent_manager

# 自动使用配置的参数
agent = agent_manager.create_agent("zhipu", "glm-4.5")
# max_iterations=15 (从config读取)
```

#### 扩展新Provider
```python
# 1. 创建Provider实现
class MyProvider(BaseProvider):
    def create_llm(self, model, api_key, **kwargs):
        # 实现LLM创建逻辑
        pass

    def validate_api_key(self, api_key):
        # 实现API密钥验证
        pass

# 2. 在providers.json中添加配置
# 3. 在ProviderRegistry中注册
# 完成！无需修改llm_manager.py
```

---

**版本**: v3.0
**日期**: 2025-10-11
**状态**: ✅ 完成并测试通过
