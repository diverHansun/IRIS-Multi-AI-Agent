# Multi-AI-Agent 架构设计文档

> **版本**: v3.0.0
> **作者**: diverHansun
> **最后更新**: 2025-10-10
> **目标**: 基于 GoF 设计模式的架构优化，为 LangGraph 集成做准备

---

## 📑 目录

1. [架构概览](#架构概览)
2. [当前架构分析](#当前架构分析)
3. [设计模式应用](#设计模式应用)
4. [优化建议](#优化建议)
5. [LangGraph 集成准备](#langgraph-集成准备)
6. [实施路线图](#实施路线图)

---

## 🏗️ 架构概览

### 系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
│                  (CLI, GUI, FastAPI)                         │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                      Agent Layer                             │
│   ZhipuAgent │ OpenAIAgent │ OllamaAgent │ FunctionCalling  │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Component Layer                           │
│  ┌──────────┬──────────┬──────────┬──────────────────────┐  │
│  │   LLM    │  Memory  │  Tools   │  Prompts & Parsers   │  │
│  └──────────┴──────────┴──────────┴──────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Infrastructure Layer                        │
│        Config │ Storage │ Logging │ Error Handling          │
└─────────────────────────────────────────────────────────────┘
```

### 核心模块职责

| 模块 | 路径 | 职责 | 设计模式 |
|------|------|------|----------|
| **Agent Factory** | `src/agents/langchain/agent_factory.py` | Agent 创建与管理 | 工厂模式 |
| **LLM Manager** | `src/llm/langchain/llm_manager.py` | LLM 实例管理 | 单例 + 工厂 |
| **Memory Manager** | `src/components/shared/memory/global_memory.py` | 会话记忆管理 | 单例 + 策略 |
| **Tool Managers** | `src/components/shared/tools/` | 工具加载与适配 | 策略 + 适配器 |
| **Config Loader** | `src/config/` | 配置加载与验证 | 单例 |
| **Prompt Registry** | `src/components/langchain/prompts/registry.py` | 提示词模板管理 | 注册表模式 |

---

## 🔍 当前架构分析

### ✅ 优点

#### 1. **模块化设计良好**
- 清晰的分层架构：Agent → Components → Infrastructure
- 职责分离明确：LLM、Memory、Tools 各司其职
- 符合单一职责原则（SRP）

#### 2. **扩展性设计**
- 支持多 LLM 提供商（Zhipu、OpenAI、Ollama）
- 工具系统插件化（SDK、MCP、Connector）
- 配置驱动设计（JSON + 环境变量）

#### 3. **统一抽象接口**
- `BaseTool`：所有工具遵循 LangChain 标准
- `BaseChatMessageHistory`：统一记忆接口
- `RunnableWithMessageHistory`：标准化带记忆的执行流程

#### 4. **完善的错误处理**
- 配置加载失败自动降级到备用配置
- API 调用失败时的智能重试机制
- 详细的日志记录和异常追踪

### ⚠️ 存在的问题

#### 1. **工厂模式实现不够优雅**

**问题代码**（`agent_factory.py:94-176`）：
```python
if provider == LLMProvider.ZHIPU:
    if model in ["glm-4.5", "glm-4.5-flash"]:
        agent = await build_zhipu_fcall_agent(...)
    else:
        agent = await build_zhipu_agent(...)
elif provider == LLMProvider.OPENAI:
    if model.startswith("gpt-5"):
        actual_temperature = 1.0
    agent = await build_openai_agent(...)
elif provider == LLMProvider.OLLAMA:
    # 特殊处理逻辑...
    agent = await build_ollama_agent(...)
```

**问题分析**：
- ❌ 硬编码的 if-else 链，违反开闭原则（OCP）
- ❌ 新增 provider 需要修改核心代码
- ❌ 特殊逻辑（temperature_fixed、thinking_mode）分散各处

**改进方向**：抽象工厂模式 + 策略注册表

---

#### 2. **工具管理职责重叠**

**问题代码**（`zhipu_agent.py:165-192`）：
```python
def _collect_tools(self):
    # SDK 工具
    sdk_tools = SDKToolManager.get_all_tools()
    self.tools.extend(sdk_tools)

    # Connector 工具
    connector_manager = ConnectorToolManager()
    connector_tools = connector_manager.get_all_tools()
    self.tools.extend(connector_tools)

async def _load_mcp_tools(self):
    await GlobalMCPManager.initialize()
    mcp_tools = GlobalMCPManager.get_tools()
    self.tools.extend(mcp_tools)
```

**问题分析**：
- ❌ 三个管理器职责重叠（都是获取工具列表）
- ❌ Agent 需要了解所有工具源的细节
- ❌ 难以统一管理工具生命周期（初始化、重载、清理）

**改进方向**：策略模式 + 组合模式

---

#### 3. **Agent 初始化流程复杂**

**问题代码**（`zhipu_agent.py:73-102`）：
```python
async def initialize(self):
    # 1. 创建LLM
    await self._create_llm()

    # 2. 收集工具
    self._collect_tools()

    # 3. 加载MCP工具
    await self._load_mcp_tools()

    # 4. 构建Agent
    self._build_agent()

    # 5. 创建带记忆的Agent
    if self.enable_memory and self.chat_memory:
        self._build_agent_with_memory()
```

**问题分析**：
- ❌ 步骤顺序固定，难以调整
- ❌ 缺乏验证和回滚机制
- ❌ 无法支持部分初始化或延迟初始化

**改进方向**：建造者模式

---

#### 4. **配置热重载机制不完善**

**问题代码**（`llm_manager.py:213-223`）：
```python
def reload_config(self):
    logger.info("🔄 重新加载LLM配置...")
    config_data = config_loader.reload_config()
    self.SUPPORTED_LLMS = self._convert_json_config(config_data)
    logger.info("✅ LLM配置重新加载完成")
```

**问题分析**：
- ❌ 仅重载配置，不通知使用方
- ❌ 已创建的 Agent 仍使用旧配置
- ❌ 缺乏配置变更的事件机制

**改进方向**：观察者模式

---

#### 5. **LLM 接口不统一**

**问题代码**（分散在各 Agent 中）：
```python
# GLM-4.5 特殊处理
if self.model == "glm-4.5":
    executor_config.update({
        "max_iterations": max(self.max_iterations, 15),
        "max_execution_time": 180,
    })

# GPT-5 温度固定
if model.startswith("gpt-5"):
    actual_temperature = 1.0

# Ollama 思考模式
disable_thinking_mode = kwargs.get('disable_thinking_mode', True)
```

**问题分析**：
- ❌ 各 provider 特殊逻辑分散
- ❌ 上层代码需要了解 provider 差异
- ❌ 难以维护和扩展

**改进方向**：适配器模式

---

#### 6. **消息处理流程单一**

**问题代码**（`message_filter.py`）：
```python
class MessageFilter:
    def should_save_message(self, user_msg: str, ai_msg: str) -> bool:
        # 仅实现命令过滤
        return not user_msg.startswith('/')
```

**问题分析**：
- ❌ 功能单一，仅支持命令过滤
- ❌ 难以扩展新的过滤规则（敏感词、长度限制等）
- ❌ 无法支持消息转换、增强等需求

**改进方向**：责任链模式

---

#### 7. **Agent 代码重复**

**问题分析**（对比 `zhipu_agent.py`、`openai_agent.py`、`ollama_agent.py`）：

| 重复代码 | 行数 | 说明 |
|---------|------|------|
| `initialize()` 流程 | ~30 行 | 初始化步骤几乎相同 |
| `_execute_query()` 逻辑 | ~50 行 | 执行逻辑 90% 重复 |
| 记忆管理方法 | ~100 行 | 完全相同的方法定义 |

**改进方向**：模板方法模式

---

#### 8. **全局管理器线程安全性不足**

**问题代码**（`global_memory.py`、`mcp/manager.py`）：
```python
class GlobalMemoryManager:
    def __init__(self, storage_dir: str = "data/sessions"):
        # 直接初始化，无线程安全保障
        self._session_histories: Dict[str, GlobalChatMessageHistory] = {}
```

**问题分析**：
- ❌ 多线程环境下可能创建多个实例
- ❌ 缺乏资源池管理和生命周期控制
- ❌ 无法优雅关闭和清理资源

**改进方向**：单例模式强化（双重检查锁定）

---

## 🎨 设计模式应用

### 1. 创建型模式

#### 1.1 抽象工厂模式 - Agent & LLM 创建

**目标**：消除硬编码的 if-else，支持插件式扩展

**设计方案**：

```python
# src/agents/langchain/factories/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class AgentFactory(ABC):
    """Agent 工厂抽象接口"""

    @abstractmethod
    async def create_agent(self, model: str, **kwargs) -> BaseAgent:
        """创建 Agent 实例"""
        pass

    @abstractmethod
    def supports_model(self, model: str) -> bool:
        """检查是否支持指定模型"""
        pass

    @abstractmethod
    def get_default_config(self, model: str) -> Dict[str, Any]:
        """获取模型默认配置"""
        pass


# src/agents/langchain/factories/zhipu_factory.py
class ZhipuAgentFactory(AgentFactory):
    """智谱 AI Agent 工厂"""

    FUNCTION_CALLING_MODELS = ["glm-4.5", "glm-4.5-flash"]
    REACT_MODELS = ["glm-4-plus", "glm-4"]

    async def create_agent(self, model: str, **kwargs):
        if model in self.FUNCTION_CALLING_MODELS:
            return await self._create_fcall_agent(model, **kwargs)
        elif model in self.REACT_MODELS:
            return await self._create_react_agent(model, **kwargs)
        else:
            raise ValueError(f"Unsupported model: {model}")

    def supports_model(self, model: str) -> bool:
        return model in (self.FUNCTION_CALLING_MODELS + self.REACT_MODELS)

    def get_default_config(self, model: str) -> Dict[str, Any]:
        # 从配置文件加载，而非硬编码
        return config_loader.get_model_config("zhipu", model)


# src/agents/langchain/factories/registry.py
class AgentFactoryRegistry:
    """Agent 工厂注册表"""

    _factories: Dict[str, AgentFactory] = {}

    @classmethod
    def register(cls, provider: str, factory: AgentFactory):
        """注册工厂"""
        cls._factories[provider] = factory

    @classmethod
    def create_agent(cls, provider: str, model: str, **kwargs):
        """通过注册表创建 Agent"""
        factory = cls._factories.get(provider)
        if not factory:
            raise ValueError(f"No factory registered for: {provider}")

        if not factory.supports_model(model):
            raise ValueError(f"Model {model} not supported by {provider}")

        return factory.create_agent(model, **kwargs)


# 启动时注册所有工厂
AgentFactoryRegistry.register("zhipu", ZhipuAgentFactory())
AgentFactoryRegistry.register("openai", OpenAIAgentFactory())
AgentFactoryRegistry.register("ollama", OllamaAgentFactory())
```

**优势**：
- ✅ 符合开闭原则：新增 provider 无需修改现有代码
- ✅ 单一职责：每个工厂只负责一个 provider
- ✅ 易于测试：可以独立测试每个工厂
- ✅ 支持插件化：通过配置文件动态加载工厂

---

#### 1.2 建造者模式 - Agent 构建流程

**目标**：简化 Agent 初始化，支持灵活配置

**设计方案**：

```python
# src/agents/langchain/builder.py
class AgentBuilder:
    """Agent 建造者"""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self._config = {}
        self._llm = None
        self._tools = []
        self._memory = None
        self._prompt = None

    def with_temperature(self, temperature: float):
        """设置温度"""
        self._config['temperature'] = temperature
        return self

    def with_tools(self, tool_providers: List[str]):
        """配置工具源"""
        self._config['tool_providers'] = tool_providers
        return self

    def with_memory(self, memory_config: Dict[str, Any]):
        """配置记忆"""
        self._config['memory'] = memory_config
        return self

    def with_prompt_template(self, template: str):
        """自定义提示词模板"""
        self._config['prompt_template'] = template
        return self

    async def build(self) -> BaseAgent:
        """构建 Agent"""
        # 1. 验证配置
        self._validate_config()

        # 2. 创建 LLM
        self._llm = await self._create_llm()

        # 3. 加载工具
        self._tools = await self._load_tools()

        # 4. 初始化记忆
        self._memory = self._init_memory()

        # 5. 构建 Agent
        agent = self._assemble_agent()

        # 6. 验证并返回
        await agent.validate()
        return agent

    # 预设配置模板
    @classmethod
    def for_react(cls, provider: str, model: str):
        """ReAct Agent 预设"""
        return (cls(provider, model)
                .with_temperature(0.1)
                .with_tools(['sdk', 'mcp', 'connector'])
                .with_memory({'max_messages': 50}))

    @classmethod
    def for_function_calling(cls, provider: str, model: str):
        """Function Calling Agent 预设"""
        return (cls(provider, model)
                .with_temperature(0.0)
                .with_tools(['sdk', 'mcp']))

    @classmethod
    def for_langgraph(cls, provider: str, model: str):
        """LangGraph Agent 预设"""
        return (cls(provider, model)
                .with_temperature(0.1)
                .with_tools(['core_nodes', 'sdk'])
                .with_memory({'type': 'checkpoint'}))


# 使用示例
agent = await (AgentBuilder.for_react("zhipu", "glm-4-plus")
               .with_temperature(0.2)
               .build())
```

**优势**：
- ✅ 流畅的链式 API
- ✅ 配置验证和错误处理集中化
- ✅ 预设模板简化常见场景
- ✅ 为 LangGraph 集成预留扩展点

---

#### 1.3 单例模式强化 - 全局管理器

**目标**：确保线程安全，添加生命周期管理

**设计方案**：

```python
# src/components/shared/memory/singleton.py
import threading
from typing import Optional

class ThreadSafeSingleton:
    """线程安全的单例基类"""

    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                # 双重检查锁定
                if cls not in cls._instances:
                    instance = super().__new__(cls)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    @classmethod
    def reset_instance(cls):
        """重置实例（用于测试）"""
        with cls._lock:
            if cls in cls._instances:
                instance = cls._instances[cls]
                if hasattr(instance, 'cleanup'):
                    instance.cleanup()
                del cls._instances[cls]


# src/components/shared/memory/global_memory.py
class GlobalMemoryManager(ThreadSafeSingleton):
    """全局记忆管理器（线程安全单例）"""

    _initialized = False

    def __init__(self, storage_dir: str = "data/sessions"):
        # 防止重复初始化
        if self._initialized:
            return

        self.storage_dir = storage_dir
        self._session_histories = {}
        self._lock = threading.RLock()  # 可重入锁
        self._initialized = True

    def get_session_history(self, session_id: str):
        """线程安全的获取会话历史"""
        with self._lock:
            if session_id not in self._session_histories:
                self._session_histories[session_id] = GlobalChatMessageHistory(
                    session_id, self
                )
            return self._session_histories[session_id]

    def cleanup(self):
        """清理资源"""
        with self._lock:
            # 保存所有会话
            for session_id in list(self._session_histories.keys()):
                self.save_session(session_id)
            self._session_histories.clear()
            self._initialized = False
```

**优势**：
- ✅ 线程安全保障
- ✅ 资源生命周期管理
- ✅ 支持测试时重置实例
- ✅ 防止重复初始化

---

### 2. 结构型模式

#### 2.1 适配器模式 - 统一 LLM 接口

**目标**：封装 provider 差异，提供统一接口

**设计方案**：

```python
# src/llm/langchain/adapters/base.py
from abc import ABC, abstractmethod

class LLMAdapter(ABC):
    """LLM 适配器抽象接口"""

    @abstractmethod
    def create_llm(self, model: str, **kwargs):
        """创建 LLM 实例"""
        pass

    @abstractmethod
    def get_model_config(self, model: str) -> Dict[str, Any]:
        """获取模型配置"""
        pass

    @abstractmethod
    def normalize_parameters(self, model: str, params: Dict) -> Dict:
        """标准化参数（处理 temperature_fixed 等特殊情况）"""
        pass

    @abstractmethod
    def get_recommended_agent_config(self, model: str) -> Dict:
        """获取推荐的 Agent 配置"""
        pass


# src/llm/langchain/adapters/zhipu_adapter.py
class ZhipuLLMAdapter(LLMAdapter):
    """智谱 AI LLM 适配器"""

    def normalize_parameters(self, model: str, params: Dict) -> Dict:
        """处理智谱特殊逻辑"""
        normalized = params.copy()

        # GLM-4.5 特殊处理
        if model == "glm-4.5":
            # 思考模式默认开启
            normalized.setdefault('thinking_mode', True)
            # Agent 模式增加迭代次数
            if normalized.get('mode') == 'agent':
                normalized['max_iterations'] = max(
                    normalized.get('max_iterations', 15), 15
                )

        return normalized

    def get_recommended_agent_config(self, model: str) -> Dict:
        """获取推荐的 Agent 配置"""
        if model in ["glm-4.5", "glm-4.5-flash"]:
            return {
                'agent_type': 'function_calling',
                'temperature': 0.0,
                'max_iterations': 15
            }
        else:
            return {
                'agent_type': 'react',
                'temperature': 0.1,
                'max_iterations': 8
            }


# src/llm/langchain/adapters/openai_adapter.py
class OpenAILLMAdapter(LLMAdapter):
    """OpenAI LLM 适配器"""

    def normalize_parameters(self, model: str, params: Dict) -> Dict:
        """处理 OpenAI 特殊逻辑"""
        normalized = params.copy()

        # GPT-5 温度固定为 1.0
        if model.startswith("gpt-5"):
            normalized['temperature'] = 1.0
            if 'temperature' in params and params['temperature'] != 1.0:
                logger.warning(f"GPT-5 temperature is fixed at 1.0")

        return normalized
```

**优势**：
- ✅ 封装 provider 差异
- ✅ 上层代码无需了解特殊逻辑
- ✅ 易于添加新 provider
- ✅ 配置标准化

---

#### 2.2 策略模式 - 工具加载

**目标**：统一工具管理接口，支持动态扩展

**设计方案**：

```python
# src/components/shared/tools/strategy/base.py
from abc import ABC, abstractmethod
from typing import List
from langchain_core.tools import BaseTool

class ToolProvider(ABC):
    """工具提供者策略接口"""

    @abstractmethod
    async def initialize(self):
        """初始化工具源"""
        pass

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """获取工具列表"""
        pass

    @abstractmethod
    async def reload(self):
        """重新加载工具"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        pass


# src/components/shared/tools/strategy/sdk_provider.py
class SDKToolProvider(ToolProvider):
    """SDK 工具提供者"""

    async def initialize(self):
        # 加载所有 SDK 工具
        self.tools = SDKToolManager.get_all_tools()

    def get_tools(self) -> List[BaseTool]:
        return self.tools

    async def reload(self):
        # SDK 工具无需重载
        pass


# src/components/shared/tools/strategy/mcp_provider.py
class MCPToolProvider(ToolProvider):
    """MCP 工具提供者"""

    async def initialize(self):
        await GlobalMCPManager.initialize()

    def get_tools(self) -> List[BaseTool]:
        return GlobalMCPManager.get_tools()

    async def reload(self):
        await GlobalMCPManager.reload_config()


# src/components/shared/tools/unified_manager.py
class UnifiedToolManager:
    """统一工具管理器（组合模式）"""

    def __init__(self):
        self._providers: List[ToolProvider] = []

    def register_provider(self, provider: ToolProvider):
        """注册工具提供者"""
        self._providers.append(provider)

    async def initialize_all(self):
        """初始化所有工具源"""
        for provider in self._providers:
            await provider.initialize()

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有工具"""
        tools = []
        for provider in self._providers:
            tools.extend(provider.get_tools())
        return tools

    async def reload_all(self):
        """重载所有工具"""
        for provider in self._providers:
            await provider.reload()


# 使用示例
tool_manager = UnifiedToolManager()
tool_manager.register_provider(SDKToolProvider())
tool_manager.register_provider(MCPToolProvider())
tool_manager.register_provider(ConnectorToolProvider())

await tool_manager.initialize_all()
tools = tool_manager.get_all_tools()
```

**优势**：
- ✅ 统一接口，易于扩展
- ✅ 解耦工具源和使用方
- ✅ 支持动态添加/移除工具源
- ✅ 为 LangGraph tool_node 做准备

---

#### 2.3 组合模式 - 工具组合

**应用场景**：LangGraph Core Nodes

```python
# components/langgraph/core_nodes/tool_node.py
class CompositeToolNode:
    """组合工具节点（支持多工具源）"""

    def __init__(self):
        self.tool_providers = []

    def add_provider(self, provider: ToolProvider):
        self.tool_providers.append(provider)

    def execute(self, state: Dict) -> Dict:
        """执行工具调用"""
        all_tools = []
        for provider in self.tool_providers:
            all_tools.extend(provider.get_tools())

        # 执行工具调用逻辑
        return self._execute_tools(state, all_tools)
```

---

### 3. 行为型模式

#### 3.1 观察者模式 - 配置热重载

**目标**：配置变更时自动通知订阅者

**设计方案**：

```python
# src/config/observer.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ConfigObserver(ABC):
    """配置观察者接口"""

    @abstractmethod
    def on_config_changed(self, config_type: str, old_config: Dict, new_config: Dict):
        """配置变更通知"""
        pass


class ConfigSubject:
    """配置主题（被观察者）"""

    def __init__(self):
        self._observers: List[ConfigObserver] = []
        self._config_cache: Dict[str, Any] = {}

    def attach(self, observer: ConfigObserver):
        """添加观察者"""
        self._observers.append(observer)

    def detach(self, observer: ConfigObserver):
        """移除观察者"""
        self._observers.remove(observer)

    def notify(self, config_type: str, old_config: Dict, new_config: Dict):
        """通知所有观察者"""
        for observer in self._observers:
            observer.on_config_changed(config_type, old_config, new_config)

    def update_config(self, config_type: str, new_config: Dict):
        """更新配置并通知"""
        old_config = self._config_cache.get(config_type, {})
        self._config_cache[config_type] = new_config
        self.notify(config_type, old_config, new_config)


# src/llm/langchain/llm_manager.py
class LLMManager(ConfigObserver):
    """LLM 管理器（配置观察者）"""

    def on_config_changed(self, config_type: str, old_config: Dict, new_config: Dict):
        """配置变更处理"""
        if config_type == "llm":
            logger.info("检测到 LLM 配置变更，重新加载...")
            self._load_config()

            # 清除缓存的 LLM 实例
            self._clear_cache()

            # 通知相关组件
            self._notify_agent_factory()


# src/agents/langchain/agent_factory.py
class AgentFactory(ConfigObserver):
    """Agent 工厂（配置观察者）"""

    def on_config_changed(self, config_type: str, old_config: Dict, new_config: Dict):
        """配置变更处理"""
        if config_type == "llm":
            # 清除缓存的 Agent
            self.clear_cache()
            logger.info("Agent 缓存已清除，下次创建将使用新配置")


# 启动时注册观察者
config_subject = ConfigSubject()
config_subject.attach(llm_manager)
config_subject.attach(agent_factory)

# 重载配置时触发通知
def reload_config():
    new_config = load_config_from_file()
    config_subject.update_config("llm", new_config)
```

**优势**：
- ✅ 配置变更自动传播
- ✅ 组件间松耦合
- ✅ 支持多个观察者
- ✅ 易于添加新的配置监听逻辑

---

#### 3.2 责任链模式 - 消息处理

**目标**：构建可扩展的消息处理流程

**设计方案**：

```python
# src/components/shared/memory/handlers/base.py
from abc import ABC, abstractmethod

class MessageHandler(ABC):
    """消息处理器抽象类"""

    def __init__(self):
        self._next_handler: Optional[MessageHandler] = None

    def set_next(self, handler: 'MessageHandler'):
        """设置下一个处理器"""
        self._next_handler = handler
        return handler

    def handle(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理消息"""
        # 当前处理器逻辑
        result = self._process(message)

        # 传递给下一个处理器
        if self._next_handler and result is not None:
            return self._next_handler.handle(result)

        return result

    @abstractmethod
    def _process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """具体处理逻辑（子类实现）"""
        pass


# src/components/shared/memory/handlers/filter_handler.py
class CommandFilterHandler(MessageHandler):
    """命令过滤处理器"""

    def _process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        content = message.get('content', '')
        if content.startswith('/'):
            logger.debug(f"过滤命令消息: {content}")
            return None  # 中断链条
        return message


class SensitiveWordFilterHandler(MessageHandler):
    """敏感词过滤处理器"""

    def __init__(self, sensitive_words: List[str]):
        super().__init__()
        self.sensitive_words = sensitive_words

    def _process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        content = message.get('content', '')
        for word in self.sensitive_words:
            if word in content:
                logger.warning(f"检测到敏感词: {word}")
                message['flagged'] = True
        return message


# src/components/shared/memory/handlers/transform_handler.py
class MessageEnhancementHandler(MessageHandler):
    """消息增强处理器"""

    def _process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # 添加时间戳
        message['timestamp'] = datetime.utcnow().isoformat()

        # 添加元数据
        message['metadata'] = {
            'length': len(message.get('content', '')),
            'type': message.get('role', 'unknown')
        }

        return message


# src/components/shared/memory/handlers/storage_handler.py
class StorageHandler(MessageHandler):
    """存储处理器（责任链末端）"""

    def __init__(self, storage):
        super().__init__()
        self.storage = storage

    def _process(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # 保存到存储
        self.storage.save_message(message)
        return message


# 构建处理链
def build_message_pipeline(storage):
    """构建消息处理管道"""
    # 创建处理器
    filter_cmd = CommandFilterHandler()
    filter_sensitive = SensitiveWordFilterHandler(['敏感词1', '敏感词2'])
    enhance = MessageEnhancementHandler()
    storage_handler = StorageHandler(storage)

    # 链接处理器
    filter_cmd.set_next(filter_sensitive).set_next(enhance).set_next(storage_handler)

    return filter_cmd


# 使用示例
pipeline = build_message_pipeline(session_storage)
result = pipeline.handle({
    'role': 'human',
    'content': '用户消息内容'
})
```

**优势**：
- ✅ 动态组合处理逻辑
- ✅ 易于添加/移除处理器
- ✅ 符合开闭原则
- ✅ 为 LangGraph middleware 做准备

---

#### 3.3 模板方法模式 - Agent 执行流程

**目标**：消除 Agent 代码重复

**设计方案**：

```python
# src/agents/langchain/base_agent.py
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    """Agent 基类（模板方法模式）"""

    def __init__(self, model: str, temperature: float = 0.1, **kwargs):
        self.model = model
        self.temperature = temperature
        self.verbose = kwargs.get('verbose', False)
        self.enable_memory = kwargs.get('enable_memory', True)

        # 核心组件
        self.llm = None
        self.tools = []
        self.agent_executor = None
        self.is_initialized = False

    async def initialize(self):
        """初始化流程（模板方法）"""
        if self.is_initialized:
            return

        try:
            # 步骤 1: 创建 LLM（子类实现）
            await self._create_llm()

            # 步骤 2: 加载工具（通用逻辑）
            await self._load_tools()

            # 步骤 3: 构建 Agent（子类实现）
            self._build_agent()

            # 步骤 4: 初始化记忆（通用逻辑）
            if self.enable_memory:
                self._init_memory()

            self.is_initialized = True
            logger.info(f"{self.__class__.__name__} 初始化完成")

        except Exception as e:
            logger.error(f"Agent 初始化失败: {e}")
            raise

    @abstractmethod
    async def _create_llm(self):
        """创建 LLM 实例（子类实现）"""
        pass

    @abstractmethod
    def _build_agent(self):
        """构建 Agent 执行器（子类实现）"""
        pass

    async def _load_tools(self):
        """加载工具（通用逻辑）"""
        tool_manager = UnifiedToolManager()
        await tool_manager.initialize_all()
        self.tools = tool_manager.get_all_tools()

    def _init_memory(self):
        """初始化记忆（通用逻辑）"""
        self.memory = GlobalMemoryManager()

    async def invoke(self, query: str, session_id: str = "default", **kwargs):
        """执行查询（模板方法）"""
        if not self.is_initialized:
            await self.initialize()

        return await self._execute_query(query, session_id, **kwargs)

    async def _execute_query(self, query: str, session_id: str, **kwargs):
        """执行查询核心逻辑（通用实现）"""
        if self.enable_memory and self.memory:
            result = await self.agent_executor.ainvoke(
                {"input": query},
                config={"configurable": {"session_id": session_id}}
            )
        else:
            result = await self.agent_executor.ainvoke({"input": query})

        return self._format_result(result)

    def _format_result(self, result: Dict) -> Dict:
        """格式化结果（通用逻辑）"""
        return {
            "output": result["output"],
            "success": True,
            "tool_calls": len(result.get("intermediate_steps", [])),
            # ...
        }


# src/agents/langchain/zhipu_agent.py
class ZhipuAgent(BaseAgent):
    """智谱 AI Agent（仅实现差异化部分）"""

    async def _create_llm(self):
        """智谱特定的 LLM 创建逻辑"""
        self.llm = create_zhipu_llm(
            model=self.model,
            temperature=self.temperature
        )

    def _build_agent(self):
        """智谱特定的 Agent 构建逻辑"""
        # 使用 ReAct 或 Function Calling
        if self.model in ["glm-4.5", "glm-4.5-flash"]:
            self.agent_executor = self._build_fcall_agent()
        else:
            self.agent_executor = self._build_react_agent()
```

**代码减少量估算**：

| 类 | 原代码行数 | 新代码行数 | 减少比例 |
|----|-----------|-----------|---------|
| ZhipuAgent | ~470 行 | ~150 行 | 68% |
| OpenAIAgent | ~400 行 | ~120 行 | 70% |
| OllamaAgent | ~450 行 | ~140 行 | 69% |

**优势**：
- ✅ 消除重复代码
- ✅ 统一执行流程
- ✅ 易于维护和扩展
- ✅ 新增 Agent 类型只需实现差异部分

---

## 🚀 优化建议

### 优先级分级

| 优先级 | 优化项 | 影响范围 | 实施难度 | 预计收益 |
|-------|--------|---------|---------|---------|
| **P0** | 模板方法模式 - BaseAgent | Agent 层 | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **P0** | 策略模式 - 工具管理 | Components 层 | ⭐⭐ | ⭐⭐⭐⭐ |
| **P1** | 建造者模式 - AgentBuilder | Agent 层 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **P1** | 抽象工厂 - AgentFactory | Agent 层 | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **P1** | 适配器模式 - LLMAdapter | LLM 层 | ⭐⭐ | ⭐⭐⭐ |
| **P2** | 观察者模式 - 配置热重载 | Config 层 | ⭐⭐⭐ | ⭐⭐⭐ |
| **P2** | 责任链模式 - 消息处理 | Memory 层 | ⭐⭐ | ⭐⭐⭐ |
| **P2** | 单例模式强化 | 全局管理器 | ⭐ | ⭐⭐ |

### 具体实施建议

#### 阶段 1：核心架构重构（2-3 周）

**Week 1: 基础抽象层**
- [ ] 创建 `BaseAgent` 抽象类（模板方法模式）
- [ ] 实现 `LLMAdapter` 接口及各 provider 适配器
- [ ] 重构 `ZhipuAgent`、`OpenAIAgent`、`OllamaAgent` 继承 `BaseAgent`

**Week 2: 工具系统统一**
- [ ] 定义 `ToolProvider` 策略接口
- [ ] 实现 `SDKToolProvider`、`MCPToolProvider`、`ConnectorToolProvider`
- [ ] 创建 `UnifiedToolManager` 组合管理器

**Week 3: 工厂模式重构**
- [ ] 设计 `AgentFactory` 抽象接口
- [ ] 实现各 provider 工厂类
- [ ] 创建 `AgentFactoryRegistry` 注册表

#### 阶段 2：增强功能（1-2 周）

**Week 4: 建造者与观察者**
- [ ] 实现 `AgentBuilder` 建造者
- [ ] 添加预设配置模板
- [ ] 实现配置观察者模式

**Week 5: 责任链与单例强化**
- [ ] 实现消息处理责任链
- [ ] 强化全局管理器的单例模式
- [ ] 添加资源生命周期管理

#### 阶段 3：文档与测试（1 周）

**Week 6: 文档与验证**
- [ ] 编写架构设计文档
- [ ] 添加单元测试和集成测试
- [ ] 性能对比测试
- [ ] 迁移指南

---

## 🌉 LangGraph 集成准备

### 架构对齐

基于优化后的架构，LangGraph 集成将非常顺畅：

```
现有架构                    LangGraph 架构
────────────────────────   ────────────────────────
UnifiedToolManager    →    Core Nodes (ToolNode, RAGNode)
BaseAgent             →    Agent Graph Builder
ResponsibilityChain   →    Middleware Pipeline
AgentBuilder          →    Graph Builder
MemoryManager         →    Checkpoint & State
```

### 集成路径

#### 1. Core Nodes 层

```python
# components/langgraph/core_nodes/tool_node.py
class ToolNode:
    """工具调用节点（复用 UnifiedToolManager）"""

    def __init__(self, tool_providers: List[str]):
        self.tool_manager = UnifiedToolManager()
        for provider_name in tool_providers:
            provider = self._get_provider(provider_name)
            self.tool_manager.register_provider(provider)

    def __call__(self, state: Dict) -> Dict:
        """LangGraph 节点接口"""
        tools = self.tool_manager.get_all_tools()
        # 执行工具调用逻辑...
        return updated_state
```

#### 2. Agent Graph 层

```python
# agents/langgraph/base_agent.py
from langgraph.graph import StateGraph

class LangGraphAgent:
    """基于 LangGraph 的 Agent"""

    def __init__(self, llm_adapter: LLMAdapter):
        self.llm_adapter = llm_adapter
        self.graph = None

    def build_graph(self, config: Dict):
        """构建 LangGraph"""
        graph = StateGraph()

        # 添加核心节点（复用现有组件）
        graph.add_node("planner", self._create_planner_node())
        graph.add_node("tool", ToolNode(['sdk', 'mcp']))
        graph.add_node("memory", MemoryNode(self.memory_manager))

        # 添加边
        graph.add_edge("planner", "tool")
        graph.add_edge("tool", "memory")

        self.graph = graph.compile()

    def _create_planner_node(self):
        """创建规划节点（使用 LLMAdapter）"""
        llm = self.llm_adapter.create_llm(self.model)
        return PlannerNode(llm)
```

#### 3. Middleware 层

```python
# agents/langgraph/middleware/logging_middleware.py
class LoggingMiddleware(MessageHandler):
    """日志中间件（复用责任链模式）"""

    def _process(self, message: Dict) -> Dict:
        logger.info(f"节点执行: {message.get('node_name')}")
        return message


# agents/langgraph/middleware/retry_middleware.py
class RetryMiddleware(MessageHandler):
    """重试中间件"""

    def _process(self, message: Dict) -> Dict:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return self._execute_with_retry(message)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"重试 {attempt + 1}/{max_retries}: {e}")
```

### 迁移优势

| 优化点 | LangGraph 集成收益 |
|-------|-------------------|
| **UnifiedToolManager** | 直接用于 ToolNode，无需重写工具管理逻辑 |
| **LLMAdapter** | 统一 LLM 接口，简化 PlannerNode 实现 |
| **ResponsibilityChain** | 直接映射为 LangGraph Middleware |
| **AgentBuilder** | 扩展为 GraphBuilder，复用构建逻辑 |
| **MemoryManager** | 直接用于 Checkpoint 和 State 管理 |

---

## 📊 实施路线图

### 甘特图

```
时间轴        Week 1      Week 2      Week 3      Week 4      Week 5      Week 6
阶段 1    ████████████████████████████████████
          BaseAgent   Adapter     Factory

阶段 2                                ████████████████████████
                                      Builder     Observer

阶段 3                                            ████████████
                                                  Test & Doc

LangGraph                                                     ████████████████
准备                                                          Alignment
```

### 里程碑

| 里程碑 | 时间 | 交付物 |
|-------|------|-------|
| **M1: 核心重构完成** | Week 3 | BaseAgent、LLMAdapter、AgentFactory |
| **M2: 增强功能上线** | Week 5 | AgentBuilder、Observer、Chain |
| **M3: 文档与测试完成** | Week 6 | 架构文档、测试报告、迁移指南 |
| **M4: LangGraph 就绪** | Week 6+ | 架构对齐验证、集成准备完成 |

---

## 📖 参考资料

### GoF 设计模式
- **创建型**: 工厂方法、抽象工厂、建造者、单例
- **结构型**: 适配器、组合、装饰器、代理
- **行为型**: 责任链、观察者、策略、模板方法

### 最佳实践
- [LangChain 架构指南](https://python.langchain.com/docs/guides/)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [SOLID 原则](https://en.wikipedia.org/wiki/SOLID)

---

## 📝 总结

### 优化收益预估

| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| **代码重复率** | ~40% | ~10% | **-75%** |
| **Agent 新增成本** | 3-5 天 | 0.5-1 天 | **-80%** |
| **配置热重载** | 不支持 | 支持 | **100%** |
| **LangGraph 集成就绪度** | 30% | 90% | **+200%** |
| **可维护性** | 中 | 高 | **+100%** |

### 关键成功因素

1. **渐进式重构**：分阶段实施，避免大爆炸式重构
2. **向后兼容**：保持现有 API 不变，内部逐步优化
3. **充分测试**：每个阶段完成后进行回归测试
4. **文档先行**：架构设计文档先于代码实施

### 下一步行动

1. **评审架构方案**：团队评审设计文档，收集反馈
2. **确定实施计划**：根据资源和时间调整路线图
3. **启动 Phase 1**：从 BaseAgent 和 LLMAdapter 开始
4. **持续迭代**：每周评审进度，及时调整方向

---

**文档版本历史**

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| v1.0 | 2025-10-10 | diverHansun | 初始版本 |

---

**附录：快速参考**

### 设计模式速查表

```python
# 工厂模式
agent = AgentFactoryRegistry.create_agent("zhipu", "glm-4-plus")

# 建造者模式
agent = await AgentBuilder.for_react("zhipu", "glm-4-plus").build()

# 策略模式
tool_manager = UnifiedToolManager()
tool_manager.register_provider(SDKToolProvider())

# 适配器模式
adapter = ZhipuLLMAdapter()
llm = adapter.create_llm("glm-4.5")

# 观察者模式
config_subject.attach(llm_manager)
config_subject.update_config("llm", new_config)

# 责任链模式
pipeline = build_message_pipeline(storage)
result = pipeline.handle(message)

# 模板方法模式
class MyAgent(BaseAgent):
    def _create_llm(self): ...
    def _build_agent(self): ...
```
