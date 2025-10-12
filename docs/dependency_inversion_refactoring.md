# Agent与LLM模块依赖解耦重构方案

## 版本信息
- **版本**: v1.2
- **日期**: 2025-10-12
- **前置重构**: v3.0 (architecture_refactoring_v3.md)
- **状态**: 设计阶段
- **v1.2更新内容**:
  - BaseProvider改为完整迁移（非抽象提取）
  - 移除单例模式，使用模块级实例
  - 统一命名为`provider_registry`
  - 明确LLM Adapter通过依赖注入解决
  - 移除ModelValidator组件
  - 明确instances为模型实现层，保留在llm模块

---

## 1. 问题分析

### 1.1 核心问题
当前架构中，`src/agents/langchain` 模块对 `src/llm/langchain` 模块存在过度依赖，违反了**依赖倒置原则**（Dependency Inversion Principle）。

**依赖倒置原则**：高层模块不应依赖低层模块，两者都应依赖抽象。

### 1.2 当前依赖关系

#### 依赖点1: AgentManager依赖LLMManager
```python
# src/agents/langchain/managers/agent_manager.py:26-27
from src.llm.langchain.managers import llm_manager
self.llm_manager = llm_manager
```

**问题**：Agent Manager直接依赖LLM Manager的具体实现，需要Provider配置时必须通过LLM模块获取，无法独立测试Agent模块。

#### 依赖点2: BaseAgent使用LLM Adapter
```python
# src/agents/langchain/instances/base_agent.py:175-186
async def _create_llm_with_adapter(self):
    llm_params = self.llm_adapter.get_llm_params()
    # 使用来自llm模块的Adapter
```

**问题**：BaseAgent需要导入llm模块的Adapter类。

**解决方案**：通过依赖注入，AgentManager传入adapter实例，BaseAgent不直接import llm模块。

#### 依赖点3: Agent实例依赖LLM创建函数
```python
# src/agents/langchain/instances/zhipu_agent.py:19-20
from src.llm.langchain.instances.zhipu_llm import create_zhipu_llm
from src.llm.langchain.managers import get_llm_info
```

**问题**：Agent实例直接导入LLM创建函数。

**解决方案**：通过AgentManager和Adapter协调，Agent实例不直接依赖LLM模块。

#### 依赖点4: FactoryRegistry依赖LLMManager
```python
# src/agents/langchain/factories/registry.py:46-48
def _get_llm_manager(self):
    from src.llm.langchain.managers import LLMManager
    self._llm_manager = LLMManager()
```

**问题**：Factory需要LLMManager验证模型，职责混乱。

#### 依赖点5: Ollama工厂依赖Provider工具
```python
# src/agents/langchain/factories/ollama_factory.py:62
from src.llm.langchain.providers.ollama import list_ollama_models
```

**问题**：工厂依赖特定Provider的工具函数，跨模块调用。

### 1.3 依赖关系图

```
[Current Architecture - Tight Coupling]

src/agents/langchain/
├── managers/agent_manager.py
│   └──> src.llm.langchain.managers.llm_manager ❌
├── instances/base_agent.py
│   └──> src.llm.langchain.adapters.* ❌
├── instances/zhipu_agent.py
│   └──> src.llm.langchain.instances.zhipu_llm ❌
│   └──> src.llm.langchain.managers.get_llm_info ❌
├── factories/registry.py
│   └──> src.llm.langchain.managers.LLMManager ❌
└── factories/ollama_factory.py
    └──> src.llm.langchain.providers.ollama.utils ❌

问题: Agent模块直接依赖LLM模块的具体实现
```

---

## 2. 解决方案

### 2.1 总体策略
引入**共享配置模块**作为抽象层，实现依赖倒置。

**核心思想**：
- Agent和LLM模块都依赖共享抽象
- 共享模块提供统一的配置、验证、工具接口
- 具体实现在各自模块内部

### 2.2 目标架构

```
[Target Architecture - Dependency Inversion]

src/core/langchain/providers/          [新增共享模块]
├── provider_registry.py  # ProviderRegistry类 + provider_registry实例
├── base.py               # BaseProvider抽象基类
└── utils/
    └── ollama.py         # Ollama工具函数

       ↑                    ↑
       |                    |
       |                    |
src/agents/langchain/  src/llm/langchain/
       |                    |
       |                    |
       └────────┬───────────┘
                |
         依赖抽象接口，不依赖彼此

优势: 两个模块通过抽象解耦，可以独立开发和测试
```

---

## 3. 详细设计

### 3.1 共享配置模块结构

```
src/core/langchain/providers/
├── __init__.py
├── provider_registry.py  # ProviderRegistry类 + provider_registry实例
├── base.py               # BaseProvider抽象基类（完整迁移）
└── utils/
    ├── __init__.py
    └── ollama.py         # Ollama工具函数（从llm模块迁移）
```

### 3.2 核心组件设计

#### 3.2.1 ProviderRegistry

**职责**：统一的Provider配置管理

**来源**：从 `src/llm/langchain/managers/provider_registry.py` **完整迁移**

**设计决策**：
- ❌ 不使用单例模式（避免测试困难）
- ✅ 使用模块级实例（全局可用，但可替换）
- ✅ 统一命名为 `provider_registry`

**接口**：
```python
# src/core/langchain/providers/provider_registry.py
class ProviderRegistry:
    """Provider注册表（共享）"""

    def __init__(self):
        """从providers.json加载配置"""
        self._providers: Dict[str, Dict[str, Any]] = {}
        self._load_from_config()

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """获取Provider配置"""
        provider_key = provider.upper()
        return self._providers.get(provider_key)

    def get_model_config(self, provider: str, model: str) -> Dict[str, Any]:
        """获取模型配置"""
        provider_config = self.get_provider_config(provider)
        if not provider_config:
            return None
        models = provider_config.get("models", {})
        return models.get(model)

    def list_providers(self) -> List[str]:
        """列出所有Provider"""
        return list(self._providers.keys())

    def validate_model(self, provider: str, model: str) -> bool:
        """验证模型是否支持"""
        model_config = self.get_model_config(provider, model)
        return model_config is not None

    def reload_config(self):
        """重新加载配置"""
        self._load_from_config()

    def _load_from_config(self):
        """从配置文件加载"""
        from src.config import config_loader
        config_data = config_loader.load_config()
        self._providers = config_data.get("providers", {})

# 全局模块级实例
provider_registry = ProviderRegistry()
```

**使用方式**：
```python
# Agent模块使用
from src.core.langchain.providers import provider_registry
config = provider_registry.get_provider_config("zhipu")

# LLM模块使用
from src.core.langchain.providers import provider_registry
config = provider_registry.get_provider_config("zhipu")

# 测试时可以替换
from src.core.langchain.providers import provider_registry
import src.core.langchain.providers.provider_registry as registry_module
registry_module.provider_registry = MockRegistry()  # 可替换
```

#### 3.2.2 BaseProvider

**职责**：Provider抽象基类

**来源**：从 `src/llm/langchain/providers/base.py` **完整迁移**

**重要说明**：
- 这是**完整迁移**，不是抽象提取
- 迁移所有代码（包括具体方法实现）
- `src/llm/langchain/providers/base.py` 会被删除
- llm模块中的具体Provider直接继承core中的BaseProvider

**接口**：
```python
# src/core/langchain/providers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseProvider(ABC):
    """Provider抽象基类（共享）"""

    def __init__(self, config: Dict[str, Any]):
        """初始化Provider"""
        self.config = config
        self.name = config.get("name")
        self.default_model = config.get("default_model")
        self.api_key_env = config.get("api_key_env")
        self.models = config.get("models", {})
        self.mode_defaults = config.get("mode_defaults", {})

    @abstractmethod
    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """创建LLM实例（由具体Provider实现）"""
        pass

    @abstractmethod
    def validate_api_key(self, api_key: str) -> bool:
        """验证API密钥"""
        pass

    def get_supported_models(self) -> Dict[str, Any]:
        """获取支持的模型（具体实现）"""
        return self.models

    def get_default_model(self) -> str:
        """获取默认模型（具体实现）"""
        return self.default_model

    def get_model_config(self, model: str) -> Optional[Dict[str, Any]]:
        """获取模型配置（具体实现）"""
        return self.models.get(model)

    def validate_model(self, model: str) -> bool:
        """验证模型是否支持（具体实现）"""
        return model in self.models

    def get_mode_defaults(self, mode: str) -> Dict[str, Any]:
        """获取模式默认参数（具体实现）"""
        return self.mode_defaults.get(mode, {})

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, default_model={self.default_model})"
```

**具体实现示例**：
```python
# src/llm/langchain/providers/zhipu/provider.py
from src.core.langchain.providers import BaseProvider

class ZhipuProvider(BaseProvider):
    """智谱Provider实现"""

    def create_llm(self, model: str, api_key: str = None, **kwargs):
        """创建智谱LLM"""
        from src.llm.langchain.instances.zhipu_llm import create_zhipu_llm
        return create_zhipu_llm(model=model, api_key=api_key, **kwargs)

    def validate_api_key(self, api_key: str) -> bool:
        """验证API密钥格式"""
        return api_key and api_key.startswith("sk-")
```

**架构层次**：
```
BaseProvider → ZhipuProvider → ZhipuAILLM (instances) → ChatZhipuAI (LangChain)
     ↓              ↓                ↓                        ↓
   抽象层        工厂层         智能封装层              LangChain原生SDK

说明：
- BaseProvider: 定义统一接口（共享）
- ZhipuProvider: 工厂实现（llm模块）
- ZhipuAILLM: 模型实例，包含业务逻辑优化（llm模块）
- ChatZhipuAI: LangChain原生模型类（第三方）
```

### 3.3 LLM Instances处理

**当前位置**：`src/llm/langchain/instances/`

**处理方式**：保留，不迁移

**理由**：
- Instances是模型的实现层，对应LangChain的各种ChatModel
- 包含模型特定的业务逻辑和优化（如GLM-4.5的thinking_mode自动启用）
- 这是Provider特定的智能封装层，应该保留在llm模块

**架构层次**：
```
Provider → Instance → LangChain ChatModel
   ↓          ↓              ↓
工厂层    智能封装层      原生SDK

示例：
ZhipuProvider → ZhipuAILLM → ChatZhipuAI
  (工厂)      (业务逻辑)    (LangChain原生)
```

**Instance层的价值**：
- 模型特定的参数优化
- 参数转换和验证
- 最佳实践封装
- 延迟初始化管理

**保留的文件**：
- `src/llm/langchain/instances/zhipu_llm.py` (保留)
- `src/llm/langchain/instances/openai_llm.py` (保留)
- `src/llm/langchain/instances/ollama_llm.py` (保留)

### 3.4 Ollama工具函数迁移

**当前位置**：`src/llm/langchain/providers/ollama/utils.py`

**目标位置**：`src/core/langchain/providers/utils/ollama.py`

**理由**：Ollama工具函数被Agent工厂使用，属于共享工具。

**迁移内容**：
```python
# src/core/langchain/providers/utils/ollama.py

async def list_ollama_models(base_url: str = None, timeout: int = 8) -> List[str]:
    """获取本机可用的Ollama模型列表"""
    # 完整迁移原有实现
    pass

async def get_ollama_models_http(base_url: str, timeout: int = 8) -> List[str]:
    """通过HTTP API获取Ollama模型"""
    pass

def get_ollama_models_cli() -> List[str]:
    """通过CLI获取Ollama模型"""
    pass
```

### 3.5 LLM Adapter依赖解决

**问题**：BaseAgent需要使用LLM Adapter，但不应该直接import llm模块。

**解决方案**：通过依赖注入

**实现方式**：
```python
# AgentManager创建adapter并传入
class AgentManager:
    def create_agent(self, provider, model, **user_params):
        # 1. 创建LLM Adapter（来自llm模块）
        from src.llm.langchain.adapters import ZhipuAdapter
        llm_adapter = ZhipuAdapter(model=model, mode="llm")

        # 2. 创建Agent Adapter（来自agent模块）
        from src.agents.langchain.adapters import ZhipuAgentAdapter
        agent_adapter = ZhipuAgentAdapter(provider=provider, model=model)

        # 3. 传入Agent（依赖注入）
        agent = ZhipuAgent(
            provider=provider,
            model=model,
            llm_adapter=llm_adapter,      # 注入
            agent_adapter=agent_adapter,   # 注入
            **user_params
        )
        return agent

# BaseAgent接收注入的adapter
class BaseAgent(ABC):
    def __init__(self, provider, model, llm_adapter, agent_adapter, **kwargs):
        self.llm_adapter = llm_adapter  # 外部传入，不直接import
        self.agent_adapter = agent_adapter
        # BaseAgent不需要知道adapter来自哪个模块
```

**优势**：
- BaseAgent不直接import llm模块
- 通过接口使用adapter（依赖抽象）
- 易于测试（可以mock adapter）

### 3.6 模块导出设计

#### src/core/langchain/providers/__init__.py

```python
"""
Core Providers Module

提供共享的Provider抽象和配置管理。
"""

from .provider_registry import ProviderRegistry, provider_registry
from .base import BaseProvider
from .utils.ollama import list_ollama_models, get_ollama_models_http

__all__ = [
    # 推荐API（模块级实例）
    'provider_registry',     # 主推荐：全局Registry实例

    # 类（高级用户）
    'ProviderRegistry',      # Registry类（自定义实例）
    'BaseProvider',          # Provider基类（扩展Provider）

    # 工具函数
    'list_ollama_models',    # Ollama模型列表
    'get_ollama_models_http', # Ollama HTTP查询
]
```

#### src/core/langchain/__init__.py

```python
"""
Core LangChain Module

提供LangChain相关的核心共享组件。
"""

from . import providers

__all__ = ['providers']
```

---

## 4. 重构步骤

### 4.1 阶段1：创建共享模块（第1-1.5周）

#### Step 1.1：创建目录结构（第1天）
```bash
mkdir -p src/core/langchain/providers/utils
touch src/core/__init__.py
touch src/core/langchain/__init__.py
touch src/core/langchain/providers/__init__.py
touch src/core/langchain/providers/provider_registry.py
touch src/core/langchain/providers/base.py
touch src/core/langchain/providers/utils/__init__.py
touch src/core/langchain/providers/utils/ollama.py
```

**验证**：
- [ ] 目录结构正确创建
- [ ] 所有__init__.py文件存在

#### Step 1.2：迁移ProviderRegistry（第2天）

**任务**：
1. 复制 `src/llm/langchain/managers/provider_registry.py` 完整内容
2. 粘贴到 `src/core/langchain/providers/provider_registry.py`
3. 移除单例模式（`__new__`方法）
4. 保持`__init__`中的初始化逻辑
5. 创建模块级实例 `provider_registry = ProviderRegistry()`
6. 编写单元测试

**代码模板**：
```python
# src/core/langchain/providers/provider_registry.py
class ProviderRegistry:
    """Provider注册表"""

    def __init__(self):
        """初始化并加载配置"""
        self._providers = {}
        self._load_from_config()

    # ... 复制所有方法

# 全局模块级实例
provider_registry = ProviderRegistry()
```

**验证**：
- [ ] provider_registry可以正确加载配置
- [ ] 可以获取Provider配置
- [ ] 单元测试通过（覆盖率>80%）

#### Step 1.3：迁移BaseProvider（第3天）

**任务**：
1. 复制 `src/llm/langchain/providers/base.py` 完整内容
2. 粘贴到 `src/core/langchain/providers/base.py`
3. 保持所有方法（包括具体实现）
4. 编写单元测试

**验证**：
- [ ] BaseProvider类定义完整
- [ ] 所有方法都存在（抽象+具体）
- [ ] 单元测试通过

#### Step 1.4：迁移Ollama工具（第4天）

**任务**：
1. 复制 `src/llm/langchain/providers/ollama/utils.py` 完整内容
2. 粘贴到 `src/core/langchain/providers/utils/ollama.py`
3. 更新import路径（如果有）
4. 在旧位置添加兼容层（临时）
5. 编写单元测试

**兼容层**：
```python
# src/llm/langchain/providers/ollama/utils.py (保留3个月)
from src.core.langchain.providers.utils.ollama import *
import warnings

warnings.warn(
    "ollama utils已迁移至src.core.langchain.providers.utils.ollama，"
    "当前位置将在v5.0中移除",
    DeprecationWarning,
    stacklevel=2
)
```

**验证**：
- [ ] Ollama工具函数正常工作
- [ ] 兼容层显示警告
- [ ] 单元测试通过

#### Step 1.5：编写导出和文档（第5天）

**任务**：
1. 编写 `src/core/langchain/providers/__init__.py`
2. 编写 `src/core/langchain/__init__.py`
3. 编写模块README
4. 运行完整测试

**验证标准（阶段1整体）**：
- [ ] 共享模块可以独立运行
- [ ] 单元测试覆盖率 > 80%
- [ ] 不影响现有功能
- [ ] 所有import路径正确
- [ ] 文档清晰完整

### 4.2 阶段2：Agent模块适配（第2周）

#### Task 2.1：修改AgentManager

```python
# Before
from src.llm.langchain.managers import llm_manager
self.llm_manager = llm_manager

# After
from src.core.langchain.providers import provider_registry
self.provider_registry = provider_registry
```

**验证**：
- [ ] AgentManager使用provider_registry
- [ ] 不再导入llm_manager
- [ ] 功能无回归

#### Task 2.2：修改FactoryRegistry

```python
# Before
self._llm_manager = LLMManager()

# After
from src.core.langchain.providers import provider_registry
self._provider_registry = provider_registry
```

**注意**：FactoryRegistry在v4.0中会被精简，这里只是临时修改。

**验证**：
- [ ] 不再依赖LLMManager
- [ ] 使用provider_registry验证模型
- [ ] 测试通过

#### Task 2.3：修改OllamaFactory

```python
# Before
from src.llm.langchain.providers.ollama import list_ollama_models

# After
from src.core.langchain.providers.utils import list_ollama_models
```

**验证**：
- [ ] OllamaFactory正常工作
- [ ] 功能无回归

#### Task 2.4：确认BaseAgent依赖注入

**检查项**：
- [ ] BaseAgent通过构造函数接收adapter
- [ ] 不直接import llm模块的adapter
- [ ] AgentManager负责创建和注入adapter

**验证标准（阶段2整体）**：
- [ ] Agent模块不再直接import llm模块
- [ ] 所有Agent测试通过
- [ ] 功能无回归

### 4.3 阶段3：LLM模块适配（第3周）

#### Task 3.1：修改LLMManager

```python
# Before
from src.llm.langchain.managers.provider_registry import provider_registry

# After
from src.core.langchain.providers import provider_registry
```

**验证**：
- [ ] LLMManager使用共享provider_registry
- [ ] 功能无变化

#### Task 3.2：更新Provider实现

```python
# Before
from src.llm.langchain.providers.base import BaseProvider

# After
from src.core.langchain.providers import BaseProvider
```

**需要更新的文件**：
- [ ] src/llm/langchain/providers/zhipu/provider.py
- [ ] src/llm/langchain/providers/openai/provider.py
- [ ] src/llm/langchain/providers/ollama/provider.py

**验证**：
- [ ] 所有Provider继承共享BaseProvider
- [ ] 功能无变化

#### Task 3.3：删除旧文件

**删除的文件**：
- [ ] `src/llm/langchain/managers/provider_registry.py`（已迁移到core）
- [ ] `src/llm/langchain/providers/base.py`（已迁移到core）

**保留的文件**：
- [x] `src/llm/langchain/instances/zhipu_llm.py`（模型实现层）
- [x] `src/llm/langchain/instances/openai_llm.py`（模型实现层）
- [x] `src/llm/langchain/instances/ollama_llm.py`（模型实现层）

**验证**：
- [ ] 旧文件已删除
- [ ] instances目录保留
- [ ] 所有测试通过

**验证标准（阶段3整体）**：
- [ ] LLM模块使用共享配置
- [ ] 所有LLM测试通过
- [ ] 代码行数减少 > 15%

### 4.4 阶段4：清理与优化（第4周）

**任务清单**：
1. 验证旧文件已删除
   - [ ] `src/llm/langchain/managers/provider_registry.py`
   - [ ] `src/llm/langchain/providers/base.py`

2. 更新所有import路径
   - [ ] 搜索并替换 `src.llm.langchain.managers.provider_registry` → `src.core.langchain.providers.provider_registry`
   - [ ] 搜索并替换 `src.llm.langchain.providers.base` → `src.core.langchain.providers.base`

3. 删除临时兼容层（3个月后）
   - [ ] 删除 `src/llm/langchain/providers/ollama/utils.py` 中的兼容代码

4. 更新文档
   - [ ] 更新架构文档
   - [ ] 更新API文档
   - [ ] 更新导入指南

5. 运行完整测试套件
   - [ ] 单元测试（所有模块）
   - [ ] 集成测试
   - [ ] 回归测试
   - [ ] 性能测试

**验证标准**：
- [ ] 所有测试通过
- [ ] 文档更新完成
- [ ] 无遗留的旧代码
- [ ] 性能无下降

---

## 5. 依赖关系对比

### 5.1 重构前
```
[AgentManager]
    ↓ (直接依赖)
[LLMManager]
    ↓
[ProviderRegistry]
```

**问题**：
- AgentManager依赖LLMManager的实现细节
- 修改LLMManager会影响Agent
- 无法独立测试

### 5.2 重构后
```
[AgentManager]         [LLMManager]
    ↓                      ↓
    └───> [ProviderRegistry] <───┘
         (共享抽象层 - core模块)
```

**优势**：
- 两个模块通过抽象解耦
- 可以独立开发和测试
- 修改一方不影响另一方

---

## 6. 代码示例

### 6.1 AgentManager重构前后对比

#### 重构前
```python
# src/agents/langchain/managers/agent_manager.py
class AgentManager:
    def __init__(self):
        from src.llm.langchain.managers import llm_manager
        self.llm_manager = llm_manager  # 直接依赖LLM模块

    def _get_provider_config(self, provider: str):
        providers = self.llm_manager.get_available_providers()
        for p in providers:
            if p["provider"].upper() == provider:
                return p
        raise ValueError(f"Provider {provider} not found")
```

#### 重构后
```python
# src/agents/langchain/managers/agent_manager.py
class AgentManager:
    def __init__(self):
        from src.core.langchain.providers import provider_registry
        self.provider_registry = provider_registry  # 依赖共享抽象

    def _get_provider_config(self, provider: str):
        config = self.provider_registry.get_provider_config(provider)
        if not config:
            raise ValueError(f"Provider {provider} not found")
        return config
```

### 6.2 FactoryRegistry重构前后对比

#### 重构前
```python
# src/agents/langchain/factories/registry.py
class FactoryRegistry:
    def _get_llm_manager(self):
        from src.llm.langchain.managers import LLMManager
        self._llm_manager = LLMManager()  # 依赖LLM模块
        return self._llm_manager

    async def create_agent(self, provider, model, **kwargs):
        llm_manager = self._get_llm_manager()
        llm_manager.get_llm_info(provider_enum, model)
```

#### 重构后
```python
# src/agents/langchain/factories/registry.py
class FactoryRegistry:
    def __init__(self):
        from src.core.langchain.providers import provider_registry
        self._provider_registry = provider_registry  # 依赖共享抽象

    async def create_agent(self, provider, model, **kwargs):
        # 使用共享配置服务验证
        if not self._provider_registry.validate_model(provider, model):
            raise ValueError(f"Invalid model: {provider}/{model}")
```

### 6.3 BaseAgent依赖注入示例

#### AgentManager注入adapter
```python
# src/agents/langchain/managers/agent_manager.py
class AgentManager:
    def create_agent(self, provider, model, **user_params):
        # 1. 创建LLM Adapter（来自llm模块，但通过依赖注入）
        from src.llm.langchain.adapters import ZhipuAdapter
        llm_adapter = ZhipuAdapter(model=model, mode="llm")

        # 2. 创建Agent Adapter（来自agent模块）
        from src.agents.langchain.adapters import ZhipuAgentAdapter
        agent_adapter = ZhipuAgentAdapter(provider=provider, model=model)

        # 3. 创建Agent（注入adapters）
        agent = ZhipuAgent(
            provider=provider,
            model=model,
            llm_adapter=llm_adapter,      # 注入
            agent_adapter=agent_adapter,   # 注入
            **user_params
        )
        return agent
```

#### BaseAgent接收注入
```python
# src/agents/langchain/instances/base_agent.py
class BaseAgent(ABC):
    def __init__(
        self,
        provider: str,
        model: str,
        llm_adapter,        # 外部注入，不需要知道来自哪里
        agent_adapter,      # 外部注入
        **user_params
    ):
        self.provider = provider
        self.model = model
        self.llm_adapter = llm_adapter        # 接收注入
        self.agent_adapter = agent_adapter    # 接收注入

        # 使用adapter，但不需要import llm模块
        agent_params = agent_adapter.get_agent_params(**user_params)
```

---

## 7. 测试策略

### 7.1 单元测试

#### 共享模块测试
```python
# tests/core/providers/test_provider_registry.py
def test_provider_registry_instance():
    """测试模块级实例"""
    from src.core.langchain.providers import provider_registry

    # 验证是ProviderRegistry实例
    assert isinstance(provider_registry, ProviderRegistry)

    # 验证可以获取配置
    config = provider_registry.get_provider_config("zhipu")
    assert config is not None
    assert config["name"] == "智谱AI"

def test_provider_registry_validate():
    """测试模型验证"""
    from src.core.langchain.providers import provider_registry

    assert provider_registry.validate_model("zhipu", "glm-4-plus") == True
    assert provider_registry.validate_model("zhipu", "invalid-model") == False

def test_provider_registry_replaceable():
    """测试可替换性（用于测试）"""
    import src.core.langchain.providers.provider_registry as registry_module

    # 保存原实例
    original = registry_module.provider_registry

    # 替换为mock
    mock_registry = MockRegistry()
    registry_module.provider_registry = mock_registry

    # 验证替换成功
    from src.core.langchain.providers import provider_registry
    assert provider_registry is mock_registry

    # 恢复
    registry_module.provider_registry = original
```

#### Agent模块测试
```python
# tests/agents/test_agent_manager.py
def test_agent_manager_no_llm_dependency():
    """确保AgentManager不依赖llm_manager"""
    # 不应该导入llm.managers
    with pytest.raises(ImportError):
        # AgentManager内部不应该有这个import
        from src.agents.langchain.managers.agent_manager import llm_manager
```

### 7.2 集成测试

```python
# tests/integration/test_dependency_inversion.py
async def test_agent_and_llm_independent():
    """测试Agent和LLM模块可以独立工作"""

    # 测试Agent模块独立工作
    from src.agents.langchain.managers import agent_manager
    config = agent_manager._get_provider_config("zhipu")
    assert config is not None

    # 测试LLM模块独立工作
    from src.llm.langchain.managers import create_llm
    llm = create_llm("zhipu", "glm-4-plus")
    assert llm is not None

    # 测试共享模块
    from src.core.langchain.providers import provider_registry
    assert provider_registry.validate_model("zhipu", "glm-4-plus")
```

---

## 8. 风险评估与缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 导入路径大量变更 | 高 | 高 | 提供兼容层，分阶段迁移，自动化替换工具 |
| 配置加载逻辑变化 | 中 | 低 | 充分测试，保持配置格式不变 |
| Adapter依赖注入失败 | 高 | 中 | 详细测试，提供明确示例 |
| Ollama工具迁移问题 | 低 | 低 | 保留兼容层3个月 |
| 测试覆盖不足 | 中 | 中 | 阶段1要求覆盖率>80% |

---

## 9. 向后兼容策略

### 9.1 兼容层设计

```python
# src/llm/langchain/managers/provider_registry.py (保留3个月)
from src.core.langchain.providers import ProviderRegistry, provider_registry
import warnings

warnings.warn(
    "ProviderRegistry已迁移至src.core.langchain.providers，"
    "当前位置将在v5.0中移除",
    DeprecationWarning,
    stacklevel=2
)

# 保持旧导入可用
__all__ = ['ProviderRegistry', 'provider_registry']
```

### 9.2 废弃时间表

| 版本 | 时间 | 操作 | 说明 |
|------|------|------|------|
| v4.0 | 立即 | 添加DeprecationWarning | 旧路径可用但警告 |
| v4.5 | 3个月后 | 升级为FutureWarning | 更明显的警告 |
| v5.0 | 6个月后 | 移除兼容层 | 完全移除旧路径 |

---

## 10. 收益分析

### 10.1 量化指标

| 指标 | 当前 | 优化后 | 改善 |
|------|------|--------|------|
| 模块间直接依赖 | 5个 | 0个 | -100% |
| 配置管理重复代码 | 是 | 否 | 减少约200行 |
| 模块独立测试能力 | 困难 | 简单 | 测试时间-50% |
| 代码耦合度 | 高 | 低 | -70% |

### 10.2 定性收益

**架构**：
- Agent和LLM模块完全解耦
- 配置管理统一，职责清晰
- 符合依赖倒置原则

**开发**：
- 团队可并行开发
- 减少代码冲突
- 新增Provider更简单

**测试**：
- 模块可独立测试
- Mock依赖更容易
- 测试覆盖率提升

---

## 11. 总结

### 11.1 核心改进
1. 创建 `src/core/langchain/providers/` 共享模块
2. Agent和LLM都依赖共享抽象，不再相互依赖
3. 配置管理统一（`provider_registry`）
4. BaseProvider完整迁移，不是抽象提取
5. 使用模块级实例，不使用单例模式
6. LLM Adapter通过依赖注入解决
7. Instances保留在llm模块（模型实现层）

### 11.2 关键决策
- ✅ BaseProvider完整迁移（包括具体方法）
- ✅ 移除单例模式，使用模块级实例
- ✅ 统一命名为`provider_registry`
- ✅ LLM Adapter通过依赖注入
- ✅ 移除ModelValidator组件
- ✅ Instances保留在llm模块

### 11.3 预期收益
- 模块独立性提升 > 70%
- 代码行数减少约15%
- 开发效率提升 > 30%
- 测试覆盖率提升

### 11.4 实施周期
4-4.5周（分阶段实施，降低风险）

---

## 附录A：文件操作清单

| 操作 | 源文件 | 目标文件 |
|------|--------|----------|
| 完整迁移 | `src/llm/langchain/managers/provider_registry.py` | `src/core/langchain/providers/provider_registry.py` |
| 完整迁移 | `src/llm/langchain/providers/base.py` | `src/core/langchain/providers/base.py` |
| 完整迁移 | `src/llm/langchain/providers/ollama/utils.py` | `src/core/langchain/providers/utils/ollama.py` |
| 保留 | `src/llm/langchain/instances/*.py` | 不迁移（模型实现层） |
| 删除 | `src/llm/langchain/managers/provider_registry.py` | 阶段3删除 |
| 删除 | `src/llm/langchain/providers/base.py` | 阶段3删除 |

## 附录B：import路径映射

| 旧路径 | 新路径 | 废弃版本 |
|--------|--------|---------|
| `src.llm.langchain.managers.provider_registry.provider_registry` | `src.core.langchain.providers.provider_registry` | v5.0 |
| `src.llm.langchain.managers.provider_registry.ProviderRegistry` | `src.core.langchain.providers.ProviderRegistry` | v5.0 |
| `src.llm.langchain.providers.base.BaseProvider` | `src.core.langchain.providers.BaseProvider` | v5.0 |
| `src.llm.langchain.providers.ollama.utils` | `src.core.langchain.providers.utils.ollama` | v5.0 |

---

**文档版本**: v1.2
**最后更新**: 2025-10-12
**下一步**: 参考 `agents_api_unification_v4.md` 进行API统一重构

**v1.2更新说明**：
- ✅ BaseProvider改为完整迁移（非抽象提取）
- ✅ 移除单例模式，使用模块级实例
- ✅ 统一命名为`provider_registry`
- ✅ 明确LLM Adapter通过依赖注入解决
- ✅ 移除ModelValidator组件，直接用Registry
- ✅ 补充instances说明（模型实现层，保留）
- ✅ 细化测试策略（包括可替换性测试）
- ✅ 更新代码示例和验证清单
