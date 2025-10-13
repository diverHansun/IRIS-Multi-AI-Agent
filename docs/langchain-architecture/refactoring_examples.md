# 重构后的新架构使用示例

本文档展示重构后的GoF设计模式实现和使用方法。

## 架构概览

### 1. 适配器模式 (Adapter Pattern) - LLM参数适配

**位置**: `src/llm/langchain/adapters/`

**用途**: 统一处理不同LLM提供商的配置和特殊逻辑

```python
from src.llm.langchain.adapters import ZhipuAdapter, OpenAIAdapter, OllamaAdapter

# 1. Zhipu Adapter - 处理thinking_mode
adapter = ZhipuAdapter(model="glm-4.5", mode="agent")
params = adapter.get_llm_params(temperature=0.1)
# 返回: {
#   "temperature": 0.1,
#   "thinking_mode": True,  # 自动从config读取
#   "max_iterations": 15,   # 从mode_overrides应用
#   ...
# }

# 2. OpenAI Adapter - 处理temperature_fixed
adapter = OpenAIAdapter(model="gpt-5", mode="llm")
params = adapter.get_llm_params(temperature=0.5)
# 返回: {
#   "temperature": 1.0,  # 强制使用1.0，忽略用户的0.5
#   ...
# }
# 控制台警告: "gpt-5 使用固定temperature=1.0 (用户设置的0.5被忽略)"

# 3. Ollama Adapter - Agent模式优化
adapter = OllamaAdapter(model="qwen:7b", mode="agent")
params = adapter.get_llm_params(temperature=0.1)
# 返回: {
#   "temperature": 0.0,  # 自动优化为0.0
#   "disable_thinking_mode": True,
#   ...
# }
```

### 2. 抽象工厂模式 (Abstract Factory Pattern) - Agent创建

**位置**: `src/agents/langchain/factories/`

**用途**: 消除if-else链，通过注册表动态选择工厂

```python
from src.agents.langchain.factories import (
    get_global_registry,
    ZhipuAgentFactory,
    OpenAIAgentFactory,
)

# 1. 使用全局注册表
registry = get_global_registry()

# 自动注册了三个工厂: ZHIPU, OPENAI, OLLAMA
print(registry.get_all_providers())
# ['ZHIPU', 'OPENAI', 'OLLAMA']

# 2. 获取工厂并创建Agent
factory = registry.get_factory("ZHIPU")
agent = await factory.create_agent(
    model="glm-4.5-flash",  # 自动选择Function Calling Agent
    temperature=0.1,
    enable_memory=True
)

# 3. 直接使用具体工厂
zhipu_factory = ZhipuAgentFactory()

# glm-4.5 → Function Calling Agent
agent1 = await zhipu_factory.create_agent(model="glm-4.5")

# glm-4-plus → ReAct Agent
agent2 = await zhipu_factory.create_agent(model="glm-4-plus")
```

### 3. 建造者模式 (Builder Pattern) - 流式API

**位置**: `src/agents/langchain/builders/`

**用途**: 提供流式API，简化Agent构建

#### 基础用法

```python
from src.agents.langchain.builders import AgentBuilder

# 流式API构建Agent
builder = AgentBuilder()

agent = await (builder
    .with_provider("zhipu")
    .with_model("glm-4.5")
    .with_temperature(0.1)
    .with_memory(enabled=True)
    .with_verbose(True)
    .build())
```

#### 使用预设配置

```python
from src.agents.langchain.builders import AgentPresets

# 1. ReAct Agent预设
agent = await (AgentPresets
    .for_react(provider="zhipu", model="glm-4-plus")
    .with_verbose(True)
    .build())

# 2. Function Calling Agent预设
agent = await (AgentPresets
    .for_function_calling(model="glm-4.5-flash")
    .build())

# 3. 代码生成Agent预设
agent = await (AgentPresets
    .for_coding(model="glm-4.5")
    .with_temperature(0.05)  # 覆盖默认值
    .build())

# 4. 聊天Agent预设（高创造性）
agent = await (AgentPresets
    .for_chat(temperature=0.8)
    .build())

# 5. Ollama本地模型预设
agent = await (AgentPresets
    .for_ollama_local(model="auto", base_url="http://localhost:11434")
    .build())

# 6. GPT-5预设（temperature自动为1.0）
agent = await (AgentPresets
    .for_gpt5(model="gpt-5", api_key="sk-...")
    .build())

# 7. LangGraph工作流预设（未来）
agent = await (AgentPresets
    .for_langgraph()
    .with_model("glm-4.5")
    .build())
```

## 向后兼容性

所有现有API保持不变，可以继续使用：

```python
# 旧的API仍然工作
from src.agents.langchain import (
    agent_factory,
    create_agent,
    create_zhipu_agent,
    create_openai_agent,
)

# 方式1: 使用全局工厂实例
agent = await agent_factory.create_agent(
    provider="zhipu",
    model="glm-4.5",
    temperature=0.1
)

# 方式2: 便捷函数
agent = await create_agent(provider="zhipu", model="glm-4.5")
agent = await create_zhipu_agent(model="glm-4-plus")
agent = await create_openai_agent(model="gpt-4o-mini")

# 内部实现已改为使用Registry，但API完全兼容
```

## 新旧对比

### 旧方式（agent_factory.py中的if-else）

```python
# agent_factory.py (旧逻辑，已重构)
if provider == LLMProvider.ZHIPU:
    if model in ["glm-4.5", "glm-4.5-flash"]:
        from .zhipu_fcall_agent import build_zhipu_fcall_agent
        agent = await build_zhipu_fcall_agent(...)
    else:
        agent = await build_zhipu_agent(...)
elif provider == LLMProvider.OPENAI:
    if model.startswith("gpt-5"):
        actual_temperature = 1.0  # 硬编码
    agent = await build_openai_agent(...)
elif provider == LLMProvider.OLLAMA:
    # 更多特殊逻辑...
```

### 新方式（Registry + Factory）

```python
# 1. 获取工厂
factory = registry.get_factory(provider)

# 2. 工厂内部处理所有逻辑
agent = await factory.create_agent(...)

# 优点：
# - 消除if-else链
# - 每个Provider的逻辑在独立工厂中
# - 易于扩展新Provider
# - 易于测试
```

## 配置驱动

所有特殊逻辑都从 `config/llms/providers.json` 读取：

```json
{
  "providers": {
    "ZHIPU": {
      "models": {
        "glm-4.5": {
          "mode_overrides": {
            "llm": {
              "thinking_mode": true
            }
          }
        }
      }
    },
    "OPENAI": {
      "models": {
        "gpt-5": {
          "temperature_fixed": true,
          "default_temperature": 1.0
        }
      }
    }
  }
}
```

Adapter会自动读取这些配置并应用。

## 测试建议

```python
# 1. 测试Adapter
from src.llm.langchain.adapters import ZhipuAdapter

adapter = ZhipuAdapter(model="glm-4.5", mode="agent")
params = adapter.get_llm_params()
assert params.get("thinking_mode") == True

# 2. 测试Factory
from src.agents.langchain.factories import ZhipuAgentFactory

factory = ZhipuAgentFactory()
assert factory.is_function_calling_model("glm-4.5") == True
assert factory.is_function_calling_model("glm-4-plus") == False

# 3. 测试Builder
from src.agents.langchain.builders import AgentBuilder

builder = AgentBuilder()
builder.with_provider("zhipu").with_model("glm-4.5")
agent = await builder.build()
assert agent is not None

# 4. 测试向后兼容
from src.agents.langchain import create_zhipu_agent

agent = await create_zhipu_agent(model="glm-4.5")
assert agent is not None
```

## 总结

### 实现的GoF模式

1. **模板方法模式** (Template Method) - `BaseAgent`
2. **策略模式** (Strategy) - `ToolProvider`
3. **组合模式** (Composite) - `UnifiedToolManager`
4. **适配器模式** (Adapter) - `LLMAdapter`, `ZhipuAdapter`, etc.
5. **抽象工厂模式** (Abstract Factory) - `FactoryRegistry`, `ZhipuAgentFactory`, etc.
6. **建造者模式** (Builder) - `AgentBuilder`, `AgentPresets`

### 优势

- 消除硬编码if-else链
- 配置驱动，易于维护
- 模块化，易于扩展
- 保持向后兼容
- 为LangGraph集成做准备
