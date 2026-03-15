# 代码变更清单

## 1. 概述

本文档逐文件列出 Provider Registry 动态化重构所需的代码修改，
按优先级排序，并标注每项修改的风险级别。

## 2. 变更一览

| 文件 | 变更类型 | 优先级 | 风险 | 说明 |
|------|---------|--------|------|------|
| `config/llm/models/providers.json` | 修改 | P0 | 低 | 新增 `adapter` 字段，key 改小写，新增 tongyi |
| `config/agents/basic/models/providers.json` | 修改 | P0 | 低 | 新增 `adapter` 字段，新增 tongyi |
| `src/core/providers/llm_provider_registry.py` | 修改 | P0 | 中 | key 统一小写 |
| `src/llm/adapters/base.py` | 修改 | P0 | 中 | `self.provider` 改为 lowercase |
| `src/llm/adapters/zhipu_adapter.py` | 修改 | P0 | 低 | 接受 `provider_name` 参数 |
| `src/llm/adapters/openai_adapter.py` | 修改 | P0 | 低 | 接受 `provider_name` 参数 |
| `src/llm/adapters/ollama_adapter.py` | 修改 | P0 | 低 | 接受 `provider_name` 参数 |
| `src/llm/managers/llm_manager.py` | 修改 | P0 | 高 | 移除 Enum，config-driven adapter |
| `src/llm/managers/__init__.py` | 修改 | P0 | 低 | 移除 LLMProvider 导出 |
| `src/llm/__init__.py` | 修改 | P0 | 低 | 移除 LLMProvider 导出 |
| `src/agents/basicagents/managers/agent_manager.py` | 修改 | P0 | 中 | config-driven adapter |
| `src/core/config/settings.py` | 修改 | P1 | 低 | `_validate_config()` 动态化 |

## 3. 配置文件修改

### 3.1 config/llm/models/providers.json

**变更内容**：

1. `schema_version` 从 `"1.0"` 升级为 `"2.0"`
2. 所有 provider key 从大写改为小写
3. 每个 provider 新增 `"adapter"` 字段
4. 新增 `tongyi` provider（`adapter: "openai"`）

**变更范围**：整个文件重写

**详见**：`03-config-changes.md` 第 2.2 节

### 3.2 config/agents/basic/models/providers.json

**变更内容**：

1. `schema_version` 从 `"1.0"` 升级为 `"2.0"`
2. 每个 provider 新增 `"adapter"` 字段
3. 新增 `tongyi` provider（`adapter: "openai"`，含 agent 参数）

**变更范围**：整个文件重写

**详见**：`03-config-changes.md` 第 3 节；`docs/setup/06-config-changes.md` 第 7 节

**注意**：此文件的 tongyi 配置在 `docs/setup/06-config-changes.md` 中也有定义。
两者内容一致，本文档额外定义了 `adapter` 字段。

## 4. Registry 层修改

### 4.1 src/core/providers/llm_provider_registry.py

**变更项**：

| 方法/属性 | 变更 |
|----------|------|
| `_load_from_config()` | 加载后 key 统一转小写 |
| `get_provider_config()` | 移除 `.upper()` 转换，改为 `.lower()` |
| `get_model_config()` | 同上 |
| `get_llm_config()` | 移除 `provider.upper()` 调用 |
| `get_api_key()` | 同上 |
| `get_model_info()` | 同上 |
| `validate_model()` | 同上 |

**核心变更代码**：

```python
# _load_from_config()
def _load_from_config(self) -> None:
    self._providers = {}
    config_data = self._config_loader.load_shared_json("llm/providers.json") or {}
    if not config_data and self._custom_config_path:
        config_data = _load_json_file(self._custom_config_path) or {}
    providers_raw = config_data.get("providers", {})
    # Normalise all keys to lowercase
    self._providers = {k.lower(): v for k, v in providers_raw.items()}
    logger.info("Loaded %d LLM provider configurations", len(self._providers))

# get_provider_config()
def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
    return self._providers.get(provider.lower())

# get_llm_config() -- 关键行变更
def get_llm_config(self, provider: str, model: Optional[str] = None, **user_params):
    provider_key = provider.lower()  # was provider.upper()
    provider_config = self.get_provider_config(provider_key)
    ...
```

**风险评估**：中等。key 大小写变更影响所有通过 `LLMProviderRegistry` 查询的代码。
但由于 `get_provider_config()` 内部做了 `.lower()` 处理，
调用方传入任何大小写都能正确查找。

### 4.2 src/core/providers/basicagents_provider_registry.py

**无需修改**。已使用 lowercase key，且 `adapter` 字段通过 `get_provider_config()`
返回的 dict 自然可见。

## 5. Adapter 层修改

### 5.1 src/llm/adapters/base.py

**变更项**：

| 位置 | 变更 |
|------|------|
| `__init__` line 38 | `self.provider = provider.upper()` 改为 `self.provider = provider.lower()` |

改造后 `self.provider` 存储 lowercase 名称（如 `"tongyi"`），
与 registry 的 key 格式一致。

### 5.2 src/llm/adapters/zhipu_adapter.py

**变更项**：

```python
# 变更前
class ZhipuAdapter(LLMAdapter):
    def __init__(self, model, provider_registry=None, mode="llm"):
        super().__init__(provider="ZHIPU", model=model, ...)

# 变更后
class ZhipuAdapter(LLMAdapter):
    def __init__(self, model, provider_registry=None, mode="llm",
                 provider_name: str = "zhipu"):
        super().__init__(provider=provider_name, model=model, ...)
```

新增 `provider_name` 参数（默认 `"zhipu"`），允许 manager 传入实际 provider 名。
默认值保证独立使用时的向后兼容。

### 5.3 src/llm/adapters/openai_adapter.py

同 5.2 模式，默认 `provider_name="openai"`。
当 tongyi 使用时，manager 传入 `provider_name="tongyi"`，
adapter 内部从 registry 读取 tongyi 自己的配置（base_url、models 等）。

### 5.4 src/llm/adapters/ollama_adapter.py

同 5.2 模式，默认 `provider_name="ollama"`。

**详见**：`02-adapter-system.md` 第 2.5 节

### 5.5 src/llm/managers/__init__.py

**变更**：移除 `LLMProvider` 的导入和导出。

```python
# 变更前
from .llm_manager import (
    LLMManager,
    LLMProvider,     # 移除
    llm_manager,
    ...
)

__all__ = [
    "LLMManager",
    "LLMProvider",   # 移除
    ...
]
```

### 5.6 src/llm/__init__.py

**变更**：同 5.5，移除 `LLMProvider` 的导入和导出。

```python
# 变更前
from .managers import (
    LLMManager,
    LLMProvider,     # 移除
    get_llm_info,
)

__all__ = [
    ...
    "LLMProvider",   # 移除
    ...
]
```

## 6. Manager 层修改

### 6.1 src/llm/managers/llm_manager.py

这是本次重构变更最大的文件。

**移除**：

```python
# 整个 LLMProvider Enum 类删除
class LLMProvider(Enum):
    ZHIPU = "zhipu"
    OPENAI = "openai"
    OLLAMA = "ollama"
```

**新增**：

```python
# 文件顶部，import 之后
ADAPTER_REGISTRY = {
    "zhipu": (ZhipuAdapter, ZhipuAILLM),
    "openai": (OpenAIAdapter, OpenAILLM),
    "ollama": (OllamaAdapter, OllamaLLM),
}
```

**方法级变更**：

| 方法 | 变更描述 |
|------|---------|
| `__init__()` | 移除 `_adapter_map`/`_instance_map`；`_api_keys` 类型改为 `Dict[str, str]` |
| `_load_api_keys()` | 遍历 registry 动态加载（详见 `02-adapter-system.md` 5.2） |
| `_normalise_provider()` | 返回 `str`，移除 Enum 转换（详见 `02-adapter-system.md` 3.2） |
| `create_llm()` | 调用链适配新签名 |
| `_create_adapter()` | 从 config 读取 adapter 类型（详见 `02-adapter-system.md` 3.3） |
| `_create_instance()` | 同上（详见 `02-adapter-system.md` 3.4） |
| `_prepare_instance_params()` | 用 `adapter_type` 替代 `provider_enum` 判断（详见 `02-adapter-system.md` 6） |
| `_resolve_api_key()` | 基于 provider name 查找（详见 `02-adapter-system.md` 5.3） |
| `_provider_available()` | 基于 `api_key_env` 判断（详见 `02-adapter-system.md` 5.4） |
| `set_api_key()` | 移除 Enum 判断（详见 `02-adapter-system.md` 5.6） |

**create_llm() 改造后流程**：

```python
async def create_llm(self, provider: str, model=None, mode="llm", **kwargs):
    provider_name = self._normalise_provider(provider)
    provider_config = self._get_provider_config(provider_name)
    adapter_type = self._resolve_adapter_type(provider_name, provider_config)
    model_name = self._resolve_model_name(provider_config, model)

    user_params = kwargs.copy()
    explicit_api_key = user_params.pop("api_key", None)

    adapter = self._create_adapter(provider_name, model_name, mode)

    # Ollama auto-detect
    if adapter_type == "ollama" and model_name == "auto":
        base_url = user_params.get("base_url") or settings.ollama_base_url
        model_name = await adapter.resolve_auto_model(base_url)

    llm_params = adapter.get_llm_params(**user_params)
    llm_params["model"] = model_name

    final_params = self._prepare_instance_params(
        provider_name=provider_name,
        adapter_type=adapter_type,
        provider_config=provider_config,
        adapter=adapter,
        adapter_params=llm_params,
        explicit_api_key=explicit_api_key,
        user_params=user_params,
    )

    instance = self._create_instance(provider_name, final_params)
    llm = instance.create_llm()
    return llm
```

**_resolve_adapter_type 新增方法**：

```python
def _resolve_adapter_type(self, provider_name: str, config: Dict[str, Any]) -> str:
    """Get adapter type from config, with fallback for legacy configs."""
    adapter = config.get("adapter")
    if adapter:
        return adapter
    # Fallback for old configs without adapter field
    known = {"zhipu": "zhipu", "ollama": "ollama"}
    return known.get(provider_name, "openai")
```

**风险评估**：高。这是调用链最核心的文件，所有 LLM 创建都经过此处。
需要充分的单元测试和集成测试覆盖。

### 6.2 src/agents/basicagents/managers/agent_manager.py

**新增**（模块级函数，保持现有延迟导入风格）：

```python
def _get_agent_adapter_class(adapter_type: str):
    """Lazy-load agent adapter class by adapter type."""
    if adapter_type == "zhipu":
        from src.agents.basicagents.adapters.zhipu_agent_adapter import ZhipuAgentAdapter
        return ZhipuAgentAdapter
    elif adapter_type == "openai":
        from src.agents.basicagents.adapters.openai_agent_adapter import OpenAIAgentAdapter
        return OpenAIAgentAdapter
    return None
```

**方法级变更**：

| 方法 | 变更描述 |
|------|---------|
| `_create_adapter()` | 从 registry 读取 adapter 类型，通过 `_get_agent_adapter_class()` 获取类 |

**改造后代码**（详见 `02-adapter-system.md` 3.5）。

**实施依赖**：此变更依赖 `config/agents/basic/models/providers.json` 已新增
`adapter` 字段。JSON 配置变更和代码变更必须在同一个 commit 中。

**风险评估**：中等。BasicAgent 的调用链相对简单。

**限制**：BasicAgent 只支持 `"zhipu"` 和 `"openai"` 两种 adapter 类型。
Ollama 不支持 BasicAgent 模式。如果用户配置了 `adapter: "ollama"` 的 provider
并尝试用于 BasicAgent，会抛出 `ProviderNotFoundError`。

## 7. Settings 层修改

### 7.1 src/core/config/settings.py

**变更项**：

| 函数/方法 | 变更描述 |
|----------|---------|
| `_validate_config()` | 改为基于 registry 动态检查可用 provider |

**变更前**（`settings.py:140-176` 实际代码）：

```python
def _validate_config() -> None:
    errors = []
    has_zhipu = settings.has_zhipu()
    has_openai = settings.has_openai()
    has_anthropic = settings.has_anthropic()
    has_ollama = True

    if not has_zhipu and not has_openai and not has_anthropic:
        errors.append(
            "At least one LLM API key must be configured "
            "(ZHIPU_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)"
        )

    logger.debug(
        "LLM Providers: zhipu=%s, openai=%s, anthropic=%s, ollama=%s",
        has_zhipu, has_openai, has_anthropic, has_ollama,
    )
    logger.debug(
        "Optional services: tavily=%s, amap=%s, notion=%s",
        settings.has_tavily(), settings.has_amap(), settings.has_notion(),
    )

    if errors:
        for error in errors:
            logger.warning(error)
        logger.warning("Please configure your API keys in ~/.iris/.env or project .env file")
```

**变更后**（详见 `02-adapter-system.md` 5.5）：

使用 try/except + 延迟导入 registry 做动态检查，fallback 到旧的 Settings 检查方式。

**注意点**：
- 使用 try/except 包裹 registry 导入，避免导入时序问题导致启动失败
- 保留 fallback 到旧的 Settings 检查方式
- `Settings` 类本身不做修改，保持向后兼容

**风险评估**：低。`_validate_config()` 只输出 warning 日志，不影响功能。

## 8. 不需要修改的文件

| 文件 | 原因 |
|------|------|
| `src/core/providers/basicagents_provider_registry.py` | 已使用 lowercase key，adapter 字段通过返回 dict 自然传递 |
| `src/core/providers/deepagents_provider_registry.py` | 不受影响（使用 `init_chat_model`） |
| `src/core/providers/subagents_provider_registry.py` | 不受影响（使用 `init_chat_model`） |
| `src/llm/instances/*.py` | instance 实现不变 |
| `src/agents/basicagents/adapters/*.py` | agent adapter 实现不变 |
| `src/agents/basicagents/config.py` | AgentConfig 通过 registry 获取配置，无硬编码 |
| `src/core/config/loader.py` | 配置加载机制不变 |
| `src/core/config/models.py` | IrisConfig 模型不变 |

## 9. 实施顺序

```
Phase 1: 配置层（无功能影响）
  1. 修改 config/llm/models/providers.json
  2. 修改 config/agents/basic/models/providers.json

Phase 2: Adapter 层
  3. 修改 llm/adapters/base.py（provider lowercase）
  4. 修改 llm/adapters/zhipu_adapter.py（provider_name 参数）
  5. 修改 llm/adapters/openai_adapter.py（provider_name 参数）
  6. 修改 llm/adapters/ollama_adapter.py（provider_name 参数）

Phase 3: Registry 层
  7. 修改 llm_provider_registry.py（key 小写化）

Phase 4: Manager 层（必须与 Phase 1-3 同时提交）
  8. 修改 llm_manager.py（移除 Enum，config-driven adapter）
  9. 修改 llm/managers/__init__.py（移除 LLMProvider 导出）
  10. 修改 llm/__init__.py（移除 LLMProvider 导出）
  11. 修改 agent_manager.py（config-driven adapter）

Phase 5: 验证层
  12. 修改 settings.py（_validate_config 动态化）

Phase 6: 测试
  13. 验证现有 provider（zhipu/openai/ollama）正常工作
  14. 验证新增 provider（tongyi）正常工作
  15. 验证用户级配置覆盖和合并
```

## 10. 测试验证清单

### 10.1 功能测试

| 测试项 | 预期结果 |
|--------|---------|
| `create_llm("zhipu", "glm-4.5-flash")` | 使用 ZhipuAdapter 创建 |
| `create_llm("openai", "gpt-4o")` | 使用 OpenAIAdapter 创建 |
| `create_llm("tongyi", "qwen3-max")` | 使用 OpenAIAdapter 创建（adapter="openai"） |
| `create_llm("ollama")` | 使用 OllamaAdapter 创建 |
| `create_agent("zhipu")` | 使用 ZhipuAgentAdapter |
| `create_agent("tongyi")` | 使用 OpenAIAgentAdapter |
| `get_available_providers()` | 包含 zhipu/openai/tongyi/ollama |
| `_provider_available("tongyi")` | 有 TONGYI_API_KEY 时返回 True |

### 10.2 兼容性测试

| 测试项 | 预期结果 |
|--------|---------|
| 旧格式 JSON（无 adapter 字段） | 正常工作，adapter 自动推断 |
| 旧格式 JSON（UPPERCASE key） | 正常工作，key 自动转小写 |
| 用户级配置新增 provider | 正常合并到 registry |
| 用户级配置新增 model | 正常合并到现有 provider |

### 10.3 错误处理测试

| 测试项 | 预期结果 |
|--------|---------|
| 未知 provider | `ValueError: Provider 'xxx' not found` |
| 未知 adapter 类型 | `ValueError: Unknown adapter type 'xxx'` |
| 缺失 API key | `ValueError: API key for provider 'xxx' not configured` |
| 缺失 adapter 字段（新配置） | fallback 推断为 "openai" |

## 11. 回滚方案

如果重构引入问题，回滚步骤：

1. 恢复 `config/llm/models/providers.json` 为原始大写 key 版本
2. 恢复 `llm_manager.py` 的 `LLMProvider` Enum 版本
3. 恢复 `agent_manager.py` 的硬编码 adapter_map
4. 恢复 `settings.py` 的硬编码 `_validate_config()`

配置文件和代码修改均在同一个 commit 或 PR 中，可通过 `git revert` 整体回滚。
