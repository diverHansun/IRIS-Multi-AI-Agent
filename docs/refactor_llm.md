# LLM模块架构重构方案

## 📋 一、现有问题分析

### 1.1 架构问题

#### **问题1：功能重复严重**

- **Provider vs Adapter职责重叠**
  - `Provider.create_llm()` 处理参数并创建LLM
  - `Adapter.get_llm_params()` 也处理相同参数
  - 结果：参数被处理2-3次，逻辑重复

- **配置读取重复**
  - `ProviderRegistry` 加载 `providers.json`
  - `Adapter` 又重新读取相同文件
  - 结果：配置被读取2次，浪费资源

- **Instance也处理参数**
  - `OllamaLLM.__init__()` 调用 `_get_model_config()` 读配置
  - 内部又设置默认值：`self.temperature = temperature if temperature is not None else recommended_params.get("temperature", 0.1)`
  - 结果：参数优先级混乱

#### **问题2：参数传递链路混乱**

**当前LLM模块调用链（有问题）：**

```
用户 → llm_manager.create_llm(**kwargs)
    ↓ (绕过Adapter)
    → Provider.create_llm(**kwargs)
    ↓ (硬编码默认值)
    → Instance(**kwargs)
    ↓ (又读配置)
    → SDK
```

**当前Agent模块调用链（正常）：**

```
用户 → agent_manager.create_agent()
    ↓
    → LLMAdapter.get_llm_params() ✅
    ↓
    → llm_manager.create_llm(**llm_params)
    ↓
    → Provider → Instance → SDK
```

**发现：**

- ✅ Agent模块使用了Adapter，参数正确
- ❌ LLM模块直接调用时绕过了Adapter
- ❌ `mode_overrides` 配置完全不生效

#### **问题3：创建方式不一致**

| Provider | 创建方式 | 是否使用Adapter | 是否使用Instance包装 |

|---------|---------|---------------|-------------------|

| OpenAI  | 直接创建`ChatOpenAI` | ❌ | ❌ |

| Ollama  | 使用`OllamaLLM`包装 | ❌ | ✅ |

| Zhipu   | 使用`ZhipuAILLM`包装 | ❌ | ✅ |

#### **问题4：Provider层冗余**

- Agent模块绕过Provider，直接调用`llm_manager`
- Provider实际只是转发调用，没有实质作用
- 保留Provider增加维护成本

---

## 🎯 二、重构方案设计

### 2.1 核心思想

**分层解耦 + 职责明确 + 消除冗余**

```
Config (providers.json)
    ↓
ProviderRegistry (统一配置入口) ← 只提供配置查询
    ↓
Manager (控制中心) ← 协调流程
    ├→ Adapter (参数处理) ← 依赖注入ProviderRegistry
    └→ Instance (SDK封装) ← 只接收参数，不读配置
    
废弃：
    ❌ src/llm/langchain/providers/*/provider.py
    ❌ src/agents/langchain/providers (已废弃)
```

### 2.2 各层职责定义

#### **层级1：ProviderRegistry (src/core/langchain/providers)**

**职责：**

- ✅ 加载和缓存 `providers.json` 配置
- ✅ 提供配置查询接口
- ❌ 不创建LLM/Agent实例
- ❌ 不处理参数逻辑

**保留方法：**

```python
class ProviderRegistry:
    def get_provider_config(provider: str) -> Dict
    def get_model_config(provider: str, model: str) -> Dict
    def get_model_info(provider: str, model: str) -> Dict
    def list_providers() -> Dict
    def validate_model(provider: str, model: str) -> bool
    def reload_config() -> bool
```

**移除方法：**

```python
❌ def get_provider_instance()  # 删除
```

---

#### **层级2：Manager (LLMManager / AgentManager)**

**职责：**

- ✅ 协调整个创建流程
- ✅ 管理API密钥
- ✅ 创建Adapter（依赖注入ProviderRegistry）
- ✅ 选择Instance类型
- ❌ 不处理参数逻辑

**LLMManager重构：**

```python
class LLMManager:
    def __init__(self):
        self.provider_registry = provider_registry
        self._api_keys = {}
    
    def create_llm(self, provider: str, model: str = None, **user_kwargs):
        """创建LLM实例"""
        provider = provider.upper()
        
        # 1. 获取配置
        provider_config = self.provider_registry.get_provider_config(provider)
        if not model:
            model = provider_config.get("default_model")
        
        # 2. 创建Adapter（依赖注入）
        adapter = self._create_adapter(provider, model)
        
        # 3. 获取处理后的参数
        llm_params = adapter.get_llm_params(**user_kwargs)
        
        # 4. 选择Instance并创建
        return self._create_instance(provider, model, llm_params)
    
    def _create_adapter(self, provider: str, model: str):
        """创建Adapter（依赖注入ProviderRegistry）"""
        adapter_map = {
            "ZHIPU": ZhipuAdapter,
            "OPENAI": OpenAIAdapter,
            "OLLAMA": OllamaAdapter,
        }
        adapter_class = adapter_map.get(provider)
        
        # 依赖注入ProviderRegistry
        return adapter_class(
            provider=provider,
            model=model,
            provider_registry=self.provider_registry
        )
    
    def _create_instance(self, provider: str, model: str, llm_params: Dict):
        """选择Instance（if-else方式）"""
        if provider == "ZHIPU":
            from src.llm.langchain.instances import ZhipuAILLM
            return ZhipuAILLM(**llm_params).create_llm()
        
        elif provider == "OPENAI":
            from src.llm.langchain.instances import OpenAILLM
            return OpenAILLM(**llm_params).create_llm()
        
        elif provider == "OLLAMA":
            from src.llm.langchain.instances import OllamaLLM
            return OllamaLLM(**llm_params).create_llm()
        
        else:
            raise ValueError(f"Unsupported provider: {provider}")
```

---

#### **层级3：Adapter (参数处理层)**

**职责：**

- ✅ 通过ProviderRegistry获取配置（依赖注入）
- ✅ 合并参数：mode_defaults + mode_overrides + user_params
- ✅ 处理特殊逻辑（temperature_fixed等）
- ❌ 不读取JSON文件
- ❌ 不创建LLM实例

**LLMAdapter重构：**

```python
class LLMAdapter(ABC):
    def __init__(self, provider: str, model: str, provider_registry):
        """依赖注入ProviderRegistry"""
        self.provider = provider
        self.model = model
        self.provider_registry = provider_registry
        
        # 从ProviderRegistry获取配置
        self._provider_config = provider_registry.get_provider_config(provider)
        self._model_config = provider_registry.get_model_config(provider, model)
    
    def get_llm_params(self, **user_kwargs) -> Dict[str, Any]:
        """获取LLM参数（三层优先级）"""
        # 1. mode_defaults.llm
        params = self._provider_config.get("mode_defaults", {}).get("llm", {}).copy()
        
        # 2. mode_overrides.llm
        overrides = self._model_config.get("mode_overrides", {}).get("llm", {})
        params.update(overrides)
        
        # 3. 用户参数（最高优先级）
        for key, value in user_kwargs.items():
            if value is not None:
                params[key] = value
        
        # 4. 子类特殊逻辑
        params = self._apply_special_logic(params, user_kwargs)
        
        return params
    
    @abstractmethod
    def _apply_special_logic(self, params: Dict, user_kwargs: Dict) -> Dict:
        """子类实现特殊逻辑"""
        pass
```

**AgentAdapter同样改进：**

```python
class AgentAdapter(ABC):
    def __init__(self, provider: str, model: str, provider_registry):
        """依赖注入ProviderRegistry"""
        self.provider = provider
        self.model = model
        self.provider_registry = provider_registry
        
        # 从ProviderRegistry获取配置
        self._provider_config = provider_registry.get_provider_config(provider)
        self._model_config = provider_registry.get_model_config(provider, model)
    
    def get_agent_params(self, **user_params) -> Dict[str, Any]:
        """获取Agent参数（三层优先级）"""
        # 1. mode_defaults.agent
        params = self._provider_config.get("mode_defaults", {}).get("agent", {}).copy()
        
        # 2. mode_overrides.agent
        overrides = self._model_config.get("mode_overrides", {}).get("agent", {})
        params.update(overrides)
        
        # 3. 用户参数
        for key, value in user_params.items():
            if value is not None:
                params[key] = value
        
        return params
```

---

#### **层级4：Instance (SDK封装层)**

**职责：**

- ✅ 封装SDK调用
- ✅ 提供特定功能（健康检查、初始化等）
- ❌ 不读取配置
- ❌ 不处理参数默认值

**Instance重构：**

```python
class OllamaLLM:
    def __init__(self, model: str, base_url: str, temperature: float, **kwargs):
        """直接接收处理好的参数"""
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.kwargs = kwargs
        
        # ❌ 移除：不再调用 _get_model_config()
        # ❌ 移除：不再设置参数默认值
    
    async def health_check(self) -> bool:
        """保留：特定功能"""
        ...
    
    def create_llm(self) -> BaseChatModel:
        """创建SDK实例"""
        return ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=self.temperature,
            **self.kwargs
        )
```

---

### 2.3 完整调用流程

#### **LLM模块调用流程（重构后）：**

```
用户：llm = llm_manager.create_llm(provider="zhipu", model="glm-4.5", temperature=0.2)
    ↓
LLMManager.create_llm()
    ├→ 1. 查询配置
    │   └→ ProviderRegistry.get_provider_config("ZHIPU")
    │   └→ ProviderRegistry.get_model_config("ZHIPU", "glm-4.5")
    │
    ├→ 2. 创建Adapter（依赖注入）
    │   └→ ZhipuAdapter(provider, model, provider_registry)
    │
    ├→ 3. 获取参数
    │   └→ adapter.get_llm_params(temperature=0.2)
    │       └→ mode_defaults.llm: {temperature: 0.1, streaming: True}
    │       └→ mode_overrides.llm: {thinking_mode: True}
    │       └→ user_kwargs: {temperature: 0.2}
    │       └→ 返回: {temperature: 0.2, streaming: True, thinking_mode: True}
    │
    └→ 4. 创建Instance
        └→ ZhipuAILLM(temperature=0.2, streaming=True, thinking_mode=True, ...)
            └→ ChatZhipuAI(...)
```

#### **Agent模块调用流程（同步改进）：**

```
用户：agent = await agent_manager.create_agent(provider="zhipu", model="glm-4.5")
    ↓
AgentManager.create_agent()
    ├→ 1. 创建LLM Adapter（依赖注入）
    │   └→ ZhipuAdapter(provider, model, provider_registry)
    │
    ├→ 2. 创建Agent Adapter（依赖注入）
    │   └→ ZhipuAgentAdapter(provider, model, provider_registry)
    │
    └→ 3. 传递给Factory
        └→ BaseAgent.initialize()
            ├→ llm_params = llm_adapter.get_llm_params()
            ├→ llm_manager.create_llm(**llm_params)
            └→ agent_params = agent_adapter.get_agent_params()
                └→ create_agent_executor(**agent_params)
```

---

## 🔧 三、实施步骤

### 阶段1：修改ProviderRegistry

- [ ] 移除 `get_provider_instance()` 方法
- [ ] 确保所有配置查询方法稳定

### 阶段2：重构Adapter层

- [ ] 修改 `LLMAdapter.__init__()`，接收 `provider_registry` 参数
- [ ] 移除 `load_config()` 方法中的JSON读取逻辑
- [ ] 改用 `provider_registry.get_provider_config()` 获取配置
- [ ] 修改 `AgentAdapter.__init__()`，同样改为依赖注入
- [ ] 更新所有Adapter子类（Zhipu/OpenAI/Ollama）

### 阶段3：重构LLMManager

- [ ] 添加 `_create_adapter()` 方法（依赖注入）
- [ ] 添加 `_create_instance()` 方法（if-else选择）
- [ ] 重构 `create_llm()` 方法，使用Adapter
- [ ] 移除对Provider的依赖

### 阶段4：简化Instance层

- [ ] 移除 `OllamaLLM._get_model_config()` 方法
- [ ] 移除Instance内部的配置读取逻辑
- [ ] 移除参数默认值设置，直接使用传入参数
- [ ] 同步修改 `ZhipuAILLM` 和 `OpenAILLM`

### 阶段5：删除Provider层

- [ ] 删除 `src/llm/langchain/providers/zhipu/provider.py`
- [ ] 删除 `src/llm/langchain/providers/openai/provider.py`
- [ ] 删除 `src/llm/langchain/providers/ollama/provider.py`
- [ ] 清理相关imports

### 阶段6：更新AgentManager

- [ ] 修改 `_create_llm_adapter()` 传入 `provider_registry`
- [ ] 修改 `_create_agent_adapter()` 传入 `provider_registry`

### 阶段7：测试验证

- [ ] 测试LLM直接创建流程
- [ ] 测试Agent创建流程（包含LLM创建）
- [ ] 验证配置正确生效（mode_overrides）
- [ ] 验证参数优先级
- [ ] 验证特殊逻辑（temperature_fixed等）

---

## 📊 四、重构前后对比

| 维度 | 重构前 | 重构后 |

|-----|-------|--------|

| **配置读取** | 重复2次（Registry + Adapter） | 只读1次（Registry） |

| **参数处理** | 处理2-3次（Adapter + Provider + Instance） | 只处理1次（Adapter） |

| **架构层级** | 6层（Config → Registry → Manager → Provider → Instance → SDK） | 4层（Config → Registry → Manager → Adapter → Instance → SDK） |

| **参数优先级** | 混乱（多处设置默认值） | 清晰（user > overrides > defaults） |

| **代码重复** | 严重（Provider和Adapter功能重叠） | 最小化（职责单一） |

| **维护成本** | 高（多层冗余） | 低（职责明确） |

---

## ✅ 五、预期收益

1. **架构统一**：LLM和Agent模块使用相同的分层架构
2. **性能提升**：配置只读取1次，参数只处理1次
3. **职责清晰**：每层只做一件事，易于理解和维护
4. **配置生效**：mode_overrides正确应用，参数优先级明确
5. **减少冗余**：删除Provider层，消除重复代码
6. **易于扩展**：新增Provider只需添加Adapter和Instance