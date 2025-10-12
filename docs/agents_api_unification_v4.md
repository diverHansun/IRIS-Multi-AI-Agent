# Agent模块API统一重构方案 v4.0

## 版本信息
- **版本**: v4.0
- **日期**: 2025-10-12
- **前置重构**: v3.0 (architecture_refactoring_v3.md)
- **关联文档**: dependency_inversion_refactoring.md
- **状态**: 设计阶段

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
1. 统一创建入口：只推荐一种创建方式
2. 清晰职责划分：每个组件只做一件事
3. 简化调用链：减少不必要的嵌套
4. 一致的Adapter使用：所有方式都使用Adapter
5. 最小化API暴露：只暴露必要的接口
6. 向后兼容：保持旧代码可用，标记废弃

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
1. 单一入口：推荐使用AgentManager
2. 职责分离：Registry只做注册，Factory只做创建
3. 配置驱动：所有创建方式必须使用Adapter
4. 向后兼容：保留旧API但标记@deprecated

### 3.2 目标架构

```
[推荐使用]
user → agent_manager.create_agent("zhipu", "glm-4.5")
           ↓
       AgentManager (统一入口)
           ├── 获取配置 (ConfigService)
           ├── 创建Adapters (LLMAdapter + AgentAdapter)
           └── 调用Factory
               ↓
           ZhipuAgentFactory (纯创建逻辑)
               ↓
           ZhipuAgent.__init__() (初始化)

[组件职责]
- AgentManager: 统一入口，协调创建流程
- FactoryRegistry: 纯注册表，只做注册和查找
- Factory: 纯创建逻辑，不做配置管理
- BaseAgent: 移除双模式，只支持Adapter
- Builder: 废弃
```

---

## 4. 详细设计

### 4.1 核心组件接口

#### 4.1.1 AgentManager

```python
class AgentManager:
    def __init__(self):
        from src.core.langchain.providers import config_service
        self.config_service = config_service
        self.factory_registry = FactoryRegistry()

    def create_agent(
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
        """
        config = self.config_service.get_provider_config(provider)
        if not model:
            model = config.get("default_model")

        llm_adapter = self._create_llm_adapter(provider, model)
        agent_adapter = self._create_agent_adapter(provider, model)

        factory = self.factory_registry.get_factory(provider)
        return factory.create_agent_with_adapters(
            model=model,
            llm_adapter=llm_adapter,
            agent_adapter=agent_adapter,
            **user_params
        )

    def list_available_agents(self) -> List[Dict[str, Any]]:
        """列出可用Agent"""
        pass
```

#### 4.1.2 FactoryRegistry（精简版）

```python
class FactoryRegistry:
    """Agent工厂注册表（只做注册和查找）"""

    def __init__(self, auto_register_defaults: bool = True):
        self._factories: Dict[str, BaseAgentFactory] = {}
        if auto_register_defaults:
            self._register_default_factories()

    def register_factory(self, provider: str, factory: BaseAgentFactory):
        self._factories[provider.upper()] = factory

    def get_factory(self, provider: str) -> Optional[BaseAgentFactory]:
        return self._factories.get(provider.upper())

    def has_factory(self, provider: str) -> bool:
        return provider.upper() in self._factories

    def list_providers(self) -> List[str]:
        return list(self._factories.keys())

    # 移除的方法（迁移到AgentManager或ConfigService）：
    # - create_agent() → AgentManager.create_agent()
    # - get_available_configurations() → ConfigService.list_providers()
    # - _get_llm_manager() → 移除
    # - validate_model() → ConfigService.validate_model()
```

#### 4.1.3 BaseAgentFactory

```python
class BaseAgentFactory(ABC):
    @abstractmethod
    async def create_agent(self, model: str, **kwargs):
        """旧接口，保持兼容"""
        pass

    async def create_agent_with_adapters(
        self,
        model: str,
        llm_adapter,
        agent_adapter,
        **user_params
    ):
        """新接口，推荐使用"""
        return await self.create_agent(model=model, **user_params)
```

#### 4.1.4 BaseAgent（精简版）

```python
class BaseAgent(ABC):
    def __init__(
        self,
        provider: str,
        model: str,
        llm_adapter,        # 必需
        agent_adapter,      # 必需
        **user_params
    ):
        self.provider = provider
        self.model = model
        self.llm_adapter = llm_adapter
        self.agent_adapter = agent_adapter

        # 从Adapter获取配置（统一方式）
        agent_params = agent_adapter.get_agent_params(**user_params)

        self.temperature = agent_params.get("temperature")
        self.verbose = agent_params.get("verbose", False)
        self.max_iterations = agent_params.get("max_iterations", 8)
        self.enable_memory = agent_params.get("memory_enabled", True)
        self.max_execution_time = agent_params.get("max_execution_time")

        # 移除 self._use_adapters 判断
        # 移除双模式分支逻辑
```

### 4.2 调用链优化

| 阶段 | 优化前 | 优化后 |
|------|--------|--------|
| 层1 | FactoryRegistry.create_agent()<br>获取LLMManager、验证、配置 | AgentManager.create_agent()<br>获取配置、创建Adapters |
| 层2 | ZhipuAgentFactory.create_agent()<br>判断类型、选择方法 | ZhipuAgentFactory.create_agent_with_adapters()<br>创建实例 |
| 层3 | build_zhipu_agent()<br>创建实例、initialize() | ZhipuAgent.__init__() + initialize()<br>初始化 |
| 层4 | ZhipuAgent.__init__() + initialize()<br>初始化、创建LLM、加载工具 | - |

**优势**: 减少1层嵌套，职责清晰，配置逻辑集中

### 4.3 向后兼容策略

#### 4.3.1 兼容函数包装

```python
# src/agents/langchain/factories/__init__.py
import warnings

async def create_agent(provider: str, model: str = None, **kwargs):
    """
    .. deprecated:: 4.0
        请使用 agent_manager.create_agent()
    """
    warnings.warn(
        "create_agent已废弃，请使用agent_manager.create_agent()，"
        "此函数将在v5.0中移除",
        DeprecationWarning,
        stacklevel=2
    )
    from src.agents.langchain.managers import agent_manager
    return agent_manager.create_agent(provider, model, **kwargs)
```

```python
# src/agents/langchain/instances/zhipu_agent.py
async def build_zhipu_agent(model: str = "glm-4-plus", **kwargs) -> ZhipuAgent:
    """
    .. deprecated:: 4.0
        请使用 agent_manager.create_agent("zhipu", model)
    """
    warnings.warn(...)

    # 包装为新方式
    llm_adapter = ZhipuAdapter(model=model, mode="llm")
    agent_adapter = ZhipuAgentAdapter(provider="zhipu", model=model)

    agent = ZhipuAgent(
        provider="zhipu",
        model=model,
        llm_adapter=llm_adapter,
        agent_adapter=agent_adapter,
        **kwargs
    )
    await agent.initialize()
    return agent
```

#### 4.3.2 废弃时间表

| 版本 | 操作 | 说明 |
|------|------|------|
| v4.0 | 标记@deprecated | DeprecationWarning |
| v4.0 | 更新文档 | 标注废弃API |
| v4.5 | 升级警告 | FutureWarning |
| v5.0 | 移除兼容层 | 完全移除 |

### 4.4 API暴露优化

**优化前（27个）**：
- Agent实例类：8个
- Factory Registry：6个
- 具体Factory类：4个
- 便捷函数：3个
- 配置查询：1个
- Builder：2个
- Adapters：3个（未在__all__）

**优化后（12个）**：
```python
# src/agents/langchain/__init__.py
"""
推荐使用:
    from src.agents.langchain.managers import agent_manager
    agent = agent_manager.create_agent("zhipu", "glm-4.5")
"""

# === 推荐API ===
from .managers import (
    agent_manager,           # 全局实例
    AgentManager,            # 类（自定义）
)

# === 向后兼容API（@deprecated）===
from .instances import (
    ZhipuAgent, OpenAIAgent, OllamaAgent, ZhipuFCallAgent,
    build_zhipu_agent, build_zhipu_fcall_agent,
    build_openai_agent, build_ollama_agent,
)
from .factories import (create_agent, create_default_agent)

# === 高级API ===
from .adapters import (BaseAgentAdapter)

__all__ = [
    # 推荐 (2个)
    "agent_manager", "AgentManager",
    # 兼容 (9个)
    "ZhipuAgent", "OpenAIAgent", "OllamaAgent", "ZhipuFCallAgent",
    "build_zhipu_agent", "build_zhipu_fcall_agent",
    "build_openai_agent", "build_ollama_agent", "create_agent",
    # 高级 (1个)
    "BaseAgentAdapter",
]
```

---

## 5. 命名规范与约定

### 5.1 模块结构规范

```
src/
├── core/langchain/providers/          # 核心共享模块
│   ├── registry.py                    # ProviderConfigRegistry
│   ├── base.py                        # BaseProvider
│   ├── validator.py                   # ModelValidator
│   └── utils/                         # 工具函数
│
├── llm/langchain/                     # LLM模块
│   ├── managers/llm_manager.py        # LLMManager
│   ├── providers/                     # Provider实现
│   ├── adapters/                      # LLM Adapter
│   └── instances/                     # LLM实例（建议废弃）
│
└── agents/langchain/                  # Agent模块
    ├── managers/agent_manager.py      # AgentManager
    ├── factories/                     # Agent工厂
    ├── adapters/                      # Agent Adapter
    └── instances/                     # Agent实例
```

### 5.2 类命名规范

| 类型 | 格式 | 示例 | 说明 |
|------|------|------|------|
| 管理器类 | `名词Manager` | `AgentManager`, `LLMManager` | 不加Controller/Service后缀 |
| 注册表类 | `名词Registry` | `ProviderRegistry`, `FactoryRegistry` | 不加Config前缀 |
| 工厂类 | `Provider类型Factory` | `ZhipuAgentFactory`, `OpenAIAgentFactory` | Provider + Agent/LLM + Factory |
| 适配器类 | `Provider类型Adapter` | `ZhipuAdapter`, `ZhipuAgentAdapter` | Provider + 可选类型 + Adapter |
| 实例类 | `Provider类型` | `ZhipuAgent`, `OpenAIAgent` | Provider + Agent/LLM |
| 基类 | `Base + 类型` | `BaseAgent`, `BaseProvider` | Base前缀 |
| 服务类 | `功能 + Service` | `ConfigService`, `ValidationService` | 仅在必要时使用 |

### 5.3 方法命名一致性

#### 5.3.1 动词对照表

| 操作 | LLM模块 | Agent模块 | 共享模块 |
|------|---------|-----------|----------|
| 创建 | `create_llm()` | `create_agent()` | `create_provider()` |
| 获取配置 | `get_llm_info()` | `get_agent_info()` | `get_provider_config()` |
| 列表 | `list_models()` | `list_agents()` | `list_providers()` |
| 验证 | `validate_model()` | `validate_model()` | `validate_config()` |
| 注册 | - | `register_factory()` | `register_provider()` |

#### 5.3.2 命名模式对照

| 模式 | 格式 | 示例 |
|------|------|------|
| 单例实例 | 小写_名词 | `agent_manager`, `llm_manager`, `registry` |
| 管理器类 | 名词Manager | `AgentManager`, `LLMManager` |
| 工厂类 | Provider类型Factory | `ZhipuAgentFactory` |
| 适配器类 | Provider类型Adapter | `ZhipuAdapter`, `ZhipuAgentAdapter` |
| 实例类 | Provider类型 | `ZhipuAgent`, `OpenAIAgent` |
| 注册表类 | 名词Registry | `ProviderRegistry`, `FactoryRegistry` |

### 5.4 参数命名规范

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

## 6. API分层设计

### 6.1 三层API策略

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

### 6.2 各层详细设计

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

### 6.3 层间调用规则

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
agent_manager → config_service  # 同为Manager层

# ❌ 错误
agent_manager → llm_manager → agent_manager  # 循环依赖
```

**规则3**: 跨层调用需要通过接口
```python
# ✅ 正确
agent_manager → IConfigService接口 → ProviderRegistry实现

# ❌ 错误
agent_manager → 直接访问配置文件  # 跳过服务层
```

### 6.4 使用示例对比

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

## 7. 实施计划

### 7.1 阶段划分

| 阶段 | 周期 | 任务 | 验证标准 |
|------|------|------|----------|
| 阶段1 | 第1-2周 | 重构核心组件 | 单元测试通过，新方式创建成功 |
| 阶段2 | 第3周 | 兼容层实现 | 旧代码100%兼容，警告正确 |
| 阶段3 | 第4周 | 文档更新 | 文档清晰，示例可运行 |
| 阶段4 | 第5周 | 废弃Builder | 无新代码使用Builder |

### 7.2 阶段1任务清单

- [ ] 重构FactoryRegistry（移除create_agent等方法，60行）
- [ ] 增强AgentManager（集成配置服务）
- [ ] 重构BaseAgent（移除双模式）
- [ ] 调整Factory接口（添加create_agent_with_adapters）
- [ ] 编写单元测试（覆盖率>85%）
- [ ] 运行回归测试

### 7.3 阶段2任务清单

- [ ] 实现兼容函数（create_agent, build_*_agent）
- [ ] 添加DeprecationWarning
- [ ] 更新__init__.py（标记@deprecated）
- [ ] 编写兼容性测试
- [ ] 验证旧代码可运行

### 7.4 阶段3任务清单

- [ ] 更新用户文档
- [ ] 编写迁移指南
- [ ] 更新代码注释（@deprecated）
- [ ] 编写示例代码
- [ ] 创建FAQ

### 7.5 阶段4任务清单

- [ ] 标记Builder为废弃
- [ ] 迁移现有Builder使用
- [ ] 更新变更日志
- [ ] 代码审查
- [ ] 发布v4.0

---

## 8. 使用示例

### 8.1 推荐方式（Layer 1 & 2）

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

### 8.2 迁移示例

```python
# 旧方式1: FactoryRegistry
from src.agents.langchain.factories import create_agent
agent = await create_agent("zhipu", "glm-4.5", verbose=True)

# 新方式
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5", verbose=True)

# ─────────────────────────────────────────────────────

# 旧方式2: Builder
from src.agents.langchain import AgentBuilder
agent = await AgentBuilder()
    .with_provider("zhipu")
    .with_model("glm-4.5")
    .with_temperature(0.5)
    .build()

# 新方式（更简洁）
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5", temperature=0.5)

# ─────────────────────────────────────────────────────

# 旧方式3: 直接实例化
from src.agents.langchain import build_zhipu_agent
agent = await build_zhipu_agent("glm-4.5", verbose=True)

# 新方式
from src.agents.langchain.managers import agent_manager
agent = agent_manager.create_agent("zhipu", "glm-4.5", verbose=True)
```

---

## 9. 测试策略

### 9.1 测试覆盖矩阵

| 测试类型 | 覆盖内容 | 目标覆盖率 |
|---------|---------|-----------|
| 单元测试 | 各组件独立功能 | >85% |
| 集成测试 | 端到端创建流程 | >80% |
| 兼容性测试 | 旧API向后兼容 | 100% |
| 性能测试 | 调用链性能 | 基准±10% |

### 9.2 关键测试用例

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

## 10. 风险与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| BaseAgent双模式移除破坏旧代码 | 高 | 中 | 兼容层包装，确保build_*_agent()可用 |
| FactoryRegistry大量修改影响使用 | 中 | 中 | 提供兼容函数，废弃警告 |
| Builder废弃影响用户 | 低 | 低 | 清晰迁移指南，Builder使用较少 |
| API暴露减少功能不可用 | 低 | 低 | 保留高级API（BaseAgentAdapter） |

---

## 11. 收益分析

### 11.1 量化指标

| 指标 | 当前 | 优化后 | 改善 |
|------|------|--------|------|
| 公开API数量 | 27个 | 12个 | -56% |
| FactoryRegistry行数 | 210行 | 60行 | -71% |
| BaseAgent复杂度 | 双模式 | 单模式 | -50% |
| 调用链层数 | 4层 | 3层 | -25% |
| 学习曲线 | 4种方式 | 1种推荐 | -75% |

### 11.2 定性收益

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

## 12. 与依赖解耦方案的关系

### 12.1 关系图

```
[dependency_inversion_refactoring.md]
    ↓ 基础
创建共享配置模块 (src/core/langchain/providers/)
    ↓ 依赖
[本方案 - agents_api_unification_v4.md]
    ↓ 使用
AgentManager依赖ConfigService（而非LLMManager）
```

### 12.2 实施顺序

**推荐**: 先依赖解耦，再API统一

**可选**: 并行实施（团队A: 依赖解耦，团队B: API统一）

---

## 13. 总结

### 13.1 核心改进
1. 统一到 `agent_manager.create_agent()` 单一入口
2. 精简FactoryRegistry为纯注册表（-71%代码）
3. 移除BaseAgent双模式支持（-50%复杂度）
4. 废弃Builder模式（减少学习成本）
5. 减少公开API（-56%暴露符号）
6. 定义清晰的命名规范和API分层

### 13.2 预期收益
- 用户体验提升：只需记住1种创建方式
- 代码质量提升：减少30%重复代码
- 维护成本降低：职责清晰，易于扩展
- 向后兼容：旧代码100%可用

### 13.3 实施周期
5周（分阶段实施，降低风险）

---

**文档版本**: v4.0
**最后更新**: 2025-10-12
**前置文档**: architecture_refactoring_v3.md
**关联文档**: dependency_inversion_refactoring.md
