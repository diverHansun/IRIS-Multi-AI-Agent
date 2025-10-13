# Agent模块API统一重构方案 v4.0

## 版本信息
- **版本**: v4.0
- **日期**: 2025-10-12
- **前置重构**: v3.0 (architecture_refactoring_v3.md)
- **关联文档**: dependency_inversion_refactoring.md
- **状态**: 实施阶段
- **重大决策**:
  - 分阶段移除BaseAgent双模式支持（v4.0保留+警告，v5.0完全移除）
  - FactoryRegistry精简为注册表+缓存（约70行）
  - 完全废弃Builder模式
  - 统一创建流程: Manager → Factory → Adapters → Instances
  - 保持异步方法（create_agent为async）

---

## 1. 当前问题

### 1.1 问题汇总表

| 问题 | 描述 | 影响 |
|------|------|------|
| 4套API并存 | AgentManager/FactoryRegistry/Builder/直接实例化 | 用户困惑，维护成本高 |
| BaseAgent双模式 | 新旧方式共存，代码分支多 | 测试复杂度翻倍，认知负担高 |
| FactoryRegistry职责混乱 | 注册+验证+配置+创建 | 违反单一职责原则 |
| 调用链4层嵌套 | 每层都有配置逻辑 | 调试困难，性能开销 |
| 暴露API过多 | 27个公开符号 | 学习成本高，难以选择 |
| Adapter使用不一致 | 不同方式使用不同模式 | 配置参数应用不一致 |

### 1.2 4套API对比

| API方式 | 代码示例 | 状态 | 问题 |
|---------|---------|------|------|
| AgentManager | `agent_manager.create_agent("zhipu", "glm-4.5")` | v3.0新增 | 未统一 |
| FactoryRegistry | `await create_agent("zhipu", "glm-4.5")` | 旧方式 | 职责重叠 |
| Builder | `AgentBuilder().with_provider("zhipu").build()` | v3.0新增 | 学习成本高 |
| 直接实例化 | `await build_zhipu_agent("glm-4.5")` | 传统方式 | 不使用配置驱动 |

---

## 2. 优化目标与成功标准

### 2.1 优化目标
1. 统一创建入口：只推荐AgentManager
2. 清晰职责划分：Manager(协调) → Factory(创建) → Adapters(配置) → Instances(实现)
3. 简化调用链：从4层减少到3层
4. 强制使用Adapter：BaseAgent只支持Adapter方式
5. 最小化API暴露：只暴露必要的接口
6. 向后兼容：通过兼容层包装，标记废弃
7. 废弃Builder：移除冗余的建造者模式

### 2.2 成功标准

| 指标 | 当前 | 目标 | 改善 |
|------|------|------|------|
| 公开API数量 | 27个 | ≤15个 | -44% |
| 调用链层数 | 4层 | 2-3层 | -25% |
| FactoryRegistry行数 | 210行 | 60行 | -71% |
| 单元测试覆盖率 | 70% | >85% | +15% |
| 向后兼容性 | - | 100% | - |

---

## 3. 解决方案

### 3.1 总体策略

以AgentManager为唯一推荐入口，简化其他组件职责，保留兼容层。

**设计原则**：
1. 单一入口：强制使用AgentManager
2. 职责分离：Manager(协调) → Factory(创建) → Adapters(配置) → Instances(实现)
3. 分阶段废弃：BaseAgent v4.0保留双模式+警告，v5.0完全移除
4. 精简Registry：FactoryRegistry只做注册、查找和缓存（约70行）
5. 废弃Builder：完全移除建造者模式
6. 向后兼容：旧API通过兼容层包装
7. 保持异步：create_agent为async方法，自动调用initialize()

### 3.2 目标架构

```
[统一创建流程]
user → agent_manager.create_agent("zhipu", "glm-4.5")
           ↓
       AgentManager (协调层)
           ├── 获取配置 (provider_registry)
           ├── 创建Adapters (LLMAdapter + AgentAdapter)
           └── 获取Factory (factory_registry)
               ↓
           ZhipuAgentFactory (工厂层)
               └── 创建Agent实例
                   ↓
               ZhipuAgent (实例层)
                   ├── __init__(provider, model, llm_adapter, agent_adapter)
                   └── initialize() (加载工具、创建executor)

[清晰的职责分层]
1. Manager层: 协调创建流程，整合配置和Adapters
2. Factory层: 纯创建逻辑，返回Agent实例
3. Adapter层: 参数管理和转换
4. Instance层: Agent具体实现

[废弃的模式]
- ❌ Builder模式: 冗余，增加复杂度
- ❌ FactoryRegistry.create_agent(): 职责重复
- ❌ BaseAgent双模式: 维护困难
- ❌ 直接实例化: 绕过配置管理
```

---

## 4. 关键问题与决策

### 4.1 同步 vs 异步方法

**问题**：文档初稿提出"移除所有async/await"，但实际代码中initialize()等方法涉及网络请求，是否应该保持异步？

**决策**：保持异步方法

**理由**：
- Agent的initialize()涉及网络请求（MCP工具初始化、Connector连接等）
- 工具加载需要异步：`await tool_manager.initialize_all()`
- 保持与现有代码的一致性，避免破坏性变更
- 用户体验更好：`agent = await agent_manager.create_agent()`返回已初始化的实例

**实施**：
```python
# AgentManager.create_agent() 为异步方法
async def create_agent(self, provider, model, **kwargs):
    agent = agent_class(...)
    await agent.initialize()  # 自动初始化
    return agent

# 使用方式
agent = await agent_manager.create_agent("zhipu", "glm-4.5")
```

### 4.2 BaseAgent双模式移除策略

**问题**：立即移除双模式可能破坏现有代码，需要确保平滑过渡。

**决策**：分阶段废弃，而非立即移除

**阶段规划**：

| 版本 | 操作 | 行为 |
|------|------|------|
| v4.0 | 保留双模式+废弃警告 | 旧方式触发DeprecationWarning |
| v4.5 | 升级警告级别 | 改为FutureWarning，更明显 |
| v5.0 | 完全移除旧方式 | 强制要求adapter参数 |

**兼容层实现**：
```python
# build_zhipu_agent 提供完整兼容
async def build_zhipu_agent(model: str, **kwargs):
    warnings.warn(
        "build_zhipu_agent已废弃，请使用 agent_manager.create_agent('zhipu', model)。"
        "此函数将在v5.0中移除。",
        DeprecationWarning
    )
    from src.agents.langchain.managers import agent_manager
    return await agent_manager.create_agent("zhipu", model, **kwargs)
```

### 4.3 FactoryRegistry精简范围

**问题**：目标50行过于激进，缓存功能是否保留？

**决策**：保留缓存功能，目标调整为70行

**理由**：
- Agent创建开销大（加载工具、初始化模型），缓存可显著提升性能
- 缓存逻辑简单（约20行），不增加显著复杂度
- 缓存是注册表的合理职责

**保留功能**：
- 核心注册功能（30行）：register、get、has、list
- 缓存功能（20行）：get_cached、set_cached、clear_cache
- 辅助功能（20行）：初始化、默认注册等

**移除功能**：
- create_agent() → 移至AgentManager
- get_available_configurations() → 移至provider_registry
- _get_llm_manager() → 使用provider_registry替代
- validate_model() → 移至provider_registry

### 4.4 配置传递机制优化

**问题**：确保所有现有配置参数都能通过Adapter正确传递。

**决策**：明确职责分离，Agent参数和LLM参数分开处理

**职责划分**：

```python
# AgentAdapter：只处理Agent相关参数
AGENT_PARAMS = [
    "max_iterations",
    "max_execution_time", 
    "verbose",
    "memory_enabled",
    "prompt_provider",  # ReAct提示词选择
]

# LLMAdapter：只处理LLM相关参数
LLM_PARAMS = [
    "temperature",
    "streaming",
    "top_p",
    "max_tokens",
]
```

**特殊参数处理**：
- `temperature`：由LLMAdapter处理，传给LLM实例，Agent不持有此属性
- `prompt_provider`：Agent专用，用于ReAct提示词选择
- `disable_thinking_mode`：Ollama专用，通过kwargs传递

---

## 5. 详细设计

### 5.1 核心组件接口

#### 5.1.1 AgentManager

```python
class AgentManager:
    """Agent管理器 - 唯一推荐的创建入口"""

    def __init__(self):
        from src.core.langchain.providers import provider_registry
        from src.agents.langchain.factories import FactoryRegistry
        
        self.provider_registry = provider_registry
        self.factory_registry = FactoryRegistry()

    async def create_agent(
        self,
        provider: str,
        model: str = None,
        agent_type: str = "auto",
        **user_params
    ):
        """
        创建Agent（唯一推荐方式）

        Args:
            provider: zhipu/openai/ollama
            model: 模型名称，None时使用默认
            agent_type: auto/react/function_calling
            **user_params: 用户参数，覆盖配置

        Returns:
            初始化完成的Agent实例

        创建流程:
            1. 从provider_registry获取配置
            2. 创建LLM Adapter和Agent Adapter
            3. 创建Agent实例（传入adapters）
            4. 自动调用initialize()初始化
            5. 返回已初始化的Agent
        """
        # 1. 获取配置
        config = self.provider_registry.get_provider_config(provider)
        if not config:
            raise ValueError(f"Provider {provider} not found")
        
        if not model:
            model = config.get("default_model")

        # 2. 创建Adapters
        llm_adapter = self._create_llm_adapter(provider, model)
        agent_adapter = self._create_agent_adapter(provider, model)

        # 3. 获取Agent类并创建实例
        agent_class = self._get_agent_class(provider, model, agent_type)
        agent = agent_class(
            provider=provider,
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            **user_params
        )
        
        # 4. 自动初始化
        await agent.initialize()
        
        return agent

    def list_available_agents(self) -> List[Dict[str, Any]]:
        """列出可用Agent"""
        pass
```

#### 5.1.2 FactoryRegistry（精简版）

```python
class FactoryRegistry:
    """Agent工厂注册表（精简版：注册 + 查找 + 缓存）"""

    def __init__(self, auto_register_defaults: bool = True):
        """
        初始化工厂注册表
        
        Args:
            auto_register_defaults: 是否自动注册默认工厂
        """
        self._factories: Dict[str, BaseAgentFactory] = {}
        self._agent_cache: Dict[str, Any] = {}  # Agent缓存
        
        if auto_register_defaults:
            self._register_default_factories()

    def register_factory(self, provider: str, factory: BaseAgentFactory):
        """注册工厂"""
        self._factories[provider.upper()] = factory

    def get_factory(self, provider: str) -> Optional[BaseAgentFactory]:
        """获取工厂"""
        return self._factories.get(provider.upper())

    def has_factory(self, provider: str) -> bool:
        """检查工厂是否存在"""
        return provider.upper() in self._factories

    def list_providers(self) -> List[str]:
        """列出已注册的Provider"""
        return list(self._factories.keys())
    
    def get_cached_agent(self, cache_key: str) -> Optional[Any]:
        """获取缓存的Agent"""
        return self._agent_cache.get(cache_key)
    
    def set_cached_agent(self, cache_key: str, agent: Any):
        """缓存Agent"""
        self._agent_cache[cache_key] = agent
    
    def clear_cache(self):
        """清除缓存"""
        self._agent_cache.clear()
    
    def _register_default_factories(self):
        """注册默认工厂"""
        from .zhipu_factory import ZhipuAgentFactory
        from .openai_factory import OpenAIAgentFactory
        from .ollama_factory import OllamaAgentFactory
        
        self.register_factory("zhipu", ZhipuAgentFactory())
        self.register_factory("openai", OpenAIAgentFactory())
        self.register_factory("ollama", OllamaAgentFactory())

# 精简说明:
# - 从394行精简到约70行（-82%）
# - 完全移除的方法：
#   × create_agent() - 移至AgentManager
#   × get_available_configurations() - 移至provider_registry
#   × _get_llm_manager() - 使用provider_registry替代
#   × validate_model() - 移至provider_registry
#   × _create_adapters() - 移至AgentManager
# - 保留核心职责：注册、查找、缓存
```

#### 5.1.3 BaseAgentFactory

```python
class BaseAgentFactory(ABC):
    """Agent工厂基类"""
    
    @abstractmethod
    def create_agent(
        self,
        provider: str,
        model: str,
        llm_adapter,
        agent_adapter,
        **user_params
    ):
        """
        创建Agent实例（唯一接口）
        
        Args:
            provider: Provider名称
            model: 模型名称
            llm_adapter: LLM适配器
            agent_adapter: Agent适配器
            **user_params: 用户参数
            
        Returns:
            初始化完成的Agent实例
            
        说明:
            - 移除旧的create_agent(**kwargs)接口
            - 强制使用Adapter方式
            - 同步方法，不使用async
        """
        pass
```

#### 5.1.4 BaseAgent（v4.0版本）

```python
class BaseAgent(ABC):
    """Agent基类（v4.0版本：保留双模式但标记废弃）"""
    
    def __init__(
        self,
        provider: str = None,
        model: str = None,
        llm_adapter = None,
        agent_adapter = None,
        # 以下为旧式参数（向后兼容，v5.0将移除）
        temperature: float = None,
        verbose: bool = None,
        max_iterations: int = None,
        enable_memory: bool = None,
        **user_params
    ):
        """
        初始化BaseAgent
        
        Args:
            provider: Provider名称（新方式必需）
            model: 模型名称（必需）
            llm_adapter: LLM适配器（新方式必需）
            agent_adapter: Agent适配器（新方式必需）
            temperature: 温度参数（旧方式，已废弃）
            verbose: 详细输出（旧方式，已废弃）
            max_iterations: 最大迭代（旧方式，已废弃）
            enable_memory: 启用记忆（旧方式，已废弃）
            **user_params: 用户参数，覆盖配置
            
        v4.0 变更:
            - 保留双模式支持（向后兼容）
            - 旧方式触发DeprecationWarning
            - v5.0将移除旧方式支持
        """
        # 判断使用新方式还是旧方式
        self._use_adapters = (llm_adapter is not None and agent_adapter is not None)
        
        if not self._use_adapters:
            # 旧方式：发出废弃警告
            import warnings
            warnings.warn(
                "直接传参方式已废弃，请使用 agent_manager.create_agent()。"
                "此方式将在v5.0中移除。",
                DeprecationWarning,
                stacklevel=2
            )
        
        self.provider = provider
        self.model = model
        self.llm_adapter = llm_adapter
        self.agent_adapter = agent_adapter

        if self._use_adapters:
            # 新方式：从Adapter获取配置
            agent_params = agent_adapter.get_agent_params(**user_params)
            self.verbose = agent_params.get("verbose", False)
            self.max_iterations = agent_params.get("max_iterations", 8)
            self.enable_memory = agent_params.get("memory_enabled", True)
            self.max_execution_time = agent_params.get("max_execution_time")
        else:
            # 旧方式：直接使用传入参数
            self.verbose = verbose if verbose is not None else False
            self.max_iterations = max_iterations if max_iterations is not None else 8
            self.enable_memory = enable_memory if enable_memory is not None else True
            self.max_execution_time = None
        
        # Core components
        self.llm = None
        self.tools = []
        self.agent_executor = None
        self.is_initialized = False

    @abstractmethod
    async def initialize(self):
        """初始化Agent（由子类实现）"""
        pass
```

### 5.2 调用链优化

| 阶段 | 优化前 | 优化后 |
|------|--------|--------|
| 层1 | FactoryRegistry.create_agent()<br>获取LLMManager、验证、配置 | AgentManager.create_agent()<br>获取配置、创建Adapters |
| 层2 | ZhipuAgentFactory.create_agent()<br>判断类型、选择方法 | ZhipuAgentFactory.create_agent_with_adapters()<br>创建实例 |
| 层3 | build_zhipu_agent()<br>创建实例、initialize() | ZhipuAgent.__init__() + initialize()<br>初始化 |
| 层4 | ZhipuAgent.__init__() + initialize()<br>初始化、创建LLM、加载工具 | - |

**优势**: 减少1层嵌套，职责清晰，配置逻辑集中

### 5.3 向后兼容策略

#### 5.3.1 兼容函数包装

```python
# src/agents/langchain/factories/__init__.py
import warnings

def create_agent(provider: str, model: str = None, **kwargs):
    """
    .. deprecated:: 4.0
        请使用 agent_manager.create_agent()
    
    此函数已废弃，将在v5.0中移除。
    """
    warnings.warn(
        "create_agent已废弃，请使用agent_manager.create_agent()。"
        "此函数将在v5.0中移除。",
        DeprecationWarning,
        stacklevel=2
    )
    from src.agents.langchain.managers import agent_manager
    return agent_manager.create_agent(provider, model, **kwargs)
```

```python
# src/agents/langchain/instances/zhipu_agent.py
def build_zhipu_agent(model: str = "glm-4-plus", **kwargs) -> ZhipuAgent:
    """
    .. deprecated:: 4.0
        请使用 agent_manager.create_agent("zhipu", model)
    
    此函数已废弃，将在v5.0中移除。
    现在通过AgentManager统一创建。
    """
    warnings.warn(
        "build_zhipu_agent已废弃，请使用agent_manager.create_agent('zhipu', model)。"
        "此函数将在v5.0中移除。",
        DeprecationWarning,
        stacklevel=2
    )
    
    from src.agents.langchain.managers import agent_manager
    return agent_manager.create_agent("zhipu", model, **kwargs)
```

#### 5.3.2 废弃时间表

| 版本 | 操作 | 说明 |
|------|------|------|
| v4.0 | 标记@deprecated | DeprecationWarning |
| v4.0 | 更新文档 | 标注废弃API |
| v4.5 | 升级警告 | FutureWarning |
| v5.0 | 移除兼容层 | 完全移除 |

### 5.4 API暴露优化

**优化前（27个）**：
- Agent实例类：8个
- Factory Registry：6个
- 具体Factory类：4个
- 便捷函数：3个
- 配置查询：1个
- Builder：2个
- Adapters：3个（未在__all__）

**优化后（7个）**：
```python
# src/agents/langchain/__init__.py
"""
Agent模块 - 统一入口

推荐使用:
    from src.agents.langchain.managers import agent_manager
    agent = agent_manager.create_agent("zhipu", "glm-4.5")

创建流程:
    Manager → Factory → Adapters → Instances
"""

# === 推荐API（唯一推荐）===
from .managers import (
    agent_manager,           # 全局实例（主推荐）
    AgentManager,            # 类（自定义实例）
)

# === 向后兼容API（@deprecated，v5.0移除）===
from .instances import (
    build_zhipu_agent,
    build_openai_agent,
    build_ollama_agent,
)
from .factories import (
    create_agent,
)

__all__ = [
    # 推荐API (2个)
    "agent_manager",         # ⭐ 主推荐
    "AgentManager",          # 自定义实例用
    
    # 兼容API (4个) - 标记废弃
    "build_zhipu_agent",     # @deprecated
    "build_openai_agent",    # @deprecated
    "build_ollama_agent",    # @deprecated
    "create_agent",          # @deprecated
]

# 说明:
# - 从27个精简到7个（-74%）
# - 只推荐使用agent_manager
# - Builder完全移除（废弃）
# - 兼容API保留但标记废弃
```

---

## 6. 命名规范与约定

### 6.1 模块结构规范

```
src/
├── core/langchain/providers/          # 核心共享模块
│   ├── provider_registry.py           # ProviderRegistry + provider_registry实例
│   ├── base.py                        # BaseProvider抽象基类
│   └── utils/
│       └── ollama.py                  # Ollama工具函数
│
├── llm/langchain/                     # LLM模块
│   ├── managers/llm_manager.py        # LLMManager
│   ├── providers/                     # Provider实现（继承BaseProvider）
│   ├── adapters/                      # LLM Adapter
│   └── instances/                     # LLM实例（保留，模型实现层）
│
└── agents/langchain/                  # Agent模块
    ├── managers/
    │   └── agent_manager.py           # AgentManager（唯一入口）
    ├── factories/
    │   ├── registry.py                # FactoryRegistry（纯注册表）
    │   ├── zhipu_factory.py           # ZhipuAgentFactory
    │   ├── openai_factory.py          # OpenAIAgentFactory
    │   └── ollama_factory.py          # OllamaAgentFactory
    ├── adapters/                      # Agent Adapter
    └── instances/                     # Agent实例（BaseAgent及子类）
```

### 6.2 类命名规范

| 类型 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 管理器类 | `名词Manager` | `AgentManager`, `LLMManager` | 不加Controller/Service后缀 |
| 注册表类 | `名词Registry` | `ProviderRegistry`, `FactoryRegistry` | 不加Config前缀 |
| 工厂类 | `Provider类型Factory` | `ZhipuAgentFactory`, `OpenAIAgentFactory` | Provider + Agent/LLM + Factory |
| 适配器类 | `Provider类型Adapter` | `ZhipuAdapter`, `ZhipuAgentAdapter` | Provider + 可选类型 + Adapter |
| 实例类 | `Provider类型` | `ZhipuAgent`, `OpenAIAgent` | Provider + Agent/LLM |
| 基类 | `Base + 类型` | `BaseAgent`, `BaseProvider` | Base前缀 |
| 服务类 | `功能 + Service` | `ConfigService`, `ValidationService` | 仅在必要时使用 |

### 6.3 方法命名一致性

#### 6.3.1 动词对照表

| 操作 | LLM模块 | Agent模块 | 共享模块 |
|------|---------|-----------|----------|
| 创建 | `create_llm()` | `create_agent()` | `create_provider()` |
| 获取配置 | `get_llm_info()` | `get_agent_info()` | `get_provider_config()` |
| 列表 | `list_models()` | `list_agents()` | `list_providers()` |
| 验证 | `validate_model()` | `validate_model()` | `validate_config()` |
| 注册 | - | `register_factory()` | `register_provider()` |

#### 6.3.2 命名模式对照

| 模式 | 格式 | 示例 |
|------|------|------|
| 单例实例 | 小写_名词 | `agent_manager`, `llm_manager`, `registry` |
| 管理器类 | 名词Manager | `AgentManager`, `LLMManager` |
| 工厂类 | Provider类型Factory | `ZhipuAgentFactory` |
| 适配器类 | Provider类型Adapter | `ZhipuAdapter`, `ZhipuAgentAdapter` |
| 实例类 | Provider类型 | `ZhipuAgent`, `OpenAIAgent` |
| 注册表类 | 名词Registry | `ProviderRegistry`, `FactoryRegistry` |

### 6.4 参数命名规范

| 参数类型 | 命名 | 类型 | 示例 |
|---------|------|------|------|
| Provider名称 | `provider` | `str` | "zhipu", "openai" |
| 模型名称 | `model` | `str` | "glm-4.5", "gpt-4" |
| API密钥 | `api_key` | `str` | "sk-xxx" |
| 温度 | `temperature` | `float` | 0.1, 0.5 |
| 详细模式 | `verbose` | `bool` | True, False |
| 最大迭代 | `max_iterations` | `int` | 8, 15 |
| 启用记忆 | `enable_memory` | `bool` | True, False |
| Agent类型 | `agent_type` | `str` | "auto", "react" |

---

## 7. API分层设计

### 7.1 三层API策略

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: 便捷函数层（给普通用户）                       │
│ - create_agent(provider, model, **kwargs)            │
│ - create_llm(provider, model, **kwargs)              │
│ 特点：简单、直接、无需了解内部结构                       │
└─────────────────────────────────────────────────────┘
                        ↓ 调用
┌─────────────────────────────────────────────────────┐
│ Layer 2: Manager层（给高级用户和内部）                 │
│ - agent_manager.create_agent()                       │
│ - llm_manager.create_llm()                           │
│ - registry.get_provider_config()                     │
│ 特点：更多控制、可查询状态、可配置                       │
└─────────────────────────────────────────────────────┘
                        ↓ 调用
┌─────────────────────────────────────────────────────┐
│ Layer 3: 底层实现层（给扩展者）                        │
│ - BaseProvider, BaseAgentFactory                     │
│ - LLMAdapter, AgentAdapter                           │
│ - Agent实例类                                         │
│ 特点：完全控制、可扩展、需要理解架构                     │
└─────────────────────────────────────────────────────┘
```

### 7.2 各层详细设计

#### Layer 1: 便捷函数层

**目标用户**: 普通用户

**设计目标**: 最简API，隐藏复杂性

**API设计**:
```python
# src/agents/langchain/__init__.py
from .managers import agent_manager

def create_agent(provider: str, model: str = None, **kwargs):
    """
    便捷函数：创建Agent

    Example:
        >>> agent = create_agent("zhipu", "glm-4.5", verbose=True)
    """
    return agent_manager.create_agent(provider, model, **kwargs)

# src/llm/langchain/__init__.py
from .managers import llm_manager

def create_llm(provider: str, model: str = None, **kwargs):
    """
    便捷函数：创建LLM

    Example:
        >>> llm = create_llm("zhipu", "glm-4.5")
    """
    return llm_manager.create_llm(provider, model, **kwargs)
```

**使用场景**:
- 快速原型开发
- 简单脚本
- 不需要自定义配置

#### Layer 2: Manager层

**目标用户**: 高级用户、内部组件

**设计目标**: 提供更多控制和查询能力

**API设计**:
```python
# AgentManager接口
class AgentManager:
    def create_agent(self, provider, model, agent_type, **user_params):
        """创建Agent"""

    def list_available_agents(self) -> List[Dict]:
        """列出可用Agent"""

    def get_agent_info(self, provider, model) -> Dict:
        """获取Agent配置信息"""

# ProviderRegistry接口（共享）
class ProviderConfigRegistry:
    def get_provider_config(self, provider) -> Dict:
        """获取Provider配置"""

    def validate_model(self, provider, model) -> bool:
        """验证模型"""

    def list_providers(self) -> List[str]:
        """列出Provider"""
```

**使用场景**:
- 需要查询可用模型
- 需要验证配置
- 需要自定义记忆管理器
- 内部组件调用

#### Layer 3: 底层实现层

**目标用户**: 扩展开发者

**设计目标**: 提供完全控制和扩展能力

**API设计**:
```python
# 基类和接口
class BaseProvider(ABC):
    @abstractmethod
    def create_llm(self, model, api_key, **kwargs):
        """创建LLM"""

    @abstractmethod
    def validate_api_key(self, api_key) -> bool:
        """验证密钥"""

class BaseAgentFactory(ABC):
    @abstractmethod
    async def create_agent_with_adapters(self, model, llm_adapter, agent_adapter, **kwargs):
        """使用Adapter创建Agent"""

class BaseAgentAdapter(ABC):
    @abstractmethod
    def get_agent_params(self, **user_params) -> Dict:
        """获取Agent参数"""
```

**使用场景**:
- 实现自定义Provider
- 实现自定义Agent类型
- 实现自定义参数逻辑
- 深度定制

### 7.3 层间调用规则

**规则1**: 上层只能调用下层，不能反向调用
```python
# ✅ 正确
create_agent() → agent_manager.create_agent() → factory.create_agent_with_adapters()

# ❌ 错误
factory.create_agent() → create_agent()  # 下层不能调用上层
```

**规则2**: 同层之间可以调用（但要避免循环依赖）
```python
# ✅ 正确
agent_manager → provider_registry  # Manager依赖共享配置

# ❌ 错误
agent_manager → llm_manager → agent_manager  # 循环依赖
```

**规则3**: 跨层调用需要通过接口
```python
# ✅ 正确
agent_manager → provider_registry（共享配置）

# ❌ 错误
agent_manager → 直接访问配置文件  # 跳过服务层
```

### 7.4 使用示例对比

#### Layer 1示例（推荐给普通用户）
```python
from src.agents.langchain import create_agent

# 最简单的使用方式
agent = create_agent("zhipu", "glm-4.5")

# 覆盖部分参数
agent = create_agent("zhipu", "glm-4.5", verbose=True, temperature=0.5)
```

#### Layer 2示例（高级用户）
```python
from src.agents.langchain.managers import agent_manager

# 查询可用Agent
agents = agent_manager.list_available_agents()
for info in agents:
    print(f"{info['provider']}/{info['model']}")

# 创建Agent（更多控制）
agent = agent_manager.create_agent(
    provider="zhipu",
    model="glm-4.5",
    agent_type="function_calling",  # 明确指定类型
    verbose=True
)

# 获取Agent信息
info = agent_manager.get_agent_info("zhipu", "glm-4.5")
print(info)
```

#### Layer 3示例（扩展开发者）
```python
from src.agents.langchain.managers import AgentManager
from src.agents.langchain.factories import BaseAgentFactory
from src.agents.langchain.adapters import BaseAgentAdapter

# 自定义Adapter
class MyAgentAdapter(BaseAgentAdapter):
    def get_agent_params(self, **user_params):
        # 自定义参数逻辑
        params = super().get_agent_params(**user_params)
        params["my_custom_param"] = "value"
        return params

# 自定义Factory
class MyAgentFactory(BaseAgentFactory):
    async def create_agent_with_adapters(self, model, llm_adapter, agent_adapter, **kwargs):
        # 自定义创建逻辑
        agent = MyAgent(
            provider="my_provider",
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            **kwargs
        )
        await agent.initialize()
        return agent

# 注册自定义Factory
manager = AgentManager()
manager.factory_registry.register_factory("my_provider", MyAgentFactory())

# 使用
agent = manager.create_agent("my_provider", "my-model")
```

---

## 8. 实施计划

### 8.1 阶段划分

| 阶段 | 周期 | 任务 | 验证标准 |
|------|------|------|----------|
| 阶段1 | 第1-2周 | 重构核心组件 | 单元测试通过，新方式创建成功 |
| 阶段2 | 第3周 | 兼容层实现 | 旧代码100%兼容，警告正确 |
| 阶段3 | 第4周 | 文档更新 | 文档清晰，示例可运行 |
| 阶段4 | 第5周 | 废弃Builder | 无新代码使用Builder |

### 8.2 阶段1任务清单（核心重构）

- [ ] 精简FactoryRegistry
  - [ ] 移除create_agent方法（→ AgentManager）
  - [ ] 移除get_available_configurations（→ provider_registry）
  - [ ] 移除_get_llm_manager依赖
  - [ ] 移除validate_model（→ provider_registry）
  - [ ] 只保留注册和查找功能（目标50行）

- [ ] 重构BaseAgent
  - [ ] 移除双模式支持
  - [ ] 移除self._use_adapters判断
  - [ ] 移除所有旧式参数（temperature, verbose等直接参数）
  - [ ] 强制要求llm_adapter和agent_adapter

- [ ] 更新Factory接口
  - [ ] 统一为create_agent(provider, model, llm_adapter, agent_adapter, **kwargs)
  - [ ] 移除旧的create_agent(**kwargs)
  - [ ] 改为同步方法（移除async）

- [ ] 增强AgentManager
  - [ ] 集成provider_registry（不使用config_service）
  - [ ] 实现_create_llm_adapter方法
  - [ ] 实现_create_agent_adapter方法
  - [ ] 完善list_available_agents方法

- [ ] 移除Builder
  - [ ] 删除src/agents/langchain/builders/目录
  - [ ] 更新__init__.py移除Builder导出

- [ ] 测试
  - [ ] 编写单元测试（覆盖率>85%）
  - [ ] 运行回归测试

### 8.3 阶段2任务清单（兼容层）

- [ ] 实现兼容函数
  - [ ] factories/create_agent() - 转发到agent_manager
  - [ ] instances/build_zhipu_agent() - 转发到agent_manager
  - [ ] instances/build_openai_agent() - 转发到agent_manager
  - [ ] instances/build_ollama_agent() - 转发到agent_manager
  - [ ] 全部改为同步方法（移除async）

- [ ] 添加废弃警告
  - [ ] 所有兼容函数添加DeprecationWarning
  - [ ] 说明迁移路径
  - [ ] 标注v5.0移除时间

- [ ] 更新__init__.py
  - [ ] 精简导出（27个→7个）
  - [ ] 标记废弃API
  - [ ] 添加使用说明

- [ ] 测试
  - [ ] 编写兼容性测试
  - [ ] 验证旧代码可运行
  - [ ] 确认警告正确显示

### 8.4 阶段3任务清单

- [ ] 更新用户文档
- [ ] 编写迁移指南
- [ ] 更新代码注释（@deprecated）
- [ ] 编写示例代码
- [ ] 创建FAQ

### 8.5 阶段4任务清单（发布准备）

- [ ] 清理代码
  - [ ] 删除Builder相关代码
  - [ ] 清理未使用的导入
  - [ ] 统一代码风格

- [ ] 文档
  - [ ] 更新变更日志（CHANGELOG）
  - [ ] 标注所有破坏性变更
  - [ ] 提供迁移指南

- [ ] 验证
  - [ ] 代码审查
  - [ ] 性能测试
  - [ ] 完整回归测试

- [ ] 发布
  - [ ] 标记版本v4.0
  - [ ] 发布说明
  - [ ] 通知用户破坏性变更

---

## 9. 使用示例

### 9.1 推荐方式（Layer 1 & 2）

```python
# Layer 1: 便捷函数（最简单）
from src.agents.langchain import create_agent
agent = create_agent("zhipu", "glm-4.5", verbose=True)

# Layer 2: Manager（更多控制）
from src.agents.langchain.managers import agent_manager

# 创建Agent（使用默认配置）
agent = agent_manager.create_agent("zhipu", "glm-4.5")

# 创建Agent（覆盖配置参数）
agent = agent_manager.create_agent(
    provider="zhipu",
    model="glm-4.5",
    temperature=0.5,
    verbose=True,
    max_iterations=15
)

# 列出可用Agent
agents = agent_manager.list_available_agents()
```

### 9.2 迁移示例

```python
# 旧方式1: FactoryRegistry
from src.agents.langchain.factories import create_agent
agent = create_agent("zhipu", "glm-4.5", verbose=True)  # @deprecated

# 新方式（唯一推荐）
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5", verbose=True)

# ─────────────────────────────────────────────────────

# 旧方式2: Builder（已完全废弃）
from src.agents.langchain import AgentBuilder  # 不再可用
# Builder模式已完全移除，请使用AgentManager

# 新方式
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5", temperature=0.5)

# ─────────────────────────────────────────────────────

# 旧方式3: 直接实例化
from src.agents.langchain import build_zhipu_agent
agent = build_zhipu_agent("glm-4.5", verbose=True)  # @deprecated

# 新方式
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5", verbose=True)

# ─────────────────────────────────────────────────────

# 说明:
# 1. 移除所有async/await（create_agent是同步方法）
# 2. Builder完全废弃，不提供兼容层
# 3. build_*_agent保留兼容层，但标记废弃
```

---

## 10. 测试策略

### 10.1 测试覆盖矩阵

| 测试类型 | 覆盖内容 | 目标覆盖率 |
|---------|---------|-----------|
| 单元测试 | 各组件独立功能 | >85% |
| 集成测试 | 端到端创建流程 | >80% |
| 兼容性测试 | 旧API向后兼容 | 100% |
| 性能测试 | 调用链性能 | 基准±10% |

### 10.2 关键测试用例

```python
# 单元测试
def test_create_agent_with_defaults():
    agent = agent_manager.create_agent("zhipu", "glm-4.5")
    assert agent.max_iterations == 15  # 从配置读取

def test_create_agent_with_overrides():
    agent = agent_manager.create_agent("zhipu", "glm-4.5", max_iterations=20)
    assert agent.max_iterations == 20  # 用户参数优先

# 兼容性测试
async def test_build_zhipu_agent_deprecated():
    with warnings.catch_warnings(record=True) as w:
        agent = await build_zhipu_agent("glm-4.5")
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)

# 集成测试
async def test_full_agent_creation_flow():
    agent = agent_manager.create_agent("zhipu", "glm-4.5")
    await agent.initialize()
    assert agent.is_initialized
    result = await agent.invoke("测试查询")
    assert result["success"]
```

---

## 11. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| BaseAgent双模式移除破坏旧代码 | 高 | 中 | 兼容层包装，确保build_*_agent()可用 |
| FactoryRegistry大量修改影响使用 | 中 | 中 | 提供兼容函数，废弃警告 |
| Builder废弃影响用户 | 低 | 低 | 清晰迁移指南，Builder使用较少 |
| API暴露减少功能不可用 | 低 | 低 | 保留高级API（BaseAgentAdapter） |

---

## 12. 收益分析

### 12.1 量化指标

| 指标 | 当前 | 优化后 | 改善 |
|------|------|--------|------|
| 公开API数量 | 27个 | 12个 | -56% |
| FactoryRegistry行数 | 210行 | 60行 | -71% |
| BaseAgent复杂度 | 双模式 | 单模式 | -50% |
| 调用链层数 | 4层 | 3层 | -25% |
| 学习曲线 | 4种方式 | 1种推荐 | -75% |

### 12.2 定性收益

**用户体验**：
- 只需记住 `agent_manager.create_agent()`
- 参数传递直观，无需了解内部结构
- 文档清晰，示例简洁

**代码质量**：
- 职责清晰，易于维护
- 减少重复代码 > 30%
- 测试覆盖更简单

**可扩展性**：
- 新增Provider只需实现Factory
- 不需要修改多个组件
- 向后兼容策略明确

---

## 13. 与依赖解耦方案的关系

### 13.1 关系图

```
[dependency_inversion_refactoring.md]
    ↓ 基础
创建共享配置模块 (src/core/langchain/providers/)
    ↓ 依赖
[本方案 - agents_api_unification_v4.md]
    ↓ 使用
AgentManager依赖provider_registry（不依赖LLMManager）
```

### 13.2 实施顺序

**推荐**: 先依赖解耦，再API统一

**可选**: 并行实施（团队A: 依赖解耦，团队B: API统一）

---

## 14. 总结

### 14.1 核心改进
1. 统一到 `agent_manager.create_agent()` 单一入口（强制）
2. 精简FactoryRegistry为注册表+缓存（-82%代码，394行→70行）
3. 分阶段移除BaseAgent双模式（v4.0保留+警告，v5.0完全移除）
4. 完全废弃Builder模式（-100%，228行→0行）
5. 减少公开API（-74%，27个→7个）
6. 清晰的创建流程：Manager → Factory → Adapters → Instances
7. 保持异步方法（create_agent为async，自动调用initialize）
8. 使用provider_registry替代LLMManager依赖
9. 明确Adapter职责分离（LLM参数 vs Agent参数）

### 14.2 预期收益
- 用户体验提升：只需记住1种创建方式（`await agent_manager.create_agent()`）
- 代码质量提升：减少500+行重复代码
- 维护成本降低：职责清晰（Manager→Factory→Adapters→Instances）
- 向后兼容：旧代码可用（通过兼容层），分阶段废弃
- 架构清晰：分阶段推进Adapter统一，v5.0完全统一
- 性能优化：保留缓存功能，提升Agent创建速度

### 14.3 实施周期
5周（分阶段实施，降低风险）

---

**文档版本**: v4.0
**最后更新**: 2025-10-12
**前置文档**: architecture_refactoring_v3.md
**关联文档**: dependency_inversion_refactoring.md
