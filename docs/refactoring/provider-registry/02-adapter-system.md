# Adapter 类型系统与动态 API Key 加载

## 1. 概述

本文档定义 adapter 类型系统、ADAPTER_REGISTRY 映射、provider key 统一规范，
以及动态 API key 加载机制。

## 2. Adapter 类型系统

### 2.1 混合适配器策略

系统保留三种 adapter 实现，通过 JSON 配置中的 `adapter` 字段声明使用哪种：

| adapter 类型 | LLM 层 Adapter | LLM 层 Instance | BasicAgent 层 Adapter | 底层 SDK |
|-------------|---------------|-----------------|---------------------|---------|
| `"zhipu"` | `ZhipuAdapter` | `ZhipuAILLM` | `ZhipuAgentAdapter` | `ChatZhipuAI` |
| `"openai"` | `OpenAIAdapter` | `OpenAILLM` | `OpenAIAgentAdapter` | `ChatOpenAI` |
| `"ollama"` | `OllamaAdapter` | `OllamaLLM` | (不适用) | `ChatOllama` |

**设计决策**：
- 智谱沿用智谱专用 SDK（`ChatZhipuAI`），保持 thinking_mode 等特性
- tongyi 及所有自定义 provider 走 OpenAI-compatible 路径（`ChatOpenAI` + `base_url`）
- Ollama 保留专用路径（本地模型，无 API key，有 auto-detect 逻辑）

### 2.2 adapter 字段示例

```json
{
  "providers": {
    "zhipu": { "adapter": "zhipu", ... },
    "openai": { "adapter": "openai", ... },
    "tongyi": { "adapter": "openai", ... },
    "ollama": { "adapter": "ollama", ... },
    "my-custom-llm": { "adapter": "openai", ... }
  }
}
```

`tongyi` 和 `my-custom-llm` 都声明 `adapter: "openai"`，
因此复用 `OpenAIAdapter` / `OpenAILLM` / `OpenAIAgentAdapter`。

### 2.3 ADAPTER_REGISTRY

在 `llm_manager.py` 中定义全局适配器注册表，替代原来的硬编码映射：

```python
# Adapter type -> (AdapterClass, InstanceClass)
ADAPTER_REGISTRY = {
    "zhipu": (ZhipuAdapter, ZhipuAILLM),
    "openai": (OpenAIAdapter, OpenAILLM),
    "ollama": (OllamaAdapter, OllamaLLM),
}
```

在 `agent_manager.py` 中定义 BasicAgent 适配器注册表（使用延迟导入，与现有代码一致）：

```python
def _get_agent_adapter_class(adapter_type: str):
    """Lazy-load agent adapter class."""
    if adapter_type == "zhipu":
        from src.agents.basicagents.adapters.zhipu_agent_adapter import ZhipuAgentAdapter
        return ZhipuAgentAdapter
    elif adapter_type == "openai":
        from src.agents.basicagents.adapters.openai_agent_adapter import OpenAIAgentAdapter
        return OpenAIAgentAdapter
    return None
```

注意：
- adapter 注册表仍然在代码中定义（因为 adapter 类是 Python 类），
  但 provider -> adapter 的映射由 JSON 配置的 `adapter` 字段决定
- BasicAgent 只支持 `"zhipu"` 和 `"openai"` 两种 adapter 类型，
  Ollama 不支持 BasicAgent 模式（本地模型通常不支持 function calling agent）

### 2.4 adapter 解析流程

```
用户请求 create_llm(provider="tongyi", model="qwen3-max")
    |
    v
registry.get_provider_config("tongyi")
    |
    v
provider_config = { "adapter": "openai", "api_key_env": "TONGYI_API_KEY", ... }
    |
    v
adapter_type = provider_config["adapter"]  # "openai"
    |
    v
adapter_cls, instance_cls = ADAPTER_REGISTRY["openai"]
    |
    v
OpenAIAdapter(provider_name="tongyi", ...) + OpenAILLM 创建实例
    |
    v
adapter 内部通过 provider_name="tongyi" 从 registry 读取 tongyi 的配置
（base_url, api_key_env, models 等均为 tongyi 自己的配置，不是 openai 的）
```

### 2.5 Adapter 基类 provider 参数改造

**关键问题**：当前 adapter 基类 (`src/llm/adapters/base.py`) 的 `__init__` 接受
`provider` 参数，各子类硬编码传入自己的 provider 名（如 `provider="OPENAI"`）。
这意味着 adapter 内部通过 `self.provider` 从 registry 查找配置时，
始终查找的是 adapter 类型对应的 provider，而不是实际请求的 provider。

例如：`tongyi` 使用 `adapter: "openai"`，`OpenAIAdapter.__init__` 传入
`provider="OPENAI"`，导致 adapter 读取的是 OPENAI 的配置而非 tongyi 的。

**改造方案**：adapter 基类和子类需要接受外部传入的 `provider_name` 参数。

```python
# src/llm/adapters/base.py -- 改造后
class LLMAdapter(ABC):
    def __init__(
        self,
        provider: str,             # actual provider name (e.g., "tongyi")
        model: Optional[str],
        provider_registry: Optional[LLMProviderRegistry] = None,
        mode: str = "llm",
    ):
        self.provider_registry = provider_registry or default_registry
        self.provider = provider.lower()   # was provider.upper()
        self.mode = mode

        provider_config = self.provider_registry.get_provider_config(self.provider)
        if not provider_config:
            raise ValueError(f"Provider {self.provider} not found in registry")
        self._provider_config = provider_config
        ...
```

```python
# src/llm/adapters/openai_adapter.py -- 改造后
class OpenAIAdapter(LLMAdapter):
    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[LLMProviderRegistry] = None,
        mode: str = "llm",
        provider_name: str = "openai",  # new: allow override
    ):
        super().__init__(
            provider=provider_name,     # was hardcoded "OPENAI"
            model=model,
            provider_registry=provider_registry,
            mode=mode,
        )
```

```python
# src/llm/adapters/zhipu_adapter.py -- 改造后
class ZhipuAdapter(LLMAdapter):
    def __init__(
        self,
        model: Optional[str],
        provider_registry: Optional[LLMProviderRegistry] = None,
        mode: str = "llm",
        provider_name: str = "zhipu",  # new: allow override
    ):
        super().__init__(
            provider=provider_name,     # was hardcoded "ZHIPU"
            model=model,
            provider_registry=provider_registry,
            mode=mode,
        )
```

OllamaAdapter 同理，默认 `provider_name="ollama"`。

**LLMManager._create_adapter 传入 provider_name**：

```python
def _create_adapter(self, provider_name: str, model: str, mode: str):
    adapter_cls = ...  # from ADAPTER_REGISTRY
    return adapter_cls(
        model=model,
        provider_registry=self.provider_registry,
        mode=mode,
        provider_name=provider_name,  # pass actual provider name
    )
```

这样 `create_llm("tongyi", "qwen3-max")` 时：
- `adapter_type = "openai"` -> 使用 `OpenAIAdapter`
- `provider_name = "tongyi"` -> adapter 内部读取 tongyi 的配置
- adapter 的 `self.provider = "tongyi"`，从 registry 查到 tongyi 的
  `base_url`、`api_key_env`、`models` 等

## 3. 移除 LLMProvider Enum

### 3.1 当前 Enum 的使用点

| 使用位置 | 当前用法 | 改造方案 |
|---------|---------|---------|
| `LLMManager.__init__` | `_api_keys: Dict[LLMProvider, str]` | 改为 `Dict[str, str]`，key 为 provider name |
| `LLMManager._normalise_provider()` | `LLMProvider(provider_name)` 做枚举校验 | 改为 registry 查找校验 |
| `LLMManager._load_api_keys()` | 逐个检查 `settings.zhipu_api_key` | 改为遍历 registry，从 `api_key_env` 动态加载 |
| `LLMManager._provider_available()` | `LLMProvider.OLLAMA.value` 判断 | 改为检查 `adapter == "ollama"` |
| `LLMManager._prepare_instance_params()` | `provider_enum == LLMProvider.OLLAMA` | 改为 `adapter_type == "ollama"` |
| `LLMManager._resolve_api_key()` | `_api_keys.get(provider_enum)` | 改为 `_api_keys.get(provider_name)` |
| `LLMManager.set_api_key()` | `provider_enum == LLMProvider.OLLAMA` | 改为检查 adapter 类型 |

### 3.2 改造后的 _normalise_provider

```python
def _normalise_provider(self, provider: str) -> str:
    """Normalise provider name to lowercase and validate existence."""
    provider_name = str(provider).lower()
    if not self.provider_registry.get_provider_config(provider_name):
        raise ValueError(f"Provider '{provider_name}' not found in registry")
    return provider_name
```

返回值从 `Tuple[str, LLMProvider]` 简化为 `str`。

### 3.3 改造后的 _create_adapter (LLM)

```python
def _create_adapter(self, provider_name: str, model: str, mode: str):
    """Create adapter based on provider's configured adapter type."""
    provider_config = self._get_provider_config(provider_name)
    adapter_type = self._resolve_adapter_type(provider_name, provider_config)

    entry = ADAPTER_REGISTRY.get(adapter_type)
    if not entry:
        raise ValueError(
            f"Unknown adapter type '{adapter_type}' for provider '{provider_name}'"
        )

    adapter_cls = entry[0]
    return adapter_cls(
        model=model,
        provider_registry=self.provider_registry,
        mode=mode,
        provider_name=provider_name,  # pass actual provider name
    )
```

### 3.4 改造后的 _create_instance (LLM)

```python
def _create_instance(self, provider_name: str, params: Dict[str, Any]):
    """Create LLM instance based on provider's configured adapter type."""
    provider_config = self._get_provider_config(provider_name)
    adapter_type = provider_config.get("adapter")

    entry = ADAPTER_REGISTRY.get(adapter_type)
    if not entry:
        raise ValueError(
            f"Unknown adapter type '{adapter_type}' for provider '{provider_name}'"
        )

    instance_cls = entry[1]
    return instance_cls(**params)
```

### 3.5 改造后的 AgentManager._create_adapter (BasicAgent)

```python
def _create_adapter(self, provider: str, config: AgentConfig, **kwargs):
    """Create adapter based on provider's configured adapter type."""
    provider_config = self.provider_registry.get_provider_config(provider)
    if not provider_config:
        raise ProviderNotFoundError(
            provider, list(self.provider_registry.list_providers().keys())
        )

    adapter_type = provider_config.get("adapter")
    if not adapter_type:
        # Fallback for old configs
        known = {"zhipu": "zhipu", "ollama": "ollama"}
        adapter_type = known.get(provider, "openai")

    adapter_class = _get_agent_adapter_class(adapter_type)
    if not adapter_class:
        raise ProviderNotFoundError(
            provider, ["zhipu", "openai"]
        )

    return adapter_class(config=config, **kwargs)
```

## 4. Provider Key 统一

### 4.1 规范

所有 registry 统一使用 **lowercase** provider key：

```
zhipu, openai, tongyi, ollama, my-custom-llm
```

### 4.2 LLM Registry 变更

当前 `LLMProviderRegistry` 内部使用 UPPERCASE key：

```python
def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
    provider_key = provider.upper()  # UPPERCASE lookup
    return self._providers.get(provider_key)
```

改为 lowercase：

```python
def _load_from_config(self) -> None:
    ...
    providers_raw = config_data.get("providers", {})
    # Normalise keys to lowercase
    self._providers = {k.lower(): v for k, v in providers_raw.items()}

def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
    return self._providers.get(provider.lower())
```

### 4.3 JSON 配置同步

`config/llm/models/providers.json` 的 key 从大写改为小写：

```json
{
  "providers": {
    "zhipu": { ... },
    "openai": { ... },
    "ollama": { ... }
  }
}
```

为兼容过渡期，`_load_from_config()` 在加载时统一转小写，
因此旧的大写 key 配置仍然可以正常工作。

### 4.4 影响评估

LLM registry 的 key 大小写变更影响以下调用方：

| 调用方 | 当前传入 | 变更后 |
|--------|---------|--------|
| `LLMManager._normalise_provider()` | 返回 `provider.upper()` | 返回 `provider.lower()` |
| `LLMManager._get_provider_config()` | 传入大写 | 传入小写 |
| `LLMManager.create_llm()` | 全链路大写 | 全链路小写 |
| `LLMManager.get_available_providers()` | `provider_key.lower()` 转换 | 直接使用 |

由于 `_load_from_config()` 在加载阶段就统一了大小写，
调用方无论传入大写还是小写，`get_provider_config()` 内部都做 `.lower()` 处理。

## 5. 动态 API Key 加载

### 5.1 当前问题

`_load_api_keys()` 依赖 `Settings` 类的具体属性：

```python
if settings.zhipu_api_key:
    self._api_keys[LLMProvider.ZHIPU] = settings.zhipu_api_key
```

新增 provider 必须同时扩展 `Settings` 类。

### 5.2 改造方案

从 registry 中读取每个 provider 的 `api_key_env`，直接检查环境变量：

```python
def _load_api_keys(self) -> None:
    """Load API keys dynamically from provider configs."""
    try:
        self._api_keys = {}
        for provider_name, config in self.provider_registry.list_providers().items():
            api_key_env = config.get("api_key_env")
            if not api_key_env:
                continue  # No API key needed (e.g., Ollama)
            api_key = os.getenv(api_key_env)
            if api_key and not api_key.startswith("your_"):
                self._api_keys[provider_name] = api_key
    except Exception as exc:
        logger.warning("Failed to load API keys from registry: %s", exc)
```

这样新增 provider 只需在 JSON 中声明 `api_key_env`，
`.env` 中有对应的值即可自动被加载。

### 5.3 _resolve_api_key 改造

**行为变更**：当前代码在缓存中找不到 key 时直接报错。
改造后新增环境变量 fallback 路径，允许在运行时动态设置环境变量后被识别。

```python
def _resolve_api_key(self, provider_name: str, explicit_api_key: Optional[str]) -> str:
    """Resolve API key with priority: explicit > cached > env (new fallback)."""
    if explicit_api_key:
        return explicit_api_key

    cached = self._api_keys.get(provider_name)
    if cached:
        return cached

    # NEW: Fallback to live env check (supports runtime key addition)
    provider_config = self._get_provider_config(provider_name)
    env_name = provider_config.get("api_key_env", "API_KEY")
    api_key = os.getenv(env_name)
    if api_key and not api_key.startswith("your_"):
        self._api_keys[provider_name] = api_key
        return api_key

    raise ValueError(
        f"API key for provider '{provider_name}' not configured. "
        f"Please set environment variable {env_name}"
    )
```

### 5.4 _provider_available 改造

```python
def _provider_available(self, provider_name: str) -> bool:
    """Check if provider has available API key or doesn't need one."""
    provider_config = self.provider_registry.get_provider_config(provider_name)
    if not provider_config:
        return False
    # Providers without api_key_env (e.g., Ollama) are always available
    if not provider_config.get("api_key_env"):
        return True
    return provider_name in self._api_keys
```

### 5.5 Settings 类的变更

`Settings` 类本身不需要修改（保留现有属性以兼容直接引用的代码）。

需要修改的是 `_validate_config()` 函数，使其基于 registry 动态检查。

当前 `_validate_config()` 的实际实现（`settings.py:140-176`）包含：
错误收集列表、DEBUG 日志输出 provider 状态、对 zhipu/openai/anthropic 三个
provider 的硬编码检查。改造后替换为 registry-driven 动态检查。

```python
def _validate_config() -> None:
    """Validate configuration -- check at least one LLM provider is configured."""
    import os

    has_any_llm = False

    try:
        from src.core.providers import llm_registry
        for provider_name, config in llm_registry.list_providers().items():
            api_key_env = config.get("api_key_env")
            if not api_key_env:
                has_any_llm = True  # Ollama: no key needed
                continue
            key = os.getenv(api_key_env, "")
            if key and not key.startswith("your_"):
                has_any_llm = True
                logger.debug("LLM provider available: %s", provider_name)
    except Exception:
        # Fallback to legacy check if registry unavailable during import
        has_any_llm = (
            settings.has_zhipu()
            or settings.has_openai()
            or settings.has_anthropic()
            or settings.has_tongyi()
        )

    if not has_any_llm:
        logger.warning(
            "No LLM API key configured. "
            "Please run '/iris setup' or edit ~/.iris/.env"
        )
```

注意：
- `_validate_config()` 在模块加载时执行。由于 `settings.py` 和
  `llm_provider_registry.py` 之间存在导入时序，使用 try/except + 延迟导入
  避免循环导入问题
- fallback 路径保留旧的 Settings 检查方式，确保即使 registry 加载失败也能工作

### 5.6 set_api_key 改造

```python
def set_api_key(self, provider: str, api_key: str) -> None:
    """Set or override provider API key at runtime."""
    if not api_key:
        raise ValueError("API key must not be empty")
    provider_name = provider.lower()
    provider_config = self.provider_registry.get_provider_config(provider_name)
    if not provider_config:
        raise ValueError(f"Provider '{provider_name}' not found")
    if not provider_config.get("api_key_env"):
        logger.info(
            "Provider '%s' does not require an API key, ignoring",
            provider_name,
        )
        return
    self._api_keys[provider_name] = api_key
```

## 6. Ollama 特殊处理

Ollama 作为本地模型引擎有以下特殊行为需要保留：

| 特殊行为 | 处理方式 |
|---------|---------|
| 无 API key | `api_key_env: null` -> 跳过 key 加载 |
| auto-detect 模型 | `model == "auto"` 时调用 `adapter.resolve_auto_model()` |
| base_url 参数 | 使用 `OLLAMA_BASE_URL` 环境变量或默认 `http://localhost:11434` |
| timeout / keep_alive | 从 `extra_params` 读取 |

改造后通过 `adapter_type == "ollama"` 判断，而不是 `provider_enum == LLMProvider.OLLAMA`。

**行为变更**：当前 openai provider 的 base_url fallback 使用 `settings.openai_base_url`。
改造后改为使用 provider config 中的 `base_url` / `base_url_env`（通过 registry 的
`_resolve_base_url()` 方法）。这意味着 tongyi 等 provider 会使用各自配置中的
`base_url`，而不是共享 openai 的 base_url。

对于 openai provider 本身，其配置中的 `base_url_env: "OPENAI_BASE_URL"` 仍然会
读取 `OPENAI_BASE_URL` 环境变量，行为不变。

```python
def _prepare_instance_params(
    self,
    provider_name: str,
    adapter_type: str,
    provider_config: Dict[str, Any],
    adapter,
    adapter_params: Dict[str, Any],
    explicit_api_key: Optional[str],
    user_params: Dict[str, Any],
) -> Dict[str, Any]:
    params = adapter_params.copy()
    params.setdefault("model", adapter.model)

    if adapter_type == "ollama":
        base_url = params.get("base_url") or settings.ollama_base_url
        params["base_url"] = base_url
        params.setdefault("timeout", settings.ollama_timeout)
        params.setdefault("keep_alive", settings.ollama_keep_alive)
    else:
        api_key = self._resolve_api_key(provider_name, explicit_api_key)
        params["api_key"] = api_key
        # Delegate base_url resolution to registry (handles base_url_env)
        base_url = (
            params.get("base_url")
            or user_params.get("base_url")
            or self.provider_registry._resolve_base_url(provider_config)
        )
        if base_url:
            params["base_url"] = base_url

    return params
```

注意：`self.provider_registry._resolve_base_url()` 是 `LLMProviderRegistry`
已有的方法（`llm_provider_registry.py:259`），处理 `base_url_env` 环境变量优先、
`base_url` 配置值兜底的逻辑。这里直接复用，不新增方法。
